"""Vérifie que l'API H1 plafonne aussi les corps sans taille annoncée fiable."""

from dataclasses import replace

from fastapi.testclient import TestClient

import app as api


def test_corps_plus_grand_que_la_limite_malgre_content_length_faux(monkeypatch):
    monkeypatch.setenv("H1_API_TOKEN", "jeton-test-h1-assez-long-pour-etre-valide")
    monkeypatch.setattr(api.SECURITE, "conf",
                        replace(api.SECURITE.conf, taille_max_corps=64))

    reponse = TestClient(api.app).post(
        "/api/retours/simulation",
        headers={"Authorization": "Bearer jeton-test-h1-assez-long-pour-etre-valide",
                 "Content-Length": "1",
                 "Content-Type": "application/fhir+json"},
        content=b'{"contenu":"' + b"x" * 128 + b'"}',
    )

    assert reponse.status_code == 413
    assert reponse.json()["resourceType"] == "OperationOutcome"
