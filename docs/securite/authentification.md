# Authentification du personnel

Code : [`securite/utilisateurs.py`](../../securite/utilisateurs.py) (comptes et
sessions), [`securite/routes_auth.py`](../../securite/routes_auth.py) (routes),
[`securite/outils/gerer_utilisateurs.py`](../../securite/outils/gerer_utilisateurs.py)
(administration). Branché automatiquement sur H1 et H2 par `installer_securite`.

## Pourquoi

Le registre de jetons authentifie des **systèmes** : l'API de l'autre hôpital, un
outil interne. Il ne dit pas **qui**, dans l'établissement, a consulté un dossier,
envoyé un retour ou modifié un consentement. Or la loi 09-08 impose de pouvoir
tracer les accès aux données de santé, et l'interface graphique sera utilisée par
des personnes. Il fallait donc :

- un compte nominatif par personne, avec des droits liés à sa fonction ;
- des sessions courtes, révocables immédiatement ;
- une protection contre l'essai de mots de passe ;
- le nom de la personne dans les journaux, à la place d'un jeton anonyme.

## Rôles

Un rôle donne des portées existantes ; aucune route n'a été modifiée pour cela.

| Rôle | Portées (préfixées `h1:` ou `h2:` selon le service) | Usage |
| --- | --- | --- |
| `medecin` | `export`, `simulation`, `import`, `patient.lire`, `patient.chercher`, `consentement.lire` | consulter, envoyer et recevoir les dossiers |
| `accueil` | `patient.lire`, `patient.chercher`, `patient.creer`, `consentement.lire`, `consentement.gerer` | identité du patient et recueil du consentement, **sans** le contenu médical |
| `dpo` | `audit`, `consentement.lire` | délégué à la protection des données |

Le rôle est relu à chaque requête : un changement de rôle ou une désactivation
prend effet immédiatement, sans attendre l'expiration du jeton.

## Mots de passe

- Hachage **scrypt** (bibliothèque standard Python), sel aléatoire de 16 octets,
  16 Mio de mémoire par calcul. Le mot de passe n'est jamais stocké ni journalisé.
- Politique : 12 à 128 caractères, sans l'identifiant, ni mot de passe courant,
  ni caractère répété en boucle. La longueur est préférée aux règles de
  composition, qui poussent vers des mots de passe prévisibles.
- Compte créé ou réinitialisé avec un **mot de passe provisoire**. Tant qu'il n'est
  pas changé, la session ne donne accès à aucun dossier.
- Un identifiant inconnu coûte le même calcul qu'un identifiant connu, et le
  message d'erreur est identique : impossible de deviner quels comptes existent.

## Sessions

| Élément | Valeur |
| --- | --- |
| Jeton d'accès | JWT HS256, 15 min (`SEC_SESSION_DUREE`), audience `h1-session` ou `h2-session` |
| Jeton de renouvellement | aléatoire 256 bits, 8 h (`SEC_SESSION_RENOUVELLEMENT`), **usage unique** |
| Secret de signature | `SEC_SESSION_SECRET`, propre à chaque hôpital et distinct de `SEC_JWT_SECRET` |

- Chaque renouvellement fournit un nouveau jeton de renouvellement. Présenter un
  jeton déjà utilisé, signe qu'une copie circule, ferme **toute** la session.
- La déconnexion révoque le jeton d'accès et la chaîne de renouvellement.
- Une session ouverte au CHU n'est pas valable à la clinique : le secret et
  l'audience diffèrent.
- **Verrouillage** : après `SEC_ECHECS_MAX` échecs (5 par défaut), le compte **et**
  l'adresse sont bloqués `SEC_VERROU_SECONDES` (300 s), même avec le bon mot de passe.

## Routes (contrat pour l'interface)

