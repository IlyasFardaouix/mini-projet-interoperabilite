"""
Adaptateur ALLER : Oracle (H1, CHU Al Massira) -> FHIR R5.

Entrée : un « dossier » = dictionnaire Python construit à partir des tables Oracle
          (voir oracle_repo.lire_dossier), donc ce module ne dépend PAS d'Oracle
          et peut être testé sans base.
Sortie : un Bundle FHIR de type « transaction » + la liste des alertes et des rejets.

Ressources produites (fiche FHIR de l'équipe) :
  Organization (CHU), Practitioner, Patient, Encounter, Observation,
  ServiceRequest (adressage CHU -> clinique, si adressage=True).
"""
import re
import sys
import uuid
from itertools import zip_longest
from datetime import date, datetime, timezone
from pathlib import Path

import config as C

# Regles de consentement communes a H1 et H2 (dossier securite/ a la racine du depot).
_RACINE = str(Path(__file__).resolve().parent.parent)
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)
from securite import consentement as CONS  # noqa: E402


# --------------------------------------------------------------------------
# Erreurs métier (l'API les transforme en OperationOutcome + code HTTP)
# --------------------------------------------------------------------------
class ConsentementRefuse(Exception):
    """Cas D1 : pas de consentement actif -> transfert interdit (HTTP 403)."""
    http = 403


class DonneeInvalide(Exception):
    """Cas D8 : donnée obligatoire absente -> transfert rejeté (HTTP 422)."""
    http = 422


def vers_operation_outcome(exc):
    """Transforme une erreur en ressource FHIR OperationOutcome (pour l'API)."""
    code = "forbidden" if isinstance(exc, ConsentementRefuse) else "invalid"
    return {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "code": code, "diagnostics": str(exc)}],
    }


# --------------------------------------------------------------------------
# Petits utilitaires de conversion
# --------------------------------------------------------------------------
def uid(system, value):
    """UUID stable calculé à partir d'un identifiant métier.
    Même patient => même fullUrl à chaque export (rejouable sans doublon, cas D15)."""
    return "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"{system}|{value}"))


def date_fhir(d):
    """datetime/date Oracle -> 'AAAA-MM-JJ' (type FHIR date)."""
    if d is None:
        return None
    if isinstance(d, datetime):
        d = d.date()
    return d.isoformat()


def datetime_fhir(d):
    """datetime Oracle (heure locale) -> 'AAAA-MM-JJThh:mm:ss+01:00' (type FHIR dateTime)."""
    if d is None:
        return None
    if not isinstance(d, datetime):
        d = datetime(d.year, d.month, d.day)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + C.TZ


def tel_international(tel):
    """'06 12 34 56 78' -> '+212612345678'"""
    chiffres = re.sub(r"\D", "", tel or "")
    if not chiffres:
        return None
    if chiffres.startswith("212"):
        return "+" + chiffres
    if chiffres.startswith("0"):
        return "+212" + chiffres[1:]
    return chiffres


def age(naissance, ref=None):
    if isinstance(naissance, datetime):
        naissance = naissance.date()
    ref = ref or date.today()
    return ref.year - naissance.year - ((ref.month, ref.day) < (naissance.month, naissance.day))


def slug(texte):
    return re.sub(r"[^a-z0-9]+", "-", (texte or "").lower()).strip("-")


def meta(maintenant):
    return {"lastUpdated": maintenant, "source": C.CHU["source"],
            "security": [dict(s) for s in C.SECURITE]}


def ref_clinique():
    """Référence logique vers la clinique (on n'envoie pas sa ressource Organization)."""
    return {"identifier": {"system": C.SYS_ANNUAIRE, "value": C.CLINIQUE["id_annuaire"]},
            "display": C.CLINIQUE["nom"]}


# --------------------------------------------------------------------------
# Construction des ressources
# --------------------------------------------------------------------------
def organization_chu(m):
    return {
        "resourceType": "Organization",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_ANNUAIRE, "value": C.CHU["id_annuaire"]}],
        "active": True,
        "type": [{"text": "Centre hospitalier universitaire public"}],
        "name": C.CHU["nom"],
    }


