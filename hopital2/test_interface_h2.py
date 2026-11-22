"""Interface web du personnel, cote H2 : page, config publique, recherche, dossier, envoi."""
import copy
import os
from pathlib import Path

import pytest
from bson import json_util
from fastapi.testclient import TestClient

import api_h2
import stores
from test_client_envoi import FausseApiH1

DOCS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "patients_h2.json"), encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "referentiels_h2.json"), encoding="utf-8").read())
JETON = "secret-test"
STATIQUE = Path(__file__).resolve().parent.parent / "interface" / "static"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON)
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire(copy.deepcopy(DOCS), REFS))
    return TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})


def test_config_et_page_sont_publiques_avec_une_csp_dediee():
    sans_jeton = TestClient(api_h2.app)
    c = sans_jeton.get("/ui/config.json")
    assert c.status_code == 200 and c.json()["service"] == "H2" and c.json()["autre"] == "H1"
    page = sans_jeton.get("/ui/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    csp = page.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp and "frame-ancestors 'none'" in csp
    assert sans_jeton.get("/ui/app.js").status_code == 200 and sans_jeton.get("/ui/style.css").status_code == 200


def test_la_csp_des_routes_de_donnees_reste_fermee(api):
    r = api.get("/api/ui/patients")
    assert r.headers["content-security-policy"].startswith("default-src 'none'; frame-ancestors")


def test_le_code_de_la_page_n_ecrit_jamais_du_html_venu_de_l_api():
    """Le contenu d'un dossier vient de l'autre hopital : jamais d'innerHTML, d'eval, ni de stockage navigateur."""
    js = (STATIQUE / "app.js").read_text(encoding="utf-8")
    for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                     "localStorage", "sessionStorage"):
        assert interdit not in js, interdit
    html = (STATIQUE / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in html and " onclick=" not in html and " style=" not in html


@pytest.mark.parametrize("chemin", ["/api/ui/patients", "/api/ui/dossier/P2-0051", "/api/ui/envois", "/api/ui/journal"])
def test_routes_d_appui_exigent_un_jeton(chemin, monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON)
    assert TestClient(api_h2.app).get(chemin).status_code == 401


def test_recherche_par_nom_cin_et_identifiant(api):
    tous = api.get("/api/ui/patients").json()["resultats"]
    assert 1 <= len(tous) <= 50
    par_id = api.get("/api/ui/patients", params={"q": "P2-0051"}).json()["resultats"]
    assert [p["id"] for p in par_id] == ["P2-0051"]
    par_cin = api.get("/api/ui/patients", params={"q": "ab123456"}).json()["resultats"]
    assert "P2-0051" in [p["id"] for p in par_cin]
    nom = par_id[0]["nom"].lower()
    assert "P2-0051" in [p["id"] for p in api.get("/api/ui/patients", params={"q": nom}).json()["resultats"]]
    assert api.get("/api/ui/patients", params={"q": "zzzz-inconnu"}).json()["resultats"] == []


def test_dossier_lisible(api):
    d = api.get("/api/ui/dossier/P2-0051").json()
    assert d["service"] == "H2" and d["patient"]["id"] == "P2-0051" and d["patient"]["sexe"] in ("M", "F")
    assert d["allergies"] and d["sejours"]
    s = d["sejours"][0]
    assert s["diagnostics"] and s["mesures"] and s["examens"]
    assert api.get("/api/ui/dossier/P2-9999").status_code == 404
    assert api.get("/api/ui/dossier/AB123456").json()["patient"]["id"] == "P2-0051"          # par CIN aussi


def test_envoi_vers_h1_et_file_d_attente(api, monkeypatch, tmp_path):
    import ui_h2
    h1 = FausseApiH1()
    monkeypatch.setenv("H2_FILE_ENVOI", str(tmp_path / "file.sqlite3"))
    monkeypatch.setattr(ui_h2, "client_local", lambda: api)
    monkeypatch.setattr(ui_h2, "client_h1", lambda: h1.client)
    r = api.post("/api/ui/envoi/P2-0051")
    assert r.status_code == 200 and r.json()["statut"] == "envoye", r.text
    liste = api.get("/api/ui/envois").json()["envois"]
    assert len(liste) == 1 and liste[0]["patient_id"] == "P2-0051" and liste[0]["statut"] == "envoye"


def test_envoi_non_configure_donne_un_message_clair(api, monkeypatch, tmp_path):
    monkeypatch.setenv("H2_FILE_ENVOI", str(tmp_path / "file.sqlite3"))
    for variable in ("H2_JETON_LOCAL", "H1_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    r = api.post("/api/ui/envoi/P2-0051")
    assert r.status_code == 503 and "non configure" in r.json()["issue"][0]["diagnostics"]


def test_journal_expose_le_chainage(api):
    api.get("/api/ui/patients")
    r = api.get("/api/ui/journal", params={"limite": 5})
    assert r.status_code == 200 and r.json()["chaine"]["intact"] is True
    assert 1 <= len(r.json()["evenements"]) <= 5 and all("prec" not in e for e in r.json()["evenements"])


# ---------------------------------------------------------------- mode demonstration (DEMO=1)
@pytest.fixture
def demo(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO", "1")
    monkeypatch.setenv("H2_TOKEN", JETON)
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire(copy.deepcopy(DOCS), REFS))
    monkeypatch.setenv("H2_FILE_ENVOI", str(tmp_path / "file.sqlite3"))
    return TestClient(api_h2.app)          # volontairement SANS jeton


def test_demo_desactivee_par_defaut(monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)
    c = TestClient(api_h2.app)
    assert c.get("/api/demo/patients").status_code == 404
    assert c.post("/api/demo/envoi/P2-0051").status_code == 404
    assert c.get("/ui/config.json").json()["demo"] is False


def test_demo_refuse_les_appels_hors_du_poste(demo):
    distant = TestClient(api_h2.app, client=("203.0.113.9", 5000))
    assert distant.get("/api/demo/patients").status_code == 403


def test_demo_liste_sans_compte_et_sans_donnee_medicale(demo):
    r = demo.get("/api/demo/patients")
    assert r.status_code == 200
    d = r.json()
    assert d["autre_etablissement"] and d["patients"]
    assert set(d["patients"][0]) == {"id", "nom", "prenom", "consentement"}
    assert "allergies" not in r.text and "visits" not in r.text


def test_demo_reglage_du_consentement_et_erreurs(demo):
    pid = demo.get("/api/demo/patients").json()["patients"][0]["id"]
    assert demo.post(f"/api/demo/consentement/{pid}/refuse").json()["consentement"]["statut"] == "refuse"

    assert demo.post(f"/api/demo/consentement/{pid}/inconnu").status_code == 422
    assert demo.post("/api/demo/consentement/INCONNU/actif").status_code == 404
    # retrait sans accord actif : message clair (409), pas d'erreur serveur
    assert demo.post(f"/api/demo/consentement/{pid}/retire").status_code == 409


def test_demo_retrait_apres_accord(demo):
    pid = demo.get("/api/demo/patients").json()["patients"][0]["id"]
    assert demo.post(f"/api/demo/consentement/{pid}/actif").json()["consentement"]["partage"] is True
    r = demo.post(f"/api/demo/consentement/{pid}/retire").json()["consentement"]
    assert r["statut"] == "retire" and r["partage"] is False


def test_demo_etapes_deduites_du_resultat_reel():
    from interface.demo import etapes_envoi
    bloque, v = etapes_envoi({"statut": "bloque", "http": 403, "detail": "x"}, {"motif": "refus"}, "CHU")
    assert [x["etat"] for x in bloque] == ["echec", "saute", "saute", "saute", "saute"] and v["etat"] == "bloque"
    ok, v = etapes_envoi({"statut": "envoye", "http": 201}, {}, "CHU")
    assert [x["etat"] for x in ok] == ["ok"] * 5 and v["etat"] == "ok" and ok[4]["texte"] == "Aucune image transférée avec cet envoi."
    vide, _ = etapes_envoi({"statut": "envoye", "http": 201, "imagerie": []}, {}, "CHU")
    assert vide[4]["texte"] == "Aucune image dans ce dossier."
    img, _ = etapes_envoi({"statut": "envoye", "http": 201,
                           "imagerie": [{"statut": "RECUPEREE", "instances": 2}, {"statut": "RECUPEREE", "instances": 3}]}, {}, "CHU")
    assert img[4]["etat"] == "ok" and "2 examen(s) transféré(s), 5 image(s)" in img[4]["texte"]
    refus, _ = etapes_envoi({"statut": "envoye", "http": 201, "imagerie": [{"statut": "REFUSEE"}]}, {}, "CHU")
    assert refus[4]["etat"] == "echec" and "imagerie exclue" in refus[4]["texte"]
    patiente, _ = etapes_envoi({"statut": "envoye", "http": 201, "imagerie": [{"statut": "EN_ATTENTE"}]}, {}, "CHU")
    assert patiente[4]["etat"] == "attente"
    cause, _ = etapes_envoi({"statut": "envoye", "http": 201,
                             "imagerie": [{"statut": "EN_ATTENTE", "detail": "PACS injoignable (ConnectError)"}]}, {}, "CHU")
    assert "PACS injoignable (ConnectError)" in cause[4]["texte"]
    att, v = etapes_envoi({"statut": "en_attente", "http": None, "detail": "injoignable"}, {}, "CHU")
    assert [x["etat"] for x in att] == ["ok", "ok", "attente", "attente", "saute"] and v["etat"] == "attente"
    ref, v = etapes_envoi({"statut": "refuse_simulation", "http": 422, "detail": "d"}, {}, "CHU")
    assert [x["etat"] for x in ref] == ["ok", "ok", "echec", "saute", "saute"] and v["etat"] == "echec"
    inconnu, v = etapes_envoi({"statut": "refuse_simulation", "http": 404,
                               "detail": "not-found: Patient introuvable dans H1."}, {}, "CHU")
    assert "inconnu" in v["titre"] and "rien n'est transféré" in v["titre"] and inconnu[3]["etat"] == "saute"


def test_page_demo_n_ecrit_jamais_du_html_venu_de_l_api():
    js = (STATIQUE / "demo.js").read_text(encoding="utf-8")
    for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                     "localStorage", "sessionStorage", "Authorization"):
        assert interdit not in js, interdit
    html = (STATIQUE / "demo.html").read_text(encoding="utf-8")
    assert "<script>" not in html and " onclick=" not in html and " style=" not in html


def test_demo_detail_envoyes_et_recus(demo, monkeypatch):
    """Fiche patient + contenu du Bundle ; listes des envoyes et des recus."""
    import ui_h2
    from interface.demo import lire_reponse_bundle
    r = demo.get("/api/demo/patients").json()
    assert r["envoyes"] == [] and isinstance(r["recus"], list) and len(r["patients"]) == 60
    pid = "P2-0051"
    d = demo.get(f"/api/demo/patient/{pid}")
    assert d.status_code == 200 and d.json()["dossier"]["patient"]["id"] == pid
    assert demo.get("/api/demo/patient/INCONNU").status_code == 404

    class Rep:                                        # reponse simulee de GET .../bundle
        status_code = 200
        def json(self):
            return {"type": "transaction", "entry": [
                {"request": {"method": "PUT"}, "resource": {"resourceType": "Patient", "id": "p", "name": [{"family": "X", "given": ["Y"]}]}},
                {"request": {"method": "PUT"}, "resource": {"resourceType": "Observation", "id": "o",
                 "code": {"text": "Glycemie"}, "valueQuantity": {"value": 1.2, "unit": "g/L"}}}]}
    b = lire_reponse_bundle(Rep())
    assert b["disponible"] and b["total"] == 2 and {c["type"] for c in b["comptes"]} == {"Patient", "Observation"}
    assert [x["resume"] for x in b["entrees"]] == ["Y X", "Glycemie : 1.2 g/L"] and '"resourceType"' in b["entrees"][0]["json"]

    class Refus(Rep):
        status_code = 403
        def json(self):
            return {"issue": [{"diagnostics": "Export refuse : consentement refuse (loi 09-08)."}]}
    assert lire_reponse_bundle(Refus())["disponible"] is False and "consentement" in lire_reponse_bundle(Refus())["motif"]

    # patient recu : une ligne d'audit « Reception d'un dossier » le fait apparaitre dans les recus
    doc = api_h2.STORE.get(pid)
    api_h2.STORE.docs[pid].setdefault("_audit_log", []).append(
        {"event_type": "Réception d'un dossier (Bundle)", "recorded_at": "2026-11-22T09:00:00+00:00"})
    assert [x["patient"] for x in demo.get("/api/demo/patients").json()["recus"]] == [pid]


def test_les_noms_de_famille_des_patients_de_h2_sont_tous_differents():
    noms = [d["last_name"] for d in DOCS]
    assert len(noms) == len(set(noms)) == 60


# ── aperçu des images DICOM ──────────────────────────────────────────────────
UID_ETUDE = "2.25.11060236952204337488"        # étude de P2-0051 dans les données de démonstration


@pytest.fixture
def pacs(monkeypatch):
    from datetime import datetime
    import ui_h2
    from imagerie.dicom import generer_etude, vers_octets
    from imagerie.dicomweb import EntrepotMemoire
    memoire = EntrepotMemoire()
    memoire.stocker([vers_octets(ds) for ds in generer_etude(
        {"id": "P2-0051", "nom": "Alaoui", "prenom": "Youssef", "naissance": "1968-04-12", "sexe": "M"},
        {"study_uid": UID_ETUDE, "instances": 2, "date": datetime(2026, 9, 20)}, etablissement="Clinique")])
    monkeypatch.setattr(ui_h2.AdaptateurH2, "_pacs", lambda self: memoire)
    return memoire


def test_demo_fiche_liste_les_examens_d_imagerie(demo):
    dossier = demo.get("/api/demo/patient/P2-0051").json()["dossier"]
    assert any(x["study_uid"] == UID_ETUDE and x["pret"] and x["instances"] == 2 for x in dossier["imagerie"])


def test_demo_apercu_png_d_une_image(demo, pacs):
    r = demo.get(f"/api/demo/image/P2-0051/{UID_ETUDE}/1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content.startswith(b"\x89PNG")
    for secret in (b"ALAOUI", b"Alaoui", b"Youssef", b"P2-0051"):
        assert secret not in r.content


def test_demo_apercu_refuse_une_etude_d_un_autre_patient_ou_inconnue(demo, pacs):
    autre = demo.get("/api/demo/patients").json()["patients"]
    autre_id = next(p["id"] for p in autre if p["id"] != "P2-0051")
    assert demo.get(f"/api/demo/image/{autre_id}/{UID_ETUDE}/0").status_code == 404      # pas son étude
    assert demo.get("/api/demo/image/P2-0051/2.25.999/0").status_code == 404
    assert demo.get(f"/api/demo/image/P2-0051/{UID_ETUDE}/7").status_code == 404         # rang hors étude
    assert demo.get("/api/demo/image/P2-0051/abc..%3Cscript%3E/0").status_code == 422
    assert demo.get(f"/api/demo/image/P2-0051/{UID_ETUDE}/500").status_code == 422


def test_demo_apercu_sans_pacs_repond_503_pas_500(demo, monkeypatch):
    import ui_h2
    monkeypatch.setattr(ui_h2.AdaptateurH2, "_pacs", lambda self: None)
    assert demo.get(f"/api/demo/image/P2-0051/{UID_ETUDE}/0").status_code == 503


def test_demo_apercu_desactive_sans_demo(monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)
    assert TestClient(api_h2.app).get(f"/api/demo/image/P2-0051/{UID_ETUDE}/0").status_code == 404
