"""Tests de l'API H2 v3. Lancer :  python -m pytest -q   (depuis ce dossier)"""
import copy
import json
from dataclasses import replace

from bson import json_util
import os

import pytest
from fastapi.testclient import TestClient
from fhir.resources.bundle import Bundle

import adaptateur_fhir_h2 as fhir_vers_h2
import adaptateur_h2_fhir as h2_vers_fhir
import api_h2
import echange
import stores
from exemples_h1 import SYSTEM_IPP_H1, bundle_h1

DOCS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "patients_h2.json"), encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "referentiels_h2.json"), encoding="utf-8").read())
JETON = "secret-test"


CLE_TEST = "v1:" + "A" * 43                  # 32 octets nuls en base64url : tests seulement


def _fabriquer_store(kind):
    if kind == "memoire":
        return stores.StoreMemoire(copy.deepcopy(DOCS), REFS)
    import mongomock
    if kind == "mongo_chiffre":                  # dossiers chiffrés au repos (AES-256-GCM)
        from securite.chiffrement import Chiffreur
        s = stores.StoreMongoChiffre(client=mongomock.MongoClient(), nom_base="hopital2",
                                     chiffreur=Chiffreur.depuis_texte(CLE_TEST))
        for d in copy.deepcopy(DOCS):
            s.remplacer(d)
    else:
        s = stores.StoreMongo(client=mongomock.MongoClient(), nom_base="hopital2")
        s.col.insert_many(copy.deepcopy(DOCS))
    for nom, docs in REFS.items():
        s.db[nom].insert_many(copy.deepcopy(docs))
    return s


@pytest.fixture(params=["memoire", "mongo", "mongo_chiffre"])
def api(request, monkeypatch):
    """Client HTTP authentifié, sur chaque type de base (mémoire, MongoDB simulé)."""
    monkeypatch.setenv("H2_TOKEN", JETON)
    monkeypatch.setattr(api_h2, "STORE", _fabriquer_store(request.param))
    return TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})


def nb_patients():
    return len(api_h2.STORE.all(10000))


def importer(api, bundle, simulation=False, **entetes):
    return api.post("/api/retours/simulation" if simulation else "/api/retours", json=bundle, headers=entetes)


def types(bundle):
    return [e["resource"]["resourceType"] for e in bundle["entry"]]


# ═════════════════════════════════════════════════════════════════════════════
# Authentification et routes publiques
# ═════════════════════════════════════════════════════════════════════════════
def test_health_et_metadata_sans_jeton(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON)
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire())
    c = TestClient(api_h2.app)
    h = c.get("/health")
    assert h.status_code == 200 and h.json()["statut"] == "ok"
    # /health ne publie plus l'etat de l'authentification : annoncer
    # « authentification desactivee » a un appelant anonyme lui indiquerait
    # ou insister (voir docs/securite/politique-securite.md, constat P1-4).
    assert "authentification" not in h.json()
    m = c.get("/metadata")
    assert m.status_code == 200 and m.json()["resourceType"] == "CapabilityStatement"
    assert m.json()["fhirVersion"] == "5.0.0"


def test_uri_mongo_encode_les_identifiants(monkeypatch):
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.setenv("MONGO_UTILISATEUR", "compte@h2")
    monkeypatch.setenv("MONGO_MOT_DE_PASSE", "exemple:/?")
    monkeypatch.setenv("MONGO_HOTE", "mongo")
    assert api_h2.uri_mongo() == (
        "mongodb://compte%40h2:exemple%3A%2F%3F@mongo:27017/?authSource=admin")


@pytest.mark.parametrize("methode,chemin", [
    ("get", "/api/patients/P2-0051/bundle"), ("post", "/api/retours"), ("post", "/api/retours/simulation"),
    ("post", "/Bundle"), ("get", "/Patient/P2-0051"), ("get", "/Patient"), ("post", "/Patient"),
    ("get", "/Patient/P2-0051/$everything")])
def test_routes_protegees_exigent_le_jeton(monkeypatch, methode, chemin):
    monkeypatch.setenv("H2_TOKEN", JETON)
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire(copy.deepcopy(DOCS), REFS))
    c = TestClient(api_h2.app)
    r = getattr(c, methode)(chemin)
    assert r.status_code == 401
    assert r.json()["resourceType"] == "OperationOutcome"
    assert r.headers["www-authenticate"] == 'Bearer realm="H2"'
    r = getattr(c, methode)(chemin, headers={"Authorization": "Bearer mauvais"})
    assert r.status_code == 401
    r = getattr(c, methode)(chemin, headers={"Authorization": f"Basic {JETON}"})
    assert r.status_code == 401


