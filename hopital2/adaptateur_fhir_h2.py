#!/usr/bin/env python3
"""
adaptateur_fhir_h2.py  —  v3.4  (FHIR R5 — 17 ressources)
=======================================================================
Adaptateur FHIR R5 (Bundle) → document MongoDB Hôpital 2 (Clinique Al Baçar)

Changements v3.4 (par rapport à v3.3)
-------------------------------------
  • Un identifiant H2 « UNKNOWN » (bundle émis par un ancien adaptateur) est traité
    comme absent : patient_id = None, jamais « UNKNOWN » en base.

Changements v3.3 (par rapport à v3.2)
-------------------------------------
  • Plus de plantage sur Encounter.diagnosis (R5 : condition/use sont des listes).
  • Références résolues via fullUrl (urn:uuid:…, URL absolues) ET « Type/id ».
  • UID DICOM : « urn:oid:<UID> » → <UID> (retrait réel du préfixe).
    Le CIN reste sous le system « urn:ma:cin » (inchangé).
  • imaging[].imaging_id conservé (les DiagnosticReport.study restent valides).
  • Conversion d'unité implémentée (glycémie g/L → mg/dL, ×100).
  • Contrôles : unité manquante (D10), valeur impossible (D11), sortie antérieure
    à l'admission (D12), champs obligatoires Patient (D8) → rejet motivé.
  • Alerte PIO : _interpretation / _referenceRange / _bodySite calculés (S2).
  • Observations non numériques (valueString / valueCodeableConcept) → value_text.
  • Groupe sanguin : Observation LOINC 882-1 sans encounter → blood_type.
  • Condition.severity / onset_date repris ; admission.* relue par code.
  • Consent : statuts R5 et R4 acceptés ; purpose = Coding.
  • AllergyIntolerance : seules les allergies verificationStatus=confirmed sont gardées.
  • Références Patient.link sans préfixe « Patient/ » (plus de double préfixe).
  • patient_id = None si le bundle ne porte pas d'identifiant H2 (patient venant de H1) :
    l'API attribue le P2-xxxx ; les autres identifiants sont gardés dans _external_ids.
  • Mode strict (défaut) : lève MappingError si une erreur est détectée ;
    strict=False les consigne dans doc["_mapping_errors"].

Usage CLI
---------
  python adaptateur_fhir_h2.py --bundle bundle_fhir.json --out doc_h2.json
  python adaptateur_fhir_h2.py --bundle bundle_fhir.json --lenient
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Optional

logger = logging.getLogger("fhir_h2")

# ══════════════════════════════════════════════════════════════════════════════
# 0. TABLES DE CORRESPONDANCE
# ══════════════════════════════════════════════════════════════════════════════

GENDER_MAP = {"male": 1, "female": 2, "other": None, "unknown": None}
ENCOUNTER_CLASS_MAP = {"EMER": 1, "AMB": 2, "IMP": 3}

# R5 : draft | active | inactive | not-done | entered-in-error | unknown
# R4 (accepté en entrée pour compatibilité avec l'équipe H1) : proposed | rejected
CONSENT_STATUS_MAP = {
    "active": "active", "not-done": "refused", "rejected": "refused",
    "draft": "proposed", "proposed": "proposed", "inactive": "inactive",
}

BODYSITE_SNOMED_TO_LABEL = {"18944008": "right eye", "8966001": "left eye"}
LOINC_BODYSITE = {"79892-6": "right eye", "79893-4": "left eye"}
INTERPRETATION_MAP = {"H": "high", "HH": "critical-high", "L": "low", "LL": "critical-low",
                      "N": "normal", "A": "abnormal"}

BLOOD_PRESSURE_PANEL_LOINC = "85354-9"
BLOOD_GROUP_LOINC = "882-1"
PIO_LOINCS = ("79892-6", "79893-4")
PIO_REFERENCE_RANGE = {"low": 10, "high": 21, "unit": "mm[Hg]"}

# (LOINC, unité en minuscules) → (facteur, unité cible)
UNIT_CONVERSIONS: dict[tuple[str, str], tuple[float, str]] = {
    ("2339-0", "g/l"):    (1.0,  "g/L"),
    ("2339-0", "mg/dl"):  (0.01, "g/L"),
    ("2339-0", "mmol/l"): (0.18, "g/L"),
}

# Bornes plausibles (après conversion) — au-delà : valeur rejetée (cas D11)
PLAUSIBLE_RANGE = {
    "79892-6": (0, 80), "79893-4": (0, 80),
    "8480-6": (40, 300), "8462-4": (20, 200), "8867-4": (20, 250),
    "59408-5": (50, 100), "2708-6": (50, 100), "8310-5": (30, 45),
    "2339-0": (0.1, 10), "4548-4": (2, 25),
}

H2_SYSTEM_PATIENT_ID = "urn:clinique-al-bacar:patient"
H2_SYSTEM_NATIONAL_ID = "urn:ma:cin"

AUDIT_ACTION_MAP = {"C": "create", "R": "read", "U": "update", "D": "delete", "E": "execute"}
CRITICALITY_MAP_FHIR_TO_H2 = {"high": "ELEVEE", "low": "FAIBLE", "unable-to-assess": "MOYENNE"}
SEVERITY_FHIR_VALUES = {"mild", "moderate", "severe"}


class MappingError(ValueError):
    """Bundle non conforme au contrat H2 (champ obligatoire absent, valeur invalide…)."""


# ══════════════════════════════════════════════════════════════════════════════
# 1. UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _first(lst, default=None):
    return lst[0] if lst else default


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _pick_identifier(identifiers: list[dict], system: str) -> Optional[str]:
    for i in identifiers or []:
        if i.get("system") == system:
            return i.get("value")
    return None


def _pick_identifier_by_type(identifiers: list[dict], code: str) -> Optional[str]:
    for i in identifiers or []:
        for c in i.get("type", {}).get("coding", []):
            if c.get("code") == code:
                return i.get("value")
    return None


def _iso_date_only(s: Optional[str]) -> Optional[str]:
    return s[:10] if s else None


def _strip_oid(uid: Optional[str]) -> str:
    """'urn:oid:2.25.123' → '2.25.123' (retire le préfixe, pas un jeu de caractères)."""
    if not uid:
        return ""
    for prefix in ("urn:oid:", "oid:"):
        if uid.startswith(prefix):
            return uid[len(prefix):]
    return uid


def _coding_display(cc: Any) -> Optional[str]:
    """Texte lisible d'un CodeableConcept (ou Coding)."""
    if not cc or not isinstance(cc, dict):
        return None
    if cc.get("text"):
        return cc["text"]
    if cc.get("display"):                       # Coding direct
        return cc["display"]
    for c in cc.get("coding", []):
        if c.get("display"):
            return c["display"]
    return None


