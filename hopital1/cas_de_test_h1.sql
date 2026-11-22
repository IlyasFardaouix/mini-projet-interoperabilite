-- Cas de test Hôpital 1 (Oracle) — à exécuter sur la connexion hopital1
-- Crée la table allergie + remplace les patients P1-0106..P1-0120 par les cas de test.
SET DEFINE OFF;
BEGIN EXECUTE IMMEDIATE 'DROP TABLE allergie CASCADE CONSTRAINTS'; EXCEPTION WHEN OTHERS THEN NULL; END;
/
CREATE TABLE allergie (
  id_allergie VARCHAR2(16) PRIMARY KEY,
  ipp         VARCHAR2(12) REFERENCES patient(ipp),
  code_local  VARCHAR2(20),
  libelle     VARCHAR2(80),
  criticite   VARCHAR2(10) CHECK (criticite IN ('ELEVEE','FAIBLE')));
DELETE FROM mesure     WHERE id_sejour IN (SELECT id_sejour FROM sejour WHERE ipp BETWEEN 'P1-0106' AND 'P1-0120');
DELETE FROM diagnostic WHERE id_sejour IN (SELECT id_sejour FROM sejour WHERE ipp BETWEEN 'P1-0106' AND 'P1-0120');
DELETE FROM sejour       WHERE ipp BETWEEN 'P1-0106' AND 'P1-0120';
DELETE FROM consentement WHERE ipp BETWEEN 'P1-0106' AND 'P1-0120';
DELETE FROM patient      WHERE ipp BETWEEN 'P1-0106' AND 'P1-0120';


