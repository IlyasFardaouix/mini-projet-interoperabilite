"""Refuse les fichiers sensibles présents dans l'index Git avant un commit."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args: str) -> bytes:
    resultat = subprocess.run(["git", *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)
    return resultat.stdout


def interdit(chemin: str) -> bool:
    chemin = chemin.replace("\\", "/")
    morceaux = PurePosixPath(chemin).parts
    nom = morceaux[-1].lower()
    if morceaux[0] == "archive":
        return True
    if any(p in {".venv", "venv", "__pycache__", ".pytest_cache",
                 "jetons_locaux", "certificats", "comptes", "journaux", "sortie", "output"}
           for p in morceaux):
        return True
    if nom == "registre_jetons.json":
        return True
    if (nom == ".env" or nom.startswith(".env.") or nom.endswith(".env")) \
            and nom not in {".env.example", ".env.sample", ".env.template"}:
        return True
    return nom.endswith((".key", ".pem", ".p12", ".pfx", ".sqlite", ".db"))


def controler() -> list[str]:
    chemins = [p.decode("utf-8", "surrogateescape") for p in
               git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT").split(b"\0")
               if p]
    erreurs = []
    for chemin in chemins:
        if interdit(chemin):
            erreurs.append(f"{chemin}: chemin sensible")
            continue
        try:
            contenu = git("show", f":{chemin}")
        except subprocess.CalledProcessError:
            erreurs.append(f"{chemin}: contenu de l'index illisible")
            continue
        if re.search(rb"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", contenu):
            erreurs.append(f"{chemin}: clé privée détectée")
        if PurePosixPath(chemin).name.lower() in {".env.example", ".env.sample", ".env.template"}:
            for numero, ligne in enumerate(contenu.decode("utf-8", "replace").splitlines(), 1):
                correspondance = re.match(
                    r"^\s*(?:ORACLE_PWD|H1_API_TOKEN|H2_TOKEN|MONGO_MOT_DE_PASSE|"
                    r"SEC_JWT_SECRET|SEC_SEL_AUDIT)\s*=\s*(.*)$", ligne)
                if not correspondance:
                    continue
                valeur = correspondance.group(1).strip().strip('"\'')
                if valeur and not re.search(r"A_REMPLACER|REMPLACER|EXEMPLE|EXAMPLE|^<|^\$\{",
                                            valeur, re.IGNORECASE):
                    erreurs.append(f"{chemin}:{numero}: valeur potentiellement réelle")
    return erreurs


def main() -> int:
    try:
        erreurs = controler()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Vérification des fichiers préparés impossible : {exc}", file=sys.stderr)
        return 1
    for erreur in erreurs:
        print(f"Commit refusé : {erreur}", file=sys.stderr)
    return int(bool(erreurs))


if __name__ == "__main__":
    raise SystemExit(main())
