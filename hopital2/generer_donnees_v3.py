#!/usr/bin/env python3
"""
generer_donnees_v3.py
══════════════════════════════════════════════════════════════════════════════
Générateur principal — Schéma natif v3 — Clinique Al Baçar (Hôpital 2)
Produit un fichier mongosh-compatible : sortie/hopital2_mongodb_v3.js

Architecture FHIR R5 — 17 ressources couvertes.
Compatibilité : adaptateurs v3.3

Modèle de données :
  - Collections SÉPARÉES pour les référentiels partagés (organisations,
    praticiens, rôles, équipements, services, endpoints) → évite la
    duplication dans chaque document patient.
  - Collection `patients` : données propres au patient + clés étrangères.

Usage :
  python generer_donnees_v3.py [--graine N] [--sortie DOSSIER] [--nb-patients N]
══════════════════════════════════════════════════════════════════════════════
"""

import argparse, json, os, random, re
from datetime import datetime, timedelta, date

# ══════════════════════════════════════════════════════════════════════════════
# 1. RÉFÉRENTIELS FIXES (collections séparées, NON dupliqués par patient)
# ══════════════════════════════════════════════════════════════════════════════

ORG_DOC = {
    "org_id":        "ORG-ALBACAR",
    "identifier":    "CLINIQUE-AL-BACAR",
    "active":        True,
    "type_label":    "Clinique privée d'ophtalmologie",
    "name":          "Clinique Al Baçar",
    "city":          "Casablanca",
    "country":       "MA",
    "_endpoint_ref": "EP-PACS-001"
}

LOCATIONS_DOCS = [
    {"location_id": "LOC-RETINA",   "name": "Service Rétine",               "_type": "exam-room",     "_dept": "Retina"},
    {"location_id": "LOC-GLAUCOMA", "name": "Service Glaucome",             "_type": "exam-room",     "_dept": "Glaucoma"},
    {"location_id": "LOC-CATARACT", "name": "Service Cataracte",            "_type": "operating-room","_dept": "Cataract Surgery"},
    {"location_id": "LOC-REFRACT",  "name": "Service Chirurgie Réfractive", "_type": "operating-room","_dept": "Refractive Surgery"},
    {"location_id": "LOC-GENERAL",  "name": "Consultation Générale",        "_type": "consultation",  "_dept": "General Ophthalmology"},
]
DEPT_TO_LOC = {loc["_dept"]: loc["location_id"] for loc in LOCATIONS_DOCS}

ENDPOINT_DOCS = [
    {
        "endpoint_id":     "EP-PACS-001",
        "status":          "active",
        "connection_type": "dicom-wado-rs",
        "name":            "PACS Orthanc — DICOMweb WADO-RS",
        "address":         "http://localhost:8042/dicom-web",
        "mime_type":       "application/dicom"
    },
    {
        "endpoint_id":     "EP-FHIR-001",
        "status":          "active",
        "connection_type": "hl7-fhir-rest",
        "name":            "Serveur FHIR R5 — Clinique Al Baçar",
        "address":         "http://localhost:8080/fhir",
        "mime_type":       "application/fhir+json"
    }
]

DEVICE_DOCS = [
    {
        "device_id":     "DEV-TONO-001",
        "display_name":  "Tonomètre à aplanation Goldmann",
        "status":        "active",
        "manufacturer":  "Haag-Streit",
        "model_number":  "AT 900",
        "serial_number": "HS-AT900-20240312",
        "type_label":    "Tonomètre à aplanation",
        "_location_ref": "LOC-RETINA"
    },
    {
        "device_id":     "DEV-OCT-001",
        "display_name":  "OCT Spectralis",
        "status":        "active",
        "manufacturer":  "Heidelberg Engineering",
        "model_number":  "Spectralis HRA+OCT",
        "serial_number": "HE-SPEC-20230518",
        "type_label":    "Tomographe en cohérence optique",
        "_location_ref": "LOC-RETINA"
    },
    {
        "device_id":     "DEV-RETINO-001",
        "display_name":  "Rétinographe non mydriatique",
        "status":        "active",
        "manufacturer":  "Topcon",
        "model_number":  "NW400",
        "serial_number": "TC-NW400-20240101",
        "type_label":    "Rétinographe",
        "_location_ref": "LOC-RETINA"
    }
]

DEPT_SPECIALTY = {
    "Retina":               "Rétinologie",
    "Glaucoma":             "Glaucomatologie",
    "Cataract Surgery":     "Chirurgie de la cataracte",
    "Refractive Surgery":   "Chirurgie réfractive",
    "General Ophthalmology":"Ophtalmologie générale",
}
DEPARTMENTS = list(DEPT_SPECIALTY.keys())

# ══════════════════════════════════════════════════════════════════════════════
# 2. LISTES DÉMOGRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════

