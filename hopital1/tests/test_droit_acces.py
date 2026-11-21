"""Droit d'accès de la personne côté H1 (Oracle simulé)."""
from contextlib import contextmanager
from datetime import datetime as dt

import pytest
from fastapi.testclient import TestClient

import app as api
import oracle_repo as repo

JETON = "jeton-test-h1-assez-long-pour-etre-valide"

TABLES = {
    "patient": [dict(ipp="P1-0106", nom="Alaoui", prenom="Youssef", cin="AB123456",
                     date_naissance=dt(1968, 4, 12), ville="Settat")],
    "consentement": [dict(id_consentement="CST-0106", ipp="P1-0106", statut="ACTIF",
                          finalite="Partage soins", date_consentement=dt(2026, 10, 1))],
    "sejour": [dict(id_sejour="ST-0106-1", ipp="P1-0106", service="Endocrinologie",
                    date_admission=dt(2026, 10, 5)),
               dict(id_sejour="SJ-H2-1", ipp="P1-0106", service="Ophtalmologie", id_externe="V-P2-0051-01",
                    etablissement="Clinique Al Baçar", date_admission=dt(2026, 9, 20))],
    "diagnostic": [], "mesure": [], "allergie": [],
    "etude_imagerie": [dict(id_etude="IM-1", ipp="P1-0106", study_uid="2.25.1", statut="RECUPEREE")],
    "compte_rendu": [dict(id_cr="CR-1", ipp="P1-0106", conclusion="Rétinopathie")],
    "resultat_ophtalmo": [],
    "journal_echange": [dict(date_echange=dt(2026, 10, 6), sens="ALLER", statut="OK", details="{}"),
                        dict(date_echange=dt(2026, 10, 20), sens="RETOUR", statut="OK", details="{}")],
}


class Curseur:
    def __init__(self, conn):
        self.conn, self.description, self._lignes = conn, None, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None, **binds):
        sql = " ".join(sql.split())
        self.conn.requetes.append((sql, params or binds))
        if not sql.startswith("SELECT"):
            return
        table = sql.split(" FROM ")[1].split()[0]
        lignes = [l for l in TABLES.get(table, [])
                  if "ipp" not in l or binds.get("v") in (None, l["ipp"])]
        if table == "patient" and binds.get("v") != "P1-0106":
            lignes = []
        colonnes = sorted({c for l in lignes for c in l}) or ["ipp"]
        if sql.startswith("SELECT ipp"):
            colonnes = ["ipp"]
        self.description = [(c.upper(),) for c in colonnes]
        self._lignes = [tuple(l.get(c) for c in colonnes) for l in lignes]

    def fetchone(self):
        return self._lignes[0] if self._lignes else None

    def fetchall(self):
        return list(self._lignes)


class Connexion:
    def __init__(self):
        self.requetes, self.commits = [], 0

    def cursor(self):
        return Curseur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def test_reponse_complete_et_demande_tracee():
    conn = Connexion()
    r = repo.droit_acces(conn, "P1-0106", agent="utilisateur:dpo1")
    assert r["patient"] == "P1-0106" and r["responsable_du_traitement"]["code"] == "H1"
    assert r["donnees"]["dossier"]["patient"]["nom"] == "Alaoui"
    assert r["donnees"]["donnees_recues_de_la_clinique"]["compte_rendu"][0]["id_cr"] == "CR-1"
    assert r["destinataires"] == [{"etablissement": "Clinique Al Baçar", "code": "H2",
                                   "transmissions": 1, "derniere": "2026-10-06T00:00:00"}]
    assert r["origine_des_donnees"][0]["elements"] == 3            # 1 séjour externe + 2 lignes reçues
    assert r["consentement"]["partage_autorise"] is True
    journal = next(p for s, p in conn.requetes if s.startswith("INSERT INTO journal_echange"))
    assert journal[0] == "DROIT_ACCES" and journal[1] == "P1-0106" and conn.commits >= 1


def test_patient_inconnu():
    with pytest.raises(LookupError):
        repo.droit_acces(Connexion(), "P1-9999", agent="x")


def test_route_reservee_au_dpo(monkeypatch):
    from dataclasses import replace
    import json

    from securite.jetons import Verificateur, empreinte_complete

    @contextmanager
    def connexion():
        yield Connexion()

    monkeypatch.setattr(repo, "connexion", connexion)
    monkeypatch.setenv("H1_API_TOKEN", JETON)
    assert TestClient(api.app, headers={"Authorization": f"Bearer {JETON}"}).get(
        "/api/patients/P1-0106/droit-acces").status_code == 200

    autre = "jeton-medecin-" + "m" * 30
    etat = api.app.state.securite
    registre = etat.conf.registre.parent / "registre-droit-acces-test.json"
    registre.write_text(json.dumps({"clients": [{"id": "h1-interne", "actif": True,
                                                 "empreinte": "sha256:" + empreinte_complete(autre),
                                                 "portees": ["h1:export"]}]}), encoding="utf-8")
    monkeypatch.setattr(etat, "verificateur",
                        Verificateur(replace(etat.conf, registre=registre, variable_jeton="")))
    r = TestClient(api.app, headers={"Authorization": f"Bearer {autre}"}).get("/api/patients/P1-0106/droit-acces")
    assert r.status_code == 403
