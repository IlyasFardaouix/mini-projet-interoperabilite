# Procédure de gestion des secrets

Cycle de vie des secrets du projet d'interopérabilité : génération, transmission entre
les deux établissements, stockage, rotation, révocation, et conduite à tenir en cas de
fuite.

| | |
|---|---|
| Version | 1.0 |
| Date | 21 novembre 2026 |
| Public | responsable H1, responsable H2, responsable sécurité |
| Document parent | [`politique-securite.md`](politique-securite.md) |
| Toutes les commandes | se lancent depuis `d:\interoperabilite\projet` (PowerShell) |

---

## 1. Les deux règles permanentes

**Règle 1 : jamais de secret dans Git.** Le dépôt est public. Un secret poussé une fois
reste dans l'historique, dans les clones des autres contributeurs et dans les copies de
GitHub. Il est à considérer comme définitivement compromis, même après suppression du
fichier.

**Règle 2 : jamais de secret affiché à l'écran.** Un jeton affiché par `echo`, par un
`print` ou par un outil se retrouve dans l'historique du terminal, dans le
défilement de la fenêtre, dans une capture d'écran et dans un partage d'écran de
démonstration. Les outils du projet écrivent les secrets dans des fichiers et
n'affichent que des empreintes.

Conséquences pratiques :

- aucun secret dans un `.env.example`, un `README`, un commentaire de code, un message
  de commit, une issue ou une capture d'écran ;
