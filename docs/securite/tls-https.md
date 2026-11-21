# Mise en place de HTTPS entre les deux hôpitaux

Procédure complète : création de l'autorité de certification interne, lancement des deux
API en HTTPS, échange du certificat racine, vérification, erreurs fréquentes.

| | |
|---|---|
| Version | 1.0 |
| Date | 21 novembre 2026 |
| Public | responsable H1, responsable H2, responsable sécurité |
| Document parent | [`politique-securite.md`](politique-securite.md) |
| Toutes les commandes | les exemples partent de la racine du dépôt (PowerShell) |
| Durée | environ 20 minutes la première fois, les deux postes ensemble |

---

## 1. Pourquoi

Constat P0-2 de l'audit : les deux API répondaient en HTTP clair. Sur un réseau local
partagé, toute personne capable de capturer le trafic lisait :

- le contenu des Bundles : nom, date de naissance, CIN, diagnostics, comptes rendus ;
- l'en-tête `Authorization`, donc le jeton, réutilisable ensuite à volonté ;
- les URL, qui contiennent l'identifiant du patient.

HTTPS (TLS) apporte trois choses, toutes nécessaires ici :

| Apport | Ce qu'il empêche |
|---|---|
| Confidentialité | lire les données de santé et le jeton en transit |
| Authentification du serveur | se faire passer pour l'autre hôpital et récupérer les Bundles ou les jetons |
| Intégrité | modifier un Bundle en transit (valeur d'une mesure, identifiant d'un patient) |

En mode `strict` (défaut), une requête en clair est refusée par la couche de sécurité
avec un 403 et le motif `tls_absent`. Seule `/health` reste joignable en clair.

---

## 2. Vue d'ensemble

| Étape | Qui | Résultat |
|---|---|---|
| 1 | un seul des deux postes crée l'autorité interne et les deux certificats serveurs | `securite/certificats/` |
| 2 | chaque hôpital lance son API avec son certificat | H1 sur `https://...:8000`, H2 sur `https://...:8002` |
| 3 | le poste qui a créé l'autorité transmet `ac_interop.cert.pem` à l'autre | certificat racine présent des deux côtés |
| 4 | chaque appelant renseigne `SEC_CA` | les appels sortants vérifient le certificat du serveur |
| 5 | vérification croisée avec `curl` | `/health` et un échange complet répondent en HTTPS |

Choix de simplicité : **une seule autorité pour les deux hôpitaux**. Chaque certificat
serveur est signé par elle, donc un seul fichier racine suffit à chaque poste pour
vérifier l'autre. En production, chaque établissement aurait sa propre autorité.

---

## 3. Étape 1 — créer l'autorité et les certificats

Dépendance nécessaire, une seule fois :

```powershell
py -m pip install "cryptography>=43"
```

Génération :

```powershell
.\.venv\Scripts\python.exe securite\outils\generer_certificats.py
```

Avec les adresses réelles des postes (voir le chapitre 7, à faire dès maintenant si les
deux API ne tournent pas sur la même machine) :

```powershell
py securite\outils\generer_certificats.py --ip 192.168.1.20 --ip 192.168.1.31 --dns poste-h1 --dns poste-h2
```

Fichiers produits dans `securite/certificats/` :

| Fichier | Contenu | Circule ? |
|---|---|---|
| `ac_interop.cert.pem` | certificat racine de l'autorité interne, valable 5 ans | **oui**, à transmettre à l'autre hôpital |
| `ac_interop.key.pem` | clé privée de l'autorité | **non**, ne quitte jamais le poste |
| `h1.cert.pem` | certificat serveur de H1, valable 1 an | oui, mais inutile à l'autre : il est déjà envoyé pendant la poignée de main TLS |
| `h1.key.pem` | clé privée du serveur H1 | **non** |
| `h2.cert.pem` | certificat serveur de H2 | voir ci-dessus |
| `h2.key.pem` | clé privée du serveur H2 | **non** |

L'outil n'écrase jamais un certificat existant : il faut `--forcer` pour cela. Clés
ECDSA P-256 : plus courtes que RSA pour une solidité équivalente, et acceptées par
uvicorn, httpx et les navigateurs.

Contrôle du contenu, à tout moment :

```powershell
py securite\outils\generer_certificats.py --decrire
```

La sortie donne le sujet, l'émetteur, la date d'expiration, le nombre de jours restants
et surtout les **noms couverts** : c'est cette liste que le client vérifie.

