"""
api_h2.py — API REST FHIR R5 de l'Hôpital 2 (Clinique Al Baçar / MongoDB)          v3.0
==================================================================================
Même rôle et mêmes règles que l'API de H1 (CHU / Oracle) : chaque hôpital ENVOIE et REÇOIT.

ROUTES « ÉCHANGE » (miroir de l'API H1)
  GET  /health                          l'API répond-elle ? (sans authentification)
  GET  /api/patients/{id}/bundle        ENVOYER : Bundle transaction d'un patient H2
  POST /api/retours/simulation          RECEVOIR à blanc : tout est contrôlé, rien n'est écrit
  POST /api/retours                     RECEVOIR pour de bon (idempotent)

ROUTES FHIR STANDARD
  GET  /metadata                        CapabilityStatement (sans authentification)
  POST /Patient                         enregistre UN patient (sans son dossier)
  GET  /Patient/{id}                    lit un patient
  GET  /Patient?identifier=system|val   cherche un patient (ex. urn:ma:cin|AB123456)
  POST /Bundle                          = POST /api/retours
  GET  /Patient/{id}/$everything        = GET /api/patients/{id}/bundle

AUTHENTIFICATION   Authorization: Bearer <jeton>   OBLIGATOIRE sur toute route de dossier.
                   Chaque route exige une portée précise (h2:export, h2:import…) : voir
                   securite/ et docs/securite/politique-securite.md. Sans jeton configuré,
                   les routes de dossier répondent 503 — jamais en accès libre.
EN-TÊTE OPTIONNEL  X-Exchange-Id: <uuid>   identifiant d'échange : rejouer = sans danger

CODES  200 OK · 201 patient créé · 400 requête illisible · 401 jeton · 403 consentement,
       portée insuffisante ou TLS absent · 404 patient inconnu · 409 identité ambiguë /
       doublon · 413 corps trop volumineux · 422 Bundle non conforme · 429 débit dépassé
       503 base indisponible, écriture non confirmée ou authentification non configurée

LANCER    uvicorn api_h2:app --port 8002 --ssl-keyfile ../securite/certificats/h2.key.pem \
                  --ssl-certfile ../securite/certificats/h2.cert.pem
          (sans TLS, uniquement sur un poste de test : SEC_MODE=local SEC_TLS_REQUIS=0)
VARIABLES MONGO_URI · MONGO_DB (défaut hopital2) · FHIR_BASE_URL · H1_IPP_SYSTEM
          jetons et sécurité : voir .env.example et securite/README.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.exceptions import HTTPException as StarletteHTTPException

import adaptateur_h2_fhir as h2_vers_fhir
import echange
from echange import ErreurEchange
from stores import DejaExistant, StoreIndisponible, StoreMemoire, StoreMongo

# ── couche de securite commune (dossier securite/ a la racine du depot) ──────
# L'API se lance depuis son propre dossier (uvicorn api_h2:app) alors que le
# package securite vit un niveau au-dessus : on ajoute donc la racine du depot
# au chemin d'import. Voir securite/README.md.
_RACINE = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).with_name(".env"), override=False)
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from securite import exiger_portee, installer_securite, lire_json_securise, tracer  # noqa: E402

VERSION = "3.0"
FHIR_JSON = "application/fhir+json"

# base des fullUrl : à régler sur l'adresse HTTPS réelle de l'API.
h2_vers_fhir.FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "https://localhost:8002/fhir")

def uri_mongo() -> Optional[str]:
    """Construit l'URI locale sans exposer le mot de passe dans la configuration Docker."""
    if os.getenv("MONGO_URI"):
        return os.environ["MONGO_URI"]
    utilisateur = os.getenv("MONGO_UTILISATEUR")
    mot_de_passe = os.getenv("MONGO_MOT_DE_PASSE")
    if utilisateur and mot_de_passe:
        hote = os.getenv("MONGO_HOTE", "127.0.0.1")
        return (f"mongodb://{quote_plus(utilisateur)}:{quote_plus(mot_de_passe)}"
                f"@{hote}:27017/?authSource=admin")
    return None


_URI_MONGO = uri_mongo()
STORE = (StoreMongo(_URI_MONGO, os.getenv("MONGO_DB", "hopital2"))
         if _URI_MONGO else StoreMemoire())

