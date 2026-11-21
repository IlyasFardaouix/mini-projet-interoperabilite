"""Genere les jetons d'acces des deux hopitaux et le registre associe.

    py securite/outils/generer_jetons.py
    py securite/outils/generer_jetons.py --client h2-clinique --portees h1:import,h1:simulation
    py securite/outils/generer_jetons.py --rotation h1-chu

Ce que l'outil ecrit :

  securite/registre_jetons.json        les EMPREINTES des jetons et leurs droits
  securite/jetons_locaux/<client>.txt  le jeton en clair, un fichier par client
  securite/jetons_locaux/env.jetons    les valeurs a recopier dans les .env

Le jeton en clair n'est jamais affiche a l'ecran : il irait dans l'historique du
terminal et dans les captures d'ecran. Il est ecrit dans un fichier, que l'on
transmet a l'autre hopital par un canal separe (voir
docs/securite/procedure-secrets.md), puis que l'on supprime.

`securite/jetons_locaux/` et `securite/registre_jetons.json` sont exclus de Git.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

from securite.config import PORTEES_CONNUES                      # noqa: E402
from securite.jetons import empreinte_complete                   # noqa: E402

DOSSIER = RACINE / "securite"
REGISTRE = DOSSIER / "registre_jetons.json"
LOCAUX = DOSSIER / "jetons_locaux"

# Clients prevus par le contrat d'echange. Chacun recoit le minimum necessaire :
# l'API de H1 ne peut qu'envoyer un retour a H2, et inversement. Aucun client ne
# cumule la lecture des dossiers des deux cotes.
CLIENTS = [
    {"id": "h1-chu",
     "portees": ["h2:simulation", "h2:import"],
     "description": "API du CHU Al Massira : envoie ses Bundles a la clinique."},
    {"id": "h2-clinique",
     "portees": ["h1:simulation", "h1:import"],
     "description": "API de la Clinique Al Bacar : envoie ses retours au CHU."},
    {"id": "h1-interne",
     "portees": ["h1:export", "h1:simulation", "h1:import"],
     "description": "Outils locaux du CHU (exporter.py, importer.py)."},
    {"id": "h2-interne",
     "portees": ["h2:export", "h2:simulation", "h2:import",
                 "h2:patient.lire", "h2:patient.chercher", "h2:patient.creer"],
     "description": "Outils locaux de la clinique (client_envoi.py, demo.py)."},
    {"id": "supervision",
     "portees": [],
     "description": "Sonde de disponibilite : /health et /metadata seulement."},
    {"id": "audit",
     "portees": ["h1:audit", "h2:audit"],
     "description": "Responsable securite : relecture des journaux d'acces."},
]


def charger_registre() -> dict:
    if REGISTRE.exists():
        try:
            contenu = json.loads(REGISTRE.read_text(encoding="utf-8"))
            if isinstance(contenu, dict) and isinstance(contenu.get("clients"), list):
                return contenu
        except ValueError:
            print("ATTENTION : registre existant illisible, il sera remplace.")
    return {"version": 1, "clients": []}


def ecrire_local(nom: str, valeur: str) -> Path:
    LOCAUX.mkdir(parents=True, exist_ok=True)
    chemin = LOCAUX / nom
    chemin.write_text(valeur + "\n", encoding="utf-8")
    try:
        chemin.chmod(0o600)
    except OSError:
        pass
    return chemin


def nouveau_jeton() -> str:
    """256 bits d'entropie : hors de portee d'une attaque par force brute."""
    return secrets.token_urlsafe(32)


def entree(client: dict, jeton: str, jours: int) -> dict:
    maintenant = datetime.now(timezone.utc)
    return {
        "id": client["id"],
        "description": client.get("description", ""),
        "empreinte": "sha256:" + empreinte_complete(jeton),
        "portees": list(client["portees"]),
        "expire_le": (maintenant + timedelta(days=jours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actif": True,
        "cree_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def portees_invalides(portees) -> list:
    mauvaises = []
    for portee in portees:
        service, _, suffixe = portee.partition(":")
        if service not in {"h1", "h2"} or (suffixe not in PORTEES_CONNUES and suffixe != "*"):
            mauvaises.append(portee)
    return mauvaises


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Genere les jetons d'acces et le registre du projet.")
    analyseur.add_argument("--client", help="ne (re)generer que ce client")
    analyseur.add_argument("--portees", help="liste de portees separees par des virgules")
    analyseur.add_argument("--rotation", help="remplacer le jeton d'un client existant")
    analyseur.add_argument("--jours", type=int, default=90,
                           help="duree de validite du jeton (defaut : 90)")
    analyseur.add_argument("--forcer", action="store_true",
                           help="regenerer les jetons deja presents dans le registre")
    arguments = analyseur.parse_args(argv)

    registre = charger_registre()
    existants = {e.get("id"): e for e in registre["clients"]}

    cible = arguments.rotation or arguments.client
    if cible:
        modele = next((c for c in CLIENTS if c["id"] == cible), {"id": cible, "portees": []})
        if arguments.portees:
            modele = dict(modele,
                          portees=[p.strip() for p in arguments.portees.split(",") if p.strip()])
        demandes = [modele]
        forcer = True
    else:
        demandes = CLIENTS
        forcer = arguments.forcer

    mauvaises = portees_invalides([p for c in demandes for p in c["portees"]])
    if mauvaises:
        print("Portees inconnues : " + ", ".join(mauvaises))
        print("Suffixes valides  : " + ", ".join(sorted(PORTEES_CONNUES)))
        return 2

    ecrits = []
    for client in demandes:
        if client["id"] in existants and not forcer:
            print("  = " + client["id"] + " : deja dans le registre, inchange.")
            continue
        jeton = nouveau_jeton()
        existants[client["id"]] = entree(client, jeton, arguments.jours)
        ecrits.append((client["id"], ecrire_local(client["id"] + ".txt", jeton),
                       client["portees"]))

    registre["clients"] = [existants[cle] for cle in sorted(existants)]
    registre["maj_le"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    REGISTRE.write_text(json.dumps(registre, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    try:
        REGISTRE.chmod(0o600)
    except OSError:
        pass

    # Valeurs de service : sel du journal d'audit et cle de signature des JWT.
    env = LOCAUX / "env.jetons"
    if not env.exists() or arguments.forcer:
        ecrire_local("env.jetons", "\n".join([
            "# A RECOPIER dans le .env de chaque service, JAMAIS a commiter.",
            "# Un sel different par hopital est normal : il empeche de recouper",
            "# les journaux des deux etablissements.",
            "SEC_SEL_AUDIT=" + secrets.token_urlsafe(32),
            "SEC_JWT_SECRET=" + secrets.token_urlsafe(48),
        ]))
        print("  + valeurs de service -> " + str(env))

    print("\nRegistre : " + str(REGISTRE) + "  (" + str(len(registre["clients"])) + " clients)")
    if ecrits:
        print("Jetons ecrits (a transmettre hors Git, puis a supprimer) :")
        for nom, chemin, portees in ecrits:
            print("  + " + nom.ljust(14) + str(chemin))
            print("    portees : " + (", ".join(portees) or "aucune (health/metadata seulement)"))
    print("\nEtapes suivantes :")
    print("  1. recopier securite/jetons_locaux/env.jetons dans le .env de chaque service")
    print("  2. transmettre a l'autre hopital SON jeton, par un canal separe")
    print("  3. supprimer les fichiers de securite/jetons_locaux/ une fois transmis")
    print("  4. verifier : py securite/outils/verifier_securite.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
