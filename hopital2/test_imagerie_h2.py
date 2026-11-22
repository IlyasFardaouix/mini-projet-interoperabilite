"""Imagerie côté H2 : chargement du PACS, Endpoint annoncé, passerelle et règles de partage."""
import copy
import json
import os
from dataclasses import replace

import pytest
from bson import json_util
from fastapi.testclient import TestClient
from fhir.resources.bundle import Bundle

import api_h2
import echange
import stores
from charger_dicom import charger

from imagerie.dicom import depuis_octets, uid_serie
from imagerie.dicomweb import EntrepotMemoire, decoder_multipart

DOCS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "patients_h2.json"),
                            encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "referentiels_h2.json"),
                            encoding="utf-8").read())
JETON = "secret-test"
PATIENT = "P2-0051"
ETUDE = next(i["study_uid"] for v in next(d for d in DOCS if d["patient_id"] == PATIENT)["visits"]
             for i in v.get("imaging", []))
JETON_H1 = "jeton-h1-chu-" + "z" * 30


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON)
    store = stores.StoreMemoire(copy.deepcopy(DOCS), REFS)
    pacs = EntrepotMemoire()
    charger(store, pacs, patients=[PATIENT, "P2-0052"])
    monkeypatch.setattr(api_h2, "STORE", store)
    monkeypatch.setattr(api_h2, "PACS", pacs)
    return TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})


@pytest.fixture
def chu(api, monkeypatch, tmp_path):
    """Client « h1-chu » du registre (autre établissement), portée h2:imagerie.lire."""
    from securite.jetons import Verificateur, empreinte_complete

    registre = tmp_path / "registre.json"
    registre.write_text(json.dumps({"clients": [
        {"id": "h1-chu", "empreinte": "sha256:" + empreinte_complete(JETON_H1),
         "portees": ["h2:import", "h2:imagerie.lire"], "actif": True}]}), encoding="utf-8")
    etat = api_h2.app.state.securite
    monkeypatch.setattr(etat, "verificateur",
                        Verificateur(replace(etat.conf, registre=registre, jwt_secret="", variable_jeton="")))
    return TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON_H1}"})


def modifier(patient_id, fonction):
    doc = api_h2.STORE.get(patient_id)
    fonction(doc)
    api_h2.STORE.remplacer(doc)


# ── chargement et Bundle ─────────────────────────────────────────────────────
def test_chargement_coherent_avec_le_dossier(api):
    instances = api_h2.PACS.etude(ETUDE)
    assert len(instances) == 2
    assert depuis_octets(instances[0]).PatientID == PATIENT
    etude = next(i for v in api_h2.STORE.get(PATIENT)["visits"] for i in v.get("imaging", []))
    assert etude["series_uid"] == uid_serie(ETUDE)


def test_bundle_annonce_la_passerelle_et_la_serie(api):
    b = api.get(f"/api/patients/{PATIENT}/bundle").json()
    Bundle.model_validate(b)
    endpoints = [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Endpoint"]
    assert endpoints and all(e["address"] == echange.URL_DICOMWEB for e in endpoints)
    assert "8042" not in json.dumps(b)                       # jamais l'adresse du PACS
    etude = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "ImagingStudy")
    assert etude["series"][0]["uid"] == uid_serie(ETUDE)


# ── passerelle ───────────────────────────────────────────────────────────────
def test_personnel_de_la_clinique(api):
    r = api.get(f"/dicom-web/studies/{ETUDE}")
    assert r.status_code == 200
    assert len(decoder_multipart(r.content, r.headers["content-type"])) == 2


def test_chu_avec_consentement(chu):
    r = chu.get(f"/dicom-web/studies/{ETUDE}")
    assert r.status_code == 200
    assert depuis_octets(decoder_multipart(r.content, r.headers["content-type"])[0]).StudyInstanceUID == ETUDE


@pytest.mark.parametrize("changement, extrait", [
    (lambda d: d["consent"].update(excluded_categories=["imagerie"]), "exclu l'imagerie"),
    (lambda d: d["consent"].update(recipients=["H2"]), "vers H1 non autorise"),
    (lambda d: d["consent"].update(status="inactive"), "retire"),
    (lambda d: d["consent"].update(valid_until="2020-01-01"), "expire"),
])
def test_chu_refuse_selon_le_consentement(chu, changement, extrait):
    modifier(PATIENT, changement)
    r = chu.get(f"/dicom-web/studies/{ETUDE}")
    assert r.status_code == 403 and extrait in r.json()["issue"][0]["diagnostics"]


def test_anti_boucle_etude_venue_du_chu(chu):
    def marquer(d):
        for v in d["visits"]:
            for i in v.get("imaging", []):
                i["_origin"] = "H1"
    modifier(PATIENT, marquer)
    r = chu.get(f"/dicom-web/studies/{ETUDE}")
    assert r.status_code == 403 and "Anti-boucle" in r.json()["issue"][0]["diagnostics"]


def test_le_personnel_garde_l_acces_meme_si_le_partage_est_refuse(api):
    modifier(PATIENT, lambda d: d["consent"].update(excluded_categories=["imagerie"]))
    assert api.get(f"/dicom-web/studies/{ETUDE}").status_code == 200


def test_etude_inconnue_404(chu):
    assert chu.get("/dicom-web/studies/2.25.123").status_code == 404


def test_portee_requise(api, monkeypatch, tmp_path):
    from securite.jetons import Verificateur, empreinte_complete

    registre = tmp_path / "r.json"
    registre.write_text(json.dumps({"clients": [
        {"id": "h1-chu", "empreinte": "sha256:" + empreinte_complete(JETON_H1),
         "portees": ["h2:import"], "actif": True}]}), encoding="utf-8")
    etat = api_h2.app.state.securite
    monkeypatch.setattr(etat, "verificateur",
                        Verificateur(replace(etat.conf, registre=registre, jwt_secret="", variable_jeton="")))
    r = TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON_H1}"}).get(f"/dicom-web/studies/{ETUDE}")
    assert r.status_code == 403 and "h2:imagerie.lire" in r.json()["issue"][0]["diagnostics"]


def test_sans_pacs_configure_503(api, monkeypatch):
    monkeypatch.setattr(api_h2, "PACS", None)
    assert api.get(f"/dicom-web/studies/{ETUDE}").status_code == 503
