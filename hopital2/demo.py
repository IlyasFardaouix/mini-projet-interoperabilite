#!/usr/bin/env python3
"""
demo.py — scénario de transfert de dossier patient entre H1 (CHU / Oracle) et H2 (Clinique / MongoDB)
=====================================================================================================
Lancer :  python demo.py        (aucun serveur à démarrer : l'API H2 est appelée en direct, base en mémoire)
Les Bundles « H1 » sont fabriqués par exemples_h1.py avec le format du contrat reçu de H1.
"""
import copy
import json

from bson import json_util
import logging
import os
import sys
import tempfile

# La couche de securite fige sa configuration au moment ou l'API est importee :
# ces variables doivent donc etre posees AVANT « import api_h2 ».
# Le mode local tolere le trafic en clair (la demonstration appelle l'API en
# direct, sans serveur ni TLS) ; il ne desactive PAS l'authentification : le
# jeton reste exige sur toutes les routes de dossier, comme le montre l'etape 13.
os.environ.setdefault("H2_TOKEN", "jeton-demo")
os.environ.setdefault("SEC_MODE", "local")
os.environ.setdefault("SEC_TLS_REQUIS", "0")
os.environ.setdefault("SEC_SEL_AUDIT", "sel-de-demonstration")
os.environ.setdefault("SEC_JOURNAL",
                      os.path.join(tempfile.gettempdir(), "demo-securite-h2.jsonl"))

from fastapi.testclient import TestClient

import api_h2
import stores
from exemples_h1 import SYSTEM_IPP_H1, bundle_h1

DOCS = json_util.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "patients_h2.json"),
                      encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "referentiels_h2.json"),
                      encoding="utf-8").read())
for nom in ("fhir_h2", "h2_fhir"):                 # les adaptateurs journalisent déjà les rejets : on évite le doublon
    logging.getLogger(nom).setLevel(logging.ERROR)
api_h2.STORE = stores.StoreMemoire(copy.deepcopy(DOCS), REFS)
h2 = TestClient(api_h2.app, headers={"Authorization": "Bearer jeton-demo"})


def etape(n, titre):
    print(f"\n── Étape {n} : {titre}")


def ligne(r, extra=""):
    print(f"   → HTTP {r.status_code} {extra}")
    return r


def types(b):
    return sorted({e["resource"]["resourceType"] for e in b["entry"]})


print("DÉMONSTRATION — transfert de dossier patient H1 ⇄ H2 (FHIR R5)")

etape(1, "H1 vérifie que l'API de H2 répond, sans jeton")
r = ligne(TestClient(api_h2.app).get("/health"))
print("  ", r.json())

etape(2, "H1 envoie un patient à H2 : d'abord une SIMULATION (rien n'est écrit)")
b = bundle_h1()
r = ligne(h2.post("/api/retours/simulation", json=b))
print(f"   Patient provisoire {r.json()['patient_id']} · à créer : {r.json()['lignes_par_type']}")
print(f"   Patients en base : {len(api_h2.STORE.all(1000))} (inchangé)")

etape(3, "H1 envoie pour de bon (identifiant d'échange ech-1)")
r = ligne(h2.post("/api/retours", json=b, headers={"X-Exchange-Id": "ech-1"}), "(201 = patient créé)")
pid = r.json()["patient_id"]
print(f"   H2 a attribué {pid} ; IPP de H1 conservé : ", api_h2.STORE.get(pid)["_external_ids"])

etape(4, "Panne réseau : H1 ne sait pas si l'envoi a abouti et le REJOUE")
r = ligne(h2.post("/api/retours", json=b, headers={"X-Exchange-Id": "ech-1"}), "(200 = déjà reçu)")
print(f"   deja_traite = {r.json()['deja_traite']} · patients en base : {len(api_h2.STORE.all(1000))} → pas de doublon")

etape(5, "Le CHU envoie une 2e fois le même patient SANS identifiant d'échange (rejeu non tracé)")
r = ligne(h2.post("/api/retours", json=b))
print(f"   éléments écrits : {r.json()['lignes_par_type'] or 'aucun'} · déjà présents : {r.json()['deja_presents']}")

etape(6, "Retrouver le patient par son CIN ou par l'IPP du CHU")
for filtre in ("urn:ma:cin|CD654321", f"{SYSTEM_IPP_H1}|P1-0106"):
    r = ligne(h2.get(f"/Patient?identifier={filtre}"), f"total = {h2.get(f'/Patient?identifier={filtre}').json()['total']}")

etape(7, "ANTI-BOUCLE : H1 demande à H2 le dossier qu'il vient d'envoyer")
r = ligne(h2.get(f"/api/patients/{pid}/bundle"))
print(f"   Ressources renvoyées : {types(r.json())} → ses propres données ne lui reviennent pas")

etape(8, "H2 envoie le dossier d'un de SES patients (rétinopathie, imagerie DICOM) vers H1")
r = ligne(h2.get("/api/patients/P2-0051/bundle"))
bun = r.json()
print(f"   Bundle {bun['type']} · {len(bun['entry'])} ressources : {types(bun)}")
print(f"   Patient = {bun['entry'][0]['request']}")

etape(9, "Consentement refusé : le dossier ne part pas (loi 09-08)")
doc = api_h2.STORE.get("P2-0054"); doc["consent"]["status"] = "refused"; api_h2.STORE.remplacer(doc)
r = ligne(h2.get("/api/patients/P2-0054/bundle"))
print("  ", r.json()["issue"][0]["diagnostics"])
print("   Trace d'audit :", api_h2.STORE.get("P2-0054")["_audit_log"][-1]["outcome_code"])

etape(10, "Consentement refusé côté H1 : H2 refuse aussi de le recevoir")
r = ligne(h2.post("/api/retours", json=bundle_h1(ipp="P1-0900", cin="NOUVEAU1", consent="not-done")))
print("  ", r.json()["issue"][0]["diagnostics"])

etape(11, "Bundle non conforme (tension 500 mmHg) : rejeté en entier")
r = ligne(h2.post("/api/retours", json=bundle_h1(ipp="P1-0901", cin="NOUVEAU2", tension=(500, 80))))
print("  ", r.json()["issue"][0]["diagnostics"])

etape(12, "Conflit : H1 dit A-, H2 a A+ → signalé, jamais écrasé")
d3 = api_h2.STORE.get("P2-0055")
r = ligne(h2.post("/api/retours", json=bundle_h1(
    ipp="P1-0155", cin=d3["national_id"], nom=d3["last_name"], prenom=d3["first_name"],
    naissance=d3["birth_date"], sexe="male", groupe="A-", telephone=d3["phone"])))
print("  ", [a["message"] for a in r.json()["alertes"]], "· valeur conservée :", api_h2.STORE.get("P2-0055")["blood_type"])

etape(13, "Sans jeton : accès refusé")
r = ligne(TestClient(api_h2.app).get(f"/api/patients/{pid}/bundle"))
print("  ", r.json()["issue"][0]["diagnostics"])

print("\nFin de la démonstration.")