def practitioner(nom_medecin, m):
    """'Dr Bennani' -> Practitioner (prefix Dr, family Bennani)."""
    morceaux = nom_medecin.replace("Dr.", "Dr").split()
    prefix = [morceaux.pop(0)] if morceaux and morceaux[0].lower() == "dr" else []
    nom = {"family": " ".join(morceaux) or nom_medecin}
    if prefix:
        nom["prefix"] = prefix
    return {
        "resourceType": "Practitioner",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_MEDECIN_CHU, "value": slug(nom_medecin)}],
        "active": True,
        "name": [nom],
    }


def patient_fhir(p, m, url_org, url_medecin, alertes):
    if not p.get("nom") or not p.get("prenom"):
        raise DonneeInvalide(f"Patient {p.get('ipp')} : nom ou prénom manquant")
    if not p.get("date_naissance"):                                   # cas D8
        raise DonneeInvalide(f"Patient {p['ipp']} : date de naissance manquante "
                             "(champ obligatoire du contrat) -> transfert rejeté")

    identifiants = []
    if p.get("cin"):
        identifiants.append({"use": "official", "system": C.SYS_CIN, "value": p["cin"]})
    else:                                                             # cas D4 / D7
        alertes.append(f"{p['ipp']} : pas de CIN -> rapprochement par traits "
                       "(nom, prénom, naissance, sexe) avec validation humaine côté clinique")
    identifiants.append({"use": "usual", "system": C.SYS_IPP_CHU, "value": p["ipp"]})

    if age(p["date_naissance"]) < C.AGE_MAJORITE:                     # cas D7
        alertes.append(f"{p['ipp']} : patient mineur -> consentement du représentant légal requis")

    res = {
        "resourceType": "Patient",
        "meta": m, "language": C.LANGUE,
        "identifier": identifiants,
        "active": True,
        "name": [{"use": "official", "family": p["nom"], "given": [p["prenom"]]}],
        "gender": C.SEXE_VERS_FHIR.get(p.get("sexe"), "unknown"),
        "birthDate": date_fhir(p["date_naissance"]),
        "managingOrganization": {"reference": url_org, "display": C.CHU["nom"]},
    }
    tel = tel_international(p.get("telephone"))
    if tel:
        res["telecom"] = [{"system": "phone", "use": "mobile", "value": tel}]
    if p.get("ville"):   # minimisation (loi 09-08) : ville + pays, pas la rue
        res["address"] = [{"use": "home", "city": p["ville"], "country": "MA"}]
    if url_medecin:
        res["generalPractitioner"] = [{"reference": url_medecin}]
    return res


def diagnostic_fhir(d, alertes):
    """Ligne diagnostic -> élément Encounter.diagnosis (CodeableReference, sans Condition)."""
    codings = []
    cim = C.MALADIE_VERS_CIM10.get(d.get("code_local"))
    if cim:
        codings.append({"system": C.ICD10, "code": cim[0]})
    else:                                                             # cas D9
        alertes.append(f"{d['id_diagnostic']} : code local inconnu '{d.get('code_local')}' "
                       "-> envoyé en texte seul, à mettre en file de revue")
    if d.get("code_local"):
        codings.append({"system": C.SYS_CODE_LOCAL_MALADIE, "code": d["code_local"]})
    concept = {"text": d.get("libelle") or d.get("code_local")}
    if codings:
        concept["coding"] = codings
    return {"condition": [{"concept": concept}],
            "use": [{"coding": [{"system": C.DIAG_USE, "code": "final"}]}]}


