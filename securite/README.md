# Couche de sécurité commune

Partie **Sécurité** du mini-projet d'interopérabilité : jetons et droits d'accès,
HTTPS/TLS, journal d'audit, durcissement HTTP. Les deux API (`hopital1/`, le CHU
sur Oracle, et `hopital2/`, la clinique sur MongoDB) branchent le même code, afin
que les règles soient identiques des deux côtés de l'échange et qu'il n'y ait
**qu'une seule implémentation à auditer**.

- Politique, modèle de menaces et matrice des droits : [`docs/securite/politique-securite.md`](../docs/securite/politique-securite.md)
- Gestion et rotation des secrets : [`docs/securite/procedure-secrets.md`](../docs/securite/procedure-secrets.md)
- Mise en place de HTTPS : [`docs/securite/tls-https.md`](../docs/securite/tls-https.md)
- Référence des variables de configuration : [`docs/securite/configuration.md`](../docs/securite/configuration.md)

---

## Mise en route (5 commandes)

À lancer depuis la **racine du dépôt**.

```powershell
# 1. Jetons par client + registre + clés de service
.\.venv\Scripts\python.exe securite/outils/generer_jetons.py

# 2. Autorité de certification interne + certificats des deux API
#    Mettre l'adresse IP réelle du poste : 127.0.0.1 ne désigne que la machine
#    qui exécute la commande, l'autre hôpital ne peut pas s'en servir.
.\.venv\Scripts\python.exe securite/outils/generer_certificats.py --ip 192.168.1.20

# 3. Recopier env.h1 dans hopital1/.env et env.h2 dans hopital2/.env

# 4. Installer le garde-fou de commit (refuse de commiter un secret)
.\.venv\Scripts\python.exe securite/outils/installer_hooks.py

# 5. Vérifier l'état de sécurité du dépôt
.\.venv\Scripts\python.exe securite/outils/verifier_securite.py
```

Puis lancer les services en HTTPS, chacun dans un terminal ouvert à la racine :

```powershell
Set-Location hopital1
..\.venv\Scripts\python.exe -m uvicorn app:app --port 8000 `
    --ssl-keyfile ../securite/certificats/h1.key.pem `
    --ssl-certfile ../securite/certificats/h1.cert.pem
```

```powershell
Set-Location hopital2
..\.venv\Scripts\python.exe -m uvicorn api_h2:app --port 8002 `
    --ssl-keyfile ../securite/certificats/h2.key.pem `
    --ssl-certfile ../securite/certificats/h2.cert.pem
```

Sur un poste de test isolé, sans certificats : `SEC_MODE=local` et
`SEC_TLS_REQUIS=0`. Ce mode n'est pas acceptable dès qu'un vrai échange a lieu.

---

## Branchement dans une API

Deux lignes suffisent. `installer_securite` doit être appelé **avant** la
déclaration des routes : l'intergiciel enveloppe toute l'application.

```python
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from securite import exiger_portee, installer_securite

app = FastAPI(...)
SECURITE = installer_securite(app, service="H1")      # ou "H2"


@app.get("/api/patients/{ipp}/bundle",
         dependencies=[Depends(exiger_portee("export"))])
def exporter_dossier(ipp: str):
    ...
```

Quand la route a besoin de savoir **qui** appelle (pour en déduire le
destinataire, ou pour autoriser une option) :

```python
@app.get("/api/patients/{patient_id}/bundle")
def bundle_patient(patient_id: str, appelant=Depends(exiger_portee("export"))):
    print(appelant.client, appelant.portees)
    if not appelant.autorise("h2:audit"):
        ...
```

---

## Portées (droits)

Une portée = un droit précis sur une route. Elle s'écrit
`<service>:<suffixe>` : `exiger_portee("export")` dans l'API de H2 exige
`h2:export`. Le même code dans l'API de H1 exige `h1:export`.

