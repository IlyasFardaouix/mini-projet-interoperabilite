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


def rechercher_patients(conn, texte, limite=50):
    """Recherche pour l'interface : nom, prenom, CIN ou IPP contenant `texte` (sans casse).
    Texte vide : les premiers patients par ordre alphabetique. Valeur toujours liee (jamais
    concatenee dans le SQL) ; % et _ saisis sont traites comme des caracteres ordinaires."""
    motif = "%" + (texte or "").upper().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    cur = conn.cursor()
    cur.execute("SELECT ipp, nom, prenom, sexe, date_naissance, cin FROM patient "
                "WHERE UPPER(nom) LIKE :q ESCAPE '\\' OR UPPER(prenom) LIKE :q ESCAPE '\\' "
                "OR UPPER(cin) LIKE :q ESCAPE '\\' OR UPPER(ipp) LIKE :q ESCAPE '\\' "
                "ORDER BY nom, prenom FETCH FIRST :n ROWS ONLY", q=motif, n=int(limite))
    return _lignes(cur)


def lister_retours(conn, limite=30):
    """Patients ayant recu des donnees de la clinique (journal des retours acceptes), le plus recent d'abord."""
    cur = conn.cursor()
    cur.execute("SELECT ipp, MAX(date_echange) AS dernier, COUNT(*) AS n FROM journal_echange "
                "WHERE sens = 'RETOUR' AND statut = 'OK' AND ipp IS NOT NULL GROUP BY ipp "
                "ORDER BY MAX(date_echange) DESC FETCH FIRST :n ROWS ONLY", n=int(limite))
    return _lignes(cur)


def lire_recus(conn, ipp):
    """Donnees recues de la clinique (resultats, comptes rendus, imagerie) pour l'interface."""
    cur = conn.cursor()
    recus = {}
    for table in ("etude_imagerie", "compte_rendu", "resultat_ophtalmo"):
        cur.execute(f"SELECT * FROM {table} WHERE ipp = :v", v=ipp)
        recus[table] = _lignes(cur)
    return recus


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
# PATIENT SEUL (routes FHIR standard : POST/GET /Patient, comme H2)
# --------------------------------------------------------------------------
class PatientExistant(ValueError):
    """Un patient avec ce CIN existe deja (HTTP 409)."""


