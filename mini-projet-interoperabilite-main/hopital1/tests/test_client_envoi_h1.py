"""Client d'envoi H1 -> H2 (file d'attente + reprise), contre une fausse API H2.

L'export passe par la VRAIE API H1 (app.py) ; seul Oracle est remplace par les dossiers de test.
"""
from contextlib import contextmanager

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import app as api
import client_envoi_h1 as client_envoi
import h1_to_fhir as ALL
import oracle_repo as repo
from client_envoi_h1 import Outbox, envoyer_dossier, reprendre
from tests.donnees import dossier

JETON = "jeton-test-h1-assez-long-pour-etre-valide"


class FausseApiH2:
    """Imite les routes de H2 : POST /api/retours/simulation et POST /api/retours."""

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
                    {"severity": "error", "code": "processing", "diagnostics": f"H2 simule : {self.mode}"}]},
                    status_code=codes[self.mode])
            return JSONResponse({"simulation": chemin.endswith("simulation")}, status_code=200)

        @app.post("/api/retours/simulation")
        async def sim(request: Request):
            return await traiter(request, "/api/retours/simulation")

        @app.post("/api/retours")
        async def vrai(request: Request):
            return await traiter(request, "/api/retours")

        self.client = TestClient(app, headers={"Authorization": "Bearer jeton-h2"})

    def definitifs(self):
        return [r for r in self.recus if r[0] == "/api/retours"]


class H2Injoignable:
    def post(self, *a, **k):
        raise httpx.ConnectError("connexion refusee")


@pytest.fixture
def h1(monkeypatch):
    """Vraie API H1, Oracle remplace par les dossiers de test (S1 nominal, D1 consentement refuse)."""
    base = {"P1-0106": dossier("S1"), "P1-0108": dossier("D1")}

    @contextmanager
    def faux_oracle():
        yield object()

    def exporter(conn, cin=None, ipp=None, adressage=True, destinataire="H2"):
        if ipp not in base:
            raise LookupError(ipp)
        bundle, alertes, rejets = ALL.dossier_vers_bundle(base[ipp], adressage=adressage, destinataire=destinataire)
        return bundle, alertes, rejets

    def lire_consentements(conn, ipp, **_):
        if ipp not in base:
            raise LookupError(ipp)
        return [base[ipp]["consentement"]]

    monkeypatch.setenv("H1_API_TOKEN", JETON)
    monkeypatch.setattr(repo, "connexion", faux_oracle)
    monkeypatch.setattr(repo, "exporter", exporter)
    monkeypatch.setattr(repo, "lire_consentements", lire_consentements)
    client = TestClient(api.app, headers={"Authorization": f"Bearer {JETON}"})
    client.base = base
    return client


def test_envoi_nominal(h1):
    h2, outbox = FausseApiH2(), Outbox()
    r = envoyer_dossier("P1-0106", h1, h2.client, outbox, maintenant=1000.0)
    assert r["statut"] == "envoye" and r["http"] == 200 and r["tentatives"] == 1
    assert [c for c, _, _ in h2.recus] == ["/api/retours/simulation", "/api/retours"]     # simulation d'abord
    _, echange_id, bundle = h2.definitifs()[0]
    assert echange_id == r["echange_id"] == bundle["identifier"]["value"]
    assert bundle["type"] == "transaction"
    assert [e["resource"]["resourceType"] for e in bundle["entry"]].count("Patient") == 1
    assert outbox.lister()[0]["statut"] == "envoye"


def test_h2_injoignable_puis_reprise_sans_doublon(h1):
    outbox = Outbox()
    r = envoyer_dossier("P1-0106", h1, H2Injoignable(), outbox, maintenant=1000.0)
    assert r["statut"] == "en_attente" and r["tentatives"] == 1 and "nouvelle tentative dans 60 s" in r["detail"]
    h2 = FausseApiH2()
    assert reprendre(outbox, h2.client, maintenant=1030.0) == []             # trop tot : le delai n'est pas ecoule
    assert h2.recus == []
    res = reprendre(outbox, h2.client, maintenant=1061.0)
    assert len(res) == 1 and res[0]["statut"] == "envoye" and res[0]["tentatives"] == 2
    assert len(h2.definitifs()) == 1 and h2.definitifs()[0][1] == r["echange_id"]     # meme identifiant d'echange
    assert reprendre(outbox, h2.client, maintenant=99999.0) == []             # plus rien a faire


def test_h2_en_503_reste_en_attente_avec_delai_croissant(h1):
    h2, outbox = FausseApiH2(), Outbox()
    h2.mode = "503"
    r = envoyer_dossier("P1-0106", h1, h2.client, outbox, maintenant=0.0)    # la simulation en 503 n'arrete pas l'envoi
    assert r["statut"] == "en_attente" and r["http"] == 503
    delais, t = [], 0.0
    for _ in range(4):
        ligne = outbox.get(r["envoi_id"])
        delais.append(ligne["prochaine"] - t)
        t = ligne["prochaine"]
        r = reprendre(outbox, h2.client, maintenant=t)[0]
    assert delais == [60, 300, 1800, 7200]