def test_sans_jeton_configure_les_routes_de_dossier_sont_fermees(monkeypatch, tmp_path):
    """Sans authentification configuree, l'API ne sert AUCUNE donnee de sante.

    L'ancienne version basculait en « mode developpement » et repondait 200 :
    une API de donnees de sante totalement ouverte des que la variable
    H2_TOKEN etait absente ou mal orthographiee (constat P0-1 de
    docs/securite/politique-securite.md). Le comportement attendu est
    maintenant 503 : le service se declare indisponible plutot que de s'ouvrir.
    """
    # Isoler les trois sources de jetons : un poste de developpement peut
    # posseder un registre et une cle JWT dans ses fichiers .env locaux.
    from securite.jetons import Verificateur

    etat = api_h2.app.state.securite
    sans_jeton = replace(etat.conf, registre=tmp_path / "registre-absent.json",
                         jwt_secret="", variable_jeton="")
    monkeypatch.setattr(etat, "verificateur", Verificateur(sans_jeton))
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire(copy.deepcopy(DOCS), REFS))
    c = TestClient(api_h2.app)

    r = c.get("/api/patients/P2-0051/bundle")
    assert r.status_code == 503
    assert r.json()["resourceType"] == "OperationOutcome"

    # Meme avec un jeton inventé : rien ne passe.
    assert c.get("/api/patients/P2-0051/bundle",
                 headers={"Authorization": "Bearer nimporte-quoi"}).status_code == 503

    # /health reste joignable : il ne renvoie aucune donnee de patient et sert
    # aux sondes de supervision.
    assert c.get("/health").status_code == 200


def test_route_inconnue_renvoie_operation_outcome(api):
    r = api.get("/nimporte/quoi")
    assert r.status_code == 404 and r.json()["resourceType"] == "OperationOutcome"


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT  H2 → H1
# ═════════════════════════════════════════════════════════════════════════════
def test_export_bundle_transaction_valide_r5(api):
    r = api.get("/api/patients/P2-0051/bundle")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/fhir+json")
    b = r.json()
    assert b["type"] == "transaction" and b["identifier"]["system"] == echange.SYSTEM_ECHANGE
    Bundle.model_validate(b)                                   # FHIR R5 valide (fhir.resources)


def test_export_un_seul_patient_cin_et_instructions(api):
    b = api.get("/api/patients/P2-0051/bundle").json()
    assert types(b).count("Patient") == 1
    patient = b["entry"][0]
    assert patient["resource"]["resourceType"] == "Patient"
    ids = {(i["system"], i["value"]) for i in patient["resource"]["identifier"]}
    assert ("urn:ma:cin", "AB123456") in ids and ("urn:clinique-al-bacar:patient", "P2-0051") in ids
    assert patient["request"] == {"method": "POST", "url": "Patient",
                                  "ifNoneExist": "identifier=urn:ma:cin|AB123456"}
    for e in b["entry"][1:]:
        res = e["resource"]
        assert e["request"] == {"method": "PUT", "url": f"{res['resourceType']}/{res['id']}"}


def test_export_unites_ucum_et_sans_audit(api):
    b = api.get("/api/patients/P2-0051/bundle").json()
    assert "AuditEvent" not in types(b)
    codes = {q["code"] for e in b["entry"] for q in
             [e["resource"].get("valueQuantity", {})] + [c.get("valueQuantity", {})
                                                         for c in e["resource"].get("component", [])] if q}
    assert "mmHg" not in codes and "mm[Hg]" in codes
    assert "AuditEvent" in types(api.get("/api/patients/P2-0051/bundle?inclure_audit=true").json())


def _orphelines(bundle):
    ids = {f"{e['resource']['resourceType']}/{e['resource']['id']}" for e in bundle["entry"]}
    return {r for e in bundle["entry"] for r in echange._references(e["resource"]) if r not in ids}


def test_export_ne_garde_que_l_annuaire_reference_par_le_dossier(api):
    """Minimisation (loi 09-08) : pas les 30 médecins, rôles, équipements et services de la clinique."""
    b = api.get("/api/patients/P2-0051/bundle").json()
    t = types(b)
    for inutile in ("Practitioner", "PractitionerRole", "Device", "Location"):
        assert inutile not in t
    assert t.count("Organization") == 1 and t.count("Endpoint") == 1       # clinique + PACS référencés
    assert len(b["entry"]) == 16 and not _orphelines(b)
    complet = api.get("/api/patients/P2-0051/bundle?inclure_catalogue=true").json()
    # avec le catalogue : SON médecin, SON rôle, SON service — pas les 28 praticiens de la clinique
    assert len(complet["entry"]) == 19 and types(complet).count("Practitioner") == 1
    assert types(complet).count("PractitionerRole") == 1 and types(complet).count("Location") == 1
    assert not _orphelines(complet)