def _coding_code(cc: Any) -> Optional[str]:
    """Code d'un CodeableConcept (ou Coding) ; à défaut texte/display."""
    if not cc or not isinstance(cc, dict):
        return None
    if cc.get("code"):
        return cc["code"]
    for c in cc.get("coding", []):
        if c.get("code"):
            return c["code"]
    return _coding_display(cc)


def _concept_of(x: Any) -> dict:
    """CodeableReference R5 → son concept ; CodeableConcept R4 → lui-même."""
    if isinstance(x, dict):
        return x.get("concept") or x
    return {}


def _ref_display(ref: Any) -> Optional[str]:
    """Pour les champs « nom » (performer, requester…) : display d'abord."""
    if not ref or not isinstance(ref, dict):
        return None
    return ref.get("display") or ref.get("reference")


def _ref_value(ref: Any) -> Optional[str]:
    """Pour les champs « lien » (org_ref, practitioner_ref…) : reference d'abord."""
    if not ref or not isinstance(ref, dict):
        return None
    return ref.get("reference") or ref.get("display")


def _unprefix(ref: Optional[str], rtype: str) -> Optional[str]:
    if ref and ref.startswith(rtype + "/"):
        return ref[len(rtype) + 1:]
    return ref


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _err(errors: Optional[list], msg: str) -> None:
    logger.warning(msg)
    if errors is not None:
        errors.append(msg)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Patient
# ══════════════════════════════════════════════════════════════════════════════

