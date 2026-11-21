"""Premiere etape de l'API H1 : export HTTP d'un dossier en Bundle FHIR R5.

Lancer depuis ce dossier, avec TLS :
    python -m uvicorn app:app --host 127.0.0.1 --port 8000 \
        --ssl-keyfile ../securite/certificats/h1.key.pem \
        --ssl-certfile ../securite/certificats/h1.cert.pem

Sans TLS, uniquement sur un poste de test isole : SEC_MODE=local SEC_TLS_REQUIS=0.

Toutes les routes de dossier exigent un jeton Bearer ET la portee correspondante
(h1:export, h1:simulation, h1:import). Voir securite/README.md et
docs/securite/politique-securite.md. /health reste libre.

La route d'export est une route applicative, pas une transaction FHIR de reception.
"""

import oracledb
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

import h1_to_fhir as aller
import oracle_repo as repo
from valider import valider_bundle
from retour_api import extraire_consentement, verifier_bundle_retour

# Couche de securite commune aux deux hopitaux (dossier securite/ a la racine du
# depot). L'API se lance depuis son propre dossier, le package vit un niveau
# au-dessus : on ajoute donc la racine du depot au chemin d'import.
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).with_name(".env"), override=False)
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from securite import AccesRefuse, exiger_portee, installer_securite, lire_json_securise, tracer  # noqa: E402
from imagerie.dicomweb import entrepot_depuis_env  # noqa: E402
from imagerie.passerelle import routeur_dicomweb  # noqa: E402


class FHIRResponse(JSONResponse):
    media_type = "application/fhir+json"


CORPS_BUNDLE_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {"application/fhir+json": {"schema": {"type": "object"}}},
    }
}


app = FastAPI(
    title="API H1 - CHU Al Massira",
    version="0.4.0",
    description="Export des dossiers Oracle en Bundles FHIR R5 (5.0.0).",
)

# Authentification par portees, journal d'acces, en-tetes de securite,
# limitation de debit, exigence de TLS. A appeler avant les routes.
# Portees de ce service : h1:export, h1:simulation, h1:import, h1:audit,
# h1:consentement.lire, h1:consentement.gerer, h1:imagerie.lire.
SECURITE = installer_securite(app, service="H1")


def erreur(http, code, message):
    return FHIRResponse(
        status_code=http,
        content={
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": code, "diagnostics": message}],
        },
        headers={"Cache-Control": "no-store"},
    )


@app.exception_handler(RequestValidationError)
async def requete_invalide(request: Request, exc: RequestValidationError):
    return erreur(422, "invalid", "Corps JSON absent ou mal forme.")


# Les refus d'authentification et de droits sont traites par la couche
# securite/ : elle renvoie le meme OperationOutcome, ajoute l'en-tete
# WWW-Authenticate sur les 401 et ecrit la tentative dans le journal d'acces.


@app.get("/health", tags=["Etat du service"])
def etat_service():
    """Verifie que l'API repond. Ne teste pas la connexion Oracle."""
    return {"status": "ok", "service": "H1", "fhirVersion": "5.0.0"}


@app.get(
    "/api/patients/{ipp}/bundle",
    tags=["Export Oracle"],
    dependencies=[Depends(exiger_portee("export"))],
    response_class=FHIRResponse,
    responses={
        401: {"description": "Jeton Bearer absent ou invalide"},
        403: {"description": "Consentement refuse ou absent"},
        404: {"description": "Patient introuvable"},
        422: {"description": "Donnee obligatoire manquante"},
        500: {"description": "Bundle genere non conforme a la structure R5"},
        503: {"description": "Acces Oracle indisponible"},
    },
)
def exporter_dossier(ipp: str):
    """Lit Oracle et renvoie le Bundle. Aucun envoi a la clinique a cette etape.

Les elements ecartes par l'adaptateur sont comptes dans les en-tetes
X-H1-Rejection-Count et X-H1-Alert-Count et detailles dans le journal Oracle.
"""
    try:
        with repo.connexion() as conn:
            bundle, alertes, rejets = repo.exporter(conn, ipp=ipp)
    except (aller.ConsentementRefuse, aller.DonneeInvalide) as exc:
        return FHIRResponse(
            status_code=exc.http,
            content=aller.vers_operation_outcome(exc),
            headers={"Cache-Control": "no-store"},
        )
    except LookupError:
        return erreur(404, "not-found", "Patient introuvable dans H1.")
    except oracledb.DatabaseError:
        return erreur(503, "transient", "Acces a Oracle indisponible.")

    if valider_bundle(bundle):
        return erreur(500, "exception", "Le Bundle genere ne passe pas la validation de structure FHIR R5.")

    return FHIRResponse(
        content=bundle,
        headers={
            "Cache-Control": "no-store",
            "X-H1-Alert-Count": str(len(alertes)),
            "X-H1-Rejection-Count": str(len(rejets)),
        },
    )


