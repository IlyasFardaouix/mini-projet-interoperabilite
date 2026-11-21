"""
echange.py — règles d'échange H2 ⇄ H1 (aucune dépendance à FastAPI : testable seule)
====================================================================================
Ce module est le « chef d'orchestre » entre la base H2 et les deux adaptateurs v3.3 :

  EXPORT  (H2 → H1)  document Mongo ─► adaptateur_h2_fhir ─► Bundle FHIR « transaction »
                     • consentement vérifié avant l'export (ConsentError → 403) : statut, période,
                       finalité, destinataire ; catégories exclues par le patient retirées du Bundle
                     • ANTI-BOUCLE : ce qui est venu de H1 n'est jamais renvoyé à H1
                     • unités mises en UCUM (mmHg → mm[Hg]), un seul Patient, AuditEvent exclus

  IMPORT  (H1 → H2)  Bundle ─► adaptateur_fhir_h2 ─► fusion dans le dossier ─► base
                     • mode strict : champ obligatoire / unité / valeur impossible → 422
                     • consentement actif exigé (Bundle ET dossier local) → sinon 403
  CONSENTEMENT       recueil, retrait (droit d'opposition) et historique : securite/consentement.py
                     • identité : CIN (urn:ma:cin), identifiant H2, IPP de H1 ; ambiguïté → 409
                     • REJEU SANS DOUBLON : un 2e envoi identique ne crée rien
                     • CONFLITS signalés (alertes), jamais d'écrasement silencieux
                     • simulation possible : tout est calculé, rien n'est écrit
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

import adaptateur_fhir_h2 as fhir_vers_h2
import adaptateur_h2_fhir as h2_vers_fhir
from adaptateur_fhir_h2 import MappingError
from adaptateur_h2_fhir import ConsentError, normalize_dates

# Regles de consentement communes a H1 et H2 (dossier securite/ a la racine du depot).
import sys
from pathlib import Path

_RACINE = str(Path(__file__).resolve().parent.parent)
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)
from securite import consentement as CONS  # noqa: E402
from securite import droit_acces as DA  # noqa: E402

SYSTEM_CIN = fhir_vers_h2.H2_SYSTEM_NATIONAL_ID                 # urn:ma:cin
SYSTEM_ID_H2 = fhir_vers_h2.H2_SYSTEM_PATIENT_ID                # urn:clinique-al-bacar:patient
SYSTEM_IPP_H1 = os.getenv("H1_IPP_SYSTEM", "https://chu-almassira.ma/ipp")
SYSTEM_ECHANGE = "urn:clinique-al-bacar:echange"                # identifiant d'échange (Bundle.identifier)
ORIGINE_H1 = "H1"
# Adresse publique de la passerelle DICOMweb de la clinique, annoncée dans les
# Endpoint DICOM des Bundles. Jamais l'adresse du PACS lui-même (local, sans TLS).
URL_DICOMWEB = os.getenv("H2_DICOMWEB_URL", "https://127.0.0.1:8002/dicom-web")

LISTES_VISITE = ("conditions", "observations", "imaging", "reports", "service_requests", "procedures")
CATALOGUES = {                      # liste du document → (type FHIR, champ clé)
    "_organizations": ("Organization", "org_id"),
    "_practitioners": ("Practitioner", "prac_id"),
    "_roles": ("PractitionerRole", "role_id"),
    "_devices": ("Device", "device_id"),
    "_locations": ("Location", "location_id"),
    "_endpoints": ("Endpoint", "endpoint_id"),
}
UNITES_UCUM = {"mmHg": "mm[Hg]"}    # la base stocke « mmHg » ; UCUM exige « mm[Hg] »


class ErreurEchange(Exception):
    """Erreur renvoyée au client avec un code HTTP et un OperationOutcome."""

    def __init__(self, code: int, type_fhir: str, message: str):
        super().__init__(message)
        self.code, self.type_fhir, self.message = code, type_fhir, message


# ═════════════════════════════════════════════════════════════════════════════
# 1. OUTILS
# ═════════════════════════════════════════════════════════════════════════════
def maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_dt(v) -> Optional[str]:
    """Horodatage → ISO 8601 UTC (pour comparer « 07:43+01:00 » et « 06:43Z »)."""
    if not v:
        return None
    s = str(v)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sans_prefixe(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def _cle(item: dict, fonction) -> Any:
    """Clé naturelle d'un élément ; à défaut, son contenu (pour ne jamais créer de doublon)."""
    k = fonction(item)
    return k if k else ("contenu", json.dumps(_sans_prefixe(item), sort_keys=True, default=str))


def ajouter_audit(doc: dict, action: str, evenement: str, resultat: str = "success", *,
                  agent: str = "API FHIR H2", echange_id: Optional[str] = None) -> None:
    """Journal d'accès (loi 09-08), au format _audit_log[] lu par adaptateur_h2_fhir."""
    entree = {
        "audit_id": f"audit-{uuid.uuid4().hex[:12]}", "event_type": evenement, "action": action,
        "recorded_at": maintenant(), "outcome_code": resultat, "patient_ref": doc["patient_id"],
        "agent_who": agent, "source_observer": "API FHIR H2", "_entity_ref": doc["patient_id"],
    }
    if echange_id:
        entree["exchange_id"] = echange_id
    doc.setdefault("_audit_log", []).append(entree)


