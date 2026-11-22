"""Racine du depot dans le chemin d'import, reglages de securite de test."""

import os
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

_TEMPORAIRE = Path(tempfile.gettempdir()) / "interop-tests-imagerie"
_TEMPORAIRE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("SEC_MODE", "local")
os.environ.setdefault("SEC_TLS_REQUIS", "0")
os.environ.setdefault("SEC_JOURNAL", str(_TEMPORAIRE / "securite-imagerie.jsonl"))
os.environ.setdefault("SEC_REGISTRE", str(_TEMPORAIRE / "registre-absent.json"))
