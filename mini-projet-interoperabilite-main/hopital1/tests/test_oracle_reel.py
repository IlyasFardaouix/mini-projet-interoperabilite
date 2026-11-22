"""Tests sur une VRAIE base Oracle (sans simulation). Ignores tant qu'aucune base de test n'est configuree.

    docker compose up -d                                   (dans hopital1/ ; attendre « healthy »)
    set ORACLE_TEST_USER=hopital1  ORACLE_TEST_PWD=...  ORACLE_TEST_DSN=localhost:1521/FREEPDB1
    set ORACLE_TEST_RESET=oui
    python -m pytest tests/test_oracle_reel.py -v

ATTENTION : ces tests SUPPRIMENT puis recreent toutes les tables H1 du schema vise. N'utiliser qu'une
base de test. Pour cette raison ils exigent ORACLE_TEST_RESET=oui et n'utilisent jamais ORACLE_USER/PWD/DSN.

Ce que ces tests verifient et que les tests simules ne peuvent pas verifier : que le SQL du depot est
accepte par Oracle (MERGE, FETCH FIRST, REGEXP_LIKE, FOR UPDATE, contraintes), que le DDL de base
est coherent avec les trois autres scripts, que l'import est atomique et rejouable sans doublon, et que
les routes HTTP fonctionnent de bout en bout avec Oracle derriere.
"""
import json
import os

import pytest

CONFIGURE = all(os.getenv(v) for v in ("ORACLE_TEST_USER", "ORACLE_TEST_PWD", "ORACLE_TEST_DSN")) \
    and os.getenv("ORACLE_TEST_RESET") == "oui"
pytestmark = pytest.mark.skipif(
    not CONFIGURE, reason="base Oracle de test non configuree (ORACLE_TEST_USER/PWD/DSN + ORACLE_TEST_RESET=oui)")

if CONFIGURE:
    import oracledb
    from fastapi.testclient import TestClient

    import app as api
    import h1_to_fhir as ALL
    import initialiser_base_h1 as init
    import oracle_repo as repo
    from valider import valider_bundle

JETON = "jeton-test-h1-assez-long-pour-etre-valide"
EXEMPLES_H2 = os.path.join(os.path.dirname(__file__), "..", "..", "hopital2", "exemples")
H2_0051 = os.path.join(EXEMPLES_H2, "retour_H2_P2-0051_retinopathie_imagerie.json")


def compter(conn, table, where="1=1", **binds):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", binds)
        return cur.fetchone()[0]


def tout_compter(conn):
    return {t: compter(conn, t) for t, _ in repo.ORDRE_TABLES}


@pytest.fixture(scope="module")
def base():
    """Schema complet cree une fois ; les donnees sont rechargees avant chaque test."""
    os.environ["ORACLE_USER"] = os.environ["ORACLE_TEST_USER"]
    os.environ["ORACLE_PWD"] = os.environ["ORACLE_TEST_PWD"]
    os.environ["ORACLE_DSN"] = os.environ["ORACLE_TEST_DSN"]
    conn = repo.connexion()
    init.supprimer_tables(conn)
    init.creer_schema(conn)
    yield conn
    init.supprimer_tables(conn)
    conn.close()


@pytest.fixture
def conn(base):
    with base.cursor() as cur:
        for table in init.TABLES:
            cur.execute(f"DELETE FROM {table}")
    base.commit()
    init.executer_script(base, init.ICI / "donnees_demo_h1.sql")
    return base


@pytest.fixture
def http(monkeypatch, conn):
    monkeypatch.setenv("H1_API_TOKEN", JETON)
    return TestClient(api.app, headers={"Authorization": f"Bearer {JETON}"})


def retour_h2():
    return json.load(open(H2_0051, encoding="utf-8"))