def map_patient(p: dict) -> dict:
    ids = p.get("identifier", [])
    h2_id = _pick_identifier(ids, H2_SYSTEM_PATIENT_ID)
    if h2_id and str(h2_id).upper() == "UNKNOWN":
        h2_id = None                               # faux identifiant d'un ancien export : on le considère absent

    name = _first(p.get("name", []), {})
    family, given = name.get("family"), _first(name.get("given", []))
    gender = p.get("gender")
    missing = [lbl for lbl, v in (("name.family", family), ("name.given", given),
                                  ("birthDate", p.get("birthDate")), ("gender", gender)) if not v]
    if missing:
        raise MappingError(
            f"Patient {p.get('id')} : champ(s) obligatoire(s) absent(s) : {', '.join(missing)}")

    doc: dict[str, Any] = {
        "patient_id": h2_id,                       # None si patient venant de H1 → l'API attribue P2-xxxx
        "last_name": family, "first_name": given,
        "sex": GENDER_MAP.get(gender),
        "birth_date": p.get("birthDate"),
    }
    if doc["sex"] is None:
        logger.warning("Sexe non mappable '%s' → null", gender)

    doc["national_id"] = (_pick_identifier(ids, H2_SYSTEM_NATIONAL_ID)
                          or _pick_identifier_by_type(ids, "NI"))
    doc["phone"] = next((t.get("value") for t in p.get("telecom", [])
                         if t.get("system") == "phone"), None)
    addr = _first(p.get("address", []), {})
    doc["address"] = {"street": _first(addr.get("line", []), ""), "city": addr.get("city", "")}

    # groupe sanguin : normalement une Observation (voir bundle_to_h2_document) ;
    # extension locale acceptée en secours
    doc["blood_type"] = None
    for ext in p.get("extension", []):
        if "blood-type" in ext.get("url", "") or "bloodGroup" in ext.get("url", ""):
            doc["blood_type"] = ext.get("valueString") or ext.get("valueCode")

    # identifiants autres que H2 / CIN (ex. IPP de l'hôpital 1) : utiles au rapprochement
    doc["_external_ids"] = [{"system": i.get("system"), "value": i.get("value")}
                            for i in ids
                            if i.get("system") not in (H2_SYSTEM_PATIENT_ID, H2_SYSTEM_NATIONAL_ID)
                            and i.get("value")] or None

    gp = p.get("generalPractitioner", [])
    doc["_gp"] = _ref_display(gp[0]) if gp else None
    mo = p.get("managingOrganization", {})
    doc["_org"] = mo.get("display") or mo.get("reference") or None
    doc["_links"] = [{"ref": _unprefix(lk.get("other", {}).get("reference"), "Patient"),
                      "type": lk.get("type")} for lk in p.get("link", [])] or None

    contacts = p.get("contact", [])
    if contacts:
        c0 = contacts[0]
        cname = c0.get("name", {})
        rel = _first([_coding_display(r) for r in c0.get("relationship", [])])
        doc["_contact"] = {
            "relationship": rel,
            "name": cname.get("text") or " ".join(
                x for x in (_first(cname.get("given", [])), cname.get("family")) if x) or None,
            "phone": next((t.get("value") for t in c0.get("telecom", [])
                           if t.get("system") == "phone"), None),
        }
    else:
        doc["_contact"] = None

    doc["visits"] = []
    doc["consent"] = None
    return doc


# ══════════════════════════════════════════════════════════════════════════════
# 3. Encounter
# ══════════════════════════════════════════════════════════════════════════════

def _extract_class_code_r5(class_list: list[dict]) -> str:
    for item in class_list:
        for c in item.get("coding", []):
            if c.get("code"):
                return c["code"].upper()
        if item.get("code"):
            return item["code"].upper()
    return ""


def map_encounter(e: dict) -> dict:
    vid = e.get("id", "")
    raw = e.get("class", [])
    class_code = (_extract_class_code_r5(raw) if isinstance(raw, list)
                  else raw.get("code", "").upper() if isinstance(raw, dict) else "")
    vtype = ENCOUNTER_CLASS_MAP.get(class_code)
    period = e.get("actualPeriod") or e.get("period") or {}
    start, end = period.get("start"), period.get("end")

    if vtype is None:
        raise MappingError(f"Encounter {vid} : classe '{class_code}' inconnue ou absente")
    if not start:
        raise MappingError(f"Encounter {vid} : actualPeriod.start absent")
    if end and end < start:                        # invariant FHIR per-1 (cas D12)
        raise MappingError(f"Encounter {vid} : fin ({end}) antérieure au début ({start})")

    visit: dict[str, Any] = {"visit_id": vid, "visit_type": vtype}

    department = None
    for t in _as_list(e.get("type")):
        department = _coding_display(t)
        if department:
            break
    if not department:
        for st in _as_list(e.get("serviceType")):          # R5 : CodeableReference
            department = _coding_display(_concept_of(st))
            if department:
                break
    visit["department"] = department or ""
    visit["admitted_at"], visit["discharged_at"] = start, end

    physician = None
    for part in e.get("participant", []):
        actor = part.get("actor") or part.get("individual") or {}
        disp = actor.get("display")
        if not disp:
            continue
        codes = [c.get("code") for t in part.get("type", []) for c in t.get("coding", [])]
        if "PPRF" in codes:
            physician = disp
            break
        physician = physician or disp
    visit["physician"] = physician

    reason = None
    for r in e.get("reason", []):
        for val in _as_list(r.get("value")):
            reason = _coding_display(_concept_of(val))
            if reason:
                break
        reason = reason or r.get("text")
        if reason:
            break
    if not reason:
        for rc in e.get("reasonCode", []):                 # R4 en secours
            reason = _coding_display(rc)
            if reason:
                break
    visit["reason"] = reason

    visit["_status"] = e.get("status")

    diag = None
    d0 = _first(e.get("diagnosis", []))
    if d0:
        cond = _first(_as_list(d0.get("condition")), {})   # R5 : liste de CodeableReference
        diag = _coding_display(_concept_of(cond)) or cond.get("display")
        if not diag:
            diag = _coding_display(_first(_as_list(d0.get("use")), {}))
    visit["_diagnosis"] = diag

    adm = e.get("admission") or {}
    visit["_admission"] = ({
        "origin": _ref_display(adm.get("origin")),
        "admitSource": _coding_code(adm.get("admitSource")),
        "destination": _ref_display(adm.get("destination")),
        "disposition": _coding_code(adm.get("dischargeDisposition")),
    } if adm else None)

    sp = e.get("serviceProvider", {})
    visit["_serviceProvider"] = sp.get("display") or sp.get("reference") or None
    visit["_priority"] = _coding_code(e.get("priority"))
    visit["_basedOn"] = _first([b.get("reference") for b in e.get("basedOn", [])])

    for k in ("conditions", "observations", "imaging", "procedures", "reports", "service_requests"):
        visit[k] = []
    return visit