-- S1 P1-0106 Youssef Alaoui — nominal, allergie fluorescéine transmise
INSERT INTO patient VALUES ('P1-0106','Alaoui','Youssef','M',TO_DATE('12/04/1968','DD/MM/YYYY'),'AB123456','06 12 34 56 78','N°12, Rue Alaoui, Hay Riad','Settat','A+');
INSERT INTO consentement VALUES ('CST-0106','P1-0106','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0106-1','P1-0106','CONS','Endocrinologie',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'),NULL,'Dr Bennani','Suivi diabète type 2');
INSERT INTO diagnostic VALUES ('DGT-0106-1','ST-0106-1','Diabète de type 2','DIAB2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0106-1','ST-0106-1','TA_SYS',138,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0106-2','ST-0106-1','TA_DIA',85,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0106-3','ST-0106-1','HBA1C',8.2,'%',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0106-4','ST-0106-1','GLY',1.6,'g/L',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO allergie VALUES ('ALT-0106-1','P1-0106','ALL_FLUO','Fluorescéine','ELEVEE');

-- S2 P1-0107 Fatima Bennani — HTA (alerte PIO au retour, côté H2)
INSERT INTO patient VALUES ('P1-0107','Bennani','Fatima','F',TO_DATE('30/09/1975','DD/MM/YYYY'),'K445120','06 23 45 67 89','N°45, Avenue Hassan II, Maârif','Casablanca','O+');
INSERT INTO consentement VALUES ('CST-0107','P1-0107','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0107-1','P1-0107','CONS','Médecine interne',TO_DATE('05/10/2026 10:00','DD/MM/YYYY HH24:MI'),NULL,'Dr Idrissi','Suivi hypertension');
INSERT INTO diagnostic VALUES ('DGT-0107-1','ST-0107-1','Hypertension artérielle essentielle','HTA',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0107-1','ST-0107-1','TA_SYS',165,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0107-2','ST-0107-1','TA_DIA',98,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0107-3','ST-0107-1','FC',88,'/min',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D1 P1-0108 Omar Idrissi — consentement REFUSE (aller bloqué, 403)
INSERT INTO patient VALUES ('P1-0108','Idrissi','Omar','M',TO_DATE('17/02/1990','DD/MM/YYYY'),'J778241','06 34 56 78 90','N°8, Rue des Écoles, Agdal','Rabat','B+');
INSERT INTO consentement VALUES ('CST-0108','P1-0108','REFUSE','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0108-1','P1-0108','CONS','Médecine interne',TO_DATE('05/10/2026 08:30','DD/MM/YYYY HH24:MI'),NULL,'Dr Tazi','Céphalées');
INSERT INTO diagnostic VALUES ('DGT-0108-1','ST-0108-1','Migraine','MIG',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0108-1','ST-0108-1','TA_SYS',120,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0108-2','ST-0108-1','FC',76,'/min',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D2 P1-0109 Salma Tazi — consentement H1 ACTIF (refus côté H2 au retour)
INSERT INTO patient VALUES ('P1-0109','Tazi','Salma','F',TO_DATE('05/06/1959','DD/MM/YYYY'),'T220145','06 45 67 89 01','N°30, Bd Zerktouni, Gueliz','Marrakech','O+');
INSERT INTO consentement VALUES ('CST-0109','P1-0109','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0109-1','P1-0109','CONS','Endocrinologie',TO_DATE('05/10/2026 09:15','DD/MM/YYYY HH24:MI'),NULL,'Dr Alaoui','Suivi diabète type 2');
INSERT INTO diagnostic VALUES ('DGT-0109-1','ST-0109-1','Diabète de type 2','DIAB2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0109-1','ST-0109-1','GLY',1.9,'g/L',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0109-2','ST-0109-1','HBA1C',7.5,'%',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D3 P1-0110 Karim Berrada — groupe sanguin A+ (conflit avec A- en H2)
INSERT INTO patient VALUES ('P1-0110','Berrada','Karim','M',TO_DATE('21/11/1982','DD/MM/YYYY'),'B334091','06 56 78 90 12','N°102, Rue Ibn Sina, Hay Nahda','Fès','A+');
INSERT INTO consentement VALUES ('CST-0110','P1-0110','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0110-1','P1-0110','CONS','Endocrinologie',TO_DATE('05/10/2026 11:00','DD/MM/YYYY HH24:MI'),NULL,'Dr Bennani','Suivi diabète type 2');
INSERT INTO diagnostic VALUES ('DGT-0110-1','ST-0110-1','Diabète de type 2','DIAB2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0110-1','ST-0110-1','GLY',2.1,'g/L',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0110-2','ST-0110-1','HBA1C',9.0,'%',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- S3 P1-0111 Nadia Chraibi — création nouveau dossier en H2 (absente de H2)
INSERT INTO patient VALUES ('P1-0111','Chraibi','Nadia','F',TO_DATE('08/03/1980','DD/MM/YYYY'),'NC556677','06 67 89 01 23','N°17, Rue de Fès, Hay Salam','Kénitra','O+');
INSERT INTO consentement VALUES ('CST-0111','P1-0111','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0111-1','P1-0111','CONS','Cardiologie',TO_DATE('05/10/2026 09:45','DD/MM/YYYY HH24:MI'),NULL,'Dr Idrissi','Contrôle tension');
INSERT INTO diagnostic VALUES ('DGT-0111-1','ST-0111-1','Hypertension artérielle essentielle','HTA',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0111-1','ST-0111-1','TA_SYS',150,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0111-2','ST-0111-1','TA_DIA',95,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D4 P1-0112 Rachid Ouazzani — CIN ABSENT (match probabiliste par traits)
INSERT INTO patient VALUES ('P1-0112','Ouazzani','Rachid','M',TO_DATE('25/07/1972','DD/MM/YYYY'),NULL,'06 78 90 12 34','N°5, Avenue Mohammed V, Centre','Tanger','A+');
INSERT INTO consentement VALUES ('CST-0112','P1-0112','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0112-1','P1-0112','CONS','Médecine interne',TO_DATE('05/10/2026 10:30','DD/MM/YYYY HH24:MI'),NULL,'Dr Tazi','Suivi diabète type 2');
INSERT INTO diagnostic VALUES ('DGT-0112-1','ST-0112-1','Diabète de type 2','DIAB2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0112-1','ST-0112-1','GLY',1.5,'g/L',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D5 P1-0113 Youcef El Fassi — même CIN EF889900 (H2 : Elfassi Youssef)
INSERT INTO patient VALUES ('P1-0113','El Fassi','Youcef','M',TO_DATE('19/01/1988','DD/MM/YYYY'),'EF889900','06 89 01 23 45','N°22, Rue Al Qods, Dakhla','Agadir','B+');
INSERT INTO consentement VALUES ('CST-0113','P1-0113','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0113-1','P1-0113','CONS','Endocrinologie',TO_DATE('05/10/2026 08:45','DD/MM/YYYY HH24:MI'),NULL,'Dr Alaoui','Suivi diabète type 2');
INSERT INTO diagnostic VALUES ('DGT-0113-1','ST-0113-1','Diabète de type 2','DIAB2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0113-1','ST-0113-1','GLY',1.7,'g/L',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D6 P1-0114 Khadija Amrani — homonyme (même nom/naissance, CIN différent de H2)
INSERT INTO patient VALUES ('P1-0114','Amrani','Khadija','F',TO_DATE('14/03/1979','DD/MM/YYYY'),'KA112233','06 90 12 34 56','N°60, Bd Anfa, Racine','Oujda','O+');
INSERT INTO consentement VALUES ('CST-0114','P1-0114','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0114-1','P1-0114','CONS','Cardiologie',TO_DATE('05/10/2026 11:15','DD/MM/YYYY HH24:MI'),NULL,'Dr Bennani','Contrôle tension');
INSERT INTO diagnostic VALUES ('DGT-0114-1','ST-0114-1','Hypertension artérielle essentielle','HTA',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0114-1','ST-0114-1','TA_SYS',145,'mm[Hg]',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D7 P1-0115 Yasmine Lahlou — MINEURE 16 ans, pas de CIN (consentement rep. légal)
INSERT INTO patient VALUES ('P1-0115','Lahlou','Yasmine','F',TO_DATE('06/09/2010','DD/MM/YYYY'),NULL,'06 11 22 33 44','N°3, Rue Ibn Battouta, Centre','Salé','O+');
INSERT INTO consentement VALUES ('CST-0115','P1-0115','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0115-1','P1-0115','CONS','Médecine interne',TO_DATE('05/10/2026 09:20','DD/MM/YYYY HH24:MI'),NULL,'Dr Idrissi','Asthme');
INSERT INTO diagnostic VALUES ('DGT-0115-1','ST-0115-1','Asthme','ASTM',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0115-1','ST-0115-1','SPO2',97,'%',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D8 P1-0116 Mehdi Kettani — date de naissance MANQUANTE (rejet par le profil)
INSERT INTO patient VALUES ('P1-0116','Kettani','Mehdi','M',NULL,'MK445566','06 22 33 44 55','N°14, Avenue des FAR, Centre','Meknès','A+');
INSERT INTO consentement VALUES ('CST-0116','P1-0116','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0116-1','P1-0116','CONS','Médecine interne',TO_DATE('05/10/2026 10:10','DD/MM/YYYY HH24:MI'),NULL,'Dr Tazi','Contrôle tension');
INSERT INTO diagnostic VALUES ('DGT-0116-1','ST-0116-1','Hypertension artérielle essentielle','HTA',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));

-- D9 P1-0117 Hassan Sebti — code local INCONNU 'DT2' (non normalisé)
INSERT INTO patient VALUES ('P1-0117','Sebti','Hassan','M',TO_DATE('11/11/1970','DD/MM/YYYY'),'HS778899','06 33 44 55 66','N°9, Rue Tarik, Wilaya','Tétouan','O+');
INSERT INTO consentement VALUES ('CST-0117','P1-0117','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0117-1','P1-0117','CONS','Endocrinologie',TO_DATE('05/10/2026 08:50','DD/MM/YYYY HH24:MI'),NULL,'Dr Alaoui','Diabète (saisie libre)');
INSERT INTO diagnostic VALUES ('DGT-0117-1','ST-0117-1','Diabete type 2 (saisie non normalisee)','DT2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0117-1','ST-0117-1','GLY',1.8,'g/L',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D10 P1-0118 Latifa Naciri — glycémie SANS unité (Observation rejetée)
INSERT INTO patient VALUES ('P1-0118','Naciri','Latifa','F',TO_DATE('23/04/1985','DD/MM/YYYY'),'LN223344','06 44 55 66 77','N°27, Rue Oued Ziz, Hay Riad','Béni Mellal','O+');
INSERT INTO consentement VALUES ('CST-0118','P1-0118','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0118-1','P1-0118','CONS','Endocrinologie',TO_DATE('05/10/2026 09:35','DD/MM/YYYY HH24:MI'),NULL,'Dr Bennani','Suivi diabète type 2');
INSERT INTO diagnostic VALUES ('DGT-0118-1','ST-0118-1','Diabète de type 2','DIAB2',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0118-1','ST-0118-1','GLY',1.45,NULL,TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D11 P1-0119 Adil Zniber — SpO2 = 150 % (valeur impossible, rejet plausibilité)
INSERT INTO patient VALUES ('P1-0119','Zniber','Adil','M',TO_DATE('30/12/1978','DD/MM/YYYY'),'AZ990011','06 55 66 77 88','N°41, Bd Mohammed VI, Centre','Nador','A+');
INSERT INTO consentement VALUES ('CST-0119','P1-0119','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0119-1','P1-0119','URG','Urgences',TO_DATE('05/10/2026 07:40','DD/MM/YYYY HH24:MI'),NULL,'Dr Idrissi','Dyspnée');
INSERT INTO diagnostic VALUES ('DGT-0119-1','ST-0119-1','Pneumonie','PNM',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0119-1','ST-0119-1','SPO2',150,'%',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0119-2','ST-0119-1','FC',110,'/min',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

-- D12 P1-0120 Samira Tahiri — date de sortie ANTÉRIEURE à l'admission (Encounter invalide)
INSERT INTO patient VALUES ('P1-0120','Tahiri','Samira','F',TO_DATE('17/08/1991','DD/MM/YYYY'),'ST334455','06 66 77 88 99','N°53, Rue Ibn Rochd, Centre','Mohammedia','O+');
INSERT INTO consentement VALUES ('CST-0120','P1-0120','ACTIF','Continuité des soins',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO sejour VALUES ('ST-0120-1','P1-0120','URG','Urgences',TO_DATE('05/10/2026 10:00','DD/MM/YYYY HH24:MI'),TO_DATE('03/10/2026 09:00','DD/MM/YYYY HH24:MI'),'Dr Tazi','Crise d''asthme');
INSERT INTO diagnostic VALUES ('DGT-0120-1','ST-0120-1','Asthme','ASTM',TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure VALUES ('MST-0120-1','ST-0120-1','SPO2',93,'%',TO_DATE('05/10/2026 09:30','DD/MM/YYYY HH24:MI'));

COMMIT;