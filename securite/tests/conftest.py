"""Fixtures communes aux tests de la couche de securite.

Trois principes tenus par ce fichier :

* aucun test n'ecrit dans le depot : registre, journal et certificats vont tous
  dans `tmp_path` ;
* aucun test ne depend du poste : toutes les variables SEC_* (et les jetons
  historiques) sont effacees avant chaque test ;
* `Configuration` est gelee (frozen=True) : chaque variante se construit en
  posant les variables d'environnement avec `monkeypatch`, puis en appelant
  `charger()`. Jamais par mutation d'un objet existant.
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]          # racine du projet
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from securite import (                                                  # noqa: E402
    charger,
    exiger_portee,
    installer_securite,
    lire_json_securise,
    tracer,
)
from securite.jetons import empreinte_complete                          # noqa: E402

# Variables lues par la couche de securite. Toutes effacees avant chaque test.
VARIABLES_SECURITE = (
    "SEC_MODE", "SEC_REGISTRE", "SEC_JOURNAL", "SEC_SEL_AUDIT", "SEC_JWT_SECRET",
    "SEC_JWT_ISS", "SEC_JWT_AUD", "SEC_TLS_REQUIS", "SEC_TLS_VERIF", "SEC_CA",
    "SEC_TAILLE_MAX_CORPS", "SEC_DEBIT_PAR_MINUTE", "SEC_ECHECS_MAX",
    "SEC_VERROU_SECONDES", "SEC_ROTATION_JOURS", "SEC_ANONYMISER_IP",
    "SEC_PROXY_DE_CONFIANCE", "H1_API_TOKEN", "H2_TOKEN",
    "SEC_SESSION_SECRET", "SEC_UTILISATEURS", "SEC_SESSION_DUREE", "SEC_SESSION_RENOUVELLEMENT",
)

# Jetons de test : aucune valeur reelle, uniquement des chaines de laboratoire.
JETON_REGISTRE = "jeton-registre-de-test-0123456789abcdefghij"
JETON_PARTAGE = "jeton-partage-de-test-0123456789abcdefghij"
JETON_INCONNU = "jeton-jamais-declare-0123456789abcdefghij"
CLIENT_REGISTRE = "h1-chu-settat"
PORTEES_REGISTRE = "h2:export h2:import"

# Limite de corps appliquee par la route de test qui lit son JSON elle-meme.
LIMITE_ROUTE = 64

EN_TETE = {"Authorization": "Bearer " + JETON_REGISTRE}


# ---------------------------------------------------------------------------
# Environnement et dossiers
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch):
    """Isole chaque test des reglages SEC_* eventuels du poste."""
    for nom in VARIABLES_SECURITE:
        monkeypatch.delenv(nom, raising=False)


@pytest.fixture
def dossier(tmp_path):
    """Dossier de travail temporaire : registre, journal, certificats."""
    chemin = tmp_path / "securite"
    chemin.mkdir()
    return chemin


@pytest.fixture
def chemin_registre(dossier):
    return dossier / "registre_jetons.json"


@pytest.fixture
def chemin_journal(dossier):
    return dossier / "journal-securite.jsonl"


# ---------------------------------------------------------------------------
# Registre de jetons
# ---------------------------------------------------------------------------
def entree_registre(jeton=JETON_REGISTRE, **surcharges):
    """Entree de registre valide pour `jeton`, modifiable champ par champ."""
    entree = {
        "id": CLIENT_REGISTRE,
        "empreinte": "sha256:" + empreinte_complete(jeton),
        "portees": PORTEES_REGISTRE,
        "actif": True,
    }
    entree.update(surcharges)
    return entree


def ecrire_registre(chemin, *entrees):
    """Ecrit un registre JSON et renvoie son chemin."""
    Path(chemin).write_text(json.dumps({"clients": list(entrees)}, indent=1),
                            encoding="utf-8")
    return Path(chemin)


@pytest.fixture
def registre(chemin_registre):
    """Registre temporaire contenant une entree valide pour JETON_REGISTRE."""
    return ecrire_registre(chemin_registre, entree_registre())


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@pytest.fixture
def reglages(monkeypatch, chemin_registre, chemin_journal):
    """Fabrique une Configuration : pose les SEC_* puis appelle charger().

        conf = reglages()                           # H2, mode local, sans TLS
        conf = reglages(SEC_TLS_REQUIS="1")         # une variante
        conf = reglages(service="H1", H1_API_TOKEN="...")
    """
    def construire(service="H2", **variables):
        base = {
            "SEC_MODE": "local",
            "SEC_TLS_REQUIS": "0",
            "SEC_REGISTRE": str(chemin_registre),
            "SEC_JOURNAL": str(chemin_journal),
            "SEC_SEL_AUDIT": "sel-de-test",
            "SEC_TAILLE_MAX_CORPS": "4096",
            "SEC_DEBIT_PAR_MINUTE": "120",
            "SEC_ECHECS_MAX": "3",
            "SEC_VERROU_SECONDES": "300",
        }
        base.update(variables)
        for nom, valeur in base.items():
            if valeur is None:
                monkeypatch.delenv(nom, raising=False)
            else:
                monkeypatch.setenv(nom, str(valeur))
        return charger(service)
    return construire


@pytest.fixture
def conf(reglages):
    """Configuration de test par defaut, pour le service H2."""
    return reglages()


# ---------------------------------------------------------------------------
# Application FastAPI de test
# ---------------------------------------------------------------------------
def poser_routes(app):
    """Routes de test : deux publiques, trois protegees par exiger_portee."""
    from fastapi import Depends, Request
    from fastapi.responses import JSONResponse

    @app.get("/health")
    def sante():
        return {"etat": "ok"}

    @app.get("/metadata")
    def metadonnees():
        return {"resourceType": "CapabilityStatement"}

    @app.get("/api/patients/{ipp}/bundle",
             dependencies=[Depends(exiger_portee("export"))])
    def exporter(ipp: str):
        return {"resourceType": "Bundle", "id": ipp}

    @app.post("/api/retours")
    async def importer(requete: Request, appelant=Depends(exiger_portee("import"))):
        contenu = await lire_json_securise(requete, maximum=LIMITE_ROUTE)
        tracer(requete, echange_id="ECH-TEST-0001")
        return {"client": appelant.client, "recu": contenu}

    @app.post("/api/retours/simulation",
              dependencies=[Depends(exiger_portee("simulation"))])
    def simuler():
        return {"simulation": True}

    @app.get("/api/entetes-techniques")
    def entetes_techniques():
        # Imite un serveur bavard : l'intergiciel doit retirer ces deux en-tetes
        # et conserver les autres.
        return JSONResponse({"ok": True},
                            headers={"server": "uvicorn/0.30",
                                     "x-powered-by": "FastAPI",
                                     "X-Trace-Test": "a-garder"})
    return app


@pytest.fixture
def application(reglages, registre):
    """Fabrique une application FastAPI equipee de la couche de securite.

    L'etat de securite reste accessible par app.state.securite.
    """
    from fastapi import FastAPI

    def construire(service="H2", **variables):
        configuration = reglages(service=service, **variables)
        app = FastAPI()
        installer_securite(app, service=configuration.service, conf=configuration)
        return poser_routes(app)
    return construire


@pytest.fixture
def client(application):
    """Fabrique un TestClient sur l'application de test.

        c = client()                                   # requetes en http://
        c = client(base_url="https://testserver")       # requetes en https://
    """
    from fastapi.testclient import TestClient

    def construire(base_url="http://testserver", **variables):
        return TestClient(application(**variables), base_url=base_url)
    return construire


# ---------------------------------------------------------------------------
# Lecture du journal ecrit pendant un test
# ---------------------------------------------------------------------------
def lignes_journal(chemin, evenement=None):
    """Lignes JSON du journal, filtrees sur un type d'evenement."""
    chemin = Path(chemin)
    if not chemin.exists():
        return []
    lues = [json.loads(ligne)
            for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()]
    if evenement is None:
        return lues
    return [ligne for ligne in lues if ligne.get("evenement") == evenement]