def trouver_patient(store, identifiant: str) -> dict:
    """Par identifiant H2 (P2-0051) ou, à défaut, par CIN / identifiant externe. 404 sinon."""
    doc = store.get(identifiant) or store.find_by_identifier(None, identifiant)
    if doc is None:
        raise ErreurEchange(404, "not-found", f"Patient {identifiant} introuvable dans H2.")
    return doc


# ═════════════════════════════════════════════════════════════════════════════
# 2. EXPORT H2 → H1
# ═════════════════════════════════════════════════════════════════════════════
def _est_de(item: Any, origine: str) -> bool:
    return isinstance(item, dict) and item.get("_origin") == origine


def filtrer_pour(doc: dict, destinataire: str) -> dict:
    """ANTI-BOUCLE : copie du dossier sans ce qui a été reçu de `destinataire`."""
    d = copy.deepcopy(doc)
    d["visits"] = [v for v in d.get("visits", []) if not _est_de(v, destinataire)]
    for v in d["visits"]:
        for k in LISTES_VISITE:
            v[k] = [x for x in v.get(k, []) if not _est_de(x, destinataire)]
    d["allergies"] = [a for a in d.get("allergies", []) if not _est_de(a, destinataire)]
    for k in CATALOGUES:
        d[k] = [x for x in d.get(k, []) if not _est_de(x, destinataire)]
    if (d.get("_origine_champs") or {}).get("blood_type") == destinataire:
        d["blood_type"] = None
    return d


def normaliser_unites(doc: dict) -> dict:
    for v in doc.get("visits", []):
        for o in v.get("observations", []):
            if o.get("unit") in UNITES_UCUM:
                o["unit"] = UNITES_UCUM[o["unit"]]
    return doc


def patient_fhir(doc: dict) -> dict:
    """Ressource Patient seule, avec les identifiants externes (ex. IPP de H1)."""
    res = h2_vers_fhir._prune(h2_vers_fhir.build_patient(doc))
    for ext in doc.get("_external_ids") or []:
        res["identifier"].append({"system": ext["system"], "value": ext["value"]})
    return res


TYPES_CATALOGUE = {rtype for rtype, _ in CATALOGUES.values()}


