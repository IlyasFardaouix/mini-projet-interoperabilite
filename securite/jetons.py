"""Jetons d'acces : verification, portees (droits), et resistance a la force brute.

Trois sources de jetons sont acceptees, dans cet ordre :

1. **Registre de jetons** (`securite/registre_jetons.json`, hors depot Git).
   Un jeton par client appelant, avec ses portees et sa date d'expiration.
   Le registre ne contient que des empreintes SHA-256 : le jeton en clair n'est
   jamais stocke, ni cote serveur, ni dans Git.
2. **JWT HS256** si `SEC_JWT_SECRET` est defini : utile quand les deux hopitaux
   veulent des jetons a duree de vie courte, portant leurs portees.
3. **Jeton partage historique** (`H1_API_TOKEN` / `H2_TOKEN`) : conserve pour ne
   pas casser les postes deja configures. Il recoit toutes les portees du
   service et est signale comme « a migrer » dans le journal de securite.

Si aucune des trois sources n'est configuree, la verification echoue en 503 :
l'API ne sert jamais de donnees de sante sans authentification.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .config import Configuration, PORTEES_CONNUES

CLIENT_HISTORIQUE = "jeton-partage"
PORTEE_TOTALE = "*"


class AccesRefuse(Exception):
    """Refus d'acces, traduit en OperationOutcome par l'intergiciel.

    `http` : code HTTP a renvoyer. `type_fhir` : code d'issue FHIR.
    `motif` : libelle court, destine au journal de securite (jamais au client).
    """

    def __init__(self, http: int, type_fhir: str, message: str, motif: str = ""):
        super().__init__(message)
        self.http = http
        self.type_fhir = type_fhir
        self.message = message
        self.motif = motif or type_fhir


@dataclass
class Appelant:
    """Identite reconnue derriere un jeton valide."""

    client: str
    portees: frozenset
    empreinte: str                      # 12 caracteres hex : trace le jeton sans le reveler
    source: str                         # "registre" | "session" | "jwt" | "historique"
    expire_le: Optional[str] = None
    avertissements: tuple = field(default=())
    utilisateur: Optional[str] = None   # login de la personne (source "session")
    role: Optional[str] = None

    def autorise(self, portee: str) -> bool:
        if PORTEE_TOTALE in self.portees or portee in self.portees:
            return True
        service, _, _ = portee.partition(":")
        return f"{service}:{PORTEE_TOTALE}" in self.portees


# ---------------------------------------------------------------------------
# Empreintes
# ---------------------------------------------------------------------------
def empreinte_complete(jeton: str) -> str:
    """SHA-256 du jeton. C'est ce qui est stocke dans le registre."""
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def empreinte_courte(jeton: str) -> str:
    """12 caracteres hex : suffisant pour correler des lignes de journal,
    insuffisant pour retrouver le jeton."""
    return empreinte_complete(jeton)[:12]


# ---------------------------------------------------------------------------
# Registre de jetons
# ---------------------------------------------------------------------------
def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _expire(valeur: Optional[str], reference: Optional[datetime] = None) -> bool:
    if not valeur:
        return False
    try:
        limite = datetime.fromisoformat(str(valeur).replace("Z", "+00:00"))
    except ValueError:
        return True                                  # date illisible : on refuse
    if limite.tzinfo is None:
        limite = limite.replace(tzinfo=timezone.utc)
    return limite <= (reference or _maintenant())