# ══════════════════════════════════════════════════════════════════════════════
# 4. Condition
# ══════════════════════════════════════════════════════════════════════════════

def map_condition(c: dict) -> dict:
    cc = c.get("code", {})
    codings = cc.get("coding", [])
    icd = next((x for x in codings if "icd-10" in x.get("system", "").lower()),
               _first(codings, {}))
    code, label = icd.get("code"), icd.get("display") or cc.get("text")
    if not code or not label:
        raise MappingError(f"Condition {c.get('id')} : code ou libellé absent")
    sys_l = icd.get("system", "").lower()
    out = {"system": "ICD-10" if "icd-10" in sys_l else "SNOMED" if "snomed" in sys_l
           else icd.get("system") or "ICD-10",
           "code": code, "label": label}
    sev = _coding_display(c.get("severity"))
    if sev:
        out["severity"] = sev
    if c.get("onsetDateTime"):
        out["onset_date"] = c["onsetDateTime"]
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 5. Observation
# ══════════════════════════════════════════════════════════════════════════════

def _loinc_of(cc: dict) -> Optional[str]:
    codings = cc.get("coding", [])
    return next((c.get("code") for c in codings if "loinc.org" in c.get("system", "")),
                _first([c.get("code") for c in codings]))


def _convert(loinc: str, value: float, unit: str) -> tuple[float, str]:
    key = (loinc, unit.lower())
    if key in UNIT_CONVERSIONS:
        factor, tgt = UNIT_CONVERSIONS[key]
        return round(value * factor, 3), tgt
    return value, unit


def _plausible(loinc: str, value: float) -> bool:
    lo, hi = PLAUSIBLE_RANGE.get(loinc, (None, None))
    return lo is None or lo <= value <= hi


