#!/usr/bin/env python3
"""
adaptateur_h2_fhir.py  —  v3.4  (FHIR R5 — 17 ressources)
=======================================================================
Adaptateur H2 (MongoDB Clinique Al Baçar) → Bundle FHIR R5 (collection)

Changements v3.4 (par rapport à v3.3)
-------------------------------------
  • JAMAIS d'identifiant « UNKNOWN » : un document sans patient_id lève
    MissingPatientIdError (attribuer P2-xxxx avant l'export). Les trois
    valeurs par défaut « UNKNOWN » (Patient, groupe sanguin, Consent) sont supprimées.
  • Références « Type/ID » : la partie ID passe par _safe_id (ex. PRAC-FASSI_FIHRI
    → Practitioner/PRAC-FASSI-FIHRI), elle correspond donc à l'id de la ressource.

Changements v3.3 (par rapport à v3.2)
-------------------------------------
  • IDs FHIR STABLES : Patient=patient_id, Encounter=visit_id,
    Observation=obs-<visit>-<n>, Condition=cond-<visit>-<n>,
    ImagingStudy=img-<visit> (ou imaging_id), Consent=consent-<patient>.
    → les références (DiagnosticReport.study…) se résolvent, et un ré-export
      ne crée plus de doublons chez le récepteur.
  • fullUrl = <FHIR_BASE_URL>/<Type>/<id> (références relatives valides).
  • UID DICOM : valeur « urn:oid:<UID> » (system urn:dicom:uid). Le CIN reste
    sous le system « urn:ma:cin » (inchangé).
  • series.uid n'est plus inventé : la série n'est émise que si series_uid existe.
  • Dates BSON (datetime) normalisées en ISO 8601 UTC ; birth_date JJ/MM/AAAA
    (cas D13) converti, sinon omis.
  • blood_type exporté en Observation (LOINC 882-1, valueString, category laboratory).
  • PIO : bodySite déduit du LOINC, referenceRange 10–21 et interpretation
    (H / L / N) calculés si absents (alerte S2).
  • Consent R5 : statuts R5 (refused → not-done + decision deny), purpose = Coding,
    policyBasis.url corrigée (cndp.ma). Export BLOQUÉ si consentement non actif
    (ConsentError) — désactivable par enforce_consent=False.
  • ServiceRequest.code = CodeableReference (R5). Condition.clinicalStatus ajouté.
  • Références typées (Location/…, Endpoint/…), serviceProvider = organisation réelle
    du document, Endpoint DICOM rattaché automatiquement aux ImagingStudy.
  • Catégories d'Observation alignées (glycémie / HbA1c = laboratory).
  • Pas de chaînes vides / listes vides dans les ressources (_prune).

Usage CLI
---------
  python adaptateur_h2_fhir.py --patient doc_h2.json --out bundle_fhir.json --pretty
  python adaptateur_h2_fhir.py --patient doc_h2.json --visit-id V2-0051-1
"""

import argparse
import json
import logging
import re
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("h2_fhir")

# ══════════════════════════════════════════════════════════════════════════════
# 0. CONFIGURATION ET TABLES DE CORRESPONDANCE
# ══════════════════════════════════════════════════════════════════════════════

# À aligner avec l'API REST (base du serveur FHIR). Sert à construire les fullUrl.
FHIR_BASE_URL = "https://localhost:8002/fhir"

H2_SYSTEM_PATIENT_ID  = "urn:clinique-al-bacar:patient"
H2_SYSTEM_NATIONAL_ID = "urn:ma:cin"                      # CIN (inchangé)
FHIR_SYSTEM_LOINC     = "http://loinc.org"
FHIR_SYSTEM_ICD10     = "http://hl7.org/fhir/sid/icd-10"
FHIR_SYSTEM_SNOMED    = "http://snomed.info/sct"
FHIR_SYSTEM_ACT_CODE  = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
FHIR_SYSTEM_DICOM_UID = "urn:dicom:uid"                   # system de l'identifiant d'étude
FHIR_SYSTEM_ACSN      = "http://terminology.hl7.org/CodeSystem/v2-0203"
FHIR_SYSTEM_DICOM_MOD = "http://dicom.nema.org/resources/ontology/DCM"
FHIR_SYSTEM_ENDPOINT_CT = "http://terminology.hl7.org/CodeSystem/endpoint-connection-type"
UCUM = "http://unitsofmeasure.org"

DEFAULT_CLINIC_REF = {
    "reference": "Organization/CLINIQUE-AL-BACAR",
    "display": "Clinique Al Baçar",
}

GENDER_MAP_REVERSE = {1: "male", 2: "female"}
VISIT_TYPE_MAP = {1: "EMER", 2: "AMB", 3: "IMP"}
ENCOUNTER_CLASS_DISPLAY = {"EMER": "Emergency", "AMB": "Ambulatory", "IMP": "Inpatient encounter"}

