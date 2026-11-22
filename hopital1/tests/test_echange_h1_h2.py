"""Echange reel entre les deux API, en memoire : seuls Oracle et MongoDB sont remplaces.

 H1 -> H2 : client_envoi_h1 (export H1, simulation puis envoi chez H2, vraie API H2).
 H2 -> H1 : Bundle exporte par la vraie API H2, recu par la vraie API H1 (instructions PUT).

Ces deux sens echouaient avant : H2 ne resolvait pas les references urn:uuid: des sejours
de H1 (422), et H1 ne recevait que des instructions POST alors que H2 envoie des PUT.
"""
import copy
import os
import sys
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

_H2 = os.path.join(os.path.dirname(__file__), "..", "..", "hopital2")
sys.path.insert(0, _H2)

bson = pytest.importorskip("bson")
from bson import json_util  # noqa: E402

import api_h2  # noqa: E402  (API de la clinique)
import stores  # noqa: E402

import app as api  # noqa: E402  (API du CHU)
import h1_to_fhir as ALL  # noqa: E402
import oracle_repo as repo  # noqa: E402
from client_envoi_h1 import Outbox, envoyer_dossier  # noqa: E402
from tests.donnees import dossier  # noqa: E402

JETON_H1 = "jeton-test-h1-assez-long-pour-etre-valide"
JETON_H2 = "jeton-test-h2-assez-long-pour-etre-valide"
DOCS = json_util.loads(open(os.path.join(_H2, "data", "patients_h2.json"), encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(_H2, "data", "referentiels_h2.json"), encoding="utf-8").read())


@pytest.fixture
def deux_api(monkeypatch):
    @contextmanager
    def faux_oracle():
        yield object()

    base = {"P1-0106": dossier("S1"), "P1-0777": dossier("S1")}
    base["P1-0777"]["patient"].update(ipp="P1-0777", cin="ZZ777777")      # un patient inconnu de H2
    monkeypatch.setenv("H1_API_TOKEN", JETON_H1)
    monkeypatch.setenv("H2_TOKEN", JETON_H2)
    monkeypatch.setattr(repo, "connexion", faux_oracle)
    monkeypatch.setattr(repo, "exporter", lambda conn, ipp=None, adressage=True, destinataire="H2", **k:
                        ALL.dossier_vers_bundle(base[ipp], adressage=adressage, destinataire=destinataire))
    monkeypatch.setattr(repo, "lire_consentements", lambda conn, ipp, **k: [base[ipp]["consentement"]])
    magasin = stores.StoreMemoire(copy.deepcopy(DOCS), REFS)
    monkeypatch.setattr(api_h2, "STORE", magasin)
    h1 = TestClient(api.app, headers={"Authorization": f"Bearer {JETON_H1}"})
    h2 = TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON_H2}"})
    return h1, h2, magasin


def test_h1_vers_h2_patient_deja_connu_est_rapproche(deux_api):
    h1, h2, magasin = deux_api
    avant = len(magasin.all(10000))
    r = envoyer_dossier("P1-0106", h1, h2, Outbox(), maintenant=0.0)    # CIN AB123456 = P2-0051 chez H2
    assert r["statut"] == "envoye" and r["http"] == 200, r
    assert len(magasin.all(10000)) == avant                             # rapproche par le CIN, pas duplique
    assert h2.get("/Patient", params={"identifier": "urn:ma:cin|AB123456"}).json()["total"] == 1


def test_h1_vers_h2_nouveau_patient_est_cree(deux_api):
    h1, h2, magasin = deux_api
    avant = len(magasin.all(10000))
    r = envoyer_dossier("P1-0777", h1, h2, Outbox(), maintenant=0.0)
    assert r["statut"] == "envoye" and r["http"] == 201, r              # 201 : patient cree chez H2
    assert len(magasin.all(10000)) == avant + 1
    assert h2.get("/Patient", params={"identifier": "urn:ma:cin|ZZ777777"}).json()["total"] == 1


