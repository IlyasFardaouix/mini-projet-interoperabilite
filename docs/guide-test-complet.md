# Guide de test complet, étape par étape

Objectif : prouver, avec des résultats chiffrés, que **l'envoi et la réception de Bundles** entre H1 et H2 fonctionnent
**avec la sécurité activée**, et que **chaque erreur** prévue est bien renvoyée. Ce guide complète
`fiche_test_complet.pdf` (installation) et [`test-echange-securise.md`](test-echange-securise.md).

Deux niveaux de test, à faire dans cet ordre :

| Niveau | Ce que c'est | Outil | Durée |
| --- | --- | --- | --- |
| 1. Tests de code | pytest : adaptateurs, API, sécurité, client d'envoi, Oracle réel | `docker compose -f docker-compose.tests.yml …` | 5 à 8 min |
| 2. Tests d'échange | les **deux API réellement lancées**, en HTTPS, avec les jetons du registre | `tests_integration/echange_complet.py` | 4 à 6 min |
| 3. Tests manuels | ce qui ne s'automatise pas : comptes du personnel, droit d'accès, DICOM, chiffrement, coupure réelle | sections 5.1 à 5.8 | 30 min |

Convention : commandes PowerShell, depuis la racine du dépôt, venv `.\.venv`. `py` = `.\.venv\Scripts\python.exe`.

---

## Étape 0 : prérequis

- [ ] Docker Desktop lancé ; `git`, Python 3.12.
- [ ] Branche à jour : `git pull`.
- [ ] Deux postes (H1 et H2) **ou** un seul poste qui joue les deux rôles (plus simple pour une première passe).
- [ ] Rien à tester sur une base de production : le script **crée des patients de test** (CIN `ZT…`) et **retire puis
  rétablit le consentement** du patient nominal de chaque hôpital.

## Étape 1 : tests de code (tout dans Docker)

```powershell
docker compose -f docker-compose.tests.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -f docker-compose.tests.yml down -v
```

**Attendu** : `=== TOUT EST VERT ===`, code de sortie 0. Sinon la ligne `>>> ECHEC : <étape>` dit laquelle des quatre
étapes casse (sécurité + imagerie, H2, H1 avec Oracle réel, audit).
Premier lancement : le démarrage d'Oracle et les tests `test_oracle_reel.py` n'ont jamais été exécutés avant vous ;
si l'un échoue, notez le message, c'est probablement le DDL `schema_base_h1.sql` à ajuster à votre base.

Sans Docker : `py -m pytest securite/tests imagerie/tests -q`, puis `cd hopital2; py -m pytest -q`, puis
`cd ..\hopital1; py -m pytest tests -q`.

## Étape 2 : installation, secrets, certificats

Suivre les sections 1 à 3 de la fiche, puis :

```powershell
py securite\outils\generer_jetons.py                 # registre + un jeton par client
py securite\outils\generer_certificats.py --ip <adresse IP du poste>
py securite\outils\generer_jetons.py --rotation h1-interne   # seulement si le registre existait avant : ajoute h1:patient.*
```

Un seul poste : mettez `--ip 127.0.0.1`. Deux postes : l'adresse IP **réelle** de chaque poste (jamais `127.0.0.1`),
puis transmettez à l'autre hôpital **son certificat racine** (`ac_interop.cert.pem`, seul) et **ses jetons** par un canal
séparé du dépôt (`docs/securite/procedure-secrets.md`).

Jetons dont ce guide a besoin :

| Jeton | Sert à | Poste qui le détient |
| --- | --- | --- |
| `h1-interne`, `h1-accueil` | outils et accueil du CHU, sur l'API H1 | H1 |
| `h1-chu` | H1 appelle H2 (simulation, import, imagerie) | H1 |
| `h2-interne`, `h2-accueil` | outils et accueil de la clinique, sur l'API H2 | H2 |
| `h2-clinique` | H2 appelle H1 (simulation, import) | H2 |

