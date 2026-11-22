# Adaptateur H1 (CHU Al Massira, Oracle) ⇄ FHIR R5

Version retenue par l'équipe : **FHIR R5 (5.0.0)**. La mention R4 du cahier
des charges initial devra être alignée sur cette décision dans le rendu.

## Démarrer l'API H1

Installer les dépendances, configurer le `.env` local et générer le registre de
jetons et les certificats selon le [guide racine](../README.md#mise-en-route).
Depuis `hopital1/`, lancer ensuite :

```powershell
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --ssl-keyfile ..\securite\certificats\h1.key.pem --ssl-certfile ..\securite\certificats\h1.cert.pem
```

Pour un essai HTTP sur un poste isolé, régler `SEC_MODE=local` et
`SEC_TLS_REQUIS=0` dans le `.env` local et omettre les deux options SSL.

- Documentation interactive : https://127.0.0.1:8000/docs
- État de l'API (sans test Oracle) : `GET /health`
- Export de Youssef : `GET /api/patients/P1-0106/bundle`

### Mêmes routes que l'API de H2

| Route | Rôle | Portée |
| --- | --- | --- |
| `GET /metadata` | CapabilityStatement (sans jeton) | aucune |
| `POST /Patient` | enregistrer UN patient (201, 409 si CIN connu, 422) | `h1:patient.creer` |
| `GET /Patient/{ipp}` | lire un patient | `h1:patient.lire` |
| `GET /Patient?identifier=urn:ma:cin\|AB123456` | chercher (Bundle `searchset`) | `h1:patient.chercher` |
| `GET /Patient/{ipp}/$everything` | = `GET /api/patients/{ipp}/bundle` | `h1:export` |
| `POST /Bundle` | = `POST /api/retours` | `h1:import` |

L'export porte `Bundle.identifier` (système `urn:chu-almassira:echange`) et l'en-tête `X-Exchange-Id`.
La réception lit `X-Exchange-Id`, le reporte dans `journal_echange.details` et le renvoie. Un patient créé
par `POST /Patient` n'a pas de consentement : son dossier n'est pas exportable (403) tant qu'il n'en a pas.

### Envoyer un dossier à la clinique (file d'attente + reprise)

`client_envoi_h1.py` fait pour H1 ce que `hopital2/client_envoi.py` fait pour H2 : export, simulation chez H2,
file SQLite chiffrée, envoi, reprises à 1 min, 5 min, 30 min, 2 h, 6 h, consentement revérifié avant chaque reprise.

    python client_envoi_h1.py envoyer P1-0106
    python client_envoi_h1.py reprendre          (à planifier, par exemple toutes les minutes)
    python client_envoi_h1.py etat

Variables : voir `.env.example` (`H2_BASE_URL`, `H1_JETON_VERS_H2`, `H1_JETON_LOCAL`, `H1_CLE_CHIFFREMENT`).

Les routes de dossier exigent `Authorization: Bearer <jeton>` et la portée
appropriée. Le jeton local `h1-interne` se trouve dans
`../securite/jetons_locaux/h1-interne.txt` après génération et ne doit jamais
être commité. Dans Swagger, utiliser **Authorize** et saisir sa valeur seule,
sans le préfixe Bearer.
Sans jeton valide : 401 + OperationOutcome avant tout accès à Oracle.
Sans configuration serveur : 503. `/health` reste accessible sans jeton.

`configurer_jeton.py` ne sert qu'aux anciens essais locaux avec un jeton
partagé donnant tous les droits ; préférer le registre de la
[couche commune](../securite/README.md). Le `.env` est exclu de Git.

La route d'export lit Oracle et renvoie un Bundle R5 avec le type de contenu
`application/fhir+json`. Les erreurs métier sont retournées en `OperationOutcome`
(403 consentement, 404 patient inconnu, 422 données obligatoires absentes).
Les en-têtes `X-H1-Alert-Count` et `X-H1-Rejection-Count` signalent les alertes
et les éléments écartés par l'adaptateur ; leurs détails sont dans le journal Oracle.
La validation Python porte sur la structure et ne remplace pas le validateur officiel HL7.

Cette étape est destinée au lancement local. L'envoi HTTP à H2 reste à intégrer.

## Réception du retour en simulation

`POST /api/retours/simulation` reçoit le Bundle JSON de la clinique. La route
contrôle sa structure R5 complète, ses références internes et la présence d'un
seul patient identifiable par CIN ou IPP CHU. Le patient doit déjà être connu
d'Oracle et son dernier consentement local doit être ACTIF. Les cas ambigus
sont refusés (409), sans rapprochement automatique par traits.

La route essaie l'import puis effectue un ROLLBACK, y compris après une erreur
d'écriture. Elle renvoie un rapport applicatif JSON (comptages, alertes, éléments
ignorés), pas un Bundle transaction-response. Elle ne constitue donc pas encore
un endpoint de transaction FHIR standard et ne conserve pas de journal d'import.

