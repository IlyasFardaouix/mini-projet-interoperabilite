"""
Accès à la base Oracle H1 : lecture d'un dossier (aller) et écriture des lignes
reçues (retour). C'est le SEUL fichier qui parle à Oracle.
"""
import json
import os
import uuid
from datetime import datetime

import config as C
import fhir_to_h1 as RET
import h1_to_fhir as ALL
from h1_to_fhir import CONS   # regles de consentement communes (securite/consentement.py)
from securite import droit_acces as DA  # noqa: E402  (racine ajoutee par h1_to_fhir)

# Plus recent d'abord ; a date egale, l'identifiant (numero de version) departage.
SQL_CONSENTEMENTS = """SELECT * FROM consentement WHERE ipp = :v
                       ORDER BY date_consentement DESC NULLS LAST, id_consentement DESC"""

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
    cur.execute(SQL_CONSENTEMENTS, v=p["ipp"])
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


def exporter(conn, cin=None, ipp=None, adressage=True, destinataire="H2"):
    """Renvoie (bundle, alertes, rejets). Lève ConsentementRefuse / DonneeInvalide."""
    dossier = lire_dossier(conn, cin=cin, ipp=ipp)
    if dossier is None:
        raise LookupError(f"Aucun patient H1 avec CIN={cin} / IPP={ipp}")
    ipp = dossier["patient"]["ipp"]
    try:
        bundle, alertes, rejets = ALL.dossier_vers_bundle(dossier, adressage=adressage,
                                                          destinataire=destinataire)
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
        cur.execute(SQL_CONSENTEMENTS, v=ipp)
        lignes = _lignes(cur)
        decision = CONS.evaluer(CONS.depuis_oracle(lignes[0] if lignes else None))
        if not decision.autorise:
            raise ALL.ConsentementRefuse(f"Consentement local : {decision.motif} : retour interdit (loi 09-08).")
    return ipp


def patient_de_l_etude(conn, study_uid):
    """IPP du patient d'une etude d'imagerie recue, ou None."""
    with conn.cursor() as cur:
        cur.execute("SELECT ipp FROM etude_imagerie WHERE study_uid = :v", v=study_uid)
        ligne = cur.fetchone()
    return ligne[0] if ligne else None


# --------------------------------------------------------------------------
# CONSENTEMENT : etat, recueil, retrait (une ligne par version, jamais d'UPDATE)
# --------------------------------------------------------------------------
class ConsentementSansObjet(ValueError):
    """Retrait demande alors qu'aucun consentement n'est actif (HTTP 409)."""


def etat_consentement(ipp, lignes):
    """Consentement en vigueur, decision de partage et historique (plus recent d'abord)."""
    versions = [(l.get("id_consentement"), CONS.depuis_oracle(l)) for l in lignes]
    actuel = versions[0][1] if versions else None
    decision = CONS.evaluer(actuel)
    return {
        "patient_ipp": ipp,
        "partage_autorise": decision.autorise,
        "motif": decision.motif,
        "actuel": dict(actuel.en_dict(), id=versions[0][0]) if actuel else None,
        "historique": [dict(c.en_dict(), id=i) for i, c in versions[1:]],
    }


def lire_consentements(conn, ipp, *, verrouiller=False):
    """Versions du consentement d'un patient. LookupError si le patient est inconnu."""
    with conn.cursor() as cur:
        cur.execute("SELECT ipp FROM patient WHERE ipp = :v" + (" FOR UPDATE" if verrouiller else ""), v=ipp)
        if cur.fetchone() is None:
            raise LookupError("Patient inconnu au CHU.")
        cur.execute(SQL_CONSENTEMENTS, v=ipp)
        return _lignes(cur)


def _nouvelle_version(conn, ipp, lignes, consentement, evenement, agent):
    """INSERT de la nouvelle version + journal, dans la meme transaction."""
    ident = f"CST-{ipp[3:]}-{len(lignes) + 1:03d}"
    if len(ident) > 14:                                 # ID_CONSENTEMENT VARCHAR2(14)
        ident = "C" + uuid.uuid4().hex[:13].upper()
    valeurs = {"id_consentement": ident, "ipp": ipp, **CONS.vers_oracle(consentement),
               "date_consentement": datetime.now()}      # date ET heure : ordre des versions
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO consentement ({', '.join(valeurs)}) "
                    f"VALUES ({', '.join(':' + c for c in valeurs)})", valeurs)
    journaliser(conn, "CONSENTEMENT", ipp, valeurs["statut"], {
        "evenement": evenement, "id_consentement": ident, "agent": agent,
        "recueilli_par": consentement.recueilli_par,
        "destinataires": list(consentement.destinataires),
        "categories_exclues": list(consentement.categories_exclues),
    }, commit=False, strict=True)