## Étape 3 : démarrer les services et vérifier

**Poste H1**

```powershell
# Oracle (compte hopital1), UNE seule fois, dans cet ordre (ou : py hopital1\initialiser_base_h1.py --donnees)
#   @hopital1/schema_base_h1.sql   @hopital1/schema_retour_h1.sql   @hopital1/schema_consentement_h1.sql
cd hopital1
..\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 `
    --ssl-keyfile ..\securite\certificats\h1.key.pem --ssl-certfile ..\securite\certificats\h1.cert.pem
```

**Poste H2** (voir fiche section 5) :

```powershell
cd hopital2
docker compose up -d mongo orthanc
..\.venv\Scripts\python.exe charger_mongo.py hopital2_mongodb_v3.js
..\.venv\Scripts\python.exe chiffrer_mongo.py
docker compose up -d api
```

**Vérification** (depuis chaque poste vers les deux API ; `-s -o NUL -w "%{http_code}"` n'affiche que le code) :

```powershell
curl.exe --cacert securite\certificats\ac_interop.cert.pem https://<ip-H1>:8000/health
curl.exe --cacert securite\certificats\ac_interop.cert.pem https://<ip-H2>:8002/health
```

**Attendu** : `{"status":"ok",…}` côté H1, `{"statut":"ok","base":"disponible",…}` côté H2.
Échec `SSL certificate problem` : le certificat ne couvre pas l'adresse utilisée, régénérer avec la bonne `--ip`.

## Étape 4 : le script d'échange complet (le cœur du test)

### 4.1 Configuration

Variables (valeurs par défaut pour un poste unique) :

```powershell
$env:H1_URL = "https://<ip-H1>:8000"
$env:H2_URL = "https://<ip-H2>:8002"
$env:SEC_CA = "securite\certificats\ac_interop.cert.pem"
# Jetons : le script lit securite\jetons_locaux\<client>.txt, ou la variable JETON_<CLIENT> (ex. JETON_H1_CHU).
# Cas de test : patients du jeu de démonstration (valeurs par défaut) ; à changer si vos ids diffèrent.
$env:H1_IPP_OK = "P1-0106"; $env:H1_IPP_REFUSE = "P1-0108"      # CHU : nominal / consentement refusé
$env:H2_ID_OK  = "P2-0051"; $env:H2_ID_REFUSE  = "P2-0054"      # clinique : nominal / consentement refusé
```

Sur deux postes, chacun n'a que **ses** jetons : les essais dont le jeton manque sont **ignorés (SKIP)**, pas en échec.
Faites donc tourner le script sur chaque poste.

Pour aller plus vite, relever la limite de débit des **deux** API pendant le test (`SEC_DEBIT_PAR_MINUTE=100000` dans
leurs `.env`, puis redémarrer). Sans cela le script ralentit tout seul : il attend le délai annoncé sur chaque 429.
**Remettre la valeur d'origine après.**

### 4.2 Lancer

```powershell
py tests_integration\echange_complet.py                  # groupes A à H : sans risque pour les données de démonstration
py tests_integration\echange_complet.py --seulement C D  # seulement certains groupes
py tests_integration\echange_complet.py --destructif     # + groupe I (à faire EN DERNIER, voir 4.4)
```

Sortie : une ligne par essai (`OK` / `ECHEC` / `SKIP`), un résumé, et **`sortie\rapport_echange_complet.md`**
(tableau attendu / obtenu / durée : c'est le « résultat chiffré » pour le rapport). Chaque lancement **remplace** le
rapport : copiez-le avant d'en refaire un. Code de sortie 0 = aucun échec.

### 4.3 Ce que chaque groupe vérifie

| Groupe | Contenu | Codes attendus |
| --- | --- | --- |
| **A** Disponibilité et TLS | `/health`, `/metadata` (CapabilityStatement R5) publics ; `http://` sur le port TLS refusé ; certificat d'une autorité inconnue refusé | 200 ; connexion refusée |
| **B** Authentification | sans jeton, jeton inconnu ; portée manquante (`h2-clinique` lit un dossier H1, `h1-chu` lit H2, accueil lit un dossier, `h1-chu` utilisé sur H1, droit d'accès sans DPO) | 401 ; 403 |
| **C** Envoi (export de Bundle) | H1 et H2 : Bundle `transaction`, `Bundle.identifier` (et en-tête `X-Exchange-Id` côté H1 ; H2 ne pose que `Bundle.identifier`), `Patient` unique, `Consent` joint, une `request` par entrée, pas de rue exportée ; consentement refusé ; patient inconnu ; alias `$everything` | 200 ; 403 ; 404 |
| **D** Réception | H1→H2 : simulation (rien écrit), import (patient créé), **rejeu du même `X-Exchange-Id` sans doublon**, nouvel identifiant d'échange sans doublon, alias `/Bundle`, patient déjà connu rapproché, **CIN d'un dossier + IPP d'un autre → ambigu**. H2→H1 : simulation, import avec les `PUT` de H2, rejeu, `X-Exchange-Id` renvoyé, identifiant d'échange invalide | 200/201 ; 409 ; 422 |
| **E** Erreurs de Bundle (**sur H1 et sur H2**) | pas un Bundle, JSON invalide, corps vide, **sans `Consent`**, `Consent` refusé, deux `Patient`, instruction `DELETE`, `request.url` incohérente, patient sans identité, sans date de naissance, référence cassée, retour pour patient inconnu, corps de 6 Mo | 400/422 ; 403 ; 409 ; 404 ; 413 |
| **F** Routes Patient (H1 et H2) | `POST /Patient` (201 + `Location`), doublon de CIN, recherche, lecture, inconnu, sans nom, mauvais type, patient créé **non exportable sans consentement** | 201 ; 409 ; 200 ; 404 ; 422 ; 403 |
| **G** Consentement (H1 et H2) | état, recueil invalide (sans `recueilli_par`, statut invalide), **retrait** puis export refusé, double retrait, recueil limité à un destinataire puis export refusé, nouveau recueil puis export rétabli, historique conservé | 200 ; 201 ; 422 ; 409 ; 403 |
| **H** Client d'envoi | H1→H2 et H2→H1 : envoi nominal, consentement refusé bloqué avant l'envoi, patient inconnu, **API cible éteinte → mise en file → reprise trop tôt (rien ne part) → reprise à l'heure (envoi, même identifiant) → plus rien à reprendre**, **retrait du consentement pendant l'attente → envoi annulé** | `envoye` ; `bloque` ; `en_attente` ; `annule` |
| **I** Limites (`--destructif`) | au-delà de `SEC_DEBIT_PAR_MINUTE` requêtes authentifiées ; `SEC_ECHECS_MAX` jetons faux puis **un bon jeton refusé** | 429 |

**Résultat attendu** : `0 en échec`. Sur l'environnement de mise au point (TLS strict, registre de jetons, MongoDB en
mémoire, Oracle simulé), les groupes A à H donnent **120 essais sur 120** et le groupe I **2 sur 2**. Les essais Oracle et MongoDB
réels sont ceux que vous ajoutez.