LAST_NAMES = [
    "Alaoui","Bennani","Chraibi","Idrissi","Tazi","Berrada","Ouazzani","El Fassi",
    "Amrani","Naciri","Lahlou","Kettani","Sebti","Zniber","Squalli","Tahiri",
    "Mekouar","Benali","Bakkali","Fassi-Fihri","Mansouri","Ghali","Rahimi",
    "Oulkadi","Benslimane","Mrabet","Benkirane","Belghiti","Bargach","Bensouda",
    "Zaidane","Lamrani","Chaoui","Bennis","Boulahia","Zerhouni","Jaidi","Kabbaj",
    "Benabbou","Mrani","Lyazidi","Benjelloun","Belkadi","Bouayad","Mernissi",
    "Benomar","Figuigui","Bentaleb","Khattabi","Rahhali","Essaadi","Belkhadir",
    "Boutaleb","Bendriss","Benbrahim","Cherkaoui","Bensaid","Raissouni","Errafii",
    "Bennouna","Tahouri","Idrissi-Kaitouni","Benchekroun","Touimi","Belyamani",
]
FIRST_NAMES_M = [
    "Youssef","Omar","Karim","Rachid","Hassan","Mehdi","Adil","Hamza","Khalid",
    "Mohammed","Ahmed","Anas","Bilal","Reda","Nabil","Hicham","Saad","Tariq",
    "Zakaria","Ilyas","Jawad","Ayoub","Walid","Soufiane","Ismail","Othmane",
    "Badr","Rayan","Yassine","Imad","Ayman","Noureddine","Abdelhak","Mounir",
]
FIRST_NAMES_F = [
    "Fatima","Nadia","Salma","Khadija","Yasmine","Imane","Samira","Latifa",
    "Zineb","Hasnae","Meriem","Siham","Lamiae","Houda","Btissam","Ghita",
    "Souad","Naima","Rajae","Wafae","Sanae","Aicha","Loubna","Meryem",
    "Hind","Sara","Leila","Amina","Oumaima","Nour","Hafsa","Ikram",
]
STREETS_CASA = [
    "Rue Mohammed V","Bd Hassan II","Av des FAR","Rue Ibnou Rachiq",
    "Bd Zerktouni","Rue de Fès","Av Mers Sultan","Rue Oum Errabia",
    "Bd d'Anfa","Rue Colbert","Av Lalla Yacout","Rue Allal Ben Abdellah",
]
PHYSICIANS = [
    "Dr. Touimi","Dr. Benchekroun","Dr. Idrissi-Kaitouni","Dr. Belyamani",
    "Dr. Mernissi","Dr. Fassi-Fihri","Dr. Bargach","Dr. Belghiti",
    "Dr. Bensouda","Dr. Mansouri","Dr. Ghali","Dr. Rahimi","Dr. Oulkadi",
    "Dr. Benslimane","Dr. Mrabet","Dr. Benkirane","Dr. Zaidane","Dr. Lamrani",
    "Dr. Chaoui","Dr. Bennis","Dr. Boulahia","Dr. Zerhouni","Dr. Jaidi",
    "Dr. Kabbaj","Dr. Benabbou","Dr. Mrani","Dr. Lyazidi","Dr. Benjelloun",
    "Dr. Belkadi","Dr. Bouayad",
]

CONDITIONS_BY_DEPT = {
    "Retina": [
        ("E11.3", "H36.0", "Diabetic retinopathy"),
        ("H35.3", None,    "Age-related macular degeneration"),
        ("H35.0", None,    "Background retinopathy"),
    ],
    "Glaucoma": [
        ("H40.1", None, "Primary open-angle glaucoma"),
        ("H40.2", None, "Primary angle-closure glaucoma"),
    ],
    "Cataract Surgery": [
        ("H25.9", None, "Age-related cataract, unspecified"),
        ("H26.9", None, "Unspecified cataract"),
    ],
    "Refractive Surgery": [
        ("H52.1", None, "Myopia"),
        ("H52.0", None, "Hypermetropia"),
    ],
    "General Ophthalmology": [
        ("H10.9", None, "Conjunctivitis, unspecified"),
        ("H04.1", None, "Dry eye syndrome"),
        ("H16.9", None, "Keratitis, unspecified"),
    ],
}
REASONS_BY_DEPT = {
    "Retina":               ["Diabetic retinopathy follow-up","Macular degeneration check","Visual acuity decrease"],
    "Glaucoma":             ["Glaucoma monitoring","Elevated intraocular pressure","Optic nerve evaluation"],
    "Cataract Surgery":     ["Cataract surgery","Pre-operative assessment","Post-operative follow-up"],
    "Refractive Surgery":   ["Myopia correction — LASIK","Pre-LASIK evaluation","Post-LASIK follow-up"],
    "General Ophthalmology":["Routine eye exam","Red eye","Blurred vision","Annual check-up"],
}
VISIT_TYPES = {
    "Retina": 2, "Glaucoma": 2,
    "Cataract Surgery": 3, "Refractive Surgery": 3,
    "General Ophthalmology": 2,
}