# H2 → statuts FHIR R5 (R5 : draft | active | inactive | not-done | entered-in-error | unknown)
CONSENT_STATUS_MAP_REVERSE = {
    "active":   "active",
    "refused":  "not-done",     # R4 « rejected » n'existe plus en R5 ; decision=deny porte le refus
    "proposed": "draft",
    "inactive": "inactive",
}

BODYSITE_LABEL_TO_SNOMED = {
    "right eye": {"code": "18944008", "display": "Right eye structure"},
    "left eye":  {"code": "8966001",  "display": "Left eye structure"},
}
LOINC_BODYSITE = {"79892-6": "right eye", "79893-4": "left eye"}   # PIO OD / OG

INTERPRETATION_MAP_REVERSE = {
    "high": "H", "critical-high": "HH", "low": "L",
    "critical-low": "LL", "normal": "N", "abnormal": "A",
}

BLOOD_PRESSURE_PANEL_LOINC = "85354-9"
BLOOD_GROUP_LOINC = "882-1"          # ABO + Rh (à reconfirmer sur loinc.org)
BLOOD_GROUP_STATUS = "final"         # H2 ne stocke pas la validation labo : à discuter

PIO_LOINCS = ("79892-6", "79893-4")
PIO_RANGE = {"low": 10, "high": 21, "unit": "mm[Hg]"}   # tables_fhir_h2 §20

LOINC_DISPLAY = {
    "79892-6": "Intraocular pressure of Right eye",
    "79893-4": "Intraocular pressure of Left eye",
    "85354-9": "Blood pressure panel",
    "8480-6": "Systolic blood pressure", "8462-4": "Diastolic blood pressure",
    "2339-0": "Glucose [Mass/volume] in Blood", "4548-4": "Hemoglobin A1c",
    "8867-4": "Heart rate", "59408-5": "Oxygen saturation by pulse oximetry",
    "2708-6": "Oxygen saturation", "8310-5": "Body temperature",
    BLOOD_GROUP_LOINC: "ABO and Rh group [Type] in Blood",
}
LOINC_CATEGORY = {
    "85354-9": "vital-signs", "8480-6": "vital-signs", "8462-4": "vital-signs",
    "8867-4": "vital-signs", "59408-5": "vital-signs", "2708-6": "vital-signs",
    "8310-5": "vital-signs",
    "2339-0": "laboratory", "4548-4": "laboratory", BLOOD_GROUP_LOINC: "laboratory",
    "79892-6": "exam", "79893-4": "exam",
}

DICOM_MODALITY_DISPLAY = {
    "OPT": "Ophthalmic Tomography (OCT)", "OP": "Ophthalmic Photography",
    "OPV": "Ophthalmic Visual Field", "OAM": "Ophthalmic Axial Measurements",
    "OPM": "Ophthalmic Mapping", "IOL": "Intraocular Lens Data",
    "SLO": "Scanning Laser Ophthalmoscopy",
}

AUDIT_ACTION_MAP_REVERSE = {"create": "C", "read": "R", "update": "U", "delete": "D", "execute": "E"}
_CRITICALITY_MAP = {"ELEVEE": "high", "MOYENNE": "unable-to-assess", "FAIBLE": "low"}
_SEVERITY_FHIR_VALUES = {"mild", "moderate", "severe"}

CNDP_POLICY_URL = "https://www.cndp.ma"   # autorité de la loi 09-08 (à confirmer)


class ConsentError(Exception):
    """Export refusé : consentement absent ou non actif (loi 09-08)."""


# ══════════════════════════════════════════════════════════════════════════════
# 1. UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_uuid() -> str:
    return str(uuid.uuid4())


def normalize_dates(obj: Any) -> Any:
    """datetime/date BSON → chaînes ISO 8601 (UTC pour les datetime)."""
    if isinstance(obj, datetime):
        if obj.tzinfo is None:                      # pymongo renvoie du naïf = UTC
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: normalize_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_dates(v) for v in obj]
    return obj


def _fhir_date(value: Optional[str]) -> Optional[str]:
    """Accepte AAAA-MM-JJ[...] ; convertit JJ/MM/AAAA (cas D13) ; sinon None."""
    if not value:
        return None
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        logger.warning("Date au format JJ/MM/AAAA convertie : %s", s)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    logger.warning("Date invalide ignorée : %r", s)
    return None


def _safe_id(value: str) -> str:
    """ID FHIR valide : [A-Za-z0-9\\-.]{1,64}."""
    return re.sub(r"[^A-Za-z0-9\-.]", "-", str(value))[:64]