### 4.4 Le groupe I bloque l'adresse du testeur

Après les faux jetons, l'adresse reste bloquée `SEC_VERROU_SECONDES` (300 s) : toutes les requêtes suivantes vers cette API
reçoivent 429, y compris le script lui-même. Lancez `--destructif` **en dernier**, puis attendez 5 minutes avant de
refaire un essai.

### 4.5 Si un essai échoue

| Symptôme | Cause probable |
| --- | --- |
| `A*` : un essai attendu en exception passe en `ECHEC` | l'API accepte `http://` ou un certificat inconnu : `SEC_MODE` n'est pas `strict` ou `SEC_TLS_REQUIS=0` |
| `B*` renvoie 503 au lieu de 401 | aucun jeton configuré côté serveur : 503 volontaire, rien n'est ouvert |
| `C1`, `D*` : `export H1 impossible` | Oracle injoignable (503), ou patient absent : vérifier `H1_IPP_OK` |
| `D2` 422 « encounter introuvable » | H2 n'a pas la correction `urn:uuid:` : mettre à jour `adaptateur_fhir_h2.py` |
| `D7`/`D8` 422 « seules les instructions POST… » | H1 n'a pas la correction `PUT` : mettre à jour `retour_api.py` |
| `F*` H1 en 403 | le registre n'a pas `h1:patient.*` pour `h1-interne` : `generer_jetons.py --rotation h1-interne` |
| `G1` ÉCHEC « partage non autorisé au départ » | le patient nominal n'a pas de consentement actif : en recueillir un |
| n'importe quel essai en 429 | limite de débit : relever `SEC_DEBIT_PAR_MINUTE` (4.1) ou patienter |
| `H*` en `SKIP` | jeton `h1-chu`/`h2-clinique`… absent sur ce poste |

