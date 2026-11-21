# Politique de sécurité de l'échange FHIR R5

Échange de dossiers patients entre le **CHU Al Massira** (H1) et la **Clinique Al Baçar** (H2).

| | |
|---|---|
| Version | 1.0 |
| Date | 21 novembre 2026 |
| Auteur | étudiant responsable du lot « sécurité » |
| Public | enseignant évaluateur, responsable H1, responsable H2 |
| Documents liés | [`procedure-secrets.md`](procedure-secrets.md), [`tls-https.md`](tls-https.md), [`../../SECURITY.md`](../../SECURITY.md) |

---

## 1. Objet et périmètre

### 1.1 Objet

Ce document décrit les règles de sécurité appliquées à l'échange de données de santé
entre les deux API du projet, les mesures techniques qui les mettent en oeuvre, et les
écarts qui restent à traiter. Il sert de référence commune aux trois contributeurs :
une règle énoncée ici doit être vérifiable dans le code ou dans une procédure.

### 1.2 Périmètre

Dans le périmètre :

- l'API FastAPI de H1 (`hopital1/`, base Oracle) ;
- l'API FastAPI de H2 (`hopital2/`, base MongoDB) ;
- la couche de sécurité commune (`securite/`) branchée sur les deux API ;
- les appels sortants d'une API vers l'autre (`securite/client.py`) ;
- les secrets du projet et leur cycle de vie.

Hors périmètre : les systèmes d'information hospitaliers réels, les postes de travail
des utilisateurs, le réseau de l'établissement, la sécurité physique des serveurs, et
la conservation des dossiers médicaux eux-mêmes.

### 1.3 Qui fait quoi

| Rôle | Responsabilité | Fichiers principaux |
|---|---|---|
| Responsable H1 | API et base Oracle du CHU, journal métier `journal_echange`, atomicité des écritures | `hopital1/` |
| Responsable H2 | API et base MongoDB de la clinique, journal métier `_audit_log`, client d'envoi | `hopital2/` |
| Responsable sécurité | couche `securite/`, jetons et portées, TLS, journal d'accès, cette documentation | `securite/`, `docs/securite/`, `SECURITY.md` |

Les mesures de sécurité sont communes : chaque responsable applique la même couche de
son côté, avec la même configuration. Les écarts constatés sont suivis au chapitre 11.

---

## 2. Ce qui est protégé

### 2.1 Nature des données

| Catégorie | Exemples dans le projet | Sensibilité |
|---|---|---|
| Identité du patient | nom, prénom, date de naissance, IPP (H1), identifiant `P2-xxxx` (H2) | données à caractère personnel |
| Identifiant national | CIN, porté par `Patient.identifier` (`urn:ma:cin`) | donnée personnelle, identifiant unique et non révocable |
| Données cliniques | séjours, diagnostics, mesures, résultats d'ophtalmologie, imagerie, comptes rendus, allergies, groupe sanguin | **données sensibles** (données de santé) |
| Consentement | ressource `Consent` du Bundle, champ `consent` du document Mongo | preuve de la base légale de l'échange |
| Journaux | journal métier des échanges, journal d'accès de la couche sécurité | données personnelles indirectes (horodatage, adresse IP, pseudonyme) |

Un Bundle d'échange réunit les trois premières catégories dans un seul message. C'est
l'objet le plus sensible du projet : sa divulgation expose à la fois l'identité civile
et l'état de santé d'une personne.

### 2.2 Cadre légal marocain

La loi **09-08** relative à la protection des personnes physiques à l'égard du
traitement des données à caractère personnel (promulguée par le dahir n° 1-09-15 du
18 février 2009) encadre ce traitement. La **CNDP** (Commission nationale de contrôle
de la protection des données à caractère personnel) en assure le contrôle.

Points qui déterminent les choix de ce document :

| Exigence de la loi 09-08 | Traduction dans le projet |
|---|---|
| Les données de santé sont des données sensibles : leur traitement suppose le consentement de la personne et une autorisation préalable de la CNDP | le consentement est vérifié des deux côtés, avant export et avant intégration ; aucun Bundle sans `Consent` actif n'est accepté (403) |
| Finalité déterminée et proportionnalité | seules les données nécessaires à la continuité des soins sont échangées ; l'annuaire de l'établissement et le journal d'accès d'un patient ne sont pas inclus par défaut |
| Confidentialité et sécurité du traitement | authentification de l'appelant, chiffrement du transport, droits par client, limitation de débit |
| Traçabilité des accès | journal d'accès distinct du journal métier, conservé et vérifiable |
| Durée de conservation limitée | durée proposée pour le journal d'accès : 1 an (voir 8.6) |

Le projet est un prototype pédagogique : il ne traite aucune donnée réelle et ne fait
l'objet d'aucune déclaration à la CNDP. Les mesures sont néanmoins conçues pour être
celles qu'exigerait un traitement réel.

### 2.3 Correspondance avec le RGPD

| Article du RGPD | Objet | Mesure correspondante ici |
|---|---|---|
| Art. 9 | les données concernant la santé sont des catégories particulières de données, dont le traitement est interdit sauf exception, notamment la prise en charge médicale | contrôle du consentement avant tout échange, portées distinctes pour l'export et pour l'import |
| Art. 32 | sécurité du traitement : chiffrement, pseudonymisation, intégrité, disponibilité, vérification régulière des mesures | TLS exigé, pseudonymisation du journal d'accès, chaînage du journal, limitation de débit, tests de la couche sécurité |
| Art. 33 | notification d'une violation de données à l'autorité de contrôle | procédure de fuite de secret, étape 5 (voir `procedure-secrets.md`) |

La loi 09-08 et le RGPD poursuivent le même objectif ; la correspondance ci-dessus sert
à justifier les mesures, pas à transposer une obligation européenne au Maroc.

---

## 3. Modèle de menaces