def map_observation(o: dict, errors: Optional[list] = None) -> Optional[dict]:
    loinc = _loinc_of(o.get("code", {}))
    oid = o.get("id")
    if not loinc:
        _err(errors, f"Observation {oid} : code LOINC absent — ignorée")
        return None
    at = (o.get("effectiveDateTime") or o.get("effectivePeriod", {}).get("start")
          or o.get("effectiveInstant"))
    if not at:
        _err(errors, f"Observation {oid} ({loinc}) : date effective absente — ignorée")
        return None

    # ── Forme B : panel tension ──
    if loinc == BLOOD_PRESSURE_PANEL_LOINC:
        comps, unit = [], "mm[Hg]"
        for comp in o.get("component", []):
            cl = _loinc_of(comp.get("code", {}))
            vq = comp.get("valueQuantity", {})
            v = vq.get("value")
            if cl and _num(v):
                if not _plausible(cl, v):
                    _err(errors, f"Observation {oid} : {cl}={v} hors plage plausible — ignorée")
                    return None
                comps.append({"loinc": cl, "value": v})
                unit = vq.get("code") or vq.get("unit") or unit
        if not comps:
            _err(errors, f"Observation {oid} : panel TA sans composante — ignorée")
            return None
        return {"loinc": loinc, "components": comps, "unit": unit, "at": at}

    # ── Forme A : scalaire ──
    obs: dict[str, Any]
    vq = o.get("valueQuantity")
    if vq and vq.get("value") is not None:
        value = vq["value"]
        raw_unit = vq.get("code") or vq.get("unit") or ""
        if not _num(value):
            _err(errors, f"Observation {oid} ({loinc}) : valeur non numérique — ignorée")
            return None
        if not raw_unit:
            _err(errors, f"Observation {oid} ({loinc}) : unité absente — ignorée")
            return None
        value, unit = _convert(loinc, value, raw_unit)
        if not _plausible(loinc, value):
            _err(errors, f"Observation {oid} ({loinc}) : {value} {unit} hors plage plausible — ignorée")
            return None
        obs = {"loinc": loinc, "value": value, "unit": unit, "at": at}
    else:
        text = o.get("valueString") or _coding_display(o.get("valueCodeableConcept"))
        if not text:
            _err(errors, f"Observation {oid} ({loinc}) : sans valeur — ignorée")
            return None
        obs = {"loinc": loinc, "value_text": text, "at": at}

    # bodySite (SNOMED → libellé ; à défaut déduit du LOINC de la PIO)
    bs = o.get("bodySite") or {}
    body_site = None
    for c in bs.get("coding", []):
        body_site = BODYSITE_SNOMED_TO_LABEL.get(c.get("code", "")) or c.get("display")
        if body_site:
            break
    body_site = body_site or bs.get("text") or LOINC_BODYSITE.get(loinc)

    interp = None
    for c in _first(o.get("interpretation", []), {}).get("coding", []):
        interp = INTERPRETATION_MAP.get(c.get("code", "")) or c.get("display")
        if interp:
            break

    ref_range = None
    if o.get("referenceRange"):
        rr = o["referenceRange"][0]
        ref_range = {"low": rr.get("low", {}).get("value"), "high": rr.get("high", {}).get("value"),
                     "text": rr.get("text")}

    # Alerte PIO (tables_fhir_h2 §20) : calculée si absente
    if loinc in PIO_LOINCS and "value" in obs:
        ref_range = ref_range or {"low": PIO_REFERENCE_RANGE["low"],
                                  "high": PIO_REFERENCE_RANGE["high"], "text": None}
        if not interp:
            lo, hi = ref_range.get("low"), ref_range.get("high")
            interp = ("high" if hi is not None and obs["value"] > hi else
                      "low" if lo is not None and obs["value"] < lo else "normal")

    performer = _ref_display(_first(o.get("performer", []), {}))
    device = _ref_value(o.get("device"))
    for k, v in (("_bodySite", body_site), ("_interpretation", interp),
                 ("_referenceRange", ref_range), ("_performer", performer), ("_device", device)):
        if v:
            obs[k] = v
    return obs


# ══════════════════════════════════════════════════════════════════════════════
# 6. ImagingStudy / Endpoint / DiagnosticReport
# ══════════════════════════════════════════════════════════════════════════════

def map_imaging_study(i: dict) -> dict:
    idents = i.get("identifier", [])
    modality = "OP"
    for m in i.get("modality", []):
        code = _first([c.get("code") for c in m.get("coding", []) if c.get("code")])
        if code:
            modality = code
            break
    s0 = _first(i.get("series", []), {})
    n_inst = (i.get("numberOfInstances") or s0.get("numberOfInstances")
              or len(s0.get("instance", [])))
    img: dict[str, Any] = {
        "imaging_id": i.get("id"),
        "study_uid": _strip_oid(_pick_identifier(idents, "urn:dicom:uid")),
        "modality": modality,
        "accession": _pick_identifier_by_type(idents, "ACSN") or "",
        "description": i.get("description", ""),
        "instances": n_inst or 0,
        "started_at": i.get("started"),
        "referrer": _ref_display(i.get("referrer")),
        "endpoint_ref": _first([e.get("reference") for e in i.get("endpoint", [])]),
    }
    if s0.get("uid"):
        img["series_uid"] = _strip_oid(s0["uid"])
    lat = _coding_display(s0.get("laterality"))
    if lat:
        img["_laterality"] = lat
    return img


def map_endpoint(e: dict) -> dict:
    conn = ""
    for ct in e.get("connectionType", []) if isinstance(e.get("connectionType"), list) \
            else [e.get("connectionType") or {}]:
        conn = _coding_code(ct) or ""
        if conn:
            break
    mime = _first(_first(e.get("payload", []), {}).get("mimeType", []))
    return {"endpoint_id": e.get("id", ""), "status": e.get("status", ""),
            "connection_type": conn, "name": e.get("name", ""), "address": e.get("address", ""),
            "org_ref": _ref_value(e.get("managingOrganization")), "mime_type": mime}


def map_diagnostic_report(d: dict) -> dict:
    rep = {
        "report_id": d.get("id", ""), "status": d.get("status", ""),
        "code_label": _coding_display(d.get("code")),
        "effective_at": d.get("effectiveDateTime") or d.get("effectivePeriod", {}).get("start"),
        "issued_at": d.get("issued"),
        "performer": _ref_display(_first(d.get("performer", []), {})),
        "imaging_ref": _first([s.get("reference") for s in d.get("study", [])]),
        "conclusion": d.get("conclusion"),
    }
    res = _first([r.get("reference") for r in d.get("result", [])])
    if res:
        rep["_result_ref"] = res
    return rep