## Étape 5 : tests manuels

### 5.1 Comptes du personnel (interface)

```powershell
py securite\outils\gerer_utilisateurs.py --service h2 creer m.test --nom "Medecin test" --role medecin
py securite\outils\gerer_utilisateurs.py --service h2 creer a.test --nom "Accueil test" --role accueil
py securite\outils\gerer_utilisateurs.py --service h2 creer d.test --nom "DPO test" --role dpo
```

(idem `--service h1`). Chaque commande affiche un mot de passe provisoire.

| Essai | Requête | Attendu |
| --- | --- | --- |
| Connexion | `POST /auth/connexion` `{"login":"m.test","mot_de_passe":"<provisoire>"}` | 200 `access_token` (15 min) + `refresh_token` |
| Avant changement du mot de passe | `GET /api/patients/{id}/bundle` avec ce jeton | **403** (session provisoire) |
| Changement | `POST /auth/mot-de-passe` `{"ancien","nouveau"}` (≥ 12 caractères) | 200 nouveaux jetons ; 422 si trop court |
| Médecin lit un dossier | `GET /api/patients/{id}/bundle` | 200 |
| Accueil lit un dossier | idem avec `a.test` | **403** |
| Accueil recueille un consentement | `POST /api/patients/{id}/consentement` | 201 |
| Verrouillage | 5 mauvais mots de passe sur `m.test`, puis le bon | **429** pendant 300 s |
| Renouvellement à usage unique | `POST /auth/renouvellement` deux fois avec le même `refresh_token` | 200 puis 401, et la session est fermée |
| Déconnexion | `POST /auth/deconnexion` puis réutiliser le jeton | 204 puis **401** |
| Mauvais service | un jeton de session H1 présenté à H2 | 401 |

### 5.2 Droit d'accès (loi 09-08, art. 7)

Avec la session `d.test` (rôle `dpo`) : `GET /api/patients/{id}/droit-acces` → **200** (dossier, données reçues,
consentement, journal des échanges). Avec `m.test` ou `a.test` → **403**. La demande est tracée (journal Oracle
`DROIT_ACCES` côté H1, `_audit_log` côté H2).

### 5.3 Imagerie DICOM

1. H2 : `docker compose up -d orthanc`, puis `py charger_dicom.py`.
2. `GET https://<ip-H2>:8002/dicom-web/studies/<uid>` avec le jeton `h1-chu` → 200 (image) ; sans jeton → 401.
3. Même route avec le jeton `h2-clinique` ou `h1-accueil` → **403** (portée `imagerie.lire` absente).
4. Consentement du patient avec `"categories_exclues": ["imagerie"]` : l'export ne contient plus d'`ImagingStudy` **et** la
   passerelle refuse l'étude (403).
