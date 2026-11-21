"""Forme commune de la reponse au droit d'acces (securite/droit_acces.py)."""

from datetime import datetime

from securite import droit_acces as DA
from securite.utilisateurs import ROLES


def test_entree_sans_champs_vides():
    e = DA.entree_acces(datetime(2026, 11, 21, 9, 30), "ALLER", "Envoi", resultat="OK", destinataire="H2")
    assert e == {"date": "2026-11-21T09:30:00", "action": "ALLER", "evenement": "Envoi",
                 "resultat": "OK", "destinataire": "H2"}


def test_destinataires_seulement_les_transmissions_reussies():
    acces = [DA.entree_acces("2026-01-01", "read", "Export", resultat="success", destinataire="H1"),
             DA.entree_acces("2026-02-01", "read", "Export", resultat="success", destinataire="H1"),
             DA.entree_acces("2026-03-01", "read", "Export", resultat="refused", destinataire="H1"),
             DA.entree_acces("2026-04-01", "read", "Lecture", resultat="success")]
    assert DA.destinataires(acces) == [{"etablissement": "CHU Al Massira", "code": "H1",
                                        "transmissions": 2, "derniere": "2026-02-01"}]


def test_reponse_complete_et_triee():
    r = DA.reponse(service="H2", patient="P2-0051", donnees={"x": 1}, consentement=None,
                   acces=[DA.entree_acces("2026-02-01", "b", "B"), DA.entree_acces("2026-01-01", "a", "A")])
    assert r["responsable_du_traitement"]["etablissement"] == "Clinique Al Baçar"
    assert [a["action"] for a in r["historique_des_acces"]] == ["a", "b"]
    assert {"rectification", "opposition", "reclamation"} <= set(r["droits"])
    assert "art. 7" in r["objet"] and r["finalite"]


def test_seul_le_dpo_a_le_droit_d_acces():
    assert [role for role, portees in ROLES.items() if "droit_acces" in portees] == ["dpo"]
