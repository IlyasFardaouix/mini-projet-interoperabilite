# État d'avancement

Dernière mise à jour : 21 novembre 2026, après la livraison de la partie
**Sécurité** et la réorganisation du dépôt.

Pour identifier les composants et les responsabilités de chaque lot, voir
[`architecture-et-contributions.md`](architecture-et-contributions.md).

---

## En une phrase

Les deux API fonctionnent chacune de leur côté et sont maintenant protégées par
une couche de sécurité commune. **L'échange réel entre les deux postes n'a
jamais été fait** : c'est l'étape suivante, et elle demande les deux hôpitaux en
même temps.

---

## Hôpital 1 — CHU Al Massira (Oracle)

### Fait

- Oracle installé dans Docker, données chargées.
- Tables de réception des résultats, de l'imagerie et des comptes rendus de la
  clinique (`hopital1/schema_retour_h1.sql`).
- API FastAPI : production du Bundle d'un patient, simulation de retour, import
  définitif.
- Contrôle du consentement local avant export et avant réception.
- Erreurs renvoyées en `OperationOutcome`.
- Import atomique : les données et le journal sont validés ensemble
  (`hopital1/oracle_repo.py`, fonction `recevoir_retour`).
- Rejeu vérifié : deux envois du même retour ne créent pas de doublon (MERGE sur
  les identifiants métier).
- Anti-boucle : les données reçues de la clinique ne lui sont pas réexpédiées.
- Exemples validés en FHIR R5 5.0.0, zéro erreur sur l'aller et le retour. Des
  avertissements restent à revoir.
- Tests des adaptateurs et de l'API.

### Reste à faire

| À faire | Pour qui |
| --- | --- |
| Envoi HTTP effectif vers l'API de H2 (le code d'envoi n'existe pas encore côté CHU) | H1 |
| Lire l'en-tête `X-Exchange-Id` et le reporter dans `journal_echange` | H1 |
| Ajouter à `journal_echange` les colonnes : identifiant d'échange, destinataire, empreinte du jeton, adresse IP, code HTTP | H1 |
| Rendre atomique l'import en ligne de commande `hopital1/importer.py` : les données sont validées, puis le journal séparément. Si le journal échoue, les données restent écrites sans trace. La route API, elle, est correcte | H1 |
| Remplacer les codes SNOMED œil droit / œil gauche signalés inactifs (`18944008`, `8966001`) | H1 + H2 |
| Trancher l'unité de la glycémie : H1 utilise g/L, H2 stocke mg/dL | H1 + H2 |
| Reporter la mention « R4 » du cahier des charges en R5 | H1 |
| Les DDL des tables de base (`patient`, `consentement`, `sejour`, `diagnostic`, `mesure`) ne sont pas dans le dépôt : seul le schéma de retour y est | H1 |

---

## Hôpital 2 — Clinique Al Baçar (MongoDB)

### Fait

- API FastAPI v3.0 : routes d'échange, simulation, import sans doublon.
- Adaptateurs MongoDB ⇄ FHIR dans les deux sens.
- Consentement vérifié dans le Bundle **et** dans le dossier local.
- Anti-boucle par marquage de l'origine (`_origin`) de chaque élément.
- Conflits signalés en alertes, jamais d'écrasement silencieux.
- Client d'envoi avec file d'attente SQLite et reprises (1 min, 5 min, 30 min,
  2 h, 6 h) : `hopital2/client_envoi.py`.
- Journal d'accès métier dans le document du patient (`_audit_log`).
- `Dockerfile` et `docker-compose.yml`, 60 patients de démonstration, exemples
  de Bundles aller et retour.
- Tests de l'API et du client d'envoi.

### Reste à faire

| À faire | Pour qui |
| --- | --- |
| Tester avec un **vrai** MongoDB : la suite tourne sur `mongomock` | H2 |
| Passer les exemples au validateur HL7 officiel | H2 |
| Verrou optimiste : aujourd'hui « dernier écrit gagne » en cas d'écriture simultanée | H2 |
| Vérifier que `data/patients_h2.json` et `exemples/` ne contiennent aucune donnée réelle (ce dépôt est public) | H2 |

---

## À décider ensemble

Ces points bloquent l'échange réel. Ils ne peuvent pas être tranchés d'un seul côté.

| Sujet | Question |
| --- | --- |
| Format de la réponse de réception | Les deux côtés renvoient aujourd'hui un rapport JSON applicatif. Une transaction REST FHIR standard attend un `transaction-response`. Il faut choisir le même des deux côtés. |
| Création du Patient | `POST` + `ifNoneExist` (ce que fait H2) ou `PUT` conditionnel ? |
| Délais et reprises | Délai d'attente, nombre de tentatives, et qui relance. |
| Terminologies | Codes SNOMED œil droit / gauche, unité de la glycémie. |
| `meta.source` de la clinique | H1 attend `https://clinique-yeux.ma/dpi`, à confirmer par H2. |
| Adresses réseau | Chaque hôpital doit communiquer l'adresse IP réelle de son poste. `127.0.0.1` ne désigne que la machine qui exécute la commande. |
| Jetons et certificats | Échange des jetons et du certificat racine, par un canal séparé du dépôt. Voir [`securite/procedure-secrets.md`](securite/procedure-secrets.md). |

---

## Sécurité

### Fait

Couche commune dans [`securite/`](../securite/), branchée sur les deux API.
Détail et justification : [`securite/politique-securite.md`](securite/politique-securite.md).

- Authentification par jeton avec **portées** : un jeton qui n'a le droit que
  d'envoyer un retour ne peut pas lire les dossiers.
- Registre de jetons à empreintes SHA-256, révocation sans redémarrage,
  expiration, rotation.
- JWT HS256 en option, pour des jetons à durée de vie courte.
- **Correction d'une faille** : l'API de la clinique s'ouvrait entièrement quand
  la variable `H2_TOKEN` était absente. Elle répond maintenant `503`.
- **Correction d'une faille** : le paramètre `destinataire` était choisi par
  l'appelant, ce qui permettait de contourner l'anti-boucle et de récupérer les
  données que son propre établissement avait transmises. Il est maintenant
  déduit de l'identité du jeton.
- HTTPS exigé, autorité de certification interne, certificats ECDSA, client
  sortant qui vérifie le certificat et ne suit pas les redirections.
- Journal d'accès JSONL chaîné, incluant les refus 401 / 403 / 413 / 429, sans
  aucune donnée de santé (identifiants pseudonymisés, valeurs sensibles
  masquées).
- Limitation de débit, verrouillage après échecs, limite de taille du corps,
  en-têtes de sécurité HTTP.
- MongoDB avec authentification, port limité à la boucle locale, conteneur sans
  privilège.
- `.gitignore` racine, garde-fou de commit, auditeur automatique du dépôt.

### Reste à faire

| À faire | Pour qui |
| --- | --- |
| Changer dans Oracle les deux mots de passe exposés par un ancien commit : celui du compte d'administration et celui du compte applicatif `hopital1`. La purge de l'historique Git ne remplace pas cette rotation ; les anciens clones et caches peuvent conserver les valeurs. | H1 |
| Vérifier sur chaque poste que `H1_API_TOKEN` et `H2_TOKEN` restent vides lorsque le registre de jetons est en place : ces anciens jetons partagés donnent toutes les portées du service. | H1 et H2 |

Hors périmètre du prototype, listées dans la politique de sécurité :
signature des Bundles, authentification mutuelle TLS, fournisseur d'identité
réel, collecteur de journaux externe.
