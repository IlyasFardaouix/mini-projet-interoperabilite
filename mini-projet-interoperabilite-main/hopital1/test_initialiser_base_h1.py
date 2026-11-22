"""Decoupage des scripts SQL : un commentaire apres le `;` ne doit pas fusionner deux instructions."""
from pathlib import Path

import initialiser_base_h1 as init

ICI = Path(init.__file__).parent


def test_commentaire_apres_point_virgule_ne_fusionne_pas():
    sql = "CREATE TABLE a (x NUMBER);   -- note\nCREATE INDEX ia ON a(x);\n"
    assert list(init.instructions(sql)) == ["CREATE TABLE a (x NUMBER)", "CREATE INDEX ia ON a(x)"]


def test_point_virgule_dans_une_chaine_et_commentaire_dans_une_chaine():
    sql = "INSERT INTO t VALUES ('a -- b');\n"
    assert list(init.instructions(sql)) == ["INSERT INTO t VALUES ('a -- b')"]


def test_scripts_du_depot_une_instruction_par_ordre_ddl():
    for script in (*init.SCRIPTS, "donnees_demo_h1.sql"):
        for sql in init.instructions((ICI / script).read_text(encoding="utf-8")):
            if sql.lstrip().upper().startswith(("BEGIN", "DECLARE")):
                continue
            assert sum(sql.upper().count(k) for k in ("CREATE TABLE", "CREATE INDEX", "INSERT INTO", "ALTER TABLE")) <= 1, sql[:80]
            assert not sql.rstrip().endswith(";")
