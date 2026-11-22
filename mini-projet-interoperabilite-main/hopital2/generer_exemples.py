#!/usr/bin/env python3
"""
generer_exemples.py — fabrique les fichiers du dossier exemples/ à partir de VRAIES réponses de l'API
(jamais écrits à la main : ce que vous lisez est ce que l'API renvoie).
"""
import copy
import json

from bson import json_util
import os

from fastapi.testclient import TestClient
from fhir.resources.bundle import Bundle

import api_h2
import stores
from exemples_h1 import bundle_h1

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "exemples")
DOCS = json_util.loads(open(os.path.join(ICI, "data", "patients_h2.json"), encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(ICI, "data", "referentiels_h2.json"), encoding="utf-8").read())
JETON = "jeton-de-demonstration"


def ecrire(nom, contenu):
    with open(os.path.join(SORTIE, nom), "w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(SORTIE, exist_ok=True)
    os.environ["H2_TOKEN"] = JETON
    api_h2.STORE = stores.StoreMemoire(copy.deepcopy(DOCS), REFS)
    c = TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})

    # ── H2 → H1 : Bundles « aller » (à envoyer au CHU) ──
    for pid, nom in (("P2-0051", "retour_H2_P2-0051_retinopathie_imagerie.json"),
                     ("P2-0052", "retour_H2_P2-0052_alerte_glaucome.json")):
        b = c.get(f"/api/patients/{pid}/bundle").json()
        Bundle.model_validate(b)                                    # FHIR R5 valide ?
        ecrire(nom, b)

    # ── H1 → H2 : Bundle reçu de H1 et réponses de l'API ──
    b_h1 = bundle_h1()
    Bundle.model_validate(b_h1)
    ecrire("aller_H1_nouveau_patient.json", b_h1)
    ecrire("reponse_200_simulation.json", c.post("/api/retours/simulation", json=b_h1).json())
    ecrire("reponse_201_import.json", c.post("/api/retours", json=b_h1, headers={"X-Exchange-Id": "ech-demo-1"}).json())
    ecrire("reponse_200_rejeu_sans_doublon.json", c.post("/api/retours", json=b_h1, headers={"X-Exchange-Id": "ech-demo-2"}).json())
    d3 = next(d for d in DOCS if d["patient_id"] == "P2-0055")      # cas D3 : A+ chez H2, A- chez H1
    conflit = bundle_h1(ipp="P1-0155", cin=d3["national_id"], nom=d3["last_name"], prenom=d3["first_name"],
                        naissance=d3["birth_date"], sexe="male" if d3["sex"] == 1 else "female", groupe="A-",
                        telephone=d3["phone"])
    ecrire("reponse_200_avec_conflit_groupe_sanguin.json", c.post("/api/retours", json=conflit).json())

    # ── Erreurs (OperationOutcome) ──
    sans_jeton = TestClient(api_h2.app)
    ecrire("erreur_401_jeton.json", sans_jeton.get("/api/patients/P2-0051/bundle").json())
    ecrire("erreur_403_consentement_refuse.json", c.post("/api/retours", json=bundle_h1(ipp="P1-0900", cin="X1", consent="not-done")).json())
    ecrire("erreur_409_identite_ambigue.json", c.post("/api/retours", json=bundle_h1(ipp="P1-0106", cin="K445120")).json())
    ecrire("erreur_422_bundle_invalide.json", c.post("/api/retours", json=bundle_h1(ipp="P1-0901", cin="X2", tension=(500, 80))).json())
    ecrire("erreur_404_patient_inconnu.json", c.get("/api/patients/P2-9999/bundle").json())
    print("Exemples écrits dans", SORTIE, ":", len(os.listdir(SORTIE)), "fichiers")


if __name__ == "__main__":
    main()
