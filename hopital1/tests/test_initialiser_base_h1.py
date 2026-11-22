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


def test_noms_des_patients_de_demonstration_sont_tous_differents():
    """Aucun nom de famille repete dans H1, et aucun en commun avec la clinique (sauf les cas d'identite voulus)."""
    import json
    import re
    sql = (init.ICI / "donnees_demo_h1.sql").read_text(encoding="utf-8")
    noms = re.findall(r"INSERT INTO patient .*?VALUES \('P1-\d+', '([^']+)'", sql, flags=re.S)
    assert len(noms) >= 8 and len(noms) == len(set(noms)), noms
    h2 = {p["last_name"] for p in json.load(open(init.ICI.parent / "hopital2" / "data" / "patients_h2.json", encoding="utf-8"))}
    voulus = {"Alaoui", "Idrissi"}          # S1 et D1 : meme personne des deux cotes (identite a rapprocher)
    assert not (set(noms) & h2) - voulus, set(noms) & h2
