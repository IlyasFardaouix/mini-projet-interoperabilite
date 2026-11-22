"""Imagerie côté H1 : récupération depuis la passerelle de la clinique, passerelle du CHU."""
from contextlib import contextmanager
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

import app as api
import oracle_repo as repo
from recuperer_imagerie import recuperer

from imagerie.dicom import generer_etude, vers_octets
from imagerie.dicomweb import EntrepotMemoire, decoder_multipart, encoder_multipart

BASE_H2 = "https://clinique.test:8002/dicom-web"
LOCALE = "https://127.0.0.1:8000/dicom-web"
UID = "2.25.11060236952204337488"
JETON = "jeton-test-h1-assez-long-pour-etre-valide"


def etude(uid=UID):
    return [vers_octets(ds) for ds in generer_etude(
        {"id": "P2-0051", "nom": "Alaoui", "prenom": "Youssef", "naissance": "1968-04-12", "sexe": "M"},
        {"study_uid": uid, "instances": 2, "date": datetime(2026, 9, 20)}, etablissement="Clinique")]


class FauxCurseur:
    def __init__(self, conn):
        self.conn, self.description, self._lignes = conn, None, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None, **binds):
        self.conn.requetes.append((" ".join(sql.split()), params or binds))
        if sql.startswith("SELECT id_etude"):
            cols = ["id_etude", "ipp", "study_uid", "url_pacs", "statut"]
            self.description = [(c.upper(),) for c in cols]
            self._lignes = [tuple(e.get(c) for c in cols) for e in self.conn.etudes]

    def fetchall(self):
        return list(self._lignes)


class FausseConnexion:
    def __init__(self, etudes):
        self.etudes, self.requetes, self.commits = etudes, [], 0

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.commits += 1

    def mises_a_jour(self):
        return [p for s, p in self.requetes if s.startswith("UPDATE etude_imagerie")]


def clinique(reponses):
    """Fausse passerelle de la clinique : {uid: octets | code HTTP}."""
    appels = []

    def repondre(requete):
        appels.append(str(requete.url))
        valeur = reponses.get(requete.url.path.rsplit("/", 1)[1], 404)
        if isinstance(valeur, int):
            return httpx.Response(valeur)
        corps, type_contenu = encoder_multipart(valeur)
        return httpx.Response(200, content=corps, headers={"Content-Type": type_contenu})

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    client.appels = appels
    return client


def ligne(uid=UID, url=BASE_H2, id_etude="IM-1"):
    return {"id_etude": id_etude, "ipp": "P1-0106", "study_uid": uid, "url_pacs": url, "statut": "available"}


# ── récupération ─────────────────────────────────────────────────────────────
def test_recuperation_nominale():
    conn, pacs = FausseConnexion([ligne()]), EntrepotMemoire()
    bilan = recuperer(conn, clinique({UID: etude()}), pacs, base_h2=BASE_H2, url_locale=LOCALE)
    assert bilan == [{"study_uid": UID, "statut": "RECUPEREE", "instances": 2}]
    assert len(pacs.etude(UID)) == 2
    maj = conn.mises_a_jour()[0]
    assert maj["s"] == "RECUPEREE" and maj["u"] == LOCALE and maj["n"] == 2
    assert any(s.startswith("INSERT INTO journal_echange") for s, _ in conn.requetes) and conn.commits == 1


def test_adresse_inconnue_jamais_appelee():
    """Un Bundle forgé ne doit pas faire partir le jeton du CHU vers une autre adresse."""
    conn, client = FausseConnexion([ligne(url="https://attaquant.example/dicom-web")]), clinique({UID: etude()})
    bilan = recuperer(conn, client, EntrepotMemoire(), base_h2=BASE_H2, url_locale=LOCALE)
    assert bilan[0]["statut"] == "URL_REFUSEE" and client.appels == []


def test_instances_d_une_autre_etude_rejetees():
    conn, pacs = FausseConnexion([ligne()]), EntrepotMemoire()
    bilan = recuperer(conn, clinique({UID: etude("2.25.42")}), pacs, base_h2=BASE_H2, url_locale=LOCALE)
    assert bilan[0]["statut"] == "INCOHERENTE" and not pacs.existe(UID) and not pacs.existe("2.25.42")