def _references(obj: Any):
    """Toutes les valeurs « reference » d'une ressource (récursif)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "reference" and isinstance(v, str):
                yield v
            else:
                yield from _references(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _references(x)


def elaguer_catalogue(entrees: list) -> list:
    """MINIMISATION (loi 09-08) : la base répète l'annuaire de la clinique (médecins, rôles, équipements,
    services…) dans chaque dossier. On ne garde que les éléments RÉFÉRENCÉS par le dossier du patient,
    directement ou à travers un autre élément gardé."""
    par_ref = {f"{e['resource']['resourceType']}/{e['resource']['id']}": e for e in entrees}
    gardes: set = set()
    pile = [r for e in entrees if e["resource"]["resourceType"] not in TYPES_CATALOGUE
            for r in _references(e["resource"])]
    while pile:
        ref = pile.pop()
        e = par_ref.get(ref)
        if e and e["resource"]["resourceType"] in TYPES_CATALOGUE and ref not in gardes:
            gardes.add(ref)
            pile.extend(_references(e["resource"]))
    return [e for e in entrees if e["resource"]["resourceType"] not in TYPES_CATALOGUE
            or f"{e['resource']['resourceType']}/{e['resource']['id']}" in gardes]


INTERPRETATIONS = {"N": "normal", "H": "high", "L": "low", "HH": "critical-high", "LL": "critical-low", "A": "abnormal"}


def normaliser_observations(doc: dict) -> dict:
    """Schéma natif v3 → clés lues par l'adaptateur : interpretation (N/H/L…) → _interpretation,
    referenceRange → _referenceRange. (bodySite est déduit du LOINC par l'adaptateur.)"""
    for v in doc.get("visits", []):
        for o in v.get("observations", []):
            if o.get("interpretation") and "_interpretation" not in o:
                o["_interpretation"] = INTERPRETATIONS.get(o["interpretation"], o["interpretation"])
            if o.get("referenceRange") and "_referenceRange" not in o:
                o["_referenceRange"] = o["referenceRange"]
    return doc


def _ajouter(doc: dict, cle: str, items: list, champ_id: str, transformer=None) -> None:
    deja = {x.get(champ_id) for x in doc.get(cle, [])}
    for it in items:
        if it.get(champ_id) not in deja:
            doc.setdefault(cle, []).append(transformer(it) if transformer else dict(it))
            deja.add(it.get(champ_id))


def enrichir_annuaire(doc: dict, ref: Optional[dict]) -> dict:
    """Schéma v3 : l'annuaire (organisation, praticiens, rôles, services, endpoints, équipements) est dans des
    collections à part. On y joint, pour CE patient seulement, ce que son dossier référence (minimisation) ;
    l'adaptateur lit ces éléments sous _organizations, _practitioners, _roles, _locations, _endpoints, _devices."""
    if not ref:
        return doc
    par = lambda nom, champ: {x.get(champ): x for x in ref.get(nom, [])}      # noqa: E731
    orgs, pracs = par("organisations", "org_id"), par("practitioners", "prac_id")
    locs, eps, devs = par("locations", "location_id"), par("endpoints", "endpoint_id"), par("devices", "device_id")
    roles = ref.get("practitioner_roles", [])

    prac_ids = {v.get("physician_ref") for v in doc.get("visits", []) if v.get("physician_ref")}
    roles_p = [r for r in roles if r.get("practitioner_ref") in prac_ids]
    org_ids = {doc.get("org_ref")} | {r.get("org_ref") for r in roles_p}
    org_l = [orgs[i] for i in org_ids if i in orgs]
    ep_ids = {o.get("_endpoint_ref") for o in org_l} | {
        i.get("endpoint_ref") for v in doc.get("visits", []) for i in v.get("imaging", [])}
    dev_ids = {o.get("_device") for v in doc.get("visits", []) for o in v.get("observations", [])}
    loc_ids = {r.get("_location_ref") for r in roles_p} | {devs[i].get("_location_ref") for i in dev_ids if i in devs}

    _ajouter(doc, "_organizations", org_l, "org_id")
    _ajouter(doc, "_practitioners", [pracs[i] for i in prac_ids if i in pracs], "prac_id")
    _ajouter(doc, "_roles", roles_p, "role_id")
    _ajouter(doc, "_locations", [locs[i] for i in loc_ids if i in locs], "location_id",
             lambda x: {"location_id": x["location_id"], "name": x.get("name"), "status": "active",
                        "_type_label": x.get("_type")})
    _ajouter(doc, "_endpoints", [eps[i] for i in ep_ids if i in eps], "endpoint_id")
    _ajouter(doc, "_devices", [devs[i] for i in dev_ids if i in devs], "device_id")
    return doc


def construire_bundle(doc: dict, destinataire: str = ORIGINE_H1, inclure_audit: bool = False,
                      echange_id: Optional[str] = None, inclure_catalogue: bool = False,
                      referentiels: Optional[dict] = None) -> dict:
    """Bundle FHIR R5 « transaction » prêt à envoyer. Lève ConsentError si le consentement
    n'autorise pas le partage vers ce destinataire (statut, période, finalité, destinataire)."""
    try:
        decision = CONS.verifier(CONS.depuis_mongo(doc.get("consent")), operation="Export",
                                 destinataire=destinataire)
    except CONS.ConsentementRefuse as exc:
        raise ConsentError(str(exc)) from exc
    d = filtrer_pour(normaliser_observations(normaliser_unites(copy.deepcopy(doc))), destinataire)
    enrichir_annuaire(d, referentiels)
    if not d.get("_organizations"):          # dossier sans annuaire (ex. patient venu de H1) : la clinique reste référencée
        d["_organizations"] = [{"org_id": "CLINIQUE-AL-BACAR", "name": "Clinique Al Baçar", "active": True}]
    try:
        bundle = h2_vers_fhir.convert(d)
    except h2_vers_fhir.MissingPatientIdError as exc:   # l'adaptateur refuse « UNKNOWN » : on le traduit en erreur API
        raise ErreurEchange(500, "exception", f"Export refusé : {exc}") from exc

    # Consent complet (période, destinataires, exclusions), produit par la règle commune.
    for e in bundle["entry"]:
        res = e["resource"]
        if res["resourceType"] == "Consent":
            e["resource"] = CONS.vers_fhir(CONS.depuis_mongo(d.get("consent")), id_ressource=res["id"],
                                          patient_ref=res["subject"],
                                          organisation_ref=(res.get("controller") or [None])[0])
    # Images : l'autre hôpital passe par la passerelle sécurisée, pas par le PACS.
    for e in bundle["entry"]:
        res = e["resource"]
        if res["resourceType"] == "Endpoint" and any(
                "dicom" in (c.get("code") or "")
                for cc in res.get("connectionType") or [] for c in cc.get("coding") or []):
            res["address"] = URL_DICOMWEB
    # Catégories que le patient a exclues du partage (ex. imagerie).
    bundle, _ = CONS.filtrer_bundle(bundle, decision.categories_exclues)

    entrees = [e for e in bundle["entry"]
               if inclure_audit or e["resource"]["resourceType"] != "AuditEvent"]
    if not inclure_catalogue:
        entrees = elaguer_catalogue(entrees)
    for e in entrees:
        res = e["resource"]
        if res["resourceType"] == "Patient":
            res["identifier"] = patient_fhir(d)["identifier"]
            cin = d.get("national_id")
            # Patient : création conditionnelle (« crée si ce CIN n'existe pas »)
            e["request"] = ({"method": "POST", "url": "Patient",
                             "ifNoneExist": f"identifier={SYSTEM_CIN}|{cin}"} if cin
                            else {"method": "PUT", "url": f"Patient/{res['id']}"})
        else:
            # autres ressources : PUT avec identifiant stable = mise à jour ou création (rejeu sans doublon)
            e["request"] = {"method": "PUT", "url": f"{res['resourceType']}/{res['id']}"}

    bundle["type"] = "transaction"
    bundle["entry"] = entrees
    bundle["identifier"] = {"system": SYSTEM_ECHANGE, "value": echange_id or str(uuid.uuid4())}
    return bundle


def exporter(store, identifiant: str, *, destinataire: str = ORIGINE_H1,
             inclure_audit: bool = False, inclure_catalogue: bool = False) -> dict:
    """GET /api/patients/{id}/bundle : contrôle le consentement, trace l'accès, renvoie le Bundle."""
    doc = trouver_patient(store, identifiant)
    echange_id = str(uuid.uuid4())
    try:
        bundle = construire_bundle(doc, destinataire, inclure_audit, echange_id, inclure_catalogue,
                                   store.referentiels())
    except ConsentError as exc:
        ajouter_audit(doc, "read", "Export du dossier", "refused",
                      agent=f"Export vers {destinataire}", echange_id=echange_id)
        store.remplacer(doc)
        raise ErreurEchange(403, "forbidden", str(exc))
    ajouter_audit(doc, "read", "Export du dossier", agent=f"Export vers {destinataire}",
                  echange_id=echange_id)
    store.remplacer(doc)
    return bundle


# ═════════════════════════════════════════════════════════════════════════════
# 3. IMPORT H1 → H2
# ═════════════════════════════════════════════════════════════════════════════
class Rapport:
    """Compte rendu d'un import (mêmes rubriques que le rapport de l'API H1)."""

    def __init__(self, echange_id: str, simulation: bool):
        self.echange_id, self.simulation = echange_id, simulation
        self.patient_id: Optional[str] = None
        self.patient_provisoire = False
        self.patient_cree = False
        self.deja_traite = False
        self.lignes: Counter = Counter()      # éléments écrits (créés ou complétés)
        self.deja: Counter = Counter()        # éléments déjà présents (rejeu)
        self.alertes: list[dict] = []
        self.ignores: list[dict] = []

    def alerte(self, code: str, message: str, **extra):
        self.alertes.append({"code": code, "message": message, **extra})

    def dict(self) -> dict:
        r = {"simulation": self.simulation, "modifications_conservees": not self.simulation,
             "echange_id": self.echange_id, "patient_id": self.patient_id,
             "patient_cree": self.patient_cree, "deja_traite": self.deja_traite,
             "lignes_par_type": dict(self.lignes), "deja_presents": dict(self.deja),
             "alertes": self.alertes, "ignores": self.ignores}
        if self.patient_provisoire:
            r["patient_id_provisoire"] = True
        return r


def verifier_structure(bundle: Any, rapport: Rapport) -> None:
    if (not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle"
            or bundle.get("type") not in ("collection", "transaction") or not bundle.get("entry")):
        raise ErreurEchange(400, "invalid",
                            "Attendu : un Bundle (type transaction ou collection) avec au moins une entrée.")
    entrees = bundle["entry"]
    n_patients = sum(1 for e in entrees if (e.get("resource") or {}).get("resourceType") == "Patient")
    if n_patients != 1:
        raise ErreurEchange(422, "invalid", f"Un seul Patient est attendu dans le Bundle ({n_patients} trouvé(s)).")
    if bundle["type"] == "transaction":
        sans_instruction = 0
        for e in entrees:
            req, rtype = e.get("request"), (e.get("resource") or {}).get("resourceType", "")
            if not req:
                sans_instruction += 1
                continue
            if str(req.get("method", "")).upper() not in ("PUT", "POST"):
                raise ErreurEchange(422, "not-supported",
                                    f"Instruction {req.get('method')} non supportée (seuls PUT et POST sont acceptés).")
            if str(req.get("url", "")).split("?")[0].split("/")[0] != rtype:
                raise ErreurEchange(422, "invalid",
                                    f"request.url « {req.get('url')} » ne correspond pas à la ressource {rtype}.")
        if sans_instruction:
            rapport.alerte("instruction-absente",
                           f"{sans_instruction} entrée(s) sans request : traitées comme des mises à jour (PUT).")


def convertir(bundle: dict, rapport: Rapport) -> dict:
    """Bundle → document H2. Le consentement est contrôlé avant le contenu : 403 prime sur 422."""
    consents = [e["resource"] for e in bundle["entry"]
                if (e.get("resource") or {}).get("resourceType") == "Consent"]
    if not consents:
        raise ErreurEchange(403, "forbidden", "Transfert refusé : aucun consentement dans le Bundle (loi 09-08).")
    recu = CONS.depuis_fhir(consents[0])
    try:
        decision = CONS.verifier(recu, operation="Transfert", destinataire="H2")
    except CONS.ConsentementRefuse as exc:
        raise ErreurEchange(403, "forbidden", str(exc)) from exc
    bundle, ignorees = CONS.filtrer_bundle(bundle, decision.categories_exclues)
    if ignorees:
        rapport.alerte("consentement-partiel",
                       f"{ignorees} ressource(s) ignorée(s) : catégorie(s) exclue(s) du partage par le patient "
                       f"({', '.join(sorted(decision.categories_exclues))}).")

    try:
        doc = fhir_vers_h2.bundle_to_h2_document(bundle, strict=False)
    except MappingError as exc:
        raise ErreurEchange(422, "invalid", str(exc))
    erreurs = [e for e in doc.pop("_mapping_errors", []) if not e.startswith("Aucun Consent")]
    doc["consent"] = CONS.vers_mongo(recu)              # période, destinataires et exclusions conservés
    if erreurs:
        raise ErreurEchange(422, "invalid", "; ".join(erreurs))

    nb_audit = sum(1 for e in bundle["entry"] if (e.get("resource") or {}).get("resourceType") == "AuditEvent")
    if nb_audit:
        rapport.ignores.append({"type": "AuditEvent", "nombre": nb_audit,
                                "raison": "le journal d'accès est propre à chaque hôpital"})
    doc["_audit_log"] = []
    return doc


def apparier(doc_in: dict, store) -> Optional[dict]:
    """Retrouve le dossier H2 correspondant. None = nouveau patient. 409 si ambigu."""
    ident = []
    if doc_in.get("patient_id"):
        if not store.get(doc_in["patient_id"]):
            raise ErreurEchange(422, "not-found",
                                f"Identifiant H2 {doc_in['patient_id']} inconnu : "
                                "ne fournir que les identifiants que H2 a déjà communiqués.")
        ident.append((SYSTEM_ID_H2, doc_in["patient_id"]))
    if doc_in.get("national_id"):
        ident.append((SYSTEM_CIN, doc_in["national_id"]))
    ident += [(e["system"], e["value"]) for e in doc_in.get("_external_ids") or []]
    if not ident:
        raise ErreurEchange(422, "required",
                            "Identité insuffisante : le Patient doit porter un CIN (urn:ma:cin) "
                            "ou un identifiant de l'hôpital d'origine (ex. IPP).")
    trouves: dict[str, dict] = {}
    for system, value in ident:
        for d in store.find_all_by_identifier(system, value):
            trouves[d["patient_id"]] = d
    if len(trouves) > 1:
        raise ErreurEchange(409, "multiple-matches",
                            "Identité ambiguë : ces identifiants correspondent à plusieurs dossiers H2 "
                            f"({', '.join(sorted(trouves))}). Rapprochement à valider manuellement.")
    return next(iter(trouves.values())) if trouves else None


# ── marquage de l'origine ────────────────────────────────────────────────────
def _marquer(doc: dict, origine: str) -> None:
    for k in CATALOGUES:
        for x in doc.get(k, []):
            x["_origin"] = origine
    for a in doc.get("allergies", []):
        a["_origin"] = origine
    for v in doc.get("visits", []):
        _marquer_visite(v, origine)


def _marquer_visite(v: dict, origine: str) -> None:
    v["_origin"] = origine
    for k in LISTES_VISITE:
        for x in v.get(k, []):
            x["_origin"] = origine


# ── création d'un nouveau dossier ────────────────────────────────────────────
def _compter_visite(v: dict, rapport: Rapport) -> None:
    rapport.lignes["Encounter"] += 1
    for k, (rtype, _) in SOUS_LISTES.items():
        rapport.lignes[rtype] += len(v.get(k, []))


def nouveau_document(doc_in: dict, origine: str, rapport: Rapport) -> dict:
    doc = copy.deepcopy(doc_in)
    doc["patient_id"] = None                           # attribué par la base (P2-xxxx)
    _marquer(doc, origine)
    doc["_origin"] = origine
    doc["_origine_champs"] = {"blood_type": origine} if doc.get("blood_type") else {}
    doc["consent"]["_origin"] = origine
    rapport.lignes["Patient"] += 1
    rapport.lignes["Consent"] += 1
    rapport.lignes["AllergyIntolerance"] += len(doc.get("allergies", []))
    for k, (rtype, _) in CATALOGUES.items():
        rapport.lignes[rtype] += len(doc.get(k, []))
    for v in doc.get("visits", []):
        _compter_visite(v, rapport)
    if not doc.get("national_id"):
        rapport.alerte("identite-sans-cin",
                       "Patient créé sans CIN : le rapprochement ne repose que sur l'identifiant de l'hôpital d'origine "
                       "(risque de doublon, à vérifier manuellement).")
    rapport.lignes = +rapport.lignes                   # retire les compteurs à 0
    return doc


# ── fusion dans un dossier existant ──────────────────────────────────────────
SOUS_LISTES = {
    "conditions": ("Condition", lambda c: (c.get("system"), c.get("code"))),
    "observations": ("Observation", lambda o: (o.get("loinc"), _norm_dt(o.get("at")))),
    "imaging": ("ImagingStudy", lambda i: i.get("imaging_id") or i.get("study_uid")),
    "reports": ("DiagnosticReport", lambda r: r.get("report_id")),
    "service_requests": ("ServiceRequest", lambda s: s.get("sr_id")),
    "procedures": ("Procedure", lambda p: p.get("proc_id")),
}
CHAMPS_IDENTITE = ("last_name", "first_name", "sex", "birth_date", "phone", "national_id", "blood_type")
CHAMPS_VISITE = ("visit_type", "department", "admitted_at", "discharged_at", "physician", "reason")


def _valeur_comparable(champ: str, v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    if champ == "birth_date":
        return h2_vers_fhir._fhir_date(str(v))
    if champ in ("admitted_at", "discharged_at"):
        return _norm_dt(v)
    if champ in ("last_name", "first_name", "department", "physician", "reason"):
        return " ".join(str(v).split()).casefold()
    return str(v).strip()


def _fusion_champs(cible: dict, entrant: dict, champs, rapport: Rapport, rtype: str,
                   origine: str, ou: str, origine_champs: Optional[dict] = None) -> bool:
    """Complète les champs vides ; signale (sans écraser) les valeurs qui diffèrent."""
    modifie = False
    for champ in champs:
        e, n = _valeur_comparable(champ, cible.get(champ)), _valeur_comparable(champ, entrant.get(champ))
        if n is None:
            continue
        if e is None:
            cible[champ] = entrant[champ]
            if origine_champs is not None:
                origine_champs[champ] = origine
            modifie = True
        elif e != n:
            rapport.alerte("conflit", f"{ou} : {champ} diffère (H2 « {cible.get(champ)} » / reçu « {entrant.get(champ)} ») "
                           "— valeur H2 conservée.", type=rtype, champ=champ,
                           valeur_h2=cible.get(champ), valeur_recue=entrant.get(champ))
    return modifie


def fusionner(existant: dict, entrant: dict, origine: str, rapport: Rapport) -> dict:
    """Ajoute à `existant` ce qui manque ; ne modifie jamais une valeur déjà présente."""
    doc = normalize_dates(copy.deepcopy(existant))     # dates BSON → chaînes ISO (comparables)
    doc.setdefault("_origine_champs", {})

    # identité
    modifie = _fusion_champs(doc, entrant, CHAMPS_IDENTITE, rapport, "Patient", origine,
                             f"Patient {doc['patient_id']}", doc["_origine_champs"])
    adr_e, adr_n = doc.setdefault("address", {}) or {}, entrant.get("address") or {}
    doc["address"] = adr_e
    for champ in ("street", "city"):
        if adr_n.get(champ) and not adr_e.get(champ):
            adr_e[champ] = adr_n[champ]
            modifie = True
        elif adr_n.get(champ) and adr_e.get(champ) and adr_n[champ].casefold() != adr_e[champ].casefold():
            rapport.alerte("conflit", f"Patient {doc['patient_id']} : adresse ({champ}) diffère — valeur H2 conservée.",
                           type="Patient", champ=f"address.{champ}")
    for k in ("_gp", "_org", "_links", "_contact"):
        if not doc.get(k) and entrant.get(k):
            doc[k] = entrant[k]
            modifie = True
    connus = {(x.get("system"), x.get("value")) for x in doc.get("_external_ids") or []}
    for x in entrant.get("_external_ids") or []:
        if (x["system"], x["value"]) not in connus:
            doc.setdefault("_external_ids", [])
            doc["_external_ids"] = (doc["_external_ids"] or []) + [x]
            modifie = True
    rapport.lignes["Patient"] += 1 if modifie else 0
    rapport.deja["Patient"] += 0 if modifie else 1

    # consentement et allergies
    rapport.deja["Consent"] += 1                       # le consentement local fait foi
    _fusion_liste(doc, entrant, "allergies", "AllergyIntolerance",
                  lambda a: a.get("allergy_id"), origine, rapport)

    # référentiels
    for k, (rtype, champ_cle) in CATALOGUES.items():
        _fusion_liste(doc, entrant, k, rtype, lambda x, c=champ_cle: x.get(c), origine, rapport)

    # visites
    visites = {v.get("visit_id"): v for v in doc.get("visits", [])}
    for v_in in entrant.get("visits", []):
        v = visites.get(v_in.get("visit_id"))
        if v is None:
            v_new = copy.deepcopy(v_in)
            _marquer_visite(v_new, origine)
            doc.setdefault("visits", []).append(v_new)
            _compter_visite(v_new, rapport)
            continue
        modif_v = _fusion_champs(v, v_in, CHAMPS_VISITE, rapport, "Encounter", origine,
                                 f"Encounter {v.get('visit_id')}")
        rapport.lignes["Encounter"] += 1 if modif_v else 0
        rapport.deja["Encounter"] += 0 if modif_v else 1
        for k, (rtype, f) in SOUS_LISTES.items():
            _fusion_liste(v, v_in, k, rtype, f, origine, rapport)

    rapport.lignes = +rapport.lignes
    rapport.deja = +rapport.deja
    return doc


def _fusion_liste(cible: dict, entrant: dict, nom: str, rtype: str, fonction_cle, origine: str,
                  rapport: Rapport) -> None:
    liste = cible.setdefault(nom, [])
    index = {_cle(x, fonction_cle): x for x in liste}
    for x_in in entrant.get(nom, []) or []:
        existant = index.get(_cle(x_in, fonction_cle))
        if existant is None:
            x = copy.deepcopy(x_in)
            x["_origin"] = origine
            liste.append(x)
            rapport.lignes[rtype] += 1
            continue
        rapport.deja[rtype] += 1
        if rtype == "Observation":                     # même mesure, valeur différente = conflit
            for champ in ("value", "value_text", "components"):
                if x_in.get(champ) is not None and existant.get(champ) not in (None, x_in.get(champ)):
                    rapport.alerte("conflit", f"Observation {x_in.get('loinc')} du {x_in.get('at')} : "
                                   f"{champ} diffère — valeur H2 conservée.", type="Observation", champ=champ,
                                   valeur_h2=existant.get(champ), valeur_recue=x_in.get(champ))


# ── point d'entrée ───────────────────────────────────────────────────────────
def _echange_du_bundle(bundle: Any) -> Optional[str]:
    """Identifiant d'échange porté par le Bundle (Bundle.identifier), s'il y en a un."""
    ident = bundle.get("identifier") if isinstance(bundle, dict) else None
    if isinstance(ident, list):
        ident = ident[0] if ident else None
    return ident.get("value") if isinstance(ident, dict) else None


def importer(bundle: Any, store, *, commit: bool, exchange_id: Optional[str] = None,
             origine: str = ORIGINE_H1) -> tuple[dict, int]:
    """POST /api/retours (commit=True) ou /api/retours/simulation (commit=False).
    Retourne (rapport, code HTTP) : 201 si un patient est créé, 200 sinon."""
    fourni = exchange_id or _echange_du_bundle(bundle)
    rapport = Rapport(fourni or str(uuid.uuid4()), simulation=not commit)

    verifier_structure(bundle, rapport)
    doc_in = convertir(bundle, rapport)
    existant = apparier(doc_in, store)

    if existant is not None:
        rapport.patient_id = existant["patient_id"]
        locale = CONS.evaluer(CONS.depuis_mongo(existant.get("consent")))
        if not locale.autorise:
            raise ErreurEchange(403, "forbidden",
                                f"Réception refusée : consentement local du patient {existant['patient_id']} : "
                                f"{locale.motif} (loi 09-08).")
        if fourni and any(a.get("exchange_id") == fourni for a in existant.get("_audit_log", [])):
            rapport.deja_traite = True                 # même échange déjà reçu : rien à refaire
            return rapport.dict(), 200
        doc = fusionner(existant, doc_in, origine, rapport)
        if commit:
            ajouter_audit(doc, "update", "Réception d'un dossier (Bundle)",
                          agent=f"{origine} → H2", echange_id=rapport.echange_id)
            store.remplacer(doc)                       # données + audit dans UN document = atomique
        return rapport.dict(), 200

    doc = nouveau_document(doc_in, origine, rapport)
    rapport.patient_cree = True
    if commit:
        def finaliser(d):
            ajouter_audit(d, "create", "Réception d'un dossier (Bundle)",
                          agent=f"{origine} → H2", echange_id=rapport.echange_id)
        rapport.patient_id = store.creer(doc, finaliser)["patient_id"]
    else:
        rapport.patient_id, rapport.patient_provisoire = store.next_id(), True
    return rapport.dict(), 201 if commit else 200


# ═════════════════════════════════════════════════════════════════════════════
# 3 bis. GESTION DU CONSENTEMENT (recueil, retrait, historique)
# ═════════════════════════════════════════════════════════════════════════════
def etat_consentement(doc: dict) -> dict:
    """Consentement en vigueur, décision de partage et historique (plus récent d'abord)."""
    actuel = CONS.depuis_mongo(doc.get("consent"))
    decision = CONS.evaluer(actuel)
    return {
        "patient_id": doc["patient_id"],
        "partage_autorise": decision.autorise,
        "motif": decision.motif,
        "actuel": actuel.en_dict() if actuel else None,
        "historique": [CONS.depuis_mongo(h).en_dict()
                       for h in reversed(doc.get("consent_history", [])) if h],
    }


def lire_consentement(store, identifiant: str) -> dict:
    return etat_consentement(trouver_patient(store, identifiant))


def _nouvelle_version(store, doc: dict, nouveau, evenement: str, agent: str) -> dict:
    """La version précédente passe dans l'historique : rien n'est écrasé."""
    if doc.get("consent"):
        doc.setdefault("consent_history", []).append(doc["consent"])
    doc["consent"] = CONS.vers_mongo(nouveau)          # recueilli ici : plus d'origine externe
    ajouter_audit(doc, "update", evenement, agent=agent)
    store.remplacer(doc)                               # consentement + historique + audit : un seul document
    return etat_consentement(doc)


def enregistrer_consentement(store, identifiant: str, corps: Any, *, agent: str) -> dict:
    """Recueil d'un consentement (actif ou refusé). 422 si la saisie est incohérente."""
    doc = trouver_patient(store, identifiant)
    try:
        nouveau = CONS.depuis_saisie(corps)
    except CONS.ConsentementInvalide as exc:
        raise ErreurEchange(422, "invalid", str(exc)) from exc
    return _nouvelle_version(store, doc, nouveau, f"Consentement recueilli ({nouveau.statut})",
                             f"{agent} / {nouveau.recueilli_par}")


def retirer_consentement(store, identifiant: str, corps: Any, *, agent: str) -> dict:
    """Retrait du consentement (droit d'opposition) : 409 s'il n'y a rien à retirer."""
    doc = trouver_patient(store, identifiant)
    corps = corps if isinstance(corps, dict) else {}
    actuel = CONS.depuis_mongo(doc.get("consent"))
    if actuel is None or actuel.statut != CONS.ACTIF:
        raise ErreurEchange(409, "conflict", "Aucun consentement actif à retirer pour ce patient.")
    try:
        nouveau = CONS.retirer(actuel, corps.get("motif"), recueilli_par=corps.get("recueilli_par"))
    except CONS.ConsentementInvalide as exc:
        raise ErreurEchange(422, "invalid", str(exc)) from exc
    return _nouvelle_version(store, doc, nouveau, "Consentement retiré",
                             f"{agent} / {nouveau.recueilli_par}")


# ═════════════════════════════════════════════════════════════════════════════
# 3 ter. IMAGERIE : qui peut lire une étude DICOM (passerelle /dicom-web)
# ═════════════════════════════════════════════════════════════════════════════
def autoriser_imagerie(store, study_uid: str, *, destinataire: Optional[str]) -> str:
    """Identifiant H2 du patient de l'étude si la lecture est permise.

    `destinataire` : établissement qui appelle (ex. « H1 »), None pour le personnel
    de la clinique. Pour un autre établissement : consentement valide vers lui,
    imagerie non exclue par le patient, et jamais une étude qu'il nous a lui-même
    transmise (anti-boucle).
    """
    doc = store.find_by_study_uid(study_uid)
    if doc is None:
        raise ErreurEchange(404, "not-found", "Étude d'imagerie inconnue de H2.")
    if destinataire:
        try:
            decision = CONS.verifier(CONS.depuis_mongo(doc.get("consent")),
                                     operation="Partage de l'imagerie", destinataire=destinataire)
        except CONS.ConsentementRefuse as exc:
            raise ErreurEchange(403, "forbidden", str(exc)) from exc
        if "imagerie" in decision.categories_exclues:
            raise ErreurEchange(403, "forbidden",
                                "Partage refusé : le patient a exclu l'imagerie du partage (loi 09-08).")
        etude = next(i for v in doc.get("visits", []) for i in v.get("imaging", [])
                     if i.get("study_uid") == study_uid)
        if _est_de(etude, destinataire):
            raise ErreurEchange(403, "forbidden", "Anti-boucle : cette étude provient de "
                                + destinataire + ".")
    return doc["patient_id"]


# ═════════════════════════════════════════════════════════════════════════════
# 3 quater. DROIT D'ACCÈS DE LA PERSONNE (loi 09-08, art. 7)
# ═════════════════════════════════════════════════════════════════════════════
def _destinataire_de_l_audit(entree: dict) -> Optional[str]:
    agent = str(entree.get("agent_who") or "")
    if agent.startswith("Export vers "):
        return agent.removeprefix("Export vers ").strip() or None
    return None


def _origines(valeur: Any, compte: Counter) -> None:
    if isinstance(valeur, dict):
        if valeur.get("_origin"):
            compte[valeur["_origin"]] += 1
        for enfant in valeur.values():
            _origines(enfant, compte)
    elif isinstance(valeur, list):
        for enfant in valeur:
            _origines(enfant, compte)


def droit_acces(store, identifiant: str, *, agent: str) -> dict:
    """Tout ce que la clinique détient sur la personne, sous forme intelligible :
    dossier complet en FHIR R5 (sans filtre de consentement ni anti-boucle : c'est
    SON dossier), consentement et historique, accès, destinataires, origine.
    La demande est elle-même ajoutée au journal du patient."""
    doc = trouver_patient(store, identifiant)
    ajouter_audit(doc, "read", "Droit d'accès (loi 09-08, art. 7)", agent=agent)
    store.remplacer(doc)

    copie = normaliser_observations(normaliser_unites(copy.deepcopy(doc)))
    try:
        bundle = h2_vers_fhir.convert(copie, enforce_consent=False)
    except h2_vers_fhir.MissingPatientIdError as exc:
        raise ErreurEchange(500, "exception", f"Dossier illisible : {exc}") from exc
    bundle["type"] = "collection"
    bundle["entry"] = [{"fullUrl": e.get("fullUrl"), "resource": e["resource"]}
                       for e in bundle["entry"] if e["resource"]["resourceType"] != "AuditEvent"]

    acces = [DA.entree_acces(a.get("recorded_at"), a.get("action"), a.get("event_type"),
                             agent=a.get("agent_who"), resultat=a.get("outcome_code"),
                             echange_id=a.get("exchange_id"), destinataire=_destinataire_de_l_audit(a))
             for a in doc.get("_audit_log", [])]
    origines = Counter()
    _origines(doc, origines)
    origine = [{"etablissement": DA.ETABLISSEMENTS.get(o, o), "code": o, "elements": n}
               for o, n in sorted(origines.items())]
    return DA.reponse(service="H2", patient=doc["patient_id"], donnees={"dossier_fhir": bundle},
                      consentement=etat_consentement(doc), acces=acces, origine_des_donnees=origine)


# ═════════════════════════════════════════════════════════════════════════════
# 4. POST /Patient (patient seul, sans dossier)
# ═════════════════════════════════════════════════════════════════════════════
def creer_patient_seul(patient: Any, store) -> dict:
    if not isinstance(patient, dict) or patient.get("resourceType") != "Patient":
        raise ErreurEchange(400, "invalid", "resourceType doit valoir « Patient ».")
    bundle = {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": patient}]}
    try:
        doc = fhir_vers_h2.bundle_to_h2_document(bundle, strict=False)
    except MappingError as exc:
        raise ErreurEchange(422, "invalid", str(exc))
    doc.pop("_mapping_errors", None)
    doc["patient_id"] = None                           # l'API attribue toujours l'identifiant
    existant = apparier(doc, store)
    if existant:
        raise ErreurEchange(409, "duplicate",
                            f"Un patient avec ces identifiants existe déjà ({existant['patient_id']}).")
    # sans Consent : enregistré mais NON exportable ($everything / bundle → 403)
    return store.creer(doc, lambda d: ajouter_audit(d, "create", "Création de patient"))