app = FastAPI(title="API FHIR R5 – Hôpital 2 (Clinique Al Baçar)", version=VERSION)

# Branche l'authentification par portées, le journal d'accès, les en-têtes de
# sécurité, la limitation de débit et l'exigence de TLS. À appeler avant les
# routes : l'intergiciel enveloppe toute l'application.
SECURITE = installer_securite(app, service="H2")


# ═════════════════════════════════════════════════════════════════════════════
# Erreurs : toujours une ressource FHIR OperationOutcome
# ═════════════════════════════════════════════════════════════════════════════
def reponse(contenu: dict, code: int = 200, entetes: Optional[dict] = None, media: str = FHIR_JSON):
    return JSONResponse(contenu, status_code=code, media_type=media, headers=entetes)


def operation_outcome(gravite: str, type_fhir: str, message: str) -> dict:
    return {"resourceType": "OperationOutcome",
            "issue": [{"severity": gravite, "code": type_fhir, "diagnostics": message}]}


@app.exception_handler(ErreurEchange)
async def _erreur_echange(_, exc: ErreurEchange):
    entetes = {"WWW-Authenticate": "Bearer"} if exc.code == 401 else None
    return reponse(operation_outcome("error", exc.type_fhir, exc.message), exc.code, entetes)


@app.exception_handler(StoreIndisponible)
async def _store_indisponible(_, exc: StoreIndisponible):
    return reponse(operation_outcome(
        "error", "transient",
        "Base de données indisponible ou écriture non confirmée. Renvoyez la même requête "
        "(même X-Exchange-Id) : le rejeu ne crée pas de doublon."), 503, {"Retry-After": "30"})


@app.exception_handler(DejaExistant)
async def _deja_existant(_, exc: DejaExistant):
    return reponse(operation_outcome("error", "duplicate", f"Le patient {exc} existe déjà."), 409)


@app.exception_handler(RequestValidationError)
async def _requete_invalide(_, exc: RequestValidationError):
    return reponse(operation_outcome("error", "invalid", "Paramètre de requête invalide."), 400)


@app.exception_handler(StarletteHTTPException)
async def _http(_, exc: StarletteHTTPException):
    type_fhir = {404: "not-found", 405: "not-supported"}.get(exc.status_code, "processing")
    return reponse(operation_outcome("error", type_fhir, str(exc.detail)), exc.status_code)


@app.exception_handler(Exception)
async def _inattendu(_, exc: Exception):
    return reponse(operation_outcome("fatal", "exception", "Erreur interne du serveur."), 500)


# ═════════════════════════════════════════════════════════════════════════════
# Authentification et droits d'accès — couche securite/
# ═════════════════════════════════════════════════════════════════════════════
# Chaque route déclare la PORTÉE qu'elle exige, et non plus un simple « jeton
# valide ou non ». Un jeton qui n'a le droit que d'envoyer un retour ne peut pas
# lire les dossiers de la clinique. Si aucune source de jetons n'est configurée,
# les routes répondent 503 : l'API ne sert jamais de données de santé sans
# authentification (l'ancienne version passait en « mode développement » ouvert).
#
# Portées de ce service : h2:export, h2:simulation, h2:import, h2:patient.lire,
# h2:patient.creer, h2:patient.chercher, h2:audit, h2:annuaire,
# h2:consentement.lire, h2:consentement.gerer.

# Hôpital d'où provient chaque client : c'est lui, et non un paramètre de
# requête, qui détermine le destinataire d'un export. Sinon un appelant pourrait
# déclarer un autre destinataire et récupérer ainsi les données que son propre
# établissement nous avait transmises, en contournant l'anti-boucle.
HOPITAL_DU_CLIENT = {"h1-chu": "H1", "h2-clinique": "H2"}


def destinataire_de(appelant, demande: Optional[str]) -> str:
    """Destinataire effectif d'un export, déduit de l'identité du jeton."""
    impose = HOPITAL_DU_CLIENT.get(appelant.client)
    if impose:
        if demande and demande.strip().upper() != impose:
            raise ErreurEchange(
                403, "forbidden",
                "Ce jeton ne peut exporter que vers " + impose + ".")
        return impose
    # Outils internes de la clinique : le destinataire reste un choix explicite.
    return (demande or "H1").strip().upper()


