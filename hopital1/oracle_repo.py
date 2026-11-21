"""
Accès à la base Oracle H1 : lecture d'un dossier (aller) et écriture des lignes
reçues (retour). C'est le SEUL fichier qui parle à Oracle.
"""
import json
import os

import config as C
import fhir_to_h1 as RET
import h1_to_fhir as ALL

ORDRE_TABLES = [("patient", "ipp"), ("sejour", "id_sejour"), ("diagnostic", "id_diagnostic"),
                ("mesure", "id_mesure"), ("etude_imagerie", "id_etude"),
                ("resultat_ophtalmo", "id_resultat"), ("compte_rendu", "id_cr")]


def connexion():
    import oracledb
    from dotenv import load_dotenv
    load_dotenv()
    return oracledb.connect(user=os.getenv("ORACLE_USER"), password=os.getenv("ORACLE_PWD"),
                            dsn=os.getenv("ORACLE_DSN"))


def _lignes(cur):
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# --------------------------------------------------------------------------
# ALLER : Oracle -> dossier (dict) -> Bundle FHIR
# --------------------------------------------------------------------------
def lire_dossier(conn, cin=None, ipp=None):
    cur = conn.cursor()
    if cin:
        cur.execute("SELECT * FROM patient WHERE cin = :v", v=cin)
    else:
        cur.execute("SELECT * FROM patient WHERE ipp = :v", v=ipp)
    pts = _lignes(cur)
    if not pts:
        return None
    p = pts[0]
    cur.execute("""SELECT * FROM consentement WHERE ipp = :v
                   ORDER BY date_consentement DESC""", v=p["ipp"])
    cons = _lignes(cur)
    cur.execute("SELECT * FROM sejour WHERE ipp = :v ORDER BY date_admission", v=p["ipp"])
    sejours = _lignes(cur)
    for s in sejours:
        cur.execute("SELECT * FROM diagnostic WHERE id_sejour = :v", v=s["id_sejour"])
        s["diagnostics"] = _lignes(cur)
        cur.execute("SELECT * FROM mesure WHERE id_sejour = :v ORDER BY date_mesure", v=s["id_sejour"])
        s["mesures"] = _lignes(cur)
    try:
        cur.execute("SELECT * FROM allergie WHERE ipp = :v", v=p["ipp"])
        allergies = _lignes(cur)
    except Exception:
        allergies = []
    return {"patient": p, "consentement": cons[0] if cons else None,
            "sejours": sejours, "allergies": allergies}


def journaliser(conn, sens, ipp, statut, details, *, commit=True, strict=False):
    try:
        conn.cursor().execute(
            "INSERT INTO journal_echange (sens, ipp, statut, details) VALUES (:1, :2, :3, :4)",
            [sens, ipp, statut, json.dumps(details, ensure_ascii=False, default=str)[:4000]])
        if commit:
            conn.commit()
    except Exception:
        if strict:
            raise
        pass   # table pas encore créée : on n'empêche pas l'échange


def exporter(conn, cin=None, ipp=None, adressage=True):
    """Renvoie (bundle, alertes, rejets). Lève ConsentementRefuse / DonneeInvalide."""
    dossier = lire_dossier(conn, cin=cin, ipp=ipp)
    if dossier is None:
        raise LookupError(f"Aucun patient H1 avec CIN={cin} / IPP={ipp}")
    ipp = dossier["patient"]["ipp"]
    try:
        bundle, alertes, rejets = ALL.dossier_vers_bundle(dossier, adressage=adressage)
    except (ALL.ConsentementRefuse, ALL.DonneeInvalide) as e:
        statut = "REFUSE" if isinstance(e, ALL.ConsentementRefuse) else "REJETE"
        journaliser(conn, "ALLER", ipp, statut, [str(e)])
        raise
    journaliser(conn, "ALLER", ipp, "PARTIEL" if rejets else "OK",
                {"alertes": alertes, "rejets": rejets, "ressources": len(bundle["entry"])})
    return bundle, alertes, rejets


# --------------------------------------------------------------------------
# RETOUR : Bundle FHIR -> lignes -> Oracle
# --------------------------------------------------------------------------
def _merge(cur, table, cle, ligne):
    cols = list(ligne)
    src = ", ".join(f":{c} {c}" for c in cols)
    maj = ", ".join(f"t.{c} = s.{c}" for c in cols if c != cle)
    sql = (f"MERGE INTO {table} t USING (SELECT {src} FROM dual) s ON (t.{cle} = s.{cle}) "
           f"WHEN MATCHED THEN UPDATE SET {maj} "
           f"WHEN NOT MATCHED THEN INSERT ({', '.join(cols)}) "
           f"VALUES ({', '.join('s.' + c for c in cols)})")
    cur.execute(sql, ligne)


class IdentiteAmbigue(ValueError):
    """Le retour doit attendre une reconciliation humaine (HTTP 409)."""