5. H1 : `py recuperer_imagerie.py` télécharge les images, vérifie leur intégrité ; vérifier ensuite dans Oracle
   `SELECT COUNT(*) FROM etude_imagerie;`.
6. Anti-boucle : sur H1, `GET /dicom-web/studies/<uid>` avec `h2-clinique` → **403** (les images viennent de la clinique,
   elles ne lui sont pas rendues).

### 5.4 Chiffrement et absence de doublon dans les bases

**MongoDB (H2)** : `docker compose exec mongo mongosh` puis `use hopital2; db.patients.findOne()`.
Attendu : seulement `patient_id`, `_idx`, `_cle`, `_chiffre` ; ni nom ni CIN en clair.

**Pas de doublon après rejeu** :

- H2 : `db.patients.countDocuments({})` avant et après les groupes D (+1 patient de test par lancement, jamais +2).
- H1 : `@hopital1/verifier_retour.sql` (comptes par table, derniers imports). Attendu après un rejeu : **mêmes comptes**,
  deux lignes `RETOUR` dans `journal_echange` (chaque réception est tracée), dont `details` contient l'`echange_id`.

### 5.5 File d'attente avec une vraie coupure

1. Arrêter l'API H2 (`docker compose stop api`).
2. Sur H1 : `py hopital1\client_envoi_h1.py envoyer <ipp>` → `en_attente`, « nouvelle tentative dans 60 s ».
3. `py hopital1\client_envoi_h1.py etat` → une ligne `en_attente`.
4. Redémarrer H2 (`docker compose start api`), attendre 60 s, `py hopital1\client_envoi_h1.py reprendre` → `envoye`,
   **même `echange_id`** qu'à l'étape 2.
5. Variante : avant l'étape 4, retirer le consentement du patient (accueil H1), puis `reprendre` → **`annule`**, rien n'est
   parti. Rétablir le consentement ensuite.
6. Fermer le terminal entre les étapes 2 et 4 : la file SQLite survit au redémarrage.
7. Côté H2→H1 : même scénario avec `hopital2\client_envoi.py` (`reprendre(..., h2=...)`).

### 5.6 Sécurité de configuration