def _prune(obj: Any) -> Any:
    """Supprime None, "", [] et {} (invalides ou inutiles en FHIR JSON)."""
    if isinstance(obj, dict):
        out = {k: _prune(v) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(obj, list):
        out = [_prune(v) for v in obj]
        return [v for v in out if v not in (None, "", [], {})]
    return obj


class MissingPatientIdError(ValueError):
    """Document H2 sans patient_id : export impossible (pas d'identifiant « UNKNOWN »)."""


def _require_pid(doc: dict) -> str:
    pid = doc.get("patient_id")
    if not pid:
        raise MissingPatientIdError(
            "Document sans patient_id : attribuer un identifiant H2 (P2-xxxx) avant l'export.")
    return str(pid)


def _ref(rtype: str, value: Optional[str]) -> Optional[dict]:
    """Référence typée : 'ORG-1' → Organization/ORG-1 ; 'Organization/ORG-1' inchangé."""
    if not value:
        return None
    v = str(value)
    if v.startswith(("urn:", "http")):
        return {"reference": v}
    if "/" in v:                                   # « Type/ID » : l'ID doit rester un id FHIR valide
        t, _, i = v.partition("/")
        return {"reference": f"{t}/{_safe_id(i)}"}
    return {"reference": f"{rtype}/{_safe_id(v)}"}


def _display(name: Optional[str]) -> Optional[dict]:
    return {"display": name} if name else None


def _cc(text: Optional[str]) -> Optional[dict]:
    return {"text": text} if text else None


def _entry(resource: dict) -> dict:
    return {
        "fullUrl": f"{FHIR_BASE_URL}/{resource['resourceType']}/{resource['id']}",
        "resource": _prune(resource),
    }


def _clinic_ref(doc: dict) -> dict:
    orgs = doc.get("_organizations") or []
    if orgs and orgs[0].get("org_id"):
        return {"reference": f"Organization/{_safe_id(orgs[0]['org_id'])}",
                "display": orgs[0].get("name") or DEFAULT_CLINIC_REF["display"]}
    return DEFAULT_CLINIC_REF


def _snomed_body_site(label: Optional[str]) -> Optional[dict]:
    if not label:
        return None
    lk = BODYSITE_LABEL_TO_SNOMED.get(label.lower())
    if not lk:
        return {"text": label}
    return {"coding": [{"system": FHIR_SYSTEM_SNOMED, "code": lk["code"],
                        "display": lk["display"]}], "text": label}


def _oid_value(uid: str) -> str:
    """UID DICOM → valeur FHIR 'urn:oid:<UID>' (idempotent)."""
    u = str(uid).strip()
    if u.startswith("urn:oid:"):
        return u
    if u.startswith("oid:"):
        u = u[4:]
    return "urn:oid:" + u


# ══════════════════════════════════════════════════════════════════════════════
# 2. RESSOURCES « DOCUMENT » : Patient, Consent, groupe sanguin
# ══════════════════════════════════════════════════════════════════════════════

def build_patient(doc: dict) -> dict:
    pid = _require_pid(doc)
    identifiers = [{"system": H2_SYSTEM_PATIENT_ID, "value": pid}]
    if doc.get("national_id"):
        identifiers.append({"use": "official", "system": H2_SYSTEM_NATIONAL_ID,
                            "value": doc["national_id"]})
    res: dict[str, Any] = {"resourceType": "Patient", "id": _safe_id(pid),
                           "identifier": identifiers, "active": True}

    given = doc.get("first_name")
    res["name"] = [{"use": "official", "family": doc.get("last_name"),
                    "given": [given] if given and given != "—" else None}]
    res["gender"] = GENDER_MAP_REVERSE.get(doc.get("sex"))
    res["birthDate"] = _fhir_date(doc.get("birth_date"))

    addr = doc.get("address") or {}
    if addr:
        res["address"] = [{"line": [addr.get("street")] if addr.get("street") else None,
                           "city": addr.get("city"), "country": "MA"}]
    if doc.get("phone"):
        res["telecom"] = [{"system": "phone", "value": doc["phone"]}]
    if doc.get("_gp"):
        res["generalPractitioner"] = [{"display": doc["_gp"]}]
    if doc.get("_org"):
        res["managingOrganization"] = {"display": doc["_org"]}
    if doc.get("_links"):
        res["link"] = [{"other": _ref("Patient", lk.get("ref")),
                        "type": lk.get("type", "seealso")} for lk in doc["_links"]]
    c = doc.get("_contact")
    if c:
        res["contact"] = [{"relationship": [_cc(c.get("relationship"))],
                           "name": {"text": c.get("name")} if c.get("name") else None,
                           "telecom": [{"system": "phone", "value": c["phone"]}]
                           if c.get("phone") else None}]
    return res


def build_blood_group(doc: dict, patient_ref: dict) -> Optional[dict]:
    """Groupe sanguin = Observation laboratoire (fiche Excel « Cas d'usage »)."""
    bt = doc.get("blood_type")
    if not bt:
        return None
    return {
        "resourceType": "Observation",
        "id": _safe_id(f"blood-{_require_pid(doc)}"),
        "status": BLOOD_GROUP_STATUS,
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                  "code": "laboratory", "display": "Laboratory"}]}],
        "code": {"coding": [{"system": FHIR_SYSTEM_LOINC, "code": BLOOD_GROUP_LOINC,
                             "display": LOINC_DISPLAY[BLOOD_GROUP_LOINC]}]},
        "subject": patient_ref,
        "valueString": bt,
    }