@app.post(
    "/api/retours/simulation",
    tags=["Retour clinique"],
    dependencies=[Depends(exiger_portee("simulation"))],
    openapi_extra=CORPS_BUNDLE_OPENAPI,
    responses={
        401: {"description": "Jeton Bearer absent ou invalide"},
        403: {"description": "Consentement local absent ou refuse"},
        404: {"description": "Patient inconnu au CHU"},
        409: {"description": "Rapprochement d'identite ambigu"},
        422: {"description": "Bundle invalide ou incompatible avec le contrat"},
        503: {"description": "Acces Oracle indisponible"},
    },
)
async def simuler_retour(requete: Request):
    """Essaie l'import d'un retour puis annule les ecritures.

Route applicative de preparation : renvoie un rapport JSON de simulation,
pas un transaction-response et ne conserve aucune modification du dossier.
"""
    bundle = await lire_json_securise(requete)
    # Consent joint par la clinique : controle (403), puis retire avant l'import.
    try:
        bundle, alertes_consentement = extraire_consentement(bundle)
    except aller.ConsentementRefuse as exc:
        return erreur(403, "forbidden", str(exc))
    try:
        patient = verifier_bundle_retour(bundle)
    except (ValueError, TypeError, KeyError):
        return erreur(422, "invalid", "Bundle invalide : verifier la structure R5, les identifiants et les references internes.")

    try:
        with repo.connexion() as conn:
            try:
                ipp = repo.verifier_patient_retour(conn, patient)
                resultat = repo.importer(conn, bundle, creer_patients=False, simulation=True)
            finally:
                # Aussi en cas d'erreur de conversion ou d'ecriture intermediaire.
                conn.rollback()
    except aller.ConsentementRefuse as exc:
        return erreur(403, "forbidden", str(exc))
    except repo.IdentiteAmbigue as exc:
        return erreur(409, "conflict", str(exc))
    except LookupError:
        return erreur(404, "not-found", "Patient introuvable dans H1.")
    except (ValueError, TypeError, KeyError):
        return erreur(422, "invalid", "Les donnees du retour ne peuvent pas etre converties vers Oracle.")
    except oracledb.DatabaseError:
        return erreur(503, "transient", "La simulation Oracle a echoue ; aucune modification conservee.")

    # Le journal de securite ne porte que le pseudonyme du patient : l'IPP en
    # clair reste dans le journal Oracle, qui est deja protege par la base.
    tracer(requete, ressource=SECURITE.journal.pseudonyme(ipp))
    return JSONResponse(
        content={
            "simulation": True,
            "modifications_conservees": False,
            "patient_ipp": ipp,
            "lignes_par_table": {table: len(resultat[table]) for table, _ in repo.ORDRE_TABLES},
            "alertes": alertes_consentement + resultat["alertes"],
            "ignores": resultat["ignores"],
        },
        headers={"Cache-Control": "no-store"},
    )


@app.post(
    "/api/retours",
    tags=["Retour clinique"],
    dependencies=[Depends(exiger_portee("import"))],
    openapi_extra=CORPS_BUNDLE_OPENAPI,
    responses={
        401: {"description": "Jeton absent ou invalide"},
        403: {"description": "Consentement local absent ou refuse"},
        404: {"description": "Patient inconnu au CHU"},
        409: {"description": "Identite ambigue"},
        422: {"description": "Retour invalide ou non integrable"},
        503: {"description": "Import Oracle non confirme"},
    },
)
async def recevoir_retour(requete: Request):
    """Import definitif et journal atomiques. Rejouer les memes identifiants
metier met a jour les memes lignes par MERGE. Reponse : rapport JSON applicatif.
"""
    bundle = await lire_json_securise(requete)
    # Consent joint par la clinique : controle (403), puis retire avant l'import.
    try:
        bundle, alertes_consentement = extraire_consentement(bundle)
    except aller.ConsentementRefuse as exc:
        return erreur(403, "forbidden", str(exc))
    try:
        patient = verifier_bundle_retour(bundle, definitif=True)
    except (ValueError, TypeError, KeyError):
        return erreur(422, "invalid", "Retour invalide : verifier les identifiants stables, les references et la structure R5.")

    try:
        with repo.connexion() as conn:
            ipp, resultat = repo.recevoir_retour(conn, bundle, patient)
    except aller.ConsentementRefuse as exc:
        return erreur(403, "forbidden", str(exc))
    except repo.IdentiteAmbigue as exc:
        return erreur(409, "conflict", str(exc))
    except LookupError:
        return erreur(404, "not-found", "Patient introuvable dans H1.")
    except (aller.DonneeInvalide, ValueError, TypeError, KeyError):
        return erreur(422, "invalid", "Retour non integrable : aucune ecriture validee.")
    except oracledb.DatabaseError:
        return erreur(503, "transient", "Import Oracle non confirme. Verifier le journal avant une reprise.")

    tracer(requete, ressource=SECURITE.journal.pseudonyme(ipp))
    return JSONResponse(
        content={
            "simulation": False,
            "modifications_conservees": True,
            "patient_ipp": ipp,
            "lignes_par_table": {table: len(resultat[table]) for table, _ in repo.ORDRE_TABLES},
            "alertes": alertes_consentement + resultat["alertes"],
            "ignores": resultat["ignores"],
        },
        headers={"Cache-Control": "no-store"},
    )


