"""Auditeur de securite automatique du depot d'interoperabilite FHIR (H1 <-> H2).

    py securite/outils/verifier_securite.py
    py securite/outils/verifier_securite.py --json
    py securite/outils/verifier_securite.py --racine <chemin>

L'outil parcourt le depot et renvoie une liste de constats. Chaque constat porte
un identifiant stable (SEC-001 ...), une gravite, le fichier et la ligne quand
c'est applicable, une explication courte et la correction a appliquer.

    P0  bloquant   : un secret ou une donnee de sante peut fuir, ou une
                     authentification peut etre contournee.
    P1  important  : durcissement manquant, a corriger avant la mise en service.
    P2  remarque   : information, document manquant, verification humaine.

Code de sortie : 2 s'il reste un P0, 1 s'il reste un P1, 0 sinon.

Regles de prudence que l'outil s'applique a lui-meme :

  * le contenu d'un fichier `.env` n'est JAMAIS lu : seuls son existence et son
    statut Git sont examines ;
  * la valeur d'un secret detecte n'est jamais recopiee dans le rapport : on
    affiche le nom de la variable, le fichier, la ligne et la longueur ;
  * les URL de systemes FHIR (loinc.org, snomed.info/sct, terminology.hl7.org,
    hl7.org/fhir ...) sont des identifiants de vocabulaire, pas des adresses
    reseau : elles ne produisent aucun constat ;
  * une erreur dans un controle n'interrompt pas les autres : elle devient un
    constat P2 « controle interrompu ».

Bibliotheque standard uniquement : l'outil doit tourner sur n'importe quel poste
sans installation. Aucun nom de dossier n'est code en dur, l'audit fonctionne
avant comme apres le renommage api_h1/ -> hopital1/ et api3/ -> hopital2/.

Source volontairement sans accents, comme le reste du package securite/.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

RACINE_PAR_DEFAUT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Reglages du parcours
# ---------------------------------------------------------------------------

DOSSIERS_IGNORES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "archive", ".mypy_cache", ".ruff_cache", ".tox", "site-packages",
    ".idea", ".vscode",
}

TAILLE_MAX_LECTURE = 2 * 1024 * 1024        # au-dela, on ne lit pas le contenu
TAILLE_VOLUMINEUSE = 1024 * 1024            # seuil du controle « fichier lourd »

EXTENSIONS_BINAIRES = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin", ".o", ".a", ".lib",
    ".jar", ".class", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
    ".db", ".sqlite", ".sqlite3", ".mdb", ".dmp", ".whl", ".woff", ".woff2",
    ".ttf", ".eot", ".mp3", ".mp4", ".avi", ".mov", ".pfx", ".p12", ".der",
}

GRAVITES = ("P0", "P1", "P2")
LIBELLE_GRAVITE = {"P0": "bloquant", "P1": "important", "P2": "remarque"}

# Systemes de codage FHIR : ce sont des identifiants (des URN deguisees en URL),
# pas des serveurs que l'on joint en clair. Aucun controle ne doit les signaler.
SYSTEMES_FHIR = (
    "loinc.org",
    "snomed.info",
    "terminology.hl7.org",
    "hl7.org/fhir",
    "unitsofmeasure.org",
    "dicom.nema.org",
    "nucc.org",
    "ncbi.nlm.nih.gov",
    "whocc.no",
    "urn:oid:",
    "urn:uuid:",
    "urn:ietf:",
    "urn:ma:",
)

# ---------------------------------------------------------------------------
# Constat
# ---------------------------------------------------------------------------


@dataclass
class Constat:
    """Un point d'audit, pret a etre affiche ou serialise."""

    identifiant: str
    gravite: str
    titre: str
    explication: str
    correction: str
    chemin: str = ""
    ligne: Optional[int] = None

    def vers_dict(self) -> dict:
        return {
            "identifiant": self.identifiant,
            "gravite": self.gravite,
            "titre": self.titre,
            "chemin": self.chemin,
            "ligne": self.ligne,
            "explication": self.explication,
            "correction": self.correction,
        }

    def cle_de_tri(self):
        return (GRAVITES.index(self.gravite) if self.gravite in GRAVITES else 9,
                self.identifiant, self.chemin, self.ligne or 0)


# ---------------------------------------------------------------------------
# Petits utilitaires partages
# ---------------------------------------------------------------------------


def est_fichier_env(nom: str) -> bool:
    """Vrai pour .env, prod.env, .env.local, .env.example ..."""
    return nom == ".env" or nom.endswith(".env") or nom.startswith(".env.")


def est_exemple_env(nom: str) -> bool:
    """Vrai pour les gabarits publiables (.env.example et variantes)."""
    return nom in {".env.example", ".env.exemple", ".env.sample",
                   ".env.template", ".env.dist", ".env.modele"}


def est_fichier_de_test(chemin_relatif: str) -> bool:
    morceaux = chemin_relatif.split("/")
    nom = morceaux[-1]
    if {"tests", "test", "testing"} & set(morceaux[:-1]):
        return True
    return (nom.startswith("test_") or nom.startswith("tests.")
            or nom.endswith("_test.py") or nom == "conftest.py")


def est_systeme_fhir(valeur: str) -> bool:
    """Vrai si la chaine designe un systeme de codage FHIR, pas une adresse."""
    minuscule = valeur.lower()
    return any(systeme in minuscule for systeme in SYSTEMES_FHIR)


def est_document(chemin_relatif: str) -> bool:
    return chemin_relatif.lower().endswith((".md", ".rst", ".txt", ".adoc"))


def est_code_python(chemin_relatif: str) -> bool:
    return chemin_relatif.lower().endswith(".py")


def nom_de(chemin_relatif: str) -> str:
    return chemin_relatif.rsplit("/", 1)[-1]


def taille_lisible(octets: int) -> str:
    if octets >= 1024 * 1024:
        return "%.1f Mo" % (octets / (1024.0 * 1024.0))
    return "%.0f Ko" % (octets / 1024.0)


def _lignes_de_chaines(lignes: list) -> set:
    """Numeros de lignes situes a l'interieur d'un bloc triple-guillemets.

    Sert a ne pas confondre une consigne de documentation (lancer avec
    --reload) avec du code reellement execute.
    """
    triples = (chr(34) * 3, chr(39) * 3)
    dedans = set()
    delimiteur = None
    for numero, ligne in enumerate(lignes, 1):
        if delimiteur is None:
            trouve = None
            for marque in triples:
                position = ligne.find(marque)
                if position != -1 and (trouve is None or position < trouve[0]):
                    trouve = (position, marque)
            if trouve is None:
                continue
            marque = trouve[1]
            if ligne.count(marque) >= 2:
                continue                      # chaine ouverte et fermee ici
            delimiteur = marque
            dedans.add(numero)
        else:
            dedans.add(numero)
            if delimiteur in ligne:
                delimiteur = None
    return dedans


def lignes_de_code(contexte, chemin_relatif: str):
    """Itere (numero, ligne) en sautant commentaires et docstrings Python."""
    lignes = contexte.lignes(chemin_relatif)
    dans_chaine = _lignes_de_chaines(lignes) if est_code_python(chemin_relatif) else set()
    for numero, ligne in enumerate(lignes, 1):
        if numero in dans_chaine:
            continue
        nue = ligne.strip()
        if not nue or nue.startswith("#"):
            continue
        yield numero, ligne


# ---------------------------------------------------------------------------
# Contexte : racine, fichiers, contenus en cache, etat Git
# ---------------------------------------------------------------------------


