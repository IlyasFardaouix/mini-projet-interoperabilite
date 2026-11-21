"""Configuration de la couche de securite, lue uniquement dans l'environnement.

Aucun secret n'est ecrit dans ce fichier : tout vient de variables
d'environnement, elles-memes alimentees par un fichier .env hors depot Git.

Regle de base : *fail-closed*. Si la configuration d'authentification est
absente, les routes protegees repondent 503 et refusent le trafic ; elles ne
basculent jamais en « mode ouvert ».
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Portees (scopes) reconnues. Une portee = un droit precis sur une route.
# Le suffixe est en minuscules ; le prefixe est le service qui expose la route.
PORTEES_CONNUES = {
    "export",            # GET  /api/patients/{id}/bundle  : envoyer un dossier
    "simulation",        # POST /api/retours/simulation    : essai sans ecriture
    "import",            # POST /api/retours               : ecriture definitive
    "patient.lire",      # GET  /Patient/{id}
    "patient.creer",     # POST /Patient
    "patient.chercher",  # GET  /Patient?identifier=...
    "audit",             # lecture du journal d'acces (inclure_audit=true)
    "annuaire",          # annuaire complet de l'etablissement (inclure_catalogue=true)
    "consentement.lire",   # GET  /api/patients/{id}/consentement : etat et historique
    "consentement.gerer",  # POST /api/patients/{id}/consentement[/retrait] : recueil, retrait
}

# Variable d'environnement historique portant le jeton partage, par service.
JETON_HISTORIQUE = {"H1": "H1_API_TOKEN", "H2": "H2_TOKEN"}

DEFAUTS = {
    "SEC_MODE": "strict",
    "SEC_TAILLE_MAX_CORPS": "5000000",      # 5 Mo : un Bundle de dossier reste tres en dessous
    "SEC_DEBIT_PAR_MINUTE": "120",
    "SEC_ECHECS_MAX": "5",
    "SEC_VERROU_SECONDES": "300",
    "SEC_JWT_ISS": "interop-sante",
    "SEC_ROTATION_JOURS": "90",
}


def _entier(nom: str) -> int:
    brut = (os.getenv(nom) or DEFAUTS.get(nom) or "0").strip()
    try:
        return int(brut)
    except ValueError:
        return int(DEFAUTS.get(nom, "0"))


def _booleen(nom: str, defaut: bool) -> bool:
    brut = (os.getenv(nom) or "").strip().lower()
    if brut in {"1", "true", "oui", "yes"}:
        return True
    if brut in {"0", "false", "non", "no"}:
        return False
    return defaut


@dataclass(frozen=True)
class Configuration:
    """Instantane de la configuration de securite d'un service."""

    service: str                       # "H1" ou "H2"
    mode: str                          # "strict" (defaut) ou "local"
    registre: Path                     # registre des jetons (hors depot Git)
    journal: Path                      # journal de securite, format JSONL
    sel_audit: str                     # cle HMAC de pseudonymisation du journal
    jwt_secret: str                    # secret HS256 ; vide = JWT desactive
    jwt_iss: str
    jwt_aud: str
    tls_requis: bool
    ca: str                            # bundle de confiance pour les appels sortants
    taille_max_corps: int
    debit_par_minute: int
    echecs_max: int
    verrou_secondes: int
    rotation_jours: int
    # Nom de la variable d'environnement portant le jeton partage historique.
    # On stocke le NOM et pas la valeur : le jeton est relu a chaque requete,
    # ce qui permet de le changer sans redemarrer le service. Le reste de la
    # configuration, lui, est fige au demarrage : les reglages de transport ne
    # doivent pas pouvoir changer en cours de route.
    variable_jeton: str = ""

    @property
    def jeton_historique(self) -> str:
        if not self.variable_jeton:
            return ""
        return (os.getenv(self.variable_jeton) or "").strip()

    @property
    def strict(self) -> bool:
        return self.mode == "strict"

    def portee(self, suffixe: str) -> str:
        """« export » -> « h2:export » pour le service courant."""
        return f"{self.service.lower()}:{suffixe}"


def charger(service: str) -> Configuration:
    """Construit la configuration du service depuis l'environnement."""
    service = service.upper().strip()
    if service not in JETON_HISTORIQUE:
        raise ValueError(f"Service inconnu : {service!r} (attendu H1 ou H2).")

    mode = (os.getenv("SEC_MODE") or DEFAUTS["SEC_MODE"]).strip().lower()
    if mode not in {"strict", "local"}:
        mode = "strict"

    registre = Path(os.getenv("SEC_REGISTRE") or RACINE / "securite" / "registre_jetons.json")
    journal = Path(os.getenv("SEC_JOURNAL") or RACINE / "journaux" / f"securite-{service.lower()}.jsonl")

    return Configuration(
        service=service,
        mode=mode,
        registre=registre,
        journal=journal,
        # Sans sel configure, on derive une valeur stable par service : le journal
        # reste pseudonymise, mais non correlable entre deux postes.
        sel_audit=(os.getenv("SEC_SEL_AUDIT") or f"sel-local-{service.lower()}").strip(),
        jwt_secret=(os.getenv("SEC_JWT_SECRET") or "").strip(),
        jwt_iss=(os.getenv("SEC_JWT_ISS") or DEFAUTS["SEC_JWT_ISS"]).strip(),
        jwt_aud=(os.getenv("SEC_JWT_AUD") or service).strip(),
        tls_requis=_booleen("SEC_TLS_REQUIS", defaut=(mode == "strict")),
        ca=(os.getenv("SEC_CA") or "").strip(),
        taille_max_corps=_entier("SEC_TAILLE_MAX_CORPS"),
        debit_par_minute=_entier("SEC_DEBIT_PAR_MINUTE"),
        echecs_max=_entier("SEC_ECHECS_MAX"),
        verrou_secondes=_entier("SEC_VERROU_SECONDES"),
        rotation_jours=_entier("SEC_ROTATION_JOURS"),
        variable_jeton=JETON_HISTORIQUE[service],
    )