# ══════════════════════════════════════════════════════════════════════════════
# 7. Catalogue : Organization, Practitioner, PractitionerRole, Device, Location
# ══════════════════════════════════════════════════════════════════════════════

def map_organization(o: dict) -> dict:
    org = {
        "org_id": o.get("id", ""),
        "identifier": _first([i.get("value") for i in o.get("identifier", []) if i.get("value")]),
        "active": o.get("active", True),
        "type_label": _coding_display(_first(o.get("type", []), {})),
        "name": o.get("name", ""),
    }
    if o.get("partOf"):
        org["_part_of"] = _ref_value(o["partOf"])
    ep = _first([e.get("reference") for e in o.get("endpoint", [])])
    if ep:
        org["_endpoint_ref"] = ep
    return org


def map_practitioner(p: dict) -> dict:
    name = _first(p.get("name", []), {})
    prac = {
        "prac_id": p.get("id", ""),
        "identifier": _first([i.get("value") for i in p.get("identifier", []) if i.get("value")]),
        "active": p.get("active", True),
        "last_name": name.get("family", ""),
        "first_name": _first(name.get("given", []), ""),
        "phone": next((t.get("value") for t in p.get("telecom", []) if t.get("system") == "phone"), None),
    }
    q = _first(p.get("qualification", []))
    if q:
        prac["qualification"] = _coding_display(q.get("code", {}))
    return prac


def map_practitioner_role(r: dict) -> dict:
    role = {
        "role_id": r.get("id", ""), "active": r.get("active", True),
        "practitioner_ref": _ref_value(r.get("practitioner")),
        "org_ref": _ref_value(r.get("organization")),
        "code_label": _coding_display(_first(r.get("code", []), {})),
        "specialty_label": _coding_display(_first(r.get("specialty", []), {})),
    }
    loc = _first([l.get("reference") for l in r.get("location", [])])
    if loc:
        role["_location_ref"] = loc
    return role


def map_device(d: dict) -> dict:
    dev = {
        "device_id": d.get("id", ""), "display_name": d.get("displayName", ""),
        "status": d.get("status", ""), "manufacturer": d.get("manufacturer", ""),
        "model_number": d.get("modelNumber", ""), "serial_number": d.get("serialNumber", ""),
        "type_label": _coding_display(_first(_as_list(d.get("type")), {})),
    }
    if d.get("owner"):
        dev["_owner_ref"] = _ref_value(d["owner"])
    if d.get("location"):
        dev["_location_ref"] = _ref_value(d["location"])
    return dev


def map_location(l: dict) -> dict:
    loc = {"location_id": l.get("id", ""), "status": l.get("status", ""), "name": l.get("name", ""),
           "org_ref": _ref_value(l.get("managingOrganization"))}
    t = _coding_display(_first(l.get("type", []), {}))
    if t:
        loc["_type_label"] = t
    if l.get("partOf"):
        loc["_part_of"] = _ref_value(l["partOf"])
    return loc


# ══════════════════════════════════════════════════════════════════════════════
# 8. ServiceRequest / Procedure / AuditEvent / Consent / AllergyIntolerance
# ══════════════════════════════════════════════════════════════════════════════

def map_service_request(s: dict) -> dict:
    reason = None
    for r in s.get("reason", []):
        reason = _coding_display(_concept_of(r)) or _ref_display(r.get("reference"))
        if reason:
            break
    sr = {
        "sr_id": s.get("id", ""),
        "identifier": _first([i.get("value") for i in s.get("identifier", []) if i.get("value")]),
        "status": s.get("status", ""), "intent": s.get("intent", ""),
        # R5 : CodeableReference {concept:{…}} ; R4 : CodeableConcept — les deux acceptés
        "code_label": _coding_display(_concept_of(s.get("code"))),
        "authored_on": s.get("authoredOn"),
        "requester": _ref_display(s.get("requester")),
        "performer": _ref_display(_first(s.get("performer", []), {})),
    }
    if s.get("priority"):
        sr["_priority"] = s["priority"]
    if reason:
        sr["_reason"] = reason
    return sr


def map_procedure(p: dict) -> dict:
    performer = None
    for pf in p.get("performer", []):
        performer = _ref_display(pf.get("actor") or pf.get("individual") or {})
        if performer:
            break
    proc = {
        "proc_id": p.get("id", ""),
        "identifier": _first([i.get("value") for i in p.get("identifier", []) if i.get("value")]),
        "status": p.get("status", ""), "code_label": _coding_display(p.get("code")),
        "occurred_at": p.get("occurrenceDateTime") or p.get("occurrencePeriod", {}).get("start"),
        "performer": performer,
        "body_site": _coding_display(_first(p.get("bodySite", []), {})),
    }
    if p.get("outcome"):
        proc["_outcome"] = _coding_display(p["outcome"])
    rep = _first([r.get("reference") for r in p.get("report", [])])
    if rep:
        proc["_report_ref"] = rep
    return proc