def encounter_fhir(s, m, url_pat, url_org, url_medecin, adressage, alertes, rejets):
    if s.get("date_sortie") and s.get("date_admission") and s["date_sortie"] < s["date_admission"]:
        rejets.append(f"{s['id_sejour']} : date de sortie avant l'admission -> séjour rejeté")  # D12
        return None
    classe = C.TYPE_SEJOUR_VERS_FHIR.get(s.get("type_sejour"), ("AMB", "ambulatory"))
    termine = bool(s.get("date_sortie")) or s.get("type_sejour") == "CONS"
    periode = {"start": datetime_fhir(s.get("date_admission"))}
    if s.get("date_sortie"):
        periode["end"] = datetime_fhir(s["date_sortie"])

    res = {
        "resourceType": "Encounter",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_SEJOUR_CHU, "value": s["id_sejour"]}],
        "status": "completed" if termine else "in-progress",
        "class": [{"coding": [{"system": C.V3_ACTCODE, "code": classe[0], "display": classe[1]}]}],
        "type": [{"coding": [{"system": C.SYS_SERVICE_CHU, "code": s.get("service") or "inconnu"}],
                  "text": f"{s.get('type_sejour')} - {s.get('service')}"}],
        "subject": {"reference": url_pat},
        "serviceProvider": {"reference": url_org, "display": C.CHU["nom"]},
        "actualPeriod": periode,
    }
    if url_medecin:
        res["participant"] = [{
            "type": [{"coding": [{"system": C.V3_PARTICIP, "code": "ATND", "display": "attender"}]}],
            "actor": {"reference": url_medecin}}]
    if s.get("motif"):
        res["reason"] = [{"value": [{"concept": {"text": s["motif"]}}]}]
    diags = [diagnostic_fhir(d, alertes) for d in s.get("diagnostics", [])]
    if diags:
        res["diagnosis"] = diags
    if adressage:   # le séjour qui déclenche l'adressage vers la clinique
        res["admission"] = {
            "destination": ref_clinique(),
            "dischargeDisposition": {"coding": [{"system": C.DISCHARGE, "code": "other-hcf",
                                                 "display": "Other healthcare facility"}],
                                     "text": "Adressé à la clinique d'ophtalmologie"},
        }
    return res


def interpretation(valeur, normale):
    bas, haut = normale
    code, txt = ("L", "Low") if valeur < bas else ("H", "High") if valeur > haut else ("N", "Normal")
    return [{"coding": [{"system": C.V3_INTERP, "code": code, "display": txt}]}]


def observation_fhir(mz, m, url_pat, url_enc, url_medecin, rejets):
    ref = C.MESURES.get(mz.get("code_local"))
    if ref is None:
        rejets.append(f"{mz['id_mesure']} : code mesure inconnu '{mz.get('code_local')}' -> rejetée")
        return None
    if mz.get("valeur") is None:
        rejets.append(f"{mz['id_mesure']} : valeur absente -> rejetée")
        return None
    if not mz.get("unite"):                                           # cas D10
        rejets.append(f"{mz['id_mesure']} : {ref['libelle']} sans unité -> rejetée")
        return None
    if mz["unite"] != ref["ucum"]:
        rejets.append(f"{mz['id_mesure']} : unité '{mz['unite']}' inattendue "
                      f"(attendu {ref['ucum']}) -> rejetée")
        return None
    valeur = float(mz["valeur"])
    bas, haut = ref["plausible"]
    if not bas <= valeur <= haut:                                     # cas D11
        rejets.append(f"{mz['id_mesure']} : {ref['libelle']} = {valeur} {ref['affiche']} "
                      f"hors plage plausible [{bas}-{haut}] -> rejetée")
        return None

    nb, nh = ref["normale"]
    res = {
        "resourceType": "Observation",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_MESURE_CHU, "value": mz["id_mesure"]}],
        "status": "final",
        "category": [{"coding": [{"system": C.OBS_CATEGORY, "code": ref["categorie"]}]}],
        "code": {"coding": [{"system": C.LOINC, "code": ref["loinc"]},
                            {"system": C.SYS_CODE_LOCAL_MESURE, "code": mz["code_local"]}],
                 "text": ref["libelle"]},
        "subject": {"reference": url_pat},
        "encounter": {"reference": url_enc},
        "effectiveDateTime": datetime_fhir(mz.get("date_mesure")),
        "valueQuantity": {"value": valeur, "unit": ref["affiche"],
                          "system": C.UCUM, "code": ref["ucum"]},
        "interpretation": interpretation(valeur, ref["normale"]),
        "referenceRange": [{
            "low": {"value": nb, "unit": ref["affiche"], "system": C.UCUM, "code": ref["ucum"]},
            "high": {"value": nh, "unit": ref["affiche"], "system": C.UCUM, "code": ref["ucum"]}}],
    }
    if url_medecin:
        res["performer"] = [{"reference": url_medecin}]
    if res["effectiveDateTime"] is None:
        del res["effectiveDateTime"]
    return res


