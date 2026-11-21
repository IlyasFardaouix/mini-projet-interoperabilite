"""Journal de securite : qui a appele quoi, quand, avec quel resultat.

Le journal metier existe deja de chaque cote (table `journal_echange` cote H1,
champ `_audit_log` du document Mongo cote H2). Il trace les echanges reussis,
pas les tentatives d'acces. Ce module ajoute la trace d'acces exigee par la
loi 09-08 (et par le RGPD pour les donnees de sante) : chaque requete, y compris
les refus 401 / 403 / 429, laisse une ligne.

Trois choix de conception :

1. **Format JSONL**, une ligne JSON par evenement : lisible, greppable,
   analysable sans outil, et toujours ajoute en fin de fichier.
2. **Chainage par empreinte** : chaque ligne porte l'empreinte SHA-256 de la
   precedente (`prec`). Supprimer ou modifier une ligne casse la chaine, ce qui
   se detecte avec `verifier_chaine()`. Ce n'est pas une signature : cela ne
   protege pas contre quelqu'un qui reecrit tout le fichier, mais cela rend une
   retouche ponctuelle visible.
3. **Pas de donnee de sante dans le journal.** Les identifiants de patient sont
   remplaces par un pseudonyme HMAC stable (meme patient = meme pseudonyme, sans
   possibilite de remonter a l'identifiant sans la cle). Les valeurs des
   parametres de recherche, qui peuvent contenir un CIN, sont masquees.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Parametres de requete dont la VALEUR est une donnee personnelle : on garde le
# nom du parametre (utile pour l'analyse) et on masque la valeur.
PARAMETRES_SENSIBLES = {"identifier", "cin", "ipp", "name", "family", "given",
                        "birthdate", "patient", "subject", "telecom", "email"}

# En-tetes qui ne doivent jamais etre journalises.
ENTETES_INTERDITES = {"authorization", "proxy-authorization", "cookie", "set-cookie",
                      "x-api-key", "x-auth-token"}

# Segment de chemin qui ressemble a un identifiant de ressource.
_SEGMENT_IDENTIFIANT = re.compile(
    r"^(?:P\d-\d+|[A-Z]{1,2}\d{4,}|\d{4,}|[0-9a-fA-F-]{16,}|[A-Z]\d+-\d+)$")

TAILLE_ROTATION = 5 * 1024 * 1024          # 5 Mo : au-dela, le fichier est archive


def horodatage() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _canonique(entree: dict) -> bytes:
    return json.dumps(entree, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def empreinte_entree(entree: dict) -> str:
    return hashlib.sha256(_canonique(entree)).hexdigest()


class JournalSecurite:
    """Ecrit le journal d'acces en JSONL chaine, de maniere thread-safe."""

    def __init__(self, chemin: Path, *, sel: str, service: str,
                 anonymiser_ip: Optional[bool] = None,
                 taille_rotation: int = TAILLE_ROTATION):
        self.chemin = Path(chemin)
        self.service = service
        self._sel = (sel or "sel-absent").encode("utf-8")
        self._mutex = threading.Lock()
        self._derniere = None
        self.taille_rotation = taille_rotation
        if anonymiser_ip is None:
            anonymiser_ip = (os.getenv("SEC_ANONYMISER_IP") or "").strip() in {"1", "true", "oui"}
        self.anonymiser_ip = anonymiser_ip
        self.erreurs_ecriture = 0

    # -- pseudonymisation --------------------------------------------------
    def pseudonyme(self, valeur: Optional[str]) -> Optional[str]:
        """Identifiant -> pseudonyme stable, non reversible sans la cle."""
        if not valeur:
            return None
        court = hmac.new(self._sel, str(valeur).encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return "p:" + court

    def ip(self, adresse: Optional[str]) -> Optional[str]:
        if not adresse:
            return None
        if not self.anonymiser_ip:
            return adresse
        if ":" in adresse:                                  # IPv6 : on garde le prefixe /48
            morceaux = adresse.split(":")
            return ":".join(morceaux[:3]) + "::/48"
        morceaux = adresse.split(".")
        if len(morceaux) == 4:
            return ".".join(morceaux[:3]) + ".0/24"
        return adresse

    # -- normalisation du chemin ------------------------------------------
    def normaliser_chemin(self, chemin: str) -> tuple:
        """`/api/patients/P2-0051/bundle` -> (`/api/patients/{id}/bundle`, pseudonyme).

        Le gabarit sert aux statistiques, le pseudonyme a la tracabilite.
        """
        identifiants = []
        segments = []
        for segment in (chemin or "/").split("/"):
            if segment and _SEGMENT_IDENTIFIANT.match(segment):
                identifiants.append(segment)
                segments.append("{id}")
            else:
                segments.append(segment)
        gabarit = "/".join(segments) or "/"
        return gabarit, self.pseudonyme(identifiants[0]) if identifiants else None

    def masquer_parametres(self, requete: str) -> dict:
        """Garde les noms des parametres, masque les valeurs sensibles."""
        resultat = {}
        for couple in (requete or "").split("&"):
            if not couple:
                continue
            nom, _, valeur = couple.partition("=")
            nom = nom.strip()[:40]
            if not nom:
                continue
            if nom.lower() in PARAMETRES_SENSIBLES:
                resultat[nom] = "***"
            else:
                resultat[nom] = valeur[:60]
        return resultat

    # -- ecriture ----------------------------------------------------------
    def enregistrer(self, evenement: str, **champs) -> dict:
        entree = {"horodatage": horodatage(), "service": self.service, "evenement": evenement}
        entree.update({k: v for k, v in champs.items() if v is not None and v != ""})
        with self._mutex:
            # La rotation doit preceder le calcul de « prec » : elle remet la
            # chaine a zero, donc la premiere ligne du nouveau fichier doit
            # pointer sur « genesis ». Sinon verifier_chaine signale une rupture
            # des la premiere ligne, a chaque rotation.
            self._pivoter_si_besoin()
            entree["prec"] = self._derniere or self._empreinte_derniere_ligne()
            ligne = _canonique(entree)
            try:
                self.chemin.parent.mkdir(parents=True, exist_ok=True)
                with self.chemin.open("ab") as fichier:
                    fichier.write(ligne + b"\n")
                self._derniere = hashlib.sha256(ligne).hexdigest()
            except OSError:
                # Un journal illisible ne doit pas empecher de soigner un patient :
                # on compte l'incident et on continue. Le compteur est expose par
                # le diagnostic de demarrage.
                self.erreurs_ecriture += 1
        return entree

    def _empreinte_derniere_ligne(self) -> str:
        """Au premier appel, reprend la chaine la ou le fichier existant s'arrete."""
        try:
            with self.chemin.open("rb") as fichier:
                derniere = b""
                for ligne in fichier:
                    if ligne.strip():
                        derniere = ligne.rstrip(b"\n")
                if derniere:
                    return hashlib.sha256(derniere).hexdigest()
        except OSError:
            pass
        return "genesis"

    def _pivoter_si_besoin(self) -> None:
        try:
            if self.chemin.exists() and self.chemin.stat().st_size >= self.taille_rotation:
                suffixe = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                self.chemin.rename(self.chemin.with_name(self.chemin.name + "." + suffixe))
                self._derniere = None
        except OSError:
            pass


def verifier_chaine(chemin: Path) -> dict:
    """Relit un journal et verifie que le chainage n'a pas ete rompu.

    Renvoie {"lignes": n, "intact": bool, "premiere_rupture": numero | None}.
    """
    chemin = Path(chemin)
    attendu = "genesis"
    numero = 0
    rupture = None
    illisibles = 0
    try:
        with chemin.open("rb") as fichier:
            for brut in fichier:
                brut = brut.rstrip(b"\n")
                if not brut.strip():
                    continue
                numero += 1
                try:
                    entree = json.loads(brut)
                except ValueError:
                    illisibles += 1
                    rupture = rupture or numero
                    continue
                if rupture is None and entree.get("prec") != attendu:
                    rupture = numero
                attendu = hashlib.sha256(brut).hexdigest()
    except OSError:
        return {"lignes": 0, "intact": True, "premiere_rupture": None, "illisibles": 0,
                "absent": True}
    return {"lignes": numero, "intact": rupture is None, "premiere_rupture": rupture,
            "illisibles": illisibles, "absent": False}