def map_audit_event(a: dict) -> dict:
    raw = a.get("action", "")
    outcome = a.get("outcome") or {}
    oc = outcome.get("code")                       # R5 : Coding ; R4-like : CodeableConcept
    outcome_code = (oc.get("code") or oc.get("display") or _coding_display(oc)) if isinstance(oc, dict) else oc
    ent = _first(a.get("entity", []), {})
    audit = {
        "audit_id": a.get("id", ""), "event_type": _coding_display(a.get("code")),
        "action": AUDIT_ACTION_MAP.get(raw, raw),
        "recorded_at": a.get("recorded"), "outcome_code": outcome_code or "",
        "patient_ref": _ref_value(a.get("patient")),
        "agent_who": _ref_display(_first(a.get("agent", []), {}).get("who")),
        "source_observer": _ref_display(a.get("source", {}).get("observer")),
        "_entity_ref": _ref_value(ent.get("what")),
    }
    if a.get("severity"):
        audit["_severity"] = a["severity"]
    if a.get("encounter"):
        audit["_encounter_ref"] = _ref_value(a["encounter"])
    return audit


def map_consent(c: dict) -> dict:
    status = CONSENT_STATUS_MAP.get(c.get("status", ""), c.get("status"))
    # décision explicite « deny » = refus, quel que soit le status
    if c.get("decision") == "deny" and status == "active":
        status = "refused"

    purpose = None
    prov = _first(_as_list(c.get("provision")), {})
    p0 = _first(prov.get("purpose", []), {})        # R5 : Coding
    purpose = p0.get("display") or p0.get("code") or _coding_display(p0)
    if not purpose:
        sc = c.get("scope", {}).get("coding", [])
        purpose = next((x.get("code") for x in sc if x.get("code")), "care-continuity")

    signed_by = None
    v0 = _first(c.get("verification", []), {})
    vw = v0.get("verifiedWith", {})
    signed_by = vw.get("display") or vw.get("identifier", {}).get("value")
    if not signed_by:
        pf = _first(c.get("performer", []), {})
        signed_by = pf.get("display") or pf.get("identifier", {}).get("value")
    for ext in c.get("extension", []):
        if "legal-representative" in ext.get("url", ""):
            signed_by = "representative"

    return {"status": status, "purpose": purpose, "signed_by": signed_by or "patient",
            "date": _iso_date_only(c.get("date") or c.get("dateTime"))}


def map_allergy_intolerance(a: dict) -> Optional[dict]:
    ver = _coding_code(a.get("verificationStatus"))
    if ver and ver != "confirmed":                 # tables_fhir_h2 §17 : confirmed requis
        logger.warning("AllergyIntolerance %s : verificationStatus=%s — non persistée", a.get("id"), ver)
        return None
    code_cc = a.get("code", {})
    sub0 = _first(code_cc.get("coding", []), {})
    r0 = _first(a.get("reaction", []), {})
    m0 = _first(r0.get("manifestation", []), {})
    concept = _concept_of(m0)
    rc0 = _first(concept.get("coding", []), {})
    res = {
        "allergy_id": a.get("id") or "",
        "substance": code_cc.get("text") or sub0.get("display", ""),
        "snomed_substance": sub0.get("code", ""),
        "reaction": concept.get("text") or rc0.get("display", ""),
        "snomed_reaction": rc0.get("code", ""),
        "criticite": CRITICALITY_MAP_FHIR_TO_H2.get(a.get("criticality", ""), "MOYENNE"),
        "date": _iso_date_only(a.get("recordedDate")),
        "status": _coding_code(a.get("clinicalStatus")) or "active",
        "category": _first(a.get("category", [])) or "medication",
    }
    sev = r0.get("severity", "")
    if sev in SEVERITY_FHIR_VALUES:
        res["severity"] = sev
    return res


# ══════════════════════════════════════════════════════════════════════════════
# 9. ASSEMBLEUR
# ══════════════════════════════════════════════════════════════════════════════