def test_abandon_apres_le_maximum_de_tentatives(h1):
    h2, outbox = FausseApiH2(), Outbox()
    h2.mode = "503"
    r = envoyer_dossier("P1-0106", h1, h2.client, outbox, simuler_avant=False, maintenant=0.0)
    t = 0.0
    while r["statut"] == "en_attente":
        t = outbox.get(r["envoi_id"])["prochaine"]
        r = reprendre(outbox, h2.client, maintenant=t)[0]
    assert r["statut"] == "echec" and r["tentatives"] == client_envoi.MAX_TENTATIVES and "Abandon" in r["detail"]
    assert reprendre(outbox, h2.client, maintenant=t + 10**7) == []


def test_refus_a_la_simulation_rien_n_est_mis_en_file(h1):
    h2, outbox = FausseApiH2(), Outbox()
    h2.mode = "422"
    r = envoyer_dossier("P1-0106", h1, h2.client, outbox, maintenant=0.0)
    assert r["statut"] == "refuse_simulation" and r["http"] == 422 and "H2 simule" in r["detail"]
    assert outbox.lister() == [] and h2.definitifs() == []


@pytest.mark.parametrize("code", ["409", "422", "403"])
def test_erreur_definitive_en_echec_sans_reprise(h1, code):
    h2, outbox = FausseApiH2(), Outbox()
    h2.mode = code
    r = envoyer_dossier("P1-0106", h1, h2.client, outbox, simuler_avant=False, maintenant=0.0)
    assert r["statut"] == "echec" and r["http"] == int(code) and r["tentatives"] == 1
    assert reprendre(outbox, h2.client, maintenant=10**6) == [] and len(h2.definitifs()) == 1


def test_consentement_refuse_bloque_l_envoi(h1):
    h2, outbox = FausseApiH2(), Outbox()
    r = envoyer_dossier("P1-0108", h1, h2.client, outbox, maintenant=0.0)
    assert r["statut"] == "bloque" and r["http"] == 403
    assert h2.recus == [] and outbox.lister() == []


def test_patient_inconnu_export_impossible(h1):
    r = envoyer_dossier("P1-9999", h1, FausseApiH2().client, Outbox(), maintenant=0.0)
    assert r["statut"] == "export_impossible" and r["http"] == 404


def test_file_d_attente_survit_a_un_redemarrage(h1, tmp_path):
    chemin = str(tmp_path / "outbox.sqlite")
    r = envoyer_dossier("P1-0106", h1, H2Injoignable(), Outbox(chemin, chiffreur=None), maintenant=0.0)
    assert r["statut"] == "en_attente"
    h2 = FausseApiH2()
    res = reprendre(Outbox(chemin, chiffreur=None), h2.client, maintenant=100.0)   # nouvelle instance = redemarrage
    assert res[0]["statut"] == "envoye" and len(h2.definitifs()) == 1


def test_bundle_chiffre_dans_la_file(h1, tmp_path):
    from securite.chiffrement import Chiffreur
    chemin = str(tmp_path / "outbox.sqlite")
    ch = Chiffreur.depuis_texte("v1:" + "A" * 43)
    envoyer_dossier("P1-0106", h1, H2Injoignable(), Outbox(chemin, chiffreur=ch), maintenant=0.0)
    brut = Outbox(chemin, chiffreur=None).db.execute("SELECT bundle FROM envois").fetchone()[0]
    assert "Alaoui" not in brut and not brut.lstrip().startswith("{")           # illisible sur le disque
    h2 = FausseApiH2()
    assert reprendre(Outbox(chemin, chiffreur=ch), h2.client, maintenant=100.0)[0]["statut"] == "envoye"
    assert h2.definitifs()[0][2]["resourceType"] == "Bundle"


def test_retrait_du_consentement_annule_la_reprise(h1):
    outbox = Outbox()
    r = envoyer_dossier("P1-0106", h1, H2Injoignable(), outbox, maintenant=0.0)
    assert r["statut"] == "en_attente"
    h1.base["P1-0106"]["consentement"].update(statut="RETIRE")              # le patient retire son consentement
    h2 = FausseApiH2()
    res = reprendre(outbox, h2.client, h1=h1, maintenant=100.0)
    assert res[0]["statut"] == "annule" and "loi 09-08" in res[0]["detail"]
    assert h2.recus == []                                                   # rien n'est parti
    assert reprendre(outbox, h2.client, h1=h1, maintenant=10**7) == []


def test_consentement_non_verifiable_rien_ne_part(h1):
    outbox = Outbox()
    envoyer_dossier("P1-0106", h1, H2Injoignable(), outbox, maintenant=0.0)

    class H1Muet:
        def get(self, *a, **k):
            raise httpx.ConnectError("injoignable")

    h2 = FausseApiH2()
    res = reprendre(outbox, h2.client, h1=H1Muet(), maintenant=100.0)
    assert res[0]["statut"] == "en_attente" and "non vérifiable" in res[0]["detail"]
    assert h2.recus == []


def test_h1_injoignable_a_l_export():
    class H1Muet:
        def get(self, *a, **k):
            raise httpx.ConnectError("injoignable")
    r = envoyer_dossier("P1-0106", H1Muet(), FausseApiH2().client, Outbox(), maintenant=0.0)
    assert r["statut"] == "export_impossible" and r["http"] is None


def test_meme_echange_ne_peut_etre_mis_deux_fois_en_file():
    outbox = Outbox()
    outbox.ajouter("P1-0106", "ech-1", "{}", 0.0)
    with pytest.raises(Exception):
        outbox.ajouter("P1-0106", "ech-1", "{}", 0.0)