def check_consent(doc: dict) -> bool:
    c = doc.get("consent")
    return bool(c) and c.get("status") == "active"


def build_consent(doc: dict, patient_ref: dict) -> Optional[dict]:
    c = doc.get("consent")
    if not c:
        return None
    status = CONSENT_STATUS_MAP_REVERSE.get(c.get("status", "proposed"), "draft")
    date_val = _fhir_date(c.get("date"))
    res: dict[str, Any] = {
        "resourceType": "Consent",
        "id": _safe_id(f"consent-{_require_pid(doc)}"),
        "status": status,
        "category": [{"coding": [{"system": FHIR_SYSTEM_LOINC, "code": "59284-0",
                                  "display": "Consent Document"}]}],
        "subject": patient_ref,
        "date": date_val,
        "controller": [_clinic_ref(doc)],
        "policyBasis": {"url": CNDP_POLICY_URL},
        "decision": "permit" if status == "active" else "deny",
    }
    if c.get("signed_by"):
        res["verification"] = [{
            "verified": True,
            "verificationType": {"text": "signature"},
            "verifiedWith": {"display": c["signed_by"]},
            "verificationDate": [date_val] if date_val else None,
        }]
    if c.get("purpose"):
        res["provision"] = [{"purpose": [{"code": c["purpose"], "display": c["purpose"]}]}]
    return res


# ══════════════════════════════════════════════════════════════════════════════
# 3. CATALOGUE (Organization, Practitioner, Role, Device, Location, Endpoint)
# ══════════════════════════════════════════════════════════════════════════════

def build_organizations(doc: dict) -> list[dict]:
    out = []
    for o in doc.get("_organizations", []):
        out.append({
            "resourceType": "Organization", "id": _safe_id(o.get("org_id") or _new_uuid()),
            "active": o.get("active", True),
            "identifier": [{"value": o["identifier"]}] if o.get("identifier") else None,
            "type": [_cc(o.get("type_label"))], "name": o.get("name"),
            "partOf": _ref("Organization", o.get("_part_of")),
            "endpoint": [_ref("Endpoint", o.get("_endpoint_ref"))],
        })
    return out


def build_practitioners(doc: dict) -> list[dict]:
    out = []
    for p in doc.get("_practitioners", []):
        given = p.get("first_name")
        out.append({
            "resourceType": "Practitioner", "id": _safe_id(p.get("prac_id") or _new_uuid()),
            "active": p.get("active", True),
            "identifier": [{"value": p["identifier"]}] if p.get("identifier") else None,
            "name": [{"use": "official", "family": p.get("last_name"),
                      "given": [given] if given and given != "—" else None}],
            "telecom": [{"system": "phone", "value": p["phone"]}] if p.get("phone") else None,
            "qualification": [{"code": _cc(p.get("qualification"))}] if p.get("qualification") else None,
        })
    return out


def build_practitioner_roles(doc: dict) -> list[dict]:
    out = []
    for r in doc.get("_roles", []):
        out.append({
            "resourceType": "PractitionerRole", "id": _safe_id(r.get("role_id") or _new_uuid()),
            "active": r.get("active", True),
            "practitioner": _ref("Practitioner", r.get("practitioner_ref")),
            "organization": _ref("Organization", r.get("org_ref")),
            "code": [_cc(r.get("code_label"))], "specialty": [_cc(r.get("specialty_label"))],
            "location": [_ref("Location", r.get("_location_ref"))],
        })
    return out


def build_devices(doc: dict) -> list[dict]:
    out = []
    for d in doc.get("_devices", []):
        out.append({
            "resourceType": "Device", "id": _safe_id(d.get("device_id") or _new_uuid()),
            "displayName": d.get("display_name"), "status": d.get("status"),
            "manufacturer": d.get("manufacturer"), "modelNumber": d.get("model_number"),
            "serialNumber": d.get("serial_number"), "type": [_cc(d.get("type_label"))],
            "owner": _ref("Organization", d.get("_owner_ref")),
            "location": _ref("Location", d.get("_location_ref")),
        })
    return out