# ── Pool d'allergies — criticite v3.3 (MOYENNE remplace MODEREE) ──────────────
ALLERGIES_POOL = [
    {"substance":"Fluorescein sodium","reaction":"Urticaria",        "criticite":"ELEVEE", "snomed_sub":"372639009","snomed_react":"126485001"},
    {"substance":"Tetracaine",        "reaction":"Contact dermatitis","criticite":"MOYENNE","snomed_sub":"372697009","snomed_react":"238567008"},
    {"substance":"Atropine",          "reaction":"Tachycardia",       "criticite":"MOYENNE","snomed_sub":"372819007","snomed_react":"3415004"},
    {"substance":"Penicillin",        "reaction":"Anaphylaxis",       "criticite":"ELEVEE", "snomed_sub":"764146007","snomed_react":"39579001"},
    {"substance":"Betaxolol",         "reaction":"Bradycardia",       "criticite":"MOYENNE","snomed_sub":"372512008","snomed_react":"48867003"},
    {"substance":"Sulfonamides",      "reaction":"Urticaria",         "criticite":"FAIBLE", "snomed_sub":"387406002","snomed_react":"126485001"},
]
BLOOD_TYPES = ["A+","A-","B+","B-","AB+","AB-","O+","O-"]

# ══════════════════════════════════════════════════════════════════════════════
# 3. PATIENTS FIXES (S1–S2, D1–D14)
# ══════════════════════════════════════════════════════════════════════════════

FIXED_PATIENTS = {
    "P2-0051": {"last_name":"Alaoui",   "first_name":"Youssef","sex":1,"birth_date":"1968-04-12","national_id":"AB123456","phone":"+212638780038","address":{"street":"12 Rue Hassan II","city":"Casablanca"},  "blood_type":"B+", "_dept":"Retina",              "_physician":"Dr. Touimi",      "_consent":"active",  "_note":"S1 — rétinopathie diabétique"},
    "P2-0052": {"last_name":"Bennani",  "first_name":"Fatima", "sex":2,"birth_date":"1975-09-30","national_id":"K445120", "phone":"+212661102234","address":{"street":"7 Bd Hassan II","city":"Casablanca"},    "blood_type":"A+", "_dept":"Glaucoma",             "_physician":"Dr. Benchekroun","_consent":"active",  "_note":"S2 — PIO 27/24 mmHg"},
    "P2-0053": {"last_name":"Idrissi",  "first_name":"Omar",   "sex":1,"birth_date":"1952-07-01","national_id":"M990012", "phone":"+212670001234","address":{"street":"3 Rue de Fès","city":"Casablanca"},      "blood_type":"O+", "_dept":"Retina",              "_physician":"Dr. Touimi",      "_consent":"active",  "_note":"D1 — consentement refusé H1"},
    "P2-0054": {"last_name":"Tazi",     "first_name":"Salma",  "sex":2,"birth_date":"1963-11-20","national_id":"F112233", "phone":"+212655443322","address":{"street":"15 Av des FAR","city":"Casablanca"},     "blood_type":"AB+","_dept":"Glaucoma",             "_physician":"Dr. Mernissi",    "_consent":"refused", "_note":"D2 — consentement refusé H2"},
    "P2-0055": {"last_name":"Berrada",  "first_name":"Karim",  "sex":1,"birth_date":"1944-03-05","national_id":"G554321", "phone":"+212688776655","address":{"street":"9 Rue Ibnou Rachiq","city":"Casablanca"}, "blood_type":"A+", "_dept":"Cataract Surgery",      "_physician":"Dr. Belghiti",    "_consent":"active",  "_note":"D3 — conflit groupe sanguin A+/A-"},
    "P2-0056": {"last_name":"Ouazzani", "first_name":"Rachid", "sex":1,"birth_date":"1958-06-14","national_id":None,      "phone":"+212621345678","address":{"street":"21 Bd Zerktouni","city":"Casablanca"},    "blood_type":"O+", "_dept":"Retina",              "_physician":"Dr. Touimi",      "_consent":"active",  "_note":"D4 — CIN absent"},
    "P2-0057": {"last_name":"El Fassi", "first_name":"Youcef", "sex":1,"birth_date":"1971-02-28","national_id":"H223344", "phone":"+212698001122","address":{"street":"5 Rue Allal Ben Abdellah","city":"Casablanca"},"blood_type":"B+","_dept":"Glaucoma",    "_physician":"Dr. Benchekroun","_consent":"active",  "_note":"D5 — orthographe différente"},
    "P2-0058": {"last_name":"Amrani",   "first_name":"Khadija","sex":2,"birth_date":"1965-08-19","national_id":"J445566", "phone":"+212614223344","address":{"street":"30 Av Mers Sultan","city":"Casablanca"},  "blood_type":"A+", "_dept":"General Ophthalmology","_physician":"Dr. Mansouri",    "_consent":"active",  "_note":"D6 — homonyme CIN différent"},
    "P2-0059": {"last_name":"Mekouar",  "first_name":"Imane",  "sex":2,"birth_date":"13/05/1990","national_id":"L667788", "phone":"+212677112233","address":{"street":"4 Rue Colbert","city":"Casablanca"},      "blood_type":"O-", "_dept":"Refractive Surgery",   "_physician":"Dr. Lamrani",     "_consent":"active",  "_note":"D13 — birth_date format JJ/MM/AAAA"},
    "P2-0060": {"last_name":"Squalli",  "first_name":"Hamza",  "sex":1,"birth_date":"1987-09-11","national_id":"N889900", "phone":"+212632009988","address":{"street":"17 Bd d'Anfa","city":"Casablanca"},       "blood_type":"B-", "_dept":"Retina",              "_physician":"Dr. Touimi",      "_consent":"active",  "_note":"D14 — imaging absente du PACS"},
}