def test_export_groupe_sanguin_en_observation_loinc(api):
    b = api.get("/api/patients/P2-0051/bundle").json()
    sang = [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Observation"
            and e["resource"]["code"]["coding"][0]["code"] == "882-1"]
    assert len(sang) == 1 and sang[0]["valueString"] == "B+" and "encounter" not in sang[0]


def test_export_consentement_refuse_403_et_audit(api):
    doc = api_h2.STORE.get("P2-0054")
    doc["consent"]["status"] = "refused"
    api_h2.STORE.remplacer(doc)
    r = api.get("/api/patients/P2-0054/bundle")
    assert r.status_code == 403 and r.json()["issue"][0]["code"] == "forbidden"
    audit = api_h2.STORE.get("P2-0054")["_audit_log"][-1]
    assert audit["outcome_code"] == "refused" and audit["action"] == "read"


def test_export_patient_inconnu_404(api):
    r = api.get("/api/patients/P2-9999/bundle")
    assert r.status_code == 404 and r.json()["issue"][0]["code"] == "not-found"


def test_export_par_cin(api):
    r = api.get("/api/patients/AB123456/bundle")
    assert r.status_code == 200 and "Patient/P2-0051" in json.dumps(r.json()["entry"][0])


def test_export_ecrit_une_ligne_d_audit(api):
    avant = len(api_h2.STORE.get("P2-0052").get("_audit_log", []))
    echange_id = api.get("/api/patients/P2-0052/bundle").json()["identifier"]["value"]
    audit = api_h2.STORE.get("P2-0052")["_audit_log"]
    assert len(audit) == avant + 1 and audit[-1]["exchange_id"] == echange_id and audit[-1]["outcome_code"] == "success"


def test_les_60_patients_s_exportent_en_r5_et_reviennent_en_base():
    for doc in copy.deepcopy(DOCS):
        if doc["consent"]["status"] != "active":                    # D2 (P2-0054) : refus → export bloqué
            with pytest.raises(echange.ConsentError):
                echange.construire_bundle(doc, referentiels=REFS)
            continue
        b = echange.construire_bundle(doc, referentiels=REFS)
        Bundle.model_validate(b)
        assert not _orphelines(b), doc["patient_id"]                   # aucune référence vers une ressource absente
        retour = fhir_vers_h2.bundle_to_h2_document(b)         # mode strict : aucune erreur
        assert retour["national_id"] == doc["national_id"] and retour["blood_type"] == doc["blood_type"]


# ═════════════════════════════════════════════════════════════════════════════
# IMPORT  H1 → H2
# ═════════════════════════════════════════════════════════════════════════════
def test_simulation_n_ecrit_rien(api):
    r = importer(api, bundle_h1(), simulation=True)
    assert r.status_code == 200
    j = r.json()
    assert j["simulation"] is True and j["modifications_conservees"] is False
    assert j["patient_cree"] is True and j["patient_id_provisoire"] is True
    assert nb_patients() == 60 and api_h2.STORE.get(j["patient_id"]) is None


def test_import_nouveau_patient_201(api):
    r = importer(api, bundle_h1())
    assert r.status_code == 201 and r.headers["location"] == "/Patient/P2-0061"
    j = r.json()
    assert j["patient_id"] == "P2-0061" and j["patient_cree"] is True and j["modifications_conservees"] is True
    assert j["lignes_par_type"] == {"Patient": 1, "Consent": 1, "Encounter": 1, "Condition": 1, "Observation": 2}
    doc = api_h2.STORE.get("P2-0061")
    assert doc["national_id"] == "CD654321" and doc["blood_type"] == "O+" and doc["consent"]["status"] == "active"
    assert doc["_external_ids"] == [{"system": SYSTEM_IPP_H1, "value": "P1-0106"}]
    assert doc["_origin"] == "H1" and doc["visits"][0]["_origin"] == "H1"
    assert api.get("/Patient?identifier=" + SYSTEM_IPP_H1 + "|P1-0106").json()["total"] == 1
    assert api.get("/Patient?identifier=urn:ma:cin|CD654321").json()["total"] == 1


