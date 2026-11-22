"""
Adaptateur RETOUR : FHIR R5 -> Oracle (H1, CHU Al Massira).

Entrée : un Bundle FHIR (transaction, collection ou searchset) envoyé par la
          clinique (compte rendu ophtalmologique : Patient, Encounter, Observation,
          DiagnosticReport, ImagingStudy, Endpoint, Practitioner...).
Sortie : des LIGNES prêtes à écrire dans les tables Oracle (dictionnaires Python),
          + alertes et ressources ignorées. L'écriture réelle est faite par
          oracle_repo.ecrire_lignes : ce module ne dépend donc PAS d'Oracle.

Tables cibles : patient, sejour, diagnostic, mesure (tables existantes) et
                resultat_ophtalmo, compte_rendu, etude_imagerie (schema_retour_h1.sql).
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone

import config as C

_TZ_LOCAL = timezone(timedelta(hours=int(C.TZ[:3]), minutes=int(C.TZ[0] + C.TZ[4:])))


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------
def id_local(prefixe, *morceaux, longueur=12):
    """Identifiant Oracle stable pour une donnée venue de l'extérieur.
    Même ressource reçue deux fois => même clé => pas de doublon (cas D15)."""
    h = hashlib.sha1("|".join(str(x) for x in morceaux).encode()).hexdigest().upper()
    return (prefixe + h)[:longueur]


def lire_datetime(v):
    """'2026-10-20T10:15:00+01:00' ou '1968-04-12' -> datetime (heure locale du CHU)."""
    if not v:
        return None
    v = v.replace("Z", "+00:00")
    if len(v) == 4:              # année seule
        v += "-01-01"
    elif len(v) == 7:            # année-mois
        v += "-01"
    d = datetime.fromisoformat(v)
    if d.tzinfo is not None:
        d = d.astimezone(_TZ_LOCAL).replace(tzinfo=None)
    return d


def tel_national(tel):
    """'+212612345678' -> '06 12 34 56 78' (format de la base H1)."""
    chiffres = re.sub(r"\D", "", tel or "")
    if not chiffres:
        return None
    if chiffres.startswith("212"):
        chiffres = "0" + chiffres[3:]
    if len(chiffres) == 10:
        return " ".join(chiffres[i:i + 2] for i in range(0, 10, 2))
    return chiffres


def identifiant(res, system):
    for i in res.get("identifier", []) or []:
        if i.get("system") == system:
            return i.get("value")
    return None


def premier_identifiant(res):
    ids = res.get("identifier") or []
    return ids[0].get("value") if ids else None


def cle_externe(res):
    """Identite metier complete pour les cles Oracle des donnees externes."""
    ids = res.get("identifier") or []
    if ids:
        return f"{ids[0].get('system', '')}|{ids[0].get('value', '')}"
    return res.get("id")


def texte_concept(cc):
    """Libellé lisible d'un CodeableConcept."""
    if not cc:
        return None
    if cc.get("text"):
        return cc["text"]
    for c in cc.get("coding", []) or []:
        if c.get("display"):
            return c["display"]
    for c in cc.get("coding", []) or []:
        if c.get("code"):
            return c["code"]
    return None


def codes(cc, system=None):
    return [c.get("code") for c in (cc or {}).get("coding", []) or []
            if system is None or c.get("system") == system]


def nom_practitioner(pr):
    if not pr:
        return None
    n = (pr.get("name") or [{}])[0]
    morceaux = (n.get("prefix") or []) + (n.get("given") or []) + [n.get("family") or ""]
    return " ".join(x for x in morceaux if x).strip() or None


class Index:
    """Retrouve une ressource du Bundle à partir d'une référence
    ('urn:uuid:...', 'Patient/123' ou URL absolue)."""

    def __init__(self, bundle):
        self.par_cle = {}
        self.ressources = []
        for e in bundle.get("entry", []) or []:
            r = e.get("resource")
            if not r:
                continue
            self.ressources.append(r)
            if e.get("fullUrl"):
                self.par_cle[e["fullUrl"]] = r
            if r.get("id"):
                self.par_cle[f"{r['resourceType']}/{r['id']}"] = r

    def resoudre(self, ref):
        if not ref:
            return None
        cible = ref.get("reference") if isinstance(ref, dict) else ref
        if not cible:
            return None
        if cible in self.par_cle:
            return self.par_cle[cible]
        m = re.search(r"([A-Za-z]+/[^/]+)$", cible)      # URL absolue .../Patient/123
        return self.par_cle.get(m.group(1)) if m else None

    def de_type(self, t):
        return [r for r in self.ressources if r.get("resourceType") == t]


