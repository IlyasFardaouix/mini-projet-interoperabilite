"""
Configuration de l'adaptateur H1 (CHU Al Massira, Oracle) <-> FHIR R5.

Ce fichier EST la table de correspondance H1 <-> FHIR sous forme de code :
les deux adaptateurs (aller et retour) lisent les mêmes tables, donc ils restent
toujours cohérents entre eux. Toute valeur marquée « À ALIGNER » doit être
identique dans les adaptateurs H2 (Hiba / Rim).
"""

# --------------------------------------------------------------------------
# 1. Établissements et systèmes d'identifiants (NamingSystems)
# --------------------------------------------------------------------------
TZ = "+01:00"                       # fuseau des dates Oracle (heure du Maroc)
LANGUE = "fr"

CHU = {
    "nom": "CHU Al Massira",
    "ville": "Settat",
    "source": "https://chu-almassira.ma/dpi",        # meta.source
    "id_annuaire": "CHU-AL-MASSIRA",
}
CLINIQUE = {
    "nom": "Clinique Al Baçar",
    "ville": "Casablanca",
    "source": "https://clinique-yeux.ma/dpi",        # À ALIGNER avec H2
    "id_annuaire": "CLINIQUE-AL-BACAR",
}

SYS_CIN = "urn:ma:cin"                                 # À ALIGNER avec H2
SYS_IPP_CHU = "https://chu-almassira.ma/ipp"
SYS_ECHANGE = "urn:chu-almassira:echange"            # Bundle.identifier : identifiant d'echange (rejeu sans doublon)
SYS_SEJOUR_CHU = "https://chu-almassira.ma/sejour"
SYS_MESURE_CHU = "https://chu-almassira.ma/mesure"
SYS_MEDECIN_CHU = "https://chu-almassira.ma/medecin"
SYS_DEMANDE_CHU = "https://chu-almassira.ma/demande"
SYS_ALLERGIE_CHU = "https://chu-almassira.ma/allergie"
SYS_CONSENTEMENT_CHU = "https://chu-almassira.ma/consentement"
CODE_ETABLISSEMENT = "H1"                    # code du CHU dans les regles de consentement communes
SYS_CODE_LOCAL_ALLERGIE = "https://chu-almassira.ma/codes/allergie"
ALLERGY_CLINICAL = "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"
ALLERGY_VERIF = "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification"
CRITICITE_VERS_FHIR = {"ELEVEE": "high", "FAIBLE": "low", "MOYENNE": "unable-to-assess"}
SYS_ANNUAIRE = "https://annuaire.sante.ma/etablissement"
SYS_CODE_LOCAL_MALADIE = "https://chu-almassira.ma/codes/maladie"
SYS_CODE_LOCAL_MESURE = "https://chu-almassira.ma/codes/mesure"
SYS_SERVICE_CHU = "https://chu-almassira.ma/codes/service"

# Terminologies standard
LOINC = "http://loinc.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10"
SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"
V3_ACTCODE = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
V3_CONFID = "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
V3_INTERP = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
V3_PARTICIP = "http://terminology.hl7.org/CodeSystem/v3-ParticipationType"
OBS_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
DISCHARGE = "http://terminology.hl7.org/CodeSystem/discharge-disposition"
ADMIT_SOURCE = "http://terminology.hl7.org/CodeSystem/admit-source"
DIAG_USE = "http://hl7.org/fhir/encounter-diagnosis-use"

SECURITE = [{"system": V3_CONFID, "code": "R", "display": "restricted"}]

# --------------------------------------------------------------------------
# 2. Tables de correspondance (dans les deux sens)
# --------------------------------------------------------------------------
SEXE_VERS_FHIR = {"M": "male", "F": "female"}
SEXE_VERS_H1 = {v: k for k, v in SEXE_VERS_FHIR.items()}

# type_sejour Oracle -> Encounter.class (v3-ActCode)
TYPE_SEJOUR_VERS_FHIR = {
    "URG": ("EMER", "emergency"),
    "CONS": ("AMB", "ambulatory"),
    "HOSP": ("IMP", "inpatient encounter"),
}
CLASSE_VERS_TYPE_SEJOUR = {v[0]: k for k, v in TYPE_SEJOUR_VERS_FHIR.items()}

