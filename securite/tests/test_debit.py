"""Limitation de debit : seau a jetons, une cle par adresse appelante.

Aucun sleep : l'horloge est injectee par le parametre `maintenant`.
"""

import pytest

from securite.debit import CHEMINS_EXEMPTES, SeauAJetons


def test_premiere_requete_autorisee():
    autorise, attendre = SeauAJetons(par_minute=60).autoriser("10.0.0.1", maintenant=0.0)
    assert autorise is True
    assert attendre == 0


def test_rafale_epuisee_puis_refus():
    seau = SeauAJetons(par_minute=60, rafale=3)
    for _ in range(3):
        assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is True
    autorise, attendre = seau.autoriser("10.0.0.1", maintenant=0.0)
    assert autorise is False
    assert attendre >= 1


def test_le_seau_se_remplit_avec_le_temps():
    """60 requetes par minute : une place se libere apres une seconde."""
    seau = SeauAJetons(par_minute=60, rafale=2)
    assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is True
    assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is True
    assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is False
    assert seau.autoriser("10.0.0.1", maintenant=0.5)[0] is False
    assert seau.autoriser("10.0.0.1", maintenant=1.0)[0] is True


def test_le_seau_ne_depasse_pas_sa_rafale():
    """Une longue pause ne donne pas droit a un stock illimite de requetes."""
    seau = SeauAJetons(par_minute=600, rafale=2)
    for _ in range(2):
        assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is True
    assert seau.autoriser("10.0.0.1", maintenant=10_000.0)[0] is True
    assert seau.autoriser("10.0.0.1", maintenant=10_000.0)[0] is True
    assert seau.autoriser("10.0.0.1", maintenant=10_000.0)[0] is False


def test_les_adresses_sont_comptees_separement():
    seau = SeauAJetons(par_minute=60, rafale=1)
    assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is True
    assert seau.autoriser("10.0.0.1", maintenant=0.0)[0] is False
    assert seau.autoriser("10.0.0.2", maintenant=0.0)[0] is True


def test_delai_annonce_coherent_avec_le_debit():
    """Le delai renvoye suffit a reconstituer un jeton (ici 6 s pour 10/min)."""
    seau = SeauAJetons(par_minute=10, rafale=1)
    seau.autoriser("10.0.0.1", maintenant=0.0)
    autorise, attendre = seau.autoriser("10.0.0.1", maintenant=0.0)
    assert autorise is False
    assert attendre == 7
    assert seau.autoriser("10.0.0.1", maintenant=float(attendre))[0] is True


@pytest.mark.parametrize("par_minute, rafale, attendus", [
    (0, None, (1, 10)),              # valeurs plancher
    (60, 0, (60, 1)),
    (400, None, (400, 100)),         # rafale par defaut : un quart du debit
    (8, None, (8, 10)),              # plancher de rafale a 10
])
def test_valeurs_limites_du_seau(par_minute, rafale, attendus):
    seau = SeauAJetons(par_minute=par_minute, rafale=rafale)
    assert (seau.par_minute, seau.rafale) == attendus
    assert seau.debit == seau.par_minute / 60.0


def test_table_des_seaux_purgee_des_entrees_pleines():
    """La table ne grossit pas indefiniment : un seau plein n'apprend plus rien."""
    seau = SeauAJetons(par_minute=600, rafale=2, taille_max_table=5)
    for numero in range(10):
        seau.autoriser("10.0.0." + str(numero), maintenant=0.0)
    assert len(seau._seaux) == 10
    seau.autoriser("10.0.1.1", maintenant=10_000.0)      # declenche la purge
    assert len(seau._seaux) <= 2


def test_chemins_exemptes_declares():
    assert CHEMINS_EXEMPTES == ("/health", "/metadata")
