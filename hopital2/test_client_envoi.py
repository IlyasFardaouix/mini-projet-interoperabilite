"""Tests du client d'envoi (file d'attente + reprise) contre une fausse API H1."""
import copy
import json

from bson import json_util
import os

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import api_h2
import client_envoi
import stores
from client_envoi import Outbox, envoyer_dossier, reprendre

DOCS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "patients_h2.json"), encoding="utf-8").read())
REFS = json_util.loads(open(os.path.join(os.path.dirname(__file__), "data", "referentiels_h2.json"), encoding="utf-8").read())
JETON_H2 = "jeton-h2"


class FausseApiH1:
    """Imite les routes de H1 : POST /api/retours/simulation et POST /api/retours."""

    def __init__(self):
        self.mode = "ok"            # ok | 422 | 409 | 403 | 503
        self.recus = []             # (chemin, exchange_id, bundle)
        app = FastAPI()

        async def traiter(request: Request, chemin: str):
            corps = await request.json()
            self.recus.append((chemin, request.headers.get("x-exchange-id"), corps))
            codes = {"422": 422, "409": 409, "403": 403, "503": 503}
            if self.mode in codes:
                return JSONResponse({"resourceType": "OperationOutcome", "issue": [
                    {"severity": "error", "code": "processing", "diagnostics": f"H1 simulé : {self.mode}"}]},
                    status_code=codes[self.mode])
            corps_rep = {"simulation": chemin.endswith("simulation")}
            if getattr(self, "imagerie", None) is not None and not chemin.endswith("simulation"):
                corps_rep["imagerie"] = self.imagerie
            return JSONResponse(corps_rep, status_code=200)

        @app.post("/api/retours/simulation")
        async def sim(request: Request):
            return await traiter(request, "/api/retours/simulation")

        @app.post("/api/retours")
        async def vrai(request: Request):
            return await traiter(request, "/api/retours")

        self.client = TestClient(app, headers={"Authorization": "Bearer jeton-h1"})

    def definitifs(self):
        return [r for r in self.recus if r[0] == "/api/retours"]


class H1Injoignable:
    def post(self, *a, **k):
        raise httpx.ConnectError("connexion refusée")


@pytest.fixture
def h2(monkeypatch):
    monkeypatch.setenv("H2_TOKEN", JETON_H2)
    monkeypatch.setattr(api_h2, "STORE", stores.StoreMemoire(copy.deepcopy(DOCS), REFS))
    return TestClient(api_h2.app, headers={"Authorization": f"Bearer {JETON_H2}"})


def test_envoi_nominal(h2):
    h1, outbox = FausseApiH1(), Outbox()
    r = envoyer_dossier("P2-0052", h2, h1.client, outbox, maintenant=1000.0)
    assert r["statut"] == "envoye" and r["http"] == 200 and r["tentatives"] == 1
    assert [c for c, _, _ in h1.recus] == ["/api/retours/simulation", "/api/retours"]     # simulation d'abord
    _, echange_id, bundle = h1.definitifs()[0]
    assert echange_id == r["echange_id"] == bundle["identifier"]["value"]
    assert bundle["type"] == "transaction"
    assert [e["resource"]["resourceType"] for e in bundle["entry"]].count("Patient") == 1
    assert outbox.lister()[0]["statut"] == "envoye"


def test_le_bilan_des_images_de_h1_est_repris(h2):
    h1 = FausseApiH1()
    h1.imagerie = [{"study_uid": "2.25.1", "statut": "RECUPEREE", "instances": 3}]
    r = envoyer_dossier("P2-0052", h2, h1.client, Outbox(), maintenant=1000.0)
    assert r["statut"] == "envoye" and r["imagerie"] == [{"statut": "RECUPEREE", "instances": 3}]
    sans = envoyer_dossier("P2-0052", h2, FausseApiH1().client, Outbox(), maintenant=1000.0)
    assert "imagerie" not in sans


def test_h1_injoignable_puis_reprise_sans_doublon(h2):
    outbox = Outbox()
    r = envoyer_dossier("P2-0052", h2, H1Injoignable(), outbox, maintenant=1000.0)
    assert r["statut"] == "en_attente" and r["tentatives"] == 1 and "nouvelle tentative dans 60 s" in r["detail"]
    h1 = FausseApiH1()
    assert reprendre(outbox, h1.client, maintenant=1030.0) == []             # trop tôt : le délai n'est pas écoulé
    assert h1.recus == []
    res = reprendre(outbox, h1.client, maintenant=1061.0)
    assert len(res) == 1 and res[0]["statut"] == "envoye" and res[0]["tentatives"] == 2
    assert len(h1.definitifs()) == 1 and h1.definitifs()[0][1] == r["echange_id"]     # même identifiant d'échange
    assert reprendre(outbox, h1.client, maintenant=99999.0) == []             # plus rien à faire


