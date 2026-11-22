"""Outils en ligne de commande de la couche de securite.

Chaque module s'execute directement depuis la racine du depot :

    py securite/outils/generer_jetons.py        jetons par client + registre
    py securite/outils/generer_certificats.py   autorite interne + certificats
    py securite/outils/verifier_securite.py     auditeur automatique du depot
    py securite/outils/installer_hooks.py       garde-fou de commit

Ils ajoutent eux-memes la racine du depot au chemin d'import : ils fonctionnent
donc sans installation prealable du package.
"""
