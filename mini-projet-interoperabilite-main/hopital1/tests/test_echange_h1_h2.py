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

    def recevoir(conn, bundle, patient, echange_id=None):
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