# ══════════════════════════════════════════════════════════════════════════════
# 4. HELPERS
# ══════════════════════════════════════════════════════════════════════════════

PIO_UNIT = "mm[Hg]"   # UCUM — v3.3
PIO_REF_LOW, PIO_REF_HIGH = 10, 21
DATE_EXTRACT = datetime(2026, 9, 25, 18, 0, 0)
DATE_MIN     = datetime(2024, 1, 1,  8, 0, 0)
DATE_MAX     = datetime(2026, 9, 25, 17, 0, 0)

def prac_id(name: str) -> str:
    return "PRAC-" + re.sub(r"[^A-Z]", "_", name.upper().replace("DR. ","")).strip("_")

def role_id(name: str) -> str:
    return "ROLE-" + re.sub(r"[^A-Z]", "_", name.upper().replace("DR. ","")).strip("_")

def next_uid(rng) -> str:
    return f"2.25.{rng.randint(10**18, 10**20)}"

def iso_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+01:00")

def iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def rand_dt(rng, start: datetime, end: datetime) -> datetime:
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, delta))

def rand_birth(rng, dept: str) -> date:
    today = date(2026, 9, 25)
    if dept == "Refractive Surgery":
        age = rng.randint(18, 45)
    elif dept == "Cataract Surgery":
        age = rng.randint(55, 80)
    else:
        age = rng.randint(35, 75)
    return today.replace(year=today.year - age) + timedelta(days=rng.randint(-180, 180))

def rand_cin(rng) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return rng.choice(letters) + rng.choice(letters) + str(rng.randint(100000, 999999))

# ══════════════════════════════════════════════════════════════════════════════
# 5. RÉFÉRENTIELS — PRATICIENS ET RÔLES (générés une seule fois)
# ══════════════════════════════════════════════════════════════════════════════

def build_practitioners(phys_dept_map: dict) -> list:
    docs = []
    for name in sorted(phys_dept_map):
        pid   = prac_id(name)
        bare  = name.replace("Dr. ", "").strip()
        toks  = bare.split()
        docs.append({
            "prac_id":       pid,
            "identifier":    pid,
            "active":        True,
            "last_name":     toks[-1],
            "first_name":    toks[0] if len(toks) > 1 else "—",
            "qualification": "Ophtalmologue"
        })
    return docs

def build_roles(phys_dept_map: dict) -> list:
    docs = []
    for name in sorted(phys_dept_map):
        dept = phys_dept_map[name]
        docs.append({
            "role_id":          role_id(name),
            "active":           True,
            "practitioner_ref": prac_id(name),
            "org_ref":          "ORG-ALBACAR",
            "code_label":       "Médecin senior",
            "specialty_label":  DEPT_SPECIALTY.get(dept, "Ophtalmologie"),
            "_location_ref":    DEPT_TO_LOC.get(dept, "LOC-GENERAL")
        })
    return docs

# ══════════════════════════════════════════════════════════════════════════════
# 6. GÉNÉRATEURS CLINIQUES
# ══════════════════════════════════════════════════════════════════════════════

def gen_pio_obs(code, label, val, side_code, side_label, t):
    return {
        "loinc": code, "label": label,
        "value": val,  "unit":  PIO_UNIT,
        "at":    iso_dt(t),
        "category": "exam",
        "interpretation": "H" if val > PIO_REF_HIGH else "N",
        "bodySite": {"snomedCode": side_code, "display": side_label},
        "referenceRange": {"low": PIO_REF_LOW, "high": PIO_REF_HIGH, "unit": PIO_UNIT}
    }

