"""Chiffrement au repos côté H2 (MongoDB, file d'envoi) et minimisation de l'export."""
import copy
import json
import os
import sqlite3

import mongomock
import pytest
from bson import json_util
from fastapi.testclient import TestClient

import api_h2
import stores
from client_envoi import Outbox

from securite.chiffrement import Chiffreur, nouvelle_cle

DOCS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "patients_h2.json"),
                            encoding="utf-8").read())
CLE = nouvelle_cle("v1")
P = next(d for d in DOCS if d["patient_id"] == "P2-0051")


def store(cle=CLE, client=None):
    return stores.StoreMongoChiffre(client=client or mongomock.MongoClient(), nom_base="hopital2",
                                    chiffreur=Chiffreur.depuis_texte(cle))


@pytest.fixture
def s():
    st = store()
    for d in copy.deepcopy(DOCS):
        st.remplacer(d)
    return st


def test_rien_de_nominatif_en_clair_dans_la_base(s):
    brut = json.dumps(list(s.col.find({}, {"_id": 0})), default=str)
    for trace in (P["national_id"], P["last_name"], P["phone"], P["address"]["street"],
                  P["visits"][0]["imaging"][0]["study_uid"], "consent", "visits"):
        assert trace not in brut, trace
    assert set(s.col.find_one({"patient_id": "P2-0051"})) == {"_id", "patient_id", "_idx", "_cle", "_chiffre"}


def test_dossier_relu_a_l_identique(s):
    assert s.get("P2-0051") == P


def test_recherches_par_index_aveugles(s):
    assert s.find_by_identifier(stores.SYSTEM_CIN, P["national_id"])["patient_id"] == "P2-0051"
    assert s.find_by_identifier(None, P["national_id"])["patient_id"] == "P2-0051"
    assert s.find_by_study_uid(P["visits"][0]["imaging"][0]["study_uid"])["patient_id"] == "P2-0051"
    assert s.find_by_identifier(None, "INCONNU") is None


def test_identifiant_externe(s):
    doc = s.get("P2-0052")
    doc["_external_ids"] = [{"system": "https://chu-almassira.ma/ipp", "value": "P1-0152"}]
    s.remplacer(doc)
    assert s.find_by_identifier("https://chu-almassira.ma/ipp", "P1-0152")["patient_id"] == "P2-0052"
    assert s.find_by_identifier(None, "P1-0152")["patient_id"] == "P2-0052"
    assert s.find_by_identifier("urn:autre", "P1-0152") is None


def test_dossier_recopie_sur_un_autre_patient_illisible(s):
    autre = s.col.find_one({"patient_id": "P2-0052"})
    s.col.update_one({"patient_id": "P2-0051"}, {"$set": {"_chiffre": autre["_chiffre"]}})
    with pytest.raises(stores.StoreIndisponible):
        s.get("P2-0051")


def test_sans_la_bonne_cle_illisible(s):
    with pytest.raises(stores.StoreIndisponible):
        store(nouvelle_cle(), client=s.client).get("P2-0051")


def test_migration_et_rotation():
    client = mongomock.MongoClient()
    clair = stores.StoreMongo(client=client, nom_base="hopital2")
    clair.col.insert_many(copy.deepcopy(DOCS))                   # base chargée en clair
    s = store(client=client)
    assert s.get("P2-0051") == P                                 # lisible avant migration
    assert s.rechiffrer_tout() == {"chiffres": len(DOCS), "deja": 0}
    assert P["national_id"] not in json.dumps(list(s.col.find({}, {"_id": 0})), default=str)
    assert s.rechiffrer_tout() == {"chiffres": 0, "deja": len(DOCS)}
    tourne = store(nouvelle_cle("v2") + "," + CLE, client=client)
    assert tourne.rechiffrer_tout()["chiffres"] == len(DOCS)
    assert store(CLE.replace("v1", "v9"), client=client).col.find_one()["_cle"] == "v2"
    assert tourne.find_by_identifier(None, P["national_id"])["patient_id"] == "P2-0051"


# ── file d'envoi ─────────────────────────────────────────────────────────────
def test_file_d_envoi_chiffree(tmp_path):
    chemin = str(tmp_path / "envois.sqlite")
    bundle = json.dumps({"resourceType": "Bundle", "entry": [{"resource": {"name": P["last_name"]}}]})
    o = Outbox(chemin, chiffreur=Chiffreur.depuis_texte(CLE))
    i = o.ajouter("P2-0051", "ech-1", bundle, 0.0)
    assert o.get(i)["bundle"] == bundle
    brut = sqlite3.connect(chemin).execute("SELECT bundle FROM envois").fetchone()[0]
    assert P["last_name"] not in brut and brut.startswith("v1:")


def test_file_d_envoi_lit_les_anciennes_lignes_en_clair(tmp_path):
    chemin = str(tmp_path / "envois.sqlite")
    i = Outbox(chemin, chiffreur=None).ajouter("P2-0051", "ech-1", '{"a": 1}', 0.0)
    assert Outbox(chemin, chiffreur=Chiffreur.depuis_texte(CLE)).get(i)["bundle"] == '{"a": 1}'


# ── minimisation (loi 09-08, art. 3) ─────────────────────────────────────────
@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", "secret-test")
    doc = copy.deepcopy(P)
    doc["_contact"] = {"relationship": "spouse", "name": "Mme Alaoui", "phone": "+212600000000"}
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire([doc] + copy.deepcopy(DOCS[1:])))
    return TestClient(api_h2.app, headers={"Authorization": "Bearer secret-test"})


def test_export_sans_rue_ni_tiers(api):
    b = api.get("/api/patients/P2-0051/bundle").json()
    patient = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Patient")
    assert patient["address"] == [{"city": "Casablanca", "country": "MA"}]
    assert "contact" not in patient and P["address"]["street"] not in json.dumps(b)
    assert patient["telecom"][0]["value"] == P["phone"]          # comme H1 : téléphone conservé


def test_le_droit_d_acces_garde_tout(api):
    r = api.get("/api/patients/P2-0051/droit-acces").json()
    assert P["address"]["street"] in json.dumps(r, ensure_ascii=False)