def build_locations(doc: dict) -> list[dict]:
    out = []
    for l in doc.get("_locations", []):
        out.append({
            "resourceType": "Location", "id": _safe_id(l.get("location_id") or _new_uuid()),
            "status": l.get("status"), "name": l.get("name"),
            "managingOrganization": _ref("Organization", l.get("org_ref")),
            "type": [_cc(l.get("_type_label"))],
            "partOf": _ref("Location", l.get("_part_of")),
        })
    return out


def build_endpoints(doc: dict) -> list[dict]:
    out = []
    for e in doc.get("_endpoints", []):
        ct = e.get("connection_type")
        out.append({
            "resourceType": "Endpoint", "id": _safe_id(e.get("endpoint_id") or _new_uuid()),
            "status": e.get("status", "active"),
            "connectionType": [{"coding": [{"system": FHIR_SYSTEM_ENDPOINT_CT, "code": ct}]}] if ct else None,
            "name": e.get("name"),
            "managingOrganization": _ref("Organization", e.get("org_ref")),
            "address": e.get("address"),
            "payload": [{"mimeType": [e["mime_type"]]}] if e.get("mime_type") else None,
        })
    return out


def _dicom_endpoint_ref(doc: dict) -> Optional[dict]:
    for e in doc.get("_endpoints", []):
        if "dicom" in (e.get("connection_type") or "") and e.get("endpoint_id"):
            return {"reference": f"Endpoint/{_safe_id(e['endpoint_id'])}"}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 4. RESSOURCES « VISITE » : Encounter, Condition, Observation, Imaging, …
# ══════════════════════════════════════════════════════════════════════════════

def _encounter_id(visit: dict) -> str:
    return _safe_id(visit.get("visit_id") or _new_uuid())


def build_encounter(visit: dict, patient_ref: dict, clinic_ref: dict) -> dict:
    code = VISIT_TYPE_MAP.get(visit.get("visit_type", 2), "AMB")
    res: dict[str, Any] = {
        "resourceType": "Encounter", "id": _encounter_id(visit),
        "status": visit.get("_status", "completed"),
        "class": [{"coding": [{"system": FHIR_SYSTEM_ACT_CODE, "code": code,
                               "display": ENCOUNTER_CLASS_DISPLAY[code]}]}],
        "subject": patient_ref, "serviceProvider": clinic_ref,
        "type": [_cc(visit.get("department"))],
        "actualPeriod": {"start": visit.get("admitted_at"), "end": visit.get("discharged_at")},
        "reason": [{"value": [{"concept": {"text": visit["reason"]}}]}] if visit.get("reason") else None,
        "participant": [{"actor": {"display": visit["physician"]}}] if visit.get("physician") else None,
        "priority": {"coding": [{"code": visit["_priority"]}]} if visit.get("_priority") else None,
        "basedOn": [_ref("ServiceRequest", visit.get("_basedOn"))],
    }
    adm = visit.get("_admission")
    if adm:
        def _c(v):
            return {"coding": [{"code": v}], "text": v} if v else None
        res["admission"] = {
            "admitSource": _c(adm.get("admitSource")),
            "dischargeDisposition": _c(adm.get("disposition")),
            "origin": _display(adm.get("origin")),
            "destination": _display(adm.get("destination")),
        }
    if visit.get("_diagnosis"):
        res["diagnosis"] = [{
            "condition": [{"concept": {"text": str(visit["_diagnosis"])}}],
            "use": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/diagnosis-role",
                                 "code": "CC", "display": "Chief complaint"}]}],
        }]
    return res


def build_conditions(visit, patient_ref, enc_ref) -> list[dict]:
    out = []
    vid = _encounter_id(visit)
    for n, c in enumerate(visit.get("conditions", []), 1):
        raw = (c.get("system") or "ICD-10").upper()
        system = FHIR_SYSTEM_ICD10 if "ICD" in raw else FHIR_SYSTEM_SNOMED if "SNOMED" in raw else c["system"]
        out.append({
            "resourceType": "Condition", "id": f"cond-{vid}-{n}"[:64],
            # R5 : clinicalStatus obligatoire — H2 ne le stocke pas, « active » par défaut
            "clinicalStatus": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
            "code": {"coding": [{"system": system, "code": c.get("code"), "display": c.get("label")}],
                     "text": c.get("label")},
            "subject": patient_ref, "encounter": enc_ref,
            "severity": _cc(c.get("severity")), "onsetDateTime": c.get("onset_date"),
        })
    return out


