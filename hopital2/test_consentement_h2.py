"""Consentement côté H2 : recueil, retrait, historique, effets sur l'export,
l'import et la file d'envoi. Lancer : python -m pytest -q (depuis ce dossier)."""
import copy
import json
import os
from dataclasses import replace

import pytest
from bson import json_util
from fastapi.testclient import TestClient
from fhir.resources.bundle import Bundle

import api_h2
import stores
from client_envoi import Outbox, envoyer_dossier, reprendre
from exemples_h1 import bundle_h1
from test_client_envoi import FausseApiH1

DOCS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "patients_h2.json"),
                            encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "referentiels_h2.json"),
                            encoding="utf-8").read())
JETON = "secret-test"
PATIENT = "P2-0051"          # dossier avec imagerie et compte rendu
URL = f"/api/patients/{PATIENT}/consentement"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON)
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire(copy.deepcopy(DOCS), REFS))
    return TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})


def types(bundle):
    return [e["resource"]["resourceType"] for e in bundle["entry"]]


def recueillir(api, **champs):
    corps = {"statut": "actif", "recueilli_par": "Accueil - poste 2", **champs}
    return api.post(URL, json=corps)


# ── lecture ──────────────────────────────────────────────────────────────────
def test_lecture_du_consentement_existant(api):
    r = api.get(URL)
    assert r.status_code == 200
    j = r.json()
    assert j["partage_autorise"] is True and j["actuel"]["statut"] == "actif" and j["historique"] == []


def test_lecture_patient_inconnu_404(api):
    assert api.get("/api/patients/P2-9999/consentement").status_code == 404


# ── recueil ──────────────────────────────────────────────────────────────────
def test_recueil_cree_une_version_et_garde_l_historique(api):
    r = recueillir(api, fin="2030-12-31", destinataires=["H1"])
    assert r.status_code == 201
    j = r.json()
    assert j["actuel"]["fin"] == "2030-12-31" and j["actuel"]["destinataires"] == ["H1"]
    assert len(j["historique"]) == 1 and j["historique"][0]["statut"] == "actif"
    audit = api_h2.STORE.get(PATIENT)["_audit_log"][-1]
    assert audit["event_type"].startswith("Consentement recueilli") and "Accueil - poste 2" in audit["agent_who"]


def test_saisie_incoherente_422_sans_ecriture(api):
    r = recueillir(api, categories_exclues=["genetique"])
    assert r.status_code == 422 and r.json()["resourceType"] == "OperationOutcome"
    assert "consent_history" not in api_h2.STORE.get(PATIENT)


def test_categorie_exclue_retiree_de_l_export(api):
    avant = api.get(f"/api/patients/{PATIENT}/bundle").json()
    assert "ImagingStudy" in types(avant)
    recueillir(api, categories_exclues=["imagerie"])
    apres = api.get(f"/api/patients/{PATIENT}/bundle").json()
    assert "ImagingStudy" not in types(apres) and "Endpoint" not in types(apres)
    Bundle.model_validate(apres)
    assert "ImagingStudy/" not in json.dumps(apres)            # aucune référence orpheline
    consent = next(e["resource"] for e in apres["entry"] if e["resource"]["resourceType"] == "Consent")
    exclus = {t["code"] for t in consent["provision"][0]["provision"][0]["resourceType"]}
    assert exclus == {"ImagingStudy", "Endpoint"}


def test_destinataire_non_autorise_bloque_l_export(api):
    recueillir(api, destinataires=["H2"])                       # le patient n'autorise pas le CHU
    r = api.get(f"/api/patients/{PATIENT}/bundle")
    assert r.status_code == 403 and "H1" in r.json()["issue"][0]["diagnostics"]


def test_consentement_expire_bloque_l_export(api):
    doc = api_h2.STORE.get(PATIENT)
    doc["consent"]["valid_until"] = "2020-01-01"
    api_h2.STORE.remplacer(doc)
    r = api.get(f"/api/patients/{PATIENT}/bundle")
    assert r.status_code == 403 and "expire" in r.json()["issue"][0]["diagnostics"]