def gen_observations(rng, dept: str, admitted_dt: datetime, fixed_pio=None) -> list:
    obs = []
    t   = admitted_dt + timedelta(minutes=10)

    if dept in ("Retina", "Glaucoma", "General Ophthalmology"):
        if fixed_pio:
            od, og = fixed_pio
        elif dept == "Glaucoma":
            od, og = rng.randint(22, 30), rng.randint(22, 28)
        else:
            od, og = rng.randint(11, 20), rng.randint(11, 20)
        obs.append(gen_pio_obs("79892-6","Right eye intraocular pressure", od,"18944008","Right eye structure",t))
        obs.append(gen_pio_obs("79893-4","Left eye intraocular pressure",  og, "8966001","Left eye structure", t))

    t += timedelta(minutes=2)
    has_hta = dept in ("Retina","Glaucoma")
    sys_bp  = rng.randint(130,160) if has_hta else rng.randint(110,130)
    dia_bp  = rng.randint(80,95)   if has_hta else rng.randint(70,85)
    obs.append({
        "loinc":"85354-9","label":"Blood pressure panel","category":"vital-signs","at":iso_dt(t),
        "components":[
            {"loinc":"8480-6","label":"Systolic BP", "value":sys_bp,"unit":"mm[Hg]"},
            {"loinc":"8462-4","label":"Diastolic BP","value":dia_bp,"unit":"mm[Hg]"},
        ]
    })

    if dept in ("Retina","General Ophthalmology"):
        t += timedelta(minutes=2)
        gly = rng.randint(160,280) if dept == "Retina" else rng.randint(80,140)
        obs.append({
            "loinc":"2339-0","label":"Glucose [Mass/volume] in Blood",
            "value":gly,"unit":"mg/dL","category":"laboratory","at":iso_dt(t),
            "interpretation":"H" if gly > 180 else "N"
        })
    return obs

def gen_conditions(rng, dept: str) -> list:
    choices = CONDITIONS_BY_DEPT.get(dept, [("H10.9",None,"Conjunctivitis")])
    code1, code2, label = rng.choice(choices)
    conds = [{"system":"ICD-10","code":code1,"label":label}]
    if code2:
        conds.append({"system":"ICD-10","code":code2,"label":label+" — manifestation"})
    return conds

def gen_imaging(rng, dept: str, patient_id: str, visit_id: str) -> list:
    if dept not in ("Retina","Glaucoma"):
        return []
    desc = "Color fundus photography, both eyes" if dept=="Retina" else "Optic nerve head photography"
    return [{"study_uid":next_uid(rng),"modality":"OP",
             "accession":f"ACC-{patient_id.replace('P2-','')}{rng.randint(10,99)}",
             "description":desc,"instances":2}]

def gen_report(dept, phys, visit_id, admitted_dt, has_imaging, conditions):
    pfx = f"RPT-{visit_id}"
    base = {"report_id":pfx,"status":"final","performer":phys,
            "imaging_ref":f"img-{visit_id}" if has_imaging else None}
    if dept=="Retina":
        has_dr = any("H36" in c["code"] for c in conditions)
        return {**base,
            "code_label":"Fond d'œil — rétinographie couleur",
            "effective_at":iso_dt(admitted_dt+timedelta(minutes=15)),
            "issued_at":iso_dt(admitted_dt+timedelta(minutes=45)),
            "conclusion":"Rétinopathie diabétique documentée. Suivi à 6 mois." if has_dr
                         else "Examen du fond d'œil réalisé."}
    if dept=="Glaucoma":
        return {**base,
            "code_label":"Champ visuel — périmétrie automatisée",
            "effective_at":iso_dt(admitted_dt+timedelta(minutes=20)),
            "issued_at":iso_dt(admitted_dt+timedelta(minutes=50)),
            "conclusion":"Déficit périphérique compatible avec un GPAO."}
    if dept=="Cataract Surgery":
        return {**base,
            "code_label":"Compte rendu opératoire — phacoémulsification",
            "effective_at":iso_dt(admitted_dt+timedelta(hours=1)),
            "issued_at":iso_dt(admitted_dt+timedelta(hours=2)),
            "conclusion":"Chirurgie réalisée sans complication. Implant LIO mis en place."}
    return None

def gen_service_request(dept, phys, visit_id, admitted_dt):
    if dept=="Retina":
        return {"sr_id":f"SR-{visit_id}","status":"completed","intent":"order",
                "code_label":"Rétinographie couleur des deux yeux",
                "authored_on":iso_dt(admitted_dt),"requester":phys}
    if dept=="Glaucoma":
        return {"sr_id":f"SR-{visit_id}","status":"completed","intent":"order",
                "code_label":"Périmétrie automatisée Humphrey 24-2",
                "authored_on":iso_dt(admitted_dt),"requester":phys}
    return None