| Suffixe            | Route couverte                                   |
| ------------------ | ------------------------------------------------ |
| `export`           | `GET /api/patients/{id}/bundle`, `$everything`    |
| `simulation`       | `POST /api/retours/simulation`                    |
| `import`           | `POST /api/retours`, `POST /Bundle`               |
| `patient.lire`     | `GET /Patient/{id}`                               |
| `patient.creer`    | `POST /Patient`                                   |
| `patient.chercher` | `GET /Patient?identifier=...`                     |
| `audit`            | option `inclure_audit=true` (journal du patient)  |
| `annuaire`         | option `inclure_catalogue=true`                   |
| `consentement.lire`  | `GET /api/patients/{id}/consentement`           |
| `consentement.gerer` | `POST /api/patients/{id}/consentement[/retrait]` |

`h1:*`, `h2:*` et `*` existent mais sont à éviter : un jeton volé donne alors
tous les droits du service. Les jetons créés par
`generer_jetons.py` appliquent le moindre privilège (voir le tableau des clients
dans la politique de sécurité).

`/health`, `/metadata`, `/docs`, `/redoc` et `/openapi.json` ne demandent aucun
jeton : ils ne renvoient aucune donnée de patient.

---

## Ce que la couche fait, à chaque requête

| Ordre | Contrôle               | Refus              | Module            |
| ----- | ---------------------- | ------------------ | ----------------- |
| 1     | Transport HTTPS exigé  | 403 `security`     | `intergiciels.py` |
| 2     | Limitation de débit    | 429 + `Retry-After`| `debit.py`        |
| 3     | Taille du corps        | 413 `too-costly`   | `intergiciels.py` |
| 4     | Jeton valide           | 401 / 503          | `jetons.py`       |
| 5     | Portée suffisante      | 403 `forbidden`    | `jetons.py`       |
| 6     | En-têtes de sécurité   | —                  | `entetes.py`      |
| 7     | Ligne de journal       | —                  | `audit.py`        |

Tous les refus sont renvoyés en `OperationOutcome` FHIR, comme les erreurs
métier des deux API.

**Fail-closed** : si aucune source de jetons n'est configurée, les routes de
dossier répondent `503` et ne servent rien. Il n'existe aucun « mode
développement » qui ouvre l'API.

---

## Les trois sources de jetons

Essayées dans cet ordre, pour le même en-tête `Authorization: Bearer <jeton>`.

1. **Registre** `securite/registre_jetons.json` — recommandé. Un jeton par
   client, avec ses portées et sa date d'expiration. Le fichier ne contient que
   des **empreintes SHA-256** : le jeton en clair n'est stocké nulle part, ni
   côté serveur, ni dans Git. Le registre est relu automatiquement quand il
   change : révoquer un jeton ne demande pas de redémarrer le service.
2. **JWT HS256** si `SEC_JWT_SECRET` est défini — pour des jetons à durée de vie
   courte. `alg` est vérifié avant la signature et seul `HS256` est accepté, ce
   qui écarte `alg: none` et la confusion d'algorithme. `iss`, `aud`, `exp` et
   `nbf` sont contrôlés.
3. **Jeton partagé historique** `H1_API_TOKEN` / `H2_TOKEN` — conservé pour ne
   pas casser les postes déjà configurés. Il reçoit toutes les portées du
   service et est signalé « à migrer » au démarrage.

---

## Journal d'accès

`journaux/securite-<service>.jsonl`, une ligne JSON par requête, **y compris les
refus** 401, 403, 413 et 429 — que les journaux métier existants (table Oracle
`journal_echange`, champ `_audit_log` du document Mongo) ne tracent pas.

```json
{"horodatage":"2026-11-21T14:05:02.117Z","service":"H2","evenement":"acces",
 "resultat":"succes","http":200,"methode":"GET","chemin":"/api/patients/{id}/bundle",
 "ressource":"p:9f2c41ab77de0351","ip":"192.168.1.20","client":"h1-chu",
 "jeton":"a41c9e07bb12","portee":"h2:export","duree_ms":58,"prec":"5e8f…"}
```

Trois règles :