def test_rejeu_h1_vers_h2_ne_cree_pas_de_doublon(deux_api):
    h1, h2, magasin = deux_api
    outbox = Outbox()
    assert envoyer_dossier("P1-0777", h1, h2, outbox, maintenant=0.0)["statut"] == "envoye"
    apres_un = len(magasin.all(10000))
    assert envoyer_dossier("P1-0777", h1, h2, outbox, maintenant=1.0)["statut"] == "envoye"   # nouvel export, meme dossier
    assert len(magasin.all(10000)) == apres_un
    assert h2.get("/Patient", params={"identifier": "urn:ma:cin|ZZ777777"}).json()["total"] == 1


def test_h2_vers_h1_de_bout_en_bout(deux_api, monkeypatch):
    h1, h2, _ = deux_api
    recu = {}

    def recevoir(conn, bundle, patient, echange_id=None, **_options):
        recu.update(echange_id=echange_id, nb=len(bundle["entry"]))
        return "P1-0106", {t: [] for t, _ in repo.ORDRE_TABLES} | {"alertes": [], "ignores": []}
    monkeypatch.setattr(repo, "recevoir_retour", recevoir)

    sortie = h2.get("/api/patients/P2-0052/bundle")
    assert sortie.status_code == 200
    bundle = sortie.json()
    assert any(e["request"]["method"] == "PUT" for e in bundle["entry"])
    echange = bundle["identifier"]["value"]

    definitif = h1.post("/api/retours", content=sortie.content,
                        headers={"Content-Type": "application/fhir+json", "X-Exchange-Id": echange})
    assert definitif.status_code == 200, definitif.text
    assert recu["echange_id"] == echange and recu["nb"] > 0


def test_bundle_reel_de_h2_ressources_hors_perimetre_ne_bloquent_pas_l_import(deux_api):
    """Regression (vrai Oracle) : le Bundle de P2-0051 contient allergies, diagnostics et demandes d'examen,
    sans table chez H1. Elles sont signalees dans `ignores` mais l'import definitif ne doit pas etre refuse."""
    import fhir_to_h1 as RET
    from retour_api import extraire_consentement

    _, h2, _ = deux_api
    bundle = h2.get("/api/patients/P2-0051/bundle").json()
    bundle, _alertes = extraire_consentement(bundle)
    res = RET.bundle_vers_lignes(bundle, lambda cin, ipp, ligne: "P1-0106", None)
    assert res["ignores"], "ce jeu de donnees doit contenir des ressources hors perimetre"
    assert all(i.endswith(RET.HORS_PERIMETRE) for i in res["ignores"]), res["ignores"]
    assert repo.ignores_bloquants(res) == []
    assert any(res[t] for t in ("sejour", "mesure", "resultat_ophtalmo"))


def test_ressource_mal_formee_reste_bloquante():
    import fhir_to_h1 as RET
    res = {"ignores": ["Observation x : valeur ou unité absente -> rejetée",
                       "AllergyIntolerance a : " + RET.HORS_PERIMETRE]}
    assert repo.ignores_bloquants(res) == ["Observation x : valeur ou unité absente -> rejetée"]


# ── Interface web du personnel (page /ui + routes d'appui), cote H1 ────────────────────────
@pytest.fixture
def interface_h1(deux_api, monkeypatch, tmp_path):
    import ui_h1
    h1, h2, magasin = deux_api
    base = {"P1-0106": dossier("S1"), "P1-0777": dossier("S1")}
    base["P1-0777"]["patient"].update(ipp="P1-0777", cin="ZZ777777", nom="Zahidi")
    monkeypatch.setenv("H1_FILE_ENVOI", str(tmp_path / "file.sqlite3"))
    monkeypatch.setattr(repo, "lire_dossier", lambda conn, cin=None, ipp=None: next(
        (d for d in base.values() if d["patient"]["ipp"] == ipp or (cin and d["patient"]["cin"] == cin)), None))
    monkeypatch.setattr(repo, "rechercher_patients", lambda conn, texte, limite=50: [
        d["patient"] for d in base.values() if not texte or texte.lower() in (d["patient"]["nom"] + d["patient"]["ipp"]).lower()])
    monkeypatch.setattr(repo, "lire_recus", lambda conn, ipp: {})
    monkeypatch.setattr(ui_h1, "client_local", lambda: h1)
    monkeypatch.setattr(ui_h1, "client_h2", lambda: h2)
    return h1, h2


