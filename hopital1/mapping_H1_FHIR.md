# Table de correspondance H1 (Oracle, CHU Al Massira) ⇄ FHIR R5

Référence pour l'équipe API : ce que l'adaptateur H1 **produit** (aller) et ce qu'il **accepte** (retour).
Les valeurs exactes sont dans `config.py` (source unique utilisée par les deux adaptateurs).

## 1. Identifiants et systèmes (à aligner avec H2)

| Donnée | `system` FHIR | Exemple |
|---|---|---|
| CIN (clé de rapprochement H1 ⇄ H2) | `urn:ma:cin` ⚠️ identique chez H2 | AB123456 |
| IPP du CHU | `https://chu-almassira.ma/ipp` | P1-0106 |
| Séjour | `https://chu-almassira.ma/sejour` | ST-0106-1 |
| Mesure | `https://chu-almassira.ma/mesure` | MST-0106-1 |
| Médecin | `https://chu-almassira.ma/medecin` | dr-bennani |
| Établissements | `https://annuaire.sante.ma/etablissement` | CHU-AL-MASSIRA / CLINIQUE-AL-BACAR |
| `meta.source` du CHU | `https://chu-almassira.ma/dpi` | — |

## 2. ALLER : Oracle → FHIR (Bundle `transaction`)

| Table.colonne Oracle | Ressource.champ FHIR | Règle de conversion |
|---|---|---|
| patient.cin | Patient.identifier (official) | absent → alerte, IPP seul (D4, D7) |
| patient.ipp | Patient.identifier (usual) | — |
| patient.nom / prenom | Patient.name.family / given | — |
| patient.sexe | Patient.gender | M → male, F → female |
| patient.date_naissance | Patient.birthDate | AAAA-MM-JJ ; absente → **rejet 422** (D8) |
| patient.telephone | Patient.telecom (phone, mobile) | 06 12 34 56 78 → +212612345678 |
| patient.ville | Patient.address.city (+ country = MA) | la rue n'est **pas** envoyée (loi 09-08) |
| patient.groupe_sanguin | Observation LOINC 882-1 (laboratory) | valueCodeableConcept.text |
| consentement.statut | — (contrôle avant export) | ≠ ACTIF → **rejet 403** (D1) |
| sejour.id_sejour | Encounter.identifier | — |
| sejour.type_sejour | Encounter.class (v3-ActCode) | URG → EMER, CONS → AMB, HOSP → IMP |
| sejour.service | Encounter.type | code local + texte |
| sejour.date_admission / date_sortie | Encounter.actualPeriod.start / end | +01:00 ; sortie < admission → séjour rejeté (D12) |
| sejour.medecin | Practitioner + Encounter.participant (ATND) | « Dr Bennani » → prefix Dr, family Bennani |
| sejour.motif | Encounter.reason.value.concept.text | — |
| diagnostic.code_local / libelle | Encounter.diagnosis.condition.concept | DIAB2 → CIM-10 E11 (+ code local) ; inconnu → texte seul + alerte (D9) |
| dernier séjour | Encounter.admission (destination = clinique, dischargeDisposition = other-hcf) + ServiceRequest (intent = order) | adressage vers la clinique |
| mesure.code_local | Observation.code | LOINC (table §4) + code local |
| mesure.valeur / unite | Observation.valueQuantity (UCUM) | sans unité → rejet (D10) ; hors plage plausible → rejet (D11) |
| mesures TA_SYS / TA_DIA au meme horodatage | Observation.code = LOINC 85354-9 ; component.code = 8480-6 / 8462-4 ; component.valueQuantity | Panel FHIR BP avec deux composants ; valeur absente explicite si une composante manque ; component.id conserve l'identifiant source H1 |
| mesure.date_mesure | Observation.effectiveDateTime | — |
| (calculé) | Observation.interpretation / referenceRange | N / H / L selon les valeurs normales |
| allergie | AllergyIntolerance | code local + libellé ; criticité ELEVEE → high, FAIBLE → low ; clinicalStatus active |