def test_import_ecrit_l_audit_dans_le_meme_document(api):
    j = importer(api, bundle_h1(), **{"X-Exchange-Id": "ech-100"}).json()
    audit = api_h2.STORE.get(j["patient_id"])["_audit_log"]
    assert len(audit) == 1 and audit[0]["exchange_id"] == "ech-100" and audit[0]["action"] == "create"
    assert audit[0]["patient_ref"] == j["patient_id"]


def test_rejeu_sans_doublon(api):
    b = bundle_h1()
    importer(api, b)
    r = importer(api, b)
    j = r.json()
    assert r.status_code == 200 and j["patient_cree"] is False and j["lignes_par_type"] == {}
    assert j["deja_presents"] == {"Patient": 1, "Consent": 1, "Encounter": 1, "Condition": 1, "Observation": 2}
    assert nb_patients() == 61
    doc = api_h2.STORE.get("P2-0061")
    assert len(doc["visits"]) == 1 and len(doc["visits"][0]["observations"]) == 2


def test_rejeu_avec_le_meme_identifiant_d_echange(api):
    b = bundle_h1()
    importer(api, b, **{"X-Exchange-Id": "ech-1"})
    r = importer(api, b, **{"X-Exchange-Id": "ech-1"})
    assert r.status_code == 200 and r.json()["deja_traite"] is True
    assert len(api_h2.STORE.get("P2-0061")["_audit_log"]) == 1      # pas de 2e écriture


def test_identifiant_d_echange_pris_dans_le_bundle(api):
    importer(api, bundle_h1(echange_id="ech-bundle"))
    r = importer(api, bundle_h1(echange_id="ech-bundle"))
    assert r.json()["deja_traite"] is True and r.json()["echange_id"] == "ech-bundle"


def test_complete_un_patient_existant_par_cin(api):
    avant = api_h2.STORE.get("P2-0052")
    b = bundle_h1(ipp="P1-0152", cin="K445120", nom="Autre", prenom="Nom", visite="H1-V-0152-01")
    r = importer(api, b)
    j = r.json()
    assert r.status_code == 200 and j["patient_id"] == "P2-0052" and j["patient_cree"] is False
    assert j["lignes_par_type"]["Encounter"] == 1 and j["lignes_par_type"]["Observation"] == 2
    apres = api_h2.STORE.get("P2-0052")
    assert len(apres["visits"]) == len(avant["visits"]) + 1
    for v_avant, v_apres in zip(avant["visits"], apres["visits"]):
        assert v_avant["visit_id"] == v_apres["visit_id"] and "_origin" not in v_apres
        assert len(v_avant["observations"]) == len(v_apres["observations"])
    assert apres["visits"][-1]["_origin"] == "H1"
    assert {"system": SYSTEM_IPP_H1, "value": "P1-0152"} in apres["_external_ids"]
    assert apres["last_name"] == avant["last_name"]                           # pas d'écrasement
    assert any(a["code"] == "conflit" and a["champ"] == "last_name" for a in j["alertes"])


def test_conflit_groupe_sanguin_signale_sans_ecraser(api):
    assert api_h2.STORE.get("P2-0055")["blood_type"] == "A+"
    j = importer(api, bundle_h1(ipp="P1-0155", cin="G554321", groupe="A-")).json()
    assert any(a["champ"] == "blood_type" and a["valeur_h2"] == "A+" and a["valeur_recue"] == "A-"
               for a in j["alertes"])
    assert api_h2.STORE.get("P2-0055")["blood_type"] == "A+"


def test_homonyme_avec_cin_different_n_est_pas_fusionne(api):
    h = api_h2.STORE.get("P2-0058")
    b = bundle_h1(ipp="P1-0158", cin="ZZ999999", nom=h["last_name"], prenom=h["first_name"],
                  naissance=h["birth_date"])
    j = importer(api, b).json()
    assert j["patient_cree"] is True and j["patient_id"] != "P2-0058"
    assert api_h2.STORE.get("P2-0058")["national_id"] == "J445566"


def test_identite_ambigue_409(api):
    importer(api, bundle_h1(ipp="P1-0900", cin="CIN900900"))                 # crée P2-0061
    r = importer(api, bundle_h1(ipp="P1-0900", cin="K445120"))              # IPP → P2-0061, CIN → P2-0052
    assert r.status_code == 409 and r.json()["issue"][0]["code"] == "multiple-matches"
    assert nb_patients() == 61