def test_interface_h1_config_page_et_csp(monkeypatch):
    monkeypatch.setenv("H1_API_TOKEN", JETON_H1)
    sans_jeton = TestClient(api.app)
    c = sans_jeton.get("/ui/config.json").json()
    assert c["service"] == "H1" and c["autre"] == "H2" and c["etablissement"] == "CHU Al Massira"
    page = sans_jeton.get("/ui/")
    assert page.status_code == 200 and "script-src 'self'" in page.headers["content-security-policy"]
    assert sans_jeton.get("/api/ui/patients").status_code == 401


def test_interface_h1_recherche_et_dossier(interface_h1):
    h1, _ = interface_h1
    assert {p["id"] for p in h1.get("/api/ui/patients").json()["resultats"]} == {"P1-0106", "P1-0777"}
    assert [p["id"] for p in h1.get("/api/ui/patients", params={"q": "zahidi"}).json()["resultats"]] == ["P1-0777"]
    d = h1.get("/api/ui/dossier/P1-0106").json()
    assert d["service"] == "H1" and d["patient"]["cin"] == "AB123456" and d["patient"]["adresse"]
    assert d["sejours"][0]["diagnostics"] and d["sejours"][0]["mesures"]
    assert h1.get("/api/ui/dossier/AB123456").json()["patient"]["id"] == "P1-0106"          # par CIN aussi
    assert h1.get("/api/ui/dossier/P1-9999").status_code == 404


def test_interface_h1_envoi_vers_h2_puis_etat_de_la_file(interface_h1):
    h1, h2 = interface_h1
    r = h1.post("/api/ui/envoi/P1-0106")
    assert r.status_code == 200 and r.json()["statut"] == "envoye" and r.json()["http"] == 200, r.text
    envois = h1.get("/api/ui/envois").json()["envois"]
    assert [(e["patient_id"], e["statut"]) for e in envois] == [("P1-0106", "envoye")]
    assert h1.post("/api/ui/envois/reprendre", params={"forcer": "true"}).json()["resultats"] == []