---

## 4. Étape 2 — lancer les API en HTTPS

### H1 — CHU Al Massira, port 8000

```powershell
Set-Location hopital1
..\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --ssl-keyfile ..\securite\certificats\h1.key.pem --ssl-certfile ..\securite\certificats\h1.cert.pem
```

### H2 — Clinique Al Baçar, port 8002

```powershell
Set-Location hopital2
..\.venv\Scripts\python.exe -m uvicorn api_h2:app --host 0.0.0.0 --port 8002 --ssl-keyfile ..\securite\certificats\h2.key.pem --ssl-certfile ..\securite\certificats\h2.cert.pem
```

Points d'attention :

- `--ssl-keyfile` prend la **clé privée**, `--ssl-certfile` le **certificat**. Les
  inverser donne une erreur au démarrage ;
- un seul worker : les compteurs de débit et d'échecs sont en mémoire (constat P2-5) ;
- au démarrage, la couche de sécurité affiche ses anomalies de configuration. La ligne
  `mode strict mais SEC_TLS_REQUIS=0` signifie que le trafic en clair est encore
  toléré : à corriger avant la démonstration ;
- l'URL devient `https://`. Il faut mettre à jour `FHIR_BASE_URL` dans le `.env` de H2,
  qui peut encore valoir `http://localhost:8002/fhir` dans un ancien `.env`.

Vérification locale immédiate, sur le poste lui-même :

```powershell
curl.exe --cacert .\securite\certificats\ac_interop.cert.pem https://localhost:8000/health
```

---

## 5. Étape 3 — transmettre le certificat racine

Le poste qui a créé l'autorité envoie à l'autre hôpital **un seul fichier** :

```
securite\certificats\ac_interop.cert.pem
```