def _pio_enrichment(obs: dict) -> tuple[Optional[str], Optional[dict]]:
    """Retourne (interpretation_label, referenceRange) pour une PIO, selon §20."""
    v = obs.get("value")
    if obs.get("loinc") not in PIO_LOINCS or not isinstance(v, (int, float)):
        return None, None
    rr = obs.get("_referenceRange") or {"low": PIO_RANGE["low"], "high": PIO_RANGE["high"]}
    interp = obs.get("_interpretation")
    if not interp:
        lo, hi = rr.get("low"), rr.get("high")
        interp = ("high" if hi is not None and v > hi else
                  "low" if lo is not None and v < lo else "normal")
    return interp, rr


def build_observations(visit, patient_ref, enc_ref) -> list[dict]:
    out = []
    vid = _encounter_id(visit)
    for n, o in enumerate(visit.get("observations", []), 1):
        loinc = o.get("loinc", "")
        res: dict[str, Any] = {
            "resourceType": "Observation", "id": f"obs-{vid}-{n}"[:64], "status": "final",
            "category": [{"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": LOINC_CATEGORY.get(loinc, "laboratory"),
                "display": LOINC_CATEGORY.get(loinc, "laboratory").replace("-", " ").title()}]}],
            "code": {"coding": [{"system": FHIR_SYSTEM_LOINC, "code": loinc,
                                 "display": LOINC_DISPLAY.get(loinc)}]},
            "subject": patient_ref, "encounter": enc_ref, "effectiveDateTime": o.get("at"),
            "bodySite": _snomed_body_site(o.get("_bodySite") or LOINC_BODYSITE.get(loinc)),
            "performer": [_display(o.get("_performer"))],
            "device": _ref("Device", o.get("_device")),
        }
        interp, rr = _pio_enrichment(o)
        interp = interp or o.get("_interpretation")
        if interp and interp in INTERPRETATION_MAP_REVERSE:
            res["interpretation"] = [{"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                "code": INTERPRETATION_MAP_REVERSE[interp], "display": interp}]}]
        rr = rr or o.get("_referenceRange")
        if rr:
            unit = rr.get("unit") or o.get("unit")
            res["referenceRange"] = [{
                "low": {"value": rr["low"], "unit": unit, "system": UCUM, "code": unit}
                if rr.get("low") is not None else None,
                "high": {"value": rr["high"], "unit": unit, "system": UCUM, "code": unit}
                if rr.get("high") is not None else None,
                "text": rr.get("text")}]

        unit = o.get("unit")
        if loinc == BLOOD_PRESSURE_PANEL_LOINC:
            res["component"] = [{
                "code": {"coding": [{"system": FHIR_SYSTEM_LOINC, "code": c.get("loinc"),
                                     "display": LOINC_DISPLAY.get(c.get("loinc"))}]},
                "valueQuantity": {"value": c["value"], "unit": unit or "mm[Hg]",
                                  "system": UCUM, "code": unit or "mm[Hg]"},
            } for c in o.get("components", []) if c.get("value") is not None]
        elif o.get("value") is not None:
            res["valueQuantity"] = {"value": o["value"], "unit": unit, "system": UCUM, "code": unit}
        elif o.get("value_text"):
            res["valueString"] = o["value_text"]
        out.append(res)
    return out


def build_imaging_studies(visit, patient_ref, enc_ref, doc) -> list[dict]:
    out = []
    vid = _encounter_id(visit)
    endpoint = _dicom_endpoint_ref(doc)
    for n, i in enumerate(visit.get("imaging", []), 1):
        rid = _safe_id(i.get("imaging_id") or (f"img-{vid}" if n == 1 else f"img-{vid}-{n}"))
        modality = i.get("modality", "OP")
        mod_cc = {"coding": [{"system": FHIR_SYSTEM_DICOM_MOD, "code": modality,
                              "display": DICOM_MODALITY_DISPLAY.get(modality, modality)}]}
        idents = []
        if i.get("study_uid"):
            idents.append({"system": FHIR_SYSTEM_DICOM_UID, "value": _oid_value(i["study_uid"])})
        if i.get("accession"):
            idents.append({"type": {"coding": [{"system": FHIR_SYSTEM_ACSN, "code": "ACSN",
                                                "display": "Accession ID"}]},
                           "value": i["accession"]})
        res: dict[str, Any] = {
            "resourceType": "ImagingStudy", "id": rid, "status": "available",
            "identifier": idents, "modality": [mod_cc], "subject": patient_ref, "encounter": enc_ref,
            "started": i.get("started_at"), "referrer": _display(i.get("referrer")),
            "endpoint": [_ref("Endpoint", i.get("endpoint_ref")) or endpoint],
            "numberOfInstances": i.get("instances") or None, "description": i.get("description"),
        }
        # La série n'est émise que si son UID réel est connu (ne pas l'inventer :
        # il doit correspondre à celui du PACS Orthanc).
        if i.get("series_uid"):
            res["series"] = [{
                "uid": i["series_uid"], "modality": mod_cc,
                "numberOfInstances": i.get("instances") or None,
                "laterality": _cc(i.get("_laterality")),
            }]
        out.append(res)
    return out


def build_diagnostic_reports(visit, patient_ref, enc_ref) -> list[dict]:
    return [{
        "resourceType": "DiagnosticReport", "id": _safe_id(r.get("report_id") or _new_uuid()),
        "status": r.get("status", "final"), "code": _cc(r.get("code_label")),
        "subject": patient_ref, "encounter": enc_ref,
        "effectiveDateTime": r.get("effective_at"), "issued": r.get("issued_at"),
        "performer": [_display(r.get("performer"))],
        "study": [_ref("ImagingStudy", r.get("imaging_ref"))],
        "conclusion": r.get("conclusion"),
        "result": [_ref("Observation", r.get("_result_ref"))],
    } for r in visit.get("reports", [])]


def build_service_requests(visit, patient_ref, enc_ref) -> list[dict]:
    return [{
        "resourceType": "ServiceRequest", "id": _safe_id(s.get("sr_id") or _new_uuid()),
        "status": s.get("status", "active"), "intent": s.get("intent", "order"),
        "identifier": [{"value": s["identifier"]}] if s.get("identifier") else None,
        # R5 : ServiceRequest.code est un CodeableReference
        "code": {"concept": {"text": s["code_label"]}} if s.get("code_label") else None,
        "subject": patient_ref, "encounter": enc_ref, "authoredOn": s.get("authored_on"),
        "requester": _display(s.get("requester")), "performer": [_display(s.get("performer"))],
        "priority": s.get("_priority"),
        "reason": [{"concept": {"text": s["_reason"]}}] if s.get("_reason") else None,
    } for s in visit.get("service_requests", [])]


def build_procedures(visit, patient_ref, enc_ref) -> list[dict]:
    out = []
    for p in visit.get("procedures", []):
        out.append({
            "resourceType": "Procedure", "id": _safe_id(p.get("proc_id") or _new_uuid()),
            "status": p.get("status", "completed"),
            "identifier": [{"value": p["identifier"]}] if p.get("identifier") else None,
            "code": _cc(p.get("code_label")), "subject": patient_ref, "encounter": enc_ref,
            "occurrenceDateTime": p.get("occurred_at"),
            "performer": [{"actor": _display(p.get("performer"))}] if p.get("performer") else None,
            "bodySite": [_snomed_body_site(p.get("body_site"))],
            "outcome": _cc(p.get("_outcome")),
            "report": [_ref("DiagnosticReport", p.get("_report_ref"))],
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 5. AuditEvent, AllergyIntolerance
# ══════════════════════════════════════════════════════════════════════════════

def build_audit_events(doc: dict, patient_ref: dict) -> list[dict]:
    out = []
    for a in doc.get("_audit_log", []):
        raw = (a.get("action") or "").lower()
        res: dict[str, Any] = {
            "resourceType": "AuditEvent", "id": _safe_id(a.get("audit_id") or _new_uuid()),
            "code": _cc(a.get("event_type")),
            "action": AUDIT_ACTION_MAP_REVERSE.get(raw, raw[:1].upper() or None),
            "recorded": a.get("recorded_at") or _now_iso(),
            # R5 : AuditEvent.outcome.code est un Coding
            "outcome": {"code": {"code": a["outcome_code"], "display": a["outcome_code"]}}
            if a.get("outcome_code") else None,
            "patient": _ref("Patient", a.get("patient_ref")) or patient_ref,
            "agent": [{"who": _display(a.get("agent_who"))}] if a.get("agent_who") else None,
            "source": {"observer": _display(a.get("source_observer"))} if a.get("source_observer") else None,
            "entity": [{"what": _ref("Patient", a["_entity_ref"])}] if a.get("_entity_ref") else None,
            "severity": a.get("_severity"),
            "encounter": _ref("Encounter", a.get("_encounter_ref")),
        }
        out.append(res)
    return out


def build_allergy_intolerances(doc: dict, patient_ref: dict) -> list[dict]:
    out = []
    for a in doc.get("allergies", []):
        sub_coding = ([{"system": FHIR_SYSTEM_SNOMED, "code": a["snomed_substance"],
                        "display": a.get("substance")}] if a.get("snomed_substance") else None)
        react = None
        if a.get("reaction"):
            r_coding = ([{"system": FHIR_SYSTEM_SNOMED, "code": a["snomed_reaction"],
                          "display": a["reaction"]}] if a.get("snomed_reaction") else None)
            sev = a.get("severity")
            react = [{"manifestation": [{"concept": {"coding": r_coding, "text": a["reaction"]}}],
                      "severity": sev if sev in _SEVERITY_FHIR_VALUES else None}]
        out.append({
            "resourceType": "AllergyIntolerance",
            "id": _safe_id(a.get("allergy_id") or _new_uuid()),
            "clinicalStatus": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                "code": a.get("status", "active")}]},
            "verificationStatus": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                "code": "confirmed"}]},
            "category": [a["category"]] if a.get("category") else None,
            "criticality": _CRITICALITY_MAP.get(a["criticite"]) if a.get("criticite") else None,
            "code": {"coding": sub_coding, "text": a.get("substance")} if a.get("substance") else None,
            "patient": patient_ref, "recordedDate": a.get("date"), "reaction": react,
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 6. ASSEMBLAGE DU BUNDLE
# ══════════════════════════════════════════════════════════════════════════════

