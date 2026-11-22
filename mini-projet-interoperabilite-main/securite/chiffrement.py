"""Chiffrement des donnees au repos (AES-256-GCM) et index aveugles.

Usage : la base MongoDB de la clinique et la file d'envoi SQLite stockent des
dossiers de sante complets. Un vol du disque, d'une sauvegarde ou un acces
direct a la base (sans passer par l'API) livrerait tout en clair. Ici :

- chaque dossier est chiffre par l'application avant d'etre ecrit ;
- la cle n'est PAS dans la base : variable d'environnement (fichier .env du
  poste, hors Git), donc une copie de la base seule est illisible ;
- AES-256-GCM est authentifie : une modification du contenu chiffre est
  detectee. Le « contexte » (identifiant du patient) est lie au chiffre : un
  dossier recopie sur un autre patient ne se dechiffre pas ;
- les recherches (CIN, identifiants externes) passent par des index aveugles :
  HMAC-SHA256 de la valeur avec une sous-cle dediee. On retrouve un patient par
  son CIN sans que le CIN figure en clair dans la base.

Format d'une valeur chiffree : « <id de cle>:<base64url(nonce 12 octets + chiffre + tag)> ».
L'identifiant de cle permet une rotation : les anciennes cles restent lisibles,
la cle courante sert a toute nouvelle ecriture.

Cles : variable d'environnement « id:cle_base64url[,id:cle,...] », la premiere
etant la courante. Generer une cle : `py securite/chiffrement.py`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class ErreurChiffrement(ValueError):
    """Cle absente, invalide, ou donnee chiffree alteree."""


def _b64e(octets: bytes) -> str:
    return base64.urlsafe_b64encode(octets).decode("ascii").rstrip("=")


def _b64d(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def _sous_cle(cle: bytes, usage: str) -> bytes:
    """Une sous-cle par usage (chiffrement, index) : HKDF-SHA256."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=("interop-sante/" + usage).encode("ascii")).derive(cle)


def nouvelle_cle(identifiant: str = "v1") -> str:
    return identifiant + ":" + _b64e(secrets.token_bytes(32))


class Chiffreur:
    def __init__(self, cles: dict, courante: str):
        if courante not in cles:
            raise ErreurChiffrement("cle courante absente du trousseau")
        for ident, cle in cles.items():
            if len(cle) != 32:
                raise ErreurChiffrement(f"la cle {ident} doit faire 32 octets (AES-256)")
            if ":" in ident or not ident:
                raise ErreurChiffrement("identifiant de cle invalide")
        self._chiffrement = {i: AESGCM(_sous_cle(c, "chiffrement")) for i, c in cles.items()}
        # Index calcules avec la cle courante : apres une rotation, l'outil de
        # migration (hopital2/chiffrer_mongo.py) rechiffre et recalcule tous les index.
        self._index = _sous_cle(cles[courante], "index")
        self.courante = courante

    @classmethod
    def depuis_texte(cls, texte: str) -> "Chiffreur":
        cles, courante = {}, None
        for morceau in (texte or "").split(","):
            morceau = morceau.strip()
            if not morceau:
                continue
            ident, sep, valeur = morceau.partition(":")
            if not sep:
                raise ErreurChiffrement("format attendu : id:cle_base64url")
            try:
                cles[ident] = _b64d(valeur)
            except (ValueError, TypeError) as exc:
                raise ErreurChiffrement(f"cle {ident} illisible") from exc
            courante = courante or ident
        if not cles:
            raise ErreurChiffrement("aucune cle")
        return cls(cles, courante)

    @classmethod
    def depuis_env(cls, variable: str) -> Optional["Chiffreur"]:
        """None si la variable est vide ; erreur si elle est mal formee (fail-closed)."""
        texte = (os.getenv(variable) or "").strip()
        return cls.depuis_texte(texte) if texte else None

    # -- octets ------------------------------------------------------------
    def chiffrer(self, donnees: bytes, contexte: str) -> str:
        nonce = secrets.token_bytes(12)
        chiffre = self._chiffrement[self.courante].encrypt(nonce, donnees, contexte.encode("utf-8"))
        return self.courante + ":" + _b64e(nonce + chiffre)

    def dechiffrer(self, valeur: str, contexte: str) -> bytes:
        ident, sep, corps = str(valeur or "").partition(":")
        if not sep or ident not in self._chiffrement:
            raise ErreurChiffrement("cle inconnue pour cette donnee")
        try:
            brut = _b64d(corps)
            return self._chiffrement[ident].decrypt(brut[:12], brut[12:], contexte.encode("utf-8"))
        except (InvalidTag, ValueError) as exc:
            raise ErreurChiffrement("donnee chiffree alteree ou contexte different") from exc

    def a_rechiffrer(self, valeur: str) -> bool:
        """Vrai si la valeur a ete chiffree avec une ancienne cle."""
        return not str(valeur or "").startswith(self.courante + ":")

    # -- JSON --------------------------------------------------------------
    def chiffrer_json(self, objet, contexte: str) -> str:
        return self.chiffrer(json.dumps(objet, ensure_ascii=False, separators=(",", ":"),
                                        default=str).encode("utf-8"), contexte)

    def dechiffrer_json(self, valeur: str, contexte: str):
        return json.loads(self.dechiffrer(valeur, contexte))

    def chiffrer_texte(self, texte: str, contexte: str) -> str:
        return self.chiffrer(texte.encode("utf-8"), contexte)

    def dechiffrer_texte(self, valeur: str, contexte: str) -> str:
        return self.dechiffrer(valeur, contexte).decode("utf-8")

    # -- index aveugles ----------------------------------------------------
    def index(self, *morceaux: str) -> str:
        """Empreinte deterministe pour la recherche : meme valeur -> meme index,
        irreversible sans la cle (pas d'attaque par dictionnaire sur les CIN)."""
        message = "\x1f".join(str(m) for m in morceaux).encode("utf-8")
        return hmac.new(self._index, message, hashlib.sha256).hexdigest()[:32]


if __name__ == "__main__":
    print("Nouvelle cle (a placer dans le .env du poste, jamais dans Git) :")
    print(nouvelle_cle())