class Contexte:
    """Tout ce qu'un controle doit savoir, lu une seule fois."""

    def __init__(self, racine):
        self.racine = Path(racine).resolve()
        self.tous = {}              # chemin relatif -> taille en octets
        self.fichiers = []          # fichiers texte examinables
        self.incidents = []         # (chemin, message) rencontres au parcours
        self._contenus = {}
        self._regles_gitignore = None
        self._ignores_git = None
        self.depot_git = self._detecter_depot()
        self.suivis_git = self._lister_suivis()
        self._parcourir()
        self.fichier_auditeur = self._chemin_de_l_auditeur()
        # Les controles de contenu sautent le fichier de l'auditeur : il cite
        # par construction tous les motifs qu'il recherche.
        self.fichiers_contenu = [chemin for chemin in self.fichiers
                                 if chemin != self.fichier_auditeur]

    # -- Git ----------------------------------------------------------------
    def _git(self, *arguments, **options):
        entree = options.get("entree")
        commande = ["git", "-C", str(self.racine)] + list(arguments)
        try:
            return subprocess.run(
                commande,
                input=entree.encode("utf-8") if entree is not None else None,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def _detecter_depot(self) -> bool:
        resultat = self._git("rev-parse", "--is-inside-work-tree")
        return bool(resultat and resultat.returncode == 0
                    and resultat.stdout.strip() == b"true")

    def _lister_suivis(self):
        """Ensemble des chemins suivis par Git, ou None hors depot."""
        if not self.depot_git:
            return None
        resultat = self._git("ls-files", "-z")
        if resultat is None or resultat.returncode != 0:
            return None
        brut = resultat.stdout.decode("utf-8", "replace")
        return {morceau for morceau in brut.split("\0") if morceau}

    def _chemin_de_l_auditeur(self):
        try:
            return Path(__file__).resolve().relative_to(self.racine).as_posix()
        except (ValueError, OSError):
            return None

    # -- Parcours -----------------------------------------------------------
    def _parcourir(self):
        for dossier, sous_dossiers, fichiers in os.walk(self.racine):
            sous_dossiers[:] = sorted(
                nom for nom in sous_dossiers
                if nom not in DOSSIERS_IGNORES and not nom.endswith(".egg-info")
            )
            for nom in sorted(fichiers):
                chemin = Path(dossier) / nom
                try:
                    taille = chemin.stat().st_size
                    relatif = chemin.relative_to(self.racine).as_posix()
                except (OSError, ValueError) as erreur:
                    self.incidents.append((str(chemin), str(erreur)))
                    continue
                self.tous[relatif] = taille
                if est_fichier_env(nom) and not est_exemple_env(nom):
                    continue                       # on ne lit jamais un .env
                if taille > TAILLE_MAX_LECTURE:
                    continue
                if Path(nom).suffix.lower() in EXTENSIONS_BINAIRES:
                    continue
                if self._semble_binaire(chemin):
                    continue
                self.fichiers.append(relatif)

    def _semble_binaire(self, chemin) -> bool:
        try:
            with chemin.open("rb") as fichier:
                return b"\0" in fichier.read(4096)
        except OSError as erreur:
            self.incidents.append((str(chemin), str(erreur)))
            return True

    # -- Contenus -----------------------------------------------------------
    def texte(self, chemin_relatif: str) -> str:
        """Contenu du fichier, lu une seule fois, jamais en echec."""
        if chemin_relatif in self._contenus:
            return self._contenus[chemin_relatif]
        contenu = ""
        nom = nom_de(chemin_relatif)
        if est_fichier_env(nom) and not est_exemple_env(nom):
            self._contenus[chemin_relatif] = ""      # garde-fou : jamais de .env
            return ""
        try:
            octets = (self.racine / chemin_relatif).read_bytes()
            for encodage in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                try:
                    contenu = octets.decode(encodage)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                contenu = octets.decode("utf-8", "replace")
        except OSError as erreur:
            self.incidents.append((chemin_relatif, str(erreur)))
            contenu = ""
        self._contenus[chemin_relatif] = contenu
        return contenu

    def lignes(self, chemin_relatif: str) -> list:
        return self.texte(chemin_relatif).splitlines()

    def ligne_brute(self, chemin_relatif: str, numero: int) -> str:
        lignes = self.lignes(chemin_relatif)
        if 1 <= numero <= len(lignes):
            return lignes[numero - 1]
        return ""

    # -- Statut Git d'un chemin ---------------------------------------------
    def est_suivi(self, chemin_relatif: str):
        if self.suivis_git is None:
            return None
        return chemin_relatif in self.suivis_git

    def est_ignore(self, chemin_relatif: str) -> bool:
        if self.depot_git:
            if self._ignores_git is None:
                self._ignores_git = self._interroger_check_ignore()
            return chemin_relatif in self._ignores_git
        return self._ignore_selon_gitignore(chemin_relatif)

    def _interroger_check_ignore(self) -> set:
        resultat = self._git("check-ignore", "--stdin", "-z",
                             entree="\0".join(self.tous))
        if resultat is None:
            return set()
        brut = resultat.stdout.decode("utf-8", "replace")
        return {morceau for morceau in brut.split("\0") if morceau}

    def _charger_regles(self):
        """Lit les .gitignore du depot (du plus general au plus specifique)."""
        regles = []
        for relatif in self.tous:
            if nom_de(relatif) != ".gitignore":
                continue
            dossier = relatif[: -len(".gitignore")].rstrip("/")
            motifs = []
            for ligne in self.lignes(relatif):
                motif = ligne.strip()
                if not motif or motif.startswith("#"):
                    continue
                negation = motif.startswith("!")
                if negation:
                    motif = motif[1:].strip()
                if not motif:
                    continue
                motifs.append((negation, motif.strip("/"), motif.endswith("/")))
            regles.append((dossier, motifs))
        regles.sort(key=lambda couple: couple[0].count("/") if couple[0] else -1)
        self._regles_gitignore = regles

    def _ignore_selon_gitignore(self, chemin_relatif: str) -> bool:
        if self._regles_gitignore is None:
            self._charger_regles()
        decision = False
        for dossier, motifs in self._regles_gitignore:
            if dossier:
                if not chemin_relatif.startswith(dossier + "/"):
                    continue
                sous_chemin = chemin_relatif[len(dossier) + 1:]
            else:
                sous_chemin = chemin_relatif
            for negation, motif, dossier_seulement in motifs:
                if _motif_gitignore_correspond(motif, sous_chemin, dossier_seulement):
                    decision = not negation
        return decision

    def versionne(self, chemin_relatif: str) -> bool:
        """Le fichier part-il (ou partirait-il) dans l'historique Git ?

        Dans un depot : reponse exacte (git ls-files). Hors depot : conclusion
        prudente, un fichier non couvert par un .gitignore est suppose
        versionne.
        """
        suivi = self.est_suivi(chemin_relatif)
        if suivi is not None:
            return suivi
        return not self.est_ignore(chemin_relatif)

    @property
    def mention_git(self) -> str:
        if self.depot_git:
            return "statut Git lu avec git ls-files"
        return ("aucun depot Git a la racine : conclusion tiree des fichiers "
                ".gitignore, a confirmer apres git init")


def _motif_gitignore_correspond(motif: str, chemin: str, dossier_seulement: bool) -> bool:
    """Equivalent approche d'un motif .gitignore, sans dependance externe."""
    chemin = chemin.strip("/")
    if not motif or not chemin:
        return False
    morceaux = chemin.split("/")
    if "/" in motif:                                   # motif ancre
        for borne in range(1, len(morceaux) + 1):
            prefixe = "/".join(morceaux[:borne])
            if fnmatch.fnmatchcase(prefixe, motif):
                if dossier_seulement and borne == len(morceaux):
                    continue
                return True
        return False
    for position, morceau in enumerate(morceaux):      # motif libre
        if fnmatch.fnmatchcase(morceau, motif):
            if dossier_seulement and position == len(morceaux) - 1:
                continue
            return True
    return False


# ---------------------------------------------------------------------------
# SEC-001  Fichier .env versionne ou non ignore                          (P0)
# ---------------------------------------------------------------------------


def controle_env_versionne(contexte) -> list:
    constats = []
    for relatif in sorted(contexte.tous):
        nom = nom_de(relatif)
        if not est_fichier_env(nom) or est_exemple_env(nom):
            continue
        if contexte.est_suivi(relatif):
            constats.append(Constat(
                identifiant="SEC-001", gravite="P0", chemin=relatif,
                titre="Fichier d'environnement suivi par Git",
                explication="Ce fichier porte les mots de passe et les jetons du "
                            "service ; il est deja dans l'index Git, donc "
                            "lisible par tout porteur du depot.",
                correction="git rm --cached " + relatif + ", ajouter le motif au "
                           ".gitignore, et considerer les valeurs comme "
                           "compromises : les regenerer."))
        elif not contexte.est_ignore(relatif):
            constats.append(Constat(
                identifiant="SEC-001", gravite="P0", chemin=relatif,
                titre="Fichier d'environnement non couvert par un .gitignore",
                explication="Le fichier existe sur le disque et aucun motif "
                            "applicable ne l'exclut : un git add . l'emportera "
                            "(" + contexte.mention_git + ").",
                correction="ajouter .env et .env.* (avec !.env.example) au "
                           ".gitignore de la racine, puis verifier avec "
                           "git check-ignore -v " + relatif))
    return constats


# ---------------------------------------------------------------------------
# SEC-002  Secret en dur dans un fichier versionne                    (P0/P2)
# ---------------------------------------------------------------------------

NOMS_SENSIBLES = (
    "mot_de_passe", "motdepasse", "password", "passwd", "pwd", "passphrase",
    "secret", "token", "jeton", "api_key", "apikey", "api_secret",
    "private_key", "cle_privee", "credential",
)

# Valeurs manifestement destinees a etre remplacees : jamais un vrai secret.
MARQUEURS_EXEMPLE = (
    "remplacer", "exemple", "example", "sample", "changeme", "change-me",
    "change_me", "placeholder", "a-definir", "a_definir", "votre", "your",
    "todo", "fixme", "demo", "factice", "fictif", "dummy", "fake", "bidon",
    "essai", "test", "masque", "redacted", "anonyme", "xxx", "***", "<", ">",
    "...",
)

_MOTIF_AFFECTATION_SENSIBLE = re.compile(
    r"(?<![\w.])(?P<nom>[A-Za-z0-9_]*(?:" + "|".join(NOMS_SENSIBLES) + r")[A-Za-z0-9_]*)"
    r"\s*[:=]\s*(?P<guillemet>[\"'])(?P<valeur>[^\"'\n]{8,})(?P=guillemet)",
    re.IGNORECASE,
)

_MOTIF_LECTURE_ENV = re.compile(r"os\.(?:getenv|environ)|getenv\s*\(|environ\s*[\[.]")


def _valeur_est_un_exemple(valeur: str) -> bool:
    minuscule = valeur.lower()
    if any(marqueur in minuscule for marqueur in MARQUEURS_EXEMPLE):
        return True
    if not re.search(r"[A-Za-z0-9]", valeur):
        return True
    if len(set(valeur)) <= 2:                      # aaaaaaaa, --------
        return True
    return False


def _valeur_n_est_pas_un_secret(valeur: str) -> bool:
    """Ecarte ce qui ne peut pas etre un secret : URL, chemin, phrase, gabarit."""
    if " " in valeur or "\t" in valeur:
        return True
    if "://" in valeur or valeur.startswith(("/", "./", "../", "\\")):
        return True
    if "{" in valeur or "}" in valeur or "%" in valeur:
        return True
    return est_systeme_fhir(valeur)


def controle_secrets_en_dur(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if est_fichier_env(nom_de(relatif)):
            continue                               # traite par SEC-014
        if not contexte.versionne(relatif):
            continue
        if est_fichier_de_test(relatif):
            continue                               # jetons factices des tests
        for numero, ligne in enumerate(contexte.lignes(relatif), 1):
            if _MOTIF_LECTURE_ENV.search(ligne):
                continue                           # valeur lue dans l'environnement
            for trouve in _MOTIF_AFFECTATION_SENSIBLE.finditer(ligne):
                valeur = trouve.group("valeur")
                if _valeur_est_un_exemple(valeur) or _valeur_n_est_pas_un_secret(valeur):
                    continue
                nom_variable = trouve.group("nom")
                longueur = len(valeur)
                if longueur >= 16:
                    constats.append(Constat(
                        identifiant="SEC-002", gravite="P0",
                        chemin=relatif, ligne=numero,
                        titre="Secret en dur : " + nom_variable,
                        explication="Une valeur litterale de " + str(longueur) +
                                    " caracteres est affectee a " + nom_variable +
                                    " dans un fichier versionne : elle restera "
                                    "dans l'historique Git meme apres correction.",
                        correction="lire la valeur dans l'environnement "
                                   "(os.getenv) et la placer dans le .env local, "
                                   "puis regenerer le secret : voir "
                                   "docs/securite/procedure-secrets.md."))
                else:
                    constats.append(Constat(
                        identifiant="SEC-002", gravite="P2",
                        chemin=relatif, ligne=numero,
                        titre="Jeton factice en dur hors dossier de tests : " + nom_variable,
                        explication="Valeur litterale de " + str(longueur) +
                                    " caracteres : trop courte pour un vrai "
                                    "secret, mais un jeton factice ecrit hors "
                                    "des tests finit souvent en service.",
                        correction="deplacer la valeur dans l'environnement, ou "
                                   "deplacer le fichier dans le dossier de tests."))
    return constats


# ---------------------------------------------------------------------------
# SEC-003  Cle privee dans le depot                                      (P0)
# ---------------------------------------------------------------------------

# Motif assemble par morceaux pour que ce fichier ne se signale pas lui-meme.
_MOTIF_CLE_PRIVEE = re.compile("-----BEGIN" + r"[A-Z0-9 ]*" + "PRIVATE KEY" + "-----")

EXTENSIONS_CLES = (".key", ".key.pem", ".pfx", ".p12")


def controle_cles_privees(contexte) -> list:
    constats = []
    for relatif in sorted(contexte.tous):
        nom = nom_de(relatif).lower()
        if not nom.endswith(EXTENSIONS_CLES):
            continue
        if not contexte.versionne(relatif):
            continue
        constats.append(Constat(
            identifiant="SEC-003", gravite="P0", chemin=relatif,
            titre="Fichier de cle privee dans le depot",
            explication="Ce fichier contient une cle privee ou un conteneur de "
                        "cles ; versionne, il permet d'usurper le service "
                        "(" + contexte.mention_git + ").",
            correction="git rm --cached " + relatif + ", exclure *.key / *.pfx / "
                       "*.p12 dans le .gitignore, puis regenerer le couple de "
                       "cles avec securite/outils/generer_certificats.py."))
    for relatif in contexte.fichiers_contenu:
        if not contexte.versionne(relatif):
            continue
        for numero, ligne in enumerate(contexte.lignes(relatif), 1):
            if _MOTIF_CLE_PRIVEE.search(ligne):
                constats.append(Constat(
                    identifiant="SEC-003", gravite="P0",
                    chemin=relatif, ligne=numero,
                    titre="Bloc de cle privee au format PEM",
                    explication="Le fichier contient un en-tete de cle privee "
                                "PEM : la cle est lisible par tout porteur du "
                                "depot, et le reste dans l'historique.",
                    correction="retirer le bloc, regenerer la cle, et garder "
                               "les cles privees hors de Git."))
                break
    return constats


# ---------------------------------------------------------------------------
# SEC-004  Authentification qui s'ouvre quand le secret est absent        (P0)
# ---------------------------------------------------------------------------

_MOTIF_DEFINITION = re.compile(r"^\s*(?:async\s+)?def\s+(?P<nom>\w+)\s*\(")
_MOTIF_SI_VIDE = re.compile(r"^\s*if\s+not\s+(?P<variable>[A-Za-z_][\w.]*)\s*:\s*$")
_MOTIF_RETOUR_NU = re.compile(r"^\s*return\s*(?:None)?\s*$")
_MOTIF_VARIABLE_ENV = re.compile(
    r"(?P<nom>[A-Za-z_]\w*)\s*=\s*\(?\s*(?:str\s*\(\s*)?os\.(?:getenv|environ)")

MOTS_AUTHENTIFICATION = ("jeton", "token", "auth", "verifier")


def _est_fichier_d_api(contexte, relatif: str) -> bool:
    if not est_code_python(relatif):
        return False
    nom = nom_de(relatif)
    if nom in {"app.py", "main.py"} or nom.startswith(("api", "auth")):
        return True
    texte = contexte.texte(relatif)
    return "FastAPI" in texte or "APIRouter" in texte


def controle_authentification_ouverte(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not _est_fichier_d_api(contexte, relatif):
            continue
        variables_env = set(_MOTIF_VARIABLE_ENV.findall(contexte.texte(relatif)))
        if not variables_env:
            continue
        lignes = contexte.lignes(relatif)
        fonction = ""
        for index, ligne in enumerate(lignes):
            definition = _MOTIF_DEFINITION.match(ligne)
            if definition:
                fonction = definition.group("nom")
                continue
            if not fonction:
                continue
            if not any(mot in fonction.lower() for mot in MOTS_AUTHENTIFICATION):
                continue
            test = _MOTIF_SI_VIDE.match(ligne)
            if not test:
                continue
            variable = test.group("variable").split(".")[0]
            if variable not in variables_env:
                continue
            for suite in lignes[index + 1: index + 4]:
                if not _MOTIF_RETOUR_NU.match(suite):
                    continue
                constats.append(Constat(
                    identifiant="SEC-004", gravite="P0",
                    chemin=relatif, ligne=index + 1,
                    titre="Authentification fail-open dans " + fonction + "()",
                    explication="Quand la variable d'environnement " + variable +
                                " est vide, la fonction rend la main sans "
                                "erreur : l'API accepte alors toutes les "
                                "requetes. Secret oublie = porte ouverte.",
                    correction="lever une erreur au lieu de rendre la main : 401 "
                               "si le jeton est absent, 503 si la configuration "
                               "manque. L'absence de secret doit fermer le "
                               "service, pas l'ouvrir."))
                break
    return constats


# ---------------------------------------------------------------------------
# SEC-005  Donnees de sante versionnees                               (P0/P2)
# ---------------------------------------------------------------------------

DOSSIERS_DE_SORTIE = ("sortie", "output")
DOSSIERS_DE_DEMONSTRATION = ("exemples", "data")
MOTIFS_FICHIERS_SANTE = ("bundle_*.json", "*_patient*.json")


def _dossier_parent_parmi(relatif: str, noms):
    morceaux = relatif.split("/")[:-1]
    for position, morceau in enumerate(morceaux):
        if morceau.lower() in noms:
            return "/".join(morceaux[: position + 1])
    return None


def controle_donnees_sante(contexte) -> list:
    constats = []
    sorties = {}
    demonstrations = {}
    isoles = []
    for relatif in sorted(contexte.tous):
        if not contexte.versionne(relatif):
            continue
        nom = nom_de(relatif).lower()
        dossier_demo = _dossier_parent_parmi(relatif, DOSSIERS_DE_DEMONSTRATION)
        if dossier_demo:
            if nom.endswith(".json"):
                demonstrations[dossier_demo] = demonstrations.get(dossier_demo, 0) + 1
            continue
        dossier_sortie = _dossier_parent_parmi(relatif, DOSSIERS_DE_SORTIE)
        if dossier_sortie:
            sorties[dossier_sortie] = sorties.get(dossier_sortie, 0) + 1
        elif any(fnmatch.fnmatch(nom, motif) for motif in MOTIFS_FICHIERS_SANTE):
            isoles.append(relatif)
    for dossier, nombre in sorted(sorties.items()):
        constats.append(Constat(
            identifiant="SEC-005", gravite="P0", chemin=dossier,
            titre="Dossier de sortie versionne (" + str(nombre) + " fichier(s))",
            explication="Ce dossier recoit les Bundles et les rapports produits "
                        "par les echanges : donnees de sante nominatives, qui "
                        "n'ont rien a faire dans Git "
                        "(" + contexte.mention_git + ").",
            correction="ajouter sortie/ et output/ au .gitignore, puis "
                       "git rm -r --cached " + dossier))
    for relatif in isoles:
        constats.append(Constat(
            identifiant="SEC-005", gravite="P0", chemin=relatif,
            titre="Fichier de donnees de sante versionne",
            explication="Le nom correspond a un Bundle ou a un dossier patient "
                        "produit par l'echange, hors dossier de demonstration.",
            correction="sortir le fichier du depot (git rm --cached) et exclure "
                       "le motif, ou le deplacer dans exemples/ apres "
                       "pseudonymisation."))
    for dossier, nombre in sorted(demonstrations.items()):
        constats.append(Constat(
            identifiant="SEC-005", gravite="P2", chemin=dossier,
            titre="Jeu de demonstration versionne (" + str(nombre) + " JSON)",
            explication="Un dossier exemples/ ou data/ est un jeu de "
                        "demonstration assume ; il faut en revanche verifier "
                        "qu'il ne contient aucune donnee reelle de patient.",
            correction="relire le contenu : noms, CIN, IPP, dates de naissance "
                       "et telephones doivent etre inventes ou pseudonymises."))
    return constats


# ---------------------------------------------------------------------------
# SEC-006  docker-compose : base sans authentification, port publie      (P0)
# ---------------------------------------------------------------------------

IMAGES_DE_BASES = ("mongo", "mongodb", "postgres", "postgresql", "mysql",
                   "mariadb", "redis", "oracle")
PORTS_DE_BASES = {
    "27017": "MongoDB", "27018": "MongoDB", "5432": "PostgreSQL",
    "3306": "MySQL/MariaDB", "1433": "SQL Server", "1521": "Oracle",
    "6379": "Redis",
}
VARIABLES_AUTH_BASES = (
    "MONGO_INITDB_ROOT_USERNAME", "MONGO_INITDB_ROOT_PASSWORD",
    "MONGODB_INITDB_ROOT_USERNAME", "POSTGRES_PASSWORD", "POSTGRES_USER",
    "MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD", "MARIADB_ROOT_PASSWORD",
    "REDIS_PASSWORD", "ORACLE_PWD", "ORACLE_PASSWORD",
)
HOTES_LOCAUX = ("127.0.0.1", "localhost", "::1")

_MOTIF_PORT = re.compile(
    r"(?:(?P<hote>\d{1,3}(?:\.\d{1,3}){3}|localhost|\[?::1\]?):)?"
    r"(?P<publie>\d{2,5}):(?P<interne>\d{2,5})")


def _blocs_de_services(lignes: list) -> list:
    """Decoupe un docker-compose en services, sans dependre de PyYAML."""
    services = []
    indentation_services = None
    indentation_service = None
    courant = None
    for numero, ligne in enumerate(lignes, 1):
        nue = ligne.strip()
        if not nue or nue.startswith("#"):
            continue
        indentation = len(ligne) - len(ligne.lstrip())
        if nue == "services:":
            indentation_services = indentation
            continue
        if indentation_services is None:
            continue
        if indentation <= indentation_services:
            if courant:
                services.append(courant)
                courant = None
            indentation_service = None
            continue
        if indentation_service is None:
            indentation_service = indentation
        if indentation == indentation_service and nue.endswith(":"):
            if courant:
                services.append(courant)
            courant = {"nom": nue[:-1].strip(), "ligne": numero, "lignes": []}
            continue
        if courant is not None:
            courant["lignes"].append((indentation, nue, numero))
    if courant:
        services.append(courant)
    return services


def _cles_du_service(service: dict) -> dict:
    lignes = service["lignes"]
    if not lignes:
        return {}
    base = min(indentation for indentation, _, _ in lignes)
    cles = {}
    courante = None
    for indentation, nue, numero in lignes:
        if indentation == base and ":" in nue:
            cle, _, reste = nue.partition(":")
            courante = cle.strip()
            cles.setdefault(courante, []).append((reste.strip(), numero))
        elif courante is not None:
            cles[courante].append((nue, numero))
    return cles


def controle_docker_compose(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        nom = nom_de(relatif).lower()
        if not (nom.startswith(("docker-compose", "compose"))
                and nom.endswith((".yml", ".yaml"))):
            continue
        for service in _blocs_de_services(contexte.lignes(relatif)):
            cles = _cles_du_service(service)
            image = " ".join(valeur for valeur, _ in cles.get("image", []))
            etiquette = (service["nom"] + " " + image).lower()
            texte_service = " ".join(nue for _, nue, _ in service["lignes"])
            if any(re.search(r"(?<![a-z0-9_])" + re.escape(moteur) + r"(?![a-z0-9_])",
                             etiquette) for moteur in IMAGES_DE_BASES):
                a_une_auth = any(variable in texte_service
                                 for variable in VARIABLES_AUTH_BASES)
                if not a_une_auth and "env_file" not in cles:
                    constats.append(Constat(
                        identifiant="SEC-006", gravite="P0",
                        chemin=relatif, ligne=service["ligne"],
                        titre="Base de donnees sans authentification : service "
                              + service["nom"],
                        explication="Le service ne definit aucune variable "
                                    "d'authentification : la base demarre sans "
                                    "mot de passe et accepte toute connexion, "
                                    "donc toute lecture du dossier des patients.",
                        correction="definir MONGO_INITDB_ROOT_USERNAME et "
                                   "MONGO_INITDB_ROOT_PASSWORD (ou "
                                   "POSTGRES_PASSWORD selon le moteur) depuis le "
                                   ".env local, puis donner a l'API une URI "
                                   "authentifiee."))
            for valeur, numero in cles.get("ports", []):
                for trouve in _MOTIF_PORT.finditer(valeur):
                    interne = trouve.group("interne")
                    publie = trouve.group("publie")
                    moteur = PORTS_DE_BASES.get(interne) or PORTS_DE_BASES.get(publie)
                    if not moteur:
                        continue
                    hote = trouve.group("hote")
                    if hote and hote.strip("[]") in HOTES_LOCAUX:
                        continue
                    constats.append(Constat(
                        identifiant="SEC-006", gravite="P0",
                        chemin=relatif, ligne=numero,
                        titre="Port " + moteur + " publie sans restriction",
                        explication="Le port " + publie + " est publie sans le "
                                    "restreindre a la boucle locale : la base "
                                    "devient joignable depuis le reseau de "
                                    "l'hopital, voire au-dela.",
                        correction="ecrire 127.0.0.1:" + publie + ":" + interne +
                                   ", ou supprimer la publication : les autres "
                                   "services joignent la base par le reseau "
                                   "interne de Docker."))
    return constats


# ---------------------------------------------------------------------------
# SEC-007 / SEC-008  Dockerfile : execution en root, tests embarques     (P1)
# ---------------------------------------------------------------------------

_MOTIF_USER = re.compile(r"^\s*USER\s+(?P<utilisateur>\S+)", re.IGNORECASE)
_MOTIF_COPY = re.compile(r"^\s*COPY\s+(?P<arguments>.+)$", re.IGNORECASE)
SOURCES_TOTALES = {".", "./", "*.py", "./*.py"}


def _dockerfiles(contexte):
    for relatif in contexte.fichiers_contenu:
        nom = nom_de(relatif).lower()
        if (nom == "dockerfile" or nom.startswith("dockerfile.")
                or nom.endswith(".dockerfile")):
            yield relatif


def controle_dockerfile_root(contexte) -> list:
    constats = []
    for relatif in _dockerfiles(contexte):
        utilisateurs = []
        for ligne in contexte.lignes(relatif):
            trouve = _MOTIF_USER.match(ligne)
            if trouve:
                utilisateurs.append(trouve.group("utilisateur").lower())
        if any(utilisateur not in {"root", "0", "0:0", "root:root"}
               for utilisateur in utilisateurs):
            continue
        constats.append(Constat(
            identifiant="SEC-007", gravite="P1", chemin=relatif,
            titre="Conteneur execute en root",
            explication="Aucune directive USER non privilegiee : le processus de "
                        "l'API tourne en root dans le conteneur, et une faille "
                        "applicative devient une prise de controle de l'image "
                        "et des volumes montes.",
            correction="creer un compte dedie (RUN useradd --uid 10001 api) et "
                       "ajouter USER api avant CMD, apres avoir donne les droits "
                       "sur les dossiers ecrits par le service."))
    return constats


def controle_dockerfile_tests(contexte) -> list:
    constats = []
    for relatif in _dockerfiles(contexte):
        dossier = relatif.rsplit("/", 1)[0] if "/" in relatif else ""
        prefixe = dossier + "/" if dossier else ""
        tests = sorted(nom_de(chemin) for chemin in contexte.tous
                       if chemin.startswith(prefixe)
                       and "/" not in chemin[len(prefixe):]
                       and nom_de(chemin).startswith("test_")
                       and chemin.endswith(".py"))
        if not tests:
            continue
        for numero, ligne in enumerate(contexte.lignes(relatif), 1):
            trouve = _MOTIF_COPY.match(ligne)
            if not trouve:
                continue
            arguments = trouve.group("arguments").split("#", 1)[0].strip()
            morceaux = arguments.split()
            sources = morceaux[:-1] if len(morceaux) > 1 else morceaux
            if not any(source in SOURCES_TOTALES for source in sources):
                continue
            constats.append(Constat(
                identifiant="SEC-008", gravite="P1", chemin=relatif, ligne=numero,
                titre="L'image embarque les fichiers de test",
                explication="Cette copie emporte aussi " + ", ".join(tests[:3]) +
                            " : jetons factices, donnees d'essai et surface de "
                            "code inutile se retrouvent dans l'image livree.",
                correction="copier explicitement les modules du service, ou "
                           "exclure test_*.py et tests/ dans un .dockerignore."))
            break
    return constats


# ---------------------------------------------------------------------------
# SEC-009  Verification TLS desactivee                                   (P1)
# ---------------------------------------------------------------------------

_MOTIFS_TLS = (
    (re.compile(r"verify\s*=\s*False"),
     "verification du certificat desactivee"),
    (re.compile(r"ssl\._create_unverified_context"),
     "contexte SSL cree sans verification"),
    (re.compile(r"InsecureRequestWarning"),
     "avertissement TLS masque"),
)


def controle_tls_desactive(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not (est_code_python(relatif) or relatif.endswith((".sh", ".ipynb"))):
            continue
        for numero, ligne in lignes_de_code(contexte, relatif):
            for motif, libelle in _MOTIFS_TLS:
                if not motif.search(ligne):
                    continue
                constats.append(Constat(
                    identifiant="SEC-009", gravite="P1",
                    chemin=relatif, ligne=numero,
                    titre="TLS non verifie : " + libelle,
                    explication="Sans verification du certificat, un tiers place "
                                "sur le reseau peut se faire passer pour l'autre "
                                "hopital et lire les Bundles echanges.",
                    correction="fournir le certificat racine (parametre verify "
                               "de httpx, ou SEC_CA) au lieu de desactiver le "
                               "controle ; voir securite/client.py."))
    return constats


# ---------------------------------------------------------------------------
# SEC-010  Dependances non epinglees                                     (P1)
# ---------------------------------------------------------------------------


def controle_dependances_non_epinglees(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        nom = nom_de(relatif)
        if not (nom.startswith("requirements") and nom.endswith(".txt")):
            continue
        libres = []
        for numero, ligne in enumerate(contexte.lignes(relatif), 1):
            declaration = ligne.split("#", 1)[0].strip()
            if not declaration or declaration.startswith(("-", ".")):
                continue
            if "==" in declaration or "://" in declaration:
                continue
            libres.append((numero, re.split(r"[<>=!~\[;\s]", declaration)[0]))
        if not libres:
            continue
        constats.append(Constat(
            identifiant="SEC-010", gravite="P1",
            chemin=relatif, ligne=libres[0][0],
            titre=str(len(libres)) + " dependance(s) non epinglee(s)",
            explication="Les lignes sans == installent la derniere version "
                        "publiee : " + ", ".join(nom for _, nom in libres[:5]) +
                        (" ..." if len(libres) > 5 else "") + ". Deux postes "
                        "n'obtiennent pas le meme code, et une version "
                        "compromise entre sans etre vue.",
            correction="figer les versions (paquet==version, ou pip freeze) et "
                       "relancer les tests a chaque montee de version."))
    return constats


# ---------------------------------------------------------------------------
# SEC-011  CORS ouvert                                                   (P1)
# ---------------------------------------------------------------------------

_MOTIFS_CORS = (
    re.compile(r"allow_origins\s*=\s*\[?\s*[\"']\*[\"']"),
    re.compile(r"allow_origin_regex\s*=\s*[\"'][^\"']*\.\*"),
)
_MOTIF_IDENTIFIANTS_CORS = re.compile(r"allow_credentials\s*=\s*True")


def controle_cors_ouvert(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not est_code_python(relatif):
            continue
        lignes = contexte.lignes(relatif)
        for numero, ligne in lignes_de_code(contexte, relatif):
            if not any(motif.search(ligne) for motif in _MOTIFS_CORS):
                continue
            voisinage = "\n".join(lignes[max(0, numero - 6): numero + 6])
            avec_identifiants = bool(_MOTIF_IDENTIFIANTS_CORS.search(voisinage))
            constats.append(Constat(
                identifiant="SEC-011", gravite="P1", chemin=relatif, ligne=numero,
                titre="CORS ouvert a toutes les origines" +
                      (" avec envoi des identifiants" if avec_identifiants else ""),
                explication="N'importe quelle page web peut appeler l'API depuis "
                            "le navigateur d'un soignant" +
                            (", en reutilisant ses identifiants : le joker et "
                             "allow_credentials=True sont incompatibles."
                             if avec_identifiants else "."),
                correction="lister les origines reellement attendues ; un "
                           "echange serveur a serveur n'a besoin d'aucun CORS."))
    return constats


# ---------------------------------------------------------------------------
# SEC-012  Mode debug ou rechargement automatique                        (P1)
# ---------------------------------------------------------------------------

_MOTIFS_DEBUG = (
    (re.compile(r"\bdebug\s*=\s*True\b"), "debug"),
    (re.compile(r"\breload\s*=\s*True\b"), "reload"),
)


def controle_mode_debug(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not est_code_python(relatif) or est_fichier_de_test(relatif):
            continue
        for numero, ligne in lignes_de_code(contexte, relatif):
            for motif, parametre in _MOTIFS_DEBUG:
                if not motif.search(ligne):
                    continue
                constats.append(Constat(
                    identifiant="SEC-012", gravite="P1",
                    chemin=relatif, ligne=numero,
                    titre="Parametre de developpement actif : " + parametre,
                    explication="Le mode debug renvoie la trace d'appel et des "
                                "extraits de donnees a l'appelant ; le "
                                "rechargement automatique surveille les "
                                "fichiers et n'a pas sa place en service.",
                    correction="retirer le parametre, ou le piloter par une "
                               "variable d'environnement qui vaut faux par "
                               "defaut."))
    return constats


# ---------------------------------------------------------------------------
# SEC-013  Ecoute sur toutes les interfaces                           (P1/P2)
# ---------------------------------------------------------------------------

_MOTIF_TOUTES_INTERFACES = re.compile(r"(?<![\d.])0\.0\.0\.0(?![\d.])")
_MOTIF_TLS_VOISIN = re.compile(
    r"--ssl-(?:keyfile|certfile)|ssl_(?:keyfile|certfile)|--ssl\b", re.IGNORECASE)
EXTENSIONS_CONFIGURATION = (".yml", ".yaml", ".sh", ".cfg", ".ini", ".toml",
                            ".service", ".http", ".conf", ".ps1", ".bat")


def _tls_dans_le_voisinage(lignes: list, numero: int) -> bool:
    """Un --host joker avec TLS sur la meme commande reste defendable."""
    debut = max(0, numero - 4)
    return bool(_MOTIF_TLS_VOISIN.search("\n".join(lignes[debut: numero + 4])))


def controle_ecoute_toutes_interfaces(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        nom = nom_de(relatif).lower()
        est_configuration = (relatif.lower().endswith(EXTENSIONS_CONFIGURATION)
                             or nom == "dockerfile" or nom.startswith("dockerfile."))
        if est_code_python(relatif) or est_configuration:
            source = list(lignes_de_code(contexte, relatif))
            dans_du_code = True
        elif est_document(relatif):
            source = list(enumerate(contexte.lignes(relatif), 1))
            dans_du_code = False
        else:
            continue
        lignes = contexte.lignes(relatif)
        for numero, ligne in source:
            if dans_du_code and ligne.lstrip().startswith("#"):
                continue
            if not _MOTIF_TOUTES_INTERFACES.search(ligne):
                continue
            if est_systeme_fhir(ligne):
                continue                       # identifiant FHIR, pas une adresse
            if not dans_du_code:
                constats.append(Constat(
                    identifiant="SEC-013", gravite="P2",
                    chemin=relatif, ligne=numero,
                    titre="Documentation : commande d'ecoute sans restriction",
                    explication="La documentation conseille une adresse "
                                "d'ecoute joker : la consigne sera suivie telle "
                                "quelle, sans TLS ni filtrage.",
                    correction="completer la consigne : adresse joker seulement "
                               "derriere TLS et pare-feu, 127.0.0.1 sinon."))
            elif _tls_dans_le_voisinage(lignes, numero):
                constats.append(Constat(
                    identifiant="SEC-013", gravite="P2",
                    chemin=relatif, ligne=numero,
                    titre="Ecoute sur toutes les interfaces, mais sous TLS",
                    explication="Le service ecoute sur chaque interface ; TLS "
                                "est configure sur la meme commande, ce qui "
                                "rend l'exposition acceptable. Reste a limiter "
                                "les adresses sources.",
                    correction="verifier le pare-feu : n'ouvrir le port qu'a "
                               "l'adresse de l'autre etablissement, et "
                               "restreindre la publication du port."))
            else:
                constats.append(Constat(
                    identifiant="SEC-013", gravite="P1",
                    chemin=relatif, ligne=numero,
                    titre="Le service ecoute sur toutes les interfaces",
                    explication="L'adresse d'ecoute joker expose l'API sur "
                                "chaque carte reseau. Ce n'est acceptable "
                                "qu'avec TLS, une authentification et un "
                                "pare-feu qui limite les adresses sources.",
                    correction="ecouter sur 127.0.0.1 en developpement ; pour "
                               "l'echange entre hopitaux, servir en HTTPS et "
                               "n'ouvrir le port qu'a l'autre etablissement."))
    return constats


# ---------------------------------------------------------------------------
# SEC-014  Valeur de vrai secret dans un .env.example                    (P1)
# ---------------------------------------------------------------------------

_MOTIF_AFFECTATION_ENV = re.compile(
    r"^\s*(?:export\s+)?(?P<cle>[A-Za-z_][\w.]*)\s*=\s*(?P<valeur>.*)$")
_MOTIF_HOTE_PORT = re.compile(r"^[\w.\-]+:\d{1,5}(/.*)?$")
_MOTIF_COURRIEL = re.compile(r"^[\w.\-]+@[\w.\-]+$")
_MOTIF_CONSTANTE = re.compile(r"^(true|false|oui|non|yes|no|strict|local|0|1)$",
                              re.IGNORECASE)


def _valeur_est_une_adresse(valeur: str) -> bool:
    if "://" in valeur or valeur.startswith(("/", "./", "\\")):
        return True
    if _MOTIF_HOTE_PORT.match(valeur) or _MOTIF_COURRIEL.match(valeur):
        return True
    if valeur.isdigit():                                 # un port, une duree
        return True
    return est_systeme_fhir(valeur)


def controle_env_exemple(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not est_exemple_env(nom_de(relatif)):
            continue
        for numero, ligne in enumerate(contexte.lignes(relatif), 1):
            if ligne.strip().startswith("#"):
                continue
            trouve = _MOTIF_AFFECTATION_ENV.match(ligne)
            if not trouve:
                continue
            valeur = trouve.group("valeur").split("#", 1)[0].strip().strip("\"'")
            if len(valeur) <= 8 or " " in valeur:
                continue
            if _valeur_est_un_exemple(valeur) or _valeur_est_une_adresse(valeur):
                continue
            if _MOTIF_CONSTANTE.match(valeur):
                continue
            constats.append(Constat(
                identifiant="SEC-014", gravite="P1", chemin=relatif, ligne=numero,
                titre="Le gabarit publie une valeur reelle : " + trouve.group("cle"),
                explication="La valeur de " + trouve.group("cle") + " fait " +
                            str(len(valeur)) + " caracteres et ne porte aucune "
                            "marque d'exemple : ce gabarit etant versionne, "
                            "c'est un identifiant de connexion publie.",
                correction="remplacer par un marqueur explicite "
                           "(A_REMPLACER_hors_depot) et changer le mot de passe "
                           "reel s'il a deja servi."))
    return constats


# ---------------------------------------------------------------------------
# SEC-015  Couche de securite non branchee sur l'application             (P1)
# ---------------------------------------------------------------------------

_MOTIF_APPLICATION = re.compile(r"^\s*(?P<nom>\w+)\s*=\s*FastAPI\s*\(", re.MULTILINE)


def controle_securite_non_branchee(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not est_code_python(relatif) or est_fichier_de_test(relatif):
            continue
        texte = contexte.texte(relatif)
        trouve = _MOTIF_APPLICATION.search(texte)
        if not trouve or "installer_securite(" in texte:
            continue
        constats.append(Constat(
            identifiant="SEC-015", gravite="P1", chemin=relatif,
            ligne=texte[: trouve.start()].count("\n") + 1,
            titre="Couche de securite non branchee sur l'application",
            explication="L'application FastAPI " + trouve.group("nom") + " est "
                        "creee sans appeler installer_securite() : ni journal "
                        "d'audit, ni en-tetes de securite, ni limitation de "
                        "debit, ni exigence de TLS. Les deux hopitaux "
                        "n'appliquent alors pas les memes regles.",
            correction="juste apres la creation de l'application : "
                       "from securite import installer_securite, puis "
                       "installer_securite(app, service=...) ; voir "
                       "securite/README.md."))
    return constats


# ---------------------------------------------------------------------------
# SEC-016  Route FastAPI sans protection                                 (P1)
# ---------------------------------------------------------------------------

# /auth/connexion et /auth/renouvellement : points d'entree de la session du
# personnel, sans jeton par construction ; proteges par le debit et le verrouillage.
CHEMINS_PUBLICS = ("/health", "/metadata", "/docs", "/redoc", "/openapi.json",
                   "/auth/connexion", "/auth/renouvellement")
_MOTIF_ROUTE = re.compile(
    r"^\s*@(?P<objet>\w+)\.(?P<verbe>get|post|put|delete|patch)\s*\(")
_MOTIF_CHEMIN_ROUTE = re.compile(r"[\"'](?P<route>/[^\"']*)[\"']")


def _declaration_de_route(lignes: list, index: int) -> str:
    """Decorateur complet (parentheses equilibrees) puis signature de la vue.

    Les decorateurs du projet tiennent sur plusieurs lignes : se limiter a la
    ligne suivante donnerait de faux constats sur des routes bien protegees.
    """
    morceaux = []
    profondeur = 0
    position = index
    while position < len(lignes):
        ligne = lignes[position]
        morceaux.append(ligne)
        profondeur += ligne.count("(") - ligne.count(")")
        position += 1
        if profondeur <= 0:
            break
    while position < len(lignes) and lignes[position].strip().startswith("@"):
        morceaux.append(lignes[position])
        position += 1
    profondeur = 0
    debut = position
    while position < len(lignes):
        ligne = lignes[position]
        morceaux.append(ligne)
        profondeur += ligne.count("(") - ligne.count(")")
        position += 1
        if profondeur <= 0 and position > debut:
            break
    return "\n".join(morceaux)


def controle_routes_non_protegees(contexte) -> list:
    constats = []
    for relatif in contexte.fichiers_contenu:
        if not est_code_python(relatif) or est_fichier_de_test(relatif):
            continue
        lignes = contexte.lignes(relatif)
        for index, ligne in enumerate(lignes):
            trouve = _MOTIF_ROUTE.match(ligne)
            if not trouve:
                continue
            declaration = _declaration_de_route(lignes, index)
            chemin_route = _MOTIF_CHEMIN_ROUTE.search(declaration)
            route = chemin_route.group("route") if chemin_route else "?"
            if route in CHEMINS_PUBLICS:
                continue
            if "dependencies=" in declaration or "Depends(" in declaration:
                continue
            constats.append(Constat(
                identifiant="SEC-016", gravite="P1",
                chemin=relatif, ligne=index + 1,
                titre="Route sans protection : " + trouve.group("verbe").upper()
                      + " " + route,
                explication="La declaration ne porte ni dependencies= ni "
                            "Depends() : la route n'exige ni jeton ni portee, "
                            "alors qu'elle n'est pas dans la liste publique "
                            "(/health, /metadata, /docs, /redoc, /openapi.json).",
                correction="ajouter dependencies=[Depends(exiger_portee(...))] "
                           "sur la route, avec la portee la plus etroite qui "
                           "suffit a son usage."))
    return constats


# ---------------------------------------------------------------------------
# SEC-017  Chainage du journal de securite                            (P1/P2)
# ---------------------------------------------------------------------------


def _charger_verifier_chaine(contexte):
    """Importe securite.audit.verifier_chaine sans faire echouer l'audit."""
    try:
        racine = str(contexte.racine)
        if racine not in sys.path:
            sys.path.insert(0, racine)
        from securite.audit import verifier_chaine
        return verifier_chaine
    except ImportError:
        return None
    except Exception:                  # package present mais inutilisable
        return None


def controle_journal_audit(contexte) -> list:
    dossier = contexte.racine / "journaux"
    try:
        journaux = sorted(dossier.glob("securite-*.jsonl")) if dossier.is_dir() else []
    except OSError:
        journaux = []
    if not journaux:
        return [Constat(
            identifiant="SEC-017", gravite="P2", chemin="journaux/",
            titre="Aucun journal de securite enregistre",
            explication="Aucun fichier journaux/securite-*.jsonl : information, "
                        "pas de defaut. Le journal se cree au premier appel "
                        "recu par une API.",
            correction="lancer une API, appeler une route protegee, puis "
                       "relancer cet audit pour verifier le chainage.")]
    verifier_chaine = _charger_verifier_chaine(contexte)
    if verifier_chaine is None:
        return [Constat(
            identifiant="SEC-017", gravite="P2", chemin="securite/audit.py",
            titre="Chainage du journal non verifie",
            explication="Le module securite.audit n'est pas importable depuis "
                        "ce poste : le chainage des journaux n'a pas pu etre "
                        "controle.",
            correction="relancer l'audit depuis la racine du depot, avec "
                       "l'interpreteur du projet.")]
    constats = []
    for journal in journaux:
        relatif = journal.relative_to(contexte.racine).as_posix()
        try:
            rapport = verifier_chaine(journal)
        except Exception as erreur:
            constats.append(Constat(
                identifiant="SEC-017", gravite="P2", chemin=relatif,
                titre="Journal de securite illisible",
                explication="La verification a echoue (" + type(erreur).__name__ + ").",
                correction="verifier les droits de lecture et l'encodage du fichier."))
            continue
        if rapport.get("intact"):
            constats.append(Constat(
                identifiant="SEC-017", gravite="P2", chemin=relatif,
                titre="Journal intact (" + str(rapport.get("lignes", 0)) + " lignes)",
                explication="Le chainage par empreintes est verifie de bout en "
                            "bout : aucune entree n'a ete retiree ni modifiee.",
                correction="aucune action ; conserver une copie hors du poste."))
        else:
            constats.append(Constat(
                identifiant="SEC-017", gravite="P1", chemin=relatif,
                ligne=rapport.get("premiere_rupture"),
                titre="Chainage du journal de securite rompu",
                explication="Le chainage s'interrompt a la ligne " +
                            str(rapport.get("premiere_rupture")) + " : une "
                            "entree a ete modifiee, retiree, ou ecrite par un "
                            "autre processus. Le journal ne prouve plus rien.",
                correction="archiver le fichier en l'etat comme piece, repartir "
                           "d'un journal neuf, et chercher la cause (edition "
                           "manuelle, deux services sur le meme fichier)."))
    return constats


# ---------------------------------------------------------------------------
# SEC-018 / SEC-019 / SEC-020  Documents, .gitignore, fichiers lourds    (P2)
# ---------------------------------------------------------------------------

DOCUMENTS_ATTENDUS = (
    ("SECURITY.md",
     "a qui signaler une faille, et sous quel delai"),
    ("docs/securite/politique-securite.md",
     "regles d'acces, portees, duree de conservation"),
    ("docs/securite/procedure-secrets.md",
     "comment creer, transmettre et renouveler un jeton"),
    ("docs/securite/tls-https.md",
     "certificats, verification, mise en service HTTPS"),
    ("securite/README.md",
     "mode d'emploi du package pour les deux equipes"),
)


def controle_documents_securite(contexte) -> list:
    constats = []
    for relatif, objet in DOCUMENTS_ATTENDUS:
        if (contexte.racine / relatif).exists():
            continue
        constats.append(Constat(
            identifiant="SEC-018", gravite="P2", chemin=relatif,
            titre="Document de securite manquant",
            explication="Attendu : " + objet + ". Sans ce document, la mesure "
                        "technique existe mais personne ne sait l'appliquer ni "
                        "la verifier.",
            correction="rediger " + relatif + " (une page suffit) et le citer "
                       "depuis le README du projet."))
    return constats


def controle_gitignore_racine(contexte) -> list:
    if (contexte.racine / ".gitignore").exists():
        return []
    return [Constat(
        identifiant="SEC-019", gravite="P2", chemin=".gitignore",
        titre="Pas de .gitignore a la racine du depot",
        explication="Les exclusions ne vivent que dans les sous-dossiers : tout "
                    "nouveau dossier (journaux/, securite/jetons_locaux/, "
                    "sortie/) part par defaut dans Git.",
        correction="creer un .gitignore a la racine couvrant .env, les cles, "
                   "les journaux et les donnees generees.")]


def controle_fichiers_volumineux(contexte) -> list:
    constats = []
    for relatif, taille in sorted(contexte.tous.items()):
        if taille <= TAILLE_VOLUMINEUSE or not contexte.versionne(relatif):
            continue
        constats.append(Constat(
            identifiant="SEC-020", gravite="P2", chemin=relatif,
            titre="Fichier volumineux versionne (" + taille_lisible(taille) + ")",
            explication="Un fichier de cette taille dans Git est rarement un "
                        "livrable : souvent un export de base, un jeu de "
                        "donnees ou un binaire. Il reste dans l'historique "
                        "pour toujours.",
            correction="verifier la nature du fichier ; s'il s'agit de donnees "
                       "ou d'un outil telecharge, l'exclure du depot et "
                       "documenter comment l'obtenir."))
    return constats


# ---------------------------------------------------------------------------
# Registre central des controles
# ---------------------------------------------------------------------------

CONTROLES = (
    ("SEC-001", "fichiers .env versionnes", controle_env_versionne),
    ("SEC-002", "secrets en dur", controle_secrets_en_dur),
    ("SEC-003", "cles privees dans le depot", controle_cles_privees),
    ("SEC-004", "authentification fail-open", controle_authentification_ouverte),
    ("SEC-005", "donnees de sante versionnees", controle_donnees_sante),
    ("SEC-006", "docker-compose et bases de donnees", controle_docker_compose),
    ("SEC-007", "conteneur execute en root", controle_dockerfile_root),
    ("SEC-008", "tests embarques dans l'image", controle_dockerfile_tests),
    ("SEC-009", "verification TLS desactivee", controle_tls_desactive),
    ("SEC-010", "dependances non epinglees", controle_dependances_non_epinglees),
    ("SEC-011", "CORS ouvert", controle_cors_ouvert),
    ("SEC-012", "mode debug", controle_mode_debug),
    ("SEC-013", "ecoute sur toutes les interfaces", controle_ecoute_toutes_interfaces),
    ("SEC-014", "gabarits .env.example", controle_env_exemple),
    ("SEC-015", "couche de securite non branchee", controle_securite_non_branchee),
    ("SEC-016", "routes non protegees", controle_routes_non_protegees),
    ("SEC-017", "journal de securite", controle_journal_audit),
    ("SEC-018", "documents de securite", controle_documents_securite),
    ("SEC-019", ".gitignore de la racine", controle_gitignore_racine),
    ("SEC-020", "fichiers volumineux", controle_fichiers_volumineux),
)


def _constats_de_parcours(contexte) -> list:
    if not contexte.incidents:
        return []
    chemin, message = contexte.incidents[0]
    return [Constat(
        identifiant="SEC-000", gravite="P2", chemin=chemin,
        titre=str(len(contexte.incidents)) + " fichier(s) non examinable(s)",
        explication="Lecture impossible (droits, nom trop long, encodage) ; "
                    "premiere erreur : " + message[:160],
        correction="verifier ces fichiers a la main, ou les exclure du depot.")]


def _n_est_qu_un_systeme_fhir(contexte, constat) -> bool:
    """Garde-fou : une ligne qui n'est qu'une URL de systeme FHIR
    (loinc.org, snomed.info/sct, terminology.hl7.org, hl7.org/fhir) est un
    identifiant de vocabulaire et ne peut jamais fonder un constat.
    """
    if not constat.chemin or not constat.ligne:
        return False
    ligne = contexte.ligne_brute(constat.chemin, constat.ligne)
    if not ligne or not est_systeme_fhir(ligne):
        return False
    nue = ligne.strip().rstrip(",").strip().strip("\"'")
    return bool(re.match(r"^(?:https?://|urn:)[\w./\-:+#]*$", nue))


def executer(contexte, trace: bool = False) -> list:
    """Lance tous les controles ; une erreur dans l'un n'arrete pas les autres."""
    constats = []
    for identifiant, intitule, controle in CONTROLES:
        try:
            constats.extend(controle(contexte) or [])
        except Exception as erreur:                 # robustesse avant tout
            if trace:
                traceback.print_exc()
            constats.append(Constat(
                identifiant=identifiant, gravite="P2",
                titre="Controle interrompu : " + intitule,
                explication="Le controle a leve " + type(erreur).__name__ +
                            " : " + str(erreur)[:200] + ". Les autres controles "
                            "ont tourne normalement.",
                correction="relancer avec --trace pour la pile d'appel, et "
                           "traiter ce controle comme non verifie."))
    constats.extend(_constats_de_parcours(contexte))
    constats = [constat for constat in constats
                if not _n_est_qu_un_systeme_fhir(contexte, constat)]
    constats.sort(key=lambda constat: constat.cle_de_tri())
    return constats


def resumer(constats: list) -> dict:
    resume = dict((gravite, 0) for gravite in GRAVITES)
    for constat in constats:
        resume[constat.gravite] = resume.get(constat.gravite, 0) + 1
    return resume


def code_de_sortie(resume: dict) -> int:
    if resume.get("P0"):
        return 2
    if resume.get("P1"):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Restitution
# ---------------------------------------------------------------------------


def ligne_de_resume(resume: dict) -> str:
    return "  ".join(gravite + ": " + str(resume.get(gravite, 0))
                     for gravite in GRAVITES)


def _plier(texte: str, largeur: int = 84, retrait: str = " " * 10) -> list:
    lignes = []
    courante = ""
    for mot in texte.split():
        if courante and len(courante) + 1 + len(mot) > largeur:
            lignes.append(retrait + courante)
            courante = mot
        else:
            courante = (courante + " " + mot).strip()
    if courante:
        lignes.append(retrait + courante)
    return lignes


def rendre_texte(contexte, constats: list, resume: dict) -> str:
    sortie = ["Audit de securite  -  " + str(contexte.racine),
              "Depot Git : " + ("oui" if contexte.depot_git else "non")
              + "  (" + contexte.mention_git + ")",
              "Fichiers examines : " + str(len(contexte.fichiers))
              + " sur " + str(len(contexte.tous)) + " presents",
              ""]
    for gravite in GRAVITES:
        lot = [constat for constat in constats if constat.gravite == gravite]
        sortie.append(gravite + " - " + LIBELLE_GRAVITE[gravite]
                      + " (" + str(len(lot)) + ")")
        if not lot:
            sortie.append("     aucun constat.")
            sortie.append("")
            continue
        for constat in lot:
            emplacement = constat.chemin
            if constat.ligne:
                emplacement += ":" + str(constat.ligne)
            sortie.append("  [" + constat.identifiant + "] " + constat.titre)
            if emplacement:
                sortie.append("          " + emplacement)
            sortie.extend(_plier(constat.explication))
            sortie.extend(_plier("Correction : " + constat.correction))
            sortie.append("")
    sortie.append("Resume : " + ligne_de_resume(resume))
    if resume.get("P0"):
        sortie.append("Verdict : au moins un constat bloquant, depot a ne pas publier.")
    elif resume.get("P1"):
        sortie.append("Verdict : pas de constat bloquant ; durcissement a terminer.")
    else:
        sortie.append("Verdict : aucun constat bloquant ni important.")
    return "\n".join(sortie)


def rendre_json(contexte, constats: list, resume: dict) -> str:
    charge = {
        "horodatage": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "racine": str(contexte.racine),
        "depot_git": contexte.depot_git,
        "fichiers_examines": len(contexte.fichiers),
        "constats": [constat.vers_dict() for constat in constats],
        "resume": resume,
        "code_de_sortie": code_de_sortie(resume),
    }
    return json.dumps(charge, indent=2, ensure_ascii=False)


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--racine", type=Path, default=RACINE_PAR_DEFAUT)
    analyseur.add_argument("--json", action="store_true", dest="format_json")
    analyseur.add_argument("--trace", action="store_true")
    options = analyseur.parse_args(argv)
    contexte = Contexte(options.racine)
    constats = executer(contexte, trace=options.trace)
    resume = resumer(constats)
    rapport = (rendre_json(contexte, constats, resume) if options.format_json
               else rendre_texte(contexte, constats, resume))
    print(rapport)
    return code_de_sortie(resume)


if __name__ == "__main__":
    raise SystemExit(main())