Dans un deuxième PowerShell ouvert dans ce dossier :

```powershell
$jetonH1 = (Get-Content ..\securite\jetons_locaux\h1-interne.txt -Raw).Trim()
Invoke-RestMethod -Method Post -Uri "https://127.0.0.1:8000/api/retours/simulation" -Headers @{Authorization="Bearer $jetonH1"} -ContentType "application/fhir+json" -InFile ".\exemples\retour_clinique_youssef.json" | ConvertTo-Json -Depth 10
```

## Import définitif du retour

`POST /api/retours` reçoit le même JSON et exige le même jeton. Il contrôle le
consentement local, refuse les retours partiels/non intégrables, puis enregistre
les données et une entrée de journal dans une seule transaction Oracle. Si
l'écriture du journal échoue, les données ne sont pas validées.

Les ressources cliniques doivent porter un identifiant stable. Les clés des
données externes incluent le patient et le système d'identification. Les mêmes
identifiants métier rejoués visent les mêmes lignes par MERGE ; chaque tentative
réussie conserve néanmoins sa propre trace dans le journal. Les imports d'un
même patient sont sérialisés par verrouillage de sa ligne Oracle.

Le résultat est un rapport JSON applicatif avec `simulation: false` et
`modifications_conservees: true`, pas un `transaction-response` FHIR standard.
Le contrat de cette route devra être partagé avec H2.

```powershell
Invoke-RestMethod -Method Post -Uri "https://127.0.0.1:8000/api/retours" -Headers @{Authorization="Bearer $jetonH1"} -ContentType "application/fhir+json" -InFile ".\exemples\retour_clinique_youssef.json" | ConvertTo-Json -Depth 10
```

Après deux envois du même exemple, exécuter `verifier_retour.sql` dans SQL*Plus :
les comptages attendus sont 1 séjour, 1 diagnostic, 1 mesure, 4 résultats
ophtalmologiques, 1 étude et 1 compte rendu. Deux imports réussis produisent
deux entrées de journal, sans doubler les données cliniques.

## Anti-boucle à l'export

Les séjours importés sont marqués par `id_externe` et `etablissement`. Ils
restent dans Oracle, mais sont exclus des exports H1 vers H2, avec leurs
mesures, diagnostics et praticiens. La demande d'adressage est construite à
partir du dernier séjour local. Un nouvel export de Youssef après le retour
contient les 10 ressources locales (pression systolique et diastolique regroupees)
et signale une alerte
anti-boucle ; il ne réémet pas le compte rendu clinique.

## Informations à transmettre à H2

Ce contrat décrit les routes applicatives H1 existantes. L'équipe H2 doit
confirmer ses propres routes et réponses avant le branchement des deux API.

