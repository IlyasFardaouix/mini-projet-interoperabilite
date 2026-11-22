"""Couche de securite commune aux deux API du projet d'interoperabilite.

Partie « Securite » du mini-projet : jetons et droits d'acces, HTTPS/TLS,
journal d'audit, durcissement HTTP. Les deux services la branchent de la meme
facon, pour que les regles soient identiques des deux cotes de l'echange.

    # dans hopital1/app.py ou hopital2/api_h2.py, juste apres app = FastAPI(...)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from securite import installer_securite, exiger_portee

    installer_securite(app, service="H1")

    @app.get("/api/patients/{ipp}/bundle", dependencies=[Depends(exiger_portee("export"))])
    def exporter(...):
        ...

Tout est pilote par des variables d'environnement (prefixe `SEC_`), decrites
dans `.env.example` et dans `docs/securite/politique-securite.md`. Aucun secret
n'est stocke dans le depot.
"""

from __future__ import annotations

from .audit import JournalSecurite, verifier_chaine
from .config import PORTEES_CONNUES, Configuration, charger
from .intergiciels import (
    EtatSecurite,
    MiddlewareSecurite,
    exiger_portee,
    installer_securite,
    lire_json_securise,
    operation_outcome,
    tracer,
)
from .jetons import (
    AccesRefuse,
    Appelant,
    Verificateur,
    creer_jwt,
    empreinte_complete,
    empreinte_courte,
    verifier_jwt,
)

__version__ = "1.0.0"

__all__ = [
    "AccesRefuse",
    "Appelant",
    "Configuration",
    "EtatSecurite",
    "JournalSecurite",
    "MiddlewareSecurite",
    "PORTEES_CONNUES",
    "Verificateur",
    "charger",
    "creer_jwt",
    "empreinte_complete",
    "empreinte_courte",
    "exiger_portee",
    "installer_securite",
    "lire_json_securise",
    "operation_outcome",
    "tracer",
    "verifier_chaine",
    "verifier_jwt",
]


def __getattr__(nom):
    """`client_securise` est charge a la demande : il a besoin de httpx."""
    if nom in {"client_securise", "verifier_url"}:
        from . import client

        return getattr(client, nom)
    raise AttributeError(nom)
