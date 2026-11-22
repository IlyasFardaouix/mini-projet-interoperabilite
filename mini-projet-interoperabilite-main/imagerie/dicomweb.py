"""DICOMweb : multipart, entrepots d'images et client de la passerelle distante.

DICOMweb (DICOM PS3.18) transporte les instances dans des corps
`multipart/related; type="application/dicom"` :

- STOW-RS  POST /studies                 depot d'instances ;
- WADO-RS  GET  /studies/{uid}           recuperation d'une etude ;
- QIDO-RS  GET  /studies?StudyInstanceUID=...   recherche.

Deux entrepots, meme interface :
- `EntrepotOrthanc` : le PACS Orthanc du service (plugin DICOMweb), joint en
  local avec un compte dedie ;
- `EntrepotMemoire` : tests et demonstration sans PACS.
"""

from __future__ import annotations

import os
import re
import secrets
import threading
from typing import Optional

TYPE_DICOM = "application/dicom"
ACCEPTE_MULTIPART = f'multipart/related; type="{TYPE_DICOM}"'


class ErreurPacs(RuntimeError):
    """PACS injoignable ou reponse inattendue (HTTP 502/503 cote API)."""


# ---------------------------------------------------------------------------
# Multipart
# ---------------------------------------------------------------------------
def encoder_multipart(parties: list) -> tuple:
    """(corps, content-type) d'un multipart/related d'instances DICOM."""
    frontiere = "dicom-" + secrets.token_hex(12)
    morceaux = []
    for octets in parties:
        morceaux.append(f"--{frontiere}\r\nContent-Type: {TYPE_DICOM}\r\n\r\n".encode("ascii"))
        morceaux.append(octets)
        morceaux.append(b"\r\n")
    morceaux.append(f"--{frontiere}--\r\n".encode("ascii"))
    return b"".join(morceaux), f'multipart/related; type="{TYPE_DICOM}"; boundary={frontiere}'


def decoder_multipart(corps: bytes, content_type: str) -> list:
    """Parties binaires d'un multipart/related (l'en-tete de chaque partie est ignore)."""
    trouve = re.search(r'boundary="?([^";]+)"?', content_type or "", re.IGNORECASE)
    if not trouve:
        raise ErreurPacs("reponse multipart sans frontiere (boundary)")
    separateur = b"--" + trouve.group(1).encode("ascii")
    parties = []
    for morceau in corps.split(separateur)[1:]:
        if morceau.startswith(b"--"):
            break                                              # frontiere de fin
        entetes, _, contenu = morceau.partition(b"\r\n\r\n")
        if contenu.endswith(b"\r\n"):
            contenu = contenu[:-2]
        parties.append(contenu)
    return parties


# ---------------------------------------------------------------------------
# Entrepots
# ---------------------------------------------------------------------------
class EntrepotMemoire:
    def __init__(self):
        self._etudes: dict = {}
        self._verrou = threading.Lock()

    def stocker(self, instances: list) -> int:
        from .dicom import depuis_octets

        with self._verrou:
            for octets in instances:
                ds = depuis_octets(octets)
                etude = self._etudes.setdefault(str(ds.StudyInstanceUID), {})
                etude[str(ds.SOPInstanceUID)] = octets      # meme SOP : remplace, pas de doublon
        return len(instances)

    def etude(self, study_uid: str) -> list:
        with self._verrou:
            return list(self._etudes.get(study_uid, {}).values())

    def existe(self, study_uid: str) -> bool:
        return bool(self.etude(study_uid))


class EntrepotOrthanc:
    """PACS Orthanc via son plugin DICOMweb (http://127.0.0.1:8042/dicom-web)."""

    def __init__(self, base_url: str, utilisateur: str = "", mot_de_passe: str = "", *, client=None):
        import httpx

        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(
            auth=(utilisateur, mot_de_passe) if utilisateur else None,
            timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False)

    def _appel(self, methode: str, chemin: str, **options):
        import httpx

        try:
            return self.client.request(methode, self.base_url + chemin, **options)
        except httpx.HTTPError as exc:
            raise ErreurPacs(f"PACS injoignable ({exc.__class__.__name__})") from exc

    def stocker(self, instances: list) -> int:
        corps, type_contenu = encoder_multipart(instances)
        r = self._appel("POST", "/studies", content=corps,
                        headers={"Content-Type": type_contenu, "Accept": "application/dicom+json"})
        if r.status_code not in (200, 202):
            raise ErreurPacs(f"depot refuse par le PACS (HTTP {r.status_code})")
        return len(instances)

    def etude(self, study_uid: str) -> list:
        r = self._appel("GET", f"/studies/{study_uid}", headers={"Accept": ACCEPTE_MULTIPART})
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            raise ErreurPacs(f"lecture refusee par le PACS (HTTP {r.status_code})")
        return decoder_multipart(r.content, r.headers.get("content-type", ""))

    def existe(self, study_uid: str) -> bool:
        r = self._appel("GET", "/studies", params={"StudyInstanceUID": study_uid},
                        headers={"Accept": "application/dicom+json"})
        if r.status_code == 204:
            return False
        if r.status_code != 200:
            raise ErreurPacs(f"recherche refusee par le PACS (HTTP {r.status_code})")
        return bool(r.json())


def entrepot_depuis_env(prefixe: str):
    """Entrepot configure par <PREFIXE>_ORTHANC_URL / _UTILISATEUR / _MOT_DE_PASSE.
    None si aucun PACS n'est configure (les routes d'imagerie repondent alors 503)."""
    url = (os.getenv(prefixe + "_ORTHANC_URL") or "").strip()
    if not url:
        return None
    return EntrepotOrthanc(url, (os.getenv(prefixe + "_ORTHANC_UTILISATEUR") or "").strip(),
                           (os.getenv(prefixe + "_ORTHANC_MOT_DE_PASSE") or "").strip())


# ---------------------------------------------------------------------------
# Passerelle de l'autre hopital
# ---------------------------------------------------------------------------
class ErreurDistante(RuntimeError):
    def __init__(self, http: Optional[int], message: str):
        super().__init__(message)
        self.http = http


def recuperer_etude_distante(client, base_dicomweb: str, study_uid: str) -> list:
    """WADO-RS sur la passerelle de l'autre hopital, avec le client securise
    (TLS verifie, jeton, pas de redirection). Renvoie les octets des instances."""
    import httpx

    try:
        r = client.get(base_dicomweb.rstrip("/") + f"/studies/{study_uid}",
                       headers={"Accept": ACCEPTE_MULTIPART})
    except httpx.HTTPError as exc:
        raise ErreurDistante(None, f"passerelle injoignable ({exc.__class__.__name__})") from exc
    if r.status_code != 200:
        raise ErreurDistante(r.status_code, f"HTTP {r.status_code}")
    return decoder_multipart(r.content, r.headers.get("content-type", ""))