def exiger_option(appelant, active: bool, portee: str, libelle: str) -> None:
    """Une option qui élargit les données renvoyées exige sa propre portée."""
    if active and not appelant.autorise(portee):
        raise ErreurEchange(
            403, "forbidden",
            "L'option " + libelle + " exige la portée " + portee + ".")


async def lire_json(requete: Request):
    """Corps JSON de la requête, avec limite de taille (voir SEC_TAILLE_MAX_CORPS)."""
    return await lire_json_securise(requete)


# ═════════════════════════════════════════════════════════════════════════════
# Routes publiques
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/health")
def sante():
    try:
        base = STORE.ping()
    except StoreIndisponible:
        base = False
    # L'état de l'authentification n'est PAS publié : annoncer « authentification
    # désactivée » à un appelant anonyme lui indiquerait où insister.
    corps = {"statut": "ok" if base else "degrade", "base": "disponible" if base else "indisponible",
             "version": VERSION, "fhir": "5.0.0"}
    return JSONResponse(corps, status_code=200 if base else 503)


@app.get("/metadata")
def metadata():
    return reponse({
        "resourceType": "CapabilityStatement", "status": "active", "date": "2026-11-21",
        "kind": "instance", "fhirVersion": "5.0.0", "format": ["json"],
        "software": {"name": "API FHIR Hôpital 2 – Clinique Al Baçar", "version": VERSION},
        "rest": [{
            "mode": "server",
            "documentation": "Dossier complet : GET /api/patients/{id}/bundle (envoi) ; "
                             "POST /api/retours ou POST /Bundle (réception, idempotent). "
                             "Bundle transaction : Patient en création conditionnelle (ifNoneExist CIN), "
                             "autres ressources en PUT à identifiant stable.",
            "security": {"description": "Jeton Bearer avec portées par client "
                                        "(h2:export, h2:simulation, h2:import, …), "
                                        "transport HTTPS exigé."},
            "resource": [
                {"type": "Patient",
                 "interaction": [{"code": "read"}, {"code": "create"}, {"code": "search-type"}],
                 "searchParam": [{"name": "identifier", "type": "token"}],
                 "operation": [{"name": "everything",
                                "definition": "http://hl7.org/fhir/OperationDefinition/Patient-everything"}]},
                {"type": "Bundle", "interaction": [{"code": "create"}]},
            ],
        }],
    })


# ═════════════════════════════════════════════════════════════════════════════
# Routes d'échange
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/api/patients/{patient_id}/bundle")
def bundle_patient(patient_id: str,
                   appelant=Depends(exiger_portee("export")),
                   destinataire: Optional[str] = Query(
                       default=None, description="hôpital destinataire ; imposé par le jeton"),
                   inclure_audit: bool = Query(default=False, description="exige la portée h2:audit"),
                   inclure_catalogue: bool = Query(
                       default=False, description="annuaire complet ; exige la portée h2:annuaire")):
    """ENVOYER : Bundle transaction du dossier. 403 si consentement non actif. Les données reçues
    du destinataire ne lui sont jamais renvoyées (anti-boucle)."""
    exiger_option(appelant, inclure_audit, "h2:audit", "inclure_audit")
    exiger_option(appelant, inclure_catalogue, "h2:annuaire", "inclure_catalogue")
    return reponse(echange.exporter(STORE, patient_id,
                                    destinataire=destinataire_de(appelant, destinataire),
                                    inclure_audit=inclure_audit, inclure_catalogue=inclure_catalogue))


async def _recevoir(requete: Request, x_exchange_id: Optional[str], commit: bool):
    bundle = await lire_json(requete)
    rapport, code = echange.importer(bundle, STORE, commit=commit, exchange_id=x_exchange_id)
    # L'identifiant d'échange part aussi dans le journal d'accès : il relie la
    # ligne de sécurité à la ligne métier du dossier patient.
    tracer(requete, echange_id=rapport["echange_id"])
    entetes = {"X-Exchange-Id": rapport["echange_id"]}
    if rapport["patient_id"] and commit:
        entetes["Location"] = f"/Patient/{rapport['patient_id']}"
    return reponse(rapport, code, entetes, media="application/json")


