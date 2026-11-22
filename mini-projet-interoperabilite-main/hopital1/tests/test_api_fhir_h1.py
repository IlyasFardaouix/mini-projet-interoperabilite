"""Routes FHIR standard de H1 (memes routes que H2) et en-tete X-Exchange-Id. Oracle est simule."""
import json
import os
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

import app as api
import fhir_to_h1 as RET
import h1_to_fhir as ALL
import oracle_repo as repo
from tests.donnees import dossier

JETON = "jeton-test-h1-assez-long-pour-etre-valide"
EXEMPLES_H2 = os.path.join(os.path.dirname(__file__), "..", "..", "hopital2", "exemples")
LIGNE = dict(ipp="P1-0200", nom="Benani", prenom="Sara", sexe="F", date_naissance=__import__("datetime").datetime(1990, 5, 3),
             cin="CD123456", telephone="06 11 22 33 44", adresse="1 rue X", ville="Settat", groupe_sanguin=None)


@pytest.fixture
def client(monkeypatch):
    @contextmanager
    def faux_oracle():
        yield object()
    monkeypatch.setenv("H1_API_TOKEN", JETON)
    monkeypatch.setattr(repo, "connexion", faux_oracle)
    return TestClient(api.app, headers={"Authorization": f"Bearer {JETON}"})


def patient_fhir(**extra):
    p = {"resourceType": "Patient", "identifier": [{"system": "urn:ma:cin", "value": "CD123456"}],
         "name": [{"family": "Benani", "given": ["Sara"]}], "gender": "female", "birthDate": "1990-05-03"}
    p.update(extra)
    return p


# ── /metadata ────────────────────────────────────────────────────────────────
def test_metadata_est_public_et_decrit_les_routes():
    r = TestClient(api.app).get("/metadata")                       # sans jeton
    assert r.status_code == 200
    cs = r.json()
    assert cs["resourceType"] == "CapabilityStatement" and cs["fhirVersion"] == "5.0.0"
    types = {x["type"]: [i["code"] for i in x["interaction"]] for x in cs["rest"][0]["resource"]}
    assert types == {"Patient": ["read", "create", "search-type"], "Bundle": ["create"]}


# ── POST /Patient ────────────────────────────────────────────────────────────
def test_creer_patient_201(client, monkeypatch):
    monkeypatch.setattr(repo, "creer_patient_seul", lambda conn, p: dict(LIGNE))
    r = client.post("/Patient", json=patient_fhir())
    assert r.status_code == 201 and r.headers["Location"] == "/Patient/P1-0200"
    res = r.json()
    assert res["resourceType"] == "Patient" and res["id"] == "P1-0200"
    assert {"system": "urn:ma:cin", "value": "CD123456", "use": "official"} in res["identifier"]
    assert "line" not in res["address"][0]                          # minimisation : pas de rue


def test_creer_patient_doublon_409(client, monkeypatch):
    def doublon(conn, p):
        raise repo.PatientExistant("Un patient avec ce CIN existe deja (P1-0106).")
    monkeypatch.setattr(repo, "creer_patient_seul", doublon)
    r = client.post("/Patient", json=patient_fhir())
    assert r.status_code == 409 and r.json()["resourceType"] == "OperationOutcome"


def test_creer_patient_incomplet_422(client):
    sans_nom = patient_fhir(name=[])
    r = client.post("/Patient", json=sans_nom)
    assert r.status_code == 422 and r.json()["resourceType"] == "OperationOutcome"


def test_routes_patient_exigent_un_jeton(monkeypatch):
    monkeypatch.setenv("H1_API_TOKEN", JETON)                         # service configure, appelant sans jeton
    sans_jeton = TestClient(api.app)
    assert sans_jeton.post("/Patient", json=patient_fhir()).status_code == 401
    assert sans_jeton.get("/Patient/P1-0106").status_code == 401
    assert sans_jeton.get("/Patient").status_code == 401
    assert sans_jeton.post("/Bundle", json={}).status_code == 401


# ── GET /Patient ─────────────────────────────────────────────────────────────
def test_lire_patient(client, monkeypatch):
    monkeypatch.setattr(repo, "lire_patient", lambda conn, ipp: dict(LIGNE) if ipp == "P1-0200" else None)
    assert client.get("/Patient/P1-0200").json()["name"][0]["family"] == "Benani"
    r = client.get("/Patient/P1-9999")
    assert r.status_code == 404 and r.json()["resourceType"] == "OperationOutcome"


def test_chercher_patient_par_cin(client, monkeypatch):
    vus = []

    def chercher(conn, system, valeur, limite=100):
        vus.append((system, valeur))
        return [dict(LIGNE)] if valeur == "CD123456" else []
    monkeypatch.setattr(repo, "chercher_patients", chercher)
    r = client.get("/Patient", params={"identifier": "urn:ma:cin|CD123456"})
    assert r.status_code == 200 and r.json()["type"] == "searchset" and r.json()["total"] == 1
    assert vus == [("urn:ma:cin", "CD123456")]
    assert client.get("/Patient", params={"identifier": "ZZ"}).json()["total"] == 0


# ── export : identifiant d'echange + alias $everything ───────────────────────
def test_export_porte_un_identifiant_d_echange(client, monkeypatch):
    monkeypatch.setattr(repo, "exporter", lambda conn, ipp=None, **k: ALL.dossier_vers_bundle(dossier("S1")))
    for chemin in ("/api/patients/P1-0106/bundle", "/Patient/P1-0106/$everything"):
        r = client.get(chemin)
        assert r.status_code == 200, chemin
        ident = r.json()["identifier"]
        assert ident["system"] == "urn:chu-almassira:echange"
        assert r.headers["X-Exchange-Id"] == ident["value"]