| Élément | Contrat H1 actuel |
|---|---|
| Version | FHIR R5, 5.0.0 |
| Export | `GET /api/patients/{ipp}/bundle` : Bundle JSON |
| Essai du retour | `POST /api/retours/simulation` : écritures annulées |
| Retour définitif | `POST /api/retours` : données et journal validés ensemble |
| Authentification | `Authorization: Bearer <jeton H1 convenu hors du dépôt>` |
| Corps d'un retour | `Content-Type: application/fhir+json`, Bundle transaction complet |
| Réponse au retour | HTTP 200, rapport `application/json` avec comptages, alertes et éléments ignorés |
| Erreurs | OperationOutcome `application/fhir+json` : 401, 403, 404, 409, 422, 503 |
| Identité commune | `Patient.identifier.system = urn:ma:cin` |
| Identité H1 | `Patient.identifier.system = https://chu-almassira.ma/ipp` |
| Rattachement du retour | Un seul patient déjà connu de H1, CIN ou IPP CHU, consentement local ACTIF |
| Origine des données | CHU : `https://chu-almassira.ma/dpi`, clinique attendue : `https://clinique-yeux.ma/dpi` |
| Références | Les ressources référencées doivent être présentes dans le même Bundle |
| Rejeu | Réutiliser les mêmes identifiants métier et leurs systèmes pour une même donnée |

La pression arterielle est representee par une Observation LOINC **85354-9**
avec deux composants : **8480-6** (systolique) et **8462-4** (diastolique),
en `mm[Hg]`. Les mesures sont appariees uniquement au meme horodatage ; une
composante manquante porte `dataAbsentReason` sans valeur inventee. H2 doit
lire `Observation.component` pour ces deux mesures. L'import H1 sait aussi
reconvertir ce panel en deux lignes de la table MESURE.

Exemples à relire ensemble : `sortie/bundle_AB123456.json` pour l'aller et
`exemples/retour_clinique_youssef.json` pour le retour. H1 stocke Encounter,
Observation (codes pris en charge), ImagingStudy et DiagnosticReport ;
Organization, Practitioner et Endpoint servent à leur interprétation. Un
type de ressource non intégrable fait refuser le retour définitif en entier.

L'URL `127.0.0.1` est utilisable seulement sur le poste H1. L'adresse réseau,
TLS, les jetons et le contrat de réponse H2 restent à convenir pour le test
entre postes. Les routes `/api/retours` et `/api/retours/simulation` renvoient
un rapport applicatif ; elles ne sont pas des endpoints de transaction FHIR standard.

```
Oracle H1 ──h1_to_fhir.py──▶ Bundle FHIR R5 ──▶ (API REST) ──▶ clinique (H2)
Oracle H1 ◀──fhir_to_h1.py── Bundle FHIR R5 ◀── (API REST) ◀── clinique (H2)
```

| Fichier | Rôle |
|---|---|
| `config.py` | Table de correspondance H1 ⇄ FHIR (codes, systèmes, unités, bornes) |
| `h1_to_fhir.py` | Adaptateur ALLER : dossier Oracle → Bundle transaction |
| `fhir_to_h1.py` | Adaptateur RETOUR : Bundle reçu → lignes des tables Oracle |
| `oracle_repo.py` | Seul fichier qui parle à Oracle (lecture, MERGE, journal) |
| `exporter.py` / `importer.py` | Commandes à lancer |
| `valider.py` | Validation de structure FHIR R5 |
| `schema_retour_h1.sql` | Nouvelles tables pour le retour (à lancer une fois) |
| `mapping_H1_FHIR.md` | Table de correspondance lisible, pour l'équipe API |
| `tests/` | Tests des adaptateurs et de l'API sans Oracle |
| `exemples/` | Bundle aller (Youssef) et bundle retour fictif de la clinique |

## Installation (une fois)

