-- ============================================================================
-- H1 (CHU Al Massira) : consentement au partage, version complete (loi 09-08)
-- A executer UNE fois, avec le compte applicatif hopital1, APRES la creation des
-- tables de base. Le script est rejouable : une colonne ou une contrainte deja
-- presente est ignoree.
--
-- Ce que le script change :
--   1. table CONSENTEMENT : periode de validite, destinataires autorises,
--      categories exclues, signataire, agent qui a recueilli, retrait ;
--   2. statut : 'RETIRE' accepte en plus de 'ACTIF' et 'REFUSE' ;
--   3. table JOURNAL_ECHANGE : le sens 'CONSENTEMENT' trace chaque recueil
--      et chaque retrait.
--
-- Une ligne = une version. L'API n'emet jamais d'UPDATE ni de DELETE sur cette
-- table : la version la plus recente (date_consentement, puis id) fait foi.
-- Les lignes existantes restent valides : colonnes nouvelles a NULL =
-- pas de limite de duree, tous destinataires, aucune categorie exclue.
-- ============================================================================

-- 1. Nouvelles colonnes -------------------------------------------------------
DECLARE
  PROCEDURE ajouter(p_def VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE consentement ADD (' || p_def || ')';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLCODE != -1430 THEN RAISE; END IF;   -- ORA-01430 : colonne deja presente
  END;
BEGIN
  ajouter('date_debut         DATE');
  ajouter('date_fin           DATE');
  ajouter('destinataires      VARCHAR2(20)');   -- ex. 'H2' ; NULL = tous les partenaires
  ajouter('categories_exclues VARCHAR2(100)');  -- ex. 'imagerie,comptes_rendus'
  ajouter('signataire         VARCHAR2(20)');   -- PATIENT | REPRESENTANT_LEGAL
  ajouter('recueilli_par      VARCHAR2(100)');  -- agent qui a recueilli le consentement
  ajouter('date_retrait       DATE');
  ajouter('motif_retrait      VARCHAR2(300)');
END;
/

-- 2. Statut RETIRE --------------------------------------------------------------
-- La contrainte d'origine porte un nom genere (SYS_C...) : on la retrouve par
-- sa colonne, puis on la remplace par une contrainte nommee.
BEGIN
  FOR c IN (SELECT uc.constraint_name
              FROM user_constraints uc
              JOIN user_cons_columns ucc ON ucc.constraint_name = uc.constraint_name
             WHERE uc.table_name = 'CONSENTEMENT' AND uc.constraint_type = 'C'
               AND ucc.column_name = 'STATUT' AND uc.constraint_name != 'CK_CONSENTEMENT_STATUT'
               AND uc.search_condition_vc NOT LIKE '%IS NOT NULL%') LOOP
    EXECUTE IMMEDIATE 'ALTER TABLE consentement DROP CONSTRAINT ' || c.constraint_name;
  END LOOP;
  EXECUTE IMMEDIATE q'[ALTER TABLE consentement ADD CONSTRAINT ck_consentement_statut
                        CHECK (statut IN ('ACTIF', 'REFUSE', 'RETIRE'))]';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -2264 THEN RAISE; END IF;     -- ORA-02264 : contrainte deja presente
END;
/

-- 3. Journal : sens CONSENTEMENT -------------------------------------------
ALTER TABLE journal_echange MODIFY (sens VARCHAR2(12));

BEGIN
  FOR c IN (SELECT uc.constraint_name
              FROM user_constraints uc
              JOIN user_cons_columns ucc ON ucc.constraint_name = uc.constraint_name
             WHERE uc.table_name = 'JOURNAL_ECHANGE' AND uc.constraint_type = 'C'
               AND ucc.column_name = 'SENS' AND uc.constraint_name != 'CK_JOURNAL_SENS'
               AND uc.search_condition_vc NOT LIKE '%IS NOT NULL%') LOOP
    EXECUTE IMMEDIATE 'ALTER TABLE journal_echange DROP CONSTRAINT ' || c.constraint_name;
  END LOOP;
  EXECUTE IMMEDIATE q'[ALTER TABLE journal_echange ADD CONSTRAINT ck_journal_sens
                        CHECK (sens IN ('ALLER', 'RETOUR', 'CONSENTEMENT'))]';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -2264 THEN RAISE; END IF;
END;
/

-- 4. Verification ---------------------------------------------------------------
-- Consentement en vigueur de chaque patient et decision de partage brute
-- (la periode et les destinataires sont evalues par l'API).
SELECT ipp, id_consentement, statut, date_debut, date_fin, destinataires, categories_exclues
  FROM (SELECT c.*, ROW_NUMBER() OVER (PARTITION BY ipp
                 ORDER BY date_consentement DESC NULLS LAST, id_consentement DESC) AS rang
          FROM consentement c)
 WHERE rang = 1
 ORDER BY ipp;
