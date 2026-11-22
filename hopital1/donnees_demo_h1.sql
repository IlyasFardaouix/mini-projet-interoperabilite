-- Jeu de demonstration FICTIF du CHU (aucune donnee reelle) : memes cas que
-- tests/donnees.py. A executer apres les trois schemas : python initialiser_base_h1.py --donnees
-- S1 : patient nominal, consentement actif. D1 : consentement refuse (export 403).

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0106', 'Alaoui', 'Youssef', 'M', TO_DATE('12/04/1968','DD/MM/YYYY'), 'AB123456', '06 12 34 56 78', 'N°1, Rue Test', 'Settat', 'A+');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0106', 'P1-0106', 'ACTIF', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0106-1', 'P1-0106', 'CONS', 'Endocrinologie', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'), 'Dr Bennani', 'Suivi diabète type 2');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0106-1', 'ST-0106-1', 'Diabète de type 2', 'DIAB2', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0106-1', 'ST-0106-1', 'TA_SYS', 138, 'mm[Hg]', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0106-2', 'ST-0106-1', 'TA_DIA', 85, 'mm[Hg]', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0106-3', 'ST-0106-1', 'HBA1C', 8.2, '%', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0106-4', 'ST-0106-1', 'GLY', 1.60, 'g/L', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'));
INSERT INTO allergie (id_allergie, ipp, code_allergene, libelle, criticite)
VALUES ('ALT-0106-1', 'P1-0106', 'ALL_FLUO', 'Fluorescéine', 'ELEVEE');

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0108', 'Idrissi', 'Omar', 'M', TO_DATE('17/02/1990','DD/MM/YYYY'), 'J778241', '06 34 56 78 90', 'N°1, Rue Test', 'Rabat', 'B+');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0108', 'P1-0108', 'REFUSE', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0108-1', 'P1-0108', 'CONS', 'Médecine interne', TO_DATE('05/10/2026 09:00','DD/MM/YYYY HH24:MI'), 'Dr Tazi', 'Céphalées');

-- Patients supplementaires pour la demonstration (noms tous differents de ceux de la clinique ;
-- IPP < P1-0108 pour que le prochain IPP attribue reste P1-0109). P1-0104 : refus ; P1-0107 : aucun consentement.

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0101', 'Hajji', 'Samira', 'F', TO_DATE('14/03/1982','DD/MM/YYYY'), 'HA204518', '06 61 20 45 18', 'N°1, Rue Test', 'Casablanca', 'A+');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0101', 'P1-0101', 'ACTIF', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0101-1', 'P1-0101', 'CONS', 'Cardiologie', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'), 'Dr Bennani', 'Suivi hypertension');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0101-1', 'ST-0101-1', 'Hypertension artérielle essentielle', 'HTA', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0101-1', 'ST-0101-1', 'TA_SYS', 152, 'mm[Hg]', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0101-2', 'ST-0101-1', 'TA_DIA', 94, 'mm[Hg]', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0101-3', 'ST-0101-1', 'FC', 78, '/min', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0102', 'Kadiri', 'Mehdi', 'M', TO_DATE('02/11/1975','DD/MM/YYYY'), 'KB311907', '06 62 31 19 07', 'N°1, Rue Test', 'Fès', 'O+');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0102', 'P1-0102', 'ACTIF', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0102-1', 'P1-0102', 'CONS', 'Pneumologie', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'), 'Dr Tazi', 'Dyspnée d''effort');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0102-1', 'ST-0102-1', 'Bronchopneumopathie chronique obstructive', 'BPCO', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0102-1', 'ST-0102-1', 'SPO2', 92, '%', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0102-2', 'ST-0102-1', 'FC', 88, '/min', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0103', 'Lazrak', 'Nadia', 'F', TO_DATE('21/06/1990','DD/MM/YYYY'), 'LC558204', '06 63 55 82 04', 'N°1, Rue Test', 'Marrakech', 'B-');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0103', 'P1-0103', 'ACTIF', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0103-1', 'P1-0103', 'CONS', 'Endocrinologie', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'), 'Dr Bennani', 'Fatigue, bilan thyroïdien');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0103-1', 'ST-0103-1', 'Hypothyroïdie', 'HYPOT', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0103-1', 'ST-0103-1', 'FC', 64, '/min', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0103-2', 'ST-0103-1', 'GLY', 0.92, 'g/L', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0104', 'Maaroufi', 'Anas', 'M', TO_DATE('30/01/1958','DD/MM/YYYY'), 'M114265', '06 64 11 42 65', 'N°1, Rue Test', 'Rabat', 'AB-');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0104', 'P1-0104', 'REFUSE', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0104-1', 'P1-0104', 'CONS', 'Cardiologie', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'), 'Dr Tazi', 'Essoufflement au repos');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0104-1', 'ST-0104-1', 'Insuffisance cardiaque', 'IC', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0104-1', 'ST-0104-1', 'TA_SYS', 118, 'mm[Hg]', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0104-2', 'ST-0104-1', 'FC', 96, '/min', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0105', 'Nejjar', 'Hind', 'F', TO_DATE('09/09/1968','DD/MM/YYYY'), 'N902316', '06 65 90 23 16', 'N°1, Rue Test', 'Tanger', 'AB+');
INSERT INTO consentement (id_consentement, ipp, statut, finalite, date_consentement)
VALUES ('CST-0105', 'P1-0105', 'ACTIF', 'Partage soins', TO_DATE('01/10/2026','DD/MM/YYYY'));
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0105-1', 'P1-0105', 'CONS', 'Néphrologie', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'), 'Dr Bennani', 'Contrôle de la fonction rénale');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0105-1', 'ST-0105-1', 'Insuffisance rénale chronique', 'IRC', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0105-1', 'ST-0105-1', 'TA_SYS', 146, 'mm[Hg]', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0105-2', 'ST-0105-1', 'TA_DIA', 88, 'mm[Hg]', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));

INSERT INTO patient (ipp, nom, prenom, sexe, date_naissance, cin, telephone, adresse, ville, groupe_sanguin)
VALUES ('P1-0107', 'Qadiri', 'Reda', 'M', TO_DATE('12/12/1995','DD/MM/YYYY'), 'Q447780', '06 67 44 77 80', 'N°1, Rue Test', 'Agadir', 'A-');
INSERT INTO sejour (id_sejour, ipp, type_sejour, service, date_admission, medecin, motif)
VALUES ('ST-0107-1', 'P1-0107', 'CONS', 'Médecine interne', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'), 'Dr Tazi', 'Anémie à explorer');
INSERT INTO diagnostic (id_diagnostic, id_sejour, libelle, code_local, date_diagnostic)
VALUES ('DGT-0107-1', 'ST-0107-1', 'Anémie', 'ANEM', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));
INSERT INTO mesure (id_mesure, id_sejour, code_local, valeur, unite, date_mesure)
VALUES ('MST-0107-1', 'ST-0107-1', 'FC', 72, '/min', TO_DATE('06/10/2026 10:00','DD/MM/YYYY HH24:MI'));

COMMIT;
