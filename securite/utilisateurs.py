"""Comptes du personnel et sessions : authentification des PERSONNES.

Le registre de jetons (jetons.py) authentifie des systemes : l'API de l'autre
hopital, un outil interne. Il ne dit pas QUI, dans l'etablissement, a consulte
ou envoye un dossier. Ce module ajoute des comptes nominatifs pour l'interface :

- un compte par personne, avec un role (medecin, accueil, dpo) ;
- mot de passe hache avec scrypt (bibliotheque standard, sel aleatoire), jamais
  stocke ni journalise en clair ;
- connexion -> jeton d'acces court (JWT HS256, 15 min) + jeton de
  renouvellement (8 h), a usage unique : chaque renouvellement en emet un
  nouveau. Reutiliser un ancien jeton de renouvellement (signe d'un vol)
  ferme toute la session ;
- verrouillage temporaire apres plusieurs echecs, par compte ET par adresse ;
- deconnexion et desactivation de compte effectives immediatement ;
- mot de passe provisoire a changer a la premiere connexion : tant qu'il n'est
  pas change, la session n'a aucun droit sur les dossiers.

Le role est relu a chaque requete : retirer un droit a quelqu'un prend effet
sans attendre l'expiration de son jeton.

Limites du prototype : sessions et revocations sont en memoire (un redemarrage
deconnecte tout le monde, ce qui reste sur) ; pas de double authentification.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Configuration
from .jetons import AccesRefuse, Appelant, CompteurEchecs, creer_jwt, empreinte_complete

# ---------------------------------------------------------------------------
# Roles : suffixes de portees, prefixes par le service (« export » -> « h2:export »)
# ---------------------------------------------------------------------------
ROLES = {
    # Soignant : consulte, envoie et recoit les dossiers ; lit le consentement.
    "medecin": ("export", "simulation", "import", "patient.lire", "patient.chercher",
                "consentement.lire"),
    # Accueil / admissions : identite du patient et recueil du consentement,
    # sans acces au contenu medical des dossiers.
    "accueil": ("patient.lire", "patient.chercher", "patient.creer",
                "consentement.lire", "consentement.gerer"),
    # Delegue a la protection des donnees : journaux d'acces et consentements.
    "dpo": ("audit", "consentement.lire"),
}

LOGIN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
MDP_MIN, MDP_MAX = 12, 128
MDP_TROP_COURANTS = {"motdepasse123", "password1234", "azertyuiop12", "123456789012",
                     "administrateur", "hopital12345", "clinique1234"}

# scrypt : 16 Mio de memoire par calcul, environ 50 ms. Suffisant pour freiner
# une attaque hors ligne sur le fichier des comptes, supportable a la connexion.
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LONGUEUR = 2 ** 14, 8, 1, 32


class SaisieInvalide(ValueError):
    """Login, role ou mot de passe non conforme (HTTP 422)."""


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _b64(octets: bytes) -> str:
    return base64.b64encode(octets).decode("ascii")


# ---------------------------------------------------------------------------
# Mots de passe
# ---------------------------------------------------------------------------
def hacher_mdp(mdp: str, *, sel: Optional[bytes] = None) -> str:
    sel = sel or secrets.token_bytes(16)
    empreinte = hashlib.scrypt(mdp.encode("utf-8"), salt=sel, n=SCRYPT_N, r=SCRYPT_R,
                               p=SCRYPT_P, dklen=SCRYPT_LONGUEUR, maxmem=64 * 1024 * 1024)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(sel)}${_b64(empreinte)}"


def verifier_mdp(mdp: str, stocke: str) -> bool:
    try:
        algo, n, r, p, sel, attendue = stocke.split("$")
        if algo != "scrypt":
            return False
        calculee = hashlib.scrypt(mdp.encode("utf-8"), salt=base64.b64decode(sel), n=int(n),
                                  r=int(r), p=int(p), dklen=len(base64.b64decode(attendue)),
                                  maxmem=64 * 1024 * 1024)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculee, base64.b64decode(attendue))


_EMPREINTE_LEURRE = None


def _leurre() -> str:
    """Empreinte calculee pour un login inconnu : meme duree de reponse, pas
    d'indice sur l'existence du compte."""
    global _EMPREINTE_LEURRE
    if _EMPREINTE_LEURRE is None:
        _EMPREINTE_LEURRE = hacher_mdp(secrets.token_urlsafe(16))
    return _EMPREINTE_LEURRE


def controler_mdp(mdp: str, login: str) -> None:
    """Politique : longueur avant tout (12 a 128 caracteres), pas le login, pas
    un mot de passe connu, pas un seul caractere repete."""
    if not isinstance(mdp, str) or not MDP_MIN <= len(mdp) <= MDP_MAX:
        raise SaisieInvalide(f"Le mot de passe doit compter entre {MDP_MIN} et {MDP_MAX} caracteres.")
    bas = mdp.lower()
    if login and login.lower() in bas:
        raise SaisieInvalide("Le mot de passe ne doit pas contenir l'identifiant.")
    if bas in MDP_TROP_COURANTS or len(set(mdp)) < 4:
        raise SaisieInvalide("Mot de passe trop previsible.")


# ---------------------------------------------------------------------------
# Comptes (fichier JSON hors depot Git, relu quand il change)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Compte:
    login: str
    nom: str
    role: str
    actif: bool
    doit_changer_mdp: bool
    empreinte_mdp: str

    def public(self) -> dict:
        return {"login": self.login, "nom": self.nom, "role": self.role, "actif": self.actif,
                "doit_changer_mdp": self.doit_changer_mdp}


class Comptes:
    def __init__(self, chemin: Optional[Path]):
        self.chemin = Path(chemin) if chemin else None
        self._comptes: dict = {}
        self._signature = None
        self._verrou = threading.RLock()

    # -- lecture -----------------------------------------------------------
    def _recharger(self) -> None:
        if self.chemin is None:
            self._comptes, self._signature = {}, None
            return
        try:
            etat = self.chemin.stat()
        except OSError:
            self._comptes, self._signature = {}, None
            return
        signature = (etat.st_mtime_ns, etat.st_size)
        if signature == self._signature:
            return
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8")).get("utilisateurs") or []
        except (OSError, ValueError, AttributeError):
            brut = []                                  # fichier illisible : aucun compte
        self._comptes = {str(c.get("login", "")).lower(): c for c in brut if isinstance(c, dict)}
        self._signature = signature

    def tous(self) -> list:
        with self._verrou:
            self._recharger()
            return [self._compte(c) for c in self._comptes.values()]

    def chercher(self, login: str) -> Optional[Compte]:
        with self._verrou:
            self._recharger()
            brut = self._comptes.get(str(login or "").strip().lower())
            return self._compte(brut) if brut else None

    @staticmethod
    def _compte(brut: dict) -> Compte:
        return Compte(login=str(brut.get("login", "")).lower(), nom=str(brut.get("nom") or ""),
                      role=str(brut.get("role") or ""), actif=brut.get("actif") is not False,
                      doit_changer_mdp=bool(brut.get("doit_changer_mdp")),
                      empreinte_mdp=str(brut.get("empreinte_mdp") or ""))

    def authentifier(self, login: str, mdp: str) -> Optional[Compte]:
        """Compte si le mot de passe est bon ET le compte actif, sinon None.
        Un login inconnu coute le meme calcul qu'un login connu."""
        compte = self.chercher(login)
        bon = verifier_mdp(str(mdp or ""), compte.empreinte_mdp if compte else _leurre())
        if compte is None or not bon or not compte.actif or compte.role not in ROLES:
            return None
        return compte

    # -- ecriture (outil d'administration et changement de mot de passe) ----
    def _ecrire(self) -> None:
        if self.chemin is None:
            raise SaisieInvalide("Aucun fichier de comptes configure (SEC_UTILISATEURS).")
        contenu = {"version": 1, "utilisateurs": sorted(self._comptes.values(), key=lambda c: c["login"])}
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = self.chemin.with_suffix(".tmp")
        temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            temporaire.chmod(0o600)
        except OSError:
            pass
        os.replace(temporaire, self.chemin)            # remplacement atomique
        self._signature = None

    def creer(self, login: str, nom: str, role: str, mdp: str, *, provisoire: bool = True) -> Compte:
        login = str(login or "").strip().lower()
        if not LOGIN.match(login):
            raise SaisieInvalide("Identifiant : 3 a 32 caracteres parmi a-z 0-9 . _ - .")
        if role not in ROLES:
            raise SaisieInvalide("Role inconnu. Roles : " + ", ".join(sorted(ROLES)) + ".")
        controler_mdp(mdp, login)
        with self._verrou:
            self._recharger()
            if login in self._comptes:
                raise SaisieInvalide(f"Le compte {login} existe deja.")
            self._comptes[login] = {
                "login": login, "nom": str(nom or "").strip()[:100], "role": role, "actif": True,
                "doit_changer_mdp": provisoire, "empreinte_mdp": hacher_mdp(mdp),
                "cree_le": _maintenant_iso(), "mdp_change_le": _maintenant_iso(),
            }
            self._ecrire()
        return self.chercher(login)

    def modifier(self, login: str, **champs) -> Compte:
        with self._verrou:
            self._recharger()
            brut = self._comptes.get(str(login or "").lower())
            if brut is None:
                raise SaisieInvalide(f"Compte inconnu : {login}.")
            if "role" in champs and champs["role"] not in ROLES:
                raise SaisieInvalide("Role inconnu. Roles : " + ", ".join(sorted(ROLES)) + ".")
            if "mdp" in champs:
                controler_mdp(champs["mdp"], brut["login"])
                brut["empreinte_mdp"] = hacher_mdp(champs.pop("mdp"))
                brut["mdp_change_le"] = _maintenant_iso()
            brut.update({k: v for k, v in champs.items() if k in {"role", "actif", "doit_changer_mdp", "nom"}})
            brut["modifie_le"] = _maintenant_iso()
            self._ecrire()
        return self.chercher(login)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def audience_session(conf: Configuration) -> str:
    return conf.service.lower() + "-session"


