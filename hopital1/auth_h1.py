"""Authentification de l'API H1 : delegue a la couche securite/ commune.

Avant : ce fichier portait sa propre verification du jeton Bearer partage
(`H1_API_TOKEN`). Il n'y avait qu'un seul jeton, donc qu'un seul niveau de
droits : tout ou rien.

Maintenant, la verification est faite par le package `securite/`, partage avec
l'API de la clinique, afin qu'il n'existe qu'UNE implementation a auditer des
deux cotes de l'echange. Ce qu'elle ajoute :

  - un jeton par client appelant, avec ses portees (droits) propres ;
  - le jeton partage `H1_API_TOKEN` reste accepte, pour ne pas casser les postes
    deja configures, mais il est signale comme « a migrer » au demarrage ;
  - verrouillage apres plusieurs echecs, journal d'acces, en-tetes de securite,
    exigence de TLS.

Le comportement de refus est inchange : 503 si l'authentification n'est pas
configuree, 401 si le jeton est absent ou invalide.

Noms conserves pour ne rien casser ailleurs :
  `verifier_jeton`          dependance FastAPI, authentifie sans exiger de portee
  `AuthentificationRefusee` ancien nom de l'exception de refus
"""

import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from securite import exiger_portee                      # noqa: E402
from securite.jetons import AccesRefuse                 # noqa: E402

# Ancien nom, conserve pour les scripts qui l'importent encore.
AuthentificationRefusee = AccesRefuse

# Authentifie l'appelant sans exiger de portee particuliere. Les routes qui
# manipulent un dossier declarent la leur : Depends(exiger_portee("export")).
verifier_jeton = exiger_portee()

__all__ = ["AccesRefuse", "AuthentificationRefusee", "exiger_portee", "verifier_jeton"]