# code_local maladie -> (CIM-10, libellé)
MALADIE_VERS_CIM10 = {
    "DIAB2": ("E11", "Diabète de type 2"),
    "HTA": ("I10", "Hypertension artérielle essentielle"),
    "ASTM": ("J45", "Asthme"),
    "IC": ("I50", "Insuffisance cardiaque"),
    "CDI": ("I25", "Cardiopathie ischémique chronique"),
    "BPCO": ("J44", "Bronchopneumopathie chronique obstructive"),
    "IRC": ("N18", "Insuffisance rénale chronique"),
    "ANEM": ("D64", "Anémie"),
    "HYPOT": ("E03", "Hypothyroïdie"),
    "ULCG": ("K25", "Ulcère gastrique"),
    "PNM": ("J18", "Pneumonie"),
    "MIG": ("G43", "Migraine"),
}
CIM10_VERS_MALADIE = {v[0]: k for k, v in MALADIE_VERS_CIM10.items()}

# code_local mesure -> paramètres LOINC / UCUM / contrôles
#   plausible = bornes physiques (hors bornes => rejet, cas D11)
#   normale   = referenceRange (sert aussi à calculer interpretation H/L/N)
MESURES = {
    "TA_SYS": {"loinc": "8480-6", "libelle": "Pression artérielle systolique",
               "ucum": "mm[Hg]", "affiche": "mmHg", "categorie": "vital-signs",
               "plausible": (40, 300), "normale": (90, 140)},
    "TA_DIA": {"loinc": "8462-4", "libelle": "Pression artérielle diastolique",
               "ucum": "mm[Hg]", "affiche": "mmHg", "categorie": "vital-signs",
               "plausible": (20, 200), "normale": (60, 90)},
    "FC": {"loinc": "8867-4", "libelle": "Fréquence cardiaque",
           "ucum": "/min", "affiche": "/min", "categorie": "vital-signs",
           "plausible": (20, 300), "normale": (60, 100)},
    "SPO2": {"loinc": "59408-5", "libelle": "Saturation en oxygène (oxymétrie de pouls)",
             "ucum": "%", "affiche": "%", "categorie": "vital-signs",
             "plausible": (0, 100), "normale": (95, 100)},
    "TEMP": {"loinc": "8310-5", "libelle": "Température corporelle",
             "ucum": "Cel", "affiche": "°C", "categorie": "vital-signs",
             "plausible": (25, 45), "normale": (36.1, 37.8)},
    "GLY": {"loinc": "2339-0", "libelle": "Glycémie",
            "ucum": "g/L", "affiche": "g/L", "categorie": "laboratory",
            "plausible": (0.1, 10), "normale": (0.7, 1.1)},
    "HBA1C": {"loinc": "4548-4", "libelle": "Hémoglobine glyquée (HbA1c)",
              "ucum": "%", "affiche": "%", "categorie": "laboratory",
              "plausible": (2, 25), "normale": (4, 6)},
}
LOINC_VERS_MESURE = {v["loinc"]: k for k, v in MESURES.items()}

# Conversions d'unités à l'import (unité reçue -> (unité H1, facteur))
CONVERSIONS_UNITES = {
    ("GLY", "mg/dL"): ("g/L", 0.01),
    ("GLY", "mmol/L"): ("g/L", 0.18),
}

# Groupe sanguin (cas d'usage de la fiche : Observation laboratoire)
LOINC_GROUPE_SANGUIN = "882-1"
LOINC_PRESSION_ARTERIELLE = "85354-9"
PROFIL_PRESSION_ARTERIELLE = "http://hl7.org/fhir/StructureDefinition/bp"
ENVOYER_GROUPE_SANGUIN = True   # décision d'équipe (fiche : « Optionnel »)

# Ophtalmologie (données reçues de la clinique au retour)
OEIL_VERS_SNOMED = {"OD": ("18944008", "Œil droit"), "OG": ("8966001", "Œil gauche")}
SNOMED_VERS_OEIL = {v[0]: k for k, v in OEIL_VERS_SNOMED.items()}
LOINC_PIO = {"79892-6": "OD", "79893-4": "OG"}   # pression intraoculaire OD / OG

# Bornes de cohérence des dates
AGE_MAJORITE = 18
