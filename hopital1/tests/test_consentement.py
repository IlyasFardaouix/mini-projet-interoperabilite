"""Consentement côté H1 : export, retour reçu, accès Oracle et routes (sans Oracle)."""
from contextlib import contextmanager
from datetime import datetime as dt

import pytest
from fastapi.testclient import TestClient

import app as api
import config as C
import h1_to_fhir as ALL
import oracle_repo as repo
from retour_api import extraire_consentement
from tests.donnees import dossier

JETON = "jeton-test-h1-assez-long-pour-etre-valide"


def ressources(bundle, rtype):
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == rtype]


def avec_consentement(cas="S1", **colonnes):
    d = dossier(cas)
    d["consentement"].update(colonnes)
    return d


# ── export ───────────────────────────────────────────────────────────────────
def test_le_bundle_porte_un_consent_r5():
    """H2 refuse (403) tout Bundle sans Consent : H1 doit en joindre un."""
    bundle, _, _ = ALL.dossier_vers_bundle(dossier("S1"))
    consents = ressources(bundle, "Consent")
    assert len(consents) == 1
    c = consents[0]
    assert c["status"] == "active" and c["decision"] == "permit"
    assert c["identifier"][0] == {"system": C.SYS_CONSENTEMENT_CHU, "value": "CST-0106"}
    url_patient = next(e["fullUrl"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
    assert c["subject"]["reference"] == url_patient
    entree = next(e for e in bundle["entry"] if e["resource"]["resourceType"] == "Consent")
    assert entree["request"]["ifNoneExist"] == f"identifier={C.SYS_CONSENTEMENT_CHU}|CST-0106"


@pytest.mark.parametrize("colonnes, motif", [
    ({"date_fin": dt(2020, 1, 1)}, "expire"),
    ({"destinataires": "H1"}, "vers H2 non autorise"),
    ({"statut": "RETIRE", "date_retrait": dt(2026, 10, 2)}, "retire"),
])
def test_export_refuse_selon_le_consentement(colonnes, motif):
    with pytest.raises(ALL.ConsentementRefuse) as e:
        ALL.dossier_vers_bundle(avec_consentement(**colonnes))
    assert motif in str(e.value) and e.value.http == 403


def test_categorie_exclue_absente_du_bundle():
    bundle, alertes, _ = ALL.dossier_vers_bundle(avec_consentement(categories_exclues="allergies"))
    assert ressources(bundle, "AllergyIntolerance") == []
    assert any("Consentement partiel" in a for a in alertes)
    consent = ressources(bundle, "Consent")[0]
    assert consent["provision"][0]["provision"][0]["resourceType"][0]["code"] == "AllergyIntolerance"


# ── retour reçu de la clinique ───────────────────────────────────────────────
def _retour(consent):
    entrees = [{"resource": {"resourceType": "Patient", "id": "p"}, "request": {"method": "POST", "url": "Patient"}},
               {"resource": {"resourceType": "ImagingStudy", "id": "i", "subject": {"reference": "Patient/p"}},
                "request": {"method": "POST", "url": "ImagingStudy"}}]
    if consent:
        entrees.append({"resource": {"resourceType": "Consent", **consent},
                        "request": {"method": "POST", "url": "Consent"}})
    return {"resourceType": "Bundle", "type": "transaction", "entry": entrees}


def test_retour_sans_consent_inchange():
    b = _retour(None)
    assert extraire_consentement(b) == (b, [])


def test_retour_consent_refuse_403():
    with pytest.raises(ALL.ConsentementRefuse):
        extraire_consentement(_retour({"status": "active", "decision": "deny"}))


def test_retour_consent_retire_avant_import_et_categories_filtrees():
    exclusion = {"provision": [{"provision": [{"resourceType": [{"code": "ImagingStudy"}]}]}]}
    b, alertes = extraire_consentement(_retour({"status": "active", **exclusion}))
    assert [e["resource"]["resourceType"] for e in b["entry"]] == ["Patient"]
    assert alertes and "imagerie" in alertes[0]


# ── accès Oracle (connexion simulée) ─────────────────────────────────────────
class FauxCurseur:
    def __init__(self, conn):
        self.conn, self.description, self._lignes = conn, None, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None, **binds):
        self.conn.requetes.append((" ".join(sql.split()), params or binds))
        if sql.lstrip().startswith("SELECT ipp FROM patient"):
            self._lignes = [("P1-0106",)] if binds.get("v") == "P1-0106" else []
        elif "FROM consentement" in sql:
            self.description = [(c.upper(),) for c in self.conn.colonnes]
            self._lignes = [tuple(l.get(c) for c in self.conn.colonnes) for l in self.conn.versions]

    def fetchone(self):
        return self._lignes[0] if self._lignes else None

    def fetchall(self):
        return list(self._lignes)


class FausseConnexion:
    colonnes = ["id_consentement", "ipp", "statut", "finalite", "date_consentement"]

    def __init__(self, versions):
        self.versions, self.requetes, self.commits, self.rollbacks = versions, [], 0, 0

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _version_active():
    return {"id_consentement": "CST-0106", "ipp": "P1-0106", "statut": "ACTIF",
            "finalite": "Partage soins", "date_consentement": dt(2026, 10, 1)}


def test_retrait_insere_une_version_et_journalise_dans_la_meme_transaction():
    conn = FausseConnexion([_version_active()])
    repo.retirer_consentement(conn, "P1-0106", {"recueilli_par": "Accueil", "motif": "Opposition"},
                              agent="h1-accueil")
    insert = next(p for s, p in conn.requetes if s.startswith("INSERT INTO consentement"))
    assert insert["id_consentement"] == "CST-0106-002" and insert["statut"] == "RETIRE"
    assert insert["motif_retrait"] == "Opposition" and insert["recueilli_par"] == "Accueil"
    journal = next(p for s, p in conn.requetes if s.startswith("INSERT INTO journal_echange"))
    assert journal[0] == "CONSENTEMENT" and journal[2] == "RETIRE"
    assert conn.commits == 1 and conn.rollbacks == 0
    assert any("FOR UPDATE" in s for s, _ in conn.requetes)     # versions sérialisées par patient


def test_retrait_sans_consentement_actif():
    conn = FausseConnexion([dict(_version_active(), statut="REFUSE")])
    with pytest.raises(repo.ConsentementSansObjet):
        repo.retirer_consentement(conn, "P1-0106", {"recueilli_par": "Accueil"}, agent="x")
    assert conn.rollbacks == 1 and not any(s.startswith("INSERT") for s, _ in conn.requetes)


def test_saisie_invalide_annule_la_transaction():
    conn = FausseConnexion([_version_active()])
    with pytest.raises(ALL.CONS.ConsentementInvalide):
        repo.enregistrer_consentement(conn, "P1-0106", {"statut": "actif"}, agent="x")
    assert conn.rollbacks == 1


def test_patient_inconnu():
    with pytest.raises(LookupError):
        repo.lire_consentements(FausseConnexion([]), "P1-9999")


def test_reception_refusee_si_consentement_local_expire():
    conn = FausseConnexion([dict(_version_active())])
    conn.colonnes = FausseConnexion.colonnes + ["date_fin"]
    conn.versions[0]["date_fin"] = dt(2020, 1, 1)
    patient = {"identifier": [{"system": C.SYS_IPP_CHU, "value": "P1-0106"}]}
    with pytest.raises(ALL.ConsentementRefuse) as e:
        repo.verifier_patient_retour(conn, patient)
    assert "expire" in str(e.value)


# ── routes ───────────────────────────────────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("H1_API_TOKEN", JETON)
    conn = FausseConnexion([_version_active()])

    @contextmanager
    def connexion():
        yield conn

    monkeypatch.setattr(repo, "connexion", connexion)
    c = TestClient(api.app, headers={"Authorization": f"Bearer {JETON}"})
    c.conn = conn
    return c


def test_route_lecture(client):
    r = client.get("/api/patients/P1-0106/consentement")
    assert r.status_code == 200 and r.json()["partage_autorise"] is True
    assert r.json()["actuel"]["id"] == "CST-0106"


def test_route_recueil_201(client):
    r = client.post("/api/patients/P1-0106/consentement",
                    json={"statut": "actif", "recueilli_par": "Accueil", "destinataires": ["H2"]})
    assert r.status_code == 201
    assert any(s.startswith("INSERT INTO consentement") for s, _ in client.conn.requetes)


@pytest.mark.parametrize("chemin, corps, code", [
    ("/api/patients/P1-9999/consentement", None, 404),
    ("/api/patients/P1-0106/consentement", {"statut": "actif"}, 422),
])
def test_route_erreurs(client, chemin, corps, code):
    r = client.post(chemin, json=corps) if corps else client.get(chemin)
    assert r.status_code == code and r.json()["resourceType"] == "OperationOutcome"


def test_route_retrait_409(client):
    client.conn.versions[0]["statut"] = "REFUSE"
    r = client.post("/api/patients/P1-0106/consentement/retrait", json={"recueilli_par": "Accueil"})
    assert r.status_code == 409


def test_routes_exigent_un_jeton(client):
    r = TestClient(api.app).get("/api/patients/P1-0106/consentement")
    assert r.status_code == 401