| Essai | Attendu |
| --- | --- |
| Démarrer une API **sans** aucun jeton configuré, appeler un dossier | **503** (jamais d'accès libre) |
| Utiliser `H1_API_TOKEN` / `H2_TOKEN` alors que le registre existe | **401** (jetons partagés refusés) |
| Appel `http://` sans TLS | connexion refusée ou 403 |
| `py securite\outils\verifier_securite.py` | `Verdict : aucun constat bloquant ni important` (0 P0, 0 P1) |
| Tenter de committer un `.env` ou un `.pem` | le hook `pre-commit` refuse (`py securite\outils\installer_hooks.py` d'abord) |

### 5.7 Journal d'accès et chaîne d'intégrité

Les journaux sont dans `journaux\securite-h1.jsonl` et `securite-h2.jsonl` : **toutes** les requêtes, refus 401/403/413/429
compris, **sans donnée de santé** (identifiants pseudonymisés).

```powershell
py securite\outils\verifier_securite.py        # vérifie aussi le chaînage : doit rester sans constat bloquant
py -c "from securite.audit import verifier_chaine; from pathlib import Path; print(verifier_chaine(Path('journaux/securite-h1.jsonl')))"
```

**Attendu** : `'intact': True, 'premiere_rupture': None`. Essai de falsification : modifier une ligne du fichier à la
main, relancer la commande : `intact: False` avec le numéro de la première ligne rompue. (Travailler sur une copie.)

### 5.8 Conformité FHIR officielle

Le validateur Python ne remplace pas le validateur HL7 : produire un Bundle (`GET /api/patients/{id}/bundle`), l'enregistrer,
`py hopital1\valider.py <fichier>` (structure), puis le valider sur <https://validator.fhir.org> en **R5 (5.0.0)**. Conserver les
rapports ; zéro erreur attendue, les avertissements sont à relire (codes SNOMED œil, unité de glycémie).

## Étape 6 : tableau des erreurs et comment les provoquer

| Code | `OperationOutcome.code` | Comment le provoquer | Couvert par |
| --- | --- | --- | --- |
| 400 | `invalid` | corps qui n'est pas un Bundle (H2), JSON illisible | E1, E2, E3 |
| 401 | `login`/`security` | pas de jeton, jeton inconnu, jeton partagé, session expirée | B1 à B3, 5.1, 5.6 |
| 403 | `forbidden` | consentement refusé / retiré / expiré / destinataire non autorisé / absent du Bundle ; portée manquante ; TLS absent | B4 à B10, E14, C3, C7, E4, E5, G5, G8 |
| 404 | `not-found` | patient inconnu à l'export ; patient inconnu du CHU à la réception | C4, C8, E12 |
| 409 | `conflict` / `multiple-matches` | CIN et IPP de deux dossiers différents ; patient créé deux fois ; retrait sans consentement actif | D12, F2, G6 |
| 413 | | corps supérieur à `SEC_TAILLE_MAX_CORPS` (5 Mo) | E13 |
| 422 | `invalid`, `not-supported`, `required` | Bundle non conforme, `DELETE`, `request.url` incohérent, deux `Patient`, pas d'identité, pas de date de naissance, référence cassée, `X-Exchange-Id` invalide | E6 à E11, D11, F6, F7, G2, G3 |
| 429 | `throttled` | plus de `SEC_DEBIT_PAR_MINUTE` requêtes ; `SEC_ECHECS_MAX` échecs d'authentification | I1, I2 |
| 503 | `transient` | Oracle ou MongoDB indisponible ; aucun jeton configuré | à provoquer en coupant la base (5.5) |

## Étape 7 : critères de réussite et rapport

Cochez quand c'est vrai, avec la preuve entre parenthèses :

- [ ] Tests de code verts (sortie de l'étape 1).
- [ ] Script d'échange : **0 échec** sur H1 et sur H2 (`rapport_echange_complet.md`, un par poste).
- [ ] Aller H1→H2 et retour H2→H1 avec les jetons du registre, rejeu sans doublon (D2 à D4, D8, D9, 5.4).
- [ ] Toutes les erreurs de l'étape 6 observées avec le bon code et un `OperationOutcome`.
- [ ] Sécurité : TLS obligatoire, jetons et portées, jeton partagé refusé, verrouillage, débit, journal chaîné intact (A, B, I, 5.6, 5.7).
- [ ] Consentement : refus, retrait, annulation d'un envoi en file, historique (C3, E4, E5, G, H8, 5.5).
- [ ] Données : chiffrées dans MongoDB (5.4), pas de doublons dans les deux bases (5.4).
- [ ] Imagerie (5.3) et droit d'accès (5.2).
- [ ] Validation FHIR officielle conservée (5.8).

Pour le rapport (« résultats chiffrés ») : nombre d'essais par groupe et durées (`rapport_echange_complet.md`), nombre de
tests pytest par suite, résultat de l'audit de sécurité, nombre de lignes du journal d'accès vérifié.

## Limites connues de ce guide

- Le script et le guide ont été mis au point contre deux API réelles en HTTPS avec les jetons du registre, mais avec **Oracle
  simulé** et **MongoDB en mémoire**. L'exécution sur les vraies bases est la vôtre : les essais D (rejeu, doublons) et
  E12 (patient inconnu) en sont le meilleur test.
- Le groupe G dépend d'un patient nominal au consentement actif sur chaque hôpital, et le groupe C d'un patient au consentement
  refusé : adaptez les variables `H1_IPP_*` / `H2_ID_*` à votre jeu de données.
- Non automatisé : l'échange entre **deux machines** (réseau, pare-feu, adresses IP dans les certificats). Lancez le script
  depuis chaque poste vers l'autre pour le couvrir.