def gen_procedure(dept, phys, visit_id, admitted_dt):
    if dept=="Cataract Surgery":
        return {"proc_id":f"PROC-{visit_id}","status":"completed",
                "code_label":"Phacoémulsification avec implant LIO",
                "occurred_at":iso_dt(admitted_dt+timedelta(hours=1)),
                "performer":phys,"body_site":"right eye"}
    if dept=="Refractive Surgery":
        return {"proc_id":f"PROC-{visit_id}","status":"completed",
                "code_label":"LASIK — chirurgie réfractive au laser excimer",
                "occurred_at":iso_dt(admitted_dt+timedelta(minutes=45)),
                "performer":phys,"body_site":"both eyes"}
    if dept=="Glaucoma":
        return {"proc_id":f"PROC-{visit_id}","status":"completed",
                "code_label":"Gonioscopie — examen de l'angle irido-cornéen",
                "occurred_at":iso_dt(admitted_dt+timedelta(minutes=30)),
                "performer":phys,"body_site":None}
    return None

def gen_audit(patient_id, admitted_dt, ctr, visit_id=None):
    return [
        {"audit_id":f"AUD-{ctr:05d}","event_type":"record-creation","action":"C",
         "recorded_at":iso_dt(admitted_dt),"outcome_code":"success",
         "patient_ref":patient_id,
         "agent_who":"FHIR-Connector-v3","source_observer":"Clinique Al Baçar — DPI",
         "encounter_ref":visit_id},
        {"audit_id":f"AUD-{ctr+1:05d}","event_type":"record-access","action":"R",
         "recorded_at":"2026-09-25T18:00:00+01:00","outcome_code":"success",
         "patient_ref":patient_id,
         "agent_who":"FHIR-Connector-v3 (export)","source_observer":"Clinique Al Baçar — DPI"}
    ]

def gen_allergy(rng, patient_id, fixed=None):
    if fixed is not None:
        return fixed
    if rng.random() > 0.20:
        return []
    e = rng.choice(ALLERGIES_POOL)
    yr,mo,dy = rng.randint(2010,2024),rng.randint(1,12),rng.randint(1,28)
    return [{"allergy_id":f"ALG-{patient_id}-01","substance":e["substance"],
             "snomed_substance":e["snomed_sub"],"reaction":e["reaction"],
             "snomed_reaction":e["snomed_react"],"criticite":e["criticite"],
             "date":f"{yr}-{mo:02d}-{dy:02d}","status":"active",
             "category":"medication","verificationStatus":"confirmed"}]

# ══════════════════════════════════════════════════════════════════════════════
# 7. GÉNÉRATEUR PATIENT (document allégé — pas de référentiels embarqués)
# ══════════════════════════════════════════════════════════════════════════════

def gen_patient(rng, patient_id, audit_ctr, fixed=None, nb_visits=None):
    if fixed:
        last,first  = fixed["last_name"], fixed["first_name"]
        sex         = fixed["sex"]
        birth_date  = fixed["birth_date"]
        national_id = fixed["national_id"]
        phone       = fixed["phone"]
        address     = fixed["address"]
        blood_type  = fixed["blood_type"]
        main_dept   = fixed["_dept"]
        main_phys   = fixed["_physician"]
        consent_st  = fixed.get("_consent","active")
    else:
        sex        = rng.choice([1,2])
        first      = rng.choice(FIRST_NAMES_M if sex==1 else FIRST_NAMES_F)
        last       = rng.choice(LAST_NAMES)
        main_dept  = rng.choice(DEPARTMENTS)
        birth_date = iso_date(rand_birth(rng, main_dept))
        national_id= rand_cin(rng)
        phone      = "+212" + str(rng.randint(600000000,699999999))
        address    = {"street":f"{rng.randint(1,99)} {rng.choice(STREETS_CASA)}","city":"Casablanca"}
        blood_type = rng.choice(BLOOD_TYPES)
        main_phys  = rng.choice(PHYSICIANS)
        consent_st = "active"

    # Allergies
    if fixed and patient_id=="P2-0051":
        fixed_alg = [{"allergy_id":"ALG-P2-0051-01","substance":"Fluorescein sodium",
                      "snomed_substance":"372639009","reaction":"Urticaria",
                      "snomed_reaction":"126485001","criticite":"ELEVEE",
                      "date":"2026-07-15","status":"active","category":"medication",
                      "verificationStatus":"confirmed"}]
    else:
        fixed_alg = None
    allergies = gen_allergy(rng, patient_id, fixed=fixed_alg)

    # Visites
    nv = nb_visits or rng.randint(1,2)   # max 2 visites par patient aléatoire → taille raisonnable
    visits = []
    for i in range(nv):
        vid  = f"V-{patient_id}-{i+1:02d}"
        dept = main_dept if i==0 else rng.choice(DEPARTMENTS)
        phys = main_phys if i==0 else rng.choice(PHYSICIANS)

        admitted_dt   = rand_dt(rng, DATE_MIN, DATE_MAX-timedelta(days=1))
        duration_h    = rng.randint(1,2) if VISIT_TYPES.get(dept,2)==2 else rng.randint(4,24)
        discharged_dt = admitted_dt + timedelta(hours=duration_h)
        if discharged_dt > DATE_EXTRACT:
            discharged_dt = None

        conditions = gen_conditions(rng, dept)

        fixed_pio = (27,24) if (patient_id=="P2-0052" and i==0 and dept=="Glaucoma") else None
        observations = gen_observations(rng, dept, admitted_dt, fixed_pio=fixed_pio)

        imaging = gen_imaging(rng, dept, patient_id, vid)
        rpt  = gen_report(dept, phys, vid, admitted_dt, bool(imaging), conditions)
        sr   = gen_service_request(dept, phys, vid, admitted_dt)
        proc = gen_procedure(dept, phys, vid, admitted_dt)

        visits.append({
            "visit_id":         vid,
            "visit_type":       VISIT_TYPES.get(dept,2),
            "department":       dept,
            "physician_ref":    prac_id(phys),   # clé étrangère (collections séparées)
            "physician":        phys,             # display pour Encounter.participant (adaptateur v3.3)
            "admitted_at":      iso_dt(admitted_dt),
            "discharged_at":    iso_dt(discharged_dt) if discharged_dt else None,
            "reason":           rng.choice(REASONS_BY_DEPT[dept]),
            "conditions":       conditions,
            "observations":     observations,
            "imaging":          imaging,
            "reports":          [rpt]  if rpt  else [],
            "service_requests": [sr]   if sr   else [],
            "procedures":       [proc] if proc else [],
        })

    adm_dt   = datetime.fromisoformat(visits[0]["admitted_at"])
    first_vid= visits[0]["visit_id"]
    cons_date= iso_date(adm_dt.date() - timedelta(days=rng.randint(5,20)))

    return {
        "patient_id":  patient_id,
        "last_name":   last,
        "first_name":  first,
        "sex":         sex,
        "birth_date":  birth_date,
        "national_id": national_id,
        "phone":       phone,
        "address":     address,
        "blood_type":  blood_type,
        "allergies":   allergies,
        "consent":     {"status":consent_st,"purpose":"care-continuity","signed_by":"patient","date":cons_date},
        "visits":      visits,
        # clés étrangères → collections séparées (pas de duplication)
        "org_ref":     "ORG-ALBACAR",
        "_audit_log":  gen_audit(patient_id, adm_dt, audit_ctr, first_vid),
    }