# ── retrait ──────────────────────────────────────────────────────────────────
def test_retrait_bloque_l_export_et_reste_trace(api):
    r = api.post(URL + "/retrait", json={"recueilli_par": "Accueil", "motif": "Opposition du patient"})
    assert r.status_code == 200
    j = r.json()
    assert j["partage_autorise"] is False and j["actuel"]["statut"] == "retire"
    assert j["actuel"]["motif_retrait"] == "Opposition du patient" and len(j["historique"]) == 1
    assert api.get(f"/api/patients/{PATIENT}/bundle").status_code == 403


def test_retrait_sans_consentement_actif_409(api):
    api.post(URL + "/retrait", json={"recueilli_par": "Accueil"})
    r = api.post(URL + "/retrait", json={"recueilli_par": "Accueil"})
    assert r.status_code == 409


def test_retrait_sans_agent_422(api):
    assert api.post(URL + "/retrait", json={"motif": "x"}).status_code == 422


def test_nouveau_consentement_apres_retrait_rouvre_le_partage(api):
    api.post(URL + "/retrait", json={"recueilli_par": "Accueil"})
    assert recueillir(api).json()["partage_autorise"] is True
    assert api.get(f"/api/patients/{PATIENT}/bundle").status_code == 200
    assert len(api.get(URL).json()["historique"]) == 2


def test_retrait_local_bloque_la_reception(api):
    api.post(URL + "/retrait", json={"recueilli_par": "Accueil"})
    r = api.post("/api/retours", json=bundle_h1(ipp="P1-0151", cin="AB123456"))
    assert r.status_code == 403 and "retire" in r.json()["issue"][0]["diagnostics"]


# ── consentement reçu dans un Bundle ─────────────────────────────────────────
def _avec_consent(bundle, **modif):
    for e in bundle["entry"]:
        if e["resource"]["resourceType"] == "Consent":
            e["resource"].update(modif)
    return bundle


def test_import_consent_expire_403(api):
    b = _avec_consent(bundle_h1(), period={"start": "2020-01-01", "end": "2021-01-01"})
    r = api.post("/api/retours", json=b)
    assert r.status_code == 403 and "expire" in r.json()["issue"][0]["diagnostics"]


def test_import_consent_reserve_a_un_autre_destinataire_403(api):
    acteur = {"role": {"coding": [{"code": "IRCP"}]},
              "reference": {"identifier": {"system": "urn:interop-sante:etablissement", "value": "H1"}}}
    b = _avec_consent(bundle_h1(), provision=[{"actor": [acteur]}])
    assert api.post("/api/retours", json=b).status_code == 403


def test_import_conserve_la_periode_recue(api):
    b = _avec_consent(bundle_h1(), period={"start": "2026-01-01", "end": "2030-12-31"})
    r = api.post("/api/retours", json=b)
    assert r.status_code in (200, 201), r.text
    doc = api_h2.STORE.get(r.json()["patient_id"])
    assert doc["consent"]["valid_until"] == "2030-12-31"


# ── portées ──────────────────────────────────────────────────────────────────
def test_portees_separees_lecture_et_gestion(api, monkeypatch, tmp_path):
    from securite.jetons import Verificateur, empreinte_complete

    jeton_lecture, jeton_accueil = "jeton-lecture-" + "x" * 30, "jeton-accueil-" + "y" * 30
    registre = tmp_path / "registre.json"
    registre.write_text(json.dumps({"version": 1, "clients": [
        {"id": "lecture", "empreinte": "sha256:" + empreinte_complete(jeton_lecture),
         "portees": ["h2:consentement.lire"], "actif": True},
        {"id": "h2-accueil", "empreinte": "sha256:" + empreinte_complete(jeton_accueil),
         "portees": ["h2:consentement.lire", "h2:consentement.gerer"], "actif": True},
    ]}), encoding="utf-8")
    etat = api_h2.app.state.securite
    conf = replace(etat.conf, registre=registre, jwt_secret="", variable_jeton="")
    monkeypatch.setattr(etat, "verificateur", Verificateur(conf))

    lecture = TestClient(api_h2.app, headers={"Authorization": f"Bearer {jeton_lecture}"})
    accueil = TestClient(api_h2.app, headers={"Authorization": f"Bearer {jeton_accueil}"})
    assert lecture.get(URL).status_code == 200
    assert lecture.post(URL + "/retrait", json={"recueilli_par": "x"}).status_code == 403
    assert accueil.post(URL + "/retrait", json={"recueilli_par": "Accueil"}).status_code == 200
    assert accueil.get(f"/api/patients/{PATIENT}/bundle").status_code == 403   # l'accueil ne lit pas les dossiers