# --------------------------------------------------------------------------
# Patient
# --------------------------------------------------------------------------
def patient_vers_ligne(pat):
    """Ressource Patient -> ligne de la table patient (sans IPP : attribué par le repo)."""
    nom = (pat.get("name") or [{}])[0]
    adr = (pat.get("address") or [{}])[0]
    tel = next((t.get("value") for t in pat.get("telecom", []) or []
                if t.get("system") == "phone"), None)
    return {
        "nom": nom.get("family"),
        "prenom": " ".join(nom.get("given") or []) or None,
        "sexe": C.SEXE_VERS_H1.get(pat.get("gender")),
        "date_naissance": lire_datetime(pat.get("birthDate")),
        "cin": identifiant(pat, C.SYS_CIN),
        "telephone": tel_national(tel),
        "adresse": (adr.get("line") or [None])[0],
        "ville": adr.get("city"),
        "groupe_sanguin": None,
    }


def comparer_identite(ligne_oracle, ligne_fhir):
    """Liste des divergences d'identité, sans rien écraser (cas D3 / D5)."""
    divergences = []
    for champ in ("nom", "prenom", "sexe", "date_naissance"):
        a, b = ligne_oracle.get(champ), ligne_fhir.get(champ)
        if isinstance(a, datetime):
            a = a.date()
        if isinstance(b, datetime):
            b = b.date()
        if a and b and str(a).strip().lower() != str(b).strip().lower():
            divergences.append(f"{champ} : H1 = '{a}' / reçu = '{b}'")
    return divergences


# --------------------------------------------------------------------------
# Conversion du Bundle
# --------------------------------------------------------------------------
# Ressources que H1 ne stocke pas (allergies, diagnostics, demandes d'examen de H2...) : elles sont
# signalees dans "ignores" mais ne font pas echouer l'import des donnees qui, elles, ont une table.
HORS_PERIMETRE = "pas de table correspondante dans H1 (v1)"