```powershell
# Depuis la racine du dépôt, après création de .venv (voir README racine).
cd hopital1
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

L'ancien historique exposait les mots de passe Oracle de l'administration et
du compte applicatif `hopital1` ; les deux doivent être changés dans Oracle.
Renseigner `ORACLE_PWD` dans `.env` **après** cette rotation ; les commandes
qui accèdent à la base échouent tant que la nouvelle valeur applicative n'est
pas configurée.

## Tester, niveau par niveau

1. **Tests sans Oracle** : `..\.venv\Scripts\python.exe -m pytest tests -q` (97 tests vérifiés, dont l'échange
   croisé H1 ⇄ H2 en mémoire ; les 16 tests Oracle sont ignorés sans base de test)
1bis. **Tests sur vraie base Oracle** : `docker compose up -d` (dans `hopital1/`), puis `ORACLE_TEST_USER`,
   `ORACLE_TEST_PWD`, `ORACLE_TEST_DSN` et `ORACLE_TEST_RESET=oui`, puis
   `python -m pytest tests/test_oracle_reel.py -v`. **Ces tests suppriment les tables H1 du schéma visé** :
   base de test uniquement. Pour une base de démonstration : `python initialiser_base_h1.py --donnees`.
2. **Validation FHIR** : `python valider.py exemples\aller_youssef_S1.json`
3. **Aller avec Oracle** : `python exporter.py AB123456` → `sortie\bundle_AB123456.json`
4. **Cas dégradés** : `python exporter.py J778241` (D1, refus 403), `python exporter.py --ipp P1-0112` (D4)…
5. **Retour avec Oracle** : lancer `schema_retour_h1.sql`, puis
   `python importer.py exemples\retour_clinique_youssef.json --simulation`, puis sans `--simulation`
6. **Test croisé avec H2** : le bundle de `exporter.py` passe dans l'adaptateur FHIR → MongoDB de Hiba ;
   le bundle de son adaptateur MongoDB → FHIR passe dans `importer.py`.
7. **Validation officielle** (requise pour le rendu) : utiliser le validateur HL7
   en ciblant explicitement R5 (`-version 5.0.0`) sur le Bundle aller et sur le retour.
   Conserver les rapports et traiter les erreurs ; la validation Python ne les remplace pas.

## Validation officielle HL7

Le rapport initial `validation/rapport_aller.json` contenait 10 erreurs. Apres
correction du panel de pression et des libelles de codes, le rapport
`validation/rapport_aller_corrige.json` contient **0 fatal, 0 error, 18 warning,
30 information** avec le validateur 7.0.6 en FHIR 5.0.0. Les avertissements
signalent notamment la narration absente, les codes locaux non declares et
l'absence de date/auteur pour le groupe sanguin : ces informations ne sont
pas inventees pour faire disparaitre les messages.

Les libelles source restent dans `CodeableConcept.text`. `Coding.display`
n'est renseigne pour LOINC/CIM-10 que si un libelle officiel est connu ; les
libelles locaux ne sont plus presentes comme des libelles officiels.

Le validateur officiel et les fichiers sous `validation/` ne sont pas inclus
dans le dépôt. Après avoir obtenu localement le validateur et généré le Bundle,
une commande de validation possible est :

```powershell
$validateur = ".\validation\validator_cli.jar"  # placer le JAR téléchargé ici
java -Xmx2g -jar $validateur ".\sortie\bundle_AB123456.json" -version 5.0.0 -output ".\validation\rapport_aller_corrige.json"
..\.venv\Scripts\python.exe resumer_validation.py ".\validation\rapport_aller_corrige.json"
```

Le script de resume renvoie un code de sortie 1 si le rapport contient des
erreurs fatales ou des erreurs.

Le Bundle de retour est valide separement : apres correction du libelle
officiel CIM-10 H36.0 dans l'exemple, `validation/rapport_retour_corrige.json`
contient **0 fatal, 0 error, 22 warning, 2 information** (validateur 7.0.6,
FHIR 5.0.0). Le texte clinique et le code sont conserves. Les avertissements
incluent 13 narrations absentes, 3 definitions de codes locaux manquantes et
6 occurrences de codes SNOMED inactifs pour les yeux droit/gauche. Ces codes
devront etre revus avec H2 ; une validation sans erreur ne resout pas ces
avertissements terminologiques.