# ── file d'envoi ─────────────────────────────────────────────────────────────
def test_retrait_apres_mise_en_file_annule_l_envoi(api):
    h1, outbox = FausseApiH1(), Outbox()
    h1.mode = "503"                                             # premier essai : H1 indisponible
    r = envoyer_dossier("P2-0052", api, h1.client, outbox, simuler_avant=False, maintenant=0.0)
    assert r["statut"] == "en_attente"
    api.post("/api/patients/P2-0052/consentement/retrait", json={"recueilli_par": "Accueil"})
    h1.mode = "ok"
    res = reprendre(outbox, h1.client, h2=api, maintenant=10**6)
    assert res[0]["statut"] == "annule" and "retire" in res[0]["detail"]
    assert len(h1.definitifs()) == 1                            # seul l'essai initial (refusé en 503)
    assert reprendre(outbox, h1.client, h2=api, maintenant=10**7) == []


def test_consentement_non_verifiable_rien_ne_part(api):
    h1, outbox = FausseApiH1(), Outbox()
    h1.mode = "503"
    envoyer_dossier("P2-0052", api, h1.client, outbox, simuler_avant=False, maintenant=0.0)
    h1.mode = "ok"
    sans_droit = TestClient(api_h2.app)                         # aucun jeton : 401
    res = reprendre(outbox, h1.client, h2=sans_droit, maintenant=10**6)
    assert res[0]["statut"] == "en_attente" and "non vérifiable" in res[0]["detail"]
    assert len(h1.definitifs()) == 1                            # toujours le seul essai initial


# ── droit d'accès de la personne (loi 09-08, art. 7) ─────────────────────────
def test_droit_acces_complet_et_trace(api):
    api.get(f"/api/patients/{PATIENT}/bundle")                 # un export vers H1
    r = api.get(f"/api/patients/{PATIENT}/droit-acces")
    assert r.status_code == 200 and r.headers["cache-control"].startswith("no-store")
    j = r.json()
    assert j["patient"] == PATIENT and j["responsable_du_traitement"]["code"] == "H2"
    Bundle.model_validate(j["donnees"]["dossier_fhir"])
    assert "AuditEvent" not in types(j["donnees"]["dossier_fhir"])
    assert j["destinataires"][0]["code"] == "H1" and j["destinataires"][0]["transmissions"] >= 1
    assert j["consentement"]["partage_autorise"] is True
    assert j["historique_des_acces"][-1]["evenement"].startswith("Droit d'accès")
    assert api_h2.STORE.get(PATIENT)["_audit_log"][-1]["event_type"].startswith("Droit d'accès")


def test_droit_acces_meme_si_le_partage_est_refuse(api):
    """C'est le dossier de la personne : ni consentement ni anti-boucle ne le filtrent."""
    api.post(URL + "/retrait", json={"recueilli_par": "Accueil"})
    r = api.get(f"/api/patients/{PATIENT}/droit-acces")
    assert r.status_code == 200 and "ImagingStudy" in types(r.json()["donnees"]["dossier_fhir"])


def test_droit_acces_reserve_a_sa_portee(api, monkeypatch, tmp_path):
    from securite.jetons import Verificateur, empreinte_complete

    jeton = "jeton-export-" + "w" * 30
    registre = tmp_path / "registre.json"
    registre.write_text(json.dumps({"clients": [
        {"id": "h2-interne", "empreinte": "sha256:" + empreinte_complete(jeton),
         "portees": ["h2:export", "h2:consentement.lire"], "actif": True}]}), encoding="utf-8")
    etat = api_h2.app.state.securite
    monkeypatch.setattr(etat, "verificateur",
                        Verificateur(replace(etat.conf, registre=registre, jwt_secret="", variable_jeton="")))
    r = TestClient(api_h2.app, headers={"Authorization": f"Bearer {jeton}"}).get(
        f"/api/patients/{PATIENT}/droit-acces")
    assert r.status_code == 403 and "h2:droit_acces" in r.json()["issue"][0]["diagnostics"]


def test_droit_acces_patient_inconnu(api):
    assert api.get("/api/patients/P2-9999/droit-acces").status_code == 404
