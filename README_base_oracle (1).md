# Base de données — Hôpital 1 (CHU Al Massira) — Oracle

Base relationnelle du **CHU public** (émetteur) du projet d'interopérabilité des DME via HL7 FHIR.
**Données 100 % fictives.** Responsable : Chaimae (Trinôme 1 / Hôpital 1).

## Contenu

- **6 tables** : `patient`, `sejour`, `diagnostic`, `mesure`, `allergie`, `consentement`.
- **120 patients** fictifs (noms, villes marocaines, sans accents).
- Dont **5 patients partagés** avec la clinique (H2), rapprochables par le **CIN**.
- Dont **15 cas de test** (P1-0106 → P1-0120) couvrant les scénarios nominaux et dégradés (voir `cas_de_test.csv`).

> Remarque importante : certaines données sont **volontairement invalides** (SpO2 à 150, date de sortie avant l'admission, glycémie sans unité, date de naissance manquante…). Ce n'est pas une erreur : c'est le **connecteur FHIR** qui doit les détecter, pas la base.

## Prérequis

- **Docker** installé et lancé.
- **DBeaver** (recommandé) pour consulter la base.

## Installation (à faire une fois)

```bash
# 1. Récupérer l'image Oracle Free
docker pull container-registry.oracle.com/database/free:latest

# 2. Lancer le conteneur (choisir votre propre mot de passe admin)
docker run -d --name oracle-h1 -p 1521:1521 -e ORACLE_PWD=MonMotDePasse123 container-registry.oracle.com/database/free:latest

# 3. Attendre le message "DATABASE IS READY TO USE!"
docker logs -f oracle-h1
```

```bash
# 4. Créer le schéma de travail hopital1
docker exec -it oracle-h1 sqlplus system/MonMotDePasse123@localhost:1521/FREEPDB1
```
Au prompt SQL> :
```sql
CREATE USER hopital1 IDENTIFIED BY hopital1pwd;
GRANT CONNECT, RESOURCE TO hopital1;
ALTER USER hopital1 QUOTA UNLIMITED ON USERS;
EXIT;
```

## Charger les données

```bash
# copier puis exécuter le script (contient structure + données + cas de test)
docker cp hopital1_oracle.sql oracle-h1:/tmp/
docker exec -it oracle-h1 sqlplus hopital1/hopital1pwd@localhost:1521/FREEPDB1 @/tmp/hopital1_oracle.sql
```

## Vérifier

```sql
SELECT COUNT(*) FROM patient;    -- 120
SELECT COUNT(*) FROM sejour;
SELECT COUNT(*) FROM mesure;
SELECT * FROM patient WHERE ipp BETWEEN 'P1-0106' AND 'P1-0120';  -- les 15 cas de test
```

## Se connecter avec DBeaver

Nouvelle connexion **Oracle** :
- Host `localhost` · Port `1521` · **Service Name** `FREEPDB1`
- Utilisateur `hopital1` · Mot de passe `hopital1pwd`

## Se connecter en Python (pour l'adaptateur Oracle → FHIR)

```bash
pip install oracledb
```
```python
import oracledb
cn = oracledb.connect(user="hopital1", password="hopital1pwd",
                      dsn="localhost:1521/FREEPDB1")
cur = cn.cursor()
cur.execute("SELECT ipp, nom, prenom, sexe, cin FROM patient WHERE ipp = :1", ["P1-0106"])
print(cur.fetchone())
```

## Fichiers du dossier

| Fichier | Rôle |
|---|---|
| `hopital1_oracle.sql` | Crée et remplit toute la base (structure + 120 patients + 15 cas de test + allergies). |
| `correspondances_codes.csv` | **Table de mapping** codes locaux ↔ FHIR (LOINC, CIM-10, SNOMED, UCUM). Indispensable pour l'adaptateur FHIR. |
| `cas_de_test.csv` | Les 16 cas de test (plan de validation commun aux deux hôpitaux). |

## Convention d'identifiants

- `ipp` : identifiant patient local (ex. `P1-0106`).
- `cin` : identifiant national — c'est **la clé de rapprochement** avec la clinique (H2).