def observations_pression(mesures, m, url_pat, url_enc, url_medecin, rejets):
    """Panels BP R5, apparies seulement a date/heure identique.

Chaque mesure source conserve son identifiant dans component.id. Une valeur
non disponible reste absente avec sa raison ; aucune valeur n'est inventee.
"""
    groupes = {}
    for mz in mesures:
        obs = observation_fhir(mz, m, url_pat, url_enc, url_medecin, rejets)
        if obs is None:
            continue
        if not obs.get("effectiveDateTime"):
            rejets.append(f"{mz['id_mesure']} : pression arterielle sans date -> rejetee")
            continue
        groupe = groupes.setdefault(obs["effectiveDateTime"], {"TA_SYS": [], "TA_DIA": []})
        groupe[mz["code_local"]].append((mz, obs))

    panels = []
    for groupe in groupes.values():
        for systolique, diastolique in zip_longest(groupe["TA_SYS"], groupe["TA_DIA"]):
            presents = [paire for paire in (systolique, diastolique) if paire]
            modele = presents[0][1]
            panel = {k: v for k, v in modele.items()
                     if k not in {"identifier", "code", "valueQuantity", "interpretation", "referenceRange"}}
            panel["meta"] = dict(m, profile=[C.PROFIL_PRESSION_ARTERIELLE])
            cle = "PA-" + "-".join(sorted(mz["id_mesure"] for mz, _ in presents))
            panel["identifier"] = [{"system": C.SYS_MESURE_CHU, "value": cle}]
            panel["code"] = {"coding": [{"system": C.LOINC, "code": C.LOINC_PRESSION_ARTERIELLE}],
                             "text": "Pression arterielle systolique et diastolique"}
            panel["component"] = []
            for local, paire in (("TA_SYS", systolique), ("TA_DIA", diastolique)):
                if paire:
                    mz, obs = paire
                    component = {k: obs[k] for k in ("code", "valueQuantity", "interpretation", "referenceRange")}
                    component["id"] = mz["id_mesure"]
                else:
                    component = {
                        "code": {"coding": [{"system": C.LOINC, "code": C.MESURES[local]["loinc"]}],
                                 "text": C.MESURES[local]["libelle"]},
                        "dataAbsentReason": {"coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
                            "code": "unknown"}]},
                    }
                panel["component"].append(component)
            panels.append(panel)
    return panels


def groupe_sanguin_fhir(p, m, url_pat):
    return {
        "resourceType": "Observation",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_MESURE_CHU, "value": f"GS-{p['ipp']}"}],
        "status": "final",
        "category": [{"coding": [{"system": C.OBS_CATEGORY, "code": "laboratory"}]}],
        "code": {"coding": [{"system": C.LOINC, "code": C.LOINC_GROUPE_SANGUIN}],
                 "text": "Groupe sanguin"},
        "subject": {"reference": url_pat},
        "valueCodeableConcept": {"text": p["groupe_sanguin"]},
    }


def _champ(ligne, *mots):
    """Valeur de la 1re colonne dont le nom contient un des mots (noms de colonnes tolérants)."""
    for k, v in ligne.items():
        if any(mot in k for mot in mots):
            return v
    return None


def allergie_fhir(al, m, url_pat, ipp):
    """Ligne de la table allergie -> AllergyIntolerance (R5)."""
    code = _champ(al, "code")
    libelle = _champ(al, "libelle", "substance", "lib")
    ident = _champ(al, "id_") or f"ALL-{ipp}-{code}"
    res = {
        "resourceType": "AllergyIntolerance",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_ALLERGIE_CHU, "value": ident}],
        "clinicalStatus": {"coding": [{"system": C.ALLERGY_CLINICAL, "code": "active"}]},
        "verificationStatus": {"coding": [{"system": C.ALLERGY_VERIF, "code": "confirmed"}]},
        "category": ["medication"],
        "code": {"text": libelle or code},
        "patient": {"reference": url_pat},
    }
    if code:
        res["code"]["coding"] = [{"system": C.SYS_CODE_LOCAL_ALLERGIE, "code": code,
                                  "display": libelle}]
    crit = C.CRITICITE_VERS_FHIR.get(str(_champ(al, "crit") or "").upper())
    if crit:
        res["criticality"] = crit
    return res


