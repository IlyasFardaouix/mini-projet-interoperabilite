# Imagerie DICOM

Code : [`imagerie/`](../imagerie/), branché sur H1 et H2.

## Ce qui manquait

Les Bundles FHIR décrivaient déjà les examens d'imagerie de la clinique
(`ImagingStudy`, `Endpoint`, `DiagnosticReport`), mais :

- aucune image n'existait : pas de fichier DICOM, pas de PACS dans le déploiement ;
- l'`Endpoint` annoncé à H1 était `http://localhost:8042/dicom-web`, c'est-à-dire
  le PACS brut : en HTTP, sans authentification, et `localhost` désigne la
  machine de H1, pas celle de la clinique. Ouvrir cette adresse au réseau aurait
  exposé toutes les images sans aucun contrôle ;
- les `ImagingStudy` n'avaient pas de série : leur UID n'était pas connu.

## Architecture

```text
Clinique (H2)                                         CHU (H1)
PACS Orthanc 127.0.0.1:8042 (compte dédié)            PACS Orthanc 127.0.0.1:8043
      ▲                                                     ▲
      │ DICOMweb local                                      │ STOW-RS local
API H2 ── /dicom-web (HTTPS, jeton, portée, ── WADO-RS ── recuperer_imagerie.py
          consentement, journal)                            │
                                                API H1 ── /dicom-web (personnel du CHU)
```

- Le PACS n'écoute que sur la boucle locale, avec authentification. Son serveur
  DICOM classique (DIMSE, port 4242) est désactivé : tout passe par DICOMweb.
- L'autre hôpital passe **uniquement** par la passerelle `/dicom-web` de l'API,
  qui applique la même sécurité que les dossiers.
- L'`Endpoint` des Bundles annonce l'adresse de cette passerelle (`H2_DICOMWEB_URL`).

## Passerelle (contrat)

| Route | Portée | Réponse |
| --- | --- | --- |
| `GET /dicom-web/studies/{StudyInstanceUID}` | `imagerie.lire` | `multipart/related; type="application/dicom"` (WADO-RS) |
| `GET /dicom-web/studies/{StudyInstanceUID}/metadata` | `imagerie.lire` | `application/dicom+json`, sans les pixels |
| `?desidentifier=true` (sur les deux) | idem | images désidentifiées (voir plus bas) |

Règles appliquées par la clinique (`echange.autoriser_imagerie`) :

| Appelant | Règle |
| --- | --- |
| Personnel de la clinique (session, outil interne) | accès à ses propres images |
| Autre établissement (`h1-chu`) | consentement valide **vers lui**, catégorie `imagerie` non exclue par le patient, et jamais une étude qu'il a lui-même transmise (anti-boucle) |

Côté CHU, les images proviennent toutes de la clinique : elles ne lui sont
jamais renvoyées (403), seul le personnel du CHU les consulte.

| Code | Cas |
| --- | --- |
| 400 | UID mal formé (il ne peut alors pas être transmis au PACS) |
| 401 / 403 | jeton ; portée manquante, consentement, imagerie exclue, anti-boucle |
| 404 | étude inconnue du dossier ou absente du PACS |
| 503 | PACS non configuré ou indisponible |

Le journal d'accès porte le pseudonyme du patient de l'étude.

## Récupération par le CHU

`hopital1/recuperer_imagerie.py` traite les études reçues dans `etude_imagerie` :

1. n'appelle que `H2_DICOMWEB_URL`. Une `url_pacs` différente (Bundle forgé,
   erreur) est marquée `URL_REFUSEE` sans aucun appel : le jeton du CHU ne part
   jamais vers une adresse inconnue ;
2. télécharge l'étude (WADO-RS, jeton `H1_JETON_VERS_H2`, TLS vérifié, pas de redirection) ;
3. vérifie que chaque instance appartient à l'étude annoncée, sinon `INCOHERENTE` ;
4. la dépose dans l'Orthanc du CHU, pointe `url_pacs` vers la passerelle du CHU,
   statut `RECUPEREE`, et trace l'opération dans `journal_echange`.

Un refus de la clinique (403) ou une étude absente (404) est définitif
(`REFUSEE`, `ABSENTE`) ; une panne laisse l'étude en attente pour le prochain passage.

## Images de démonstration

Aucune image réelle. `hopital2/charger_dicom.py` fabrique, pour chacune des 42
études décrites dans MongoDB, des photographies du fond d'œil synthétiques
(128×128, RGB, papille et vaisseaux dessinés), au format « Ophthalmic
Photography 8 Bit Image Storage », avec le même `StudyInstanceUID`, une
latéralité par instance (OD / OG) et des UID stables. Il enregistre
l'UID de série dans le dossier : les `ImagingStudy` exportés décrivent alors
exactement ce que contient le PACS.

## Désidentification

`?desidentifier=true` applique le profil de base DICOM PS3.15 (annexe E) avec
l'option « Retain UIDs » : nom et identifiant remplacés par le pseudonyme du
journal ; date de naissance, numéro d'accession, médecins, établissement et
attributs privés retirés ; `PatientIdentityRemoved = YES` et codes `113100`,
`113110`. Les UID sont conservés pour garder le lien avec l'`ImagingStudy`. Usage
prévu : enseignement ou démonstration, pas les soins.

## Mise en route

Clinique :

```powershell
# hopital2/.env : H2_ORTHANC_UTILISATEUR, H2_ORTHANC_MOT_DE_PASSE, H2_DICOMWEB_URL
Set-Location hopital2
docker compose up -d orthanc
..\.venv\Scripts\python.exe charger_dicom.py
docker compose up -d api
```

CHU : lancer un Orthanc local sur `127.0.0.1:8043` (même configuration que celui
de la clinique), renseigner `H1_ORTHANC_*`, `H2_DICOMWEB_URL` et
`H1_JETON_VERS_H2` dans `hopital1/.env`, puis après chaque retour :

```powershell
Set-Location hopital1
..\.venv\Scripts\python.exe recuperer_imagerie.py
```

Le jeton du client `h1-chu` porte désormais `h2:imagerie.lire` (voir
`generer_jetons.py`), et le rôle `medecin` aussi.

## Tests

| Suite | Fichier |
| --- | --- |
| Module commun : génération, désidentification, multipart, Orthanc simulé, passerelle | `imagerie/tests/test_imagerie.py` |
| H2 : chargement, Endpoint, règles de partage | `hopital2/test_imagerie_h2.py` |
| H1 : récupération, adresse refusée, intégrité, passerelle | `hopital1/tests/test_imagerie.py` |

```powershell
.\.venv\Scripts\python.exe -m pytest imagerie/tests -q
```

## Limites

- **Pas testé contre un vrai Orthanc** : Docker n'était pas démarré pendant le
  développement. Le client est testé contre un faux serveur DICOMweb qui imite
  STOW, WADO et QIDO. La version de l'image `orthancteam/orthanc` est à
  vérifier au premier lancement.
- Une réimportation du même retour (rejeu) remet `url_pacs` à l'adresse de la
  clinique : l'étude est simplement re-téléchargée au passage suivant, sans
  doublon dans le PACS.
- Les images ne sont pas transmises au fil de l'eau : la récupération est un
  traitement à lancer, ou à planifier.
- Une seule modalité (photographie du fond d'œil, `OP`) est générée, comme
  dans les données de la clinique ; l'OCT n'est pas simulé.
