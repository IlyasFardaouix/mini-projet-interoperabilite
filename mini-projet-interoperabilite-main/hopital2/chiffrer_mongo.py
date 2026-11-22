"""
chiffrer_mongo.py — chiffre au repos les dossiers déjà présents dans MongoDB
===========================================================================
À lancer une fois après charger_mongo.py (qui écrit les données de démonstration
en clair), puis après chaque rotation de clé. Les dossiers en clair, ou chiffrés
avec une ancienne clé, sont réécrits avec la clé courante ; les index aveugles
sont recalculés. Rejouable sans risque.

    cd hopital2
    ..\\.venv\\Scripts\\python.exe chiffrer_mongo.py

Clé : H2_CLE_CHIFFREMENT dans hopital2/.env (générée par generer_jetons.py, ou
`py ../securite/chiffrement.py`). Rotation : mettre la nouvelle clé EN PREMIER,
garder l'ancienne après une virgule, lancer ce script, puis retirer l'ancienne.
SANS LA CLÉ, LES DOSSIERS SONT PERDUS : la sauvegarder hors du poste.
"""

from __future__ import annotations

import sys


def main() -> int:
    import api_h2
    from stores import StoreMongoChiffre

    if not isinstance(api_h2.STORE, StoreMongoChiffre):
        print("MongoDB non configuré ou H2_CLE_CHIFFREMENT absent : rien n'est chiffré.", file=sys.stderr)
        return 2
    bilan = api_h2.STORE.rechiffrer_tout()
    print(f"{bilan['chiffres']} dossier(s) chiffré(s), {bilan['deja']} déjà à jour.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