def test_patient_sans_cin_ni_ipp_422(api):
    b = bundle_h1(cin=None)
    b["entry"][0]["resource"]["identifier"] = []
    r = importer(api, b)
    assert r.status_code == 422 and "Identité insuffisante" in r.json()["issue"][0]["diagnostics"]


def test_patient_sans_cin_mais_avec_ipp_cree_avec_alerte(api):
    r = importer(api, bundle_h1(ipp="P1-0777", cin=None))
    assert r.status_code == 201 and any(a["code"] == "identite-sans-cin" for a in r.json()["alertes"])


def test_identifiant_h2_inconnu_422(api):
    b = bundle_h1()
    b["entry"][0]["resource"]["identifier"].append({"system": "urn:clinique-al-bacar:patient", "value": "P2-4242"})
    r = importer(api, b)
    assert r.status_code == 422 and "inconnu" in r.json()["issue"][0]["diagnostics"]


def test_identifiant_h2_connu_retrouve_le_patient(api):
    b = bundle_h1(ipp="P1-0152", cin=None)
    b["entry"][0]["resource"]["identifier"].append({"system": "urn:clinique-al-bacar:patient", "value": "P2-0052"})
    r = importer(api, b)
    assert r.status_code == 200 and r.json()["patient_id"] == "P2-0052"


def test_import_alimente_les_champs_vides(api):
    doc = api_h2.STORE.get("P2-0052")
    doc["phone"] = None
    api_h2.STORE.remplacer(doc)
    importer(api, bundle_h1(ipp="P1-0152", cin="K445120"))
    assert api_h2.STORE.get("P2-0052")["phone"] == "+212611223344"


# ── consentement à la réception ──────────────────────────────────────────────
@pytest.mark.parametrize("statut", ["not-done", "inactive", "draft"])
def test_import_consentement_non_actif_403(api, statut):
    r = importer(api, bundle_h1(consent=statut))
    assert r.status_code == 403 and "consentement" in r.json()["issue"][0]["diagnostics"]
    assert nb_patients() == 60


def test_import_sans_consent_403(api):
    r = importer(api, bundle_h1(consent=None))
    assert r.status_code == 403 and nb_patients() == 60


def test_import_consentement_local_refuse_403(api):
    doc = api_h2.STORE.get("P2-0054")
    doc["consent"]["status"] = "refused"
    api_h2.STORE.remplacer(doc)
    r = importer(api, bundle_h1(ipp="P1-0154", cin="F112233"))
    assert r.status_code == 403 and "local" in r.json()["issue"][0]["diagnostics"]
    assert len(api_h2.STORE.get("P2-0054")["visits"]) == len(DOCS[3]["visits"])


# ── validation du Bundle ─────────────────────────────────────────────────────
def test_json_illisible_400(api):
    r = api.post("/api/retours", content=b"{oops", headers={"Content-Type": "application/fhir+json"})
    assert r.status_code == 400 and r.json()["resourceType"] == "OperationOutcome"


@pytest.mark.parametrize("corps", [{"resourceType": "Patient"}, [], {"resourceType": "Bundle", "type": "searchset",
                                   "entry": [{}]}, {"resourceType": "Bundle", "type": "transaction", "entry": []}])
def test_pas_un_bundle_exploitable_400(api, corps):
    assert importer(api, corps).status_code == 400


def test_deux_patients_422(api):
    b = bundle_h1()
    b["entry"].append(copy.deepcopy(b["entry"][0]))
    assert importer(api, b).status_code == 422


def test_unite_absente_422(api):
    b = bundle_h1()
    vq = next(e["resource"]["valueQuantity"] for e in b["entry"] if e["resource"]["id"].endswith("-2"))
    vq.pop("unit"), vq.pop("code")
    r = importer(api, b)
    assert r.status_code == 422 and "unité absente" in r.json()["issue"][0]["diagnostics"]


def test_valeur_impossible_422(api):
    b = bundle_h1(tension=(500, 80))
    r = importer(api, b)
    assert r.status_code == 422 and "hors plage" in r.json()["issue"][0]["diagnostics"] and nb_patients() == 60


def test_sortie_avant_admission_422(api):
    b = bundle_h1()
    enc = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Encounter")
    enc["actualPeriod"]["end"] = "2026-11-04T09:00:00+01:00"
    assert importer(api, b).status_code == 422


def test_champ_obligatoire_du_patient_422(api):
    b = bundle_h1()
    del b["entry"][0]["resource"]["birthDate"]
    r = importer(api, b)
    assert r.status_code == 422 and "birthDate" in r.json()["issue"][0]["diagnostics"]