def bundle_to_h2_document(bundle: dict, strict: bool = True) -> dict:
    """
    Bundle FHIR R5 → document MongoDB H2.
    strict=True  : MappingError si au moins une erreur (rejet motivé du bundle).
    strict=False : erreurs consignées dans doc['_mapping_errors'], éléments fautifs ignorés.
    """
    errors: list[str] = []
    entries = bundle.get("entry", [])

    # index fullUrl → "Type/id" (références urn:uuid: ou URL absolues)
    url_index: dict[str, str] = {}
    resources: dict[str, dict[str, dict]] = {}
    for n, entry in enumerate(entries):
        res = entry.get("resource", {})
        rtype, rid = res.get("resourceType", ""), res.get("id") or f"_anon{n}"
        resources.setdefault(rtype, {})[rid] = res
        if entry.get("fullUrl"):
            url_index[entry["fullUrl"]] = f"{rtype}/{rid}"

    def norm_ref(ref: Optional[str]) -> str:
        if not ref:
            return ""
        if ref in url_index:
            return url_index[ref]
        parts = ref.split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else ref

    patients = list(resources.get("Patient", {}).values())
    if not patients:
        raise MappingError("Le bundle ne contient pas de ressource Patient.")
    doc = map_patient(patients[0])

    for key, rtype, fn in (
        ("_organizations", "Organization", map_organization),
        ("_practitioners", "Practitioner", map_practitioner),
        ("_roles", "PractitionerRole", map_practitioner_role),
        ("_devices", "Device", map_device),
        ("_locations", "Location", map_location),
        ("_endpoints", "Endpoint", map_endpoint),
    ):
        doc[key] = [fn(r) for r in resources.get(rtype, {}).values()]

    visit_map: dict[str, dict] = {}
    for enc in resources.get("Encounter", {}).values():
        try:
            visit = map_encounter(enc)
        except MappingError as exc:
            _err(errors, str(exc))
            continue
        visit_map[f"Encounter/{enc.get('id', '')}"] = visit
        doc["visits"].append(visit)

    def target_of(res: dict) -> Optional[dict]:
        ref = norm_ref(res.get("encounter", {}).get("reference", ""))
        t = visit_map.get(ref)
        if t is None:
            _err(errors, f"{res.get('resourceType')} {res.get('id')} : encounter '{ref}' introuvable ou rejeté")
        return t

    for cond in resources.get("Condition", {}).values():
        t = target_of(cond)
        if t is not None:
            try:
                t["conditions"].append(map_condition(cond))
            except MappingError as exc:
                _err(errors, str(exc))

    for obs in resources.get("Observation", {}).values():
        # groupe sanguin : Observation sans venue → champ racine blood_type
        if _loinc_of(obs.get("code", {})) == BLOOD_GROUP_LOINC and not obs.get("encounter"):
            bt = obs.get("valueString") or _coding_display(obs.get("valueCodeableConcept"))
            if bt:
                doc["blood_type"] = bt
            continue
        t = target_of(obs)
        if t is None:
            continue
        m = map_observation(obs, errors)
        if m:
            t["observations"].append(m)

    for rtype, fn, key in (("ImagingStudy", map_imaging_study, "imaging"),
                           ("DiagnosticReport", map_diagnostic_report, "reports"),
                           ("ServiceRequest", map_service_request, "service_requests"),
                           ("Procedure", map_procedure, "procedures")):
        for res in resources.get(rtype, {}).values():
            t = target_of(res)
            if t is not None:
                t[key].append(fn(res))

    doc["_audit_log"] = [map_audit_event(a) for a in resources.get("AuditEvent", {}).values()]

    consents = list(resources.get("Consent", {}).values())
    doc["consent"] = map_consent(consents[0]) if consents else None
    if not consents:
        _err(errors, "Aucun Consent dans le bundle — transfert à refuser côté API")

    doc["allergies"] = [m for m in (map_allergy_intolerance(a)
                                    for a in resources.get("AllergyIntolerance", {}).values()) if m]

    if errors:
        if strict:
            raise MappingError("; ".join(errors))
        doc["_mapping_errors"] = errors
    return doc


# ══════════════════════════════════════════════════════════════════════════════
# 10. CLI
# ══════════════════════════════════════════════════════════════════════════════

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Bundle FHIR R5 → document MongoDB H2.")
    p.add_argument("--bundle", required=True, metavar="FICHIER")
    p.add_argument("--out", metavar="FICHIER")
    p.add_argument("--patient", metavar="P2-XXXX", help="Forcer l'identifiant patient H2")
    p.add_argument("--lenient", action="store_true", help="Ne pas échouer sur les erreurs de mapping")
    p.add_argument("--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s %(message)s")
    try:
        with open(args.bundle, encoding="utf-8") as f:
            bundle = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Impossible de lire '%s' : %s", args.bundle, exc)
        return 1
    try:
        doc = bundle_to_h2_document(bundle, strict=not args.lenient)
    except MappingError as exc:
        logger.error("Rejet : %s", exc)
        return 2
    if args.patient:
        doc["patient_id"] = args.patient
    out = json.dumps(doc, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        logger.warning("Document H2 écrit dans '%s'.", args.out)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
