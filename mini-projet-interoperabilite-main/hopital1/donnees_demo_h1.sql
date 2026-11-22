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

COMMIT;
