"""En-tetes de securite HTTP : politique appliquee a chaque reponse.

Les tests par requete complete sont dans test_intergiciels.py ; ici on verifie
la politique elle-meme, chemin par chemin.
"""

import pytest

from securite.entetes import (
    CHEMINS_SANS_CSP,
    ENTETES_A_RETIRER,
    ENTETES_BASE,
    HSTS,
    entetes_pour,
)


def test_entetes_de_base_presentes_en_http():
    entetes = entetes_pour("/api/patients/P2-0051/bundle", https=False)
    assert entetes["X-Content-Type-Options"] == "nosniff"
    assert entetes["Referrer-Policy"] == "no-referrer"
    assert entetes["X-Frame-Options"] == "DENY"
    assert "no-store" in entetes["Cache-Control"]
    assert "default-src 'none'" in entetes["Content-Security-Policy"]
    assert entetes["Cross-Origin-Resource-Policy"] == "same-origin"


def test_cache_control_interdit_tout_stockage():
    """Une reponse de dossier patient ne doit etre gardee nulle part."""
    cache = entetes_pour("/api/retours", https=True)["Cache-Control"]
    for directive in ("no-store", "no-cache", "must-revalidate", "private"):
        assert directive in cache


def test_hsts_absent_en_http():
    """Annoncer HSTS en clair n'apporte rien et bloque un poste de test."""
    assert "Strict-Transport-Security" not in entetes_pour("/api/retours", https=False)


def test_hsts_pose_en_https():
    entetes = entetes_pour("/api/retours", https=True)
    assert entetes["Strict-Transport-Security"] == HSTS
    assert "max-age=31536000" in entetes["Strict-Transport-Security"]


@pytest.mark.parametrize("chemin", list(CHEMINS_SANS_CSP))
def test_csp_retiree_pour_la_documentation(chemin):
    """La doc interactive charge ses scripts : default-src 'none' la casserait."""
    entetes = entetes_pour(chemin, https=False)
    assert "Content-Security-Policy" not in entetes
    assert "Cross-Origin-Resource-Policy" not in entetes
    assert entetes["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("chemin", ["/api/retours", "/health", "/Patient/123456", "/"])
def test_csp_presente_sur_les_routes_de_donnees(chemin):
    assert "Content-Security-Policy" in entetes_pour(chemin, https=False)


def test_entetes_pour_ne_modifie_pas_la_politique_de_reference():
    """Le retrait de la CSP pour /docs ne doit pas fuir sur les autres routes."""
    entetes_pour("/docs", https=False)
    assert "Content-Security-Policy" in ENTETES_BASE
    assert "Content-Security-Policy" in entetes_pour("/api/retours", https=False)


def test_entetes_techniques_a_retirer_declarees():
    assert set(ENTETES_A_RETIRER) == {"server", "x-powered-by"}
    assert all(nom == nom.lower() for nom in ENTETES_A_RETIRER)