def lire_patient(conn, ipp):
    """Ligne `patient` ou None."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM patient WHERE ipp = :v", v=ipp)
        lignes = _lignes(cur)
    return lignes[0] if lignes else None


def chercher_patients(conn, system=None, valeur=None, limite=100):
    """Recherche par identifiant (`system|valeur`). Sans critere : les `limite` premiers.

    CIN : table patient.cin. IPP du CHU : patient.ipp. Sans systeme, on essaie le CIN
    puis l'IPP. Un systeme inconnu ne renvoie rien (jamais tous les patients).
    """
    with conn.cursor() as cur:
        if not valeur:
            cur.execute("SELECT * FROM patient ORDER BY ipp FETCH FIRST :n ROWS ONLY", n=limite)
            return _lignes(cur)
        if system in (None, "", C.SYS_CIN):
            cur.execute("SELECT * FROM patient WHERE cin = :v", v=valeur)
            trouves = _lignes(cur)
            if trouves or system:
                return trouves
        if system in (None, "", C.SYS_IPP_CHU):
            cur.execute("SELECT * FROM patient WHERE ipp = :v", v=valeur)
            return _lignes(cur)
    return []


def _ligne_patient_valide(patient):
    """Ressource Patient -> ligne a inserer. ValueError : donnees incompletes (422)."""
    if not isinstance(patient, dict) or patient.get("resourceType") != "Patient":
        raise ValueError("resourceType doit valoir Patient.")
    ligne = RET.patient_vers_ligne(patient)
    if not ligne["nom"] or not ligne["prenom"]:
        raise ValueError("Le nom et le prenom sont obligatoires.")
    if not ligne["date_naissance"]:
        raise ValueError("Une date de naissance AAAA-MM-JJ est obligatoire.")
    if not ligne["sexe"]:
        raise ValueError("Le sexe (male|female) est obligatoire.")
    return ligne


def _inserer_patient(conn, ligne):
    """INSERT du patient (IPP attribue ici), SANS valider la transaction. PatientExistant : CIN connu."""
    with conn.cursor() as cur:
        if ligne["cin"]:
            cur.execute("SELECT ipp FROM patient WHERE cin = :v FOR UPDATE", v=ligne["cin"])
            existant = cur.fetchone()
            if existant:
                raise PatientExistant(f"Un patient avec ce CIN existe deja ({existant[0]}).")
        cur.execute("SELECT NVL(MAX(TO_NUMBER(SUBSTR(ipp, 4))), 0) + 1 FROM patient "
                    "WHERE REGEXP_LIKE(ipp, '^P1-[0-9]+$')")
        ligne["ipp"] = f"P1-{cur.fetchone()[0]:04d}"
        cols = list(ligne)
        cur.execute(f"INSERT INTO patient ({', '.join(cols)}) "
                    f"VALUES ({', '.join(':' + c for c in cols)})", ligne)
    return ligne


def creer_patient_seul(conn, patient):
    """Cree UN patient (sans son dossier). Le patient n'a pas de consentement : il
    n'est pas exportable (403 sur son Bundle) tant qu'il n'en a pas, comme chez H2.

    ValueError : donnees incompletes (422). PatientExistant : CIN deja connu (409).
    """
    ligne = _ligne_patient_valide(patient)
    try:
        _inserer_patient(conn, ligne)
        conn.commit()      # la trace est dans le journal d'acces (tracer, cote route)
    except Exception:
        conn.rollback()
        raise
    return lire_patient(conn, ligne["ipp"])


def rattacher_ou_creer_patient(conn, patient, *, creer_si_inconnu=False, consentement_joint=None,
                               verrouiller=False):
    """(ipp, cree) pour un retour clinique.

    Patient connu : comme `verifier_patient_retour` (consentement local controle).
    Patient inconnu : refuse (LookupError, 404) SAUF si `creer_si_inconnu` ET si la clinique a joint
    un consentement valide pour le CHU (`consentement_joint`, corps de saisie). Le patient et son
    consentement sont alors ecrits dans la transaction de l'appelant, qui valide ou annule le tout.
    """
    try:
        return verifier_patient_retour(conn, patient, verrouiller=verrouiller), False
    except LookupError:
        if not (creer_si_inconnu and consentement_joint):
            raise
    ligne = _inserer_patient(conn, _ligne_patient_valide(patient))
    _nouvelle_version(conn, ligne["ipp"], [], CONS.depuis_saisie(consentement_joint), "recueil",
                      "retour clinique (nouveau patient)")
    return ligne["ipp"], True


def patient_en_fhir(ligne):
    """Ligne `patient` -> ressource FHIR Patient autonome (id = IPP, sans reference interne)."""
    maintenant = datetime.now().astimezone().isoformat(timespec="seconds")
    res = ALL.patient_fhir(ligne, ALL.meta(maintenant), None, None, [])
    res["id"] = ligne["ipp"]
    res["managingOrganization"] = {"display": C.CHU["nom"]}
    return res


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


def ignores_bloquants(res):
    """Ressources rejetees parce qu'elles sont MAL FORMEES (patient non resolu, valeur absente...).
    Celles que H1 ne stocke simplement pas (HORS_PERIMETRE) sont seulement signalees, pas bloquantes."""
    return [i for i in res["ignores"] if not i.endswith(RET.HORS_PERIMETRE)]


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

    if strict and (ignores_bloquants(res) or not any(res[t] for t in ("sejour", "mesure", "resultat_ophtalmo", "etude_imagerie", "compte_rendu"))):
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


def recevoir_retour(conn, bundle, patient, echange_id=None, *, creer_si_inconnu=False, consentement_joint=None):
    """Import API definitif : dossier et journal valides ensemble, sinon rollback.

    `creer_si_inconnu` : un patient inconnu du CHU est cree (avec le consentement joint par la clinique)
    au lieu d'etre refuse ; voir `rattacher_ou_creer_patient`."""
    try:
        ipp, cree = rattacher_ou_creer_patient(conn, patient, creer_si_inconnu=creer_si_inconnu,
                                               consentement_joint=consentement_joint, verrouiller=True)
        res = importer(conn, bundle, creer_patients=False,
                       gerer_transaction=False, strict=True)
        if cree:
            res["alertes"].insert(0, f"{ipp} : patient inconnu du CHU, cree a la reception "
                                     "(consentement de la clinique enregistre).")
        journaliser(conn, "RETOUR", ipp, "OK", {
            "source": C.CLINIQUE["source"],
            "lignes_par_table": {table: len(res[table]) for table, _ in ORDRE_TABLES},
            "nombre_alertes": len(res["alertes"]),
            "patient_cree": cree,
            "echange_id": echange_id,      # X-Exchange-Id : relie l'envoi de H2 a cette ligne
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
