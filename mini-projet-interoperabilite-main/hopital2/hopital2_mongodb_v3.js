// ═══════════════════════════════════════════════════════════════
// hopital2_mongodb_v3.js  —  Clinique Al Baçar — FHIR R5 v3.3-compat
// Généré le 2026-11-21 09:39  |  graine=42
//
// Architecture : collections séparées pour les référentiels partagés
//   organisations, locations, endpoints, devices  → 1 doc par entité
//   practitioners, practitioner_roles             → 1 doc par praticien
//   patients                                      → clés étrangères (org_ref, physician_ref)
//
// Compatibilité v3.3 :
//   unit PIO : mm[Hg] | criticite défaut : MOYENNE | consent D2 : refused
//   national_id D4 : null | verificationStatus : confirmed sur allergies
// ═══════════════════════════════════════════════════════════════

db = db.getSiblingDB("hopital2");

// ── organisations ──────────────────────────────────────────────
db.organisations.drop();
db.organisations.insertMany([

  {
    "org_id": "ORG-ALBACAR",
    "identifier": "CLINIQUE-AL-BACAR",
    "active": true,
    "type_label": "Clinique privée d'ophtalmologie",
    "name": "Clinique Al Baçar",
    "city": "Casablanca",
    "country": "MA",
    "_endpoint_ref": "EP-PACS-001"
  }

]);
db.organisations.createIndex({ org_id: 1 });

// ── locations ──────────────────────────────────────────────
db.locations.drop();
db.locations.insertMany([

  {
    "location_id": "LOC-RETINA",
    "name": "Service Rétine",
    "_type": "exam-room",
    "_dept": "Retina"
  },
  {
    "location_id": "LOC-GLAUCOMA",
    "name": "Service Glaucome",
    "_type": "exam-room",
    "_dept": "Glaucoma"
  },
  {
    "location_id": "LOC-CATARACT",
    "name": "Service Cataracte",
    "_type": "operating-room",
    "_dept": "Cataract Surgery"
  },
  {
    "location_id": "LOC-REFRACT",
    "name": "Service Chirurgie Réfractive",
    "_type": "operating-room",
    "_dept": "Refractive Surgery"
  },
  {
    "location_id": "LOC-GENERAL",
    "name": "Consultation Générale",
    "_type": "consultation",
    "_dept": "General Ophthalmology"
  }

]);
db.locations.createIndex({ location_id: 1 });

// ── endpoints ──────────────────────────────────────────────
db.endpoints.drop();
db.endpoints.insertMany([

  {
    "endpoint_id": "EP-PACS-001",
    "status": "active",
    "connection_type": "dicom-wado-rs",
    "name": "PACS Orthanc — DICOMweb WADO-RS",
    "address": "http://localhost:8042/dicom-web",
    "mime_type": "application/dicom"
  },
  {
    "endpoint_id": "EP-FHIR-001",
    "status": "active",
    "connection_type": "hl7-fhir-rest",
    "name": "Serveur FHIR R5 — Clinique Al Baçar",
    "address": "http://localhost:8080/fhir",
    "mime_type": "application/fhir+json"
  }

]);
db.endpoints.createIndex({ endpoint_id: 1 });

// ── devices ──────────────────────────────────────────────
db.devices.drop();
db.devices.insertMany([

  {
    "device_id": "DEV-TONO-001",
    "display_name": "Tonomètre à aplanation Goldmann",
    "status": "active",
    "manufacturer": "Haag-Streit",
    "model_number": "AT 900",
    "serial_number": "HS-AT900-20240312",
    "type_label": "Tonomètre à aplanation",
    "_location_ref": "LOC-RETINA"
  },
  {
    "device_id": "DEV-OCT-001",
    "display_name": "OCT Spectralis",
    "status": "active",
    "manufacturer": "Heidelberg Engineering",
    "model_number": "Spectralis HRA+OCT",
    "serial_number": "HE-SPEC-20230518",
    "type_label": "Tomographe en cohérence optique",
    "_location_ref": "LOC-RETINA"
  },
  {
    "device_id": "DEV-RETINO-001",
    "display_name": "Rétinographe non mydriatique",
    "status": "active",
    "manufacturer": "Topcon",
    "model_number": "NW400",
    "serial_number": "TC-NW400-20240101",
    "type_label": "Rétinographe",
    "_location_ref": "LOC-RETINA"
  }

]);
db.devices.createIndex({ device_id: 1 });

// ── practitioners ──────────────────────────────────────────────
db.practitioners.drop();
db.practitioners.insertMany([

  {
    "prac_id": "PRAC-BARGACH",
    "identifier": "PRAC-BARGACH",
    "active": true,
    "last_name": "Bargach",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BELGHITI",
    "identifier": "PRAC-BELGHITI",
    "active": true,
    "last_name": "Belghiti",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BELKADI",
    "identifier": "PRAC-BELKADI",
    "active": true,
    "last_name": "Belkadi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENABBOU",
    "identifier": "PRAC-BENABBOU",
    "active": true,
    "last_name": "Benabbou",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENCHEKROUN",
    "identifier": "PRAC-BENCHEKROUN",
    "active": true,
    "last_name": "Benchekroun",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENJELLOUN",
    "identifier": "PRAC-BENJELLOUN",
    "active": true,
    "last_name": "Benjelloun",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENKIRANE",
    "identifier": "PRAC-BENKIRANE",
    "active": true,
    "last_name": "Benkirane",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENNIS",
    "identifier": "PRAC-BENNIS",
    "active": true,
    "last_name": "Bennis",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENSLIMANE",
    "identifier": "PRAC-BENSLIMANE",
    "active": true,
    "last_name": "Benslimane",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BENSOUDA",
    "identifier": "PRAC-BENSOUDA",
    "active": true,
    "last_name": "Bensouda",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BOUAYAD",
    "identifier": "PRAC-BOUAYAD",
    "active": true,
    "last_name": "Bouayad",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-BOULAHIA",
    "identifier": "PRAC-BOULAHIA",
    "active": true,
    "last_name": "Boulahia",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-CHAOUI",
    "identifier": "PRAC-CHAOUI",
    "active": true,
    "last_name": "Chaoui",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-FASSI_FIHRI",
    "identifier": "PRAC-FASSI_FIHRI",
    "active": true,
    "last_name": "Fassi-Fihri",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-GHALI",
    "identifier": "PRAC-GHALI",
    "active": true,
    "last_name": "Ghali",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-IDRISSI_KAITOUNI",
    "identifier": "PRAC-IDRISSI_KAITOUNI",
    "active": true,
    "last_name": "Idrissi-Kaitouni",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-JAIDI",
    "identifier": "PRAC-JAIDI",
    "active": true,
    "last_name": "Jaidi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-LAMRANI",
    "identifier": "PRAC-LAMRANI",
    "active": true,
    "last_name": "Lamrani",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-LYAZIDI",
    "identifier": "PRAC-LYAZIDI",
    "active": true,
    "last_name": "Lyazidi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-MANSOURI",
    "identifier": "PRAC-MANSOURI",
    "active": true,
    "last_name": "Mansouri",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-MERNISSI",
    "identifier": "PRAC-MERNISSI",
    "active": true,
    "last_name": "Mernissi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-MRABET",
    "identifier": "PRAC-MRABET",
    "active": true,
    "last_name": "Mrabet",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-MRANI",
    "identifier": "PRAC-MRANI",
    "active": true,
    "last_name": "Mrani",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-OULKADI",
    "identifier": "PRAC-OULKADI",
    "active": true,
    "last_name": "Oulkadi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-RAHIMI",
    "identifier": "PRAC-RAHIMI",
    "active": true,
    "last_name": "Rahimi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-TOUIMI",
    "identifier": "PRAC-TOUIMI",
    "active": true,
    "last_name": "Touimi",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-ZAIDANE",
    "identifier": "PRAC-ZAIDANE",
    "active": true,
    "last_name": "Zaidane",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  },
  {
    "prac_id": "PRAC-ZERHOUNI",
    "identifier": "PRAC-ZERHOUNI",
    "active": true,
    "last_name": "Zerhouni",
    "first_name": "—",
    "qualification": "Ophtalmologue"
  }

]);
db.practitioners.createIndex({ prac_id: 1 });

// ── practitioner_roles ──────────────────────────────────────────────
db.practitioner_roles.drop();
db.practitioner_roles.insertMany([

  {
    "role_id": "ROLE-BARGACH",
    "active": true,
    "practitioner_ref": "PRAC-BARGACH",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie de la cataracte",
    "_location_ref": "LOC-CATARACT"
  },
  {
    "role_id": "ROLE-BELGHITI",
    "active": true,
    "practitioner_ref": "PRAC-BELGHITI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie de la cataracte",
    "_location_ref": "LOC-CATARACT"
  },
  {
    "role_id": "ROLE-BELKADI",
    "active": true,
    "practitioner_ref": "PRAC-BELKADI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie réfractive",
    "_location_ref": "LOC-REFRACT"
  },
  {
    "role_id": "ROLE-BENABBOU",
    "active": true,
    "practitioner_ref": "PRAC-BENABBOU",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Rétinologie",
    "_location_ref": "LOC-RETINA"
  },
  {
    "role_id": "ROLE-BENCHEKROUN",
    "active": true,
    "practitioner_ref": "PRAC-BENCHEKROUN",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-BENJELLOUN",
    "active": true,
    "practitioner_ref": "PRAC-BENJELLOUN",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-BENKIRANE",
    "active": true,
    "practitioner_ref": "PRAC-BENKIRANE",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-BENNIS",
    "active": true,
    "practitioner_ref": "PRAC-BENNIS",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Ophtalmologie générale",
    "_location_ref": "LOC-GENERAL"
  },
  {
    "role_id": "ROLE-BENSLIMANE",
    "active": true,
    "practitioner_ref": "PRAC-BENSLIMANE",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Rétinologie",
    "_location_ref": "LOC-RETINA"
  },
  {
    "role_id": "ROLE-BENSOUDA",
    "active": true,
    "practitioner_ref": "PRAC-BENSOUDA",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie réfractive",
    "_location_ref": "LOC-REFRACT"
  },
  {
    "role_id": "ROLE-BOUAYAD",
    "active": true,
    "practitioner_ref": "PRAC-BOUAYAD",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-BOULAHIA",
    "active": true,
    "practitioner_ref": "PRAC-BOULAHIA",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Rétinologie",
    "_location_ref": "LOC-RETINA"
  },
  {
    "role_id": "ROLE-CHAOUI",
    "active": true,
    "practitioner_ref": "PRAC-CHAOUI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Rétinologie",
    "_location_ref": "LOC-RETINA"
  },
  {
    "role_id": "ROLE-FASSI_FIHRI",
    "active": true,
    "practitioner_ref": "PRAC-FASSI_FIHRI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie réfractive",
    "_location_ref": "LOC-REFRACT"
  },
  {
    "role_id": "ROLE-GHALI",
    "active": true,
    "practitioner_ref": "PRAC-GHALI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie de la cataracte",
    "_location_ref": "LOC-CATARACT"
  },
  {
    "role_id": "ROLE-IDRISSI_KAITOUNI",
    "active": true,
    "practitioner_ref": "PRAC-IDRISSI_KAITOUNI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-JAIDI",
    "active": true,
    "practitioner_ref": "PRAC-JAIDI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-LAMRANI",
    "active": true,
    "practitioner_ref": "PRAC-LAMRANI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie réfractive",
    "_location_ref": "LOC-REFRACT"
  },
  {
    "role_id": "ROLE-LYAZIDI",
    "active": true,
    "practitioner_ref": "PRAC-LYAZIDI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-MANSOURI",
    "active": true,
    "practitioner_ref": "PRAC-MANSOURI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Ophtalmologie générale",
    "_location_ref": "LOC-GENERAL"
  },
  {
    "role_id": "ROLE-MERNISSI",
    "active": true,
    "practitioner_ref": "PRAC-MERNISSI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-MRABET",
    "active": true,
    "practitioner_ref": "PRAC-MRABET",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie de la cataracte",
    "_location_ref": "LOC-CATARACT"
  },
  {
    "role_id": "ROLE-MRANI",
    "active": true,
    "practitioner_ref": "PRAC-MRANI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-OULKADI",
    "active": true,
    "practitioner_ref": "PRAC-OULKADI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Rétinologie",
    "_location_ref": "LOC-RETINA"
  },
  {
    "role_id": "ROLE-RAHIMI",
    "active": true,
    "practitioner_ref": "PRAC-RAHIMI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Chirurgie réfractive",
    "_location_ref": "LOC-REFRACT"
  },
  {
    "role_id": "ROLE-TOUIMI",
    "active": true,
    "practitioner_ref": "PRAC-TOUIMI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Rétinologie",
    "_location_ref": "LOC-RETINA"
  },
  {
    "role_id": "ROLE-ZAIDANE",
    "active": true,
    "practitioner_ref": "PRAC-ZAIDANE",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  },
  {
    "role_id": "ROLE-ZERHOUNI",
    "active": true,
    "practitioner_ref": "PRAC-ZERHOUNI",
    "org_ref": "ORG-ALBACAR",
    "code_label": "Médecin senior",
    "specialty_label": "Glaucomatologie",
    "_location_ref": "LOC-GLAUCOMA"
  }

]);
db.practitioner_roles.createIndex({ role_id: 1 });