Chaque entrée du Bundle a `request.ifNoneExist = identifier=<system>|<valeur>` et un `fullUrl` stable :
le même export rejoué ne crée pas de doublon (D15).

## 3. RETOUR : FHIR → Oracle

| Ressource FHIR reçue | Table Oracle | Règle |
|---|---|---|
| Patient | patient (recherche) | par CIN → sinon IPP CHU → sinon traits (nom, prénom, naissance) avec alerte (D4) ; plusieurs candidats → aucun rapprochement (D6) ; divergence de nom signalée, rien n'est écrasé (D5) ; inconnu → créé avec un nouvel IPP |
| Encounter | sejour (+ etablissement, id_externe) | class → type_sejour ; id_sejour = « EX » + empreinte (12 car.) |
| Encounter.diagnosis | diagnostic | CIM-10 connu → code local (E11 → DIAB2), sinon code CIM-10 tel quel (H36.0) |
| Observation avec bodySite œil ou LOINC PIO | resultat_ophtalmo | oeil = OD/OG ; valeur ou valeur_texte (acuité « 8/10 ») ; H → alerte |
| Observation LOINC connue (§4) | mesure | conversion d'unité (glycémie mg/dL → g/L ×0,01) |
| Observation LOINC 85354-9 avec component | mesure (une ligne par composant renseigne) | 8480-6 → TA_SYS, 8462-4 → TA_DIA ; composants absents non crees ; cles externes stables au rejeu |
| Observation LOINC 882-1 | — (comparaison) | groupe différent de H1 → **alerte conflit**, rien n'est écrasé (D3) |
| ImagingStudy + Endpoint | etude_imagerie | study_uid, accession, modalités, latéralités, url_pacs (WADO-RS) |
| DiagnosticReport | compte_rendu | conclusion, statut, lien vers l'étude |
| Practitioner / Organization | (texte) | nom du médecin / de l'établissement |
| Autres (Procedure, Device, Location, AuditEvent…) | — | ignorées en v1, listées dans le rapport |

Toutes les écritures sont des `MERGE` : recevoir deux fois le même Bundle ne crée pas de doublon.

## 4. Codes

| Code local H1 | LOINC | Libellé | UCUM | Plage plausible | Valeurs normales |
|---|---|---|---|---|---|
| TA_SYS | 8480-6 | Pression artérielle systolique | mm[Hg] | 40–300 | 90–140 |
| TA_DIA | 8462-4 | Pression artérielle diastolique | mm[Hg] | 20–200 | 60–90 |
| FC | 8867-4 | Fréquence cardiaque | /min | 20–300 | 60–100 |
| SPO2 | 59408-5 | Saturation O₂ (oxymétrie) | % | 0–100 | 95–100 |
| TEMP | 8310-5 | Température corporelle | Cel | 25–45 | 36,1–37,8 |
| GLY | 2339-0 | Glycémie | g/L | 0,1–10 | 0,7–1,1 |
| HBA1C | 4548-4 | HbA1c | % | 2–25 | 4–6 |

Maladies : DIAB2 → E11, HTA → I10, ASTM → J45, IC → I50, CDI → I25, BPCO → J44, IRC → N18, ANEM → D64, HYPOT → E03, ULCG → K25, PNM → J18, MIG → G43.
Ophtalmo (retour) : PIO OD 79892-6, PIO OG 79893-4 ; œil droit SNOMED 18944008, œil gauche 8966001.

## 5. Ce que l'API doit faire avec les erreurs

| Exception Python | Cas | Réponse HTTP | Corps |
|---|---|---|---|
| `ConsentementRefuse` | D1 | 403 | `vers_operation_outcome(e)` (code `forbidden`) |
| `DonneeInvalide` | D8 | 422 | `vers_operation_outcome(e)` (code `invalid`) |
| rejets / alertes (liste) | D9–D12 | 200 + Bundle partiel | à journaliser (table `journal_echange`) |