def h2_document_to_bundle(doc: dict, visit_id_filter: Optional[str] = None,
                          enforce_consent: bool = True) -> dict:
    doc = normalize_dates(doc)
    _require_pid(doc)                              # avant tout : pas d'identifiant « UNKNOWN »
    if enforce_consent and not check_consent(doc):
        st = (doc.get("consent") or {}).get("status", "absent")
        raise ConsentError(
            f"Export refusé pour {doc.get('patient_id')} : consentement '{st}' (loi 09-08).")

    resources: list[dict] = []
    patient = build_patient(doc)
    p_ref = {"reference": f"Patient/{patient['id']}"}
    clinic = _clinic_ref(doc)
    resources.append(patient)
    for r in (build_consent(doc, p_ref), build_blood_group(doc, p_ref)):
        if r:
            resources.append(r)
    resources += build_allergy_intolerances(doc, p_ref)
    for fn in (build_organizations, build_practitioners, build_practitioner_roles,
               build_devices, build_locations, build_endpoints):
        resources += fn(doc)

    visits = doc.get("visits", [])
    if visit_id_filter:
        visits = [v for v in visits if v.get("visit_id") == visit_id_filter]
    for v in visits:
        enc = build_encounter(v, p_ref, clinic)
        e_ref = {"reference": f"Encounter/{enc['id']}"}
        resources.append(enc)
        resources += build_conditions(v, p_ref, e_ref)
        resources += build_observations(v, p_ref, e_ref)
        resources += build_imaging_studies(v, p_ref, e_ref, doc)
        resources += build_diagnostic_reports(v, p_ref, e_ref)
        resources += build_service_requests(v, p_ref, e_ref)
        resources += build_procedures(v, p_ref, e_ref)
    resources += build_audit_events(doc, p_ref)

    return {
        "resourceType": "Bundle", "id": _new_uuid(), "type": "collection",
        "timestamp": _now_iso(),
        "meta": {"source": f"H2-patient-{doc['patient_id']}",
                 "tag": [{"system": "urn:clinique-al-bacar:export", "code": "H2-TO-FHIR",
                          "display": "Export H2 → FHIR R5"}]},
        "entry": [_entry(r) for r in resources],
    }


