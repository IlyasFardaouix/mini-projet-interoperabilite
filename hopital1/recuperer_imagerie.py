"""
Récupère dans le PACS du CHU les images DICOM annoncées par les retours de la clinique.

Un retour FHIR de la clinique décrit ses études d'imagerie (ImagingStudy, rangées
dans etude_imagerie avec url_pacs). Les images restent chez la clinique ; ce
module les télécharge depuis SA PASSERELLE DICOMweb (WADO-RS, jeton du CHU,
consentement vérifié par la clinique), contrôle qu'elles appartiennent bien à
l'étude annoncée, les dépose dans l'Orthanc du CHU (STOW-RS), puis pointe
url_pacs vers la passerelle du CHU.

Sécurité :
- seule l'adresse configurée H2_DICOMWEB_URL est appelée. Une url_pacs différente
  (Bundle forgé, erreur de saisie) n'est jamais suivie : le jeton du CHU ne part
  pas vers une adresse inconnue ;
- une instance dont le StudyInstanceUID diffère de l'étude demandée fait
  rejeter toute l'étude.

    cd hopital1
    ..\\.venv\\Scripts\\python.exe recuperer_imagerie.py

Variables : H2_DICOMWEB_URL, H1_JETON_VERS_H2 (jeton du client h1-chu, portée
h2:imagerie.lire), H1_ORTHANC_URL / _UTILISATEUR / _MOT_DE_PASSE, H1_DICOMWEB_URL.
Rejouable : les études déjà récupérées sont ignorées.
"""

import os
import sys
from pathlib import Path

_RACINE = str(Path(__file__).resolve().parent.parent)
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from imagerie.dicom import depuis_octets, verifier_etude  # noqa: E402
from imagerie.dicomweb import ErreurDistante, ErreurPacs, recuperer_etude_distante  # noqa: E402

URL_LOCALE = os.getenv("H1_DICOMWEB_URL", "https://127.0.0.1:8000/dicom-web")
STATUTS_FINAUX = ("RECUPEREE", "REFUSEE", "URL_REFUSEE", "INCOHERENTE", "ABSENTE")

SQL_A_RECUPERER = (
    "SELECT id_etude, ipp, study_uid, url_pacs, statut FROM etude_imagerie "
    "WHERE study_uid IS NOT NULL AND url_pacs IS NOT NULL "
    "AND (statut IS NULL OR statut NOT IN ('" + "','".join(STATUTS_FINAUX) + "')) "
    "ORDER BY id_etude")


SQL_A_RECUPERER_PATIENT = SQL_A_RECUPERER.replace("ORDER BY id_etude", "AND ipp = :ipp ORDER BY id_etude")


def _lignes(cur):
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _marquer(conn, etude, statut, details, *, url=None, instances=None):
    import oracle_repo as repo

    with conn.cursor() as cur:
        cur.execute("UPDATE etude_imagerie SET statut = :s, url_pacs = NVL(:u, url_pacs), "
                    "nb_instances = NVL(:n, nb_instances) WHERE id_etude = :i",
                    s=statut, u=url, n=instances, i=etude["id_etude"])
    repo.journaliser(conn, "RETOUR", etude["ipp"], "OK" if statut == "RECUPEREE" else "REFUSE",
                     {"imagerie": statut, "study_uid": etude["study_uid"], **details},
                     commit=False, strict=True)
    conn.commit()


