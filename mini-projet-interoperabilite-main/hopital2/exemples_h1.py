"""
exemples_h1.py — fabrique des Bundles « comme les enverrait H1 » (CHU / Oracle), pour les tests et la démo.
Format conforme au contrat reçu de H1 : Bundle transaction, un seul Patient, CIN (urn:ma:cin) + IPP du CHU,
Consent, identifiants stables, unités UCUM, tension en Observation 85354-9 (composantes 8480-6 / 8462-4).
"""
from __future__ import annotations

SYSTEM_IPP_H1 = "https://chu-almassira.ma/ipp"
BASE_H1 = "https://chu-almassira.ma/fhir"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"


def _entree(res: dict, request: dict) -> dict:
    return {"fullUrl": f"{BASE_H1}/{res['resourceType']}/{res['id']}", "resource": res, "request": request}


def _put(res: dict) -> dict:
    return _entree(res, {"method": "PUT", "url": f"{res['resourceType']}/{res['id']}"})


def bundle_h1(ipp="P1-0106", cin="CD654321", nom="Tazi", prenom="Salma", naissance="1975-09-30",
              sexe="female", consent="active", groupe="O+", avec_visite=True, visite="H1-V-0106-01",
              tension=(128, 82), glycemie_gl=1.1, echange_id=None, telephone="+212611223344") -> dict:
    pid = f"patient-{ipp}"
    p_ref = {"reference": f"Patient/{pid}"}
    identifiants = [{"system": SYSTEM_IPP_H1, "value": ipp}]
    if cin:
        identifiants.append({"use": "official", "system": "urn:ma:cin", "value": cin})
    patient = {"resourceType": "Patient", "id": pid, "identifier": identifiants,
               "name": [{"use": "official", "family": nom, "given": [prenom]}],
               "gender": sexe, "birthDate": naissance,
               "telecom": [{"system": "phone", "value": telephone}]}
    entrees = [_entree(patient, {"method": "POST", "url": "Patient", "ifNoneExist": f"identifier=urn:ma:cin|{cin}"}
                       if cin else {"method": "PUT", "url": f"Patient/{pid}"})]

    if consent:
        entrees.append(_put({
            "resourceType": "Consent", "id": f"consent-{ipp}", "status": consent,
            "decision": "permit" if consent == "active" else "deny",
            "category": [{"coding": [{"system": LOINC, "code": "59284-0", "display": "Consent Document"}]}],
            "subject": p_ref, "date": "2026-11-01"}))
    if groupe:
        entrees.append(_put({
            "resourceType": "Observation", "id": f"blood-{ipp}", "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                      "code": "laboratory"}]}],
            "code": {"coding": [{"system": LOINC, "code": "882-1", "display": "ABO and Rh group [Type] in Blood"}]},
            "subject": p_ref, "valueString": groupe}))
    if avec_visite:
        e_ref = {"reference": f"Encounter/{visite}"}
        entrees.append(_put({
            "resourceType": "Encounter", "id": visite, "status": "completed",
            "class": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                   "code": "AMB", "display": "Ambulatory"}]}],
            "subject": p_ref, "type": [{"text": "Endocrinologie"}],
            "actualPeriod": {"start": "2026-11-05T09:00:00+01:00", "end": "2026-11-05T09:40:00+01:00"}}))
        entrees.append(_put({
            "resourceType": "Condition", "id": f"cond-{visite}-1",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                           "code": "active"}]},
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "E11",
                                 "display": "Type 2 diabetes mellitus"}]},
            "subject": p_ref, "encounter": e_ref}))
        if tension:
            entrees.append(_put({
                "resourceType": "Observation", "id": f"obs-{visite}-1", "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                          "code": "vital-signs"}]}],
                "code": {"coding": [{"system": LOINC, "code": "85354-9", "display": "Blood pressure panel"}]},
                "subject": p_ref, "encounter": e_ref, "effectiveDateTime": "2026-11-05T09:10:00+01:00",
                "component": [
                    {"code": {"coding": [{"system": LOINC, "code": "8480-6"}]},
                     "valueQuantity": {"value": tension[0], "unit": "mm[Hg]", "system": UCUM, "code": "mm[Hg]"}},
                    {"code": {"coding": [{"system": LOINC, "code": "8462-4"}]},
                     "valueQuantity": {"value": tension[1], "unit": "mm[Hg]", "system": UCUM, "code": "mm[Hg]"}}]}))
        if glycemie_gl is not None:
            entrees.append(_put({
                "resourceType": "Observation", "id": f"obs-{visite}-2", "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                          "code": "laboratory"}]}],
                "code": {"coding": [{"system": LOINC, "code": "2339-0"}]},
                "subject": p_ref, "encounter": e_ref, "effectiveDateTime": "2026-11-05T09:15:00+01:00",
                "valueQuantity": {"value": glycemie_gl, "unit": "g/L", "system": UCUM, "code": "g/L"}}))
    b = {"resourceType": "Bundle", "type": "transaction", "entry": entrees}
    if echange_id:
        b["identifier"] = {"system": "https://chu-almassira.ma/echange", "value": echange_id}
    return b
