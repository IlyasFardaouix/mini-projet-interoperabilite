"""
charger_dicom.py — remplit le PACS Orthanc de la clinique avec des images DE DÉMONSTRATION
=========================================================================================
Pour chaque étude d'imagerie déjà décrite dans MongoDB (visits[].imaging[]), fabrique
des photographies du fond d'œil synthétiques au format DICOM, avec le même
StudyInstanceUID, puis les dépose dans le PACS (STOW-RS). L'identifiant de série
produit est enregistré dans le dossier (imaging.series_uid) : les ImagingStudy
exportés en FHIR décrivent alors exactement ce que contient le PACS.

Aucune image réelle : les pixels sont dessinés, les identités sont celles des
patients fictifs du jeu de démonstration.

    cd hopital2
    ..\\.venv\\Scripts\\python.exe charger_dicom.py              # MongoDB et PACS du .env
    ..\\.venv\\Scripts\\python.exe charger_dicom.py --patient P2-0051

Variables : H2_ORTHANC_URL (ex. http://127.0.0.1:8042/dicom-web),
H2_ORTHANC_UTILISATEUR, H2_ORTHANC_MOT_DE_PASSE ; MongoDB comme pour l'API.
Rejouable : un dépôt identique ne crée pas de doublon dans Orthanc.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_RACINE = str(Path(__file__).resolve().parent.parent)
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from imagerie.dicom import generer_etude, uid_serie, vers_octets  # noqa: E402

ETABLISSEMENT = "Clinique Al Bacar"


def _date(visite: dict, etude: dict):
    brut = etude.get("started_at") or visite.get("start") or visite.get("date") or ""
    try:
        return datetime.fromisoformat(str(brut).replace("Z", "")[:19])
    except ValueError:
        return None


def charger(store, pacs, *, patients=None) -> dict:
    """Dépose les études dans `pacs` et renseigne series_uid dans `store`."""
    bilan = {"etudes": 0, "instances": 0, "patients": 0}
    docs = [store.get(p) for p in patients] if patients else store.all(100000)
    for doc in filter(None, docs):
        modifie = False
        patient = {"id": doc["patient_id"], "nom": doc.get("last_name"), "prenom": doc.get("first_name"),
                   "naissance": doc.get("birth_date"), "sexe": {1: "M", 2: "F"}.get(doc.get("sex"), "O")}
        for visite in doc.get("visits", []):
            for etude in visite.get("imaging", []):
                if not etude.get("study_uid") or etude.get("modality", "OP") != "OP":
                    continue
                instances = generer_etude(patient, {**etude, "date": _date(visite, etude)},
                                          etablissement=ETABLISSEMENT)
                pacs.stocker([vers_octets(ds) for ds in instances])
                bilan["etudes"] += 1
                bilan["instances"] += len(instances)
                if etude.get("series_uid") != uid_serie(etude["study_uid"]):
                    etude["series_uid"] = uid_serie(etude["study_uid"])
                    modifie = True
        if modifie:
            store.remplacer(doc)
        bilan["patients"] += 1
    return bilan


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--patient", action="append", help="limiter à ce patient (répétable)")
    a = p.parse_args()

    import api_h2                                   # mêmes réglages MongoDB et PACS que l'API
    if api_h2.PACS is None:
        print("H2_ORTHANC_URL n'est pas défini : aucun PACS où déposer les images.", file=sys.stderr)
        return 2
    bilan = charger(api_h2.STORE, api_h2.PACS, patients=a.patient)
    print(f"{bilan['etudes']} études, {bilan['instances']} instances déposées "
          f"({bilan['patients']} dossiers parcourus).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
