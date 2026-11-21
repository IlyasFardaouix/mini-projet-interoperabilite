# Référence des variables de configuration

Toute la couche de sécurité se règle par variables d'environnement, chargées
depuis le fichier `.env` local de chaque service. **Aucun secret n'est écrit
dans le dépôt** : `.env` est exclu de Git, seul `.env.example` y figure.

Les valeurs de chemin ont un défaut calculé depuis la racine du dépôt : il n'y a
en général rien à renseigner. Ne les définir que pour placer un fichier ailleurs,
et alors avec un **chemin absolu** (un chemin relatif dépendrait du répertoire
depuis lequel le service est lancé).

---

## Action manuelle requise

Un ancien commit exposait deux mots de passe Oracle : celui de l'administration
et celui du compte applicatif `hopital1`. Les fichiers actuels ne contiennent
que des marqueurs fictifs. Le responsable H1 doit changer les deux mots de
passe dans Oracle et conserver la nouvelle valeur applicative seulement dans
son `.env` local. Une purge de l'historique ne rend pas les anciennes valeurs
sûres : des clones et caches peuvent encore les contenir.

Le reste de ce document liste les variables à ajouter aux deux `.env`.

---

## Jetons d'accès

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `SEC_REGISTRE` | `securite/registre_jetons.json` | Registre des jetons par client. Généré par `generer_jetons.py`. Relu automatiquement quand le fichier change : révoquer un jeton ne demande pas de redémarrage. |
| `H1_API_TOKEN` | *(vide)* | Jeton partagé historique de H1. Accepté mais donne **toutes** les portées du service. À vider dès que le registre est en place. |
| `H2_TOKEN` | *(vide)* | Idem pour H2. |
| `SEC_JWT_SECRET` | *(vide)* | Clé HS256 des jetons JWT à durée de vie courte. Vide = JWT désactivé. |
| `SEC_SESSION_SECRET` | *(vide)* | Clé HS256 des sessions du personnel, propre à chaque hôpital. Vide = connexion `/auth` désactivée (503). Voir `authentification.md`. |
| `SEC_UTILISATEURS` | `securite/comptes/utilisateurs-<service>.json` | Fichier des comptes du personnel (hors Git). |
| `SEC_SESSION_DUREE` | `900` | Durée du jeton d'accès d'une session, en secondes. |
| `SEC_SESSION_RENOUVELLEMENT` | `28800` | Durée du jeton de renouvellement, en secondes. |
| `SEC_JWT_ISS` | `interop-sante` | Émetteur attendu dans le `iss` du JWT. |
| `SEC_JWT_AUD` | nom du service (`H1` / `H2`) | Destinataire attendu dans le `aud` du JWT. |
| `SEC_ROTATION_JOURS` | `90` | Durée de validité par défaut des jetons générés. |

Si aucune des trois sources n'est renseignée, les routes de dossier répondent
`503`. C'est voulu : le service se déclare indisponible plutôt que de s'ouvrir.

## Journal d'accès

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `SEC_JOURNAL` | `journaux/securite-<service>.jsonl` | Fichier du journal d'accès, au format JSONL chaîné. |
| `SEC_SEL_AUDIT` | `sel-local-<service>` | Clé HMAC de pseudonymisation des identifiants de patient. **À renseigner** : avec le défaut, le pseudonyme est prévisible. Valeur propre à chaque service dans `securite/jetons_locaux/env.h1` ou `env.h2`. |
| `SEC_ANONYMISER_IP` | `0` | `1` tronque l'adresse IP (`/24` en IPv4, `/48` en IPv6). Garder `0` pour pouvoir identifier la source d'un accès anormal. |

Un sel **différent par établissement** est normal : il empêche de recouper les
journaux des deux hôpitaux pour reconstituer le parcours d'un patient.

## Transport

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `SEC_MODE` | `strict` | `strict` : TLS exigé, vérification du certificat obligatoire. `local` : tolère le trafic en clair. Réservé à un poste de test isolé. **Ne désactive jamais l'authentification.** |
| `SEC_TLS_REQUIS` | `1` en strict, `0` en local | Refuse les requêtes en clair (403), sauf `/health`. |
| `SEC_TLS_VERIF` | `1` | `0` désactive la vérification du certificat du serveur appelé. Refusé en mode strict : il faut fournir `SEC_CA`. |
| `SEC_CA` | `securite/certificats/ac_interop.cert.pem` | Certificat racine servant à vérifier le serveur appelé. |
| `SEC_PROXY_DE_CONFIANCE` | `0` | `1` fait lire `X-Forwarded-For` et `X-Forwarded-Proto`. À n'activer que derrière un reverse proxy maîtrisé : sinon un appelant choisit son adresse IP et contourne la limitation de débit comme le verrouillage après échecs. |

## Disponibilité

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `SEC_TAILLE_MAX_CORPS` | `5000000` | Taille maximale du corps d'une requête, en octets. Au-delà : `413`. Un Bundle de dossier complet reste très en dessous. |
| `SEC_DEBIT_PAR_MINUTE` | `120` | Requêtes par minute et par adresse appelante. Au-delà : `429` avec `Retry-After`. `/health` et `/metadata` n'y sont pas soumis. |
| `SEC_ECHECS_MAX` | `5` | Échecs d'authentification avant verrouillage de l'adresse. |
| `SEC_VERROU_SECONDES` | `300` | Durée du verrouillage. |

Ces deux compteurs sont **en mémoire** : avec plusieurs *workers* uvicorn, la
limite effective est multipliée par leur nombre. Voir les limites assumées dans
la [politique de sécurité](politique-securite.md).

---

## Configuration des tests

Les suites de tests tournent derrière le client de test de FastAPI, qui parle en
`http://testserver`. En mode strict, chaque requête serait refusée en `403`. Les
fichiers `conftest.py` de chaque service posent donc, **avant** l'import de
l'API :

```python
os.environ.setdefault("SEC_MODE", "local")
os.environ.setdefault("SEC_TLS_REQUIS", "0")
os.environ.setdefault("SEC_DEBIT_PAR_MINUTE", "1000000")
os.environ.setdefault("SEC_JOURNAL", <dossier temporaire>)
```

Le mode local ne désactive pas l'authentification : les tests fournissent un
jeton valide. Les tests qui vérifient spécifiquement TLS et la limitation de
débit sont dans `securite/tests/`, avec leur propre configuration.

L'ordre compte : la configuration de transport est figée au démarrage du
service, c'est-à-dire à l'import du module de l'API. Seule la valeur du jeton
partagé est relue à chaque requête, pour permettre la rotation sans redémarrage.