# ══════════════════════════════════════════════════════════════════════════════
# 8. SÉRIALISATION JS
# ══════════════════════════════════════════════════════════════════════════════

def to_js_array(docs: list) -> str:
    raw = json.dumps(docs, ensure_ascii=False, indent=2, default=str)
    raw = re.sub(r'"(\d{4}-\d{2}-\d{2}T[^"]+)"',
                 lambda m: f'ISODate("{m.group(1)}")', raw)
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return raw

def write_collection(f, coll: str, docs: list, indexes: list[str] | None = None):
    """Écrit un bloc insertMany pour une collection dans le fichier JS."""
    f.write(f"\n// ── {coll} ──────────────────────────────────────────────\n")
    f.write(f"db.{coll}.drop();\n")
    body = to_js_array(docs)
    f.write(f"db.{coll}.insertMany([\n{body}\n]);\n")
    if indexes:
        for idx in indexes:
            f.write(f"db.{coll}.createIndex({{ {idx}: 1 }});\n")

# ══════════════════════════════════════════════════════════════════════════════
# 9. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graine",      type=int, default=42)
    parser.add_argument("--sortie",      type=str, default="sortie")
    parser.add_argument("--nb-patients", type=int, default=60)
    args = parser.parse_args()

    rng = random.Random(args.graine)
    os.makedirs(args.sortie, exist_ok=True)

    nb_rand = max(0, args.nb_patients - len(FIXED_PATIENTS))

    print(f"[1/5] Génération de {args.nb_patients} patients (graine={args.graine})…")
    patient_docs   : list = []
    phys_dept_map  : dict = {}
    audit_ctr      = 1

    # Patients fixes
    for pid, fdata in FIXED_PATIENTS.items():
        patient_docs.append(gen_patient(rng, pid, audit_ctr, fixed=fdata, nb_visits=1))
        phys_dept_map[fdata["_physician"]] = fdata["_dept"]
        audit_ctr += 2

    # Patients aléatoires
    for idx in range(1, nb_rand+1):
        pid = f"P2-{idx:04d}"
        doc = gen_patient(rng, pid, audit_ctr)
        patient_docs.append(doc)
        audit_ctr += 2
        # Collecter praticiens
        for v in doc["visits"]:
            phys_dept_map.setdefault(
                next(p for p in PHYSICIANS if prac_id(p)==v["physician_ref"]),
                v["department"]
            ) if False else None   # physician_ref est déjà l'id — on reconstruira ci-dessous

    # Reconstruire phys_dept_map depuis les documents (physician_ref = prac_id)
    id_to_name = {prac_id(p): p for p in PHYSICIANS}
    for doc in patient_docs:
        for v in doc["visits"]:
            pid_ref = v["physician_ref"]
            if pid_ref in id_to_name:
                phys_dept_map.setdefault(id_to_name[pid_ref], v["department"])

    print(f"      {len(phys_dept_map)} praticiens recensés")

    print("[2/5] Construction des référentiels…")
    prac_docs = build_practitioners(phys_dept_map)
    role_docs = build_roles(phys_dept_map)

    out_path = os.path.join(args.sortie, "hopital2_mongodb_v3.js")
    print(f"[3/5] Écriture dans {out_path}…")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(
            "// ═══════════════════════════════════════════════════════════════\n"
            "// hopital2_mongodb_v3.js  —  Clinique Al Baçar — FHIR R5 v3.3-compat\n"
            f"// Généré le {datetime.now():%Y-%m-%d %H:%M}  |  graine={args.graine}\n"
            "//\n"
            "// Architecture : collections séparées pour les référentiels partagés\n"
            "//   organisations, locations, endpoints, devices  → 1 doc par entité\n"
            "//   practitioners, practitioner_roles             → 1 doc par praticien\n"
            "//   patients                                      → clés étrangères (org_ref, physician_ref)\n"
            "//\n"
            "// Compatibilité v3.3 :\n"
            "//   unit PIO : mm[Hg] | criticite défaut : MOYENNE | consent D2 : refused\n"
            "//   national_id D4 : null | verificationStatus : confirmed sur allergies\n"
            "// ═══════════════════════════════════════════════════════════════\n\n"
            'db = db.getSiblingDB("hopital2");\n'
        )

        # Collections référentiels (1 insertMany chacune, taille fixe)
        write_collection(f, "organisations",        [ORG_DOC],      ["org_id"])
        write_collection(f, "locations",            LOCATIONS_DOCS, ["location_id"])
        write_collection(f, "endpoints",            ENDPOINT_DOCS,  ["endpoint_id"])
        write_collection(f, "devices",              DEVICE_DOCS,    ["device_id"])
        write_collection(f, "practitioners",        prac_docs,      ["prac_id"])
        write_collection(f, "practitioner_roles",   role_docs,      ["role_id"])

        # Collection patients — insertions par lots de 10 pour éviter la limite 16 Mo
        print(f"[4/5] Écriture de {len(patient_docs)} patients par lots…")
        f.write("\n// ── patients ─────────────────────────────────────────────────\n")
        f.write("db.patients.drop();\n")
        BATCH = 10
        for start in range(0, len(patient_docs), BATCH):
            batch = patient_docs[start:start+BATCH]
            body  = to_js_array(batch)
            f.write(f"db.patients.insertMany([\n{body}\n]);\n")

        f.write('\ndb.patients.createIndex({ patient_id: 1 }, { unique: true });\n')
        f.write('db.patients.createIndex({ national_id: 1 });\n')
        f.write('db.patients.createIndex({ "consent.status": 1 });\n')
        nb = args.nb_patients
        f.write(f'\nprint("✓ hopital2_mongodb_v3.js chargé — {nb} patients, '
                f'schéma FHIR R5 v3.3-compat (collections séparées)");\n')

    # ── Vérifications ──────────────────────────────────────────────────────
    print("[5/5] Vérification…")
    with open(out_path, encoding="utf-8") as f:
        chk = f.read()

    taille_ko = os.path.getsize(out_path) // 1024
    nb_patients_inseres = chk.count('"patient_id"')

    checks = {
        'unit mm[Hg] (UCUM)':          (chk.count('"mm[Hg]"'),  lambda n: n > 0),
        'unit mmHg (ancien, doit=0)':   (chk.count('"mmHg"'),    lambda n: n == 0),
        'criticite MOYENNE':            (chk.count('"MOYENNE"'),  lambda n: n > 0),
        'criticite MODEREE (doit=0)':   (chk.count('"MODEREE"'), lambda n: n == 0),
        'consent refused (D2)':         (chk.count('"refused"'),  lambda n: n >= 1),
        'consent not-done (doit=0)':    (chk.count('"not-done"'),lambda n: n == 0),
        'verificationStatus confirmed': (chk.count('"confirmed"'),lambda n: n > 0),
    }

    print(f"\n[OK] {out_path}")
    print(f"     Taille : {taille_ko} Ko | Patients insérés : {nb_patients_inseres}")
    print("     Collections créées : organisations, locations, endpoints,")
    print("                          devices, practitioners, practitioner_roles, patients")
    print("\n     Vérifications v3.3 :")
    all_ok = True
    for label, (val, test) in checks.items():
        ok = test(val)
        mark = "✅" if ok else "⚠ "
        print(f"       {mark} {label:<35}: {val}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n     ✅ Toutes les vérifications v3.3 sont OK.")
    else:
        print("\n     ⚠ Des incohérences ont été détectées ci-dessus.")

    print(f"\nChargement :")
    print(f"  mongosh < {out_path}")

if __name__ == "__main__":
    main()
