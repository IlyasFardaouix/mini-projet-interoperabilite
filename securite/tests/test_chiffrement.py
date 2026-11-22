"""Chiffrement au repos (securite/chiffrement.py) et refus du jeton partage historique."""

import pytest

from securite.chiffrement import Chiffreur, ErreurChiffrement, nouvelle_cle
from securite.jetons import AccesRefuse, Verificateur

from .conftest import JETON_PARTAGE, JETON_REGISTRE, ecrire_registre, entree_registre

CLE = nouvelle_cle("v1")


def test_aller_retour_et_alea():
    c = Chiffreur.depuis_texte(CLE)
    a, b = c.chiffrer(b"dossier", "patient:P2-0051"), c.chiffrer(b"dossier", "patient:P2-0051")
    assert a != b and a.startswith("v1:") and b"dossier" not in a.encode()
    assert c.dechiffrer(a, "patient:P2-0051") == b"dossier"


def test_contexte_lie_au_chiffre():
    """Un dossier recopie sur un autre patient ne se dechiffre pas."""
    c = Chiffreur.depuis_texte(CLE)
    with pytest.raises(ErreurChiffrement):
        c.dechiffrer(c.chiffrer(b"x", "patient:A"), "patient:B")


def test_alteration_detectee():
    c = Chiffreur.depuis_texte(CLE)
    valeur = c.chiffrer(b"groupe sanguin O+", "p")
    altere = valeur[:-6] + ("A" if valeur[-6] != "A" else "B") + valeur[-5:]
    with pytest.raises(ErreurChiffrement):
        c.dechiffrer(altere, "p")


def test_mauvaise_cle():
    with pytest.raises(ErreurChiffrement):
        Chiffreur.depuis_texte(nouvelle_cle("v1")).dechiffrer(Chiffreur.depuis_texte(CLE).chiffrer(b"x", "p"), "p")


def test_rotation_ancienne_cle_lisible():
    ancienne = Chiffreur.depuis_texte(CLE)
    valeur = ancienne.chiffrer(b"x", "p")
    trousseau = Chiffreur.depuis_texte(nouvelle_cle("v2") + "," + CLE)
    assert trousseau.courante == "v2" and trousseau.dechiffrer(valeur, "p") == b"x"
    assert trousseau.a_rechiffrer(valeur) and not trousseau.a_rechiffrer(trousseau.chiffrer(b"x", "p"))


@pytest.mark.parametrize("texte", ["v1", "v1:" + "A" * 10, "v1:!!!", ":" + "A" * 43])
def test_cle_mal_formee_refusee(texte):
    with pytest.raises(ErreurChiffrement):
        Chiffreur.depuis_texte(texte)


def test_variable_absente(monkeypatch):
    monkeypatch.delenv("CLE_TEST_ABSENTE", raising=False)
    assert Chiffreur.depuis_env("CLE_TEST_ABSENTE") is None


def test_index_aveugle_deterministe_et_dependant_de_la_cle():
    c = Chiffreur.depuis_texte(CLE)
    assert c.index("cin", "AB123456") == c.index("cin", "AB123456") != c.index("cin", "AB123457")
    assert "AB123456" not in c.index("cin", "AB123456")
    assert Chiffreur.depuis_texte(nouvelle_cle()).index("cin", "AB123456") != c.index("cin", "AB123456")


# ── jeton partage historique ─────────────────────────────────────────────────
def test_jeton_partage_refuse_quand_le_registre_existe(reglages, chemin_registre):
    ecrire_registre(chemin_registre, entree_registre())
    v = Verificateur(reglages(H2_TOKEN=JETON_PARTAGE))
    with pytest.raises(AccesRefuse) as refus:
        v.verifier("Bearer " + JETON_PARTAGE)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_partage_desactive")
    assert v.verifier("Bearer " + JETON_REGISTRE).source == "registre"
    assert any("refuse" in a for a in v.diagnostic())


def test_jeton_partage_accepte_le_temps_d_une_migration(reglages, chemin_registre):
    ecrire_registre(chemin_registre, entree_registre())
    v = Verificateur(reglages(H2_TOKEN=JETON_PARTAGE, SEC_JETON_HISTORIQUE="1"))
    assert v.verifier("Bearer " + JETON_PARTAGE).source == "historique"
    assert any("ACCEPTE" in a for a in v.diagnostic())


def test_jeton_partage_seul_toujours_accepte(reglages):
    """Sans registre (poste pas encore migre), le comportement ne change pas."""
    assert Verificateur(reglages(H2_TOKEN=JETON_PARTAGE)).verifier("Bearer " + JETON_PARTAGE).source == "historique"