def recuperer(conn, client_h2, pacs_h1, *, base_h2: str, url_locale: str = URL_LOCALE, ipp=None) -> list:
    """Traite chaque étude en attente (celles du patient `ipp` si précisé) ; renvoie un bilan par étude."""
    base = base_h2.rstrip("/")
    with conn.cursor() as cur:
        if ipp is None:
            cur.execute(SQL_A_RECUPERER)
        else:
            cur.execute(SQL_A_RECUPERER_PATIENT, ipp=ipp)
        etudes = _lignes(cur)
    bilan = []
    for etude in etudes:
        uid = str(etude["study_uid"]).removeprefix("urn:oid:")     # anciennes lignes : « urn:oid:<UID> » (notation FHIR)
        annoncee = str(etude["url_pacs"]).rstrip("/")
        if annoncee not in (base, url_locale.rstrip("/")):
            _marquer(conn, etude, "URL_REFUSEE", {"motif": "adresse differente de H2_DICOMWEB_URL"})
            bilan.append({"study_uid": uid, "statut": "URL_REFUSEE"})
            continue
        try:
            octets = recuperer_etude_distante(client_h2, base, uid)
        except ErreurDistante as exc:
            if exc.http in (403, 404):                       # refus de la clinique ou étude absente
                statut = "REFUSEE" if exc.http == 403 else "ABSENTE"
                _marquer(conn, etude, statut, {"http": exc.http})
                bilan.append({"study_uid": uid, "statut": statut, "http": exc.http})
            else:                                            # passerelle indisponible : on réessaiera
                bilan.append({"study_uid": uid, "statut": "EN_ATTENTE", "detail": str(exc)})
            continue
        erreur = verifier_etude([depuis_octets(o) for o in octets], uid) if octets else "etude vide"
        if erreur:
            _marquer(conn, etude, "INCOHERENTE", {"motif": erreur})
            bilan.append({"study_uid": uid, "statut": "INCOHERENTE", "detail": erreur})
            continue
        try:
            pacs_h1.stocker(octets)
        except ErreurPacs as exc:
            bilan.append({"study_uid": uid, "statut": "EN_ATTENTE", "detail": str(exc)})
            continue
        _marquer(conn, etude, "RECUPEREE", {"instances": len(octets)},
                 url=url_locale, instances=len(octets))
        bilan.append({"study_uid": uid, "statut": "RECUPEREE", "instances": len(octets)})
    return bilan


def recuperation_automatique_active() -> bool:
    """Les images suivent-elles le dossier tout de suite ? Oui en démonstration (DEMO=1) ou avec
    H1_IMAGERIE_AUTO=1 ; sinon, on lance recuperer_imagerie.py à la main."""
    return os.getenv("DEMO") == "1" or os.getenv("H1_IMAGERIE_AUTO") == "1"


def recuperer_apres_retour(conn, ipp, *, client=None, pacs=None) -> list:
    """Récupère, juste après l'import d'un retour, les images du patient `ipp`.

    Ne lève jamais d'exception : l'import du dossier est déjà validé, et une image non transférée
    reste « en attente » (relancée par recuperer_imagerie.py). Renvoie un bilan par étude (liste vide :
    aucune image à récupérer), ou None si la récupération automatique est désactivée ou non configurée."""
    if not recuperation_automatique_active():
        return None
    base = (os.getenv("H2_DICOMWEB_URL") or "").strip()
    try:
        if pacs is None:
            from imagerie.dicomweb import entrepot_depuis_env
            pacs = entrepot_depuis_env("H1")
        if not base or pacs is None:
            return None
        if client is None:
            from securite import client_securise
            client = client_securise(base, variable_jeton="H1_JETON_VERS_H2")
        return recuperer(conn, client, pacs, base_h2=base, ipp=ipp)
    except Exception as exc:                                  # noqa: BLE001 - voir docstring
        return [{"study_uid": None, "statut": "EN_ATTENTE", "detail": type(exc).__name__}]


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"), override=False)
    import oracle_repo as repo
    from imagerie.dicomweb import entrepot_depuis_env
    from securite import client_securise

    base = (os.getenv("H2_DICOMWEB_URL") or "").strip()
    pacs = entrepot_depuis_env("H1")
    if not base or pacs is None:
        print("Définir H2_DICOMWEB_URL et H1_ORTHANC_URL dans hopital1/.env.", file=sys.stderr)
        return 2
    client = client_securise(base, variable_jeton="H1_JETON_VERS_H2")
    with repo.connexion() as conn:
        bilan = recuperer(conn, client, pacs, base_h2=base)
    for ligne in bilan:
        print(f"{ligne['study_uid']:<40} {ligne['statut']}" + (f"  ({ligne['detail']})" if ligne.get("detail") else ""))
    print(f"{sum(1 for b in bilan if b['statut'] == 'RECUPEREE')} étude(s) récupérée(s) sur {len(bilan)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
