"""Configuration de sécurité pour la suite de tests de H2.

Ce fichier est chargé par pytest AVANT les modules de test, donc avant
`import api_h2`. C'est important : la couche de sécurité fige ses réglages de
transport au démarrage du service (voir `securite/config.py`). Les positionner
ici est la seule façon de les choisir pour les tests.

Trois réglages, et la raison de chacun :

- `SEC_MODE=local` + `SEC_TLS_REQUIS=0` : le client de test de FastAPI parle en
  `http://testserver`. En mode strict, la couche refuserait chaque requête avec
  un 403 « HTTPS exigé ». Le mode local ne désactive PAS l'authentification :
  un jeton valide reste obligatoire sur les routes de dossier.
- `SEC_DEBIT_PAR_MINUTE` très élevé : toutes les requêtes de la suite viennent
  de la même adresse, elles épuiseraient sinon le quota normal (120/min) et des
  tests échoueraient en 429 pour une raison étrangère à ce qu'ils vérifient.
- `SEC_JOURNAL` dans un dossier temporaire : la suite n'écrit pas dans
  `journaux/` du dépôt.

Les tests qui vérifient explicitement TLS ou la limitation de débit sont dans
`securite/tests/`, avec leur propre configuration.
"""

import os
import tempfile
from pathlib import Path

_TEMPORAIRE = Path(tempfile.gettempdir()) / "interop-tests-h2"
_TEMPORAIRE.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("SEC_MODE", "local")
os.environ.setdefault("SEC_TLS_REQUIS", "0")
os.environ.setdefault("SEC_DEBIT_PAR_MINUTE", "1000000")
os.environ.setdefault("SEC_ECHECS_MAX", "1000000")
os.environ.setdefault("SEC_JOURNAL", str(_TEMPORAIRE / "securite-h2.jsonl"))
os.environ.setdefault("SEC_SEL_AUDIT", "sel-de-test-sans-valeur-reelle")
# Registre volontairement absent : les tests utilisent le jeton partagé, posé
# par chaque test avec monkeypatch.setenv("H2_TOKEN", ...).
os.environ.setdefault("SEC_REGISTRE", str(_TEMPORAIRE / "registre-absent.json"))
