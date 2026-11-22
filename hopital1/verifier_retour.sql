-- Verification en lecture seule apres import du retour fictif de Youssef.
SET PAGESIZE 100
SET LINESIZE 140
WHENEVER SQLERROR EXIT SQL.SQLCODE
COLUMN TABLE_NOM FORMAT A22
SELECT 'SEJOUR_RETOUR' AS TABLE_NOM, COUNT(*) AS NB_LIGNES FROM sejour
 WHERE ipp = 'P1-0106' AND id_externe = 'V-2026-1020-01'
UNION ALL SELECT 'DIAGNOSTIC_RETOUR', COUNT(*) FROM diagnostic d JOIN sejour s ON s.id_sejour = d.id_sejour
 WHERE s.ipp = 'P1-0106' AND s.id_externe = 'V-2026-1020-01'
UNION ALL SELECT 'MESURE_RETOUR', COUNT(*) FROM mesure m JOIN sejour s ON s.id_sejour = m.id_sejour
 WHERE s.ipp = 'P1-0106' AND s.id_externe = 'V-2026-1020-01'
UNION ALL SELECT 'RESULTAT_OPHTALMO', COUNT(*) FROM resultat_ophtalmo WHERE ipp = 'P1-0106'
UNION ALL SELECT 'ETUDE_IMAGERIE', COUNT(*) FROM etude_imagerie WHERE ipp = 'P1-0106'
UNION ALL SELECT 'COMPTE_RENDU', COUNT(*) FROM compte_rendu WHERE ipp = 'P1-0106';
PROMPT === Derniers imports du patient ===
SELECT id_journal, date_echange, sens, statut FROM journal_echange
 WHERE ipp = 'P1-0106' AND sens = 'RETOUR'
 ORDER BY id_journal DESC FETCH FIRST 5 ROWS ONLY;
EXIT SUCCESS