def enregistrer_consentement(conn, ipp, corps, *, agent):
    """Recueil d'un consentement (actif ou refuse). ConsentementInvalide si saisie incoherente."""
    try:
        lignes = lire_consentements(conn, ipp, verrouiller=True)
        nouveau = CONS.depuis_saisie(corps)
        _nouvelle_version(conn, ipp, lignes, nouveau, "recueil", agent)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return etat_consentement(ipp, lire_consentements(conn, ipp))


def retirer_consentement(conn, ipp, corps, *, agent):
    """Retrait (droit d'opposition) : nouvelle version RETIRE. Les exports suivants sont refuses."""
    corps = corps if isinstance(corps, dict) else {}
    try:
        lignes = lire_consentements(conn, ipp, verrouiller=True)
        actuel = CONS.depuis_oracle(lignes[0]) if lignes else None
        if actuel is None or actuel.statut != CONS.ACTIF:
            raise ConsentementSansObjet("Aucun consentement actif a retirer pour ce patient.")
        nouveau = CONS.retirer(actuel, corps.get("motif"), recueilli_par=corps.get("recueilli_par"))
        _nouvelle_version(conn, ipp, lignes, nouveau, "retrait", agent)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return etat_consentement(ipp, lire_consentements(conn, ipp))


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


# --------------------------------------------------------------------------
# DROIT D'ACCES DE LA PERSONNE (loi 09-08, art. 7)
# --------------------------------------------------------------------------
TABLES_RECUES = ("etude_imagerie", "compte_rendu", "resultat_ophtalmo")
EVENEMENTS = {"ALLER": "Envoi du dossier a la clinique", "RETOUR": "Reception de donnees de la clinique",
              "CONSENTEMENT": "Consentement", "DROIT_ACCES": "Droit d'acces (loi 09-08, art. 7)"}


def _json(valeur):
    """Lignes Oracle -> JSON (dates et nombres en texte lisible)."""
    return json.loads(json.dumps(valeur, ensure_ascii=False, default=str))


def droit_acces(conn, ipp, *, agent):
    """Tout ce que le CHU detient sur la personne : dossier, donnees recues de la
    clinique, consentement et historique, journal des echanges. La demande est
    tracee (journal_echange, sens DROIT_ACCES) avant la reponse."""
    dossier = lire_dossier(conn, ipp=ipp)
    if dossier is None:
        raise LookupError("Patient inconnu au CHU.")
    ipp = dossier["patient"]["ipp"]
    journaliser(conn, "DROIT_ACCES", ipp, "OK", {"agent": agent}, strict=True)

    recues = {}
    with conn.cursor() as cur:
        for table in TABLES_RECUES:
            cur.execute(f"SELECT * FROM {table} WHERE ipp = :v", v=ipp)
            recues[table] = _lignes(cur)
        cur.execute("SELECT date_echange, sens, statut, details FROM journal_echange "
                    "WHERE ipp = :v ORDER BY date_echange", v=ipp)
        journal = _lignes(cur)

    acces = [DA.entree_acces(j.get("date_echange"), j.get("sens"),
                             EVENEMENTS.get(j.get("sens"), j.get("sens")), resultat=j.get("statut"),
                             destinataire="H2" if j.get("sens") == "ALLER" else None)
             for j in journal]
    externes = sum(1 for s in dossier.get("sejours", [])
                   if s.get("id_externe") or (s.get("etablissement") and s["etablissement"] != C.CHU["nom"]))
    externes += sum(len(lignes) for lignes in recues.values())
    origine = [{"etablissement": DA.ETABLISSEMENTS["H2"], "code": "H2", "elements": externes}] if externes else []
    return _json(DA.reponse(
        service="H1", patient=ipp,
        donnees={"dossier": {k: v for k, v in dossier.items() if k != "consentement"},
                 "donnees_recues_de_la_clinique": recues},
        consentement=etat_consentement(ipp, lire_consentements(conn, ipp)),
        acces=acces, origine_des_donnees=origine))