@pytest.mark.parametrize("code, statut", [(403, "REFUSEE"), (404, "ABSENTE")])
def test_refus_de_la_clinique_definitif(code, statut):
    conn = FausseConnexion([ligne()])
    bilan = recuperer(conn, clinique({UID: code}), EntrepotMemoire(), base_h2=BASE_H2, url_locale=LOCALE)
    assert bilan[0]["statut"] == statut and conn.mises_a_jour()[0]["s"] == statut


def test_panne_passagere_rien_n_est_marque():
    conn = FausseConnexion([ligne()])
    bilan = recuperer(conn, clinique({UID: 503}), EntrepotMemoire(), base_h2=BASE_H2, url_locale=LOCALE)
    assert bilan[0]["statut"] == "EN_ATTENTE" and conn.mises_a_jour() == []


# ── passerelle du CHU ────────────────────────────────────────────────────────
@pytest.fixture
def chu(monkeypatch):
    monkeypatch.setenv("H1_API_TOKEN", JETON)
    pacs = EntrepotMemoire()
    pacs.stocker(etude())
    monkeypatch.setattr(api, "PACS", pacs)

    @contextmanager
    def connexion():
        yield object()

    monkeypatch.setattr(repo, "connexion", connexion)
    monkeypatch.setattr(repo, "patient_de_l_etude", lambda conn, uid: "P1-0106" if uid == UID else None)
    return TestClient(api.app, headers={"Authorization": f"Bearer {JETON}"})


def test_passerelle_chu(chu):
    r = chu.get(f"/dicom-web/studies/{UID}")
    assert r.status_code == 200 and len(decoder_multipart(r.content, r.headers["content-type"])) == 2
    assert chu.get("/dicom-web/studies/2.25.7").status_code == 404


def test_passerelle_chu_anti_boucle(chu, monkeypatch):
    from securite.jetons import Appelant

    appelant = Appelant(client="h2-clinique", portees=frozenset({"h1:imagerie.lire"}),
                        empreinte="x", source="registre")
    with pytest.raises(api.AccesRefuse) as e:
        api.autoriser_imagerie(appelant, UID)
    assert e.value.http == 403


# ── récupération automatique après un retour ─────────────────────────────────
from recuperer_imagerie import recuperer_apres_retour  # noqa: E402


def test_apres_retour_images_suivent_le_dossier(monkeypatch):
    monkeypatch.setenv("DEMO", "1")
    monkeypatch.setenv("H2_DICOMWEB_URL", BASE_H2)
    conn, pacs = FausseConnexion([ligne()]), EntrepotMemoire()
    bilan = recuperer_apres_retour(conn, "P1-0106", client=clinique({UID: etude()}), pacs=pacs)
    assert bilan == [{"study_uid": UID, "statut": "RECUPEREE", "instances": 2}]
    assert len(pacs.etude(UID)) == 2
    assert any("ipp" in str(p) and p.get("ipp") == "P1-0106" for s, p in conn.requetes if s.startswith("SELECT id_etude"))


def test_apres_retour_desactive_par_defaut(monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)
    monkeypatch.delenv("H1_IMAGERIE_AUTO", raising=False)
    client = clinique({UID: etude()})
    assert recuperer_apres_retour(FausseConnexion([ligne()]), "P1-0106", client=client, pacs=EntrepotMemoire()) is None
    assert client.appels == []


def test_apres_retour_non_configure(monkeypatch):
    monkeypatch.setenv("H1_IMAGERIE_AUTO", "1")
    monkeypatch.delenv("H2_DICOMWEB_URL", raising=False)
    assert recuperer_apres_retour(FausseConnexion([ligne()]), "P1-0106", pacs=EntrepotMemoire()) is None


def test_apres_retour_une_panne_n_annule_pas_l_import(monkeypatch):
    monkeypatch.setenv("DEMO", "1")
    monkeypatch.setenv("H2_DICOMWEB_URL", BASE_H2)
    bilan = recuperer_apres_retour(FausseConnexion([ligne()]), "P1-0106", client=object(), pacs=EntrepotMemoire())
    assert bilan and bilan[0]["statut"] == "EN_ATTENTE"