- **Aucune donnée de santé.** Les identifiants de patient deviennent un
  pseudonyme HMAC (`p:…`) stable mais non réversible sans la clé
  `SEC_SEL_AUDIT`. La correspondance en clair reste dans le journal de
  l'établissement, déjà protégé par sa base.
- **Les valeurs sensibles sont masquées.** `GET /Patient?identifier=urn:ma:cin|AB123456`
  est journalisé `{"identifier": "***"}` : le CIN ne part pas dans les journaux.
  L'en-tête `Authorization` n'est jamais écrit.
- **Chaînage.** Chaque ligne porte l'empreinte de la précédente (`prec`).
  Retoucher ou supprimer une ligne casse la chaîne :

```bash
py -c "import sys; sys.path.insert(0,'.'); from securite import verifier_chaine; print(verifier_chaine('journaux/securite-h2.jsonl'))"
```

Ce n'est pas une signature : cela ne protège pas contre la réécriture complète
du fichier par quelqu'un qui a la main sur le poste. C'est une limite assumée du
prototype, documentée dans la politique de sécurité.

---

## Contenu du dossier

| Fichier                        | Rôle                                                       |
| ------------------------------ | ---------------------------------------------------------- |
| `config.py`                    | Configuration lue dans l'environnement (variables `SEC_*`) |
| `jetons.py`                    | Registre, JWT HS256, portées, verrouillage après échecs    |
| `audit.py`                     | Journal JSONL chaîné, pseudonymisation, masquage           |
| `entetes.py`                   | Politique d'en-têtes de sécurité HTTP                      |
| `debit.py`                     | Limitation de débit (seau à jetons)                        |
| `intergiciels.py`              | Intergiciel ASGI, `installer_securite`, `exiger_portee`    |
| `client.py`                    | Client httpx durci pour appeler l'autre hôpital            |
| `utilisateurs.py`, `routes_auth.py` | Comptes du personnel, sessions et routes `/auth` — voir [`docs/securite/authentification.md`](../docs/securite/authentification.md) |
| `outils/gerer_utilisateurs.py` | Crée, désactive, réinitialise les comptes du personnel     |
| `consentement.py`              | Règles du consentement (loi 09-08), `Consent` FHIR R5, filtrage du Bundle — voir [`docs/securite/consentement.md`](../docs/securite/consentement.md) |
| `tls.py`                       | Autorité de certification interne et certificats ECDSA     |
| `outils/generer_jetons.py`     | Génère les jetons et le registre                           |
| `outils/generer_certificats.py`| Génère l'autorité et les certificats serveur               |
| `outils/verifier_securite.py`  | Auditeur automatique du dépôt                              |
| `outils/installer_hooks.py`    | Installe le garde-fou de commit                            |
| `hooks/pre-commit`             | Refuse de commiter un secret                               |
| `tests/`                       | Suite pytest de la couche                                  |

Ne sont **jamais** versionnés : `registre_jetons.json`, `jetons_locaux/`,
`certificats/*.key.pem`. Voir le [`.gitignore`](../.gitignore) de la racine.

---

## Tests

```bash
py -m venv .venv
./.venv/Scripts/python.exe -m pip install -r securite/requirements.txt
./.venv/Scripts/python.exe -m pytest securite/tests -q
```

---

## Limites assumées

C'est un prototype de projet scolaire. Ce qui manquerait en production :

- un fournisseur d'identité réel (OAuth 2.0 / SMART on FHIR) au lieu de jetons
  partagés, et l'authentification mutuelle TLS (mTLS) entre les deux API ;
- des certificats délivrés par une autorité reconnue, et des clés privées dans
  un module matériel plutôt que dans un fichier ;
- un journal expédié vers un collecteur extérieur au poste (SIEM), seule façon
  de résister à la réécriture du fichier local ;
- des compteurs de débit et d'échecs partagés : ici ils sont en mémoire, donc
  avec plusieurs *workers* uvicorn la limite effective est multipliée par leur
  nombre ;
- la signature des Bundles échangés, pour la non-répudiation.