def convert(doc_h2: dict, visit_id: Optional[str] = None, enforce_consent: bool = True) -> dict:
    """Point d'entrée public (lève ConsentError si consentement non actif)."""
    return h2_document_to_bundle(doc_h2, visit_id_filter=visit_id, enforce_consent=enforce_consent)


# ══════════════════════════════════════════════════════════════════════════════
# 7. CLI
# ══════════════════════════════════════════════════════════════════════════════

def _cli() -> int:
    p = argparse.ArgumentParser(description="Adaptateur H2 → FHIR R5.")
    p.add_argument("--patient", required=True, metavar="FICHIER", help="Document H2 (JSON)")
    p.add_argument("--out", metavar="FICHIER", help="Sortie (défaut : stdout)")
    p.add_argument("--visit-id", metavar="ID", help="N'exporter qu'une visite")
    p.add_argument("--pretty", action="store_true")
    p.add_argument("--no-consent-check", action="store_true",
                   help="Désactive le blocage si consentement non actif (tests uniquement)")
    args = p.parse_args()
    logging.basicConfig(level="WARNING", format="%(levelname)s %(name)s %(message)s")
    try:
        with open(args.patient, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERREUR] {args.patient} : {exc}", file=sys.stderr)
        return 1
    try:
        bundle = convert(doc, args.visit_id, enforce_consent=not args.no_consent_check)
    except ConsentError as exc:
        print(f"[REFUSÉ] {exc}", file=sys.stderr)
        return 3
    out = json.dumps(bundle, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"[OK] {len(bundle['entry'])} entrée(s) → {args.out}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
