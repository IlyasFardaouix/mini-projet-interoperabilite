# Mini-projet interopérabilité — CHU Al Massira ⇄ Clinique Al Baçar

Échange de dossiers patients entre deux établissements aux systèmes différents,
par **Bundles FHIR R5 (5.0.0)** sur HTTPS.

| | Hôpital 1 | Hôpital 2 |
| --- | --- | --- |
| Établissement | CHU Al Massira | Clinique Al Baçar (ophtalmologie) |
| Base | Oracle | MongoDB |
| API | FastAPI, port 8000 | FastAPI, port 8002 |
| Dossier | [`hopital1/`](hopital1/) | [`hopital2/`](hopital2/) |

Les deux établissements **envoient et reçoivent** : le CHU transmet le dossier
d'un patient adressé à la clinique, la clinique renvoie ses résultats, son
imagerie et ses comptes rendus.

```
Oracle ──► API H1 ──HTTPS──► API H2 ──► MongoDB
MongoDB ──► API H2 ──HTTPS──► API H1 ──► Oracle
```

---

## Organisation du dépôt

| Partie | Rôle | Commencer par |
| --- | --- | --- |
| [`hopital1/`](hopital1/) | CHU : Oracle, adaptateurs FHIR, API d'export et de réception | [`hopital1/README.md`](hopital1/README.md) |
| [`hopital2/`](hopital2/) | Clinique : MongoDB, adaptateurs FHIR, API et client d'envoi | [`hopital2/LISEZMOI.md`](hopital2/LISEZMOI.md) |
| [`securite/`](securite/) | Authentification, HTTPS, audit et protections HTTP des deux API | [`securite/README.md`](securite/README.md) |
| [`docs/`](docs/) | Architecture, avancement et procédures communes | [`docs/architecture-et-contributions.md`](docs/architecture-et-contributions.md) |

Le [plan détaillé du dépôt](docs/architecture-et-contributions.md) indique les
fichiers principaux, les tests et les responsabilités de chaque lot. Les noms
des responsables H1 et H2 restent à confirmer par l'équipe : un commit Git peut
regrouper le travail de plusieurs personnes.

Chaque service garde ses modules **à plat** dans son dossier : ils s'importent
entre eux par leur nom (`import config as C`, `import oracle_repo as repo`) et
se lancent depuis ce dossier. Le package `securite/` vit à la racine parce qu'il
est partagé par les deux.

---

## Mise en route

Sur Windows PowerShell, depuis la racine du dépôt :

```powershell
# Un environnement Python local et les dépendances des trois parties
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r securite/requirements.txt -r hopital1/requirements.txt -r hopital2/requirements.txt

# Sécurité : jetons, certificats, garde-fou de commit
.\.venv\Scripts\python.exe securite/outils/generer_jetons.py
$ipDuPoste = Read-Host "Adresse IP utilisée pour joindre ce poste"
.\.venv\Scripts\python.exe securite/outils/generer_certificats.py --ip $ipDuPoste
.\.venv\Scripts\python.exe securite/outils/installer_hooks.py

# Configuration locale de chaque service
if (-not (Test-Path hopital1/.env)) { Copy-Item hopital1/.env.example hopital1/.env }
if (-not (Test-Path hopital2/.env)) { Copy-Item hopital2/.env.example hopital2/.env }
# Renseigner ensuite les valeurs propres à chaque poste dans les fichiers .env.
```

Détail des variables : [`docs/securite/configuration.md`](docs/securite/configuration.md).
Pour lancer H1 et H2 en parallèle, ouvrir deux terminaux distincts à la
racine du dépôt. H1 nécessite Oracle ; H2 nécessite MongoDB.

### Lancer l'API du CHU (H1)

```powershell
Set-Location hopital1
..\.venv\Scripts\python.exe -m uvicorn app:app --port 8000 `
    --ssl-keyfile ../securite/certificats/h1.key.pem `
    --ssl-certfile ../securite/certificats/h1.cert.pem
```

### Lancer l'API de la clinique (H2)

```powershell
Set-Location hopital2
..\.venv\Scripts\python.exe -m uvicorn api_h2:app --port 8002 `
    --ssl-keyfile ../securite/certificats/h2.key.pem `
    --ssl-certfile ../securite/certificats/h2.cert.pem
# Avec MongoDB en conteneur : docker compose up -d
```

Sur un poste de test isolé, sans certificats : `SEC_MODE=local` et
`SEC_TLS_REQUIS=0` dans le `.env`.

### Démonstration sans serveur ni base

```powershell
Set-Location hopital2
..\.venv\Scripts\python.exe demo.py
```

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
| Connexion du personnel | `POST /auth/connexion`, `/auth/renouvellement`, `/auth/deconnexion`, `GET /auth/moi` | idem |
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
[`docs/securite/consentement.md`](docs/securite/consentement.md)) ; anti-boucle (les données reçues d'un établissement ne lui sont
jamais renvoyées) ; rejeu sans doublon par identifiants métier stables ;
conflits signalés, jamais d'écrasement silencieux.

---

## Sécurité

Toutes les routes de dossier exigent un jeton **et** la portée correspondante
(`h1:export`, `h2:import`, …). Sans authentification configurée, le service
répond `503` : il ne s'ouvre jamais.

- [`SECURITY.md`](SECURITY.md) — périmètre et signalement
- [`docs/securite/authentification.md`](docs/securite/authentification.md) — comptes du personnel, rôles et sessions (`/auth/...`)
- [`docs/securite/consentement.md`](docs/securite/consentement.md) — consentement au partage (loi 09-08)
- [`securite/README.md`](securite/README.md) — mode d'emploi de la couche
- [`docs/securite/politique-securite.md`](docs/securite/politique-securite.md) — politique, menaces, matrice des droits
- [`docs/securite/procedure-secrets.md`](docs/securite/procedure-secrets.md) — jetons et mots de passe
- [`docs/securite/tls-https.md`](docs/securite/tls-https.md) — mise en place de HTTPS

```powershell
.\.venv\Scripts\python.exe securite/outils/verifier_securite.py
```

**Ce dépôt ne doit jamais contenir** : fichier `.env`, jeton en clair, clé
privée, registre de jetons, journal d'accès, dossier patient réel.

---

## Tests

```powershell
# Depuis la racine du dépôt :
.\.venv\Scripts\python.exe -m pytest securite/tests -q
Set-Location hopital2
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ../hopital1
..\.venv\Scripts\python.exe -m pytest -q tests
```

---

## État d'avancement et travail restant

Voir [`docs/etat-avancement.md`](docs/etat-avancement.md) : ce qui est fait de
chaque côté, ce qui reste à faire, et pour qui.

## Qui fait quoi

Les responsabilités **par partie** et les fichiers correspondants sont dans
[`docs/architecture-et-contributions.md`](docs/architecture-et-contributions.md).
L'attribution **par personne** y est à compléter avec les noms validés par l'équipe.