Hypothèses : l'attaquant est sur le même réseau local que les deux API, ou dispose d'un
accès au dépôt GitHub public, ou a obtenu un jeton valide. Il n'a pas d'accès
administrateur aux serveurs de bases de données.

| Menace | Conséquence si elle aboutit | Mesure en place | Limite résiduelle |
|---|---|---|---|
| Écoute du réseau | lecture des Bundles en clair (identité, CIN, diagnostics) et capture du jeton Bearer | TLS exigé en mode strict : une requête en clair est refusée (403) sauf `/health` (`securite/intergiciels.py:170-175`) ; autorité de certification interne ; le client vérifie le certificat du serveur (`securite/client.py:57-71`) | l'autorité est interne : la confiance repose sur la transmission manuelle du certificat racine. Pas de mTLS : le serveur n'authentifie pas le client par certificat |
| Vol de jeton (fichier `.env` recopié, jeton resté dans un historique de terminal) | accès à toutes les routes couvertes par les portées du jeton | un jeton par client, portées minimales (`securite/outils/generer_jetons.py:43-63`) ; expiration `expire_le` ; révocation immédiate (`actif` à `false`, registre relu à chaud) ; empreinte du jeton dans chaque ligne de journal ; rotation tous les 90 jours | un jeton valide reste utilisable jusqu'à sa révocation. Pas de liaison à une adresse IP, pas de second facteur (échange de serveur à serveur) |
| Rejeu d'un échange (même Bundle renvoyé) | doublons dans le dossier du patient, comptes faussés | idempotence applicative : identifiants métier stables et en-tête `X-Exchange-Id` ; l'identifiant d'échange est conservé dans le journal d'accès | pas de signature ni d'horodatage vérifiable du Bundle (P2-4) ; H1 ne lit pas encore `X-Exchange-Id` (P2-3) |
| Appelant légitime qui dépasse ses droits (la clinique demande l'annuaire, ou le journal d'accès d'un patient) | divulgation au-delà du besoin de l'échange | portées séparées : `h2:audit` pour `inclure_audit`, `h2:annuaire` pour `inclure_catalogue` ; aucun client ne détient `h2:annuaire` par défaut ; le destinataire de l'anti-boucle est déduit de l'identité du jeton, non du paramètre de requête | la granularité s'arrête à la route : la couche sécurité ne filtre pas patient par patient, ce contrôle reste celui du consentement |
| Exfiltration massive (boucle sur tous les identifiants) | copie de la base patients | limitation de débit à 120 requêtes par minute et par adresse, avec réserve de rafale (`securite/debit.py:29-56`) ; une ligne de journal par dossier consulté ; portée `export` distincte de `patient.chercher` | compteur en mémoire, par processus (P2-5). 120 requêtes par minute suffisent à parcourir 60 dossiers : la limite ralentit, elle ne détecte pas. Aucune alerte automatique (pas de SIEM) |
| Altération du journal (effacer la ligne d'un accès) | perte de la preuve d'accès | journal JSONL chaîné : chaque ligne porte l'empreinte SHA-256 de la précédente ; `verifier_chaine()` signale la première rupture (`securite/audit.py:180-210`) | ce n'est pas une signature : qui peut écrire le fichier peut recalculer toute la chaîne. Le journal est sur le même poste que le service, sans copie externe |
| Déni de service (corps de requête énorme, rafale d'appels) | service indisponible, mémoire saturée | taille maximale du corps de 5 Mo, contrôlée sur `Content-Length` puis à la lecture en flux (`securite/intergiciels.py:187-202` et `lire_json_securise`) ; seau à jetons ; verrouillage après 5 échecs d'authentification ; délais d'attente côté client | compteurs en mémoire ; aucune protection réseau en amont (ni pare-feu applicatif, ni répartiteur de charge) |
| Fuite de secret dans Git (jeton ou mot de passe poussé sur GitHub) | compromission durable : le dépôt est public et l'historique se recopie | `.gitignore` à la racine ; `.env.example` sans valeur réelle ; le registre ne contient que des empreintes ; jetons écrits dans des fichiers exclus de Git, jamais affichés à l'écran ; contrôle des fichiers préparés avant commit | un secret déjà poussé doit être considéré comme définitivement compromis |
| Poste compromis (poste d'un contributeur infecté) | tous les secrets de ce poste, et les dossiers déjà exportés | moindre privilège : un jeton par poste, révocable sans toucher aux autres ; les clés privées ne sortent jamais du poste ; le journal d'accès est écrit côté serveur, indépendamment du poste appelant | les fichiers `.env` et les clés privées sont en clair sur le disque (pas de coffre, pas de HSM). Hors de portée du prototype |

---

## 4. Principes retenus

**1. Fail-closed.** En l'absence de configuration de sécurité, le service refuse le
trafic au lieu de l'accepter. Si aucune source de jetons n'est configurée, les routes
protégées répondent 503 (`securite/jetons.py:300-305`) ; H1 fait de même depuis
`hopital1/auth_h1.py:33-37`. Une erreur de configuration provoque une panne visible,
jamais une ouverture silencieuse.

**2. Moindre privilège.** Chaque client a son jeton et ses portées. L'API du CHU ne
peut qu'envoyer un retour à la clinique ; elle ne peut pas lire les dossiers de la
clinique. Aucun client ne cumule la lecture des dossiers des deux côtés.

**3. Défense en profondeur.** Les contrôles sont indépendants et empilés : TLS, débit,
taille du corps, jeton, portée, consentement, anti-boucle. La chute d'un contrôle ne
suffit pas à obtenir une donnée de santé. Un jeton volé ne donne rien sur une route
dont il n'a pas la portée, et rien du tout si le consentement n'est pas actif.

**4. Traçabilité.** Toute requête laisse une ligne, y compris les refus. Le journal
d'accès est distinct du journal métier, pseudonymisé et chaîné. Sans trace des refus,
une tentative d'intrusion est invisible.

**5. Pas de secret dans le dépôt.** Le dépôt est public. Aucun jeton, mot de passe, clé
privée ni donnée de patient n'y entre. Les fichiers d'exemple ne contiennent que des
valeurs fictives. Le registre de jetons ne contient que des empreintes.

---

## 5. Authentification

L'appelant présente un jeton dans l'en-tête `Authorization: Bearer <jeton>`. Trois
sources sont acceptées, essayées dans cet ordre (`securite/jetons.py:275-374`).

### 5.1 Les trois sources, dans l'ordre

| Ordre | Source | Contenu | Portées obtenues | Usage prévu |
|---|---|---|---|---|
| 1 | Registre de jetons `securite/registre_jetons.json` | une entrée par client : `id`, `empreinte` SHA-256, `portees`, `expire_le`, `actif` | celles de l'entrée | mode normal du projet |
| 2 | JWT HS256, si `SEC_JWT_SECRET` est défini | jeton signé portant `sub`, `scope`, `iss`, `aud`, `exp` | celles de la revendication `scope` | jetons de courte durée, si les deux hôpitaux en conviennent |
| 3 | Jeton partagé historique `H1_API_TOKEN` / `H2_TOKEN` | une seule valeur par service | toutes celles du service (`h1:*` ou `h2:*`) | compatibilité des postes déjà configurés ; signalé « à migrer » au démarrage |

Règles associées :

- l'ordre est strict : le registre l'emporte sur le JWT, qui l'emporte sur le jeton
  partagé. Un jeton révoqué dans le registre ne peut pas être repêché par une autre
  source, puisque le registre est consulté le premier ;
- si aucune des trois sources n'est configurée, la réponse est **503**, jamais 200 ;
- le registre est relu automatiquement quand le fichier change : une révocation prend
  effet sans redémarrer le service ;
- le JWT n'accepte que `HS256`, et l'algorithme est vérifié **avant** la signature
  (`securite/jetons.py:176-224`) : `alg: none` et la confusion d'algorithme sont donc
  exclues. `exp` est obligatoire ; `iss` et `aud` sont vérifiés ; la tolérance
  d'horloge est de 30 secondes.

### 5.2 Pourquoi des empreintes SHA-256 et pas les jetons

Le registre ne stocke que `sha256:` suivi de 64 caractères hexadécimaux.

- Le serveur n'a pas besoin de la valeur en clair : il compare l'empreinte du jeton
  reçu à celle de l'entrée.
- Un registre recopié ne donne aucun jeton utilisable : SHA-256 n'est pas inversible et
  un jeton de 256 bits (`secrets.token_urlsafe(32)`) n'est pas devinable par
  dictionnaire.
- L'empreinte courte (12 caractères hexadécimaux) peut être écrite dans le journal :
  elle permet de corréler toutes les requêtes d'un même jeton sans jamais le révéler,
  et de répondre à la question « ce jeton compromis a-t-il servi ? ».

### 5.3 Pourquoi la comparaison à temps constant

Une comparaison de chaînes classique s'arrête au premier caractère différent. Le temps
de réponse dépend alors du nombre de caractères corrects, ce qui permet de reconstruire
un jeton caractère par caractère à partir de mesures répétées.

`hmac.compare_digest` compare en temps constant. Deux usages dans le projet :

- le jeton partagé, côté H1 (`hopital1/auth_h1.py:38-40`) et dans la couche commune ;
- le registre : `Registre.chercher` parcourt **toutes** les entrées sans sortie
  anticipée (`securite/jetons.py:136-148`), pour que le temps de réponse ne révèle pas
  non plus la position de l'entrée trouvée.

### 5.4 Codes de refus

| Code | Signification | Cas typique |
|---|---|---|
| 401 | jeton absent, mal formé, invalide, expiré ou révoqué | en-tête `Authorization` manquant ; jeton d'avant la rotation |
| 403 | jeton valide mais portée absente, ou requête en clair alors que TLS est exigé | la clinique appelle `GET /api/patients/{ipp}/bundle` sur H1 sans `h1:export` |
| 413 | corps de requête trop volumineux | Bundle au-delà de 5 Mo |
| 429 | débit dépassé, ou adresse verrouillée après 5 échecs | boucle d'export trop rapide ; force brute du jeton |
| 503 | authentification non configurée sur le service | fichier `.env` absent après un déploiement |

Toutes les erreurs sont renvoyées au format FHIR `OperationOutcome`, avec un message
qui n'indique jamais si le jeton existe, ni si le patient existe.

---

## 6. Autorisation

### 6.1 Portées

Une portée s'écrit `<service>:<suffixe>`. Le service est celui qui **expose** la route
(`h1` ou `h2`) ; le suffixe est le droit précis. Suffixes reconnus
(`securite/config.py:21-32`) :

| Suffixe | Droit |
|---|---|
| `export` | envoyer un dossier complet (`GET .../bundle`) |
| `simulation` | essayer un import sans écriture |
| `import` | écrire définitivement un retour reçu |
| `patient.lire` | lire une ressource Patient |
| `patient.creer` | créer une ressource Patient |
| `patient.chercher` | rechercher un Patient par identifiant |
| `audit` | lire le journal d'accès d'un patient |
| `annuaire` | obtenir l'annuaire complet de l'établissement |

Deux jokers existent : `h1:*` ou `h2:*` (tous les droits d'un service) et `*` (tous les
droits). Ils ne sont attribués à aucun client du projet ; seul le jeton partagé
historique reçoit `h1:*` ou `h2:*`, le temps de la migration.

### 6.2 Matrice route x portée — H1 (`hopital1/`)

| Méthode | Route | Portée exigée | Fichier | Remarque |
|---|---|---|---|---|
| GET | `/health` | aucune | `hopital1/app.py:56` | état du service, aucune donnée de patient ; joignable en clair |
| GET | `/docs`, `/redoc`, `/openapi.json` | aucune | FastAPI | description des routes, sans donnée |
| GET | `/api/patients/{ipp}/bundle` | `h1:export` | `hopital1/app.py:62-66` | consentement vérifié avant export ; anti-boucle sur les données venues de H2 |
| POST | `/api/retours/simulation` | `h1:simulation` | `hopital1/app.py:109-112` | aucune écriture, annulation systématique de la transaction |
| POST | `/api/retours` | `h1:import` | `hopital1/app.py:165-168` | écriture et journal métier validés ensemble |

### 6.3 Matrice route x portée — H2 (`hopital2/`)

| Méthode | Route | Portée exigée | Fichier | Remarque |
|---|---|---|---|---|
| GET | `/health` | aucune | `hopital2/api_h2.py:131` | ne publie plus l'état de l'authentification (P1-4) |
| GET | `/metadata` | aucune | `hopital2/api_h2.py:142` | `CapabilityStatement`, sans donnée de patient |
| GET | `/api/patients/{id}/bundle` | `h2:export` | `hopital2/api_h2.py:170` | consentement vérifié ; destinataire de l'anti-boucle déduit de l'identité du jeton |
| GET | `/api/patients/{id}/bundle?inclure_audit=true` | `h2:export` **et** `h2:audit` | `hopital2/api_h2.py:172` | journal d'accès du patient |
| GET | `/api/patients/{id}/bundle?inclure_catalogue=true` | `h2:export` **et** `h2:annuaire` | `hopital2/api_h2.py:173` | annuaire complet de la clinique ; aucun client ne détient cette portée par défaut |
| POST | `/api/retours/simulation` | `h2:simulation` | `hopital2/api_h2.py:189` | aucune écriture |
| POST | `/api/retours` | `h2:import` | `hopital2/api_h2.py:195` | idempotent par identifiants métier et `X-Exchange-Id` |
| POST | `/Bundle` | `h2:import` | `hopital2/api_h2.py:204` | même traitement, nommage FHIR |
| GET | `/Patient/{id}/$everything` | `h2:export` | `hopital2/api_h2.py:209` | équivalent FHIR de la route d'export |
| POST | `/Patient` | `h2:patient.creer` | `hopital2/api_h2.py:214` | création unitaire |
| GET | `/Patient/{id}` | `h2:patient.lire` | `hopital2/api_h2.py:221` | lecture unitaire |
| GET | `/Patient?identifier=systeme\|valeur` | `h2:patient.chercher` | `hopital2/api_h2.py:226` | la valeur recherchée (CIN) est masquée dans le journal de sécurité |

### 6.4 Portées par client

Clients du registre (`securite/outils/generer_jetons.py:43-63`) :

| Client | Registre où le jeton est déclaré | Portées | Ce qu'il peut faire | Ce qu'il ne peut pas faire |
|---|---|---|---|---|
| `h1-chu` | H2 | `h2:simulation`, `h2:import` | l'API du CHU envoie ses Bundles à la clinique, après essai | lire un dossier de la clinique, y créer un patient |
| `h2-clinique` | H1 | `h1:simulation`, `h1:import` | l'API de la clinique envoie ses retours au CHU, après essai | lire un dossier du CHU |
| `h1-interne` | H1 | `h1:export`, `h1:simulation`, `h1:import` | outils locaux du CHU (`exporter.py`, `importer.py`) sur sa propre API | toucher à l'API de la clinique |
| `h2-interne` | H2 | `h2:export`, `h2:simulation`, `h2:import`, `h2:patient.lire`, `h2:patient.chercher`, `h2:patient.creer` | outils locaux de la clinique (`client_envoi.py`, `demo.py`) sur sa propre API | toucher à l'API du CHU, lire un journal d'accès, obtenir l'annuaire |
| `supervision` | H1 et H2 | aucune | appeler `/health` et `/metadata` | toute route servant une donnée de patient (403) |
| `audit` | H1 et H2 | `h1:audit`, `h2:audit` | relire le journal d'accès d'un patient des deux côtés | exporter ou écrire un dossier |

Conséquence voulue : l'export d'un dossier n'est jamais accessible à l'autre
établissement. Le flux est un **envoi** (`simulation` puis `import`), pas une lecture à
distance. La portée `export` reste réservée aux outils locaux de chaque établissement.

---

## 7. Transport

### 7.1 TLS exigé

En mode `strict` (valeur par défaut de `SEC_MODE`), une requête arrivée en clair est
refusée avec un 403 et le motif `tls_absent`. Le contrôle est le premier de
l'intergiciel, avant l'authentification : un jeton n'est jamais lu sur un canal en
clair.

Côté appels sortants, `securite/client.py:43-54` refuse une adresse `http://` quand TLS
est exigé, sauf vers `localhost`. La désactivation de la vérification du certificat
(`SEC_TLS_VERIF=0`) n'est acceptée qu'avec `SEC_MODE=local` : en mode strict, elle lève
une erreur au lieu d'être appliquée silencieusement.

### 7.2 Autorité de certification interne

Le projet ne peut pas obtenir de certificat d'une autorité publique pour deux postes de
salle de travaux pratiques. Une autorité interne est donc créée
(`securite/tls.py:77-110`) :

- `ac_interop.cert.pem` : certificat racine, **à transmettre** à l'autre hôpital ;
- `ac_interop.key.pem` : clé privée de l'autorité, qui ne quitte jamais le poste ;
- `h1.cert.pem` et `h2.cert.pem` : certificats serveurs, clés ECDSA P-256, validité
  1 an.

Chaque hôpital pointe `SEC_CA` sur le certificat racine reçu. La vérification du
certificat reste donc active, alors qu'un certificat auto-signé sans autorité aurait
poussé à la désactiver. Procédure détaillée : [`tls-https.md`](tls-https.md).

### 7.3 Pourquoi `/health` reste joignable en clair

`/health` est la seule route exemptée du contrôle TLS
(`securite/intergiciels.py:170-175`). Trois raisons :

1. elle ne renvoie aucune donnée de patient : état du service, version, état de la
   base ;
2. elle sert à vérifier qu'un service est démarré **avant** que TLS soit configuré, ce
   qui évite de désactiver TLS globalement pour diagnostiquer une panne ;
3. une sonde de disponibilité doit pouvoir l'interroger sans jeton ni certificat.

Elle est aussi exemptée de la limitation de débit, avec `/metadata`
(`securite/debit.py:26`), pour qu'une sonde n'épuise pas le quota de l'échange. En
contrepartie, elle ne publie plus l'état de l'authentification (voir P1-4).

### 7.4 Pourquoi les redirections ne sont pas suivies

`follow_redirects=False` dans `securite/client.py:110`. httpx rejoue les en-têtes de la
requête initiale sur l'adresse de destination : un serveur qui répond `302` vers une
adresse tierce recevrait l'en-tête `Authorization`, donc le jeton. Les deux API
n'utilisent aucune redirection : la suivre n'apporte rien et expose le secret. Une
réponse `3xx` doit être traitée comme une anomalie de configuration.

### 7.5 En-têtes de sécurité HTTP

Posés sur **toutes** les réponses, erreurs comprises (`securite/entetes.py:15-46`).

| En-tête | Valeur | Raison |
|---|---|---|
| `Cache-Control`, `Pragma`, `Expires` | `no-store, no-cache, must-revalidate, private` | aucun stockage du dossier par un navigateur, un proxy ou un disque |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | posé uniquement si la requête est arrivée en HTTPS |
| `X-Content-Type-Options` | `nosniff` | un JSON ne doit pas être réinterprété en HTML |
| `X-Frame-Options` | `DENY` | ces API ne s'affichent pas dans un cadre |
| `Referrer-Policy` | `no-referrer` | l'URL contient un identifiant de patient : elle ne doit pas partir en `Referer` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` | une API JSON ne charge aucune ressource externe. Retiré sur `/docs`, `/redoc` et `/openapi.json`, qui chargent leurs scripts |
| `Permissions-Policy` | capteurs désactivés | aucun capteur du poste client n'est utile à une API |
| `Cross-Origin-Resource-Policy`, `Cross-Origin-Opener-Policy` | `same-origin` | aucun site web tiers n'appelle ces API |
| `Server`, `X-Powered-By` | retirés | ne pas annoncer la pile technique ni sa version |

---

## 8. Journalisation

### 8.1 Deux journaux distincts

| | Journal métier | Journal d'accès (sécurité) |
|---|---|---|
| Où | H1 : table Oracle `journal_echange` ; H2 : champ `_audit_log[]` du document patient | fichier JSONL : `journaux/securite-h1.jsonl` et `journaux/securite-h2.jsonl` (`SEC_JOURNAL`) |
| Quoi | échanges aboutis : sens, IPP, statut, détails | toute requête HTTP, y compris 401, 403, 413, 429 et 5xx |
| Qui le tient | responsables H1 et H2 | couche sécurité |
| À quoi il sert | prouver qu'un dossier a bien été transmis et intégré | prouver qui a tenté quoi, et détecter un abus |

Les deux sont nécessaires : le journal métier ne garde pas la trace des tentatives
refusées, qui sont précisément le signal d'une attaque (constat P1-2).

### 8.2 Champs tracés

Une ligne JSON par événement (`securite/audit.py:138-166`) :

| Champ | Contenu | Exemple |
|---|---|---|
| `horodatage` | UTC, à la milliseconde | `2026-11-21T14:05:12.481Z` |
| `service` | `H1` ou `H2` | `H2` |
| `evenement` | `demarrage` ou `acces` | `acces` |
| `resultat` | `succes`, `refus`, `erreur`, `avertissement` | `refus` |
| `http` | code de réponse | `403` |
| `methode`, `chemin` | méthode et **gabarit** de route | `GET`, `/api/patients/{id}/bundle` |
| `ressource` | pseudonyme de l'identifiant présent dans l'URL | `p:9f1c4e77a02b3d55` |
| `parametres` | noms des paramètres, valeurs sensibles masquées | `{"identifier": "***"}` |
| `ip` | adresse appelante, tronquée si `SEC_ANONYMISER_IP=1` | `192.168.1.31` |
| `client`, `jeton`, `source_jeton` | identité reconnue, empreinte courte, source du jeton | `h2-clinique`, `a3f09c71b4de`, `registre` |
| `portee` | portée exigée par la route | `h1:import` |
| `echange_id` | en-tête `X-Exchange-Id`, ou identifiant décidé par la route | `ECH-2026-0042` |
| `octets`, `duree_ms` | taille annoncée du corps, durée de traitement | `18422`, `37` |
| `motif` | cause interne du refus | `portee_absente:h1:export` |
| `prec` | empreinte SHA-256 de la ligne précédente | `genesis` à la première ligne |

Le démarrage de chaque service écrit une ligne `demarrage` avec le mode, l'état de TLS,
le nombre de jetons du registre et les anomalies de configuration détectées.

### 8.3 Ce qui n'est jamais tracé

- le corps des requêtes et des réponses : il contient les données de santé ;
- les en-têtes `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`,
  `X-API-Key` et `X-Auth-Token` (`securite/audit.py:42-43`) ;
- le jeton en clair : seule l'empreinte courte est écrite ;
- les identifiants de patient en clair dans le chemin : ils sont remplacés par un
  gabarit `{id}` et un pseudonyme ;
- les valeurs des paramètres sensibles : `identifier`, `cin`, `ipp`, `name`, `family`,
  `given`, `birthdate`, `patient`, `subject`, `telecom` et `email` sont remplacées par
  `***`, le nom du paramètre étant conservé pour l'analyse
  (`securite/audit.py:38-40`).

Le journal d'accès peut donc être relu, copié et joint à un rapport sans divulguer de
donnée de santé.

### 8.4 Pseudonymisation

Les identifiants de patient sont remplacés par `p:` suivi de 16 caractères d'un
HMAC-SHA-256 calculé avec la clé `SEC_SEL_AUDIT`. Propriétés :

- **stable** : le même patient donne toujours le même pseudonyme, donc une suite
  d'accès reste analysable ;
- **non réversible sans la clé** : un journal volé ne révèle aucun identifiant ;
- **non corrélable entre les deux hôpitaux** : chaque service a son propre sel, donc le
  même patient n'a pas le même pseudonyme chez H1 et chez H2. C'est voulu : cela évite
  de reconstituer un parcours de soins en recoupant deux journaux.

Pour retrouver le patient derrière un pseudonyme, il faut la clé et l'identifiant
candidat : le responsable sécurité recalcule l'empreinte et compare. Ce geste doit être
motivé par un incident.

### 8.5 Chaînage et vérification

Chaque ligne porte dans `prec` l'empreinte SHA-256 de la ligne précédente, la première
valant `genesis`. Supprimer ou modifier une ligne rompt la chaîne.

```powershell
cd d:\interoperabilite\projet
py -c "from securite.audit import verifier_chaine; print(verifier_chaine('journaux/securite-h2.jsonl'))"
```

Sortie attendue : `{'lignes': 412, 'intact': True, 'premiere_rupture': None, ...}`.
Un `intact` à `False` signale une retouche, avec le numéro de la première ligne en
cause.

Le fichier est archivé automatiquement au-delà de 5 Mo, sous le nom
`securite-h2.jsonl.<horodatage>` (`securite/audit.py:49` et `_pivoter_si_besoin`). La
chaîne recommence à chaque archive : les archives doivent donc être conservées
ensemble.

Limite à assumer : le chaînage détecte une retouche ponctuelle, il ne l'empêche pas.
Qui a le droit d'écrire le fichier peut recalculer toute la chaîne. Une protection
réelle suppose un envoi vers un collecteur externe (voir chapitre 12).

### 8.6 Durée de conservation

**Durée proposée pour le journal d'accès : 1 an**, archives comprises, puis suppression.

Justification :

1. le journal contient des données personnelles indirectes (adresse IP, horodatage,
   pseudonyme) : la loi 09-08 impose une durée limitée et proportionnée à la finalité ;
2. 1 an couvre quatre cycles de rotation de jetons (90 jours) : toute la vie active
   d'un jeton compromis reste analysable, ce qui est la finalité du journal ;
3. 1 an couvre aussi la durée du projet et sa soutenance, donc toute demande de
   justification de l'enseignant ;
4. conserver plus longtemps un fichier non signé n'ajoute pas de valeur de preuve, mais
   augmente le volume de données personnelles exposé en cas de vol du poste.

Le journal métier (`journal_echange`, `_audit_log`) suit une autre règle : il documente
un acte de soin et sa durée de conservation relève du dossier médical. Elle n'est pas
fixée par ce document.

La suppression doit être tracée : noter dans ce document la date de purge et le nombre
de lignes supprimées. Aucune suppression n'est automatique dans le prototype.

---

## 9. Disponibilité

| Mesure | Paramètre | Défaut | Effet au dépassement |
|---|---|---|---|
| Limitation de débit par adresse appelante (seau à jetons) | `SEC_DEBIT_PAR_MINUTE` | 120 par minute, réserve de rafale de 30 | 429 avec en-tête `Retry-After` ; `/health` et `/metadata` exemptés |
| Taille maximale du corps de requête | `SEC_TAILLE_MAX_CORPS` | 5 000 000 octets | 413 ; contrôle sur `Content-Length`, puis à la lecture en flux pour un envoi `chunked` |
| Verrouillage après échecs d'authentification | `SEC_ECHECS_MAX`, `SEC_VERROU_SECONDES` | 5 échecs, 300 s | 429 jusqu'à expiration du verrou ; le compteur est remis à zéro par un succès |
| Délais d'attente des appels sortants | `securite/client.py:28-31` | 5 s connexion, 30 s lecture, 30 s écriture, 5 s pool | l'appel rend la main et la reprise applicative joue |

Dimensionnement : un Bundle de dossier complet pèse quelques dizaines de kilo-octets,
très loin des 5 Mo ; un échange normal fait quelques requêtes par minute, très loin de
120. Les limites gênent l'abus, pas l'usage prévu.

Deux limites connues :

- les compteurs sont en mémoire : avec plusieurs workers uvicorn, la limite effective
  est multipliée par le nombre de workers (constat P2-5). Le prototype doit être lancé
  avec un seul worker ;
- `X-Forwarded-For` n'est lu que si `SEC_PROXY_DE_CONFIANCE=1`
  (`securite/intergiciels.py:108-125`). Sans ce réglage, un appelant pourrait choisir
  son adresse et contourner à la fois la limitation de débit et le verrouillage.

---

## 10. Configuration

Toute la configuration passe par des variables d'environnement, lues dans le `.env` de
chaque service, hors dépôt Git.

| Variable | Défaut | Rôle |
|---|---|---|
| `SEC_MODE` | `strict` | `strict` : TLS exigé, réglages dégradés refusés. `local` : poste de test isolé |
| `SEC_REGISTRE` | `securite/registre_jetons.json` | registre des jetons (empreintes et portées) |
| `SEC_JOURNAL` | `journaux/securite-<service>.jsonl` | journal d'accès |
| `SEC_SEL_AUDIT` | dérivé du service | clé HMAC de pseudonymisation du journal |
| `SEC_JWT_SECRET` | vide | secret HS256 ; vide = JWT désactivé |
| `SEC_JWT_ISS` | `interop-sante` | émetteur attendu des JWT |
| `SEC_JWT_AUD` | nom du service | destinataire attendu des JWT |
| `SEC_TLS_REQUIS` | `1` en mode strict | refuser les requêtes en clair |
| `SEC_TLS_VERIF` | `1` | vérifier le certificat du serveur appelé ; `0` accepté seulement en mode local |
| `SEC_CA` | vide | certificat racine de confiance pour les appels sortants |
| `SEC_TAILLE_MAX_CORPS` | `5000000` | taille maximale du corps de requête, en octets |
| `SEC_DEBIT_PAR_MINUTE` | `120` | requêtes par minute et par adresse |
| `SEC_ECHECS_MAX` | `5` | échecs d'authentification avant verrouillage |
| `SEC_VERROU_SECONDES` | `300` | durée du verrouillage |
| `SEC_ROTATION_JOURS` | `90` | durée de validité des jetons générés |
| `SEC_PROXY_DE_CONFIANCE` | non défini | lire `X-Forwarded-For` et `X-Forwarded-Proto` |
| `SEC_ANONYMISER_IP` | non défini | tronquer l'adresse IP dans le journal (`/24` en IPv4) |
| `H1_API_TOKEN`, `H2_TOKEN` | — | jetons partagés historiques, conservés pour compatibilité |

Au démarrage, la couche signale les anomalies de configuration sur la sortie standard
et dans le journal : aucune source de jetons, jeton partagé seul, jeton trop court,
mode strict avec TLS désactivé, jeton expiré dans le registre
(`securite/jetons.py:285-298`).

---

## 11. Constats d'audit et suivi

Audit mené sur le code des deux API et sur le dossier d'échange. Priorités : **P0** =
exposition directe de données de santé, **P1** = défaut de contrôle ou de traçabilité,
**P2** = écart résiduel.

Chemins historiques, avant réorganisation : `api_h1/` est devenu `hopital1/` et `api3/`
est devenu `hopital2/`. Les constats ci-dessous emploient les noms actuels.

### 11.1 P0 — exposition directe

| Réf | Constat | Emplacement | Mesure appliquée | État | Qui agit |
|---|---|---|---|---|---|
| P0-1 | Si `H2_TOKEN` est absent, `verifier_jeton` retourne sans rien vérifier : l'API de santé est totalement ouverte (fail-open) | `hopital2/api_h2.py:107-115` | fail-closed : 503 quand aucune source de jetons n'est configurée | Corrigé | Sécurité |
| P0-2 | Aucun TLS : les deux API en HTTP clair, conteneur à l'écoute sur `0.0.0.0`, `FHIR_BASE_URL` en `http://` par défaut. Données de santé lisibles sur le réseau | les deux services | TLS exigé en mode strict, autorité interne, client qui vérifie le certificat | Corrigé | Sécurité |
| P0-3 | Client d'envoi sans délai d'attente explicite, sans vérification de certificat, jeton fourni par l'appelant | `hopital2/client_envoi.py` | `securite/client.py` : délais d'attente, vérification du certificat, jeton lu dans l'environnement, redirections non suivies | Corrigé | Sécurité |
| P0-4 | MongoDB sans authentification, port 27017 publié sur toutes les interfaces | `hopital2/docker-compose.yml:6-9` | authentification MongoDB activée, port lié à `127.0.0.1` | Corrigé | Sécurité et H2 |
| P0-5 | Conteneur exécuté en root ; `COPY *.py` embarque les fichiers de test dans l'image | `hopital2/Dockerfile:5-8` | utilisateur non privilégié, copie restreinte aux fichiers de service | Corrigé | Sécurité et H2 |
| P0-6 | Aucun `.gitignore` à la racine : `adaptateur_h1/sortie/` contient de vrais Bundles patients, `hopital1/.venv/` un environnement virtuel importé d'un autre poste, plus les caches `__pycache__` et `.pytest_cache`. Risque de publication de données de santé sur GitHub | racine du dépôt | `.gitignore` racine couvrant sorties, environnements, caches, secrets et certificats | Corrigé | Sécurité |
| P0-7 | Un ancien fichier d'exemple contenait une valeur de mot de passe Oracle, vraisemblablement réelle | `hopital1/.env.example` et copies historiques | valeurs d'exemple fictives uniquement ; mot de passe réel à changer (voir `procedure-secrets.md`) | Gabarit corrigé ; rotation à faire | Sécurité et H1 |

### 11.2 P1 — défaut de contrôle ou de traçabilité

| Réf | Constat | Emplacement | Mesure appliquée | État | Qui agit |
|---|---|---|---|---|---|
| P1-1 | Un seul jeton partagé par service, sans rôle : un jeton volé permet de tout lire et de tout écrire | les deux services | registre de jetons avec portées par client, moindre privilège | Corrigé | Sécurité |
| P1-2 | Aucune trace des tentatives d'accès (401, 403) : les journaux existants ne tracent que les échanges métier aboutis | les deux services | journal d'accès JSONL chaîné, une ligne par requête, refus compris | Corrigé | Sécurité |
| P1-3 | Aucune limitation de débit ni verrouillage après échecs : force brute du jeton possible | les deux services | seau à jetons par adresse, verrouillage après 5 échecs | Corrigé | Sécurité |
| P1-4 | `/health` publie l'état de l'authentification (`bool(os.getenv("H2_TOKEN"))`), ce qui annonce à un attaquant qu'elle est désactivée | `hopital2/api_h2.py:138` | champ retiré de la réponse | Corrigé | Sécurité |
| P1-5 | Le paramètre `destinataire` est choisi par l'appelant. L'anti-boucle filtre ce qui vient du destinataire : en déclarant un autre destinataire, un appelant récupère les données que l'autre hôpital lui avait envoyées | `hopital2/api_h2.py:171` | destinataire déduit de l'identité du jeton | Corrigé | Sécurité et H2 |
| P1-6 | `inclure_audit=true` expose le journal d'accès du patient à tout porteur du jeton ; `inclure_catalogue=true` expose l'annuaire | `hopital2/api_h2.py:172-173` | portée `h2:audit` et portée `h2:annuaire` exigées | Corrigé | Sécurité |
| P1-7 | Aucune limite de taille du corps de requête : un Bundle énorme épuise la mémoire | les deux services | 5 Mo, contrôlés sur `Content-Length` et à la lecture en flux | Corrigé | Sécurité |
| P1-8 | Aucun en-tête de sécurité HTTP. L'URL contient un identifiant de patient et pouvait partir en `Referer` | les deux services | en-têtes de sécurité sur toutes les réponses, dont `Referrer-Policy: no-referrer` | Corrigé | Sécurité |
| P1-9 | Une recherche par CIN place une donnée personnelle dans les journaux du serveur et des proxys | `hopital2/api_h2.py:226` | valeurs masquées dans le journal de sécurité | Partiellement corrigé : le durcissement du journal d'accès d'uvicorn reste à faire | Sécurité |
| P1-10 | Dépendances non épinglées (`fastapi>=0.110`, `oracledb` sans version) : une montée de version non maîtrisée peut introduire une faille | `hopital1/requirements.txt`, `hopital2/requirements.txt` | aucune | Reste à faire | H1 et H2 |

### 11.3 P2 — écarts résiduels

| Réf | Constat | Emplacement | Conséquence | État | Qui agit |
|---|---|---|---|---|---|
| P2-1 | Dans l'import en ligne de commande, l'écriture des données et celle du journal sont validées séparément : si le journal échoue, les données restent écrites sans trace. La route API, elle, est atomique | `hopital1/oracle_repo.py:196-204` (ligne de commande) contre `hopital1/oracle_repo.py:208-219` (API) | échange réalisé sans preuve | Reste à faire | H1 |
| P2-2 | La table `journal_echange` n'a pas de colonne pour l'identifiant d'échange, le destinataire, l'empreinte du jeton, l'adresse IP ni le code HTTP | `hopital1/schema_retour_h1.sql:59-66` | corrélation manuelle entre journal métier et journal d'accès | Reste à faire | H1 |
| P2-3 | H1 ne lit pas l'en-tête `X-Exchange-Id` : aucun identifiant d'échange côté CHU | `hopital1/app.py:165-168` | détection de rejeu asymétrique entre les deux côtés | Reste à faire | H1 |
| P2-4 | Aucune signature ni horodatage des Bundles échangés | contrat d'échange | pas de non-répudiation : un établissement peut contester avoir émis un Bundle | Hors périmètre du prototype | — |
| P2-5 | Le compteur anti-force-brute et la limitation de débit sont en mémoire : avec plusieurs workers uvicorn, la limite effective est multipliée par le nombre de workers | `securite/debit.py`, `securite/jetons.py:236-273` | limite plus permissive qu'annoncée | Documenté : lancer un seul worker | Sécurité |
| P2-6 | MongoDB n'a pas de verrou optimiste : le dernier écrit gagne | `hopital2/stores.py` | deux imports simultanés du même patient peuvent s'écraser | Reste à faire | H2 |

### 11.4 Suivi

| Priorité | Total | Corrigés | Partiels | Reste à faire | Hors périmètre |
|---|---|---|---|---|---|
| P0 | 7 | 7 | 0 | 0 | 0 |
| P1 | 10 | 8 | 1 | 1 | 0 |
| P2 | 6 | 0 | 1 | 4 | 1 |

---

## 12. Limites assumées du prototype

**Ce projet est un travail scolaire.** Il met en oeuvre des mesures de sécurité sur deux
API de démonstration, avec des données fictives, sur un réseau local. Il ne constitue
pas un système prêt à traiter des dossiers de patients réels. Les limites suivantes sont
connues et assumées.

| Limite du prototype | Ce qu'il faudrait en production |
|---|---|
| Jetons opaques gérés dans un fichier JSON, jetons partagés encore acceptés | fournisseur d'identité réel, OAuth 2.0 et profil **SMART on FHIR** : jetons de courte durée, portées standard, consentement porté par le jeton |
| Le serveur authentifie le client par jeton seulement | **mTLS** : chaque établissement présente un certificat client, vérifié par l'autre |
| Secrets et clés privées en clair dans des fichiers `.env` | coffre à secrets, clés dans un **HSM** ; aucun secret en clair sur le disque d'un poste |
| Journal local, chaîné mais non signé | envoi vers un **SIEM** ou un collecteur externe en écriture seule, avec alertes sur les suites de 401/403 et sur les volumes d'export anormaux |
| Compteurs de débit et d'échecs en mémoire, par processus | compteurs partagés (Redis) ou pare-feu applicatif en amont, pour que la limite soit globale |
| Autorité de certification interne, certificat racine transmis à la main | certificats délivrés par l'autorité de l'établissement, avec révocation (CRL ou OCSP) et renouvellement automatique |
| Dépendances non épinglées (P1-10) | versions épinglées, fichier de verrouillage, veille sur les vulnérabilités publiées |
| Bundles non signés (P2-4) | signature électronique et horodatage des messages, pour la non-répudiation |
| Sécurité relue par l'auteur de la couche | **revue de code** par un tiers et **tests d'intrusion** sur un environnement de recette |
| Aucune validation par une autorité de contrôle | déclaration et autorisation préalable auprès de la **CNDP**, analyse d'impact sur la vie privée |

---

## 13. Références

- Loi n° 09-08 relative à la protection des personnes physiques à l'égard du traitement
  des données à caractère personnel (dahir n° 1-09-15 du 18 février 2009) ; CNDP.
- Règlement (UE) 2016/679 (RGPD), articles 9, 32 et 33, cités à titre de comparaison.
- HL7 FHIR R5, sections `Security` et `AuditEvent` ; profil SMART on FHIR pour les
  portées d'accès.
- Code du projet : `securite/` (couche de sécurité), `hopital1/`, `hopital2/`.
- Procédures associées : [`procedure-secrets.md`](procedure-secrets.md),
  [`tls-https.md`](tls-https.md).
