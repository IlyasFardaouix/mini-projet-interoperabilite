"""Client HTTP durci pour les appels d'une API vers l'autre.

`hopital2/client_envoi.py` attend un `httpx.Client` deja configure avec son
`base_url` et son jeton. C'est ici qu'on le construit, pour que les quatre
reglages qui comptent soient au meme endroit et impossibles a oublier :

1. **Verification du certificat du serveur.** Avec une autorite de test, il faut
   passer son certificat racine (`SEC_CA`). Desactiver la verification demande
   un geste explicite (`SEC_TLS_VERIF=0`) qui n'est accepte qu'en mode local :
   sinon n'importe qui sur le reseau peut se faire passer pour l'autre hopital.
2. **Delais d'attente.** Sans delai, un serveur qui ne repond plus bloque le
   programme d'envoi indefiniment. Le contrat d'echange prevoit des reprises :
   elles ne servent a rien si l'appel ne rend jamais la main.
3. **Pas de suivi des redirections.** httpx rejoue les en-tetes sur la nouvelle
   adresse : une redirection vers un serveur tiers lui livrerait le jeton.
4. **Jeton lu dans l'environnement**, jamais ecrit en dur ni journalise.
"""

from __future__ import annotations

import os
from typing import Optional

from .config import Configuration

# Delais en secondes. `read` est le plus long : un import Oracle peut prendre
# quelques secondes. Il reste tres inferieur au premier delai de reprise (60 s).
DELAI_CONNEXION = 5.0
DELAI_LECTURE = 30.0
DELAI_ECRITURE = 30.0
DELAI_POOL = 5.0

ENTETES = {
    "Accept": "application/fhir+json, application/json",
    "User-Agent": "interop-sante/1.0",
}


class ConfigurationTlsRefusee(RuntimeError):
    """Reglage TLS juge trop dangereux pour etre applique."""


def verifier_url(url: str, *, tls_requis: bool) -> str:
    """Refuse une adresse en clair quand TLS est exige."""
    adresse = (url or "").strip()
    if not adresse:
        raise ValueError("adresse du service cible absente")
    if tls_requis and adresse.startswith("http://"):
        hote = adresse.removeprefix("http://").split("/")[0].split(":")[0]
        if hote not in {"localhost", "127.0.0.1", "::1"}:
            raise ConfigurationTlsRefusee(
                "Adresse en clair refusee : " + adresse + ". Utiliser https:// ou "
                "SEC_TLS_REQUIS=0 sur un poste de test isole.")
    return adresse.rstrip("/")


def _verification(conf: Optional[Configuration], ca: Optional[str]):
    """Valeur du parametre `verify` de httpx."""
    autorite = ca or (conf.ca if conf else "") or (os.getenv("SEC_CA") or "").strip()
    desactivee = (os.getenv("SEC_TLS_VERIF") or "").strip() in {"0", "false", "non"}
    if desactivee:
        mode = (conf.mode if conf else os.getenv("SEC_MODE") or "strict").lower()
        if mode != "local":
            raise ConfigurationTlsRefusee(
                "SEC_TLS_VERIF=0 n'est accepte qu'avec SEC_MODE=local. En mode strict, "
                "fournir le certificat racine dans SEC_CA.")
        return False
    if autorite:
        return autorite
    return True                                      # magasin de confiance du systeme


def client_securise(base_url: str, *, jeton: Optional[str] = None,
                    conf: Optional[Configuration] = None,
                    ca: Optional[str] = None,
                    variable_jeton: Optional[str] = None,
                    tls_requis: Optional[bool] = None):
    """Construit un `httpx.Client` pret a appeler l'autre hopital.

    `variable_jeton` : nom de la variable d'environnement portant le jeton
    (par exemple `H1_API_TOKEN` quand H2 appelle H1).
    """
    import httpx

    if tls_requis is None:
        tls_requis = conf.tls_requis if conf else (
            (os.getenv("SEC_TLS_REQUIS") or "1").strip() not in {"0", "false", "non"})

    adresse = verifier_url(base_url, tls_requis=bool(tls_requis))
    secret = jeton or (os.getenv(variable_jeton) if variable_jeton else None) or ""
    secret = secret.strip()
    if not secret:
        raise ValueError(
            "aucun jeton fourni : renseigner " + (variable_jeton or "le parametre jeton")
            + " avant d'appeler " + adresse)

    entetes = dict(ENTETES)
    entetes["Authorization"] = "Bearer " + secret

    # Pas de transport httpx personnalise : il remplacerait silencieusement le
    # reglage `verify` ci-dessous. Les reprises sont gerees au niveau applicatif,
    # par la file d'attente de hopital2/client_envoi.py.
    return httpx.Client(
        base_url=adresse,
        headers=entetes,
        verify=_verification(conf, ca),
        timeout=httpx.Timeout(connect=DELAI_CONNEXION, read=DELAI_LECTURE,
                              write=DELAI_ECRITURE, pool=DELAI_POOL),
        # Une redirection rejouerait l'en-tete Authorization sur l'adresse cible.
        follow_redirects=False,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