def test_instruction_delete_refusee_422(api):
    b = bundle_h1()
    b["entry"][-1]["request"] = {"method": "DELETE", "url": "Observation/x"}
    r = importer(api, b)
    assert r.status_code == 422 and r.json()["issue"][0]["code"] == "not-supported"


def test_url_d_instruction_incoherente_422(api):
    b = bundle_h1()
    b["entry"][-1]["request"] = {"method": "PUT", "url": "Patient/x"}
    assert importer(api, b).status_code == 422


def test_transaction_sans_instruction_acceptee_avec_alerte(api):
    b = bundle_h1()
    for e in b["entry"]:
        e.pop("request")
    r = importer(api, b)
    assert r.status_code == 201 and any(a["code"] == "instruction-absente" for a in r.json()["alertes"])


def test_bundle_collection_accepte(api):
    b = bundle_h1()
    b["type"] = "collection"
    for e in b["entry"]:
        e.pop("request")
    assert importer(api, b).status_code == 201


def test_audit_de_l_autre_hopital_ignore(api):
    b = bundle_h1()
    b["entry"].append({"resource": {"resourceType": "AuditEvent", "id": "a1", "recorded": "2026-11-05T09:00:00Z",
                                    "code": {"text": "lecture"}}, "request": {"method": "PUT", "url": "AuditEvent/a1"}})
    j = importer(api, b).json()
    assert j["ignores"] == [{"type": "AuditEvent", "nombre": 1,
                             "raison": "le journal d'accès est propre à chaque hôpital"}]
    assert len(api_h2.STORE.get(j["patient_id"])["_audit_log"]) == 1       # seulement NOTRE trace


# ═════════════════════════════════════════════════════════════════════════════
# ANTI-BOUCLE
# ═════════════════════════════════════════════════════════════════════════════
def test_anti_boucle_les_donnees_de_h1_ne_lui_sont_pas_renvoyees(api):
    importer(api, bundle_h1())
    b = api.get("/api/patients/P2-0061/bundle").json()
    # identité + consentement (+ la clinique que le consentement référence) ; rien de ce qui vient de H1
    assert sorted(types(b)) == ["Consent", "Organization", "Patient"] and not _orphelines(b)
    ids = {(i["system"], i["value"]) for i in b["entry"][0]["resource"]["identifier"]}
    assert (SYSTEM_IPP_H1, "P1-0106") in ids and ("urn:ma:cin", "CD654321") in ids
    Bundle.model_validate(b)


def test_anti_boucle_conserve_les_donnees_natives(api):
    avant = api.get("/api/patients/P2-0052/bundle").json()
    importer(api, bundle_h1(ipp="P1-0152", cin="K445120", visite="H1-V-0152-01"))
    apres = api.get("/api/patients/P2-0052/bundle").json()
    ids = lambda b: sorted(e["resource"]["id"] for e in b["entry"] if e["resource"]["resourceType"] == "Encounter")
    assert ids(avant) == ids(apres) and "H1-V-0152-01" not in ids(apres)
    assert sorted(types(avant)) == sorted(types(apres))


def test_anti_boucle_aller_retour_complet_sans_amplification(api):
    importer(api, bundle_h1())
    for _ in range(3):                                                     # H2 exporte, H1 "renvoie" ce qu'il reçoit
        b = api.get("/api/patients/P2-0061/bundle").json()
        r = importer(api, b)
        assert r.status_code == 200 and r.json()["lignes_par_type"] == {} and r.json()["alertes"] == []
    assert len(api_h2.STORE.get("P2-0061")["visits"]) == 1 and nb_patients() == 61


# ═════════════════════════════════════════════════════════════════════════════
# Pannes : 503
# ═════════════════════════════════════════════════════════════════════════════
class StoreEnPanne(stores.StoreMemoire):
    panne = False

    def _verifier(self):
        if self.panne:
            raise stores.StoreIndisponible("panne simulée")

    def ping(self):
        self._verifier()
        return True

    def get(self, pid):
        self._verifier()
        return super().get(pid)

    def find_all_by_identifier(self, system, value):
        self._verifier()
        return super().find_all_by_identifier(system, value)

    def creer(self, doc, finaliser=None):
        self._verifier()
        return super().creer(doc, finaliser)

    def remplacer(self, doc):
        self._verifier()
        super().remplacer(doc)


