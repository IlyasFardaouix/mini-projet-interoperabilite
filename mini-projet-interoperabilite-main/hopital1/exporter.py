"""
ALLER : exporte le dossier d'un patient H1 en Bundle FHIR R5.
Usage : python exporter.py AB123456            (par CIN)
        python exporter.py --ipp P1-0112        (patient sans CIN)
        python exporter.py AB123456 --sans-adressage
Résultat : sortie/bundle_<id>.json  (ou sortie/erreur_<id>.json = OperationOutcome)
"""
import argparse
import json
import os

import h1_to_fhir as ALL
import oracle_repo as repo
from valider import valider_bundle

ap = argparse.ArgumentParser()
ap.add_argument("cin", nargs="?")
ap.add_argument("--ipp")
ap.add_argument("--sans-adressage", action="store_true")
a = ap.parse_args()
cle = a.cin or a.ipp
os.makedirs("sortie", exist_ok=True)

with repo.connexion() as conn:
    try:
        bundle, alertes, rejets = repo.exporter(conn, cin=a.cin, ipp=a.ipp,
                                                adressage=not a.sans_adressage)
    except (ALL.ConsentementRefuse, ALL.DonneeInvalide) as e:
        oo = ALL.vers_operation_outcome(e)
        with open(f"sortie/erreur_{cle}.json", "w", encoding="utf-8") as f:
            json.dump(oo, f, ensure_ascii=False, indent=2)
        print(f"REFUSÉ (HTTP {e.http}) : {e}")
        print(f"-> sortie/erreur_{cle}.json")
        raise SystemExit(1)

fichier = f"sortie/bundle_{cle}.json"
with open(fichier, "w", encoding="utf-8") as f:
    json.dump(bundle, f, ensure_ascii=False, indent=2)

types = {}
for e in bundle["entry"]:
    t = e["resource"]["resourceType"]
    types[t] = types.get(t, 0) + 1
print(f"Bundle écrit : {fichier}")
print("Contenu :", ", ".join(f"{n} {t}" for t, n in types.items()))
for x in alertes:
    print("  ALERTE :", x)
for x in rejets:
    print("  REJET  :", x)
erreurs = valider_bundle(bundle)
print("Validation FHIR R5 :", "OK" if not erreurs else "ERREURS")
for x in erreurs:
    print("  -", x)