def test_h1_en_503_reste_en_attente_avec_delai_croissant(h2):
    h1, outbox = FausseApiH1(), Outbox()
    h1.mode = "503"
    r = envoyer_dossier("P2-0052", h2, h1.client, outbox, maintenant=0.0)    # la simulation en 503 n'arrête pas l'envoi
    assert r["statut"] == "en_attente" and r["http"] == 503
    delais, t = [], 0.0
    for _ in range(4):
        ligne = outbox.get(r["envoi_id"])
        delais.append(ligne["prochaine"] - t)
        t = ligne["prochaine"]
        r = reprendre(outbox, h1.client, maintenant=t)[0]
    assert delais == [60, 300, 1800, 7200]


def test_abandon_apres_le_maximum_de_tentatives(h2):
    h1, outbox = FausseApiH1(), Outbox()
    h1.mode = "503"
    r = envoyer_dossier("P2-0052", h2, h1.client, outbox, simuler_avant=False, maintenant=0.0)
    t = 0.0
    while r["statut"] == "en_attente":
        t = outbox.get(r["envoi_id"])["prochaine"]
        r = reprendre(outbox, h1.client, maintenant=t)[0]
    assert r["statut"] == "echec" and r["tentatives"] == client_envoi.MAX_TENTATIVES and "Abandon" in r["detail"]
    assert reprendre(outbox, h1.client, maintenant=t + 10**7) == []


def test_refus_a_la_simulation_rien_n_est_mis_en_file(h2):
    h1, outbox = FausseApiH1(), Outbox()
    h1.mode = "422"
    r = envoyer_dossier("P2-0052", h2, h1.client, outbox, maintenant=0.0)
    assert r["statut"] == "refuse_simulation" and r["http"] == 422 and "H1 simulé" in r["detail"]
    assert outbox.lister() == [] and h1.definitifs() == []


@pytest.mark.parametrize("code", ["409", "422", "403"])
def test_erreur_definitive_en_echec_sans_reprise(h2, code):
    h1, outbox = FausseApiH1(), Outbox()
    h1.mode = code
    r = envoyer_dossier("P2-0052", h2, h1.client, outbox, simuler_avant=False, maintenant=0.0)
    assert r["statut"] == "echec" and r["http"] == int(code) and r["tentatives"] == 1
    assert reprendre(outbox, h1.client, maintenant=10**6) == [] and len(h1.definitifs()) == 1


def test_consentement_refuse_bloque_l_envoi(h2):
    doc = api_h2.STORE.get("P2-0052")
    doc["consent"]["status"] = "refused"
    api_h2.STORE.remplacer(doc)
    h1, outbox = FausseApiH1(), Outbox()
    r = envoyer_dossier("P2-0052", h2, h1.client, outbox, maintenant=0.0)
    assert r["statut"] == "bloque" and r["http"] == 403
    assert h1.recus == [] and outbox.lister() == []


def test_patient_inconnu_export_impossible(h2):
    r = envoyer_dossier("P2-9999", h2, FausseApiH1().client, Outbox(), maintenant=0.0)
    assert r["statut"] == "export_impossible" and r["http"] == 404


def test_file_d_attente_survit_a_un_redemarrage(h2, tmp_path):
    chemin = str(tmp_path / "outbox.sqlite")
    r = envoyer_dossier("P2-0052", h2, H1Injoignable(), Outbox(chemin), maintenant=0.0)
    assert r["statut"] == "en_attente"
    h1 = FausseApiH1()
    res = reprendre(Outbox(chemin), h1.client, maintenant=100.0)              # nouvelle instance = redémarrage
    assert res[0]["statut"] == "envoye" and len(h1.definitifs()) == 1


def test_meme_echange_ne_peut_etre_mis_deux_fois_en_file():
    outbox = Outbox()
    outbox.ajouter("P2-0052", "ech-1", "{}", 0.0)
    with pytest.raises(Exception):
        outbox.ajouter("P2-0052", "ech-1", "{}", 0.0)