@app.post("/api/retours/simulation", dependencies=[Depends(exiger_portee("simulation"))])
async def simuler_reception(requete: Request, x_exchange_id: Optional[str] = Header(default=None)):
    """RECEVOIR à blanc : mêmes contrôles que l'import, aucune écriture conservée."""
    return await _recevoir(requete, x_exchange_id, commit=False)


@app.post("/api/retours", dependencies=[Depends(exiger_portee("import"))])
async def recevoir(requete: Request, x_exchange_id: Optional[str] = Header(default=None)):
    """RECEVOIR : crée le patient (201) ou complète son dossier (200). Rejeu sans doublon."""
    return await _recevoir(requete, x_exchange_id, commit=True)


# ═════════════════════════════════════════════════════════════════════════════
# Routes FHIR standard
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/Bundle", dependencies=[Depends(exiger_portee("import"))])
async def recevoir_bundle(requete: Request, x_exchange_id: Optional[str] = Header(default=None)):
    return await _recevoir(requete, x_exchange_id, commit=True)


# ═════════════════════════════════════════════════════════════════════════════
# Consentement au partage (loi 09-08) : état, recueil, retrait
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/api/patients/{patient_id}/consentement",
         dependencies=[Depends(exiger_portee("consentement.lire"))])
def lire_consentement(patient_id: str):
    """Consentement en vigueur, décision de partage (partage_autorise, motif) et historique."""
    return reponse(echange.lire_consentement(STORE, patient_id), media="application/json")


@app.post("/api/patients/{patient_id}/consentement")
async def recueillir_consentement(patient_id: str, requete: Request,
                                  appelant=Depends(exiger_portee("consentement.gerer"))):
    """Nouvelle version du consentement. Corps : statut (actif|refuse), recueilli_par,
    et facultativement debut, fin, destinataires, categories_exclues, signataire."""
    corps = await lire_json(requete)
    etat = echange.enregistrer_consentement(STORE, patient_id, corps, agent=appelant.client)
    return reponse(etat, 201, media="application/json")


@app.post("/api/patients/{patient_id}/consentement/retrait")
async def retirer_consentement(patient_id: str, requete: Request,
                               appelant=Depends(exiger_portee("consentement.gerer"))):
    """Retrait (droit d'opposition). Corps : recueilli_par, motif (facultatif).
    Les exports suivants sont refusés (403) ; client_envoi annule les envois en attente."""
    corps = await lire_json(requete)
    etat = echange.retirer_consentement(STORE, patient_id, corps, agent=appelant.client)
    return reponse(etat, media="application/json")


@app.get("/Patient/{patient_id}/$everything")
def dossier_complet(patient_id: str,
                    appelant=Depends(exiger_portee("export")),
                    destinataire: Optional[str] = Query(default=None)):
    return reponse(echange.exporter(STORE, patient_id,
                                    destinataire=destinataire_de(appelant, destinataire)))


@app.post("/Patient", dependencies=[Depends(exiger_portee("patient.creer"))])
async def creer_patient(requete: Request):
    patient = await lire_json(requete)
    doc = echange.creer_patient_seul(patient, STORE)
    return reponse(echange.patient_fhir(doc), 201, {"Location": f"/Patient/{doc['patient_id']}"})


@app.get("/Patient/{patient_id}", dependencies=[Depends(exiger_portee("patient.lire"))])
def lire_patient(patient_id: str):
    return reponse(echange.patient_fhir(echange.trouver_patient(STORE, patient_id)))


# Le paramètre `identifier` peut contenir un CIN : sa valeur est masquée dans le
# journal de sécurité (securite/audit.py, PARAMETRES_SENSIBLES).
@app.get("/Patient", dependencies=[Depends(exiger_portee("patient.chercher"))])
def chercher_patients(identifier: Optional[str] = Query(
        default=None, description="valeur  ou  system|valeur   (ex. urn:ma:cin|AB123456)")):
    if identifier:
        system, _, valeur = identifier.rpartition("|")
        docs = STORE.find_all_by_identifier(system or None, valeur)
    else:
        docs = STORE.all(100)
    return reponse({
        "resourceType": "Bundle", "type": "searchset", "total": len(docs),
        "entry": [{"fullUrl": f"{h2_vers_fhir.FHIR_BASE_URL}/Patient/{d['patient_id']}",
                   "resource": echange.patient_fhir(d)} for d in docs],
    })