def service_request_fhir(s, m, url_pat, url_enc, url_medecin, maintenant):
    res = {
        "resourceType": "ServiceRequest",
        "meta": m, "language": C.LANGUE,
        "identifier": [{"system": C.SYS_DEMANDE_CHU, "value": f"DEM-{s['id_sejour']}"}],
        "status": "active",
        "intent": "order",
        "code": {"concept": {"text": "Adressage en consultation d'ophtalmologie "
                                     "(bilan d'une complication oculaire)"}},
        "subject": {"reference": url_pat},
        "encounter": {"reference": url_enc},
        "authoredOn": maintenant,
        "performer": [ref_clinique()],
    }
    if url_medecin:
        res["requester"] = {"reference": url_medecin}
    return res


# --------------------------------------------------------------------------
# Point d'entrée : dossier Oracle -> Bundle transaction
# --------------------------------------------------------------------------
def _entree(resource, url, cle_recherche):
    return {"fullUrl": url, "resource": resource,
            "request": {"method": "POST", "url": resource["resourceType"],
                        "ifNoneExist": f"identifier={cle_recherche}"}}


def consentement_fhir(cons_oracle, consentement, m, url_pat, url_org, ipp):
    """Ressource Consent R5 du Bundle : H2 refuse (403) tout Bundle qui n'en a pas."""
    ident = (cons_oracle or {}).get("id_consentement") or f"CST-{ipp}"
    res = CONS.vers_fhir(consentement, patient_ref={"reference": url_pat},
                         organisation_ref={"reference": url_org}, meta=m, langue=C.LANGUE,
                         identifiant={"system": C.SYS_CONSENTEMENT_CHU, "value": str(ident)})
    return res, str(ident)


