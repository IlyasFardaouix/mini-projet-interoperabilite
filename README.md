# Mini-projet interopérabilité — CHU Al Massira ⇄ Clinique Al Baçar
 
Échange de dossiers patients entre deux établissements aux systèmes différents,
par **Bundles FHIR R5 (5.0.0)** sur HTTPS, avec une interface de démonstration
dans le navigateur.
 
| | Hôpital 1 | Hôpital 2 |
| --- | --- | --- |
| Établissement | CHU Al Massira | Clinique Al Baçar (ophtalmologie) |
| Base | Oracle | MongoDB |
| API | FastAPI, port 8000 | FastAPI, port 8002 |
| Imagerie (PACS Orthanc) | port 8043 | port 8042 |
| Interface | `https://127.0.0.1:8000/ui/` | `https://127.0.0.1:8002/ui/` |
| Dossier | [`hopital1/`](hopital1/) | [`hopital2/`](hopital2/) |
 
Les deux établissements **envoient et reçoivent** : le CHU transmet le dossier
d'un patient adressé à la clinique, la clinique renvoie ses résultats, son
imagerie et ses comptes rendus.
 
```
Oracle ──► API H1 ──HTTPS──► API H2 ──► MongoDB
MongoDB ──► API H2 ──HTTPS──► API H1 ──► Oracle
```
 
---
 
## Sommaire
 
