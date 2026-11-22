# Sécurité

Mini-projet scolaire d'interopérabilité santé FHIR R5 entre deux établissements
marocains : le CHU Al Massira (`hopital1/`, Oracle) et la Clinique Al Baçar
(`hopital2/`, MongoDB). Le dépôt contient du code de démonstration et des jeux de
données **fictifs**. Aucune donnée de patient réelle n'y est traitée, ni ne doit y
être ajoutée.

## Périmètre

| Couvert | Non couvert |
|---|---|
| Les deux API FastAPI (`hopital1/`, `hopital2/`) | Les systèmes d'information hospitaliers réels |
| La couche de sécurité commune (`securite/`) | Les postes de travail et le réseau des établissements |
| Les adaptateurs FHIR (`hopital1/`, `hopital2/`) | L'hébergement et la sécurité physique |

Seule la branche par défaut est maintenue. Les mesures de sécurité en place et leurs
limites sont décrites dans [`docs/securite/politique-securite.md`](docs/securite/politique-securite.md).

## Signaler un problème

1. **Ne publiez aucun élément sensible** dans un rapport : pas de jeton, pas de mot de
   passe, pas de donnée de patient, pas de capture d'écran les contenant.
2. Pour un problème sans risque immédiat : ouvrir une **issue** GitHub avec le préfixe
   `[securite]` dans le titre.
3. Pour un problème exploitable : utiliser le formulaire privé de l'onglet **Security**
   du dépôt (« Report a vulnerability »), ou passer par le canal de discussion du
   projet pour joindre l'étudiant responsable du lot sécurité.

Éléments utiles dans le signalement : fichier et ligne concernés, requête ou commande
qui reproduit le problème, effet observé, et impact estimé sur les données.

Ce projet est un travail scolaire : il n'y a ni astreinte, ni engagement de délai. Les
signalements sont traités pendant la durée du module, puis consignés dans le tableau des
constats de la politique de sécurité.

## Ce que le dépôt ne doit jamais contenir

| Interdit | Où cela doit se trouver |
|---|---|
| Jetons d'accès (`H1_API_TOKEN`, `H2_TOKEN`, jetons du registre) | `.env` du service, hors dépôt |
| Mots de passe de bases de données (Oracle, MongoDB) | `.env` du service, hors dépôt |
| `SEC_SEL_AUDIT`, `SEC_JWT_SECRET` | `.env` du service, hors dépôt |
| Registre de jetons `securite/registre_jetons.json` | poste du service exposant les routes |
| Clés privées `*.key.pem` et certificats générés | `securite/certificats/`, hors dépôt |
| Journaux d'accès (`journaux/*.jsonl`) | poste du service |
| Bundles ou exports de patients réels (`**/sortie/`) | nulle part : le projet n'utilise que des données fictives |
| Environnements virtuels et caches (`.venv/`, `__pycache__/`, `.pytest_cache/`) | sur le poste uniquement |

Les fichiers `.env.example` ne contiennent que des valeurs fictives. Un secret poussé
une fois est considéré comme compromis, même après suppression : appliquer la procédure
de fuite.

Contrôle avant un commit :

```powershell
git status --porcelain | Select-String -Pattern "\.env$|\.pem$|registre_jetons|jetons_locaux|journaux/"
```

Cette commande ne doit rien afficher.

## Mesures en place, en bref

- Authentification par jeton Bearer, **fail-closed** : sans configuration, le service
  répond 503, jamais 200.
- Droits par client sous forme de portées (`h1:export`, `h2:import`, ...) : un jeton ne
  peut faire que ce que son rôle exige.
- HTTPS exigé en mode strict, avec une autorité de certification interne et
  vérification du certificat à l'appel.
- Journal d'accès JSONL chaîné et pseudonymisé, refus compris.
- Limitation de débit, taille maximale du corps de requête, verrouillage après échecs.
- Consentement du patient vérifié des deux côtés avant tout échange.

## Documentation

| Document | Contenu |
|---|---|
| [`docs/securite/politique-securite.md`](docs/securite/politique-securite.md) | politique complète : données protégées, cadre légal (loi 09-08, CNDP), modèle de menaces, matrice des droits, journalisation, constats d'audit, limites du prototype |
| [`docs/securite/procedure-secrets.md`](docs/securite/procedure-secrets.md) | cycle de vie des secrets : génération, transmission, rotation, révocation, conduite à tenir en cas de fuite |
| [`docs/securite/tls-https.md`](docs/securite/tls-https.md) | mise en place de HTTPS pas à pas, certificats, vérification, erreurs fréquentes |
| [`securite/README.md`](securite/README.md) | utilisation de la couche de sécurité dans le code des deux API |
