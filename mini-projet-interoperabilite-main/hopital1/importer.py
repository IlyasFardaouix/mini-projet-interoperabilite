"""
RETOUR : importe dans Oracle un Bundle FHIR reçu de la clinique.
Usage : python importer.py exemples/retour_clinique_youssef.json --simulation   (n'écrit rien)
        python importer.py exemples/retour_clinique_youssef.json                (écrit)
Prérequis : avoir exécuté schema_retour_h1.sql une fois.
"""
import argparse
import json

import oracle_repo as repo

ap = argparse.ArgumentParser()
ap.add_argument("fichier")
ap.add_argument("--simulation", action="store_true")
a = ap.parse_args()

with open(a.fichier, encoding="utf-8") as f:
    bundle = json.load(f)

with repo.connexion() as conn:
    res = repo.importer(conn, bundle, simulation=a.simulation)

print("SIMULATION (rien n'est écrit)" if a.simulation else "Import terminé")
for table, _ in repo.ORDRE_TABLES:
    if res[table]:
        print(f"  {table:18s} : {len(res[table])} ligne(s)")
for x in res["alertes"]:
    print("  ALERTE :", x)
for x in res["ignores"]:
    print("  IGNORÉ :", x)
