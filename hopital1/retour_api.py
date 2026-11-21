"""Controles du contrat de retour H2 -> H1, avant tout acces Oracle."""

from datetime import date

import config as C
from fhir_to_h1 import Index
from h1_to_fhir import CONS, ConsentementRefuse
from valider import valider_bundle


def extraire_consentement(bundle):
    """Controle le Consent joint au retour, puis le retire du Bundle.

Renvoie (bundle, alertes). Leve ConsentementRefuse (403) si le Consent recu
n'autorise pas le partage vers le CHU. Le Consent n'est pas ecrit dans Oracle :
le consentement local du CHU fait foi (controle dans oracle_repo). Les
categories exclues par le patient sont retirees avant l'import. Un retour sans
Consent reste accepte : seul le consentement local est alors controle.
"""
    if not isinstance(bundle, dict) or not isinstance(bundle.get("entry"), list):
        return bundle, []        # la validation de structure renverra 422
    consents = [e.get("resource") for e in bundle["entry"]
                if isinstance(e, dict) and (e.get("resource") or {}).get("resourceType") == "Consent"]
    if not consents:
        return bundle, []
    try:
        decision = CONS.verifier(CONS.depuis_fhir(consents[0]), operation="Retour",
                                 destinataire=C.CODE_ETABLISSEMENT)
    except CONS.ConsentementRefuse as exc:
        raise ConsentementRefuse(str(exc)) from exc
    sans_consent = dict(bundle, entry=[e for e in bundle["entry"]
                                       if (e.get("resource") or {}).get("resourceType") != "Consent"])
    filtre, retirees = CONS.filtrer_bundle(sans_consent, decision.categories_exclues)
    alertes = []
    if retirees:
        alertes.append(f"Consentement partiel : {retirees} ressource(s) ignoree(s), categorie(s) "
                       f"exclue(s) du partage ({', '.join(sorted(decision.categories_exclues))}).")
    return filtre, alertes


def verifier_bundle_retour(bundle, *, definitif=False):
    """Renvoie l'unique Patient d'un Bundle de retour autonome.

ValueError : contenu incompatible avec le contrat applicatif.
La validation de structure Python ne remplace pas le validateur officiel HL7.
"""
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise ValueError("Le corps doit etre un Bundle FHIR R5.")
    if bundle.get("type") != "transaction" or not bundle.get("entry"):
        raise ValueError("Un Bundle transaction non vide est attendu.")
    if valider_bundle(bundle):
        raise ValueError("Le Bundle ne passe pas la validation de structure FHIR R5.")

    cles = set()
    for entry in bundle["entry"]:
        resource = entry.get("resource")
        if not resource:
            raise ValueError("Chaque entree doit contenir une ressource.")
        request = entry.get("request") or {}
        if request.get("method") != "POST" or request.get("url") != resource["resourceType"]:
            raise ValueError("La simulation accepte des entrees POST vers leur type de ressource.")
        aliases = [entry.get("fullUrl")]
        if resource.get("id"):
            aliases.append(f"{resource['resourceType']}/{resource['id']}")
        for alias in set(a for a in aliases if a):
            if alias in cles:
                raise ValueError("Une reference de ressource est dupliquee dans le Bundle.")
            cles.add(alias)

    idx = Index(bundle)
    patients = idx.de_type("Patient")
    if len(patients) != 1:
        raise ValueError("Un seul Patient est attendu par retour clinique.")
    patient = patients[0]
    noms = patient.get("name") or [{}]
    if not noms[0].get("family") or not noms[0].get("given"):
        raise ValueError("Le nom et le prenom du patient sont obligatoires.")
    naissance = patient.get("birthDate") or ""
    if len(naissance) != 10:
        raise ValueError("Une date de naissance complete AAAA-MM-JJ est obligatoire.")
    date.fromisoformat(naissance)

    # Aucune reconnaissance par traits sans validation humaine dans cette route.
    for system in (C.SYS_CIN, C.SYS_IPP_CHU):
        values = {i.get("value") for i in patient.get("identifier", [])
                  if i.get("system") == system and i.get("value")}
        if len(values) > 1:
            raise ValueError("Les identifiants du patient sont contradictoires.")
    if not any(i.get("system") in (C.SYS_CIN, C.SYS_IPP_CHU) and i.get("value")
               for i in patient.get("identifier", [])):
        raise ValueError("Un CIN ou un IPP du CHU est requis pour rattacher le retour.")

    def verifier_references(value):
        if isinstance(value, dict):
            ref = value.get("reference")
            if isinstance(ref, str) and idx.resoudre(ref) is None:
                raise ValueError("Une reference du retour ne se resout pas dans le Bundle.")
            for enfant in value.values():
                verifier_references(enfant)
        elif isinstance(value, list):
            for enfant in value:
                verifier_references(enfant)

    for resource in idx.ressources:
        verifier_references(resource)
        if resource["resourceType"] in {"Encounter", "Observation", "ImagingStudy", "DiagnosticReport"}:
            if idx.resoudre(resource.get("subject")) is not patient:
                raise ValueError("Chaque donnee clinique doit designer le Patient du retour.")
            if definitif:
                identifiers = resource.get("identifier") or []
                if not resource.get("id") and not any(i.get("system") and i.get("value") for i in identifiers):
                    raise ValueError("Un identifiant stable est requis pour chaque donnee clinique.")
                if identifiers and not (identifiers[0].get("system") and identifiers[0].get("value")):
                    raise ValueError("Le premier identifiant clinique doit avoir un systeme et une valeur.")
                if (resource.get("meta") or {}).get("source") == C.CHU["source"]:
                    raise ValueError("Un retour ne doit pas reimporter les donnees emises par le CHU.")
                if any(i.get("system") in (C.SYS_SEJOUR_CHU, C.SYS_MESURE_CHU) for i in identifiers):
                    raise ValueError("Une donnee du retour ne doit pas remplacer un identifiant local CHU.")
    return patient