class Registre:
    """Registre des jetons, relu automatiquement quand le fichier change."""

    def __init__(self, chemin: Path):
        self.chemin = Path(chemin)
        self._entrees = []
        self._signature = None
        self._verrou = threading.Lock()

    def entrees(self) -> list:
        with self._verrou:
            self._recharger_si_besoin()
            return list(self._entrees)

    def _recharger_si_besoin(self) -> None:
        try:
            etat = self.chemin.stat()
            signature = (etat.st_mtime_ns, etat.st_size)
        except OSError:
            self._entrees, self._signature = [], None
            return
        if signature == self._signature:
            return
        try:
            contenu = json.loads(self.chemin.read_text(encoding="utf-8"))
            brut = contenu.get("clients") if isinstance(contenu, dict) else contenu
            self._entrees = [e for e in (brut or []) if isinstance(e, dict)]
        except (OSError, ValueError):
            self._entrees = []                        # registre illisible : aucun jeton reconnu
        self._signature = signature

    def chercher(self, jeton: str) -> Optional[dict]:
        """Comparaison a temps constant sur toutes les entrees du registre."""
        presente = empreinte_complete(jeton).encode("ascii")
        trouvee = None
        for entree in self.entrees():
            attendue = str(entree.get("empreinte") or "").removeprefix("sha256:").strip().lower()
            if len(attendue) != 64:
                continue
            if hmac.compare_digest(presente, attendue.encode("ascii")):
                trouvee = entree                      # pas de sortie anticipee : temps constant
        return trouvee