def portees_du_role(role: str, service: str) -> frozenset:
    return frozenset(f"{service.lower()}:{s}" for s in ROLES.get(role, ()))


class Sessions:
    """Emission, renouvellement et revocation des jetons de session."""

    def __init__(self, conf: Configuration, comptes: Comptes):
        self.conf = conf
        self.comptes = comptes
        self.echecs = CompteurEchecs(conf.echecs_max, conf.verrou_secondes)
        self._renouvellements: dict = {}       # empreinte -> {login, famille, expire, utilise}
        self._familles_fermees: set = set()
        self._jti_revoques: dict = {}          # jti -> expiration (purge au passage)
        self._verrou = threading.Lock()

    @property
    def active(self) -> bool:
        return bool(self.conf.session_secret)

    def _exiger_active(self) -> None:
        if not self.active:
            raise AccesRefuse(503, "transient", "Connexion des utilisateurs non configuree sur ce service.",
                              "session_non_configuree")

    # -- connexion ---------------------------------------------------------
    def ouvrir(self, login: str, mdp: str, *, cle_ip: str = "") -> dict:
        self._exiger_active()
        cles = ["compte:" + str(login or "").strip().lower()] + (["ip:" + cle_ip] if cle_ip else [])
        restant = max(self.echecs.secondes_restantes(c) for c in cles)
        if restant:
            raise AccesRefuse(429, "throttled", "Trop d'echecs de connexion. Nouvel essai dans "
                              + str(restant) + " s.", "connexion_verrouillee")
        compte = self.comptes.authentifier(login, mdp)
        if compte is None:
            for cle in cles:
                self.echecs.echec(cle)
            raise AccesRefuse(401, "login", "Identifiant ou mot de passe incorrect.", "connexion_refusee")
        for cle in cles:
            self.echecs.succes(cle)
        return self._emettre(compte, famille=uuid.uuid4().hex)

    def _emettre(self, compte: Compte, *, famille: str) -> dict:
        maintenant = int(time.time())
        jti = uuid.uuid4().hex
        portees = frozenset() if compte.doit_changer_mdp else portees_du_role(compte.role, self.conf.service)
        acces = creer_jwt({"iss": self.conf.jwt_iss, "aud": audience_session(self.conf),
                           "sub": compte.login, "jti": jti, "fam": famille, "role": compte.role},
                          self.conf.session_secret, duree_s=self.conf.session_duree)
        renouvellement = secrets.token_urlsafe(32)
        with self._verrou:
            self._purger(maintenant)
            self._renouvellements[empreinte_complete(renouvellement)] = {
                "login": compte.login, "famille": famille, "utilise": False,
                "expire": maintenant + self.conf.session_renouvellement}
        return {
            "access_token": acces, "token_type": "Bearer", "expires_in": self.conf.session_duree,
            "refresh_token": renouvellement, "refresh_expires_in": self.conf.session_renouvellement,
            "utilisateur": compte.public(), "portees": sorted(portees),
            "changement_mdp_requis": compte.doit_changer_mdp,
        }

    def renouveler(self, jeton_renouvellement: str) -> dict:
        self._exiger_active()
        refus = AccesRefuse(401, "login", "Session expiree ou fermee : se reconnecter.", "renouvellement_refuse")
        maintenant = int(time.time())
        with self._verrou:
            entree = self._renouvellements.get(empreinte_complete(str(jeton_renouvellement or "")))
            if entree is None or entree["expire"] < maintenant or entree["famille"] in self._familles_fermees:
                raise refus
            if entree["utilise"]:
                # Deja utilise : quelqu'un d'autre detient une copie. On ferme tout.
                self._familles_fermees.add(entree["famille"])
                raise AccesRefuse(401, "login", "Session fermee par securite : se reconnecter.",
                                  "renouvellement_rejoue")
            entree["utilise"] = True
        compte = self.comptes.chercher(entree["login"])
        if compte is None or not compte.actif or compte.role not in ROLES:
            raise refus
        return self._emettre(compte, famille=entree["famille"])

    def fermer(self, charge: dict) -> None:
        """Deconnexion : le jeton d'acces et toute la chaine de renouvellement."""
        with self._verrou:
            self._jti_revoques[str(charge.get("jti"))] = int(charge.get("exp") or 0)
            self._familles_fermees.add(str(charge.get("fam")))

    def fermer_autres(self, login: str, sauf_famille: str) -> int:
        """Apres un changement de mot de passe : ferme les autres sessions du compte."""
        with self._verrou:
            familles = {e["famille"] for e in self._renouvellements.values()
                        if e["login"] == login and e["famille"] != sauf_famille}
            self._familles_fermees |= familles
            return len(familles)

    def _purger(self, maintenant: int) -> None:
        self._jti_revoques = {j: e for j, e in self._jti_revoques.items() if e + 60 >= maintenant}
        self._renouvellements = {k: e for k, e in self._renouvellements.items() if e["expire"] >= maintenant}

    # -- verification d'un jeton d'acces (appele par le Verificateur) ------
    def appelant(self, charge: dict, empreinte: str) -> Appelant:
        with self._verrou:
            ferme = (str(charge.get("jti")) in self._jti_revoques
                     or str(charge.get("fam")) in self._familles_fermees)
        if ferme:
            raise AccesRefuse(401, "login", "Session fermee : se reconnecter.", "session_fermee")
        compte = self.comptes.chercher(str(charge.get("sub") or ""))
        if compte is None or not compte.actif:
            raise AccesRefuse(401, "login", "Compte desactive.", "compte_desactive")
        if compte.doit_changer_mdp:
            portees, avertissements = frozenset(), ("mot de passe provisoire a changer",)
        else:
            portees, avertissements = portees_du_role(compte.role, self.conf.service), ()
        return Appelant(client="utilisateur:" + compte.login, portees=portees, empreinte=empreinte,
                        source="session", expire_le=str(charge.get("exp")),
                        avertissements=avertissements, utilisateur=compte.login, role=compte.role)

    # -- mot de passe ------------------------------------------------------
    def changer_mdp(self, appelant: Appelant, charge: dict, ancien: str, nouveau: str) -> dict:
        """Verifie l'ancien mot de passe (avec verrouillage), enregistre le nouveau,
        ferme les autres sessions et renvoie de nouveaux jetons avec les droits du role."""
        login = appelant.utilisateur
        cle = "compte:" + login
        restant = self.echecs.secondes_restantes(cle)
        if restant:
            raise AccesRefuse(429, "throttled", "Trop d'echecs. Nouvel essai dans " + str(restant) + " s.",
                              "mdp_verrouille")
        if self.comptes.authentifier(login, ancien) is None:
            self.echecs.echec(cle)
            raise AccesRefuse(401, "login", "Mot de passe actuel incorrect.", "mdp_refuse")
        self.echecs.succes(cle)
        if hmac.compare_digest(str(ancien).encode("utf-8"), str(nouveau).encode("utf-8")):
            raise SaisieInvalide("Le nouveau mot de passe doit etre different de l'ancien.")
        compte = self.comptes.modifier(login, mdp=nouveau, doit_changer_mdp=False)
        self.fermer(charge)
        self.fermer_autres(login, sauf_famille="")
        return self._emettre(compte, famille=uuid.uuid4().hex)