| À transmettre | À ne jamais transmettre |
|---|---|
| `ac_interop.cert.pem` (certificat racine, contenu public) | `ac_interop.key.pem` (clé privée de l'autorité) |
| | `h1.key.pem`, `h2.key.pem` (clés privées des serveurs) |

Un certificat n'est pas un secret : il ne contient qu'une clé publique et des noms. La
clé privée de l'autorité, elle, permet de fabriquer un certificat valable pour
n'importe quel nom : qui l'obtient peut se faire passer pour l'un des deux hôpitaux. Un
simple contrôle avant l'envoi : le fichier transmis se termine par `.cert.pem`, jamais
par `.key.pem`.

Le destinataire le place par exemple dans `securite\certificats\` et peut l'inspecter :

```powershell
py -c "from securite.tls import decrire; print(decrire('securite/certificats/ac_interop.cert.pem'))"
```

---

## 6. Étape 4 — configurer `SEC_CA` chez l'appelant

Chaque service qui **appelle** l'autre doit vérifier le certificat présenté. Il lui faut
pour cela le certificat racine. Dans le `.env` du service appelant :

```dotenv
SEC_MODE=strict
SEC_TLS_REQUIS=1
SEC_CA=C:\chemin\absolu\vers\securite\certificats\ac_interop.cert.pem
```

Pour un essai dans la session courante seulement :

```powershell
$env:SEC_CA = (Resolve-Path .\securite\certificats\ac_interop.cert.pem).Path
```

Ce que `SEC_CA` change concrètement (`securite/client.py:57-71`) :

| `SEC_CA` | Comportement de `client_securise` |
|---|---|
| renseigné | le certificat du serveur appelé doit être signé par cette autorité, et couvrir le nom utilisé dans l'URL |
| vide | seul le magasin de confiance du système est accepté : un certificat interne est donc refusé |
| vide avec `SEC_TLS_VERIF=0` | vérification désactivée — **refusé en mode strict**, accepté seulement avec `SEC_MODE=local` |

Les appels sortants ne suivent pas les redirections : une réponse `3xx` est une anomalie
de configuration, pas un cas à traiter (voir `politique-securite.md`, section 7.4).

---

## 7. Cas du réseau local : mettre la bonne adresse dans le certificat

### 7.1 Pourquoi `127.0.0.1` ne suffit pas

Un client TLS vérifie deux choses : que le certificat est signé par une autorité de
confiance, **et** que le nom utilisé dans l'URL figure dans le certificat. Les clients
actuels ne regardent que l'extension `SubjectAlternativeName` (SAN), pas le
`CommonName`.

`127.0.0.1` et `localhost` ne désignent que la machine qui exécute la commande. Quand le
poste de la clinique appelle `https://192.168.1.20:8000`, il compare `192.168.1.20` au
contenu du SAN. Si le certificat ne couvre que `localhost` et `127.0.0.1`, la
vérification échoue avec une erreur de correspondance de nom, même si le certificat est
valide et signé par la bonne autorité.

Autrement dit : un certificat généré sans option fonctionne pour une démonstration sur
un seul poste, et seulement là.

### 7.2 Trouver l'adresse réelle du poste

```powershell
ipconfig | Select-String -Pattern "IPv4"
```

Relever l'adresse de l'interface réellement utilisée sur le réseau du projet (souvent en
`192.168.x.x` ou `10.x.x.x`).

### 7.3 Regénérer les certificats avec cette adresse

```powershell
py securite\outils\generer_certificats.py --ip 192.168.1.20 --ip 192.168.1.31 --dns poste-h1 --dns poste-h2 --forcer
```

- `--ip` : une occurrence par adresse, répétable. Mettre les adresses des **deux**
  postes si les deux certificats sont générés ici.
- `--dns` : nom de machine, utile si les postes se joignent par nom.
- `--forcer` : nécessaire pour remplacer des certificats déjà présents.
- `localhost`, `127.0.0.1`, `::1`, le nom de la machine et ses adresses IPv4 locales
  sont ajoutés automatiquement.

Contrôler ensuite que l'adresse figure bien dans les noms couverts :

```powershell
py securite\outils\generer_certificats.py --decrire
```

Si l'adresse IP du poste change (DHCP, changement de réseau ou de salle), il faut
regénérer le certificat. C'est la limite d'une autorité interne sur un réseau local :
prévoir cette opération avant la démonstration, pas pendant.

---

## 8. Vérification avec curl

Sous PowerShell, `curl` est un alias de `Invoke-WebRequest` : il faut écrire
**`curl.exe`** pour utiliser le vrai client.

Étape 1 — la route libre, depuis l'autre poste :

```powershell
curl.exe --cacert .\securite\certificats\ac_interop.cert.pem https://192.168.1.20:8000/health
```

Réponse attendue : `{"status":"ok","service":"H1","fhirVersion":"5.0.0"}`.

Étape 2 — une route protégée, avec le jeton lu dans l'environnement (il n'apparaît pas à
l'écran) :

```powershell
curl.exe --cacert .\securite\certificats\ac_interop.cert.pem -H "Authorization: Bearer $env:H1_API_TOKEN" https://192.168.1.20:8000/api/patients/P1-0106/bundle
```

Étape 3 — contrôler que le refus du trafic en clair fonctionne. L'appel suivant doit
échouer, pas réussir :

```powershell
curl.exe http://192.168.1.20:8000/api/patients/P1-0106/bundle
```

Étape 4 — vérifier les en-têtes de sécurité et le code de retour :

```powershell
curl.exe -i --cacert .\securite\certificats\ac_interop.cert.pem https://192.168.1.20:8000/health
```

`Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy` et
`Cache-Control: no-store` doivent être présents.

**Ne pas utiliser `-k` (ou `--insecure`).** Cette option désactive la vérification du
certificat : l'échange reste chiffré, mais n'importe quel serveur peut se faire passer
pour l'autre hôpital, ce qui annule l'intérêt de TLS. Si `-k` est nécessaire pour que
l'appel passe, c'est le certificat ou `SEC_CA` qu'il faut corriger.

---

## 9. Erreurs fréquentes

| Message | Cause | Correction |
|---|---|---|
| `certificate verify failed: unable to get local issuer certificate` | le client ne connaît pas l'autorité interne : `SEC_CA` absent, mal orthographié, ou `--cacert` oublié | renseigner `SEC_CA` avec le chemin **absolu** du certificat racine reçu (chapitre 6) |
| `certificate verify failed: Hostname mismatch` ou `IP address mismatch` | l'adresse de l'URL ne figure pas dans le SAN du certificat : certificat généré pour `localhost` seulement | regénérer avec `--ip` et `--dns`, puis `--forcer` (chapitre 7) |
| `certificate verify failed: certificate has expired` | certificat serveur de plus d'un an, ou horloge du poste fausse | vérifier la date du poste, puis `py securite\outils\generer_certificats.py --forcer` |
| 403 avec `Ce service n'accepte que HTTPS` | l'appel est parti en `http://` alors que `SEC_TLS_REQUIS=1` | corriger l'URL en `https://`, et `FHIR_BASE_URL` dans le `.env` |
| `SSLError: WRONG_VERSION_NUMBER` | appel en `https://` vers un serveur démarré sans `--ssl-keyfile` | relancer uvicorn avec les deux options TLS (chapitre 4) |
| `ConfigurationTlsRefusee: SEC_TLS_VERIF=0 n'est accepté qu'avec SEC_MODE=local` | tentative de désactiver la vérification en mode strict | fournir le certificat racine au lieu de désactiver le contrôle |
| `FileNotFoundError` sur un `.pem` au démarrage d'uvicorn | chemin relatif erroné : les commandes du chapitre 4 se lancent depuis le dossier du service | utiliser le chemin absolu des fichiers, ou se placer dans le bon dossier |
| `OutilsTlsAbsents` | la bibliothèque `cryptography` n'est pas installée | `py -m pip install "cryptography>=43"` |
| Aucune réponse, délai dépassé | le pare-feu du poste bloque le port 8000 ou 8002 entrant, ou l'API écoute sur `127.0.0.1` seulement | autoriser le port sur le réseau local, lancer uvicorn avec `--host 0.0.0.0` |

---

## 10. Renouvellement des certificats

Les certificats serveurs sont valables 1 an, l'autorité 5 ans. À contrôler avant chaque
période d'utilisation :

```powershell
py securite\outils\generer_certificats.py --decrire
```

En dessous de 30 jours restants, l'outil affiche un avertissement. Le renouvellement se
fait avec `--forcer` et les mêmes options `--ip` et `--dns` qu'à la création. Si seul le
certificat serveur est renouvelé, l'autorité ne change pas : l'autre hôpital n'a rien à
refaire. Si l'autorité est recréée, il faut retransmettre `ac_interop.cert.pem` des deux
côtés.

---

## 11. Mode dégradé, réservé à un poste de test isolé

```dotenv
SEC_MODE=local
SEC_TLS_REQUIS=0
SEC_TLS_VERIF=0
```

Ce réglage remet les deux API en HTTP clair et désactive la vérification des
certificats. Il n'est acceptable que si **toutes** les conditions suivantes sont
réunies :

- un seul poste, qui héberge les deux API, appelées par `localhost` ;
- aucune donnée réelle : uniquement les jeux de données fictifs du projet ;
- aucun autre équipement sur le même réseau capable de capturer le trafic ;
- usage temporaire : mise au point ou exécution des tests.

Interdictions associées :

- jamais en démonstration devant un public, ni sur le réseau de l'établissement ;
- jamais avec un `.env` contenant des mots de passe de bases réelles ;
- jamais laissé en place : on revient à `SEC_MODE=strict` dès la fin de la mise au
  point.

`SEC_TLS_VERIF=0` est refusé si `SEC_MODE` n'est pas `local` : la couche de sécurité
lève une erreur au lieu d'appliquer un réglage dangereux
(`securite/client.py:57-71`). C'est volontaire : un réglage de poste de test ne doit pas
pouvoir se propager en configuration de démonstration.

---

## 12. Aide-mémoire

| Besoin | Commande |
|---|---|
| Installer la dépendance | `py -m pip install "cryptography>=43"` |
| Créer autorité et certificats | `py securite\outils\generer_certificats.py` |
| Avec les adresses du réseau local | `py securite\outils\generer_certificats.py --ip <adresse> --dns <nom> --forcer` |
| Regénérer un seul service | `py securite\outils\generer_certificats.py --service h2 --forcer` |
| Voir échéances et noms couverts | `py securite\outils\generer_certificats.py --decrire` |
| Lancer H1 en HTTPS | `py -m uvicorn app:app --host 0.0.0.0 --port 8000 --ssl-keyfile ..\securite\certificats\h1.key.pem --ssl-certfile ..\securite\certificats\h1.cert.pem` |
| Lancer H2 en HTTPS | `py -m uvicorn api_h2:app --host 0.0.0.0 --port 8002 --ssl-keyfile ..\securite\certificats\h2.key.pem --ssl-certfile ..\securite\certificats\h2.cert.pem` |
| Tester une route libre | `curl.exe --cacert <racine> https://<adresse>:8000/health` |
| Inspecter un certificat reçu | `py -c "from securite.tls import decrire; print(decrire('securite/certificats/ac_interop.cert.pem'))"` |
