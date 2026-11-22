"""Cree (ou recree) la base Oracle de H1 : tables de base, retour, consentement, jeu de demo.

    python initialiser_base_h1.py              cree les tables manquantes (schema_base, retour, consentement)
    python initialiser_base_h1.py --donnees    ajoute le jeu de demonstration fictif (P1-0106, P1-0108)
    python initialiser_base_h1.py --reset      SUPPRIME toutes les tables H1 puis les recree (base de TEST seulement)

Connexion : ORACLE_USER, ORACLE_PWD, ORACLE_DSN (fichier .env). Les scripts .sql sont ceux du depot : les
executer ici ou a la main (DBeaver, SQL*Plus) donne le meme resultat.
"""
from __future__ import annotations

import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
SCRIPTS = ("schema_base_h1.sql", "schema_retour_h1.sql", "schema_consentement_h1.sql")
TABLES = ("journal_echange", "compte_rendu", "etude_imagerie", "resultat_ophtalmo", "mesure",
          "diagnostic", "allergie", "consentement", "sejour", "patient")      # ordre de suppression


def _sans_commentaire(ligne: str) -> str:
    """Retire un commentaire `-- ...` en fin de ligne (hors guillemets simples), puis les espaces de fin."""
    dans_chaine = False
    for i, c in enumerate(ligne):
        if c == "'":
            dans_chaine = not dans_chaine
        elif not dans_chaine and ligne.startswith("--", i):
            return ligne[:i].rstrip()
    return ligne.rstrip()


def instructions(texte: str):
    """Decoupe un script Oracle : `;` ferme une instruction simple, une ligne `/` ferme un bloc PL/SQL.
    Un commentaire apres le `;` (`);   -- note`) est ignore : sans cela deux instructions seraient fusionnees."""
    tampon, bloc = [], False
    for ligne in texte.splitlines():
        brut = ligne.strip()
        if not tampon and (not brut or brut.startswith("--")):
            continue
        if not tampon:
            bloc = brut.upper().startswith(("DECLARE", "BEGIN"))
        if brut == "/":
            yield "\n".join(tampon)
            tampon, bloc = [], False
            continue
        code = ligne if bloc else _sans_commentaire(ligne)
        tampon.append(code)
        if not bloc and code.endswith(";"):
            yield "\n".join(tampon).rstrip().removesuffix(";")
            tampon = []
    if tampon and "\n".join(tampon).strip():
        yield "\n".join(tampon).rstrip().removesuffix(";")


def executer_script(conn, chemin) -> int:
    """Execute un script ; renvoie le nombre d'instructions. Les lignes de commentaire seules sont ignorees."""
    n = 0
    with conn.cursor() as cur:
        for sql in instructions(Path(chemin).read_text(encoding="utf-8")):
            cur.execute(sql)
            n += 1
    conn.commit()
    return n


def supprimer_tables(conn) -> None:
    import oracledb
    with conn.cursor() as cur:
        for table in TABLES:
            try:
                cur.execute(f"DROP TABLE {table} CASCADE CONSTRAINTS PURGE")
            except oracledb.DatabaseError as exc:
                if "ORA-00942" not in str(exc):          # table inexistante : rien a supprimer
                    raise
    conn.commit()


def creer_schema(conn) -> None:
    for script in SCRIPTS:
        executer_script(conn, ICI / script)


def main(argv: list[str]) -> int:
    import oracle_repo as repo
    with repo.connexion() as conn:
        if "--reset" in argv:
            supprimer_tables(conn)
        existantes = {l[0].lower() for l in conn.cursor().execute("SELECT table_name FROM user_tables")}
        if "patient" not in existantes:
            creer_schema(conn)
            print("Schema cree.")
        else:
            print("Tables deja presentes : schema inchange (utiliser --reset sur une base de test pour repartir de zero).")
        if "--donnees" in argv:
            executer_script(conn, ICI / "donnees_demo_h1.sql")
            print("Jeu de demonstration charge.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))