-- ==========================================================================
-- Tables H1 pour recevoir les données FHIR du RETOUR (clinique -> CHU)
-- À exécuter UNE FOIS dans le schéma hopital1 (DBeaver : Alt+X).
-- N'efface rien : les tables existantes gardent leurs données.
-- ==========================================================================

-- 1. Séjours venus d'un autre établissement : on ajoute 2 colonnes à sejour
ALTER TABLE sejour ADD (etablissement VARCHAR2(80), id_externe VARCHAR2(64));

-- 2. Résultats ophtalmologiques (un résultat par œil)
CREATE TABLE resultat_ophtalmo (
  id_resultat    VARCHAR2(14) PRIMARY KEY,
  ipp            VARCHAR2(12) NOT NULL REFERENCES patient(ipp),
  id_sejour      VARCHAR2(12) REFERENCES sejour(id_sejour),
  code_examen    VARCHAR2(80),          -- système|code (ex. http://loinc.org|79892-6)
  libelle        VARCHAR2(150),
  oeil           CHAR(2) CHECK (oeil IN ('OD','OG')),
  valeur         NUMBER(8,2),
  valeur_texte   VARCHAR2(60),          -- ex. acuité « 10/10 »
  unite          VARCHAR2(20),
  interpretation VARCHAR2(4),           -- N, H, L...
  date_examen    DATE,
  id_externe     VARCHAR2(64)
);

-- 3. Études d'imagerie (métadonnées DICOM, les pixels restent dans le PACS)
CREATE TABLE etude_imagerie (
  id_etude       VARCHAR2(14) PRIMARY KEY,
  ipp            VARCHAR2(12) NOT NULL REFERENCES patient(ipp),
  id_sejour      VARCHAR2(12) REFERENCES sejour(id_sejour),
  study_uid      VARCHAR2(128),
  accession      VARCHAR2(40),
  modalites      VARCHAR2(40),          -- OP, OPT, OPV...
  description    VARCHAR2(200),
  date_etude     DATE,
  nb_series      NUMBER(4),
  nb_instances   NUMBER(6),
  lateralites    VARCHAR2(10),          -- OD,OG
  url_pacs       VARCHAR2(300),         -- Endpoint.address (DICOMweb WADO-RS)
  statut         VARCHAR2(20)
);

-- 4. Comptes rendus (DiagnosticReport)
CREATE TABLE compte_rendu (
  id_cr          VARCHAR2(14) PRIMARY KEY,
  ipp            VARCHAR2(12) NOT NULL REFERENCES patient(ipp),
  id_sejour      VARCHAR2(12) REFERENCES sejour(id_sejour),
  libelle        VARCHAR2(200),
  statut         VARCHAR2(20),
  conclusion     VARCHAR2(2000),
  date_examen    DATE,
  date_emission  DATE,
  medecin        VARCHAR2(80),
  id_etude       VARCHAR2(14) REFERENCES etude_imagerie(id_etude),
  id_externe     VARCHAR2(64)
);

-- 5. Journal des échanges (traçabilité loi 09-08, rejeu sans doublon)
CREATE TABLE journal_echange (
  id_journal     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  date_echange   DATE DEFAULT SYSDATE,
  sens           VARCHAR2(6) CHECK (sens IN ('ALLER','RETOUR')),
  ipp            VARCHAR2(12),
  statut         VARCHAR2(10),          -- OK, REFUSE, REJETE, PARTIEL
  details        VARCHAR2(4000)
);
