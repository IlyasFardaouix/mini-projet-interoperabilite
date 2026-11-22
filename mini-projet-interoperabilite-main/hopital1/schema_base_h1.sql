-- ============================================================================
-- H1 (CHU Al Massira, Oracle) : tables de BASE du dossier patient
-- A executer en premier, avec le compte applicatif hopital1, AVANT
--   schema_retour_h1.sql  puis  schema_consentement_h1.sql
-- (ou simplement : python initialiser_base_h1.py, qui enchaine les trois).
--
-- Ces DDL manquaient au depot : seul le schema de retour y etait. Les colonnes,
-- les types et les longueurs sont deduits du code qui les lit et les ecrit
-- (oracle_repo.py, h1_to_fhir.py, fhir_to_h1.py) ; la base 1 est volontairement
-- « a la francaise » : noms de colonnes francais, dates Oracle (affichees
-- JJ/MM/AAAA), codes locaux (TA_SYS, TA_DIA, GLY...), a l'inverse de H2.
-- Les cles etrangeres ne portent pas ON DELETE CASCADE : aucune suppression
-- de dossier n'est prevue par l'API.
-- ============================================================================

CREATE TABLE patient (
  ipp             VARCHAR2(12)  PRIMARY KEY,                 -- P1-0106
  nom             VARCHAR2(80)  NOT NULL,
  prenom          VARCHAR2(80)  NOT NULL,
  sexe            CHAR(1)       CHECK (sexe IN ('M','F')),
  date_naissance  DATE,                                      -- NULL = cas D8 (transfert rejete)
  cin             VARCHAR2(12),                              -- NULL = cas D4 (rapprochement par traits)
  telephone       VARCHAR2(20),                              -- 06 12 34 56 78
  adresse         VARCHAR2(120),
  ville           VARCHAR2(60),
  groupe_sanguin  VARCHAR2(5)                                -- A+, O-, AB+...
);
CREATE UNIQUE INDEX ux_patient_cin ON patient(cin);          -- plusieurs NULL autorises

CREATE TABLE consentement (
  id_consentement   VARCHAR2(14) PRIMARY KEY,                -- CST-0106 ou CST-0106-002
  ipp               VARCHAR2(12) NOT NULL REFERENCES patient(ipp),
  statut            VARCHAR2(10) CHECK (statut IN ('ACTIF','REFUSE')),   -- RETIRE ajoute par schema_consentement_h1.sql
  finalite          VARCHAR2(60),
  date_consentement DATE
);
CREATE INDEX ix_consentement_ipp ON consentement(ipp);

CREATE TABLE sejour (
  id_sejour       VARCHAR2(12) PRIMARY KEY,                  -- ST-0106-1
  ipp             VARCHAR2(12) NOT NULL REFERENCES patient(ipp),
  type_sejour     VARCHAR2(10),                              -- CONS, HOSP...
  service         VARCHAR2(80),
  date_admission  DATE,
  date_sortie     DATE,
  medecin         VARCHAR2(80),
  motif           VARCHAR2(200)
);                                                           -- etablissement, id_externe : schema_retour_h1.sql
CREATE INDEX ix_sejour_ipp ON sejour(ipp);

CREATE TABLE diagnostic (
  id_diagnostic    VARCHAR2(14) PRIMARY KEY,                 -- DGT-0106-1
  id_sejour        VARCHAR2(12) NOT NULL REFERENCES sejour(id_sejour),
  libelle          VARCHAR2(200),
  code_local       VARCHAR2(20),                             -- DIAB2, MIG, ASTM...
  date_diagnostic  DATE
);
CREATE INDEX ix_diagnostic_sejour ON diagnostic(id_sejour);

CREATE TABLE mesure (
  id_mesure     VARCHAR2(14) PRIMARY KEY,                    -- MST-0106-1
  id_sejour     VARCHAR2(12) NOT NULL REFERENCES sejour(id_sejour),
  code_local    VARCHAR2(20),                                -- TA_SYS, TA_DIA, HBA1C, GLY, SPO2...
  valeur        NUMBER(10,3),
  unite         VARCHAR2(20),
  date_mesure   DATE
);
CREATE INDEX ix_mesure_sejour ON mesure(id_sejour);

CREATE TABLE allergie (
  id_allergie    VARCHAR2(14) PRIMARY KEY,                   -- ALT-0106-1
  ipp            VARCHAR2(12) NOT NULL REFERENCES patient(ipp),
  code_allergene VARCHAR2(20),
  libelle        VARCHAR2(150),
  criticite      VARCHAR2(10)                                -- ELEVEE, FAIBLE
);
CREATE INDEX ix_allergie_ipp ON allergie(ipp);