1. [Organisation du dépôt](#organisation-du-dépôt)
2. [Installation complète, de zéro](#installation-complète-de-zéro)
3. [Interface de démonstration](#interface-de-démonstration)
4. [Contrat d'échange](#contrat-déchange)
5. [Sécurité](#sécurité)
6. [Tests](#tests)
7. [Problèmes fréquents](#problèmes-fréquents)
8. [État d'avancement](#état-davancement-et-travail-restant)
---
 
## Organisation du dépôt
 
| Partie | Rôle | Commencer par |
| --- | --- | --- |
| [`hopital1/`](hopital1/) | CHU : Oracle, adaptateurs FHIR, API d'export et de réception | [`hopital1/README.md`](hopital1/README.md) |
| [`hopital2/`](hopital2/) | Clinique : MongoDB, adaptateurs FHIR, API et client d'envoi | [`hopital2/LISEZMOI.md`](hopital2/LISEZMOI.md) |
| [`interface/`](interface/) | Interface web commune (démonstration et connexion du personnel) | [`docs/interface.md`](docs/interface.md) |
| [`securite/`](securite/) | Authentification, HTTPS, audit et protections HTTP des deux API | [`securite/README.md`](securite/README.md) |
| [`imagerie/`](imagerie/) | Images DICOM : PACS Orthanc, passerelle DICOMweb sécurisée, désidentification | [`docs/imagerie.md`](docs/imagerie.md) |
| [`docs/`](docs/) | Architecture, avancement et procédures communes | [`docs/architecture-et-contributions.md`](docs/architecture-et-contributions.md) |
 
Le [plan détaillé du dépôt](docs/architecture-et-contributions.md) indique les
fichiers principaux, les tests et les responsabilités de chaque lot. Les noms
des responsables H1 et H2 restent à confirmer par l'équipe : un commit Git peut
regrouper le travail de plusieurs personnes.
 
Chaque service garde ses modules **à plat** dans son dossier : ils s'importent
entre eux par leur nom (`import config as C`, `import oracle_repo as repo`) et
se lancent depuis ce dossier. Les packages `securite/` et `interface/` vivent à
la racine parce qu'ils sont partagés par les deux hôpitaux.
 
---
 
## Installation complète, de zéro
 
Tout se fait dans **PowerShell**, sur un seul poste. Les commandes partent de la
racine du dépôt (le dossier qui contient `hopital1`, `hopital2`, `securite`).
Les étapes 5 et 6 (Oracle, MongoDB, Orthanc) demandent Docker et quelques minutes.
### Base Oracle du CHU

Deux jeux de données au choix (n'en exécuter qu'un seul) :

- **Base de référence** (120 patients, 15 cas de test) : `hopital1/hopital1_oracle.sql` puis `hopital1/cas_de_test_h1.sql`
- **Démonstration rapide** (8 patients) : `hopital1/schema_base_h1.sql` puis `hopital1/donnees_demo_h1.sql`

Ensuite, dans les deux cas : `hopital1/schema_retour_h1.sql` puis `hopital1/schema_consentement_h1.sql`.

Si un conteneur `oracle-h1` contient déjà la base de référence, le démarrer avec `docker start oracle-h1` au lieu de `docker compose up`.

Le code H1 a été validé sur la base de référence : 118 tests simulés, 16 tests sur un vrai Oracle (`tests/test_oracle_reel.py`, à lancer uniquement sur un compte de test séparé, car il recrée les tables), export et import réels.
 
### 1. Outils à installer
 
Docker Desktop (démarré, avec au moins 4 Go de mémoire alloués), Python 3.12 ou
plus récent avec « Add to PATH », et un navigateur. Git n'est pas nécessaire.
 
### 2. Environnement Python et dépendances
 
```powershell
cd <racine du dépôt>
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r securite/requirements.txt -r hopital1/requirements.txt -r hopital2/requirements.txt
```
 
### 3. Jetons, certificats et garde-fou de commit
 
```powershell
.\.venv\Scripts\python.exe securite/outils/generer_jetons.py
.\.venv\Scripts\python.exe securite/outils/generer_certificats.py --ip 127.0.0.1
.\.venv\Scripts\python.exe securite/outils/installer_hooks.py
```
 
Pour joindre le poste depuis une autre machine, remplacez `127.0.0.1` par
l'adresse IP du poste, ici et dans les adresses de l'étape 4.
 
### 4. Les deux fichiers `.env`
 
Chaque API charge automatiquement son `.env` (`hopital1\.env`, `hopital2\.env`) :
il n'y a rien à exporter dans chaque fenêtre. Changez les mots de passe des
quatre premières lignes avant de lancer le bloc. Il construit les deux fichiers
à partir des jetons générés à l'étape 3 et crée la clé de chiffrement de la
file d'envoi du CHU (`H1_CLE_CHIFFREMENT`).
 
```powershell
$R = (Get-Location).Path
$J = "$R\securite\jetons_locaux"
function Jeton($n) { (Get-Content "$J\$n.txt" -Raw).Trim() }
function Secrets($f) { (Get-Content "$J\$f" | Where-Object { $_.Trim() -and $_ -notmatch '^\s*#' }) -join "`n" }
$OraAdmin = "Admin_Oracle_ChangeMoi1"; $OraApp = "Hopital1_ChangeMoi1"
$MongoU = "hopital2"; $MongoP = "Mongo_ChangeMoi1"
$OrtU = "pacs"; $OrtP = "Pacs_ChangeMoi1"
 
# clé de chiffrement de la file d'envoi du CHU (à conserver : sans elle, les envois en attente sont illisibles)
$env:PYTHONPATH = $R
$CleH1 = (& "$R\.venv\Scripts\python.exe" -c "from securite.chiffrement import nouvelle_cle; print(nouvelle_cle())").Trim()
 
@"
$(Secrets 'env.h1')
SEC_CA=$R\securite\certificats\ac_interop.cert.pem
DEMO=1
H1_CLE_CHIFFREMENT=$CleH1
ORACLE_USER=hopital1
ORACLE_PWD=$OraApp
ORACLE_ADMIN_PWD=$OraAdmin
ORACLE_DSN=localhost:1521/FREEPDB1
H1_BASE_URL=https://127.0.0.1:8000
H2_BASE_URL=https://127.0.0.1:8002
H1_JETON_VERS_H2=$(Jeton 'h1-chu')
H1_JETON_LOCAL=$(Jeton 'h1-interne')
H1_ORTHANC_URL=http://127.0.0.1:8043/dicom-web
H1_ORTHANC_UTILISATEUR=$OrtU
H1_ORTHANC_MOT_DE_PASSE=$OrtP
H1_DICOMWEB_URL=https://127.0.0.1:8000/dicom-web
H2_DICOMWEB_URL=https://127.0.0.1:8002/dicom-web
"@ | Set-Content "$R\hopital1\.env" -Encoding utf8
 
@"
$(Secrets 'env.h2')
SEC_CA=$R\securite\certificats\ac_interop.cert.pem
DEMO=1
MONGO_UTILISATEUR=$MongoU
MONGO_MOT_DE_PASSE=$MongoP
MONGO_DB=hopital2
H1_BASE_URL=https://127.0.0.1:8000
H2_BASE_URL=https://127.0.0.1:8002
H1_API_TOKEN=$(Jeton 'h2-clinique')
H2_JETON_LOCAL=$(Jeton 'h2-interne')
H2_ORTHANC_URL=http://127.0.0.1:8042/dicom-web
H2_ORTHANC_UTILISATEUR=$OrtU
H2_ORTHANC_MOT_DE_PASSE=$OrtP
H2_DICOMWEB_URL=https://127.0.0.1:8002/dicom-web
FHIR_BASE_URL=https://127.0.0.1:8002/fhir
"@ | Set-Content "$R\hopital2\.env" -Encoding utf8
```
 
Notes :
- `DEMO=1` active l'interface de démonstration (voir plus bas). Sans elle,
  `/ui/` affiche la connexion du personnel.
- Les mots de passe Oracle, Mongo et Orthanc doivent être **les mêmes** dans le
  `.env` et dans la base : Oracle ne les lit qu'au premier démarrage du volume
  (voir *ORA-01017* dans les problèmes fréquents).
- `H2_ORTHANC_URL` pointe vers `127.0.0.1:8042` parce que l'API de la clinique
  tourne sur le poste, et non dans le conteneur `api` du `docker-compose`.
- Le détail des variables est dans
  [`docs/securite/configuration.md`](docs/securite/configuration.md).
### 5. Docker : les bases de données
 
**Oracle (CHU).** Attendez `(healthy)` dans `docker ps` : 2 à 5 minutes au
premier démarrage. Lancer l'initialisation avant provoque `ORA-12514`.
 
```powershell
cd hopital1
docker compose up -d
docker ps
..\.venv\Scripts\python.exe initialiser_base_h1.py --donnees
cd ..
```
 
Cela crée le schéma et 8 patients fictifs (dont un avec consentement refusé et
un sans consentement). Pour repartir de zéro, utilisez `--reset --donnees`.
 
**MongoDB et Orthanc (clinique).**
 
```powershell
cd hopital2
docker compose up -d mongo orthanc
..\.venv\Scripts\python.exe charger_mongo.py hopital2_mongodb_v3.js
..\.venv\Scripts\python.exe chiffrer_mongo.py
cd ..
```
 
Cela charge 60 patients fictifs, tous avec un nom de famille différent. Si la
base contient déjà des données, ajoutez `--remplacer` à `charger_mongo.py`.
**Sauvegardez `H2_CLE_CHIFFREMENT`** (dans `hopital2\.env`) : sans elle, les
dossiers chiffrés sont perdus.
 
### 6. DICOM
 
**Orthanc du CHU** (port 8043). Il est lancé avec un fichier d'environnement
pour éviter les problèmes de guillemets de PowerShell avec Docker.
 
```powershell
function Valeur($f, $k) { (Select-String -Path $f -Pattern "^$k=(.*)$").Matches[0].Groups[1].Value }
$u = Valeur "hopital1\.env" "H1_ORTHANC_UTILISATEUR"; $p = Valeur "hopital1\.env" "H1_ORTHANC_MOT_DE_PASSE"
@"
ORTHANC__NAME=PACS CHU Al Massira
ORTHANC__AUTHENTICATION_ENABLED=true
ORTHANC__REGISTERED_USERS={"$u": "$p"}
ORTHANC__DICOM_SERVER_ENABLED=false
ORTHANC__REMOTE_ACCESS_ALLOWED=true
DICOM_WEB_PLUGIN_ENABLED=true
"@ | Set-Content "$env:TEMP\orthanc-h1.env" -Encoding ascii
docker run -d --name orthanc-h1 --restart unless-stopped -p 127.0.0.1:8043:8042 --env-file "$env:TEMP\orthanc-h1.env" orthancteam/orthanc:26.8.2
Remove-Item "$env:TEMP\orthanc-h1.env"
```
 
**Images de démonstration de la clinique** (fonds d'œil synthétiques) :
 
```powershell
cd hopital2
..\.venv\Scripts\python.exe charger_dicom.py
cd ..
```
 
**Récupération par le CHU.** Avec `DEMO=1` (ou `H1_IMAGERIE_AUTO=1`), elle est
**automatique** : dès que le CHU importe un dossier de la clinique, il récupère
les images et les range dans son Orthanc. Il n'y a rien à lancer. La commande
ci-dessous sert seulement à **rejouer** les examens restés « en attente » (PACS
ou passerelle indisponible au moment de l'envoi), ou à récupérer les images sans
l'interface. Elle ne fonctionne que si le patient a répondu « Oui » et n'a pas
exclu l'imagerie.
 
```powershell
cd hopital1
..\.venv\Scripts\python.exe recuperer_imagerie.py
cd ..
```
 
Le CHU a besoin, dans `hopital1\.env`, de `H2_DICOMWEB_URL` (passerelle de la
clinique), de `H1_JETON_VERS_H2` (portée `h2:imagerie.lire`) et de
`H1_ORTHANC_*` (son propre Orthanc, qui doit tourner). Les deux Orthanc
doivent être démarrés avant l'envoi.
 
### 7. Lancer les deux serveurs
 
Deux fenêtres PowerShell distinctes.
 
**CHU :**
```powershell
cd <racine du dépôt>\hopital1
..\.venv\Scripts\python.exe -m uvicorn app:app --port 8000 --ssl-keyfile ..\securite\certificats\h1.key.pem --ssl-certfile ..\securite\certificats\h1.cert.pem
```
 
**Clinique :**
```powershell
cd <racine du dépôt>\hopital2
..\.venv\Scripts\python.exe -m uvicorn api_h2:app --port 8002 --ssl-keyfile ..\securite\certificats\h2.key.pem --ssl-certfile ..\securite\certificats\h2.cert.pem
```
 
**Vérification**, depuis une 3ᵉ fenêtre à la racine :
```powershell
curl.exe --ssl-no-revoke --cacert securite\certificats\ac_interop.cert.pem https://127.0.0.1:8000/health
curl.exe --ssl-no-revoke --cacert securite\certificats\ac_interop.cert.pem https://127.0.0.1:8002/health
```
Les deux doivent répondre `"status":"ok"` ou `"statut":"ok"`.
 
Sur un poste de test isolé, sans certificats : `SEC_MODE=local` et
`SEC_TLS_REQUIS=0` dans le `.env`, puis uvicorn sans les options `--ssl-…`.
 
### 8. Ouvrir la démonstration
 
- CHU : <https://127.0.0.1:8000/ui/>
- Clinique : <https://127.0.0.1:8002/ui/>
Gardez la barre oblique finale. Acceptez l'avertissement de certificat, ou
installez `securite\certificats\ac_interop.cert.pem` parmi les autorités
racines de confiance :
 
```powershell
certutil -user -addstore Root securite\certificats\ac_interop.cert.pem
```
 
Fermez ensuite complètement le navigateur et rouvrez-le.
 
### 9. Arrêter ou tout effacer
 
```powershell
# Arrêter en gardant les données
cd hopital1; docker compose stop; cd ..
cd hopital2; docker compose stop; cd ..
docker stop orthanc-h1
 
# Tout effacer (bases et volumes)
cd hopital1; docker compose down -v; cd ..
cd hopital2; docker compose down -v; cd ..
docker rm -f orthanc-h1
```
 
### Démonstration sans serveur ni base
 
```powershell
cd hopital2
..\.venv\Scripts\python.exe demo.py
```
 
---
 
## Interface de démonstration
 
Avec `DEMO=1`, `https://127.0.0.1:<port>/ui/` ouvre une interface de
démonstration, **sans compte**, réservée au poste local (les accès depuis une
autre machine reçoivent 403). La connexion du personnel reste disponible sur
`/ui/index.html`. Sans `DEMO=1`, `/ui/` affiche cette connexion et les routes
`/api/demo/*` répondent 404.
 
**Écran.** À gauche, trois onglets : *Patients*, *Envoyés*, *Reçus*, avec une
recherche par nom ou identifiant qui s'applique aux trois listes. Les listes se
rafraîchissent d'elles-mêmes toutes les 5 secondes : un dossier envoyé par
l'autre hôpital apparaît sans recharger la page. À droite, le patient choisi :
sa fiche, le consentement, le bouton d'envoi, l'imagerie DICOM (vignettes) et le contenu du Bundle FHIR.
 
**Consentement.** Une seule question : « Le patient accepte le partage avec
l'autre établissement ? », réponse **Oui** ou **Non**. Le choix est enregistré
dans la base de l'hôpital, et le consentement local fait foi.
 
**Les cinq étapes d'un envoi.**
 
1. *Consentement du patient* : sans « Oui », rien ne quitte l'hôpital (loi 09-08).
2. *Dossier converti en Bundle FHIR* : le dossier est mis au format FHIR R5.
3. *Pré-vérification par l'autre hôpital (rien n'est enregistré)* : essai à
   blanc. L'autre hôpital contrôle le format, le consentement et l'identité du
   patient, sans rien écrire. En cas d'échec, l'envoi s'arrête avec la raison.
4. *Envoi et import* : le même Bundle est renvoyé pour de bon. C'est la seule
   étape qui écrit dans la base de l'autre hôpital ; le dossier apparaît dans
   son onglet *Reçus*.
5. *Images DICOM* : les images suivent le dossier, sans bouton supplémentaire.
   Quand le CHU reçoit un dossier de la clinique, il récupère aussitôt les
   examens d'imagerie annoncés, par la passerelle DICOMweb de la clinique
   (consentement et exclusion « imagerie » vérifiés par la clinique), puis les
   range dans son Orthanc. L'étape indique le nombre d'examens et d'images
   transférés, un refus (imagerie exclue par le patient) ou une mise en attente
   (PACS indisponible). L'import du dossier n'est jamais annulé par un échec
   d'image : les examens en attente se rejouent avec `recuperer_imagerie.py`.
   Actif avec `DEMO=1` ou `H1_IMAGERIE_AUTO=1` dans `hopital1\.env`, et il
   demande `H2_DICOMWEB_URL` et `H1_ORTHANC_URL`. En cas de problème, l'étape
   affiche la cause (passerelle injoignable, Orthanc du CHU arrêté, jeton
   refusé, identifiant d'étude invalide…) plutôt qu'un simple « en attente ».
**Aperçu des images.** La fiche du patient contient une section *Imagerie DICOM*
avec une vignette par image (clic pour agrandir). Le serveur lit l'image dans le
PACS local et la convertit en PNG (bibliothèque standard Python, sans
dépendance supplémentaire) ; le navigateur ne reçoit que des pixels, **jamais
les métadonnées DICOM** (nom, identifiant, dates). Si l'image n'est pas encore
disponible (examen « en attente »), la vignette affiche « Aperçu indisponible ».
Route : `GET /api/demo/image/{patient}/{study_uid}/{rang}` (démo, poste local).
 
**Les écritures sont réelles.** Le consentement, les envois et les dossiers
reçus sont écrits dans les vraies bases (Oracle, MongoDB) et dans les journaux.
Une file d'attente SQLite garde les envois quand l'autre hôpital est injoignable.
Pour repartir de données propres : étape 5, avec `--reset` (Oracle) et
`--remplacer` (Mongo).
 
**Patient inconnu de l'autre côté.** Un dossier de la clinique pour un patient
absent du CHU est refusé par défaut. Avec `DEMO=1` (ou
`H1_CREER_PATIENTS_RETOUR=1`), le CHU crée le patient, à condition que le
Bundle contienne un consentement valable pour le CHU et un CIN.
 
**Scénario de démonstration.**
1. CHU : choisir un patient, **Oui**, *Envoyer* → « Transmis à Clinique Al Baçar ».
2. Clinique : le patient apparaît dans *Reçus* en moins de 5 secondes.
3. CHU : choisir un patient, **Non**, *Envoyer* → « Bloqué ».
4. Arrêter la clinique, envoyer un patient du CHU → « Mis en file d'attente ».
   Relancer la clinique, cliquer sur *Relancer les envois en attente*.
5. Clinique : envoyer un de ses patients vers le CHU (retour).
Détails : [`docs/interface.md`](docs/interface.md).
 
---
 
## Contrat d'échange
 
| | H1 (CHU) | H2 (Clinique) |
| --- | --- | --- |
| État du service | `GET /health` | `GET /health`, `GET /metadata` |
| Préparer un dossier à envoyer | `GET /api/patients/{ipp}/bundle` | `GET /api/patients/{id}/bundle` |
| Recevoir à blanc | `POST /api/retours/simulation` | `POST /api/retours/simulation` |
| Recevoir | `POST /api/retours` | `POST /api/retours`, `POST /Bundle` |
| Consentement : état et historique | `GET /api/patients/{ipp}/consentement` | `GET /api/patients/{id}/consentement` |
| Consentement : recueil / retrait | `POST /api/patients/{ipp}/consentement[/retrait]` | `POST /api/patients/{id}/consentement[/retrait]` |
| Droit d'accès de la personne (DPO) | `GET /api/patients/{ipp}/droit-acces` | `GET /api/patients/{id}/droit-acces` |
| Images DICOM (WADO-RS) | `GET /dicom-web/studies/{uid}[/metadata]` | `GET /dicom-web/studies/{uid}[/metadata]` |
| Connexion du personnel | `POST /auth/connexion`, `/auth/renouvellement`, `/auth/deconnexion`, `GET /auth/moi` | idem |
| Interface | `GET /ui/` | `GET /ui/` |
| Démonstration (`DEMO=1`, poste local) | `/api/demo/*` (dont `image/{id}/{uid}/{rang}`, aperçu PNG) | `/api/demo/*` (idem) |
| Documentation | `GET /docs` | `GET /docs` |
 
En-têtes : `Authorization: Bearer <jeton>`, `Accept: application/fhir+json`,
`Content-Type: application/fhir+json` à l'envoi, `X-Exchange-Id: <uuid>`
facultatif pour identifier un échange et le rejouer sans danger.
 
Identités : CIN commun `urn:ma:cin`, IPP du CHU `https://chu-almassira.ma/ipp`,
identifiant de la clinique `urn:clinique-al-bacar:patient`. Chaque établissement
conserve son propre identifiant interne.
 
Codes : `200` · `201` patient créé · `400` requête illisible · `401` jeton ·
`403` consentement, portée insuffisante ou TLS absent · `404` patient inconnu ·
`409` identité ambiguë · `413` corps trop volumineux · `422` Bundle non
conforme · `429` débit dépassé · `503` base indisponible ou authentification non
configurée. Toutes les erreurs sont renvoyées en `OperationOutcome`.
 
Règles communes : consentement vérifié avant tout envoi et avant toute
intégration (statut, période de validité, finalité, destinataire ; catégories
exclues par le patient retirées du Bundle ; voir
[`docs/securite/consentement.md`](docs/securite/consentement.md)) ; anti-boucle
(les données reçues d'un établissement ne lui sont jamais renvoyées) ; rejeu
sans doublon par identifiants métier stables ; conflits signalés, jamais
d'écrasement silencieux.
 
---
 
## Sécurité
 
Toutes les routes de dossier exigent un jeton **et** la portée correspondante
(`h1:export`, `h2:import`, …). Sans authentification configurée, le service
répond `503` : il ne s'ouvre jamais. L'interface charge uniquement ses propres
scripts et styles (politique CSP dédiée aux pages `/ui`) ; aucun jeton n'est
envoyé au navigateur, les envois sont faits côté serveur.
 
- [`SECURITY.md`](SECURITY.md) — périmètre et signalement
- [`docs/securite/authentification.md`](docs/securite/authentification.md) — comptes du personnel, rôles et sessions (`/auth/...`)
- [`docs/securite/consentement.md`](docs/securite/consentement.md) — consentement au partage (loi 09-08)
- [`docs/securite/conformite-09-08.md`](docs/securite/conformite-09-08.md) — grille de conformité à la loi 09-08 et écarts restants
- [`docs/securite/chiffrement.md`](docs/securite/chiffrement.md) — chiffrement des dossiers au repos (MongoDB, file d'envoi) et des disques
- [`securite/README.md`](securite/README.md) — mode d'emploi de la couche
- [`docs/securite/politique-securite.md`](docs/securite/politique-securite.md) — politique, menaces, matrice des droits
- [`docs/securite/procedure-secrets.md`](docs/securite/procedure-secrets.md) — jetons et mots de passe
- [`docs/securite/tls-https.md`](docs/securite/tls-https.md) — mise en place de HTTPS
```powershell
.\.venv\Scripts\python.exe securite/outils/verifier_securite.py
```
 
**Ce dépôt ne doit jamais contenir** : fichier `.env`, jeton en clair, clé
privée (`*.key.pem`), `securite/jetons_locaux/`, registre de jetons, journal
d'accès, clés de chiffrement, dossier patient réel. À l'autre établissement,
on ne transmet que `ac_interop.cert.pem`.
 
---
 
## Tests
 
```powershell
# Depuis la racine du dépôt :
.\.venv\Scripts\python.exe -m pytest securite/tests -q
.\.venv\Scripts\python.exe -m pytest imagerie/tests -q
cd hopital2
..\.venv\Scripts\python.exe -m pytest -q
cd ..\hopital1
..\.venv\Scripts\python.exe -m pytest -q tests
```
 
Les tests du CHU qui ont besoin d'un vrai Oracle (`hopital1\tests\test_oracle_reel.py`)
sont ignorés (*skipped*) tant qu'Oracle n'est pas lancé et initialisé. Une fois
Oracle `(healthy)` et la base initialisée, ils s'exécutent avec la même commande.
 
Dernier passage (sans Oracle réel) : CHU 118 réussis et 16 ignorés, clinique 282
réussis, `securite` + `imagerie` 341 réussis. Les tests de l'interface couvrent
les cinq étapes d'envoi, la récupération automatique des images, l'identifiant
`urn:oid:` et l'aperçu PNG (`imagerie\tests\test_apercu.py`). L'auditeur
`verifier_securite.py` ne signale aucun écart P0 ni P1.
 
---
 
## Problèmes fréquents
 
| Symptôme | Cause et solution |
| --- | --- |
| `DPY-6001 / ORA-12514 : service FREEPDB1 not registered` | Oracle n'a pas fini de démarrer. Attendre `(healthy)` dans `docker ps`, puis relancer l'initialisation. |
| `ORA-01017 : invalid credential` | L'utilisateur Oracle n'existe pas, ou son mot de passe diffère du `.env`. Oracle ne lit les mots de passe qu'à la création du volume : `docker compose down -v`, `docker compose up -d`, attendre `(healthy)`, puis relancer l'initialisation. |
| `ImportError: attempted relative import` au lancement du CHU | Un fichier `ui_h1.py` traîne à la racine du dépôt. Le bon est `hopital1\ui_h1.py` : supprimer ou renommer l'autre. |
| `/ui/` renvoie 404 côté clinique | Le bloc d'installation de l'interface manque à la fin de `hopital2\api_h2.py` (voir ci-dessous). |
| Page blanche sur `/ui/` | Le dossier `securite\` est ancien : la politique CSP des pages `/ui` manque (`securite\entetes.py`). Copier la version à jour, puis redémarrer. Vérifier : `curl.exe --ssl-no-revoke --cacert securite\certificats\ac_interop.cert.pem -I https://127.0.0.1:8000/ui/demo.js` doit montrer `script-src 'self'`. |
| `'StoreMongoChiffre' object is not callable` | L'adaptateur de la clinique attend une fonction : `AdaptateurH2(lambda: STORE)`. |
| `ConnectionResetError [WinError 10054]` dans la console | Sans gravité : bruit asyncio de Windows quand le navigateur ferme une connexion TLS. |
| `403 Forbidden` sur `/api/patients/{id}/bundle` | Normal quand le patient n'a pas de consentement « Oui » : l'export est refusé. |
| `H1_CLE_CHIFFREMENT absent, Bundles en clair sur le disque` | Avertissement : la file d'envoi n'est pas chiffrée. Ajouter la clé dans `hopital1\.env` (étape 4). |
| Étape 5 : « Images DICOM … en attente (PACS ou passerelle indisponible, à relancer) » | Lire le détail affiché sous l'étape. Causes courantes : Orthanc du CHU (8043) ou de la clinique (8042) arrêté ; images non chargées côté clinique (`charger_dicom.py`) ; `H2_DICOMWEB_URL` ou `H1_ORTHANC_*` absents du `hopital1\.env`. Corriger, puis `cd hopital1` et `..\.venv\Scripts\python.exe recuperer_imagerie.py`. |
| `400 Bad Request` sur `/dicom-web/studies/urn%3Aoid%3A…` dans la console de la clinique | Ancienne version du CHU : l'identifiant d'étude était transmis avec son préfixe FHIR `urn:oid:`. La passerelle exige l'UID DICOM seul (et reste volontairement stricte). Mettre à jour `hopital1\` (`recuperer_imagerie.py`, `fhir_to_h1.py`, `oracle_repo.py`) ; les anciennes étapes déjà « en attente » se rejouent avec `recuperer_imagerie.py`. |
| Vignette « Aperçu indisponible » | L'examen n'est pas encore dans le PACS de cet hôpital (récupération en attente), ou l'image est dans un format non lisible. Voir la ligne précédente. |
| Fiche d'un patient du CHU lente (plusieurs secondes) | Chaque accès Oracle ouvre une connexion, ce qui est lent sous Docker pour Windows. Pas une panne. |
| Envoi « Mis en file d'attente » | L'autre hôpital est injoignable ; l'envoi sera retenté (bouton *Relancer les envois en attente*). |
| Avertissement de certificat | Certificat auto-signé de l'étape 3 : l'accepter ou installer `ac_interop.cert.pem` (étape 8). |
 
**Bloc d'interface de la clinique** (fin de `hopital2\api_h2.py`) :
 
```python
# --- Interface graphique (démo / personnel) ---
from interface import installer_interface  # noqa: E402
from ui_h2 import AdaptateurH2  # noqa: E402
installer_interface(app, service="H2", adaptateur=AdaptateurH2(lambda: STORE))
```
 
---
 
## État d'avancement et travail restant
 
Voir [`docs/etat-avancement.md`](docs/etat-avancement.md) : ce qui est fait de
chaque côté, ce qui reste à faire, et pour qui.
 
Limites connues :
- les sessions du personnel sont gardées en mémoire (perdues au redémarrage) ;
- le CHU n'importe pas encore les allergies et diagnostics reçus de la clinique ;
- la démonstration n'a pas été validée sur deux machines distinctes, ni le
  validateur officiel HL7 exécuté ;
- la fiche d'un patient du CHU met quelques secondes (connexion Oracle ouverte à
  chaque accès, pas de pool) ;
- l'unité de la glycémie diffère (g/L au CHU, mg/dL à la clinique) ;
- le projet est en FHIR **R5** : la mention « R4 » du cahier des charges est à
  reporter ou à justifier.
## Qui fait quoi
 
Les responsabilités **par partie** et les fichiers correspondants sont dans
[`docs/architecture-et-contributions.md`](docs/architecture-et-contributions.md).
L'attribution **par personne** y est à compléter avec les noms validés par l'équipe.
 