"""Configuration de sécurité pour la suite de tests de H1.

Ce fichier est chargé par pytest AVANT les modules de test, donc avant tout
`import app`. C'est important : la couche de sécurité fige ses réglages de
transport au démarrage du service (voir `securite/config.py`). Les positionner
ici est la seule façon de les choisir pour les tests.

Les tests actuels ne couvrent que les adaptateurs et n'importent pas l'API :
ces réglages ne les concernent pas encore. Ils sont en place pour le jour où des
tests d'API arriveront, afin que le premier d'entre eux ne se heurte pas à un
403 « HTTPS exigé » dont la cause n'a rien d'évident.

Raison de chaque réglage :

- `SEC_MODE=local` + `SEC_TLS_REQUIS=0` : le client de test de FastAPI parle en
  `http://testserver`. En mode strict, la couche refuserait chaque requête. Le
  mode local ne désactive PAS l'authentification : un jeton valide reste
  obligatoire sur les routes de dossier.
- `SEC_DEBIT_PAR_MINUTE` et `SEC_ECHECS_MAX` très élevés : toutes les requêtes
  de la suite viennent de la même adresse. Sinon des tests échoueraient en 429
  pour une raison étrangère à ce qu'ils vérifient — en particulier ceux qui
  essaient volontairement un mauvais jeton.
- `SEC_JOURNAL` dans un dossier temporaire : la suite n'écrit pas dans
  `journaux/` du dépôt.

Les tests qui vérifient spécifiquement TLS, la limitation de débit et le
verrouillage après échecs sont dans `securite/tests/`, avec leur propre
configuration.
"""

import os
import tempfile
from pathlib import Path

_TEMPORAIRE = Path(tempfile.gettempdir()) / "interop-tests-h1"
_TEMPORAIRE.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("SEC_MODE", "local")
os.environ.setdefault("SEC_TLS_REQUIS", "0")
os.environ.setdefault("SEC_DEBIT_PAR_MINUTE", "1000000")
os.environ.setdefault("SEC_ECHECS_MAX", "1000000")
os.environ.setdefault("SEC_JOURNAL", str(_TEMPORAIRE / "securite-h1.jsonl"))
os.environ.setdefault("SEC_SEL_AUDIT", "sel-de-test-sans-valeur-reelle")
# Registre volontairement absent : les tests utilisent le jeton partagé.
os.environ.setdefault("SEC_REGISTRE", str(_TEMPORAIRE / "registre-absent.json"))