# ── reception : /Bundle = /api/retours, PUT accepte, X-Exchange-Id ──────────
def retour_h2(nom="retour_H2_P2-0051_retinopathie_imagerie.json"):
    return json.load(open(os.path.join(EXEMPLES_H2, nom), encoding="utf-8"))


@pytest.fixture
def import_capture(monkeypatch):
    vus = {}

    def recevoir(conn, bundle, patient, echange_id=None):
        vus["echange_id"], vus["patient"] = echange_id, patient
        return "P1-0106", {t: [] for t, _ in repo.ORDRE_TABLES} | {"alertes": [], "ignores": []}
    monkeypatch.setattr(repo, "recevoir_retour", recevoir)
    return vus


@pytest.mark.parametrize("chemin", ["/api/retours", "/Bundle"])
def test_retour_de_h2_en_put_est_accepte(client, import_capture, chemin):
    bundle = retour_h2()
    assert any(e["request"]["method"] == "PUT" for e in bundle["entry"])     # c'est bien le format de H2
    r = client.post(chemin, json=bundle, headers={"X-Exchange-Id": "ech-42"})
    assert r.status_code == 200, r.text
    assert r.json()["echange_id"] == "ech-42" and r.headers["X-Exchange-Id"] == "ech-42"
    assert import_capture["echange_id"] == "ech-42"


def test_retour_sans_entete_echange_reste_accepte(client, import_capture):
    r = client.post("/api/retours", json=retour_h2())
    assert r.status_code == 200 and r.json()["echange_id"] is None


@pytest.mark.parametrize("valeur", ["a" * 65, "id avec espace", "x;DROP"])
def test_entete_echange_invalide_422(client, import_capture, valeur):
    r = client.post("/api/retours", json=retour_h2(), headers={"X-Exchange-Id": valeur})
    assert r.status_code == 422 and "echange_id" not in import_capture


def _une_donnee(bundle):
    """Une entree controlee par H1 (le Consent, lui, est retire avant le controle)."""
    return next(e for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation")


def test_instruction_delete_refusee_422(client, import_capture):
    bundle = retour_h2()
    _une_donnee(bundle)["request"]["method"] = "DELETE"
    assert client.post("/api/retours", json=bundle).status_code == 422


def test_url_incoherente_refusee_422(client, import_capture):
    bundle = retour_h2()
    _une_donnee(bundle)["request"]["url"] = "Patient/x"
    assert client.post("/api/retours", json=bundle).status_code == 422


@pytest.mark.parametrize("nom", ["retour_H2_P2-0051_retinopathie_imagerie.json", "retour_H2_P2-0052_alerte_glaucome.json"])
def test_retours_h2_se_convertissent_en_lignes_oracle(nom):
    """De bout en bout cote conversion : le retour de H2 donne des lignes pour les tables H1."""
    bundle = retour_h2(nom)
    res = RET.bundle_vers_lignes(bundle, lambda cin, ipp_chu, ligne: "P1-0106")
    assert res["resultat_ophtalmo"] or res["etude_imagerie"] or res["compte_rendu"]
    assert all(l["ipp"] == "P1-0106" for t in ("sejour", "resultat_ophtalmo", "compte_rendu") for l in res[t])


# ── oracle_repo : creation d'un patient (curseur simule) ────────────────────
class FauxOracle:
    def __init__(self, cin_existant=None):
        self.cin_existant, self.requetes, self.valide, self.annule = cin_existant, [], 0, 0
        self.lignes = {}

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.valide += 1

    def rollback(self):
        self.annule += 1


class FauxCurseur:
    def __init__(self, conn):
        self.conn, self.description, self._r = conn, None, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None, **binds):
        sql = " ".join(sql.split())
        self.conn.requetes.append((sql, params or binds))
        if "WHERE cin" in sql:
            self._r = [("P1-0106",)] if self.conn.cin_existant else []
        elif "MAX(TO_NUMBER" in sql:
            self._r = [(201,)]
        elif sql.startswith("INSERT INTO patient"):
            self.conn.lignes[params["ipp"]] = dict(params)
        elif sql.startswith("SELECT * FROM patient WHERE ipp"):
            ligne = self.conn.lignes.get(binds["v"], {})
            self.description = [(c.upper(),) for c in ligne]
            self._r = [tuple(ligne.values())] if ligne else []

    def fetchone(self):
        return self._r[0] if self._r else None

    def fetchall(self):
        return self._r


def test_repo_creer_patient_attribue_un_ipp_et_valide():
    conn = FauxOracle()
    ligne = repo.creer_patient_seul(conn, patient_fhir())
    assert ligne["ipp"] == "P1-0201" and ligne["cin"] == "CD123456" and conn.valide == 1 and conn.annule == 0


def test_repo_creer_patient_cin_deja_connu():
    conn = FauxOracle(cin_existant=True)
    with pytest.raises(repo.PatientExistant):
        repo.creer_patient_seul(conn, patient_fhir())
    assert conn.annule == 1 and not any(s.startswith("INSERT") for s, _ in conn.requetes)


@pytest.mark.parametrize("mauvais", [
    patient_fhir(name=[]), patient_fhir(birthDate=None), patient_fhir(gender="autre"),
    {"resourceType": "Observation"}])
def test_repo_creer_patient_incomplet(mauvais):
    with pytest.raises(ValueError):
        repo.creer_patient_seul(FauxOracle(), mauvais)