def bundle_vers_lignes(bundle, trouver_ipp, nouvel_ipp=None, ignorer_propres=True):
    """
    trouver_ipp(cin, ipp_chu, ligne_patient) -> IPP existant dans Oracle, ou None.
    nouvel_ipp() -> IPP à créer si le patient est inconnu (None = refuser).
    ignorer_propres : ignore les ressources dont meta.source est le CHU lui-même
                      (données qu'Oracle possède déjà).
    Renvoie un dict {table: [lignes], 'alertes': [...], 'ignores': [...], ...}.
    """
    idx = Index(bundle)
    out = {"patient": [], "sejour": [], "diagnostic": [], "mesure": [],
           "resultat_ophtalmo": [], "compte_rendu": [], "etude_imagerie": [],
           "alertes": [], "ignores": [], "groupes_sanguins_recus": {}}

    def est_propre(r):
        return ignorer_propres and (r.get("meta") or {}).get("source") == C.CHU["source"]

    # 1. Patients -> IPP
    ipp_de = {}                                   # id python de la ressource -> IPP
    for pat in idx.de_type("Patient"):
        ligne = patient_vers_ligne(pat)
        cin, ipp_chu = ligne["cin"], identifiant(pat, C.SYS_IPP_CHU)
        ipp = trouver_ipp(cin, ipp_chu, ligne)
        if ipp is None:
            if nouvel_ipp is None:
                out["alertes"].append(f"Patient inconnu au CHU (CIN {cin}) -> données non importées")
                continue
            ipp = nouvel_ipp()
            ligne["ipp"] = ipp
            out["patient"].append(ligne)
            out["alertes"].append(f"Patient {ligne['nom']} {ligne['prenom']} créé au CHU (IPP {ipp})")
        ipp_de[id(pat)] = ipp

    def ipp_sujet(r):
        pat = idx.resoudre(r.get("subject") or r.get("patient"))
        return ipp_de.get(id(pat)) if pat else None

    # 2. Encounter -> sejour + diagnostic
    sejour_de = {}                               # id python de l'Encounter -> id_sejour
    for enc in idx.de_type("Encounter"):
        propre = identifiant(enc, C.SYS_SEJOUR_CHU)
        if propre:
            sejour_de[id(enc)] = propre
        if est_propre(enc):
            continue
        ipp = ipp_sujet(enc)
        if ipp is None:
            out["ignores"].append(f"Encounter {premier_identifiant(enc)} : patient non résolu")
            continue
        ext = premier_identifiant(enc) or enc.get("id")
        id_sejour = propre or id_local("EX", "Encounter", ipp, cle_externe(enc))
        sejour_de[id(enc)] = id_sejour
        periode = enc.get("actualPeriod") or {}
        debut, fin = lire_datetime(periode.get("start")), lire_datetime(periode.get("end"))
        if debut and fin and fin < debut:
            out["ignores"].append(f"Encounter {ext} : fin avant début -> rejeté")
            sejour_de.pop(id(enc))
            continue
        classe = next(iter(codes((enc.get("class") or [{}])[0], C.V3_ACTCODE)), None)
        medecin = None
        for part in enc.get("participant", []) or []:
            pr = idx.resoudre(part.get("actor"))
            medecin = nom_practitioner(pr) or (part.get("actor") or {}).get("display")
            if medecin:
                break
        motif = None
        for r in enc.get("reason", []) or []:
            for v in r.get("value", []) or []:
                motif = texte_concept(v.get("concept")) or motif
        fournisseur = idx.resoudre(enc.get("serviceProvider"))
        etab = (fournisseur or {}).get("name") or (enc.get("serviceProvider") or {}).get("display")
        out["sejour"].append({
            "id_sejour": id_sejour, "ipp": ipp,
            "type_sejour": C.CLASSE_VERS_TYPE_SEJOUR.get(classe, "CONS"),
            "service": next(iter(codes((enc.get("type") or [{}])[0])), None)
                       or texte_concept((enc.get("type") or [{}])[0]),
            "date_admission": debut, "date_sortie": fin,
            "medecin": medecin, "motif": motif,
            "etablissement": None if propre else (etab or C.CLINIQUE["nom"]),
            "id_externe": None if propre else ext,
        })
        for dg in enc.get("diagnosis", []) or []:
            for cond in dg.get("condition", []) or []:
                cc = cond.get("concept") or {}
                cim = next(iter(codes(cc, C.ICD10)), None)
                local = next(iter(codes(cc, C.SYS_CODE_LOCAL_MALADIE)), None)
                code_local = local or C.CIM10_VERS_MALADIE.get(cim) or cim
                out["diagnostic"].append({
                    "id_diagnostic": id_local("DX", id_sejour, code_local, texte_concept(cc),
                                              longueur=14),
                    "id_sejour": id_sejour, "libelle": texte_concept(cc),
                    "code_local": code_local, "date_diagnostic": debut,
                })

    # Ressources utiles pour ImagingStudy / DiagnosticReport
    def sejour_lie(r):
        enc = idx.resoudre(r.get("encounter"))
        return sejour_de.get(id(enc)) if enc else None

    # 3. Observation -> mesure / resultat_ophtalmo / groupe sanguin
    for obs in idx.de_type("Observation"):
        if est_propre(obs):
            continue
        ipp = ipp_sujet(obs)
        ext = premier_identifiant(obs) or obs.get("id")
        if ipp is None:
            out["ignores"].append(f"Observation {ext} : patient non résolu")
            continue
        loincs = codes(obs.get("code"), C.LOINC)
        oeil = None
        for c in (obs.get("bodySite") or {}).get("coding", []) or []:
            oeil = C.SNOMED_VERS_OEIL.get(c.get("code")) or oeil
        oeil = oeil or next((C.LOINC_PIO[c] for c in loincs if c in C.LOINC_PIO), None)
        q = obs.get("valueQuantity") or {}
        date_exam = lire_datetime(obs.get("effectiveDateTime"))
        interp = next(iter(codes((obs.get("interpretation") or [{}])[0])), None)

        if C.LOINC_GROUPE_SANGUIN in loincs:
            out["groupes_sanguins_recus"][ipp] = (texte_concept(obs.get("valueCodeableConcept"))
                                                  or obs.get("valueString"))
            continue

        if C.LOINC_PRESSION_ARTERIELLE in loincs:
            id_sejour = sejour_lie(obs)
            if not id_sejour:
                out["ignores"].append(f"Observation {ext} : pression arterielle sans sejour")
                continue
            for component in obs.get("component", []):
                local = next((C.LOINC_VERS_MESURE[c] for c in codes(component.get("code"), C.LOINC)
                              if C.LOINC_VERS_MESURE.get(c) in ("TA_SYS", "TA_DIA")), None)
                if not local:
                    out["ignores"].append(f"Observation {ext} : composant de pression non reconnu")
                    continue
                quantite = component.get("valueQuantity") or {}
                valeur = quantite.get("value")
                if valeur is None and component.get("dataAbsentReason"):
                    continue
                unite = quantite.get("code") or quantite.get("unit")
                if valeur is None or unite != "mm[Hg]":
                    out["ignores"].append(f"Observation {ext} : composant de pression sans valeur ou unite UCUM")
                    continue
                propre = (obs.get("meta") or {}).get("source") == C.CHU["source"]
                cle_mesure = component.get("id") if propre else None
                out["mesure"].append({
                    "id_mesure": cle_mesure or id_local("EX", "Observation", ipp, cle_externe(obs), local, longueur=14),
                    "id_sejour": id_sejour, "code_local": local,
                    "valeur": valeur, "unite": unite, "date_mesure": date_exam,
                })
            continue

        if oeil:                                     # résultat ophtalmologique
            code_obs = (obs.get("code") or {}).get("coding", [{}])[0]
            ligne = {
                "id_resultat": id_local("RO", "Observation", ipp, cle_externe(obs), longueur=14),
                "ipp": ipp, "id_sejour": sejour_lie(obs),
                "code_examen": f"{code_obs.get('system', '')}|{code_obs.get('code', '')}"[:80],
                "libelle": texte_concept(obs.get("code")),
                "oeil": oeil,
                "valeur": q.get("value"),
                "valeur_texte": obs.get("valueString") or texte_concept(obs.get("valueCodeableConcept")),
                "unite": q.get("code") or q.get("unit"),
                "interpretation": interp,
                "date_examen": date_exam,
                "id_externe": ext,
            }
            out["resultat_ophtalmo"].append(ligne)
            if interp in ("H", "HH", "A", "AA"):
                lib = ligne["libelle"] if oeil in (ligne["libelle"] or "") else f"{ligne['libelle']} {oeil}"
                out["alertes"].append(f"{ipp} : {lib} = "
                                      f"{ligne['valeur']} {ligne['unite'] or ''} (anormal : {interp})")
            continue

        code_local = next((C.LOINC_VERS_MESURE[c] for c in loincs if c in C.LOINC_VERS_MESURE), None)
        if code_local:                               # constante générale
            id_sejour = sejour_lie(obs)
            if not id_sejour:
                out["ignores"].append(f"Observation {ext} : sans séjour, non stockable dans mesure")
                continue
            valeur, unite = q.get("value"), q.get("code") or q.get("unit")
            if valeur is None or not unite:
                out["ignores"].append(f"Observation {ext} : valeur ou unité absente -> rejetée")
                continue
            conv = C.CONVERSIONS_UNITES.get((code_local, unite))
            if conv:
                unite, valeur = conv[0], round(valeur * conv[1], 2)
            elif unite != C.MESURES[code_local]["ucum"]:
                out["ignores"].append(f"Observation {ext} : unité '{unite}' non convertible -> rejetée")
                continue
            out["mesure"].append({
                "id_mesure": identifiant(obs, C.SYS_MESURE_CHU)
                             or id_local("EX", "Observation", ipp, cle_externe(obs), longueur=14),
                "id_sejour": id_sejour, "code_local": code_local,
                "valeur": valeur, "unite": unite, "date_mesure": date_exam,
            })
            continue

        out["ignores"].append(f"Observation {ext} ({texte_concept(obs.get('code'))}) : "
                              "code non reconnu par H1")

    # 4. ImagingStudy (+ Endpoint) -> etude_imagerie
    etude_de = {}
    for im in idx.de_type("ImagingStudy"):
        ipp = ipp_sujet(im)
        uid_etude = next((i.get("value") for i in im.get("identifier", []) or []
                          if i.get("system") == "urn:dicom:uid"), None) or premier_identifiant(im)
        if ipp is None:
            out["ignores"].append(f"ImagingStudy {uid_etude} : patient non résolu")
            continue
        acc = next((i.get("value") for i in im.get("identifier", []) or []
                    if "ACSN" in str(i.get("type")) or (i.get("value") or "").startswith("ACC")), None)
        url = None
        for ep_ref in im.get("endpoint", []) or []:
            ep = idx.resoudre(ep_ref)
            url = (ep or {}).get("address") or url
        series = im.get("series", []) or []
        lat = sorted({C.SNOMED_VERS_OEIL.get(c, c) for s in series
                      for c in codes(s.get("laterality"))})
        mods = sorted({c for m in im.get("modality", []) or [] for c in codes(m)}
                      | {c for s in series for c in codes(s.get("modality"))})
        id_etude = id_local("IM", "ImagingStudy", ipp, uid_etude, longueur=14)
        etude_de[id(im)] = id_etude
        out["etude_imagerie"].append({
            "id_etude": id_etude, "ipp": ipp, "id_sejour": sejour_lie(im),
            "study_uid": (uid_etude or "")[:128], "accession": acc,
            "modalites": ",".join(mods) or None, "description": im.get("description"),
            "date_etude": lire_datetime(im.get("started")),
            "nb_series": im.get("numberOfSeries") or len(series) or None,
            "nb_instances": im.get("numberOfInstances"),
            "lateralites": ",".join(lat) or None, "url_pacs": url,
            "statut": im.get("status"),
        })
        if not url:
            out["alertes"].append(f"ImagingStudy {uid_etude} : pas d'Endpoint -> images non consultables")

    # 5. DiagnosticReport -> compte_rendu
    for dr in idx.de_type("DiagnosticReport"):
        ipp = ipp_sujet(dr)
        ext = premier_identifiant(dr) or dr.get("id")
        if ipp is None:
            out["ignores"].append(f"DiagnosticReport {ext} : patient non résolu")
            continue
        medecin = None
        for pf in dr.get("performer", []) or []:
            medecin = nom_practitioner(idx.resoudre(pf)) or pf.get("display") or medecin
        etudes = [etude_de.get(id(idx.resoudre(s))) for s in dr.get("study", []) or []]
        out["compte_rendu"].append({
            "id_cr": id_local("CR", "DiagnosticReport", ipp, cle_externe(dr), longueur=14),
            "ipp": ipp, "id_sejour": sejour_lie(dr),
            "libelle": texte_concept(dr.get("code")),
            "statut": dr.get("status"),
            "conclusion": dr.get("conclusion"),
            "date_examen": lire_datetime(dr.get("effectiveDateTime")),
            "date_emission": lire_datetime(dr.get("issued")),
            "medecin": medecin,
            "id_etude": next((e for e in etudes if e), None),
            "id_externe": ext,
        })

    # 6. Le reste n'a pas de table dans H1 (v1)
    stockes = {"Patient", "Encounter", "Observation", "ImagingStudy", "DiagnosticReport",
               "Endpoint", "Practitioner", "Organization", "PractitionerRole"}
    for r in idx.ressources:
        if r["resourceType"] not in stockes:
            out["ignores"].append(f"{r['resourceType']} {premier_identifiant(r) or r.get('id') or ''} : "
                                  + HORS_PERIMETRE)
    return out