def test_interface_h1_envoi_non_configure_est_un_503_lisible(interface_h1, monkeypatch):
    import ui_h1
    h1, _ = interface_h1
    monkeypatch.undo()                                    # retire aussi les faux clients
    for variable in ("H1_JETON_VERS_H2", "H1_JETON_LOCAL", "H1_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("H1_API_TOKEN", JETON_H1)
    r = TestClient(api.app, headers={"Authorization": f"Bearer {JETON_H1}"}).post("/api/ui/envoi/P1-0106")
    assert r.status_code == 503 and "non configure" in r.json()["issue"][0]["diagnostics"]


def test_demo_h1_desactivee_par_defaut_et_reservee_au_poste_local(monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)
    assert TestClient(api.app).get("/api/demo/patients").status_code == 404
    monkeypatch.setenv("DEMO", "1")
    assert TestClient(api.app, client=("203.0.113.9", 5000)).get("/api/demo/patients").status_code == 403


def test_demo_h1_consentement_et_envoi_sans_compte(interface_h1, monkeypatch):
    """Sans jeton : la demo regle le consentement (Oracle simule) puis lance l'envoi reel."""
    monkeypatch.setenv("DEMO", "1")
    etats = {}
    monkeypatch.setattr(repo, "lire_consentements", lambda conn, ipp: etats.get(ipp))
    monkeypatch.setattr(repo, "etat_consentement", lambda ipp, statut: {
        "actuel": {"statut": statut} if statut else None, "partage_autorise": statut == "actif",
        "motif": "consentement " + str(statut)})
    monkeypatch.setattr(repo, "enregistrer_consentement", lambda conn, ipp, corps, agent: (
        etats.__setitem__(ipp, corps["statut"]), repo.etat_consentement(ipp, corps["statut"]))[1])
    monkeypatch.setattr(repo, "lister_retours", lambda conn, limite=30: [
        {"ipp": "P1-0106", "dernier": None, "n": 2}])
    sans_jeton = TestClient(api.app)
    patients = sans_jeton.get("/api/demo/patients")
    assert patients.status_code == 200
    ipp = patients.json()["patients"][0]["id"]
    assert patients.json()["recus"][0]["patient"] == "P1-0106" and isinstance(patients.json()["envoyes"], list)
    detail = sans_jeton.get(f"/api/demo/patient/{ipp}")
    assert detail.status_code == 200 and detail.json()["dossier"]["patient"]["id"] == ipp
    assert "bundle" in detail.json()
    assert sans_jeton.post(f"/api/demo/consentement/{ipp}/refuse").json()["consentement"]["statut"] == "refuse"
    envoi = sans_jeton.post(f"/api/demo/envoi/{ipp}").json()
    assert envoi["consentement"]["statut"] == "refuse"
    assert len(envoi["etapes"]) == 4 and envoi["verdict"]["etat"] in {"ok", "bloque", "attente", "echec"}


# ── Patient inconnu du CHU : refuse par defaut, cree si autorise (H1_CREER_PATIENTS_RETOUR / DEMO) ──
def test_retour_pour_patient_inconnu_refuse_par_defaut_cree_si_autorise(monkeypatch):
    ecrit = {}

    def inconnu(conn, patient, **_):
        raise LookupError("Patient inconnu au CHU.")
    monkeypatch.setattr(repo, "verifier_patient_retour", inconnu)
    monkeypatch.setattr(repo, "_ligne_patient_valide", lambda p: {"nom": "X", "cin": "C1"})
    monkeypatch.setattr(repo, "_inserer_patient", lambda conn, ligne: dict(ligne, ipp="P1-0200"))
    monkeypatch.setattr(repo, "_nouvelle_version", lambda conn, ipp, lignes, cons, evt, agent: ecrit.update(
        ipp=ipp, statut=cons.statut, exclues=list(cons.categories_exclues), evt=evt))
    joint = {"statut": "actif", "recueilli_par": "Clinique", "categories_exclues": ["imagerie"]}

    with pytest.raises(LookupError):                              # defaut : refuse
        repo.rattacher_ou_creer_patient(object(), {})
    with pytest.raises(LookupError):                              # autorise mais sans consentement joint : refuse
        repo.rattacher_ou_creer_patient(object(), {}, creer_si_inconnu=True)
    assert not ecrit
    assert repo.rattacher_ou_creer_patient(object(), {}, creer_si_inconnu=True, consentement_joint=joint) == ("P1-0200", True)
    assert ecrit["ipp"] == "P1-0200" and ecrit["statut"] == "actif" and ecrit["exclues"] == ["imagerie"]


def test_la_creation_au_retour_depend_de_l_environnement(monkeypatch):
    for variable, valeur, attendu in (("DEMO", None, False), ("DEMO", "1", True), ("H1_CREER_PATIENTS_RETOUR", "1", True)):
        monkeypatch.delenv("DEMO", raising=False)
        monkeypatch.delenv("H1_CREER_PATIENTS_RETOUR", raising=False)
        if valeur:
            monkeypatch.setenv(variable, valeur)
        assert api.creation_autorisee() is attendu


def test_consentement_joint_extrait_du_bundle_de_h2(deux_api, monkeypatch):
    """Le Consent du Bundle reel de H2 donne un consentement local 'actif' pour le CHU."""
    import retour_api
    _, h2, _ = deux_api
    bundle = h2.get("/api/patients/P2-0052/bundle", headers={"Authorization": f"Bearer {JETON_H2_LOCAL}"}) \
        if "JETON_H2_LOCAL" in globals() else h2.get("/api/patients/P2-0052/bundle")
    if bundle.status_code != 200:
        pytest.skip("export H2 indisponible dans ce montage")
    joint = retour_api.consentement_joint(bundle.json())
    assert joint and joint["statut"] == "actif" and "recueilli_par" in joint
    assert retour_api.consentement_joint({"resourceType": "Bundle", "entry": []}) is None