def verifier_patient_retour(conn, patient, *, verrouiller=False):
    """Rattache un retour a un patient connu et controle son consentement local.

Ce controle ne cree aucun patient et ne rapproche jamais par les seuls traits.
"""
    cin = RET.identifiant(patient, C.SYS_CIN)
    ipp_chu = RET.identifiant(patient, C.SYS_IPP_CHU)
    with conn.cursor() as cur:
        verrou = " FOR UPDATE" if verrouiller else ""
        if cin:
            cur.execute("SELECT ipp FROM patient WHERE cin = :v" + verrou, v=cin)
        elif ipp_chu:
            cur.execute("SELECT ipp FROM patient WHERE ipp = :v" + verrou, v=ipp_chu)
        else:
            raise IdentiteAmbigue("Rapprochement par traits a valider manuellement.")
        candidats = cur.fetchall()
        if not candidats:
            raise LookupError("Patient inconnu au CHU.")
        if len(candidats) != 1:
            raise IdentiteAmbigue("Plusieurs dossiers correspondent aux identifiants recus.")
        ipp = candidats[0][0]
        if ipp_chu and ipp_chu != ipp:
            raise IdentiteAmbigue("Le CIN et l'IPP du CHU ne designent pas le meme dossier.")
        cur.execute(
            """SELECT statut FROM consentement WHERE ipp = :v
               ORDER BY date_consentement DESC NULLS LAST, id_consentement DESC""", v=ipp)
        consentement = cur.fetchone()
        if not consentement or consentement[0] != "ACTIF":
            raise ALL.ConsentementRefuse("Consentement local absent ou refuse : retour interdit.")
    return ipp


def importer(conn, bundle, creer_patients=True, simulation=False, *, gerer_transaction=True, strict=False):
    """Écrit le Bundle reçu dans Oracle (MERGE : rejouable sans doublon).
    simulation=True : n'écrit rien (rollback), affiche juste ce qui serait fait."""
    cur = conn.cursor()
    alertes = []

    def trouver_ipp(cin, ipp_chu, ligne):
        if cin:
            cur.execute("SELECT * FROM patient WHERE cin = :v", v=cin)
        elif ipp_chu:
            cur.execute("SELECT * FROM patient WHERE ipp = :v", v=ipp_chu)
        else:                                   # cas D4 : pas de CIN -> traits
            cur.execute("""SELECT * FROM patient WHERE UPPER(nom) = UPPER(:n)
                           AND UPPER(prenom) = UPPER(:p) AND TRUNC(date_naissance) = TRUNC(:d)""",
                        n=ligne["nom"], p=ligne["prenom"], d=ligne["date_naissance"])
        trouves = _lignes(cur)
        if not trouves:
            return None
        if len(trouves) > 1:                    # cas D6 : homonymes
            alertes.append(f"{ligne['nom']} {ligne['prenom']} : {len(trouves)} dossiers possibles "
                           "-> aucun rapprochement automatique, validation humaine")
            return None
        h1 = trouves[0]
        if not cin:
            alertes.append(f"{h1['ipp']} : rapprochement par traits (sans CIN) -> à valider")
        for d in RET.comparer_identite(h1, ligne):   # cas D5
            alertes.append(f"{h1['ipp']} : divergence d'identité {d} (rien n'est écrasé)")
        return h1["ipp"]

    def nouvel_ipp():
        cur.execute("SELECT NVL(MAX(TO_NUMBER(SUBSTR(ipp, 4))), 0) + 1 FROM patient "
                    "WHERE REGEXP_LIKE(ipp, '^P1-[0-9]+$')")
        return f"P1-{cur.fetchone()[0]:04d}"

    res = RET.bundle_vers_lignes(bundle, trouver_ipp,
                                 nouvel_ipp if creer_patients else None)
    res["alertes"] = alertes + res["alertes"]

    for ipp, gs in res["groupes_sanguins_recus"].items():     # cas D3
        cur.execute("SELECT groupe_sanguin FROM patient WHERE ipp = :v", v=ipp)
        row = cur.fetchone()
        if row and row[0] and gs and row[0].replace(" ", "") != gs.replace(" ", ""):
            res["alertes"].append(f"CONFLIT {ipp} : groupe sanguin H1 = {row[0]} / reçu = {gs} "
                                  "(aucune valeur écrasée, vérification biologique requise)")

    if strict and (res["ignores"] or not any(res[t] for t in ("sejour", "mesure", "resultat_ophtalmo", "etude_imagerie", "compte_rendu"))):
        raise ALL.DonneeInvalide("Retour incomplet ou contenant des ressources non integrables : import annule.")

    for table, cle in ORDRE_TABLES:
        for ligne in res[table]:
            _merge(cur, table, cle, ligne)
    if not gerer_transaction:
        # Le service appelant valide les ecritures et le journal ensemble.
        return res
    if simulation:
        conn.rollback()
    else:
        conn.commit()
        ipps = sorted({l["ipp"] for t in ("sejour", "resultat_ophtalmo", "compte_rendu")
                       for l in res[t]})
        for ipp in ipps:
            journaliser(conn, "RETOUR", ipp, "OK", {"alertes": res["alertes"],
                                                     "ignores": res["ignores"]})
    return res


def recevoir_retour(conn, bundle, patient):
    """Import API definitif : dossier et journal valides ensemble, sinon rollback."""
    try:
        ipp = verifier_patient_retour(conn, patient, verrouiller=True)
        res = importer(conn, bundle, creer_patients=False,
                       gerer_transaction=False, strict=True)
        journaliser(conn, "RETOUR", ipp, "OK", {
            "source": C.CLINIQUE["source"],
            "lignes_par_table": {table: len(res[table]) for table, _ in ORDRE_TABLES},
            "nombre_alertes": len(res["alertes"]),
        }, commit=False, strict=True)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return ipp, res
