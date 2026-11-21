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

```
hopital1/              API et adaptateurs du CHU (Oracle)
hopital2/              API et adaptateurs de la clinique (MongoDB)
securite/              Couche de sécurité commune aux deux API
docs/                  Documentation partagée
  securite/            Politique, procédures, configuration
archive/               Copies historiques locales, exclues du dépôt
```

Chaque service garde ses modules **à plat** dans son dossier : ils s'importent
entre eux par leur nom (`import config as C`, `import oracle_repo as repo`) et
se lancent depuis ce dossier. Le package `securite/` vit à la racine parce qu'il
est partagé par les deux.

---

## Mise en route

```bash
# Dépendances (un environnement par poste)
py -m venv .venv
./.venv/Scripts/python.exe -m pip install -r securite/requirements.txt

# Sécurité : jetons, certificats, garde-fou de commit
py securite/outils/generer_jetons.py
py securite/outils/generer_certificats.py --ip <adresse IP du poste>
py securite/outils/installer_hooks.py

# Configuration locale de chaque service
cp hopital1/.env.example hopital1/.env      # puis renseigner les valeurs
cp hopital2/.env.example hopital2/.env
```

Détail des variables : [`docs/securite/configuration.md`](docs/securite/configuration.md).

### Lancer l'API du CHU (H1)

```bash
cd hopital1
python -m uvicorn app:app --port 8000 \
    --ssl-keyfile ../securite/certificats/h1.key.pem \
    --ssl-certfile ../securite/certificats/h1.cert.pem
```

### Lancer l'API de la clinique (H2)

```bash
cd hopital2
python -m uvicorn api_h2:app --port 8002 \
    --ssl-keyfile ../securite/certificats/h2.key.pem \
    --ssl-certfile ../securite/certificats/h2.cert.pem
# ou, avec MongoDB : docker compose up -d
```

Sur un poste de test isolé, sans certificats : `SEC_MODE=local` et
`SEC_TLS_REQUIS=0` dans le `.env`.

### Démonstration sans serveur ni base

```bash
cd hopital2 && python demo.py
```

---

## Contrat d'échange

| | H1 (CHU) | H2 (Clinique) |
| --- | --- | --- |
| État du service | `GET /health` | `GET /health`, `GET /metadata` |
| Envoyer un dossier | `GET /api/patients/{ipp}/bundle` | `GET /api/patients/{id}/bundle` |
| Recevoir à blanc | `POST /api/retours/simulation` | `POST /api/retours/simulation` |
| Recevoir | `POST /api/retours` | `POST /api/retours`, `POST /Bundle` |
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
intégration ; anti-boucle (les données reçues d'un établissement ne lui sont
jamais renvoyées) ; rejeu sans doublon par identifiants métier stables ;
conflits signalés, jamais d'écrasement silencieux.

---

## Sécurité

Toutes les routes de dossier exigent un jeton **et** la portée correspondante
(`h1:export`, `h2:import`, …). Sans authentification configurée, le service
répond `503` : il ne s'ouvre jamais.

- [`SECURITY.md`](SECURITY.md) — périmètre et signalement
- [`securite/README.md`](securite/README.md) — mode d'emploi de la couche
- [`docs/securite/politique-securite.md`](docs/securite/politique-securite.md) — politique, menaces, matrice des droits
- [`docs/securite/procedure-secrets.md`](docs/securite/procedure-secrets.md) — jetons et mots de passe
- [`docs/securite/tls-https.md`](docs/securite/tls-https.md) — mise en place de HTTPS

```bash
py securite/outils/verifier_securite.py      # auditeur automatique du dépôt
```

**Ce dépôt ne doit jamais contenir** : fichier `.env`, jeton en clair, clé
privée, registre de jetons, journal d'accès, dossier patient réel.

---

## Tests

```bash
./.venv/Scripts/python.exe -m pytest securite/tests -q     # couche de sécurité
cd hopital2 && python -m pytest -q                         # API de la clinique
cd hopital1 && python -m pytest -q tests                   # adaptateurs du CHU
```

---

## État d'avancement et travail restant

Voir [`docs/etat-avancement.md`](docs/etat-avancement.md) : ce qui est fait de
chaque côté, ce qui reste à faire, et pour qui.

## Qui fait quoi

| Partie | Périmètre |
| --- | --- |
| Hôpital 1 | Base Oracle, adaptateurs H1 ⇄ FHIR, API du CHU |
| Hôpital 2 | Base MongoDB, adaptateurs H2 ⇄ FHIR, API de la clinique, client d'envoi |
| Sécurité | `securite/`, `docs/securite/`, durcissement des deux API, organisation du dépôt |
