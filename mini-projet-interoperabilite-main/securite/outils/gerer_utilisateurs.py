"""Gestion des comptes du personnel (connexion a l'interface), poste par poste.

Volontairement en ligne de commande : aucune route HTTP ne cree ni ne modifie
de compte, ce qui retire une cible a un attaquant. A lancer sur le poste du
service concerne, par l'administrateur.

    py securite/outils/gerer_utilisateurs.py --service h2 creer a.bennani --nom "Dr A. Bennani" --role medecin
    py securite/outils/gerer_utilisateurs.py --service h2 lister
    py securite/outils/gerer_utilisateurs.py --service h2 role a.bennani dpo
    py securite/outils/gerer_utilisateurs.py --service h2 desactiver a.bennani
    py securite/outils/gerer_utilisateurs.py --service h2 reactiver a.bennani
    py securite/outils/gerer_utilisateurs.py --service h2 reinitialiser a.bennani

`creer` et `reinitialiser` affichent UNE fois un mot de passe provisoire, a
remettre en main propre : la personne doit le changer a sa premiere connexion
(POST /auth/mot-de-passe). Avant ce changement, sa session n'a aucun droit.

Fichier des comptes : SEC_UTILISATEURS, sinon securite/comptes/utilisateurs-<service>.json
(hors depot Git). Une desactivation ou un changement de role prend effet a la
requete suivante, sans redemarrer l'API.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

from securite.utilisateurs import ROLES, Comptes, SaisieInvalide  # noqa: E402


def mdp_provisoire(login: str) -> str:
    while True:
        mdp = secrets.token_urlsafe(15)                # 20 caracteres, environ 120 bits
        if login not in mdp.lower():
            return mdp


def chemin_comptes(service: str) -> Path:
    return Path(os.getenv("SEC_UTILISATEURS") or RACINE / "securite" / "comptes" / f"utilisateurs-{service}.json")


def main(arguments=None) -> int:
    analyseur = argparse.ArgumentParser(description="Comptes du personnel (H1 ou H2).")
    analyseur.add_argument("--service", required=True, choices=["h1", "h2"])
    actions = analyseur.add_subparsers(dest="action", required=True)
    creer = actions.add_parser("creer")
    creer.add_argument("login")
    creer.add_argument("--nom", required=True)
    creer.add_argument("--role", required=True, choices=sorted(ROLES))
    actions.add_parser("lister")
    for nom in ("desactiver", "reactiver", "reinitialiser"):
        actions.add_parser(nom).add_argument("login")
    role = actions.add_parser("role")
    role.add_argument("login")
    role.add_argument("role", choices=sorted(ROLES))
    a = analyseur.parse_args(arguments)

    comptes = Comptes(chemin_comptes(a.service))
    try:
        if a.action == "lister":
            for c in comptes.tous():
                etat = "actif" if c.actif else "DESACTIVE"
                provisoire = "  (mot de passe provisoire)" if c.doit_changer_mdp else ""
                print(f"{c.login:<24} {c.role:<10} {etat:<10} {c.nom}{provisoire}")
            return 0
        if a.action == "creer":
            mdp = mdp_provisoire(a.login.lower())
            c = comptes.creer(a.login, a.nom, a.role, mdp, provisoire=True)
            print(f"Compte {c.login} cree ({c.role}) dans {comptes.chemin}.")
            print(f"Mot de passe provisoire (affiche une seule fois) : {mdp}")
            return 0
        if a.action == "reinitialiser":
            mdp = mdp_provisoire(a.login.lower())
            comptes.modifier(a.login, mdp=mdp, doit_changer_mdp=True)
            print(f"Nouveau mot de passe provisoire pour {a.login} (affiche une seule fois) : {mdp}")
            print("Les sessions deja ouvertes perdent leurs droits jusqu'au changement du mot de passe.")
            return 0
        if a.action == "role":
            comptes.modifier(a.login, role=a.role)
        else:
            comptes.modifier(a.login, actif=(a.action == "reactiver"))
        print(f"Compte {a.login.lower()} : {a.action} effectue.")
        return 0
    except SaisieInvalide as exc:
        print("Refuse : " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
