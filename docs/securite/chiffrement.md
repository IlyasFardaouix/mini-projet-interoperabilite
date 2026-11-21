# Chiffrement des données au repos

Code : [`securite/chiffrement.py`](../../securite/chiffrement.py) (commun),
[`hopital2/stores.py`](../../hopital2/stores.py) (`StoreMongoChiffre`),
[`hopital2/client_envoi.py`](../../hopital2/client_envoi.py) (file d'envoi).

## Pourquoi

HTTPS protège les dossiers pendant le transport, pas une fois écrits. Un disque
volé, une sauvegarde copiée ou un accès direct à MongoDB (sans passer par l'API,
donc sans jeton ni journal) livrait tout en clair : identité, CIN, visites,
consentement. La loi 09-08 impose des mesures de sécurité adaptées à des données
de santé ; le chiffrement au repos en fait partie.

## Ce qui est chiffré

| Donnée | Où | Protection |
| --- | --- | --- |
| Dossiers patients de la clinique | MongoDB `patients` | chiffrement applicatif du document entier, AES-256-GCM |
| Bundles en attente d'envoi | SQLite de `client_envoi.py` | idem, lié à l'identifiant d'échange |
| Base Oracle du CHU | disque du poste | chiffrement du volume (BitLocker) — voir plus bas |
| Images DICOM (Orthanc) | volume Docker | chiffrement du volume — Orthanc ne chiffre pas son stockage |

## Fonctionnement (MongoDB)

Un document en base ne contient plus que :

| Champ | Contenu |
| --- | --- |
| `patient_id` | identifiant technique `P2-xxxx`, non nominatif, en clair |
| `_idx` | index aveugles : HMAC-SHA256 du CIN, des identifiants externes, des UID d'études |
| `_cle` | identifiant de la clé utilisée (`v1`, `v2`…) |
| `_chiffre` | le dossier **complet** chiffré (AES-256-GCM, nonce aléatoire, tag d'authenticité) |

- **La clé n'est pas dans la base** : `H2_CLE_CHIFFREMENT`, dans le `.env` du poste
  (hors Git), générée par `securite/outils/generer_jetons.py` ou
  `py securite/chiffrement.py`. Une copie de la base seule est illisible.
- **Authentifié** : un octet modifié dans `_chiffre` est détecté (erreur, pas de
  donnée fausse). Le chiffre est **lié au `patient_id`** : recopié sur un autre
  dossier, il ne se déchiffre pas.
- **Recherches sans clair** : le CIN n'est jamais stocké en clair, mais on retrouve
  un patient par son CIN grâce à l'index aveugle (même valeur → même empreinte,
  irréversible sans la clé, donc pas de dictionnaire de CIN possible).
- **Sous-clés séparées** (HKDF) pour le chiffrement et pour les index.
- **Transparent pour l'API** : `StoreMongoChiffre` a les mêmes méthodes que
  `StoreMongo`. Toute la suite de tests de l'API H2 tourne aussi sur le magasin
  chiffré.
- Sans `H2_CLE_CHIFFREMENT`, l'API fonctionne en clair et l'annonce au démarrage
  (`ATTENTION`). Une clé mal formée arrête le démarrage.

## Mise en place et migration

```powershell
# 1. Clé : env.h2 produit par generer_jetons.py, recopier H2_CLE_CHIFFREMENT dans hopital2/.env
# 2. Chiffrer les dossiers déjà chargés en clair (rejouable)
Set-Location hopital2
..\.venv\Scripts\python.exe chiffrer_mongo.py
```

Les anciens documents en clair restent lisibles et sont chiffrés à leur
prochaine écriture ; `chiffrer_mongo.py` les traite tous d'un coup.

**Rotation** : mettre la nouvelle clé en premier, garder l'ancienne après une
virgule (`H2_CLE_CHIFFREMENT=v2:...,v1:...`), lancer `chiffrer_mongo.py`
(rechiffre et recalcule les index), puis retirer l'ancienne.

**Sauvegarde de la clé** : sans elle, les dossiers sont définitivement perdus.
La conserver hors du poste (coffre, support séparé), jamais à côté des
sauvegardes de la base.

## Oracle (H1) et Orthanc

- **Oracle** : le chiffrement transparent d'Oracle (TDE) relève de l'option
  Advanced Security, dont la disponibilité sur l'édition utilisée (Free) est à
  vérifier par H1. Mesure retenue pour le prototype : **chiffrement du disque du
  poste** (BitLocker sous Windows), qui couvre aussi les fichiers de données du
  conteneur Oracle et les sauvegardes locales. Un chiffrement applicatif
  colonne par colonne demanderait de modifier le schéma et les requêtes de H1.
- **Orthanc** : pas de chiffrement intégré du stockage. Même mesure : volume
  Docker sur un disque chiffré.
- **Fichiers `.env`** : en clair sur le poste par construction ; protégés par les
  droits du compte et le chiffrement du disque.

## Tests

| Fichier | Couvre |
| --- | --- |
| `securite/tests/test_chiffrement.py` | aller-retour, contexte, altération, mauvaise clé, rotation, index aveugles |
| `hopital2/test_chiffrement_h2.py` | aucune donnée nominative en clair dans la base, recherches, dossier recopié, migration, rotation, file d'envoi |
| `hopital2/test_api_h2.py` | toute l'API sur magasin chiffré (paramètre `mongo_chiffre`) |

## Limites

- Les index aveugles révèlent l'égalité : deux dossiers au même CIN ont le même
  index (c'est ce qui permet la recherche).
- Le chiffrement protège contre la copie de la base, pas contre un attaquant
  qui contrôle le poste et lit la clé dans le `.env` : en production, la clé irait
  dans un coffre (HSM, gestionnaire de secrets).
- Les annuaires (praticiens, lieux, endpoints) ne sont pas chiffrés : ils ne
  contiennent pas de données de patients.
