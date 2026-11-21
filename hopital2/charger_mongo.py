#!/usr/bin/env python3
"""
charger_mongo.py — charge hopital2_mongodb_v3.js dans MongoDB (base « hopital2 », 7 collections)
================================================================================================
Collections : organisations, locations, endpoints, devices, practitioners, practitioner_roles, patients.
Sans mongosh : le fichier .js est lu par Python (ISODate(...) → vraies dates BSON).

  python charger_mongo.py hopital2_mongodb_v3.js                       # MongoDB sur localhost:27017
  python charger_mongo.py hopital2_mongodb_v3.js --uri mongodb://...   # autre serveur
  python charger_mongo.py hopital2_mongodb_v3.js --json-out data       # écrit data/patients_h2.json + data/referentiels_h2.json

Attention : les collections sont VIDÉES avant le chargement (comme le font les db.<collection>.drop() du .js).
"""
import argparse
import json
import os
import re
import sys

from bson import json_util

INDEX = {"organisations": ["org_id"], "locations": ["location_id"], "endpoints": ["endpoint_id"],
         "devices": ["device_id"], "practitioners": ["prac_id"], "practitioner_roles": ["role_id"],
         "patients": ["patient_id", "national_id"]}


def lire_js(chemin: str) -> dict:
    """{collection: [documents]} ; une collection peut avoir plusieurs insertMany (patients par lots de 10)."""
    src = open(chemin, encoding="utf-8").read()
    cols: dict = {}
    for m in re.finditer(r"db\.(\w+)\.insertMany\(", src):
        fin = src.index("]);", m.end()) + 1
        texte = re.sub(r'ISODate\("([^"]+)"\)', r'{"$date": "\1"}', src[m.end():fin])
        texte = re.sub(r"NumberInt\((-?\d+)\)", r"\1", texte)
        cols.setdefault(m.group(1), []).extend(json_util.loads(texte))
    return cols


def _json(obj):
    return json.loads(json_util.dumps(obj, json_options=json_util.RELAXED_JSON_OPTIONS))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fichier_js")
    p.add_argument("--uri", default="mongodb://localhost:27017")
    p.add_argument("--base", default="hopital2")
    p.add_argument("--json-out", metavar="DOSSIER", help="écrit des JSON dans ce dossier au lieu de charger MongoDB")
    a = p.parse_args()
    cols = lire_js(a.fichier_js)
    if "patients" not in cols:
        print("Aucune collection « patients » dans ce fichier.", file=sys.stderr)
        return 1
    if a.json_out:
        os.makedirs(a.json_out, exist_ok=True)
        with open(os.path.join(a.json_out, "patients_h2.json"), "w", encoding="utf-8") as f:
            json.dump(_json(cols["patients"]), f, ensure_ascii=False, indent=1)
        refs = {k: v for k, v in cols.items() if k != "patients"}
        with open(os.path.join(a.json_out, "referentiels_h2.json"), "w", encoding="utf-8") as f:
            json.dump(_json(refs), f, ensure_ascii=False, indent=1)
        print(f"{len(cols['patients'])} patients + {len(refs)} référentiels écrits dans {a.json_out}/")
        return 0
    from pymongo import MongoClient
    db = MongoClient(a.uri, serverSelectionTimeoutMS=5000)[a.base]
    for nom, docs in cols.items():
        db[nom].drop()
        db[nom].insert_many(docs)
        for champ in INDEX.get(nom, []):
            db[nom].create_index(champ, unique=(nom == "patients" and champ == "patient_id"))
        print(f"{nom:20s} {len(docs):3d} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