# ── schema ───────────────────────────────────────────────────────────────────
def test_les_quatre_scripts_donnent_le_schema_attendu(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM user_tables")
        tables = {l[0].lower() for l in cur.fetchall()}
        cur.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'CONSENTEMENT'")
        colonnes = {l[0].lower() for l in cur.fetchall()}
        cur.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'SEJOUR'")
        colonnes_sejour = {l[0].lower() for l in cur.fetchall()}
    assert {t for t, _ in repo.ORDRE_TABLES} | {"consentement", "allergie", "diagnostic", "mesure",
                                                "journal_echange"} <= tables
    assert {"date_fin", "destinataires", "categories_exclues", "date_retrait"} <= colonnes      # schema_consentement
    assert {"etablissement", "id_externe"} <= colonnes_sejour                                    # schema_retour


def test_le_journal_accepte_les_sens_consentement_et_droit_acces(conn):
    repo.journaliser(conn, "CONSENTEMENT", "P1-0106", "OK", {"t": 1}, strict=True)
    repo.journaliser(conn, "DROIT_ACCES", "P1-0106", "OK", {"t": 1}, strict=True)
    assert compter(conn, "journal_echange") == 2


def test_cin_unique(conn):
    with pytest.raises(oracledb.IntegrityError):
        with conn.cursor() as cur:
            cur.execute("INSERT INTO patient (ipp, nom, prenom, sexe, cin) VALUES ('P1-0999','A','B','M','AB123456')")
    conn.rollback()


# ── aller : Oracle -> Bundle ─────────────────────────────────────────────────
def test_export_du_dossier_nominal(conn):
    bundle, alertes, rejets = repo.exporter(conn, ipp="P1-0106")
    assert valider_bundle(bundle) == [] and rejets == []
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert types.count("Patient") == 1 and types.count("Consent") == 1 and "Encounter" in types
    assert compter(conn, "journal_echange", "sens = 'ALLER' AND statut = 'OK'") == 1


def test_export_par_cin(conn):
    bundle, _, _ = repo.exporter(conn, cin="AB123456")
    assert bundle["type"] == "transaction"


def test_export_refuse_sans_consentement(conn):
    with pytest.raises(ALL.ConsentementRefuse):
        repo.exporter(conn, ipp="P1-0108")
    assert compter(conn, "journal_echange", "statut = 'REFUSE'") == 1


def test_export_patient_inconnu(conn):
    with pytest.raises(LookupError):
        repo.exporter(conn, ipp="P1-9999")


# ── POST/GET Patient ─────────────────────────────────────────────────────────
def patient_fhir(cin="ZZ123456"):
    return {"resourceType": "Patient", "identifier": [{"system": "urn:ma:cin", "value": cin}],
            "name": [{"family": "Benani", "given": ["Sara"]}], "gender": "female", "birthDate": "1990-05-03"}


def test_creer_lire_chercher_patient(conn):
    ligne = repo.creer_patient_seul(conn, patient_fhir())
    assert ligne["ipp"] == "P1-0109" and ligne["nom"] == "Benani" and ligne["sexe"] == "F"
    assert repo.lire_patient(conn, "P1-0109")["cin"] == "ZZ123456"
    assert [p["ipp"] for p in repo.chercher_patients(conn, "urn:ma:cin", "ZZ123456")] == ["P1-0109"]
    assert [p["ipp"] for p in repo.chercher_patients(conn, None, "P1-0109")] == ["P1-0109"]
    assert repo.chercher_patients(conn, "systeme-inconnu", "ZZ123456") == []
    assert len(repo.chercher_patients(conn, None, None, limite=2)) == 2


def test_creer_patient_doublon_cin(conn):
    avant = compter(conn, "patient")
    with pytest.raises(repo.PatientExistant):
        repo.creer_patient_seul(conn, patient_fhir(cin="AB123456"))
    assert compter(conn, "patient") == avant


def test_patient_cree_n_est_pas_exportable_sans_consentement(conn):
    ligne = repo.creer_patient_seul(conn, patient_fhir())
    with pytest.raises(ALL.ConsentementRefuse):
        repo.exporter(conn, ipp=ligne["ipp"])


# ── retour : Bundle de H2 -> Oracle ──────────────────────────────────────────
def test_retour_de_h2_est_importe(conn):
    bundle = retour_h2()
    from retour_api import extraire_consentement, verifier_bundle_retour
    bundle, _ = extraire_consentement(bundle)
    patient = verifier_bundle_retour(bundle, definitif=True)
    avant = tout_compter(conn)
    ipp, res = repo.recevoir_retour(conn, bundle, patient, echange_id="ech-test-1")
    apres = tout_compter(conn)
    assert ipp == "P1-0106"
    assert apres["sejour"] > avant["sejour"] and sum(apres.values()) > sum(avant.values())
    assert compter(conn, "journal_echange", "sens = 'RETOUR' AND details LIKE '%ech-test-1%'") == 1


def test_rejeu_du_meme_retour_ne_cree_pas_de_doublon(conn):
    from retour_api import extraire_consentement, verifier_bundle_retour
    bundle, _ = extraire_consentement(retour_h2())
    patient = verifier_bundle_retour(bundle, definitif=True)
    repo.recevoir_retour(conn, bundle, patient, echange_id="ech-test-1")
    un_envoi = tout_compter(conn)
    repo.recevoir_retour(conn, bundle, patient, echange_id="ech-test-1")
    assert tout_compter(conn) == un_envoi                                     # MERGE : memes lignes
    assert compter(conn, "journal_echange", "sens = 'RETOUR'") == 2           # mais chaque reception est tracee


def test_import_atomique_si_le_journal_echoue(conn, monkeypatch):
    from retour_api import extraire_consentement, verifier_bundle_retour
    bundle, _ = extraire_consentement(retour_h2())
    patient = verifier_bundle_retour(bundle, definitif=True)
    avant = tout_compter(conn)

    def journal_en_panne(*a, **k):
        raise oracledb.DatabaseError("journal indisponible")
    monkeypatch.setattr(repo, "journaliser", journal_en_panne)
    with pytest.raises(oracledb.DatabaseError):
        repo.recevoir_retour(conn, bundle, patient)
    assert tout_compter(conn) == avant                                        # rien n'est reste ecrit sans trace


def test_retour_refuse_si_consentement_retire(conn):
    from retour_api import extraire_consentement, verifier_bundle_retour
    repo.retirer_consentement(conn, "P1-0106", {"motif": "demande du patient", "recueilli_par": "accueil"},
                              agent="test")
    bundle, _ = extraire_consentement(retour_h2())
    patient = verifier_bundle_retour(bundle, definitif=True)
    avant = tout_compter(conn)
    with pytest.raises(ALL.ConsentementRefuse):
        repo.recevoir_retour(conn, bundle, patient)
    assert tout_compter(conn) == avant


# ── consentement ─────────────────────────────────────────────────────────────
def test_recueil_puis_retrait_du_consentement(conn):
    etat = repo.enregistrer_consentement(conn, "P1-0108", {"statut": "actif", "recueilli_par": "accueil"},
                                         agent="test")
    assert etat["partage_autorise"] is True and len(etat["historique"]) == 1       # le REFUSE reste dans l'historique
    etat = repo.retirer_consentement(conn, "P1-0108", {"motif": "x", "recueilli_par": "accueil"}, agent="test")
    assert etat["partage_autorise"] is False
    assert compter(conn, "consentement", "ipp = 'P1-0108'") == 3                    # une ligne par version


# ── HTTP de bout en bout, Oracle derriere ────────────────────────────────────
def test_http_patient_puis_bundle_puis_retour(http, conn):
    cree = http.post("/Patient", json=patient_fhir())
    assert cree.status_code == 201, cree.text
    ipp = cree.json()["id"]
    assert http.get(f"/Patient/{ipp}").status_code == 200
    assert http.get("/Patient", params={"identifier": "urn:ma:cin|ZZ123456"}).json()["total"] == 1
    assert http.post("/Patient", json=patient_fhir()).status_code == 409           # meme CIN

    sortie = http.get("/api/patients/P1-0106/bundle")
    assert sortie.status_code == 200 and sortie.headers["X-Exchange-Id"]
    assert http.get("/Patient/P1-0106/$everything").status_code == 200
    assert http.get("/api/patients/P1-0108/bundle").status_code == 403             # consentement refuse

    retour = http.post("/Bundle", json=retour_h2(), headers={"X-Exchange-Id": "ech-http-1"})
    assert retour.status_code == 200, retour.text
    assert retour.json()["patient_ipp"] == "P1-0106" and retour.json()["echange_id"] == "ech-http-1"