# --------------------------------------------------------------------------
# Consentement au partage (loi 09-08) : etat, recueil, retrait
# --------------------------------------------------------------------------
REPONSES_CONSENTEMENT = {
    401: {"description": "Jeton Bearer absent ou invalide"},
    403: {"description": "Portee insuffisante"},
    404: {"description": "Patient introuvable"},
    503: {"description": "Acces Oracle indisponible"},
}


def _consentement(requete, ipp, action):
    """Execute `action(conn)` et traduit les erreurs en OperationOutcome."""
    try:
        with repo.connexion() as conn:
            etat = action(conn)
    except LookupError:
        return erreur(404, "not-found", "Patient introuvable dans H1.")
    except aller.CONS.ConsentementInvalide as exc:
        return erreur(422, "invalid", str(exc))
    except repo.ConsentementSansObjet as exc:
        return erreur(409, "conflict", str(exc))
    except oracledb.DatabaseError:
        return erreur(503, "transient", "Acces a Oracle indisponible ; consentement non modifie.")
    tracer(requete, ressource=SECURITE.journal.pseudonyme(ipp))
    return etat


@app.get(
    "/api/patients/{ipp}/consentement",
    tags=["Consentement"],
    dependencies=[Depends(exiger_portee("consentement.lire"))],
    responses=REPONSES_CONSENTEMENT,
)
def lire_consentement(ipp: str, requete: Request):
    """Consentement en vigueur, decision de partage (partage_autorise, motif) et historique."""
    etat = _consentement(requete, ipp,
                         lambda conn: repo.etat_consentement(ipp, repo.lire_consentements(conn, ipp)))
    return etat if isinstance(etat, JSONResponse) else JSONResponse(etat, headers={"Cache-Control": "no-store"})


@app.post(
    "/api/patients/{ipp}/consentement",
    tags=["Consentement"],
    status_code=201,
    responses={**REPONSES_CONSENTEMENT, 422: {"description": "Saisie incoherente"}},
)
async def recueillir_consentement(ipp: str, requete: Request,
                                  appelant=Depends(exiger_portee("consentement.gerer"))):
    """Nouvelle version du consentement (une ligne de plus, l'ancienne est conservee).
Corps : statut (actif|refuse), recueilli_par ; facultatifs : debut, fin,
destinataires (H2), categories_exclues (imagerie, comptes_rendus, allergies), signataire.
"""
    corps = await lire_json_securise(requete)
    etat = _consentement(requete, ipp, lambda conn: repo.enregistrer_consentement(
        conn, ipp, corps, agent=appelant.client))
    return etat if isinstance(etat, JSONResponse) else JSONResponse(
        etat, status_code=201, headers={"Cache-Control": "no-store"})


@app.post(
    "/api/patients/{ipp}/consentement/retrait",
    tags=["Consentement"],
    responses={**REPONSES_CONSENTEMENT, 409: {"description": "Aucun consentement actif"},
               422: {"description": "Saisie incoherente"}},
)
async def retirer_consentement(ipp: str, requete: Request,
                               appelant=Depends(exiger_portee("consentement.gerer"))):
    """Retrait du consentement (droit d'opposition). Corps : recueilli_par, motif.
Les exports suivants du dossier sont refuses (403).
"""
    corps = await lire_json_securise(requete)
    etat = _consentement(requete, ipp, lambda conn: repo.retirer_consentement(
        conn, ipp, corps, agent=appelant.client))
    return etat if isinstance(etat, JSONResponse) else JSONResponse(etat, headers={"Cache-Control": "no-store"})


# --------------------------------------------------------------------------
# Imagerie DICOM : passerelle DICOMweb devant le PACS du CHU (imagerie/passerelle.py)
# GET /dicom-web/studies/{uid}[/metadata], portee h1:imagerie.lire.
# Les images du CHU viennent de la clinique (recuperer_imagerie.py) : elles ne
# lui sont jamais renvoyees (anti-boucle). Seul le personnel du CHU les consulte.
# --------------------------------------------------------------------------
PACS = entrepot_depuis_env("H1")        # H1_ORTHANC_URL, _UTILISATEUR, _MOT_DE_PASSE ; None = 503
CLIENTS_EXTERNES = {"h2-clinique"}


def autoriser_imagerie(appelant, study_uid):
    if appelant.client in CLIENTS_EXTERNES:
        raise AccesRefuse(403, "forbidden", "Anti-boucle : ces images proviennent de la clinique.",
                          "imagerie_anti_boucle")
    try:
        with repo.connexion() as conn:
            ipp = repo.patient_de_l_etude(conn, study_uid)
    except oracledb.DatabaseError as exc:
        raise AccesRefuse(503, "transient", "Acces a Oracle indisponible.", "oracle") from exc
    if ipp is None:
        raise AccesRefuse(404, "not-found", "Etude d'imagerie inconnue du CHU.", "etude_inconnue")
    return SECURITE.journal.pseudonyme(ipp)


app.include_router(routeur_dicomweb(entrepot=lambda: PACS, autoriser=autoriser_imagerie))