# ---------------------------------------------------------------------------
# JWT HS256
# ---------------------------------------------------------------------------
def _b64url_decode(valeur: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(valeur + "=" * (-len(valeur) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("segment base64url invalide") from exc


def _b64url_encode(donnees: bytes) -> str:
    return base64.urlsafe_b64encode(donnees).decode("ascii").rstrip("=")


def creer_jwt(charge: dict, secret: str, *, duree_s: int = 900) -> str:
    """Emet un JWT HS256. Utilise par l'outil de generation et par les tests."""
    maintenant = int(time.time())
    corps = {"iat": maintenant, "nbf": maintenant, "exp": maintenant + duree_s}
    corps.update(charge)
    entete = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"},
                                       separators=(",", ":")).encode("utf-8"))
    donnees = _b64url_encode(json.dumps(corps, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signe = entete + "." + donnees
    signature = hmac.new(secret.encode("utf-8"), signe.encode("ascii"), hashlib.sha256).digest()
    return signe + "." + _b64url_encode(signature)


def verifier_jwt(jeton: str, secret: str, *, iss: str, aud: str,
                 maintenant: Optional[int] = None) -> dict:
    """Valide signature, algorithme, fenetre de validite, emetteur et destinataire.

    `alg` est verifie AVANT la signature et seul HS256 est accepte : « alg: none »
    et la confusion d'algorithme sont donc impossibles.
    """
    segments = jeton.split(".")
    if len(segments) != 3:
        raise ValueError("un JWT compte trois segments")
    entete_b64, charge_b64, signature_b64 = segments
    try:
        entete = json.loads(_b64url_decode(entete_b64))
    except ValueError as exc:
        raise ValueError("en-tete JWT illisible") from exc
    if not isinstance(entete, dict) or entete.get("alg") != "HS256":
        raise ValueError("algorithme refuse : seul HS256 est accepte")
    if entete.get("typ") not in (None, "JWT"):
        raise ValueError("type de jeton refuse")

    attendue = hmac.new(secret.encode("utf-8"), (entete_b64 + "." + charge_b64).encode("ascii"),
                        hashlib.sha256).digest()
    if not hmac.compare_digest(attendue, _b64url_decode(signature_b64)):
        raise ValueError("signature invalide")

    charge = json.loads(_b64url_decode(charge_b64))
    if not isinstance(charge, dict):
        raise ValueError("charge utile JWT illisible")

    horloge = int(time.time()) if maintenant is None else maintenant
    marge = 30                                        # tolerance de desynchronisation d'horloge
    exp = charge.get("exp")
    if not isinstance(exp, (int, float)) or isinstance(exp, bool):
        raise ValueError("exp obligatoire")
    if horloge > exp + marge:
        raise ValueError("jeton expire")
    nbf = charge.get("nbf")
    if isinstance(nbf, (int, float)) and not isinstance(nbf, bool) and horloge + marge < nbf:
        raise ValueError("jeton pas encore valide")
    if iss and charge.get("iss") != iss:
        raise ValueError("emetteur inattendu")
    if aud:
        destinataires = charge.get("aud")
        liste = destinataires if isinstance(destinataires, list) else [destinataires]
        if aud not in liste:
            raise ValueError("destinataire inattendu")
    return charge


def _portees_de(valeur) -> frozenset:
    if isinstance(valeur, str):
        return frozenset(p for p in valeur.replace(",", " ").split() if p)
    if isinstance(valeur, Iterable):
        return frozenset(str(p).strip() for p in valeur if str(p).strip())
    return frozenset()


# ---------------------------------------------------------------------------
# Anti-force-brute
# ---------------------------------------------------------------------------
class CompteurEchecs:
    """Verrouille une adresse apres N echecs d'authentification consecutifs.

    En memoire : suffisant pour un prototype a un seul processus. Avec plusieurs
    workers, il faut un magasin partage (Redis) ou un pare-feu applicatif.
    """

    def __init__(self, maximum: int, verrou_s: int):
        self.maximum = max(1, maximum)
        self.verrou_s = max(1, verrou_s)
        self._echecs = {}
        self._mutex = threading.Lock()

    def secondes_restantes(self, cle: str, maintenant: Optional[float] = None) -> int:
        horloge = time.monotonic() if maintenant is None else maintenant
        with self._mutex:
            nombre, jusqua = self._echecs.get(cle, (0, 0.0))
            if nombre >= self.maximum and jusqua > horloge:
                return int(jusqua - horloge) + 1
            if jusqua and jusqua <= horloge:
                self._echecs.pop(cle, None)
            return 0

    def echec(self, cle: str, maintenant: Optional[float] = None) -> int:
        horloge = time.monotonic() if maintenant is None else maintenant
        with self._mutex:
            nombre, _ = self._echecs.get(cle, (0, 0.0))
            nombre += 1
            self._echecs[cle] = (nombre, horloge + self.verrou_s)
            return nombre

    def succes(self, cle: str) -> None:
        with self._mutex:
            self._echecs.pop(cle, None)


# ---------------------------------------------------------------------------
# Verificateur
# ---------------------------------------------------------------------------
class Verificateur:
    """Transforme un en-tete Authorization en `Appelant`, ou leve `AccesRefuse`."""

    def __init__(self, conf: Configuration):
        from .utilisateurs import Comptes, Sessions    # import differe : utilisateurs importe ce module

        self.conf = conf
        self.registre = Registre(conf.registre)
        self.compteur = CompteurEchecs(conf.echecs_max, conf.verrou_secondes)
        self.sessions = Sessions(conf, Comptes(conf.utilisateurs))

    # -- configuration -----------------------------------------------------
    def configure(self) -> bool:
        return bool(self.registre.entrees() or self.conf.jwt_secret or self.conf.jeton_historique
                    or (self.conf.session_secret and self.sessions.comptes.tous()))

    def diagnostic(self) -> list:
        """Anomalies de configuration, pour le journal de demarrage."""
        anomalies = []
        if not self.configure():
            anomalies.append(
                "aucune source de jetons : registre absent, SEC_JWT_SECRET vide et jeton partage "
                "non defini. Les routes protegees repondront 503.")
        if self.conf.jeton_historique and not self.registre.entrees():
            anomalies.append(
                "seul le jeton partage est configure : tous les appelants ont tous les droits. "
                "Creer un registre : py securite/outils/generer_jetons.py")
        if 0 < len(self.conf.jeton_historique) < 32:
            anomalies.append("le jeton partage fait moins de 32 caracteres : entropie insuffisante.")
        if self.conf.strict and not self.conf.tls_requis:
            anomalies.append("mode strict mais SEC_TLS_REQUIS=0 : trafic en clair tolere.")
        for entree in self.registre.entrees():
            if _expire(entree.get("expire_le")):
                anomalies.append("jeton expire dans le registre : " + str(entree.get("id")))
        return anomalies

    # -- verification ------------------------------------------------------
    def extraire(self, autorisation: Optional[str]) -> str:
        schema, _, jeton = (autorisation or "").partition(" ")
        if schema.lower() != "bearer" or not jeton.strip():
            raise AccesRefuse(401, "login",
                              "Jeton Bearer absent ou mal forme (en-tete Authorization: Bearer <jeton>).",
                              "jeton_absent")
        return jeton.strip()

    def verifier(self, autorisation: Optional[str], *, cle_verrou: str = "") -> Appelant:
        if not self.configure():
            raise AccesRefuse(503, "transient",
                              "Authentification non configuree sur ce service.",
                              "auth_non_configuree")

        restant = self.compteur.secondes_restantes(cle_verrou) if cle_verrou else 0
        if restant:
            raise AccesRefuse(429, "throttled",
                              "Trop d'echecs d'authentification. Nouvel essai dans "
                              + str(restant) + " s.",
                              "verrouille")

        try:
            jeton = self.extraire(autorisation)
            appelant = self._reconnaitre(jeton)
        except AccesRefuse:
            if cle_verrou:
                self.compteur.echec(cle_verrou)
            raise
        if cle_verrou:
            self.compteur.succes(cle_verrou)
        return appelant

    def _reconnaitre(self, jeton: str) -> Appelant:
        court = empreinte_courte(jeton)

        entree = self.registre.chercher(jeton)
        if entree is not None:
            if entree.get("actif") is False:
                raise AccesRefuse(401, "login", "Jeton revoque.", "jeton_revoque")
            if _expire(entree.get("expire_le")):
                raise AccesRefuse(401, "login", "Jeton expire.", "jeton_expire")
            portees = _portees_de(entree.get("portees"))
            inconnues = {p.partition(":")[2] for p in portees} - PORTEES_CONNUES - {PORTEE_TOTALE, ""}
            avertissements = ("portees inconnues: " + str(sorted(inconnues)),) if inconnues else ()
            return Appelant(client=str(entree.get("id") or "inconnu"), portees=portees,
                            empreinte=court, source="registre",
                            expire_le=entree.get("expire_le"), avertissements=avertissements)

        if self.conf.session_secret and jeton.count(".") == 2:
            charge = self.charge_de_session(jeton)
            if charge is not None:
                return self.sessions.appelant(charge, court)

        if self.conf.jwt_secret and jeton.count(".") == 2:
            try:
                charge = verifier_jwt(jeton, self.conf.jwt_secret,
                                      iss=self.conf.jwt_iss, aud=self.conf.jwt_aud)
            except ValueError as exc:
                raise AccesRefuse(401, "login", "Jeton JWT refuse.", "jwt:" + str(exc)) from exc
            portees = _portees_de(charge.get("scope") or charge.get("portees"))
            return Appelant(client=str(charge.get("sub") or charge.get("client_id") or "jwt"),
                            portees=portees, empreinte=court, source="jwt",
                            expire_le=str(charge.get("exp")))

        attendu = self.conf.jeton_historique
        if attendu and hmac.compare_digest(jeton.encode("utf-8"), attendu.encode("utf-8")):
            return Appelant(client=CLIENT_HISTORIQUE,
                            portees=frozenset({self.conf.service.lower() + ":" + PORTEE_TOTALE}),
                            empreinte=court, source="historique",
                            avertissements=("jeton partage sans portees : a remplacer par un jeton du registre",))

        raise AccesRefuse(401, "login", "Jeton Bearer absent ou invalide.", "jeton_invalide")

    def charge_de_session(self, jeton: str) -> Optional[dict]:
        """Charge d'un jeton de session de CE service, None s'il n'est pas signe
        avec le secret de session (c'est alors peut-etre un JWT inter-hopitaux).
        Un jeton de session expire ou destine a l'autre hopital donne 401."""
        from .utilisateurs import audience_session

        try:
            return verifier_jwt(jeton, self.conf.session_secret, iss=self.conf.jwt_iss,
                                aud=audience_session(self.conf))
        except ValueError as exc:
            if str(exc) in {"signature invalide", "en-tete JWT illisible",
                            "algorithme refuse : seul HS256 est accepte", "type de jeton refuse"}:
                return None
            raise AccesRefuse(401, "login", "Session expiree : se reconnecter.",
                              "session:" + str(exc)) from exc