def test_base_indisponible_503_puis_rejeu_sans_doublon(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON)
    store = StoreEnPanne(copy.deepcopy(DOCS))
    monkeypatch.setattr(api_h2, "STORE", store)
    c = TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})
    store.panne = True
    assert c.get("/health").status_code == 503 and c.get("/health").json()["base"] == "indisponible"
    r = c.post("/api/retours", json=bundle_h1(), headers={"X-Exchange-Id": "ech-9"})
    assert r.status_code == 503 and r.headers["retry-after"] == "30" and r.json()["issue"][0]["code"] == "transient"
    assert c.get("/api/patients/P2-0051/bundle").status_code == 503
    store.panne = False
    assert len(store.docs) == 60                                          # rien d'écrit pendant la panne
    r = c.post("/api/retours", json=bundle_h1(), headers={"X-Exchange-Id": "ech-9"})
    assert r.status_code == 201 and len(store.docs) == 61
    assert c.post("/api/retours", json=bundle_h1(), headers={"X-Exchange-Id": "ech-9"}).json()["deja_traite"] is True


def test_mongo_injoignable_donne_503(monkeypatch):
    """Vrai StoreMongo (mongomock) dont la base tombe : PyMongoError → StoreIndisponible → 503."""
    import mongomock
    from pymongo.errors import ServerSelectionTimeoutError
    monkeypatch.setenv("H2_TOKEN", JETON)
    store = stores.StoreMongo(client=mongomock.MongoClient(), nom_base="hopital2")
    monkeypatch.setattr(api_h2, "STORE", store)
    c = TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON}"})

    def panne(*a, **k):
        raise ServerSelectionTimeoutError("mongod absent")
    monkeypatch.setattr(store.col, "find_one", panne)
    assert c.get("/api/patients/P2-0051/bundle").status_code == 503


# ═════════════════════════════════════════════════════════════════════════════
# Routes FHIR standard
# ═════════════════════════════════════════════════════════════════════════════
def test_post_patient_puis_lecture_et_recherche(api):
    p = {"resourceType": "Patient", "identifier": [{"system": "urn:ma:cin", "value": "NEW123"}],
         "name": [{"family": "Idrissi", "given": ["Nadia"]}], "gender": "female", "birthDate": "1990-01-01"}
    r = api.post("/Patient", json=p)
    assert r.status_code == 201 and r.headers["location"] == "/Patient/P2-0061"
    assert api.get("/Patient/P2-0061").json()["name"][0]["family"] == "Idrissi"
    assert api.get("/Patient?identifier=urn:ma:cin|NEW123").json()["total"] == 1
    assert api.get("/Patient?identifier=urn:ma:cin|RIEN").json()["total"] == 0
    assert api.get("/Patient/P2-9999").status_code == 404
    # sans Consent : enregistré mais non exportable
    assert api.get("/api/patients/P2-0061/bundle").status_code == 403


def test_post_patient_doublon_409_et_invalide(api):
    p = {"resourceType": "Patient", "identifier": [{"system": "urn:ma:cin", "value": "AB123456"}],
         "name": [{"family": "X", "given": ["Y"]}], "gender": "male", "birthDate": "1990-01-01"}
    assert api.post("/Patient", json=p).status_code == 409
    assert api.post("/Patient", json={"resourceType": "Observation"}).status_code == 400
    del p["birthDate"]
    p["identifier"][0]["value"] = "AUTRE"
    assert api.post("/Patient", json=p).status_code == 422


def test_alias_bundle_et_everything(api):
    r = api.post("/Bundle", json=bundle_h1())
    assert r.status_code == 201 and r.json()["patient_id"] == "P2-0061"
    assert api.get("/Patient/P2-0052/$everything").json()["type"] == "transaction"


def test_recherche_sans_parametre_liste_les_patients(api):
    j = api.get("/Patient").json()
    assert j["type"] == "searchset" and j["total"] == 60


# ═════════════════════════════════════════════════════════════════════════════
# Identifiant patient : jamais « UNKNOWN »
# ═════════════════════════════════════════════════════════════════════════════
def test_jamais_d_identifiant_unknown(api):
    # patient venant de H1, sans identifiant H2 : l'API attribue P2-xxxx AVANT d'écrire
    pid = importer(api, bundle_h1(cin=None, ipp="P1-0777")).json()["patient_id"]
    assert pid == "P2-0061" and api_h2.STORE.get(pid)["patient_id"] == pid
    assert "UNKNOWN" not in json.dumps(api.get(f"/api/patients/{pid}/bundle").json())
    assert all(d.get("patient_id") for d in api_h2.STORE.all(1000))
    # 2 patients de H1 successifs : identifiants distincts
    autre = importer(api, bundle_h1(cin="ZZ1", ipp="P1-0778")).json()["patient_id"]
    assert autre != pid
    for d in DOCS:
        if d["consent"]["status"] == "active":
            assert "UNKNOWN" not in json.dumps(echange.construire_bundle(copy.deepcopy(d), referentiels=REFS))