- aucun secret passé en argument de ligne de commande (les arguments sont visibles dans
  la liste des processus et dans l'historique du shell) ;
- un secret se transmet par fichier, et le fichier est supprimé après transmission.

---

## 2. Inventaire des secrets

| Secret | Rôle | Détenteur | Emplacement | Forme | Rotation |
|---|---|---|---|---|---|
| `H1_API_TOKEN` | jeton partagé historique de l'API H1 | H1 (valeur attendue), H2 (valeur présentée) | `hopital1/.env`, `hopital2/.env` | 43 caractères, `secrets.token_urlsafe(32)` | 90 jours, puis migration vers le registre |
| `H2_TOKEN` | jeton partagé historique de l'API H2 | H2 (valeur attendue), H1 (valeur présentée) | `hopital2/.env`, `hopital1/.env` | idem | 90 jours, puis migration vers le registre |
| Jetons du registre | un jeton par client (`h1-chu`, `h2-clinique`, `h1-interne`, `h2-interne`, `supervision`, `audit`) | le client porteur ; le serveur n'a que l'empreinte | en clair dans le `.env` du client ; empreinte dans `securite/registre_jetons.json` | 43 caractères, 256 bits | 90 jours (`expire_le`) |
| `SEC_SEL_AUDIT` | clé HMAC de pseudonymisation du journal d'accès | chaque service, séparément | `.env` du service | 43 caractères | voir 6.3 : une rotation casse la correspondance des pseudonymes |
| `SEC_JWT_SECRET` | clé de signature HS256 des JWT, si les JWT sont utilisés | les deux services (valeur commune) | `.env` des deux services | 64 caractères | 90 jours |
| `ORACLE_PWD` | mot de passe du compte Oracle de H1 | H1 | `hopital1/.env` | mot de passe du SGBD | à changer immédiatement (constat P0-7), puis 90 jours |
| Identifiants MongoDB | compte applicatif de la base `hopital2` | H2 | `hopital2/.env` (variables de `MONGO_URI`) | utilisateur et mot de passe | 90 jours |
| `ac_interop.key.pem` | clé privée de l'autorité de certification interne | poste qui a créé l'autorité | `securite/certificats/` | clé ECDSA P-256 | validité 5 ans ; ne sort jamais du poste |
| `h1.key.pem`, `h2.key.pem` | clés privées des certificats serveurs | poste du service concerné | `securite/certificats/` | clé ECDSA P-256 | validité 1 an |

Aucun de ces fichiers n'est suivi par Git (voir chapitre 5).

### 2.1 Même nom de variable, deux significations

| Variable | Sur le poste de H1 | Sur le poste de H2 |
|---|---|---|
| `H1_API_TOKEN` | valeur **attendue** par l'API H1 pour authentifier un appelant | jeton **présenté** par H2 quand il appelle H1 (jeton du client `h2-clinique`) |
| `H2_TOKEN` | jeton **présenté** par H1 quand il appelle H2 (jeton du client `h1-chu`) | valeur **attendue** par l'API H2 |

C'est la même convention que `securite/client.py`, qui lit le jeton dans la variable
d'environnement nommée d'après le service appelé (`variable_jeton="H1_API_TOKEN"`
lorsque H2 appelle H1). Avec le registre, la valeur stockée côté appelant est le jeton
de son client, pas le jeton partagé.

---

## 3. Génération

### 3.1 Jetons du registre (cas normal)

```powershell
cd d:\interoperabilite\projet
py securite\outils\generer_jetons.py
```

L'outil écrit :

| Fichier | Contenu | Suivi par Git |
|---|---|---|
| `securite/registre_jetons.json` | empreintes SHA-256, portées, dates d'expiration | non |
| `securite/jetons_locaux/<client>.txt` | le jeton en clair, un fichier par client | non |
| `securite/jetons_locaux/env.jetons` | `SEC_SEL_AUDIT` et `SEC_JWT_SECRET` à recopier | non |

Aucun jeton n'apparaît à l'écran : la sortie ne donne que le nom du client, le chemin du
fichier et les portées accordées.

Pour régénérer un seul client, ou lui donner d'autres portées :

```powershell
py securite\outils\generer_jetons.py --client h2-clinique --portees h1:simulation,h1:import
```

### 3.2 Installer un jeton dans le `.env` du client

Sans l'afficher, en le lisant depuis le fichier produit à l'étape précédente :

```powershell
py -c "from pathlib import Path; j=Path('securite/jetons_locaux/h2-clinique.txt').read_text(encoding='utf-8').strip(); f=Path('hopital2/.env'); f.write_text((f.read_text(encoding='utf-8') if f.exists() else '').rstrip() + '\nH1_API_TOKEN=' + j + '\n', encoding='utf-8'); print('H1_API_TOKEN installe dans hopital2/.env')"
```

Puis supprimer le fichier de transfert :

```powershell
Remove-Item securite\jetons_locaux\h2-clinique.txt
```

### 3.3 Jeton partagé historique de H1

H1 dispose d'un outil dédié, qui ne remplace jamais une valeur existante et n'affiche
rien (`hopital1/configurer_jeton.py`) :

```powershell
cd d:\interoperabilite\projet\hopital1
py configurer_jeton.py
```

Il faut ensuite redémarrer uvicorn pour que la valeur soit lue.

### 3.4 Valeurs de service

`SEC_SEL_AUDIT` et `SEC_JWT_SECRET` sont produits dans
`securite/jetons_locaux/env.jetons` par `generer_jetons.py`. Chaque service recopie ces
deux lignes dans son propre `.env`, puis le fichier est supprimé.

Un sel différent par hôpital est normal et voulu : il empêche de recouper les journaux
des deux établissements (voir `politique-securite.md`, section 8.4).

### 3.5 Mots de passe de base de données

- **Oracle** : l'ancien mot de passe présent dans un fichier d'exemple
  (constat P0-7) doit être considéré comme divulgué. Le
  responsable H1 change le mot de passe du compte Oracle, puis l'inscrit uniquement
  dans `hopital1/.env`. Les fichiers `.env.example` ne
  contiennent qu'une valeur fictive du type `ORACLE_PWD=a_renseigner`.
- **MongoDB** : le responsable H2 crée un compte applicatif dédié à la base `hopital2`
  et renseigne `MONGO_URI` dans `hopital2/.env`. Le port 27017 reste lié à
  `127.0.0.1`.

### 3.6 Clés et certificats TLS

Voir [`tls-https.md`](tls-https.md). Règle à retenir ici : la clé privée de l'autorité
(`ac_interop.key.pem`) et les clés serveurs (`h1.key.pem`, `h2.key.pem`) ne sont jamais
transmises. Seul le certificat racine (`ac_interop.cert.pem`) circule.

---

## 4. Transmission entre les deux hôpitaux

### 4.1 Qui reçoit quoi

| Élément | De | Vers | Nature |
|---|---|---|---|
| Jeton du client `h2-clinique` | H1 (qui tient le registre de H1) | H2 | secret |
| Jeton du client `h1-chu` | H2 (qui tient le registre de H2) | H1 | secret |
| Empreinte du jeton reçu | le destinataire | l'émetteur, pour contrôle | non secret |
| `ac_interop.cert.pem` | poste qui a créé l'autorité | l'autre hôpital | non secret |
| `ac_interop.key.pem`, `h1.key.pem`, `h2.key.pem` | — | **ne circulent pas** | secret |

Le registre est tenu par le service qui **expose** les routes : H1 déclare le jeton de
`h2-clinique`, H2 déclare celui de `h1-chu`. Chacun ne connaît donc que l'empreinte du
jeton de l'autre.

### 4.2 Canal séparé

Le jeton et l'adresse du service ne passent jamais par le même canal. Si le jeton
circule par messagerie, l'adresse et la procédure circulent autrement, et inversement.
Un seul canal compromis ne doit pas suffire à obtenir un accès.

Combinaison retenue pour le projet :

| Information | Canal |
|---|---|
| Fichier contenant le jeton | remise directe (clé USB, poste à poste) ou archive chiffrée dont le mot de passe est dicté de vive voix |
| Adresse du service, port, procédure | canal écrit habituel du projet |
| Empreinte du jeton, pour contrôle | canal écrit habituel du projet |

À éviter : coller un jeton dans une conversation de groupe, un ticket, un commentaire de
code ou un message de commit. Ces supports sont conservés et recherchables.

### 4.3 Contrôle après réception

Le destinataire vérifie qu'il a reçu le bon jeton, sans le réafficher, en comparant son
empreinte à celle annoncée par l'émetteur :

```powershell
py -c "from pathlib import Path; from securite.jetons import empreinte_complete; print('sha256:' + empreinte_complete(Path('securite/jetons_locaux/h1-chu.txt').read_text(encoding='utf-8').strip()))"
```

L'empreinte affichée doit être identique, caractère pour caractère, à celle du champ
`empreinte` de l'entrée correspondante du registre.

---

## 5. Stockage

| Règle | Détail |
|---|---|
| Un seul emplacement par secret | le `.env` du service, ou `securite/registre_jetons.json` pour les empreintes. Pas de copie de sauvegarde « au cas où » |
| Hors dépôt Git | les fichiers ci-dessous sont exclus par le `.gitignore` racine |
| Pas de secret dans l'image Docker | les valeurs sont injectées par l'environnement au lancement, jamais copiées dans l'image |
| Fichiers de transfert éphémères | `securite/jetons_locaux/` est vidé dès la transmission effectuée |

Entrées attendues dans le `.gitignore` racine :

```gitignore
.env
*.env
securite/registre_jetons.json
securite/jetons_locaux/
securite/certificats/
journaux/
**/sortie/
.venv/
__pycache__/
.pytest_cache/
```

Contrôle avant un commit : la commande ci-dessous ne doit rien afficher.

```powershell
git status --porcelain | Select-String -Pattern "\.env$|registre_jetons|jetons_locaux|certificats|\.pem$"
```

---

## 6. Rotation tous les 90 jours

`SEC_ROTATION_JOURS` vaut 90 : les jetons produits par l'outil portent une date
`expire_le` à 90 jours. Après cette date, le jeton est refusé avec un 401, même si
l'entrée est encore active.

### 6.1 Pourquoi 90 jours

Un jeton volé sans être détecté reste utilisable jusqu'à son expiration. 90 jours
bornent cette fenêtre, tout en évitant une rotation si fréquente qu'elle serait faite à
la hâte, ou contournée. La durée coïncide avec le rythme du projet : une rotation par
trimestre, soit une seule pendant le module.

### 6.2 Déroulé (sans coupure de service)

1. **Prévenir** l'autre hôpital de la date de rotation.
2. **Générer** le nouveau jeton du client concerné :

   ```powershell
   py securite\outils\generer_jetons.py --rotation h2-clinique
   ```

   L'entrée du registre est remplacée : nouvelle empreinte, nouvelle date d'expiration.
3. **Transmettre** le fichier produit par le canal séparé (chapitre 4), et communiquer
   l'empreinte par l'autre canal.
4. **Installer** le nouveau jeton dans le `.env` du client (section 3.2), puis
   redémarrer le service appelant.
5. **Vérifier** un échange complet : une simulation, puis un import, doivent répondre
   200 avec le nouveau jeton.
6. **Supprimer** le fichier de transfert des deux côtés.
7. **Noter** l'opération au chapitre 9.

Le registre étant relu à chaud, l'ancienne empreinte cesse d'être valable dès l'écriture
du fichier. Il faut donc enchaîner les étapes 2 à 4 dans la même séance. Pour éviter
toute coupure, on peut créer une seconde entrée temporaire (par exemple
`h2-clinique-2`) avec les mêmes portées, laisser les deux actives le temps de la
bascule, puis désactiver l'ancienne (chapitre 7).

### 6.3 Cas particulier de `SEC_SEL_AUDIT`

Changer le sel modifie tous les pseudonymes : les lignes antérieures du journal ne
peuvent plus être rapprochées des nouvelles. La rotation du sel n'est donc faite qu'en
même temps qu'une archive du journal, et la date du changement est notée au chapitre 9.
Sans cette note, un journal devient illisible pour l'analyse.

---

## 7. Révocation

Révoquer, c'est refuser un jeton sans attendre son expiration : départ d'un
contributeur, poste réinstallé, suspicion de vol.

Dans `securite/registre_jetons.json`, passer le champ `actif` de l'entrée à `false` :

```json
{
  "id": "h2-clinique",
  "empreinte": "sha256:...",
  "portees": ["h1:simulation", "h1:import"],
  "expire_le": "2027-02-19T10:00:00Z",
  "actif": false
}
```

Effets immédiats, sans redémarrage, le registre étant relu dès que le fichier change :

- toute requête présentant ce jeton reçoit un **401** avec le motif `jeton_revoque` ;
- la ligne du journal d'accès conserve l'empreinte du jeton refusé, ce qui permet de
  voir si l'attaquant continue d'essayer.

Ne pas supprimer l'entrée : une entrée inactive garde la trace de l'existence du jeton
et empêche de réattribuer son identifiant par erreur.

---

## 8. En cas de fuite d'un secret

Une fuite est, par exemple : un jeton collé dans une conversation, un `.env` poussé sur
GitHub, une clé privée recopiée sur une clé USB perdue, un mot de passe Oracle affiché
pendant un partage d'écran. Dans le doute, traiter comme une fuite.

### 8.1 Étapes, dans l'ordre

1. **Révoquer** le secret, tout de suite. Jeton du registre : `actif` à `false`
   (chapitre 7). Jeton partagé : vider la variable dans le `.env` et redémarrer, ce qui
   place le service en 503 jusqu'au remplacement — refus de service assumé, préférable
   à un accès ouvert. Mot de passe de base : le changer dans le SGBD. Clé privée TLS :
   regénérer le certificat concerné.
2. **Régénérer** un secret neuf et le transmettre par le canal séparé (chapitres 3
   et 4). Ne jamais réutiliser une ancienne valeur, ni une variante.
3. **Vérifier le journal d'accès** pour savoir si le secret a servi. Rechercher
   l'empreinte courte du jeton compromis :

   ```powershell
   Select-String -Path journaux\securite-h1.jsonl -SimpleMatch '"jeton":"a3f09c71b4de"'
   ```

   Puis contrôler que le journal n'a pas été retouché :

   ```powershell
   py -c "from securite.audit import verifier_chaine; print(verifier_chaine('journaux/securite-h1.jsonl'))"
   ```

   Relever : les adresses IP inconnues, les requêtes hors des heures de travail, les
   suites de 401 et 403, les exports en série. Conserver une copie des lignes
   concernées : elles sont pseudonymisées et peuvent être jointes à un rapport.
4. **Purger l'historique Git** si le secret y est entré. Le fichier doit disparaître de
   tous les commits, pas seulement du dernier :

   ```powershell
   git log --oneline -- hopital1/.env.example
   py -m pip install git-filter-repo
   py -m git_filter_repo --invert-paths --path hopital1/.env --force
   git push --force-with-lease origin main
   ```

   Prévenir les deux coéquipiers avant le `push --force` : chacun doit ensuite
   récupérer l'historique réécrit. Malgré la purge, le secret reste considéré comme
   compromis : l'étape 2 n'est pas optionnelle.
5. **Prévenir.** Dans le projet : les deux coéquipiers immédiatement, l'enseignant dans
   la journée, avec la date de la fuite, la nature du secret et les mesures prises. En
   situation réelle, une fuite portant sur des données de santé déclencherait la
   notification à la CNDP et l'information des personnes concernées (le RGPD retient un
   délai de 72 heures pour l'autorité de contrôle, article 33).
6. **Noter** l'incident au chapitre 9 et, si une mesure manquait, l'ajouter à
   `politique-securite.md`.

### 8.2 Ce qu'il ne faut pas faire

| À éviter | Pourquoi |
|---|---|
| Supprimer le fichier et commiter par-dessus | le secret reste dans l'historique et dans les clones |
| Renommer le secret sans le changer | la valeur divulguée reste valable |
| Attendre de savoir « si quelqu'un l'a vraiment utilisé » | la révocation coûte quelques minutes, l'enquête se fait après |
| Réécrire l'historique sans prévenir | les coéquipiers repoussent l'ancien historique et réintroduisent le secret |

---

## 9. Journal des opérations sur les secrets

À tenir dans ce fichier, à la main. Aucune valeur de secret n'y figure : seulement
l'identifiant du client, la nature de l'opération et sa date.

| Date | Secret concerné | Opération | Motif | Par |
|---|---|---|---|---|
| 2026-11-21 | registre complet | création initiale | mise en place de la couche sécurité | sécurité |
| | | | | |

Opérations possibles : création, rotation, révocation, changement de sel, purge de
journal, incident.

---

## 10. Aide-mémoire des commandes

| Besoin | Commande |
|---|---|
| Créer ou compléter le registre | `py securite\outils\generer_jetons.py` |
| Faire tourner un jeton | `py securite\outils\generer_jetons.py --rotation <client>` |
| Changer les portées d'un client | `py securite\outils\generer_jetons.py --client <client> --portees h1:import` |
| Empreinte d'un jeton reçu, sans l'afficher | `py -c "from pathlib import Path; from securite.jetons import empreinte_complete; print(empreinte_complete(Path('<fichier>').read_text(encoding='utf-8').strip()))"` |
| Vérifier l'intégrité d'un journal | `py -c "from securite.audit import verifier_chaine; print(verifier_chaine('journaux/securite-h1.jsonl'))"` |
| Chercher l'usage d'un jeton | `Select-String -Path journaux\securite-h1.jsonl -SimpleMatch '"jeton":"<empreinte courte>"'` |
| Contrôler qu'aucun secret n'est prêt à être commité | `git status --porcelain \| Select-String -Pattern "\.env$\|\.pem$\|registre_jetons\|jetons_locaux"` |
| Jeton partagé de H1, sans affichage | `cd hopital1` puis `py configurer_jeton.py` |

---

## 11. Vérification de la procédure

Points à contrôler avant la remise du projet :

- [ ] `git ls-files` ne renvoie aucun `.env`, aucun `.pem`, aucun `registre_jetons.json`
- [ ] les fichiers `.env.example` ne contiennent que des valeurs fictives
- [ ] `securite/jetons_locaux/` est vide
- [ ] chaque client du registre a une date `expire_le` dans le futur
- [ ] le mot de passe Oracle du constat P0-7 a été changé
- [ ] le chapitre 9 est à jour