| Route | Authentification | Corps | Réponse |
| --- | --- | --- | --- |
| `POST /auth/connexion` | aucune | `{"login", "mot_de_passe"}` | 200 jetons ; 401 ; 429 verrouillé ; 503 non configuré |
| `POST /auth/renouvellement` | aucune | `{"refresh_token"}` | 200 nouveaux jetons ; 401 |
| `POST /auth/deconnexion` | session | — | 204 |
| `GET /auth/moi` | session | — | 200 compte, rôle, portées |
| `POST /auth/mot-de-passe` | session | `{"ancien", "nouveau"}` | 200 nouveaux jetons ; 401 ancien faux ; 422 nouveau refusé |

Réponse de connexion :

```json
{
  "access_token": "eyJ...", "token_type": "Bearer", "expires_in": 900,
  "refresh_token": "...", "refresh_expires_in": 28800,
  "utilisateur": {"login": "a.bennani", "nom": "Dr A. Bennani", "role": "medecin",
                  "actif": true, "doit_changer_mdp": false},
  "portees": ["h2:consentement.lire", "h2:export", "..."],
  "changement_mdp_requis": false
}
```

L'interface envoie ensuite `Authorization: Bearer <access_token>` sur les routes
habituelles, renouvelle peu avant `expires_in`, et redirige vers le changement de
mot de passe si `changement_mdp_requis` vaut `true`. Les jetons sont à garder en
mémoire, pas dans le `localStorage` du navigateur.

Les jetons du registre (systèmes) restent acceptés comme avant ; les routes
`/auth/moi`, `/auth/deconnexion` et `/auth/mot-de-passe` leur sont refusées (403).

## Administration des comptes

Uniquement en ligne de commande, sur le poste du service : aucune route HTTP ne
crée de compte.

```powershell
.\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h2 creer a.bennani --nom "Dr A. Bennani" --role medecin
.\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h2 lister
.\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h2 role a.bennani dpo
.\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h2 desactiver a.bennani
.\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h2 reinitialiser a.bennani
```

Le mot de passe provisoire s'affiche une seule fois ; il est à remettre en main propre.

Fichier des comptes : `securite/comptes/utilisateurs-<service>.json`, ou
`SEC_UTILISATEURS`. Le dossier `securite/comptes/` est exclu de Git, de l'image
Docker et refusé par le garde-fou de commit. Dans le conteneur H2, il est monté
en écriture (le changement de mot de passe réécrit le fichier) ; l'utilisateur
du conteneur doit pouvoir y écrire.

## Configuration

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `SEC_SESSION_SECRET` | secret de signature des sessions ; vide = connexion désactivée (503) | vide |
| `SEC_UTILISATEURS` | fichier des comptes | `securite/comptes/utilisateurs-<service>.json` |
| `SEC_SESSION_DUREE` | durée du jeton d'accès, en secondes | 900 |
| `SEC_SESSION_RENOUVELLEMENT` | durée du jeton de renouvellement, en secondes | 28800 |

`securite/outils/generer_jetons.py` produit désormais `SEC_SESSION_SECRET` dans
`env.h1` et `env.h2`.

## Journal

- Connexion réussie : ligne `acces` avec `client = utilisateur:<login>`.
- Échec : ligne `refus` avec le **pseudonyme** du compte tenté, jamais le login
  en clair (une personne tape parfois son mot de passe dans le champ identifiant).
- Ensuite, chaque requête d'une session porte `client = utilisateur:<login>` et
  `source_jeton = session` ; les routes de consentement enregistrent ce nom
  dans le journal métier.

## Tests

`securite/tests/test_utilisateurs.py` (30 tests) : politique et hachage,
connexion, verrouillage, désactivation, changement de rôle, session d'un autre
hôpital, jeton expiré ou forgé, renouvellement et rejeu, déconnexion, mot de
passe provisoire, journal sans secret, outil d'administration.

## Limites

| Limite | En production |
| --- | --- |
| Sessions, révocations et compteurs en mémoire : un redémarrage déconnecte tout le monde | magasin partagé (Redis) si plusieurs processus |
| Pas de double authentification | TOTP ou carte professionnelle (CPS) |
| Comptes dans un fichier JSON par poste | annuaire de l'établissement (LDAP / fournisseur OpenID Connect) |
| Pas d'expiration périodique imposée du mot de passe | conforme aux recommandations actuelles : changement sur incident seulement |