def test_export_refuse_un_dossier_sans_identifiant():
    doc = copy.deepcopy(DOCS[0])
    doc["patient_id"] = None
    with pytest.raises(echange.ErreurEchange) as exc:
        echange.construire_bundle(doc)
    assert exc.value.code == 500 and "patient_id" in exc.value.message


def test_adaptateur_refuse_sans_patient_id_et_ignore_unknown_entrant():
    doc = copy.deepcopy(DOCS[0])
    doc.pop("patient_id")
    with pytest.raises(h2_vers_fhir.MissingPatientIdError):
        h2_vers_fhir.convert(doc)
    # bundle d'un ancien adaptateur portant l'identifiant « UNKNOWN » : traité comme absent
    b = echange.construire_bundle(copy.deepcopy(DOCS[0]))
    for e in b["entry"]:
        r = e["resource"]
        if r["resourceType"] == "Patient":
            for i in r["identifier"]:
                if i["system"] == "urn:clinique-al-bacar:patient":
                    i["value"] = "UNKNOWN"
    assert fhir_vers_h2.bundle_to_h2_document(b, strict=False)["patient_id"] is None


def test_reference_avec_underscore_resolue():
    assert h2_vers_fhir._ref("Practitioner", "Practitioner/PRAC-FASSI_FIHRI") == {
        "reference": "Practitioner/PRAC-FASSI-FIHRI"}


# ═════════════════════════════════════════════════════════════════════════════
# DONNÉES v3 : annuaire en collections séparées, cas D2 / D4 / D13
# ═════════════════════════════════════════════════════════════════════════════
def test_d2_consentement_refuse_des_donnees_bloque_l_export(api):
    r = api.get("/api/patients/P2-0054/bundle")                           # refusé dans la base elle-même
    assert r.status_code == 403 and r.json()["resourceType"] == "OperationOutcome"


def test_d13_date_de_naissance_jj_mm_aaaa_convertie(api):
    b = api.get("/api/patients/P2-0059/bundle").json()
    assert b["entry"][0]["resource"]["birthDate"] == "1990-05-13"


def test_d4_sans_cin_s_exporte_sans_identifiant_national(api):
    b = api.get("/api/patients/P2-0056/bundle").json()
    systemes = {i["system"] for i in b["entry"][0]["resource"]["identifier"]}
    assert "urn:ma:cin" not in systemes and "urn:clinique-al-bacar:patient" in systemes


def test_annuaire_joint_depuis_les_collections_a_part(api):
    b = api.get("/api/patients/P2-0052/bundle?inclure_catalogue=true").json()
    pracs = [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Practitioner"]
    assert [p["id"] for p in pracs] == ["PRAC-BENCHEKROUN"]               # le médecin de CE patient seulement
    assert not _orphelines(b)
    Bundle.model_validate(b)


def test_interpretation_et_plage_de_reference_exportees(api):
    b = api.get("/api/patients/P2-0052/bundle").json()
    pio = [e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Observation"
           and e["resource"]["code"]["coding"][0]["code"] == "79892-6"]
    assert pio and pio[0]["interpretation"][0]["coding"][0]["code"] == "H"      # 27 mmHg > 21
    assert pio[0]["valueQuantity"]["code"] == "mm[Hg]" and pio[0]["referenceRange"][0]["high"]["value"] == 21


def test_reference_practitioner_avec_underscore_resolue_dans_le_bundle(api):
    # PRAC-FASSI_FIHRI (base) → id FHIR PRAC-FASSI-FIHRI, et le rôle pointe bien dessus
    doc = next(d for d in DOCS if any(v["physician_ref"] == "PRAC-FASSI_FIHRI" for v in d["visits"])
               and d["consent"]["status"] == "active")
    b = api.get(f"/api/patients/{doc['patient_id']}/bundle?inclure_catalogue=true").json()
    ids = {f"{e['resource']['resourceType']}/{e['resource']['id']}" for e in b["entry"]}
    assert "Practitioner/PRAC-FASSI-FIHRI" in ids and not _orphelines(b)