def dossier_vers_bundle(dossier, adressage=True, maintenant=None, destinataire="H2"):
    """Renvoie (bundle, alertes, rejets).
    Lève ConsentementRefuse (D1) ou DonneeInvalide (D8) : rien n'est envoyé.

    Le consentement est évalué par la règle commune (securite/consentement.py) :
    statut, période de validité, finalité « soins » et destinataire autorisé. Les
    catégories que le patient a exclues du partage sont retirées du Bundle."""
    p = dossier["patient"]
    alertes, rejets = [], []

    consentement = CONS.depuis_oracle(dossier.get("consentement"))       # cas D1
    try:
        decision = CONS.verifier(consentement, operation=f"Transfert du patient {p['ipp']}",
                                 destinataire=destinataire)
    except CONS.ConsentementRefuse as exc:
        raise ConsentementRefuse(str(exc)) from exc
    maintenant = maintenant or datetime.now(timezone.utc).isoformat(timespec="seconds")
    m = meta(maintenant)
    entrees = []

    # Les sejours recus restent consultables dans Oracle, mais ne doivent pas
    # repartir vers leur emetteur avec une fausse origine CHU.
    tous_sejours = dossier.get("sejours", [])
    sejours = [s for s in tous_sejours
               if not s.get("id_externe")
               and (not s.get("etablissement") or s["etablissement"] == C.CHU["nom"])]
    exclus = len(tous_sejours) - len(sejours)
    if exclus:
        alertes.append(f"Anti-boucle : {exclus} sejour(s) externe(s) conserve(s) dans Oracle, exclus de l'export.")

    url_org = uid(C.SYS_ANNUAIRE, C.CHU["id_annuaire"])
    entrees.append(_entree(organization_chu(m), url_org,
                           f"{C.SYS_ANNUAIRE}|{C.CHU['id_annuaire']}"))

    # Médecins (un Practitioner par nom distinct)
    url_medecins = {}
    for s in sejours:
        nom = s.get("medecin")
        if nom and nom not in url_medecins:
            url_medecins[nom] = uid(C.SYS_MEDECIN_CHU, slug(nom))
            entrees.append(_entree(practitioner(nom, m), url_medecins[nom],
                                   f"{C.SYS_MEDECIN_CHU}|{slug(nom)}"))

    sejours = sorted(sejours,
                     key=lambda s: s.get("date_admission") or datetime.min)
    dernier_medecin = url_medecins.get(sejours[-1].get("medecin")) if sejours else None

    # Patient (clé de dédoublonnage : CIN s'il existe, sinon IPP)
    cle = (C.SYS_CIN, p["cin"]) if p.get("cin") else (C.SYS_IPP_CHU, p["ipp"])
    url_pat = uid(*cle)
    entrees.append(_entree(patient_fhir(p, m, url_org, dernier_medecin, alertes),
                           url_pat, f"{cle[0]}|{cle[1]}"))

    cons_res, cons_id = consentement_fhir(dossier.get("consentement"), consentement, m,
                                          url_pat, url_org, p["ipp"])
    entrees.append(_entree(cons_res, uid(C.SYS_CONSENTEMENT_CHU, cons_id),
                           f"{C.SYS_CONSENTEMENT_CHU}|{cons_id}"))

    if C.ENVOYER_GROUPE_SANGUIN and p.get("groupe_sanguin"):
        gs = groupe_sanguin_fhir(p, m, url_pat)
        entrees.append(_entree(gs, uid(C.SYS_MESURE_CHU, f"GS-{p['ipp']}"),
                               f"{C.SYS_MESURE_CHU}|GS-{p['ipp']}"))

    for al in dossier.get("allergies", []):
        res = allergie_fhir(al, m, url_pat, p["ipp"])
        cle_al = res["identifier"][0]["value"]
        entrees.append(_entree(res, uid(C.SYS_ALLERGIE_CHU, cle_al),
                               f"{C.SYS_ALLERGIE_CHU}|{cle_al}"))

    # Séjours valides, puis leurs mesures
    valides = []
    for i, s in enumerate(sejours):
        est_adressage = adressage and i == len(sejours) - 1
        url_med = url_medecins.get(s.get("medecin"))
        enc = encounter_fhir(s, m, url_pat, url_org, url_med, est_adressage, alertes, rejets)
        if enc is None:
            continue
        url_enc = uid(C.SYS_SEJOUR_CHU, s["id_sejour"])
        entrees.append(_entree(enc, url_enc, f"{C.SYS_SEJOUR_CHU}|{s['id_sejour']}"))
        valides.append((s, url_enc, url_med, est_adressage))

    for s, url_enc, url_med, est_adressage in valides:
        pressions = []
        for mz in s.get("mesures", []):
            if mz.get("code_local") in ("TA_SYS", "TA_DIA"):
                pressions.append(mz)
                continue
            obs = observation_fhir(mz, m, url_pat, url_enc, url_med, rejets)
            if obs:
                entrees.append(_entree(obs, uid(C.SYS_MESURE_CHU, mz["id_mesure"]),
                                       f"{C.SYS_MESURE_CHU}|{mz['id_mesure']}"))
        for panel in observations_pression(pressions, m, url_pat, url_enc, url_med, rejets):
            cle_panel = panel["identifier"][0]["value"]
            entrees.append(_entree(panel, uid(C.SYS_MESURE_CHU, cle_panel),
                                   f"{C.SYS_MESURE_CHU}|{cle_panel}"))
        if est_adressage:
            sr = service_request_fhir(s, m, url_pat, url_enc, url_med, maintenant)
            entrees.append(_entree(sr, uid(C.SYS_DEMANDE_CHU, f"DEM-{s['id_sejour']}"),
                                   f"{C.SYS_DEMANDE_CHU}|DEM-{s['id_sejour']}"))

    bundle = {"resourceType": "Bundle", "type": "transaction",
              "timestamp": maintenant, "entry": entrees}
    bundle, retirees = CONS.filtrer_bundle(bundle, decision.categories_exclues)
    if retirees:
        alertes.append(f"Consentement partiel : {retirees} ressource(s) exclue(s) du partage "
                       f"({', '.join(sorted(decision.categories_exclues))}).")
    return bundle, alertes, rejets