// ── patients ─────────────────────────────────────────────────
db.patients.drop();
db.patients.insertMany([

  {
    "patient_id": "P2-0051",
    "last_name": "Alaoui",
    "first_name": "Youssef",
    "sex": 1,
    "birth_date": "1968-04-12",
    "national_id": "AB123456",
    "phone": "+212638780038",
    "address": {
      "street": "12 Rue Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0051-01",
        "substance": "Fluorescein sodium",
        "snomed_substance": "372639009",
        "reaction": "Urticaria",
        "snomed_reaction": "126485001",
        "criticite": "ELEVEE",
        "date": "2026-07-15",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-09-14"
    },
    "visits": [
      {
        "visit_id": "V-P2-0051-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-TOUIMI",
        "physician": "Dr. Touimi",
        "admitted_at": ISODate("2026-09-20T15:33:32+01:00"),
        "discharged_at": ISODate("2026-09-20T16:33:32+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "E11.3",
            "label": "Diabetic retinopathy"
          },
          {
            "system": "ICD-10",
            "code": "H36.0",
            "label": "Diabetic retinopathy — manifestation"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 15,
            "unit": "mm[Hg]",
            "at": ISODate("2026-09-20T15:43:32+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 14,
            "unit": "mm[Hg]",
            "at": ISODate("2026-09-20T15:43:32+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-09-20T15:45:32+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 137,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 254,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2026-09-20T15:47:32+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.11060236952204337488",
            "modality": "OP",
            "accession": "ACC-005185",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0051-01",
            "status": "final",
            "performer": "Dr. Touimi",
            "imaging_ref": "img-V-P2-0051-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2026-09-20T15:48:32+01:00"),
            "issued_at": ISODate("2026-09-20T16:18:32+01:00"),
            "conclusion": "Rétinopathie diabétique documentée. Suivi à 6 mois."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0051-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2026-09-20T15:33:32+01:00"),
            "requester": "Dr. Touimi"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00001",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-09-20T15:33:32+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0051",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0051-01"
      },
      {
        "audit_id": "AUD-00002",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0051",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0052",
    "last_name": "Bennani",
    "first_name": "Fatima",
    "sex": 2,
    "birth_date": "1975-09-30",
    "national_id": "K445120",
    "phone": "+212661102234",
    "address": {
      "street": "7 Bd Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0052-01",
        "substance": "Tetracaine",
        "snomed_substance": "372697009",
        "reaction": "Contact dermatitis",
        "snomed_reaction": "238567008",
        "criticite": "MOYENNE",
        "date": "2013-09-20",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-01-29"
    },
    "visits": [
      {
        "visit_id": "V-P2-0052-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2024-02-11T13:19:57+01:00"),
        "discharged_at": ISODate("2024-02-11T14:19:57+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2024-02-11T13:29:57+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2024-02-11T13:29:57+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-02-11T13:31:57+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 137,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 94,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.96178914841424964541",
            "modality": "OP",
            "accession": "ACC-005264",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0052-01",
            "status": "final",
            "performer": "Dr. Benchekroun",
            "imaging_ref": "img-V-P2-0052-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-02-11T13:39:57+01:00"),
            "issued_at": ISODate("2024-02-11T14:09:57+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0052-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-02-11T13:19:57+01:00"),
            "requester": "Dr. Benchekroun"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0052-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-02-11T13:49:57+01:00"),
            "performer": "Dr. Benchekroun",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00003",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-02-11T13:19:57+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0052",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0052-01"
      },
      {
        "audit_id": "AUD-00004",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0052",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0053",
    "last_name": "Idrissi",
    "first_name": "Omar",
    "sex": 1,
    "birth_date": "1952-07-01",
    "national_id": "M990012",
    "phone": "+212670001234",
    "address": {
      "street": "3 Rue de Fès",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0053-01",
        "substance": "Atropine",
        "snomed_substance": "372819007",
        "reaction": "Tachycardia",
        "snomed_reaction": "3415004",
        "criticite": "MOYENNE",
        "date": "2011-02-13",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-05-16"
    },
    "visits": [
      {
        "visit_id": "V-P2-0053-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-TOUIMI",
        "physician": "Dr. Touimi",
        "admitted_at": ISODate("2024-05-30T13:50:52+01:00"),
        "discharged_at": ISODate("2024-05-30T15:50:52+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 20,
            "unit": "mm[Hg]",
            "at": ISODate("2024-05-30T14:00:52+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 15,
            "unit": "mm[Hg]",
            "at": ISODate("2024-05-30T14:00:52+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-05-30T14:02:52+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 155,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 81,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 253,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-05-30T14:04:52+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.10891662374490660454",
            "modality": "OP",
            "accession": "ACC-005358",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0053-01",
            "status": "final",
            "performer": "Dr. Touimi",
            "imaging_ref": "img-V-P2-0053-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2024-05-30T14:05:52+01:00"),
            "issued_at": ISODate("2024-05-30T14:35:52+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0053-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2024-05-30T13:50:52+01:00"),
            "requester": "Dr. Touimi"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00005",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-05-30T13:50:52+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0053",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0053-01"
      },
      {
        "audit_id": "AUD-00006",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0053",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0054",
    "last_name": "Tazi",
    "first_name": "Salma",
    "sex": 2,
    "birth_date": "1963-11-20",
    "national_id": "F112233",
    "phone": "+212655443322",
    "address": {
      "street": "15 Av des FAR",
      "city": "Casablanca"
    },
    "blood_type": "AB+",
    "allergies": [],
    "consent": {
      "status": "refused",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-08-06"
    },
    "visits": [
      {
        "visit_id": "V-P2-0054-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-MERNISSI",
        "physician": "Dr. Mernissi",
        "admitted_at": ISODate("2026-08-19T04:05:15+01:00"),
        "discharged_at": ISODate("2026-08-19T06:05:15+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 23,
            "unit": "mm[Hg]",
            "at": ISODate("2026-08-19T04:15:15+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2026-08-19T04:15:15+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-08-19T04:17:15+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 151,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 87,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.35224571169102446385",
            "modality": "OP",
            "accession": "ACC-005422",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0054-01",
            "status": "final",
            "performer": "Dr. Mernissi",
            "imaging_ref": "img-V-P2-0054-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2026-08-19T04:25:15+01:00"),
            "issued_at": ISODate("2026-08-19T04:55:15+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0054-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2026-08-19T04:05:15+01:00"),
            "requester": "Dr. Mernissi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0054-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2026-08-19T04:35:15+01:00"),
            "performer": "Dr. Mernissi",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00007",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-08-19T04:05:15+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0054",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0054-01"
      },
      {
        "audit_id": "AUD-00008",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0054",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0055",
    "last_name": "Berrada",
    "first_name": "Karim",
    "sex": 1,
    "birth_date": "1944-03-05",
    "national_id": "G554321",
    "phone": "+212688776655",
    "address": {
      "street": "9 Rue Ibnou Rachiq",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-07-08"
    },
    "visits": [
      {
        "visit_id": "V-P2-0055-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BELGHITI",
        "physician": "Dr. Belghiti",
        "admitted_at": ISODate("2025-07-21T01:55:46+01:00"),
        "discharged_at": ISODate("2025-07-21T10:55:46+01:00"),
        "reason": "Post-operative follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-07-21T02:07:46+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 121,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 76,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0055-01",
            "status": "final",
            "performer": "Dr. Belghiti",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-07-21T02:55:46+01:00"),
            "issued_at": ISODate("2025-07-21T03:55:46+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0055-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-07-21T02:55:46+01:00"),
            "performer": "Dr. Belghiti",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00009",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-07-21T01:55:46+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0055",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0055-01"
      },
      {
        "audit_id": "AUD-00010",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0055",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0056",
    "last_name": "Ouazzani",
    "first_name": "Rachid",
    "sex": 1,
    "birth_date": "1958-06-14",
    "national_id": null,
    "phone": "+212621345678",
    "address": {
      "street": "21 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-04-15"
    },
    "visits": [
      {
        "visit_id": "V-P2-0056-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-TOUIMI",
        "physician": "Dr. Touimi",
        "admitted_at": ISODate("2024-04-21T06:04:42+01:00"),
        "discharged_at": ISODate("2024-04-21T07:04:42+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 14,
            "unit": "mm[Hg]",
            "at": ISODate("2024-04-21T06:14:42+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 13,
            "unit": "mm[Hg]",
            "at": ISODate("2024-04-21T06:14:42+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-04-21T06:16:42+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 144,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 92,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 194,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-04-21T06:18:42+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.29720653539184697796",
            "modality": "OP",
            "accession": "ACC-005697",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0056-01",
            "status": "final",
            "performer": "Dr. Touimi",
            "imaging_ref": "img-V-P2-0056-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2024-04-21T06:19:42+01:00"),
            "issued_at": ISODate("2024-04-21T06:49:42+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0056-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2024-04-21T06:04:42+01:00"),
            "requester": "Dr. Touimi"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00011",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-04-21T06:04:42+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0056",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0056-01"
      },
      {
        "audit_id": "AUD-00012",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0056",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0057",
    "last_name": "El Fassi",
    "first_name": "Youcef",
    "sex": 1,
    "birth_date": "1971-02-28",
    "national_id": "H223344",
    "phone": "+212698001122",
    "address": {
      "street": "5 Rue Allal Ben Abdellah",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-02-01"
    },
    "visits": [
      {
        "visit_id": "V-P2-0057-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2024-02-20T04:47:01+01:00"),
        "discharged_at": ISODate("2024-02-20T06:47:01+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2024-02-20T04:57:01+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2024-02-20T04:57:01+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-02-20T04:59:01+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 136,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 90,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.68430941558330798447",
            "modality": "OP",
            "accession": "ACC-005760",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0057-01",
            "status": "final",
            "performer": "Dr. Benchekroun",
            "imaging_ref": "img-V-P2-0057-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-02-20T05:07:01+01:00"),
            "issued_at": ISODate("2024-02-20T05:37:01+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0057-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-02-20T04:47:01+01:00"),
            "requester": "Dr. Benchekroun"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0057-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-02-20T05:17:01+01:00"),
            "performer": "Dr. Benchekroun",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00013",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-02-20T04:47:01+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0057",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0057-01"
      },
      {
        "audit_id": "AUD-00014",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0057",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0058",
    "last_name": "Amrani",
    "first_name": "Khadija",
    "sex": 2,
    "birth_date": "1965-08-19",
    "national_id": "J445566",
    "phone": "+212614223344",
    "address": {
      "street": "30 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0058-01",
        "substance": "Tetracaine",
        "snomed_substance": "372697009",
        "reaction": "Contact dermatitis",
        "snomed_reaction": "238567008",
        "criticite": "MOYENNE",
        "date": "2013-12-18",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-04-08"
    },
    "visits": [
      {
        "visit_id": "V-P2-0058-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-MANSOURI",
        "physician": "Dr. Mansouri",
        "admitted_at": ISODate("2026-04-17T14:31:47+01:00"),
        "discharged_at": ISODate("2026-04-17T16:31:47+01:00"),
        "reason": "Red eye",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H16.9",
            "label": "Keratitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 20,
            "unit": "mm[Hg]",
            "at": ISODate("2026-04-17T14:41:47+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2026-04-17T14:41:47+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-04-17T14:43:47+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 128,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 82,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 103,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2026-04-17T14:45:47+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00015",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-04-17T14:31:47+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0058",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0058-01"
      },
      {
        "audit_id": "AUD-00016",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0058",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0059",
    "last_name": "Mekouar",
    "first_name": "Imane",
    "sex": 2,
    "birth_date": "13/05/1990",
    "national_id": "L667788",
    "phone": "+212677112233",
    "address": {
      "street": "4 Rue Colbert",
      "city": "Casablanca"
    },
    "blood_type": "O-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-05-03"
    },
    "visits": [
      {
        "visit_id": "V-P2-0059-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-LAMRANI",
        "physician": "Dr. Lamrani",
        "admitted_at": ISODate("2024-05-21T13:20:54+01:00"),
        "discharged_at": ISODate("2024-05-21T18:20:54+01:00"),
        "reason": "Post-LASIK follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-05-21T13:32:54+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 114,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 75,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0059-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2024-05-21T14:05:54+01:00"),
            "performer": "Dr. Lamrani",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00017",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-05-21T13:20:54+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0059",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0059-01"
      },
      {
        "audit_id": "AUD-00018",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0059",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0060",
    "last_name": "Squalli",
    "first_name": "Hamza",
    "sex": 1,
    "birth_date": "1987-09-11",
    "national_id": "N889900",
    "phone": "+212632009988",
    "address": {
      "street": "17 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-08-06"
    },
    "visits": [
      {
        "visit_id": "V-P2-0060-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-TOUIMI",
        "physician": "Dr. Touimi",
        "admitted_at": ISODate("2025-08-21T01:09:54+01:00"),
        "discharged_at": ISODate("2025-08-21T03:09:54+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2025-08-21T01:19:54+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2025-08-21T01:19:54+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-08-21T01:21:54+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 138,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 247,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-08-21T01:23:54+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.95346827011211737529",
            "modality": "OP",
            "accession": "ACC-006078",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0060-01",
            "status": "final",
            "performer": "Dr. Touimi",
            "imaging_ref": "img-V-P2-0060-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-08-21T01:24:54+01:00"),
            "issued_at": ISODate("2025-08-21T01:54:54+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0060-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-08-21T01:09:54+01:00"),
            "requester": "Dr. Touimi"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00019",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-08-21T01:09:54+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0060",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0060-01"
      },
      {
        "audit_id": "AUD-00020",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0060",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  }

]);
db.patients.insertMany([

  {
    "patient_id": "P2-0001",
    "last_name": "Cherkaoui",
    "first_name": "Zakaria",
    "sex": 1,
    "birth_date": "1962-03-30",
    "national_id": "ZZ376183",
    "phone": "+212667187530",
    "address": {
      "street": "98 Av des FAR",
      "city": "Casablanca"
    },
    "blood_type": "A-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-08-09"
    },
    "visits": [
      {
        "visit_id": "V-P2-0001-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENJELLOUN",
        "physician": "Dr. Benjelloun",
        "admitted_at": ISODate("2024-08-25T18:15:39+01:00"),
        "discharged_at": ISODate("2024-08-25T20:15:39+01:00"),
        "reason": "Glaucoma monitoring",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 30,
            "unit": "mm[Hg]",
            "at": ISODate("2024-08-25T18:25:39+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 28,
            "unit": "mm[Hg]",
            "at": ISODate("2024-08-25T18:25:39+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-08-25T18:27:39+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 159,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.62319856096019771060",
            "modality": "OP",
            "accession": "ACC-000112",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0001-01",
            "status": "final",
            "performer": "Dr. Benjelloun",
            "imaging_ref": "img-V-P2-0001-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-08-25T18:35:39+01:00"),
            "issued_at": ISODate("2024-08-25T19:05:39+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0001-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-08-25T18:15:39+01:00"),
            "requester": "Dr. Benjelloun"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0001-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-08-25T18:45:39+01:00"),
            "performer": "Dr. Benjelloun",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00021",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-08-25T18:15:39+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0001",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0001-01"
      },
      {
        "audit_id": "AUD-00022",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0001",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0002",
    "last_name": "El Fassi",
    "first_name": "Ghita",
    "sex": 2,
    "birth_date": "1955-05-08",
    "national_id": "CZ609597",
    "phone": "+212609289546",
    "address": {
      "street": "98 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-01-31"
    },
    "visits": [
      {
        "visit_id": "V-P2-0002-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-MERNISSI",
        "physician": "Dr. Mernissi",
        "admitted_at": ISODate("2025-02-16T02:01:38+01:00"),
        "discharged_at": ISODate("2025-02-16T04:01:38+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 30,
            "unit": "mm[Hg]",
            "at": ISODate("2025-02-16T02:11:38+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 28,
            "unit": "mm[Hg]",
            "at": ISODate("2025-02-16T02:11:38+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-02-16T02:13:38+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 153,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 86,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.62090382930256319206",
            "modality": "OP",
            "accession": "ACC-000295",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0002-01",
            "status": "final",
            "performer": "Dr. Mernissi",
            "imaging_ref": "img-V-P2-0002-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-02-16T02:21:38+01:00"),
            "issued_at": ISODate("2025-02-16T02:51:38+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0002-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-02-16T02:01:38+01:00"),
            "requester": "Dr. Mernissi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0002-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-02-16T02:31:38+01:00"),
            "performer": "Dr. Mernissi",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00023",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-02-16T02:01:38+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0002",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0002-01"
      },
      {
        "audit_id": "AUD-00024",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0002",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0003",
    "last_name": "Tahiri",
    "first_name": "Oumaima",
    "sex": 2,
    "birth_date": "1977-04-30",
    "national_id": "LA716886",
    "phone": "+212674346088",
    "address": {
      "street": "30 Rue Colbert",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0003-01",
        "substance": "Sulfonamides",
        "snomed_substance": "387406002",
        "reaction": "Urticaria",
        "snomed_reaction": "126485001",
        "criticite": "FAIBLE",
        "date": "2010-04-03",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-05-08"
    },
    "visits": [
      {
        "visit_id": "V-P2-0003-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-TOUIMI",
        "physician": "Dr. Touimi",
        "admitted_at": ISODate("2025-05-28T15:16:01+01:00"),
        "discharged_at": ISODate("2025-05-28T16:16:01+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-28T15:26:01+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-28T15:26:01+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-05-28T15:28:01+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 145,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 86,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.95674443147221351475",
            "modality": "OP",
            "accession": "ACC-000383",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0003-01",
            "status": "final",
            "performer": "Dr. Touimi",
            "imaging_ref": "img-V-P2-0003-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-05-28T15:36:01+01:00"),
            "issued_at": ISODate("2025-05-28T16:06:01+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0003-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-05-28T15:16:01+01:00"),
            "requester": "Dr. Touimi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0003-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-05-28T15:46:01+01:00"),
            "performer": "Dr. Touimi",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00025",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-05-28T15:16:01+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0003",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0003-01"
      },
      {
        "audit_id": "AUD-00026",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0003",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0004",
    "last_name": "Boutaleb",
    "first_name": "Ayman",
    "sex": 1,
    "birth_date": "1985-05-17",
    "national_id": "XP471507",
    "phone": "+212656851760",
    "address": {
      "street": "53 Rue Oum Errabia",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-03-22"
    },
    "visits": [
      {
        "visit_id": "V-P2-0004-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-ZERHOUNI",
        "physician": "Dr. Zerhouni",
        "admitted_at": ISODate("2024-04-04T11:48:15+01:00"),
        "discharged_at": ISODate("2024-04-04T13:48:15+01:00"),
        "reason": "Glaucoma monitoring",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 23,
            "unit": "mm[Hg]",
            "at": ISODate("2024-04-04T11:58:15+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 23,
            "unit": "mm[Hg]",
            "at": ISODate("2024-04-04T11:58:15+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-04-04T12:00:15+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 136,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 86,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.27722203486177068516",
            "modality": "OP",
            "accession": "ACC-000464",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0004-01",
            "status": "final",
            "performer": "Dr. Zerhouni",
            "imaging_ref": "img-V-P2-0004-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-04-04T12:08:15+01:00"),
            "issued_at": ISODate("2024-04-04T12:38:15+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0004-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-04-04T11:48:15+01:00"),
            "requester": "Dr. Zerhouni"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0004-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-04-04T12:18:15+01:00"),
            "performer": "Dr. Zerhouni",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00027",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-04-04T11:48:15+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0004",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0004-01"
      },
      {
        "audit_id": "AUD-00028",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0004",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0005",
    "last_name": "Naciri",
    "first_name": "Ghita",
    "sex": 2,
    "birth_date": "1984-01-04",
    "national_id": "DB783823",
    "phone": "+212672556484",
    "address": {
      "street": "2 Bd Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-11-17"
    },
    "visits": [
      {
        "visit_id": "V-P2-0005-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-FASSI_FIHRI",
        "physician": "Dr. Fassi-Fihri",
        "admitted_at": ISODate("2024-11-28T09:04:36+01:00"),
        "discharged_at": ISODate("2024-11-29T01:04:36+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-11-28T09:16:36+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 115,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 82,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0005-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2024-11-28T09:49:36+01:00"),
            "performer": "Dr. Fassi-Fihri",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0005-02",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENSOUDA",
        "physician": "Dr. Bensouda",
        "admitted_at": ISODate("2025-12-08T03:56:29+01:00"),
        "discharged_at": ISODate("2025-12-08T16:56:29+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-12-08T04:08:29+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 127,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 85,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0005-02",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2025-12-08T04:41:29+01:00"),
            "performer": "Dr. Bensouda",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00029",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-11-28T09:04:36+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0005",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0005-01"
      },
      {
        "audit_id": "AUD-00030",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0005",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0006",
    "last_name": "El Fassi",
    "first_name": "Houda",
    "sex": 2,
    "birth_date": "1957-04-29",
    "national_id": "ZL159942",
    "phone": "+212606729990",
    "address": {
      "street": "75 Rue Oum Errabia",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-10-10"
    },
    "visits": [
      {
        "visit_id": "V-P2-0006-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2024-10-16T00:03:24+01:00"),
        "discharged_at": ISODate("2024-10-16T01:03:24+01:00"),
        "reason": "Red eye",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H16.9",
            "label": "Keratitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 12,
            "unit": "mm[Hg]",
            "at": ISODate("2024-10-16T00:13:24+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 14,
            "unit": "mm[Hg]",
            "at": ISODate("2024-10-16T00:13:24+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-10-16T00:15:24+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 122,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 73,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 140,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-10-16T00:17:24+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00031",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-10-16T00:03:24+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0006",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0006-01"
      },
      {
        "audit_id": "AUD-00032",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0006",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0007",
    "last_name": "Lyazidi",
    "first_name": "Badr",
    "sex": 1,
    "birth_date": "1966-03-06",
    "national_id": "YL350280",
    "phone": "+212635650176",
    "address": {
      "street": "51 Av des FAR",
      "city": "Casablanca"
    },
    "blood_type": "AB+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-01-02"
    },
    "visits": [
      {
        "visit_id": "V-P2-0007-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-MRABET",
        "physician": "Dr. Mrabet",
        "admitted_at": ISODate("2024-01-15T19:18:19+01:00"),
        "discharged_at": ISODate("2024-01-16T13:18:19+01:00"),
        "reason": "Post-operative follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-01-15T19:30:19+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 112,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 76,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0007-01",
            "status": "final",
            "performer": "Dr. Mrabet",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-01-15T20:18:19+01:00"),
            "issued_at": ISODate("2024-01-15T21:18:19+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0007-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-01-15T20:18:19+01:00"),
            "performer": "Dr. Mrabet",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00033",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-01-15T19:18:19+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0007",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0007-01"
      },
      {
        "audit_id": "AUD-00034",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0007",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0008",
    "last_name": "Amrani",
    "first_name": "Walid",
    "sex": 1,
    "birth_date": "1968-08-21",
    "national_id": "FQ974244",
    "phone": "+212672909480",
    "address": {
      "street": "91 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-05-23"
    },
    "visits": [
      {
        "visit_id": "V-P2-0008-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-ZERHOUNI",
        "physician": "Dr. Zerhouni",
        "admitted_at": ISODate("2024-06-10T05:59:04+01:00"),
        "discharged_at": ISODate("2024-06-10T06:59:04+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 23,
            "unit": "mm[Hg]",
            "at": ISODate("2024-06-10T06:09:04+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2024-06-10T06:09:04+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-06-10T06:11:04+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 153,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.79984462159591283929",
            "modality": "OP",
            "accession": "ACC-000836",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0008-01",
            "status": "final",
            "performer": "Dr. Zerhouni",
            "imaging_ref": "img-V-P2-0008-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-06-10T06:19:04+01:00"),
            "issued_at": ISODate("2024-06-10T06:49:04+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0008-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-06-10T05:59:04+01:00"),
            "requester": "Dr. Zerhouni"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0008-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-06-10T06:29:04+01:00"),
            "performer": "Dr. Zerhouni",
            "body_site": null
          }
        ]
      },
      {
        "visit_id": "V-P2-0008-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BARGACH",
        "physician": "Dr. Bargach",
        "admitted_at": ISODate("2026-09-12T14:06:17+01:00"),
        "discharged_at": ISODate("2026-09-13T02:06:17+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-09-12T14:18:17+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 118,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 71,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0008-02",
            "status": "final",
            "performer": "Dr. Bargach",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2026-09-12T15:06:17+01:00"),
            "issued_at": ISODate("2026-09-12T16:06:17+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0008-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2026-09-12T15:06:17+01:00"),
            "performer": "Dr. Bargach",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00035",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-06-10T05:59:04+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0008",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0008-01"
      },
      {
        "audit_id": "AUD-00036",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0008",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0009",
    "last_name": "Alaoui",
    "first_name": "Salma",
    "sex": 2,
    "birth_date": "1947-06-03",
    "national_id": "WJ269430",
    "phone": "+212699486328",
    "address": {
      "street": "57 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0009-01",
        "substance": "Fluorescein sodium",
        "snomed_substance": "372639009",
        "reaction": "Urticaria",
        "snomed_reaction": "126485001",
        "criticite": "ELEVEE",
        "date": "2024-12-05",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-07-13"
    },
    "visits": [
      {
        "visit_id": "V-P2-0009-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-LAMRANI",
        "physician": "Dr. Lamrani",
        "admitted_at": ISODate("2025-07-27T21:22:10+01:00"),
        "discharged_at": ISODate("2025-07-28T19:22:10+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-07-27T21:34:10+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 123,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 74,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0009-01",
            "status": "final",
            "performer": "Dr. Lamrani",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-07-27T22:22:10+01:00"),
            "issued_at": ISODate("2025-07-27T23:22:10+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0009-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-07-27T22:22:10+01:00"),
            "performer": "Dr. Lamrani",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00037",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-07-27T21:22:10+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0009",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0009-01"
      },
      {
        "audit_id": "AUD-00038",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0009",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0010",
    "last_name": "Benomar",
    "first_name": "Salma",
    "sex": 2,
    "birth_date": "1977-03-05",
    "national_id": "DM918011",
    "phone": "+212675146293",
    "address": {
      "street": "53 Rue Colbert",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-09-20"
    },
    "visits": [
      {
        "visit_id": "V-P2-0010-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BOUAYAD",
        "physician": "Dr. Bouayad",
        "admitted_at": ISODate("2024-10-02T08:59:26+01:00"),
        "discharged_at": ISODate("2024-10-02T10:59:26+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2024-10-02T09:09:26+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2024-10-02T09:09:26+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-10-02T09:11:26+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 159,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 90,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.73510754636234914600",
            "modality": "OP",
            "accession": "ACC-001095",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0010-01",
            "status": "final",
            "performer": "Dr. Bouayad",
            "imaging_ref": "img-V-P2-0010-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-10-02T09:19:26+01:00"),
            "issued_at": ISODate("2024-10-02T09:49:26+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0010-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-10-02T08:59:26+01:00"),
            "requester": "Dr. Bouayad"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0010-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-10-02T09:29:26+01:00"),
            "performer": "Dr. Bouayad",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00039",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-10-02T08:59:26+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0010",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0010-01"
      },
      {
        "audit_id": "AUD-00040",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0010",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  }

]);
db.patients.insertMany([

  {
    "patient_id": "P2-0011",
    "last_name": "Zniber",
    "first_name": "Meriem",
    "sex": 2,
    "birth_date": "1981-04-17",
    "national_id": "RH309267",
    "phone": "+212661780854",
    "address": {
      "street": "45 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0011-01",
        "substance": "Tetracaine",
        "snomed_substance": "372697009",
        "reaction": "Contact dermatitis",
        "snomed_reaction": "238567008",
        "criticite": "MOYENNE",
        "date": "2016-06-09",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-03-01"
    },
    "visits": [
      {
        "visit_id": "V-P2-0011-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BELGHITI",
        "physician": "Dr. Belghiti",
        "admitted_at": ISODate("2025-03-09T22:32:02+01:00"),
        "discharged_at": ISODate("2025-03-10T13:32:02+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-03-09T22:44:02+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 127,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0011-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2025-03-09T23:17:02+01:00"),
            "performer": "Dr. Belghiti",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00041",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-03-09T22:32:02+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0011",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0011-01"
      },
      {
        "audit_id": "AUD-00042",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0011",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0012",
    "last_name": "Bennis",
    "first_name": "Siham",
    "sex": 2,
    "birth_date": "1986-01-28",
    "national_id": "PM863934",
    "phone": "+212642101056",
    "address": {
      "street": "56 Rue Colbert",
      "city": "Casablanca"
    },
    "blood_type": "A-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-01-23"
    },
    "visits": [
      {
        "visit_id": "V-P2-0012-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-OULKADI",
        "physician": "Dr. Oulkadi",
        "admitted_at": ISODate("2025-01-31T00:44:36+01:00"),
        "discharged_at": ISODate("2025-01-31T01:44:36+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-31T00:54:36+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 11,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-31T00:54:36+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-01-31T00:56:36+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 146,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 86,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 206,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-01-31T00:58:36+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.54878712461549075220",
            "modality": "OP",
            "accession": "ACC-001289",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0012-01",
            "status": "final",
            "performer": "Dr. Oulkadi",
            "imaging_ref": "img-V-P2-0012-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-01-31T00:59:36+01:00"),
            "issued_at": ISODate("2025-01-31T01:29:36+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0012-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-01-31T00:44:36+01:00"),
            "requester": "Dr. Oulkadi"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00043",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-01-31T00:44:36+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0012",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0012-01"
      },
      {
        "audit_id": "AUD-00044",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0012",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0013",
    "last_name": "Boutaleb",
    "first_name": "Wafae",
    "sex": 2,
    "birth_date": "1960-03-19",
    "national_id": "KT233470",
    "phone": "+212625748341",
    "address": {
      "street": "54 Av Lalla Yacout",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-07-31"
    },
    "visits": [
      {
        "visit_id": "V-P2-0013-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-ZERHOUNI",
        "physician": "Dr. Zerhouni",
        "admitted_at": ISODate("2026-08-14T12:03:33+01:00"),
        "discharged_at": ISODate("2026-08-15T10:03:33+01:00"),
        "reason": "Pre-operative assessment",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-08-14T12:15:33+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 122,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 70,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0013-01",
            "status": "final",
            "performer": "Dr. Zerhouni",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2026-08-14T13:03:33+01:00"),
            "issued_at": ISODate("2026-08-14T14:03:33+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0013-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2026-08-14T13:03:33+01:00"),
            "performer": "Dr. Zerhouni",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00045",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-08-14T12:03:33+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0013",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0013-01"
      },
      {
        "audit_id": "AUD-00046",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0013",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0014",
    "last_name": "Benjelloun",
    "first_name": "Rayan",
    "sex": 1,
    "birth_date": "1994-11-10",
    "national_id": "XG636004",
    "phone": "+212663509974",
    "address": {
      "street": "95 Av des FAR",
      "city": "Casablanca"
    },
    "blood_type": "A-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-05-16"
    },
    "visits": [
      {
        "visit_id": "V-P2-0014-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-MANSOURI",
        "physician": "Dr. Mansouri",
        "admitted_at": ISODate("2024-05-25T09:43:37+01:00"),
        "discharged_at": ISODate("2024-05-25T20:43:37+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-05-25T09:55:37+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 117,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 76,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0014-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2024-05-25T10:28:37+01:00"),
            "performer": "Dr. Mansouri",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0014-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2025-01-15T16:23:29+01:00"),
        "discharged_at": ISODate("2025-01-15T18:23:29+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 12,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-15T16:33:29+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-15T16:33:29+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-01-15T16:35:29+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 143,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 86,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 251,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-01-15T16:37:29+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.63423384768471385511",
            "modality": "OP",
            "accession": "ACC-001461",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0014-02",
            "status": "final",
            "performer": "Dr. Benchekroun",
            "imaging_ref": "img-V-P2-0014-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-01-15T16:38:29+01:00"),
            "issued_at": ISODate("2025-01-15T17:08:29+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0014-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-01-15T16:23:29+01:00"),
            "requester": "Dr. Benchekroun"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00047",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-05-25T09:43:37+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0014",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0014-01"
      },
      {
        "audit_id": "AUD-00048",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0014",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0015",
    "last_name": "Benbrahim",
    "first_name": "Adil",
    "sex": 1,
    "birth_date": "1981-03-20",
    "national_id": "SQ152657",
    "phone": "+212674813739",
    "address": {
      "street": "32 Bd Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "O-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-11-09"
    },
    "visits": [
      {
        "visit_id": "V-P2-0015-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-MERNISSI",
        "physician": "Dr. Mernissi",
        "admitted_at": ISODate("2025-11-18T20:19:59+01:00"),
        "discharged_at": ISODate("2025-11-18T22:19:59+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2025-11-18T20:29:59+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2025-11-18T20:29:59+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-11-18T20:31:59+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 157,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 95,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.61405661052706961305",
            "modality": "OP",
            "accession": "ACC-001519",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0015-01",
            "status": "final",
            "performer": "Dr. Mernissi",
            "imaging_ref": "img-V-P2-0015-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-11-18T20:39:59+01:00"),
            "issued_at": ISODate("2025-11-18T21:09:59+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0015-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-11-18T20:19:59+01:00"),
            "requester": "Dr. Mernissi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0015-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-11-18T20:49:59+01:00"),
            "performer": "Dr. Mernissi",
            "body_site": null
          }
        ]
      },
      {
        "visit_id": "V-P2-0015-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BELGHITI",
        "physician": "Dr. Belghiti",
        "admitted_at": ISODate("2025-02-26T10:16:24+01:00"),
        "discharged_at": ISODate("2025-02-27T00:16:24+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-02-26T10:28:24+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 127,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 72,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0015-02",
            "status": "final",
            "performer": "Dr. Belghiti",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-02-26T11:16:24+01:00"),
            "issued_at": ISODate("2025-02-26T12:16:24+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0015-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-02-26T11:16:24+01:00"),
            "performer": "Dr. Belghiti",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00049",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-11-18T20:19:59+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0015",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0015-01"
      },
      {
        "audit_id": "AUD-00050",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0015",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0016",
    "last_name": "Fassi-Fihri",
    "first_name": "Ismail",
    "sex": 1,
    "birth_date": "1987-10-27",
    "national_id": "PL668969",
    "phone": "+212662535301",
    "address": {
      "street": "54 Rue Mohammed V",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-06-01"
    },
    "visits": [
      {
        "visit_id": "V-P2-0016-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-LYAZIDI",
        "physician": "Dr. Lyazidi",
        "admitted_at": ISODate("2026-06-13T15:17:30+01:00"),
        "discharged_at": ISODate("2026-06-13T17:17:30+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2026-06-13T15:27:30+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2026-06-13T15:27:30+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-06-13T15:29:30+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 139,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 92,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.82516554642399580275",
            "modality": "OP",
            "accession": "ACC-001679",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0016-01",
            "status": "final",
            "performer": "Dr. Lyazidi",
            "imaging_ref": "img-V-P2-0016-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2026-06-13T15:37:30+01:00"),
            "issued_at": ISODate("2026-06-13T16:07:30+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0016-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2026-06-13T15:17:30+01:00"),
            "requester": "Dr. Lyazidi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0016-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2026-06-13T15:47:30+01:00"),
            "performer": "Dr. Lyazidi",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00051",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-06-13T15:17:30+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0016",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0016-01"
      },
      {
        "audit_id": "AUD-00052",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0016",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0017",
    "last_name": "Boulahia",
    "first_name": "Btissam",
    "sex": 2,
    "birth_date": "1993-04-12",
    "national_id": "NL801364",
    "phone": "+212691152880",
    "address": {
      "street": "52 Rue Allal Ben Abdellah",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-08-06"
    },
    "visits": [
      {
        "visit_id": "V-P2-0017-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-LYAZIDI",
        "physician": "Dr. Lyazidi",
        "admitted_at": ISODate("2026-08-24T23:25:15+01:00"),
        "discharged_at": ISODate("2026-08-25T20:25:15+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-08-24T23:37:15+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 122,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 70,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0017-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2026-08-25T00:10:15+01:00"),
            "performer": "Dr. Lyazidi",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00053",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-08-24T23:25:15+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0017",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0017-01"
      },
      {
        "audit_id": "AUD-00054",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0017",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0018",
    "last_name": "Oulkadi",
    "first_name": "Imad",
    "sex": 1,
    "birth_date": "1975-10-09",
    "national_id": "LG576786",
    "phone": "+212643868501",
    "address": {
      "street": "44 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "AB+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-01-14"
    },
    "visits": [
      {
        "visit_id": "V-P2-0018-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENABBOU",
        "physician": "Dr. Benabbou",
        "admitted_at": ISODate("2025-01-27T05:21:51+01:00"),
        "discharged_at": ISODate("2025-01-27T06:21:51+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 11,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-27T05:31:51+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-27T05:31:51+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-01-27T05:33:51+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 131,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 91,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 188,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-01-27T05:35:51+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.13022751335596206931",
            "modality": "OP",
            "accession": "ACC-001813",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0018-01",
            "status": "final",
            "performer": "Dr. Benabbou",
            "imaging_ref": "img-V-P2-0018-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-01-27T05:36:51+01:00"),
            "issued_at": ISODate("2025-01-27T06:06:51+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0018-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-01-27T05:21:51+01:00"),
            "requester": "Dr. Benabbou"
          }
        ],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0018-02",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-LYAZIDI",
        "physician": "Dr. Lyazidi",
        "admitted_at": ISODate("2024-02-01T23:49:19+01:00"),
        "discharged_at": ISODate("2024-02-02T00:49:19+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2024-02-01T23:59:19+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 25,
            "unit": "mm[Hg]",
            "at": ISODate("2024-02-01T23:59:19+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-02-02T00:01:19+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 151,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 83,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.36929775386440781666",
            "modality": "OP",
            "accession": "ACC-001869",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0018-02",
            "status": "final",
            "performer": "Dr. Lyazidi",
            "imaging_ref": "img-V-P2-0018-02",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-02-02T00:09:19+01:00"),
            "issued_at": ISODate("2024-02-02T00:39:19+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0018-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-02-01T23:49:19+01:00"),
            "requester": "Dr. Lyazidi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0018-02",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-02-02T00:19:19+01:00"),
            "performer": "Dr. Lyazidi",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00055",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-01-27T05:21:51+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0018",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0018-01"
      },
      {
        "audit_id": "AUD-00056",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0018",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0019",
    "last_name": "Squalli",
    "first_name": "Meriem",
    "sex": 2,
    "birth_date": "1972-05-23",
    "national_id": "UA427110",
    "phone": "+212677282128",
    "address": {
      "street": "87 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0019-01",
        "substance": "Betaxolol",
        "snomed_substance": "372512008",
        "reaction": "Bradycardia",
        "snomed_reaction": "48867003",
        "criticite": "MOYENNE",
        "date": "2021-11-08",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-03-28"
    },
    "visits": [
      {
        "visit_id": "V-P2-0019-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-JAIDI",
        "physician": "Dr. Jaidi",
        "admitted_at": ISODate("2025-04-13T19:49:02+01:00"),
        "discharged_at": ISODate("2025-04-13T20:49:02+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2025-04-13T19:59:02+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2025-04-13T19:59:02+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-04-13T20:01:02+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 143,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 91,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.71509560197005506621",
            "modality": "OP",
            "accession": "ACC-001923",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0019-01",
            "status": "final",
            "performer": "Dr. Jaidi",
            "imaging_ref": "img-V-P2-0019-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-04-13T20:09:02+01:00"),
            "issued_at": ISODate("2025-04-13T20:39:02+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0019-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-04-13T19:49:02+01:00"),
            "requester": "Dr. Jaidi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0019-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-04-13T20:19:02+01:00"),
            "performer": "Dr. Jaidi",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00057",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-04-13T19:49:02+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0019",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0019-01"
      },
      {
        "audit_id": "AUD-00058",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0019",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0020",
    "last_name": "Cherkaoui",
    "first_name": "Hasnae",
    "sex": 2,
    "birth_date": "1959-02-25",
    "national_id": "JV947458",
    "phone": "+212672232344",
    "address": {
      "street": "62 Rue Oum Errabia",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-05-04"
    },
    "visits": [
      {
        "visit_id": "V-P2-0020-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-LYAZIDI",
        "physician": "Dr. Lyazidi",
        "admitted_at": ISODate("2025-05-16T00:23:08+01:00"),
        "discharged_at": ISODate("2025-05-16T01:23:08+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-16T00:33:08+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 25,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-16T00:33:08+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-05-16T00:35:08+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 137,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 94,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.7205422425094844779",
            "modality": "OP",
            "accession": "ACC-002073",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0020-01",
            "status": "final",
            "performer": "Dr. Lyazidi",
            "imaging_ref": "img-V-P2-0020-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-05-16T00:43:08+01:00"),
            "issued_at": ISODate("2025-05-16T01:13:08+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0020-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-05-16T00:23:08+01:00"),
            "requester": "Dr. Lyazidi"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0020-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-05-16T00:53:08+01:00"),
            "performer": "Dr. Lyazidi",
            "body_site": null
          }
        ]
      },
      {
        "visit_id": "V-P2-0020-02",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENKIRANE",
        "physician": "Dr. Benkirane",
        "admitted_at": ISODate("2024-11-25T20:24:04+01:00"),
        "discharged_at": ISODate("2024-11-25T22:24:04+01:00"),
        "reason": "Glaucoma monitoring",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2024-11-25T20:34:04+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2024-11-25T20:34:04+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-11-25T20:36:04+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 158,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 88,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.74974231279283491363",
            "modality": "OP",
            "accession": "ACC-002034",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0020-02",
            "status": "final",
            "performer": "Dr. Benkirane",
            "imaging_ref": "img-V-P2-0020-02",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2024-11-25T20:44:04+01:00"),
            "issued_at": ISODate("2024-11-25T21:14:04+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0020-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2024-11-25T20:24:04+01:00"),
            "requester": "Dr. Benkirane"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0020-02",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2024-11-25T20:54:04+01:00"),
            "performer": "Dr. Benkirane",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00059",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-05-16T00:23:08+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0020",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0020-01"
      },
      {
        "audit_id": "AUD-00060",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0020",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  }

]);
db.patients.insertMany([

  {
    "patient_id": "P2-0021",
    "last_name": "Zaidane",
    "first_name": "Ikram",
    "sex": 2,
    "birth_date": "1988-12-05",
    "national_id": "QA197573",
    "phone": "+212639491631",
    "address": {
      "street": "29 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-12-28"
    },
    "visits": [
      {
        "visit_id": "V-P2-0021-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-MANSOURI",
        "physician": "Dr. Mansouri",
        "admitted_at": ISODate("2026-01-05T12:25:47+01:00"),
        "discharged_at": ISODate("2026-01-06T09:25:47+01:00"),
        "reason": "Pre-LASIK evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-01-05T12:37:47+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 123,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0021-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2026-01-05T13:10:47+01:00"),
            "performer": "Dr. Mansouri",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0021-02",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENSOUDA",
        "physician": "Dr. Bensouda",
        "admitted_at": ISODate("2025-04-21T15:44:01+01:00"),
        "discharged_at": ISODate("2025-04-22T03:44:01+01:00"),
        "reason": "Pre-LASIK evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-04-21T15:56:01+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 113,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 76,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0021-02",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2025-04-21T16:29:01+01:00"),
            "performer": "Dr. Bensouda",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00061",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-01-05T12:25:47+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0021",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0021-01"
      },
      {
        "audit_id": "AUD-00062",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0021",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0022",
    "last_name": "Belghiti",
    "first_name": "Bilal",
    "sex": 1,
    "birth_date": "2001-01-24",
    "national_id": "SV396745",
    "phone": "+212613492385",
    "address": {
      "street": "25 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0022-01",
        "substance": "Fluorescein sodium",
        "snomed_substance": "372639009",
        "reaction": "Urticaria",
        "snomed_reaction": "126485001",
        "criticite": "ELEVEE",
        "date": "2021-09-05",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-02-24"
    },
    "visits": [
      {
        "visit_id": "V-P2-0022-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-RAHIMI",
        "physician": "Dr. Rahimi",
        "admitted_at": ISODate("2024-03-12T00:56:53+01:00"),
        "discharged_at": ISODate("2024-03-12T05:56:53+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-03-12T01:08:53+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 114,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 85,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0022-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2024-03-12T01:41:53+01:00"),
            "performer": "Dr. Rahimi",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0022-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-CHAOUI",
        "physician": "Dr. Chaoui",
        "admitted_at": ISODate("2025-03-18T00:56:18+01:00"),
        "discharged_at": ISODate("2025-03-18T02:56:18+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2025-03-18T01:06:18+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 16,
            "unit": "mm[Hg]",
            "at": ISODate("2025-03-18T01:06:18+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-03-18T01:08:18+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 135,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 81,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 192,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-03-18T01:10:18+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.72236215201973504827",
            "modality": "OP",
            "accession": "ACC-002224",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0022-02",
            "status": "final",
            "performer": "Dr. Chaoui",
            "imaging_ref": "img-V-P2-0022-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-03-18T01:11:18+01:00"),
            "issued_at": ISODate("2025-03-18T01:41:18+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0022-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-03-18T00:56:18+01:00"),
            "requester": "Dr. Chaoui"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00063",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-03-12T00:56:53+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0022",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0022-01"
      },
      {
        "audit_id": "AUD-00064",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0022",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0023",
    "last_name": "Ouazzani",
    "first_name": "Yasmine",
    "sex": 2,
    "birth_date": "1983-01-11",
    "national_id": "KC360247",
    "phone": "+212615898299",
    "address": {
      "street": "72 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-11-07"
    },
    "visits": [
      {
        "visit_id": "V-P2-0023-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENABBOU",
        "physician": "Dr. Benabbou",
        "admitted_at": ISODate("2025-11-19T01:50:07+01:00"),
        "discharged_at": ISODate("2025-11-19T03:50:07+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2025-11-19T02:00:07+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2025-11-19T02:00:07+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-11-19T02:02:07+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 149,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 81,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.30985459768717842061",
            "modality": "OP",
            "accession": "ACC-002343",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0023-01",
            "status": "final",
            "performer": "Dr. Benabbou",
            "imaging_ref": "img-V-P2-0023-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-11-19T02:10:07+01:00"),
            "issued_at": ISODate("2025-11-19T02:40:07+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0023-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-11-19T01:50:07+01:00"),
            "requester": "Dr. Benabbou"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0023-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-11-19T02:20:07+01:00"),
            "performer": "Dr. Benabbou",
            "body_site": null
          }
        ]
      },
      {
        "visit_id": "V-P2-0023-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-FASSI_FIHRI",
        "physician": "Dr. Fassi-Fihri",
        "admitted_at": ISODate("2025-01-07T22:49:19+01:00"),
        "discharged_at": ISODate("2025-01-07T23:49:19+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 12,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-07T22:59:19+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 13,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-07T22:59:19+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-01-07T23:01:19+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 130,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 93,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 217,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-01-07T23:03:19+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.67294115312569327718",
            "modality": "OP",
            "accession": "ACC-002347",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0023-02",
            "status": "final",
            "performer": "Dr. Fassi-Fihri",
            "imaging_ref": "img-V-P2-0023-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-01-07T23:04:19+01:00"),
            "issued_at": ISODate("2025-01-07T23:34:19+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0023-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-01-07T22:49:19+01:00"),
            "requester": "Dr. Fassi-Fihri"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00065",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-11-19T01:50:07+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0023",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0023-01"
      },
      {
        "audit_id": "AUD-00066",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0023",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0024",
    "last_name": "Errafii",
    "first_name": "Rajae",
    "sex": 2,
    "birth_date": "1977-08-11",
    "national_id": "WU793300",
    "phone": "+212626550845",
    "address": {
      "street": "55 Bd Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0024-01",
        "substance": "Atropine",
        "snomed_substance": "372819007",
        "reaction": "Tachycardia",
        "snomed_reaction": "3415004",
        "criticite": "MOYENNE",
        "date": "2023-03-03",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-08-26"
    },
    "visits": [
      {
        "visit_id": "V-P2-0024-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BOULAHIA",
        "physician": "Dr. Boulahia",
        "admitted_at": ISODate("2024-09-15T02:02:59+01:00"),
        "discharged_at": ISODate("2024-09-15T04:02:59+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 20,
            "unit": "mm[Hg]",
            "at": ISODate("2024-09-15T02:12:59+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 15,
            "unit": "mm[Hg]",
            "at": ISODate("2024-09-15T02:12:59+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-09-15T02:14:59+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 144,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 83,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 219,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-09-15T02:16:59+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.98843212663858738038",
            "modality": "OP",
            "accession": "ACC-002461",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0024-01",
            "status": "final",
            "performer": "Dr. Boulahia",
            "imaging_ref": "img-V-P2-0024-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2024-09-15T02:17:59+01:00"),
            "issued_at": ISODate("2024-09-15T02:47:59+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0024-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2024-09-15T02:02:59+01:00"),
            "requester": "Dr. Boulahia"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00067",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-09-15T02:02:59+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0024",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0024-01"
      },
      {
        "audit_id": "AUD-00068",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0024",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0025",
    "last_name": "Berrada",
    "first_name": "Imane",
    "sex": 2,
    "birth_date": "1985-09-10",
    "national_id": "VJ127121",
    "phone": "+212612257687",
    "address": {
      "street": "30 Av Lalla Yacout",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-05-27"
    },
    "visits": [
      {
        "visit_id": "V-P2-0025-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENABBOU",
        "physician": "Dr. Benabbou",
        "admitted_at": ISODate("2026-06-14T12:02:41+01:00"),
        "discharged_at": ISODate("2026-06-14T17:02:41+01:00"),
        "reason": "Pre-LASIK evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-06-14T12:14:41+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 125,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0025-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2026-06-14T12:47:41+01:00"),
            "performer": "Dr. Benabbou",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0025-02",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-CHAOUI",
        "physician": "Dr. Chaoui",
        "admitted_at": ISODate("2025-11-08T10:58:12+01:00"),
        "discharged_at": ISODate("2025-11-08T12:58:12+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 29,
            "unit": "mm[Hg]",
            "at": ISODate("2025-11-08T11:08:12+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2025-11-08T11:08:12+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-11-08T11:10:12+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 143,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 90,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.13361781418256293821",
            "modality": "OP",
            "accession": "ACC-002530",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0025-02",
            "status": "final",
            "performer": "Dr. Chaoui",
            "imaging_ref": "img-V-P2-0025-02",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-11-08T11:18:12+01:00"),
            "issued_at": ISODate("2025-11-08T11:48:12+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0025-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-11-08T10:58:12+01:00"),
            "requester": "Dr. Chaoui"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0025-02",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-11-08T11:28:12+01:00"),
            "performer": "Dr. Chaoui",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00069",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-06-14T12:02:41+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0025",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0025-01"
      },
      {
        "audit_id": "AUD-00070",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0025",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0026",
    "last_name": "Belkhadir",
    "first_name": "Rajae",
    "sex": 2,
    "birth_date": "1989-11-16",
    "national_id": "CL364659",
    "phone": "+212643389073",
    "address": {
      "street": "15 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-09-29"
    },
    "visits": [
      {
        "visit_id": "V-P2-0026-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-ZERHOUNI",
        "physician": "Dr. Zerhouni",
        "admitted_at": ISODate("2025-10-04T06:59:10+01:00"),
        "discharged_at": ISODate("2025-10-04T07:59:10+01:00"),
        "reason": "Annual check-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H10.9",
            "label": "Conjunctivitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2025-10-04T07:09:10+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 16,
            "unit": "mm[Hg]",
            "at": ISODate("2025-10-04T07:09:10+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-10-04T07:11:10+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 129,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 85,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 120,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-10-04T07:13:10+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0026-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BARGACH",
        "physician": "Dr. Bargach",
        "admitted_at": ISODate("2025-02-19T04:34:41+01:00"),
        "discharged_at": ISODate("2025-02-19T05:34:41+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2025-02-19T04:44:41+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2025-02-19T04:44:41+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-02-19T04:46:41+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 133,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 240,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-02-19T04:48:41+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.34191480001650688887",
            "modality": "OP",
            "accession": "ACC-002630",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0026-02",
            "status": "final",
            "performer": "Dr. Bargach",
            "imaging_ref": "img-V-P2-0026-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-02-19T04:49:41+01:00"),
            "issued_at": ISODate("2025-02-19T05:19:41+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0026-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-02-19T04:34:41+01:00"),
            "requester": "Dr. Bargach"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00071",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-10-04T06:59:10+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0026",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0026-01"
      },
      {
        "audit_id": "AUD-00072",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0026",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0027",
    "last_name": "Bargach",
    "first_name": "Imane",
    "sex": 2,
    "birth_date": "1962-05-28",
    "national_id": "WE622584",
    "phone": "+212696180870",
    "address": {
      "street": "38 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "AB+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-12-25"
    },
    "visits": [
      {
        "visit_id": "V-P2-0027-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENSLIMANE",
        "physician": "Dr. Benslimane",
        "admitted_at": ISODate("2025-01-13T22:56:48+01:00"),
        "discharged_at": ISODate("2025-01-14T00:56:48+01:00"),
        "reason": "Visual acuity decrease",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 13,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-13T23:06:48+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2025-01-13T23:06:48+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-01-13T23:08:48+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 136,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 270,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-01-13T23:10:48+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.72101358730083424345",
            "modality": "OP",
            "accession": "ACC-002753",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0027-01",
            "status": "final",
            "performer": "Dr. Benslimane",
            "imaging_ref": "img-V-P2-0027-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-01-13T23:11:48+01:00"),
            "issued_at": ISODate("2025-01-13T23:41:48+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0027-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-01-13T22:56:48+01:00"),
            "requester": "Dr. Benslimane"
          }
        ],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0027-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-LYAZIDI",
        "physician": "Dr. Lyazidi",
        "admitted_at": ISODate("2024-01-05T07:38:23+01:00"),
        "discharged_at": ISODate("2024-01-05T20:38:23+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-01-05T07:50:23+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 128,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 85,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0027-02",
            "status": "final",
            "performer": "Dr. Lyazidi",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-01-05T08:38:23+01:00"),
            "issued_at": ISODate("2024-01-05T09:38:23+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0027-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-01-05T08:38:23+01:00"),
            "performer": "Dr. Lyazidi",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00073",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-01-13T22:56:48+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0027",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0027-01"
      },
      {
        "audit_id": "AUD-00074",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0027",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0028",
    "last_name": "Belkadi",
    "first_name": "Loubna",
    "sex": 2,
    "birth_date": "1957-10-08",
    "national_id": "QL297816",
    "phone": "+212693616654",
    "address": {
      "street": "31 Rue Colbert",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-02-29"
    },
    "visits": [
      {
        "visit_id": "V-P2-0028-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-BELGHITI",
        "physician": "Dr. Belghiti",
        "admitted_at": ISODate("2024-03-09T03:17:21+01:00"),
        "discharged_at": ISODate("2024-03-09T05:17:21+01:00"),
        "reason": "Routine eye exam",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H16.9",
            "label": "Keratitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2024-03-09T03:27:21+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2024-03-09T03:27:21+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-03-09T03:29:21+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 122,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 74,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 111,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-03-09T03:31:21+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0028-02",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-ZAIDANE",
        "physician": "Dr. Zaidane",
        "admitted_at": ISODate("2026-07-06T03:31:16+01:00"),
        "discharged_at": ISODate("2026-07-06T05:31:16+01:00"),
        "reason": "Optic nerve evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 29,
            "unit": "mm[Hg]",
            "at": ISODate("2026-07-06T03:41:16+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2026-07-06T03:41:16+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-07-06T03:43:16+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 146,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 94,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.32773480461674598904",
            "modality": "OP",
            "accession": "ACC-002862",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0028-02",
            "status": "final",
            "performer": "Dr. Zaidane",
            "imaging_ref": "img-V-P2-0028-02",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2026-07-06T03:51:16+01:00"),
            "issued_at": ISODate("2026-07-06T04:21:16+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0028-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2026-07-06T03:31:16+01:00"),
            "requester": "Dr. Zaidane"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0028-02",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2026-07-06T04:01:16+01:00"),
            "performer": "Dr. Zaidane",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00075",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-03-09T03:17:21+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0028",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0028-01"
      },
      {
        "audit_id": "AUD-00076",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0028",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0029",
    "last_name": "Bennis",
    "first_name": "Ayman",
    "sex": 1,
    "birth_date": "1953-03-18",
    "national_id": "NW184216",
    "phone": "+212644099326",
    "address": {
      "street": "87 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-04-04"
    },
    "visits": [
      {
        "visit_id": "V-P2-0029-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-GHALI",
        "physician": "Dr. Ghali",
        "admitted_at": ISODate("2026-04-20T18:32:20+01:00"),
        "discharged_at": ISODate("2026-04-20T23:32:20+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-04-20T18:44:20+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 117,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 79,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0029-01",
            "status": "final",
            "performer": "Dr. Ghali",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2026-04-20T19:32:20+01:00"),
            "issued_at": ISODate("2026-04-20T20:32:20+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0029-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2026-04-20T19:32:20+01:00"),
            "performer": "Dr. Ghali",
            "body_site": "right eye"
          }
        ]
      },
      {
        "visit_id": "V-P2-0029-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENSLIMANE",
        "physician": "Dr. Benslimane",
        "admitted_at": ISODate("2024-06-02T06:13:32+01:00"),
        "discharged_at": ISODate("2024-06-02T07:13:32+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 13,
            "unit": "mm[Hg]",
            "at": ISODate("2024-06-02T06:23:32+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 15,
            "unit": "mm[Hg]",
            "at": ISODate("2024-06-02T06:23:32+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-06-02T06:25:32+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 158,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 165,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-06-02T06:27:32+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.15686254818793240543",
            "modality": "OP",
            "accession": "ACC-002947",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0029-02",
            "status": "final",
            "performer": "Dr. Benslimane",
            "imaging_ref": "img-V-P2-0029-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2024-06-02T06:28:32+01:00"),
            "issued_at": ISODate("2024-06-02T06:58:32+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0029-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2024-06-02T06:13:32+01:00"),
            "requester": "Dr. Benslimane"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00077",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-04-20T18:32:20+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0029",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0029-01"
      },
      {
        "audit_id": "AUD-00078",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0029",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0030",
    "last_name": "Lamrani",
    "first_name": "Hasnae",
    "sex": 2,
    "birth_date": "1966-01-12",
    "national_id": "XF278240",
    "phone": "+212623497411",
    "address": {
      "street": "11 Rue Colbert",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-06-11"
    },
    "visits": [
      {
        "visit_id": "V-P2-0030-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-BENNIS",
        "physician": "Dr. Bennis",
        "admitted_at": ISODate("2026-06-25T05:40:25+01:00"),
        "discharged_at": ISODate("2026-06-25T06:40:25+01:00"),
        "reason": "Routine eye exam",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H10.9",
            "label": "Conjunctivitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2026-06-25T05:50:25+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 15,
            "unit": "mm[Hg]",
            "at": ISODate("2026-06-25T05:50:25+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-06-25T05:52:25+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 124,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 78,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 122,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2026-06-25T05:54:25+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0030-02",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BELKADI",
        "physician": "Dr. Belkadi",
        "admitted_at": ISODate("2025-03-23T03:41:08+01:00"),
        "discharged_at": ISODate("2025-03-24T00:41:08+01:00"),
        "reason": "Pre-LASIK evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-03-23T03:53:08+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 112,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0030-02",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2025-03-23T04:26:08+01:00"),
            "performer": "Dr. Belkadi",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00079",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-06-25T05:40:25+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0030",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0030-01"
      },
      {
        "audit_id": "AUD-00080",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0030",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  }

]);
db.patients.insertMany([

  {
    "patient_id": "P2-0031",
    "last_name": "Errafii",
    "first_name": "Souad",
    "sex": 2,
    "birth_date": "1965-10-11",
    "national_id": "RD348728",
    "phone": "+212651185849",
    "address": {
      "street": "74 Rue de Fès",
      "city": "Casablanca"
    },
    "blood_type": "AB+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-02-24"
    },
    "visits": [
      {
        "visit_id": "V-P2-0031-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-JAIDI",
        "physician": "Dr. Jaidi",
        "admitted_at": ISODate("2025-03-02T17:22:13+01:00"),
        "discharged_at": ISODate("2025-03-02T21:22:13+01:00"),
        "reason": "Pre-operative assessment",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-03-02T17:34:13+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 129,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 85,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0031-01",
            "status": "final",
            "performer": "Dr. Jaidi",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-03-02T18:22:13+01:00"),
            "issued_at": ISODate("2025-03-02T19:22:13+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0031-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-03-02T18:22:13+01:00"),
            "performer": "Dr. Jaidi",
            "body_site": "right eye"
          }
        ]
      },
      {
        "visit_id": "V-P2-0031-02",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENNIS",
        "physician": "Dr. Bennis",
        "admitted_at": ISODate("2025-07-01T15:28:38+01:00"),
        "discharged_at": ISODate("2025-07-01T16:28:38+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.1",
            "label": "Primary open-angle glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 26,
            "unit": "mm[Hg]",
            "at": ISODate("2025-07-01T15:38:38+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2025-07-01T15:38:38+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-07-01T15:40:38+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 154,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.12922879866940233785",
            "modality": "OP",
            "accession": "ACC-003149",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0031-02",
            "status": "final",
            "performer": "Dr. Bennis",
            "imaging_ref": "img-V-P2-0031-02",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-07-01T15:48:38+01:00"),
            "issued_at": ISODate("2025-07-01T16:18:38+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0031-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-07-01T15:28:38+01:00"),
            "requester": "Dr. Bennis"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0031-02",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-07-01T15:58:38+01:00"),
            "performer": "Dr. Bennis",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00081",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-03-02T17:22:13+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0031",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0031-01"
      },
      {
        "audit_id": "AUD-00082",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0031",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0032",
    "last_name": "Kettani",
    "first_name": "Zineb",
    "sex": 2,
    "birth_date": "1961-10-27",
    "national_id": "FG238579",
    "phone": "+212672398083",
    "address": {
      "street": "47 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "AB+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0032-01",
        "substance": "Penicillin",
        "snomed_substance": "764146007",
        "reaction": "Anaphylaxis",
        "snomed_reaction": "39579001",
        "criticite": "ELEVEE",
        "date": "2022-05-24",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-06-20"
    },
    "visits": [
      {
        "visit_id": "V-P2-0032-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-LYAZIDI",
        "physician": "Dr. Lyazidi",
        "admitted_at": ISODate("2024-06-28T05:50:16+01:00"),
        "discharged_at": ISODate("2024-06-28T23:50:16+01:00"),
        "reason": "Post-operative follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-06-28T06:02:16+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 114,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 77,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0032-01",
            "status": "final",
            "performer": "Dr. Lyazidi",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-06-28T06:50:16+01:00"),
            "issued_at": ISODate("2024-06-28T07:50:16+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0032-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-06-28T06:50:16+01:00"),
            "performer": "Dr. Lyazidi",
            "body_site": "right eye"
          }
        ]
      },
      {
        "visit_id": "V-P2-0032-02",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENJELLOUN",
        "physician": "Dr. Benjelloun",
        "admitted_at": ISODate("2026-05-16T02:07:13+01:00"),
        "discharged_at": ISODate("2026-05-16T17:07:13+01:00"),
        "reason": "Pre-LASIK evaluation",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-05-16T02:19:13+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 122,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 70,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0032-02",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2026-05-16T02:52:13+01:00"),
            "performer": "Dr. Benjelloun",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00083",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-06-28T05:50:16+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0032",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0032-01"
      },
      {
        "audit_id": "AUD-00084",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0032",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0033",
    "last_name": "Bennis",
    "first_name": "Meryem",
    "sex": 2,
    "birth_date": "1968-02-18",
    "national_id": "MD807617",
    "phone": "+212631383044",
    "address": {
      "street": "61 Rue Mohammed V",
      "city": "Casablanca"
    },
    "blood_type": "AB-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-08-31"
    },
    "visits": [
      {
        "visit_id": "V-P2-0033-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-BOUAYAD",
        "physician": "Dr. Bouayad",
        "admitted_at": ISODate("2026-09-14T09:34:30+01:00"),
        "discharged_at": ISODate("2026-09-14T11:34:30+01:00"),
        "reason": "Routine eye exam",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H16.9",
            "label": "Keratitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 15,
            "unit": "mm[Hg]",
            "at": ISODate("2026-09-14T09:44:30+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2026-09-14T09:44:30+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-09-14T09:46:30+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 113,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 74,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 82,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2026-09-14T09:48:30+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00085",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-09-14T09:34:30+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0033",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0033-01"
      },
      {
        "audit_id": "AUD-00086",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0033",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0034",
    "last_name": "Sebti",
    "first_name": "Latifa",
    "sex": 2,
    "birth_date": "1957-06-06",
    "national_id": "NQ489033",
    "phone": "+212689991136",
    "address": {
      "street": "96 Rue Allal Ben Abdellah",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-09-28"
    },
    "visits": [
      {
        "visit_id": "V-P2-0034-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-CHAOUI",
        "physician": "Dr. Chaoui",
        "admitted_at": ISODate("2025-10-06T20:00:58+01:00"),
        "discharged_at": ISODate("2025-10-06T21:00:58+01:00"),
        "reason": "Elevated intraocular pressure",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 28,
            "unit": "mm[Hg]",
            "at": ISODate("2025-10-06T20:10:58+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 24,
            "unit": "mm[Hg]",
            "at": ISODate("2025-10-06T20:10:58+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-10-06T20:12:58+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 131,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 91,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.64519206540541099118",
            "modality": "OP",
            "accession": "ACC-003440",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0034-01",
            "status": "final",
            "performer": "Dr. Chaoui",
            "imaging_ref": "img-V-P2-0034-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-10-06T20:20:58+01:00"),
            "issued_at": ISODate("2025-10-06T20:50:58+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0034-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-10-06T20:00:58+01:00"),
            "requester": "Dr. Chaoui"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0034-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-10-06T20:30:58+01:00"),
            "performer": "Dr. Chaoui",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00087",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-10-06T20:00:58+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0034",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0034-01"
      },
      {
        "audit_id": "AUD-00088",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0034",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0035",
    "last_name": "El Fassi",
    "first_name": "Loubna",
    "sex": 2,
    "birth_date": "2000-07-04",
    "national_id": "DQ196126",
    "phone": "+212688955314",
    "address": {
      "street": "28 Av Lalla Yacout",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-07-03"
    },
    "visits": [
      {
        "visit_id": "V-P2-0035-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2024-07-14T22:46:57+01:00"),
        "discharged_at": ISODate("2024-07-15T20:46:57+01:00"),
        "reason": "Post-LASIK follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-07-14T22:58:57+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 112,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 76,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0035-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2024-07-14T23:31:57+01:00"),
            "performer": "Dr. Benchekroun",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00089",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-07-14T22:46:57+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0035",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0035-01"
      },
      {
        "audit_id": "AUD-00090",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0035",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0036",
    "last_name": "Bakkali",
    "first_name": "Ayoub",
    "sex": 1,
    "birth_date": "1991-08-17",
    "national_id": "EE666456",
    "phone": "+212633642236",
    "address": {
      "street": "23 Bd Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0036-01",
        "substance": "Tetracaine",
        "snomed_substance": "372697009",
        "reaction": "Contact dermatitis",
        "snomed_reaction": "238567008",
        "criticite": "MOYENNE",
        "date": "2019-06-01",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-01-31"
    },
    "visits": [
      {
        "visit_id": "V-P2-0036-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-MERNISSI",
        "physician": "Dr. Mernissi",
        "admitted_at": ISODate("2025-02-16T13:37:04+01:00"),
        "discharged_at": ISODate("2025-02-16T14:37:04+01:00"),
        "reason": "Annual check-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H10.9",
            "label": "Conjunctivitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2025-02-16T13:47:04+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2025-02-16T13:47:04+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-02-16T13:49:04+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 113,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 72,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 110,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-02-16T13:51:04+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00091",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-02-16T13:37:04+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0036",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0036-01"
      },
      {
        "audit_id": "AUD-00092",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0036",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0037",
    "last_name": "Belyamani",
    "first_name": "Yassine",
    "sex": 1,
    "birth_date": "1952-04-20",
    "national_id": "ZX646781",
    "phone": "+212640484137",
    "address": {
      "street": "59 Av Lalla Yacout",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-10-06"
    },
    "visits": [
      {
        "visit_id": "V-P2-0037-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2025-10-24T12:37:56+01:00"),
        "discharged_at": ISODate("2025-10-24T13:37:56+01:00"),
        "reason": "Glaucoma monitoring",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 29,
            "unit": "mm[Hg]",
            "at": ISODate("2025-10-24T12:47:56+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2025-10-24T12:47:56+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-10-24T12:49:56+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 158,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 82,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.30667851039363427220",
            "modality": "OP",
            "accession": "ACC-003718",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0037-01",
            "status": "final",
            "performer": "Dr. Benchekroun",
            "imaging_ref": "img-V-P2-0037-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-10-24T12:57:56+01:00"),
            "issued_at": ISODate("2025-10-24T13:27:56+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0037-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-10-24T12:37:56+01:00"),
            "requester": "Dr. Benchekroun"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0037-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-10-24T13:07:56+01:00"),
            "performer": "Dr. Benchekroun",
            "body_site": null
          }
        ]
      },
      {
        "visit_id": "V-P2-0037-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BENNIS",
        "physician": "Dr. Bennis",
        "admitted_at": ISODate("2026-09-10T18:48:39+01:00"),
        "discharged_at": ISODate("2026-09-11T16:48:39+01:00"),
        "reason": "Pre-operative assessment",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-09-10T19:00:39+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 122,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 79,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0037-02",
            "status": "final",
            "performer": "Dr. Bennis",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2026-09-10T19:48:39+01:00"),
            "issued_at": ISODate("2026-09-10T20:48:39+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0037-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2026-09-10T19:48:39+01:00"),
            "performer": "Dr. Bennis",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00093",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-10-24T12:37:56+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0037",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0037-01"
      },
      {
        "audit_id": "AUD-00094",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0037",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0038",
    "last_name": "Belghiti",
    "first_name": "Hamza",
    "sex": 1,
    "birth_date": "1994-07-23",
    "national_id": "PL967611",
    "phone": "+212660867592",
    "address": {
      "street": "52 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "A-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-07-29"
    },
    "visits": [
      {
        "visit_id": "V-P2-0038-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-GHALI",
        "physician": "Dr. Ghali",
        "admitted_at": ISODate("2025-08-04T18:57:12+01:00"),
        "discharged_at": ISODate("2025-08-05T02:57:12+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-08-04T19:09:12+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 112,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 72,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0038-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2025-08-04T19:42:12+01:00"),
            "performer": "Dr. Ghali",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0038-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENSLIMANE",
        "physician": "Dr. Benslimane",
        "admitted_at": ISODate("2024-05-30T08:10:58+01:00"),
        "discharged_at": ISODate("2024-05-30T10:10:58+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "E11.3",
            "label": "Diabetic retinopathy"
          },
          {
            "system": "ICD-10",
            "code": "H36.0",
            "label": "Diabetic retinopathy — manifestation"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2024-05-30T08:20:58+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 11,
            "unit": "mm[Hg]",
            "at": ISODate("2024-05-30T08:20:58+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-05-30T08:22:58+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 148,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 90,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 245,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-05-30T08:24:58+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.45471569921505660065",
            "modality": "OP",
            "accession": "ACC-003895",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0038-02",
            "status": "final",
            "performer": "Dr. Benslimane",
            "imaging_ref": "img-V-P2-0038-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2024-05-30T08:25:58+01:00"),
            "issued_at": ISODate("2024-05-30T08:55:58+01:00"),
            "conclusion": "Rétinopathie diabétique documentée. Suivi à 6 mois."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0038-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2024-05-30T08:10:58+01:00"),
            "requester": "Dr. Benslimane"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00095",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-08-04T18:57:12+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0038",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0038-01"
      },
      {
        "audit_id": "AUD-00096",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0038",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0039",
    "last_name": "Benomar",
    "first_name": "Wafae",
    "sex": 2,
    "birth_date": "1955-12-13",
    "national_id": "GE788637",
    "phone": "+212664718365",
    "address": {
      "street": "29 Bd Hassan II",
      "city": "Casablanca"
    },
    "blood_type": "AB-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-02-23"
    },
    "visits": [
      {
        "visit_id": "V-P2-0039-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENJELLOUN",
        "physician": "Dr. Benjelloun",
        "admitted_at": ISODate("2025-03-09T01:46:32+01:00"),
        "discharged_at": ISODate("2025-03-09T02:46:32+01:00"),
        "reason": "Macular degeneration check",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2025-03-09T01:56:32+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 20,
            "unit": "mm[Hg]",
            "at": ISODate("2025-03-09T01:56:32+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-03-09T01:58:32+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 149,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 237,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-03-09T02:00:32+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.5933539746602767334",
            "modality": "OP",
            "accession": "ACC-003933",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0039-01",
            "status": "final",
            "performer": "Dr. Benjelloun",
            "imaging_ref": "img-V-P2-0039-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-03-09T02:01:32+01:00"),
            "issued_at": ISODate("2025-03-09T02:31:32+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0039-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-03-09T01:46:32+01:00"),
            "requester": "Dr. Benjelloun"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00097",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-03-09T01:46:32+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0039",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0039-01"
      },
      {
        "audit_id": "AUD-00098",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0039",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0040",
    "last_name": "Alaoui",
    "first_name": "Loubna",
    "sex": 2,
    "birth_date": "1983-01-12",
    "national_id": "XN172965",
    "phone": "+212619042093",
    "address": {
      "street": "95 Av Lalla Yacout",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-07-29"
    },
    "visits": [
      {
        "visit_id": "V-P2-0040-01",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-IDRISSI_KAITOUNI",
        "physician": "Dr. Idrissi-Kaitouni",
        "admitted_at": ISODate("2025-08-07T17:32:38+01:00"),
        "discharged_at": ISODate("2025-08-07T19:32:38+01:00"),
        "reason": "Glaucoma monitoring",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2025-08-07T17:42:38+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 23,
            "unit": "mm[Hg]",
            "at": ISODate("2025-08-07T17:42:38+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-08-07T17:44:38+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 141,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 89,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.85257229353819050919",
            "modality": "OP",
            "accession": "ACC-004020",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0040-01",
            "status": "final",
            "performer": "Dr. Idrissi-Kaitouni",
            "imaging_ref": "img-V-P2-0040-01",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2025-08-07T17:52:38+01:00"),
            "issued_at": ISODate("2025-08-07T18:22:38+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0040-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2025-08-07T17:32:38+01:00"),
            "requester": "Dr. Idrissi-Kaitouni"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0040-01",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2025-08-07T18:02:38+01:00"),
            "performer": "Dr. Idrissi-Kaitouni",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00099",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-08-07T17:32:38+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0040",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0040-01"
      },
      {
        "audit_id": "AUD-00100",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0040",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  }

]);
db.patients.insertMany([

  {
    "patient_id": "P2-0041",
    "last_name": "Lahlou",
    "first_name": "Rachid",
    "sex": 1,
    "birth_date": "1958-03-02",
    "national_id": "PR736565",
    "phone": "+212659330166",
    "address": {
      "street": "54 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-10-19"
    },
    "visits": [
      {
        "visit_id": "V-P2-0041-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BENABBOU",
        "physician": "Dr. Benabbou",
        "admitted_at": ISODate("2025-10-30T04:20:31+01:00"),
        "discharged_at": ISODate("2025-10-30T11:20:31+01:00"),
        "reason": "Post-operative follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-10-30T04:32:31+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 128,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 85,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0041-01",
            "status": "final",
            "performer": "Dr. Benabbou",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-10-30T05:20:31+01:00"),
            "issued_at": ISODate("2025-10-30T06:20:31+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0041-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-10-30T05:20:31+01:00"),
            "performer": "Dr. Benabbou",
            "body_site": "right eye"
          }
        ]
      },
      {
        "visit_id": "V-P2-0041-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2024-12-08T21:31:23+01:00"),
        "discharged_at": ISODate("2024-12-09T13:31:23+01:00"),
        "reason": "Pre-operative assessment",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-12-08T21:43:23+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 110,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 76,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0041-02",
            "status": "final",
            "performer": "Dr. Benchekroun",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-12-08T22:31:23+01:00"),
            "issued_at": ISODate("2024-12-08T23:31:23+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0041-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-12-08T22:31:23+01:00"),
            "performer": "Dr. Benchekroun",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00101",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-10-30T04:20:31+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0041",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0041-01"
      },
      {
        "audit_id": "AUD-00102",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0041",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0042",
    "last_name": "Kabbaj",
    "first_name": "Saad",
    "sex": 1,
    "birth_date": "1968-04-01",
    "national_id": "RZ551574",
    "phone": "+212623581357",
    "address": {
      "street": "17 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "B-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-04-03"
    },
    "visits": [
      {
        "visit_id": "V-P2-0042-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-ZAIDANE",
        "physician": "Dr. Zaidane",
        "admitted_at": ISODate("2024-04-22T07:10:09+01:00"),
        "discharged_at": ISODate("2024-04-22T23:10:09+01:00"),
        "reason": "Pre-operative assessment",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-04-22T07:22:09+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 123,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 70,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0042-01",
            "status": "final",
            "performer": "Dr. Zaidane",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-04-22T08:10:09+01:00"),
            "issued_at": ISODate("2024-04-22T09:10:09+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0042-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-04-22T08:10:09+01:00"),
            "performer": "Dr. Zaidane",
            "body_site": "right eye"
          }
        ]
      },
      {
        "visit_id": "V-P2-0042-02",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BENJELLOUN",
        "physician": "Dr. Benjelloun",
        "admitted_at": ISODate("2025-05-01T15:44:46+01:00"),
        "discharged_at": ISODate("2025-05-01T17:44:46+01:00"),
        "reason": "Visual acuity decrease",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-01T15:54:46+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 17,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-01T15:54:46+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-05-01T15:56:46+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 139,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 83,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 211,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-05-01T15:58:46+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.55716726536048138986",
            "modality": "OP",
            "accession": "ACC-004231",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0042-02",
            "status": "final",
            "performer": "Dr. Benjelloun",
            "imaging_ref": "img-V-P2-0042-02",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-05-01T15:59:46+01:00"),
            "issued_at": ISODate("2025-05-01T16:29:46+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0042-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-05-01T15:44:46+01:00"),
            "requester": "Dr. Benjelloun"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00103",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-04-22T07:10:09+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0042",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0042-01"
      },
      {
        "audit_id": "AUD-00104",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0042",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0043",
    "last_name": "Cherkaoui",
    "first_name": "Imane",
    "sex": 2,
    "birth_date": "1976-11-07",
    "national_id": "UN649414",
    "phone": "+212610555833",
    "address": {
      "street": "51 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "AB-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-04-19"
    },
    "visits": [
      {
        "visit_id": "V-P2-0043-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BELGHITI",
        "physician": "Dr. Belghiti",
        "admitted_at": ISODate("2024-04-28T23:37:46+01:00"),
        "discharged_at": ISODate("2024-04-29T00:37:46+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 19,
            "unit": "mm[Hg]",
            "at": ISODate("2024-04-28T23:47:46+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 14,
            "unit": "mm[Hg]",
            "at": ISODate("2024-04-28T23:47:46+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-04-28T23:49:46+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 158,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 91,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 204,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2024-04-28T23:51:46+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.34481523240705441828",
            "modality": "OP",
            "accession": "ACC-004340",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0043-01",
            "status": "final",
            "performer": "Dr. Belghiti",
            "imaging_ref": "img-V-P2-0043-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2024-04-28T23:52:46+01:00"),
            "issued_at": ISODate("2024-04-29T00:22:46+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0043-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2024-04-28T23:37:46+01:00"),
            "requester": "Dr. Belghiti"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00105",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2024-04-28T23:37:46+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0043",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0043-01"
      },
      {
        "audit_id": "AUD-00106",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0043",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0044",
    "last_name": "Rahimi",
    "first_name": "Lamiae",
    "sex": 2,
    "birth_date": "1983-02-27",
    "national_id": "CF910389",
    "phone": "+212684281857",
    "address": {
      "street": "64 Rue Oum Errabia",
      "city": "Casablanca"
    },
    "blood_type": "O-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-08-26"
    },
    "visits": [
      {
        "visit_id": "V-P2-0044-01",
        "visit_type": 2,
        "department": "General Ophthalmology",
        "physician_ref": "PRAC-ZERHOUNI",
        "physician": "Dr. Zerhouni",
        "admitted_at": ISODate("2026-09-01T16:21:35+01:00"),
        "discharged_at": ISODate("2026-09-01T18:21:35+01:00"),
        "reason": "Blurred vision",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H10.9",
            "label": "Conjunctivitis, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2026-09-01T16:31:35+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 12,
            "unit": "mm[Hg]",
            "at": ISODate("2026-09-01T16:31:35+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-09-01T16:33:35+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 125,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 120,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2026-09-01T16:35:35+01:00"),
            "interpretation": "N"
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0044-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-CHAOUI",
        "physician": "Dr. Chaoui",
        "admitted_at": ISODate("2024-03-28T14:14:54+01:00"),
        "discharged_at": ISODate("2024-03-29T05:14:54+01:00"),
        "reason": "Pre-operative assessment",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-03-28T14:26:54+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 119,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 84,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0044-02",
            "status": "final",
            "performer": "Dr. Chaoui",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-03-28T15:14:54+01:00"),
            "issued_at": ISODate("2024-03-28T16:14:54+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0044-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-03-28T15:14:54+01:00"),
            "performer": "Dr. Chaoui",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00107",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-09-01T16:21:35+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0044",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0044-01"
      },
      {
        "audit_id": "AUD-00108",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0044",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0045",
    "last_name": "Jaidi",
    "first_name": "Soufiane",
    "sex": 1,
    "birth_date": "1987-02-06",
    "national_id": "VS503159",
    "phone": "+212662104107",
    "address": {
      "street": "75 Bd d'Anfa",
      "city": "Casablanca"
    },
    "blood_type": "A+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-05-04"
    },
    "visits": [
      {
        "visit_id": "V-P2-0045-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-MRABET",
        "physician": "Dr. Mrabet",
        "admitted_at": ISODate("2025-05-14T19:23:11+01:00"),
        "discharged_at": ISODate("2025-05-14T21:23:11+01:00"),
        "reason": "Visual acuity decrease",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.0",
            "label": "Background retinopathy"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 13,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-14T19:33:11+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 11,
            "unit": "mm[Hg]",
            "at": ISODate("2025-05-14T19:33:11+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-05-14T19:35:11+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 144,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 83,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 263,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-05-14T19:37:11+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.53340370728930848006",
            "modality": "OP",
            "accession": "ACC-004520",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0045-01",
            "status": "final",
            "performer": "Dr. Mrabet",
            "imaging_ref": "img-V-P2-0045-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-05-14T19:38:11+01:00"),
            "issued_at": ISODate("2025-05-14T20:08:11+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0045-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-05-14T19:23:11+01:00"),
            "requester": "Dr. Mrabet"
          }
        ],
        "procedures": []
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00109",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-05-14T19:23:11+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0045",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0045-01"
      },
      {
        "audit_id": "AUD-00110",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0045",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0046",
    "last_name": "Bensaid",
    "first_name": "Hicham",
    "sex": 1,
    "birth_date": "1992-12-21",
    "national_id": "VF481574",
    "phone": "+212650043345",
    "address": {
      "street": "37 Av Mers Sultan",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2026-08-21"
    },
    "visits": [
      {
        "visit_id": "V-P2-0046-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENABBOU",
        "physician": "Dr. Benabbou",
        "admitted_at": ISODate("2026-09-07T09:09:22+01:00"),
        "discharged_at": ISODate("2026-09-08T09:09:22+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.0",
            "label": "Hypermetropia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-09-07T09:21:22+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 112,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0046-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2026-09-07T09:54:22+01:00"),
            "performer": "Dr. Benabbou",
            "body_site": "both eyes"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00111",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2026-09-07T09:09:22+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0046",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0046-01"
      },
      {
        "audit_id": "AUD-00112",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0046",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0047",
    "last_name": "Fassi-Fihri",
    "first_name": "Souad",
    "sex": 2,
    "birth_date": "1970-01-21",
    "national_id": "XE466813",
    "phone": "+212641638598",
    "address": {
      "street": "84 Rue Allal Ben Abdellah",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-04-19"
    },
    "visits": [
      {
        "visit_id": "V-P2-0047-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-MERNISSI",
        "physician": "Dr. Mernissi",
        "admitted_at": ISODate("2025-04-26T06:02:57+01:00"),
        "discharged_at": ISODate("2025-04-27T03:02:57+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-04-26T06:14:57+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 130,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 80,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0047-01",
            "status": "final",
            "performer": "Dr. Mernissi",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-04-26T07:02:57+01:00"),
            "issued_at": ISODate("2025-04-26T08:02:57+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0047-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-04-26T07:02:57+01:00"),
            "performer": "Dr. Mernissi",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00113",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-04-26T06:02:57+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0047",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0047-01"
      },
      {
        "audit_id": "AUD-00114",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0047",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0048",
    "last_name": "Chraibi",
    "first_name": "Meryem",
    "sex": 2,
    "birth_date": "1962-06-29",
    "national_id": "GL903373",
    "phone": "+212665266178",
    "address": {
      "street": "25 Rue Ibnou Rachiq",
      "city": "Casablanca"
    },
    "blood_type": "B+",
    "allergies": [
      {
        "allergy_id": "ALG-P2-0048-01",
        "substance": "Fluorescein sodium",
        "snomed_substance": "372639009",
        "reaction": "Urticaria",
        "snomed_reaction": "126485001",
        "criticite": "ELEVEE",
        "date": "2018-09-27",
        "status": "active",
        "category": "medication",
        "verificationStatus": "confirmed"
      }
    ],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-05-28"
    },
    "visits": [
      {
        "visit_id": "V-P2-0048-01",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-MERNISSI",
        "physician": "Dr. Mernissi",
        "admitted_at": ISODate("2025-06-07T11:29:08+01:00"),
        "discharged_at": ISODate("2025-06-08T10:29:08+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H25.9",
            "label": "Age-related cataract, unspecified"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-06-07T11:41:08+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 129,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 82,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0048-01",
            "status": "final",
            "performer": "Dr. Mernissi",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2025-06-07T12:29:08+01:00"),
            "issued_at": ISODate("2025-06-07T13:29:08+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0048-01",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2025-06-07T12:29:08+01:00"),
            "performer": "Dr. Mernissi",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00115",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-06-07T11:29:08+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0048",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0048-01"
      },
      {
        "audit_id": "AUD-00116",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0048",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0049",
    "last_name": "Bensaid",
    "first_name": "Ahmed",
    "sex": 1,
    "birth_date": "1965-10-01",
    "national_id": "XZ349068",
    "phone": "+212659619341",
    "address": {
      "street": "79 Bd Zerktouni",
      "city": "Casablanca"
    },
    "blood_type": "O-",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2025-12-15"
    },
    "visits": [
      {
        "visit_id": "V-P2-0049-01",
        "visit_type": 2,
        "department": "Retina",
        "physician_ref": "PRAC-BELGHITI",
        "physician": "Dr. Belghiti",
        "admitted_at": ISODate("2025-12-29T22:10:08+01:00"),
        "discharged_at": ISODate("2025-12-29T23:10:08+01:00"),
        "reason": "Diabetic retinopathy follow-up",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H35.3",
            "label": "Age-related macular degeneration"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 20,
            "unit": "mm[Hg]",
            "at": ISODate("2025-12-29T22:20:08+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 18,
            "unit": "mm[Hg]",
            "at": ISODate("2025-12-29T22:20:08+01:00"),
            "category": "exam",
            "interpretation": "N",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-12-29T22:22:08+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 144,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 89,
                "unit": "mm[Hg]"
              }
            ]
          },
          {
            "loinc": "2339-0",
            "label": "Glucose [Mass/volume] in Blood",
            "value": 259,
            "unit": "mg/dL",
            "category": "laboratory",
            "at": ISODate("2025-12-29T22:24:08+01:00"),
            "interpretation": "H"
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.84063967345006503002",
            "modality": "OP",
            "accession": "ACC-004963",
            "description": "Color fundus photography, both eyes",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0049-01",
            "status": "final",
            "performer": "Dr. Belghiti",
            "imaging_ref": "img-V-P2-0049-01",
            "code_label": "Fond d'œil — rétinographie couleur",
            "effective_at": ISODate("2025-12-29T22:25:08+01:00"),
            "issued_at": ISODate("2025-12-29T22:55:08+01:00"),
            "conclusion": "Examen du fond d'œil réalisé."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0049-01",
            "status": "completed",
            "intent": "order",
            "code_label": "Rétinographie couleur des deux yeux",
            "authored_on": ISODate("2025-12-29T22:10:08+01:00"),
            "requester": "Dr. Belghiti"
          }
        ],
        "procedures": []
      },
      {
        "visit_id": "V-P2-0049-02",
        "visit_type": 2,
        "department": "Glaucoma",
        "physician_ref": "PRAC-MRANI",
        "physician": "Dr. Mrani",
        "admitted_at": ISODate("2026-07-28T15:29:14+01:00"),
        "discharged_at": ISODate("2026-07-28T16:29:14+01:00"),
        "reason": "Glaucoma monitoring",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H40.2",
            "label": "Primary angle-closure glaucoma"
          }
        ],
        "observations": [
          {
            "loinc": "79892-6",
            "label": "Right eye intraocular pressure",
            "value": 22,
            "unit": "mm[Hg]",
            "at": ISODate("2026-07-28T15:39:14+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "18944008",
              "display": "Right eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "79893-4",
            "label": "Left eye intraocular pressure",
            "value": 27,
            "unit": "mm[Hg]",
            "at": ISODate("2026-07-28T15:39:14+01:00"),
            "category": "exam",
            "interpretation": "H",
            "bodySite": {
              "snomedCode": "8966001",
              "display": "Left eye structure"
            },
            "referenceRange": {
              "low": 10,
              "high": 21,
              "unit": "mm[Hg]"
            }
          },
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2026-07-28T15:41:14+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 145,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 91,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [
          {
            "study_uid": "2.25.18234674085770191322",
            "modality": "OP",
            "accession": "ACC-004976",
            "description": "Optic nerve head photography",
            "instances": 2
          }
        ],
        "reports": [
          {
            "report_id": "RPT-V-P2-0049-02",
            "status": "final",
            "performer": "Dr. Mrani",
            "imaging_ref": "img-V-P2-0049-02",
            "code_label": "Champ visuel — périmétrie automatisée",
            "effective_at": ISODate("2026-07-28T15:49:14+01:00"),
            "issued_at": ISODate("2026-07-28T16:19:14+01:00"),
            "conclusion": "Déficit périphérique compatible avec un GPAO."
          }
        ],
        "service_requests": [
          {
            "sr_id": "SR-V-P2-0049-02",
            "status": "completed",
            "intent": "order",
            "code_label": "Périmétrie automatisée Humphrey 24-2",
            "authored_on": ISODate("2026-07-28T15:29:14+01:00"),
            "requester": "Dr. Mrani"
          }
        ],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0049-02",
            "status": "completed",
            "code_label": "Gonioscopie — examen de l'angle irido-cornéen",
            "occurred_at": ISODate("2026-07-28T15:59:14+01:00"),
            "performer": "Dr. Mrani",
            "body_site": null
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00117",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-12-29T22:10:08+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0049",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0049-01"
      },
      {
        "audit_id": "AUD-00118",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0049",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  },
  {
    "patient_id": "P2-0050",
    "last_name": "Boulahia",
    "first_name": "Ahmed",
    "sex": 1,
    "birth_date": "1992-06-12",
    "national_id": "PC332823",
    "phone": "+212660549373",
    "address": {
      "street": "45 Rue Mohammed V",
      "city": "Casablanca"
    },
    "blood_type": "O+",
    "allergies": [],
    "consent": {
      "status": "active",
      "purpose": "care-continuity",
      "signed_by": "patient",
      "date": "2024-12-18"
    },
    "visits": [
      {
        "visit_id": "V-P2-0050-01",
        "visit_type": 3,
        "department": "Refractive Surgery",
        "physician_ref": "PRAC-BENCHEKROUN",
        "physician": "Dr. Benchekroun",
        "admitted_at": ISODate("2025-01-01T14:26:37+01:00"),
        "discharged_at": ISODate("2025-01-02T06:26:37+01:00"),
        "reason": "Myopia correction — LASIK",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H52.1",
            "label": "Myopia"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2025-01-01T14:38:37+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 121,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 77,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0050-01",
            "status": "completed",
            "code_label": "LASIK — chirurgie réfractive au laser excimer",
            "occurred_at": ISODate("2025-01-01T15:11:37+01:00"),
            "performer": "Dr. Benchekroun",
            "body_site": "both eyes"
          }
        ]
      },
      {
        "visit_id": "V-P2-0050-02",
        "visit_type": 3,
        "department": "Cataract Surgery",
        "physician_ref": "PRAC-BOUAYAD",
        "physician": "Dr. Bouayad",
        "admitted_at": ISODate("2024-06-03T06:05:11+01:00"),
        "discharged_at": ISODate("2024-06-04T06:05:11+01:00"),
        "reason": "Cataract surgery",
        "conditions": [
          {
            "system": "ICD-10",
            "code": "H26.9",
            "label": "Unspecified cataract"
          }
        ],
        "observations": [
          {
            "loinc": "85354-9",
            "label": "Blood pressure panel",
            "category": "vital-signs",
            "at": ISODate("2024-06-03T06:17:11+01:00"),
            "components": [
              {
                "loinc": "8480-6",
                "label": "Systolic BP",
                "value": 114,
                "unit": "mm[Hg]"
              },
              {
                "loinc": "8462-4",
                "label": "Diastolic BP",
                "value": 74,
                "unit": "mm[Hg]"
              }
            ]
          }
        ],
        "imaging": [],
        "reports": [
          {
            "report_id": "RPT-V-P2-0050-02",
            "status": "final",
            "performer": "Dr. Bouayad",
            "imaging_ref": null,
            "code_label": "Compte rendu opératoire — phacoémulsification",
            "effective_at": ISODate("2024-06-03T07:05:11+01:00"),
            "issued_at": ISODate("2024-06-03T08:05:11+01:00"),
            "conclusion": "Chirurgie réalisée sans complication. Implant LIO mis en place."
          }
        ],
        "service_requests": [],
        "procedures": [
          {
            "proc_id": "PROC-V-P2-0050-02",
            "status": "completed",
            "code_label": "Phacoémulsification avec implant LIO",
            "occurred_at": ISODate("2024-06-03T07:05:11+01:00"),
            "performer": "Dr. Bouayad",
            "body_site": "right eye"
          }
        ]
      }
    ],
    "org_ref": "ORG-ALBACAR",
    "_audit_log": [
      {
        "audit_id": "AUD-00119",
        "event_type": "record-creation",
        "action": "C",
        "recorded_at": ISODate("2025-01-01T14:26:37+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0050",
        "agent_who": "FHIR-Connector-v3",
        "source_observer": "Clinique Al Baçar — DPI",
        "encounter_ref": "V-P2-0050-01"
      },
      {
        "audit_id": "AUD-00120",
        "event_type": "record-access",
        "action": "R",
        "recorded_at": ISODate("2026-09-25T18:00:00+01:00"),
        "outcome_code": "success",
        "patient_ref": "P2-0050",
        "agent_who": "FHIR-Connector-v3 (export)",
        "source_observer": "Clinique Al Baçar — DPI"
      }
    ]
  }

]);

db.patients.createIndex({ patient_id: 1 }, { unique: true });
db.patients.createIndex({ national_id: 1 });
db.patients.createIndex({ "consent.status": 1 });

print("✓ hopital2_mongodb_v3.js chargé — 60 patients, schéma FHIR R5 v3.3-compat (collections séparées)");
