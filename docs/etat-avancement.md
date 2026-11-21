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
- Démarrage local de H2 et d'un vrai MongoDB avec Docker Compose ; `/health`
  répond `200` en HTTPS, 60 patients fictifs ont été chargés, et un appel
  authentifié à `GET /Patient` a confirmé `total=60` (sans jeton : `401`).

### Reste à faire

| À faire | Pour qui |
| --- | --- |
| Tester l'export et l'import de dossiers avec le vrai MongoDB : les tests fonctionnels automatisés emploient `mongomock` ; le test Compose local a validé la connexion, le chargement et la lecture des 60 patients | H2 |
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

### Consentement (loi 09-08)

Règles communes dans `securite/consentement.py`, branchées sur H1 et H2.
Détail et contrat des routes : [`securite/consentement.md`](securite/consentement.md).

- Consentement complet : période de validité, finalité, établissements
  destinataires, catégories exclues du partage (imagerie, comptes rendus,
  allergies), signataire, agent qui l'a recueilli.
- Recueil, retrait (droit d'opposition) et historique sur les deux API, avec
  les portées `consentement.lire` et `consentement.gerer` ; jetons
  `h1-accueil` / `h2-accueil` sans accès aux dossiers.
- Une version par changement, jamais d'écrasement ; trace dans
  `journal_echange` (H1) et `_audit_log` (H2).
- **Correction d'un blocage** : le Bundle de H1 ne contenait aucune ressource
  `Consent` ; H2 aurait refusé (403) tout dossier venu du CHU. H1 joint
  maintenant un `Consent` R5 complet.
- Un envoi en file d'attente chez H2 est annulé si le consentement est retiré
  avant la reprise.
- Migration Oracle : `hopital1/schema_consentement_h1.sql`.

### Authentification du personnel

Comptes nominatifs pour l'interface, sur les deux API. Détail et contrat :
[`securite/authentification.md`](securite/authentification.md).

- Rôles `medecin`, `accueil`, `dpo`, traduits en portées existantes.
- Mots de passe hachés (scrypt), mot de passe provisoire à changer à la première
  connexion, verrouillage par compte et par adresse.
- Jeton d'accès de 15 min, jeton de renouvellement de 8 h à usage unique
  (rejeu détecté), déconnexion et désactivation immédiates.
- Le nom de la personne figure dans le journal d'accès et dans les journaux métier.
- Comptes gérés en ligne de commande : `securite/outils/gerer_utilisateurs.py`.

### Imagerie DICOM

Images échangées en DICOMweb, avec la même sécurité que les dossiers.
Détail : [`imagerie.md`](imagerie.md).

- PACS Orthanc de la clinique dans `docker-compose.yml` : authentification,
  boucle locale, serveur DIMSE désactivé.
- Passerelle `/dicom-web` sur les deux API (WADO-RS, métadonnées), portée
  `imagerie.lire`, consentement, catégorie « imagerie », anti-boucle, journal.
- **Correction** : l'`Endpoint` DICOM des Bundles annonçait le PACS brut
  (`http://localhost:8042`, sans authentification) ; il annonce maintenant la passerelle.
- Images de démonstration cohérentes avec les 42 études de la clinique
  (`charger_dicom.py`) ; récupération et contrôle d'intégrité par le CHU
  (`recuperer_imagerie.py`) ; désidentification PS3.15 en option.

### Reste à faire

| À faire | Pour qui |
| --- | --- |
| Démarrer Orthanc (`docker compose up -d orthanc`) et vérifier la version de l'image ; charger les images avec `charger_dicom.py`. Le code n'a été testé qu'avec un faux serveur DICOMweb. | H2 |
| Lancer un Orthanc local pour le CHU (port 8043) et planifier `recuperer_imagerie.py` après les retours. | H1 |
| Sur chaque poste : relancer `generer_jetons.py --forcer` ou ajouter `SEC_SESSION_SECRET` au `.env`, puis créer les comptes du personnel avec `gerer_utilisateurs.py`. | H1 et H2 |
| Exécuter `hopital1/schema_consentement_h1.sql` sur la base Oracle du CHU, puis tester les routes de consentement contre Oracle (les tests H1 simulent la base). | H1 |
| Régénérer `hopital1/exemples/aller_youssef_S1.json` : l'exemple ne contient pas encore la ressource `Consent`. | H1 |
| Un Bundle d'aller produit par H1 passe le contrôle de consentement de H2 mais est refusé en `422` : H2 ne résout pas les références `urn:uuid:` des séjours (« encounter introuvable »). Écart d'adaptateurs, indépendant du consentement. | H1 + H2 |
| Les retours de H2 envoient leurs ressources en `PUT` alors que H1 n'accepte que des `POST` : à aligner (voir « Création du Patient » plus haut). | H1 + H2 |
| Décider si un retrait de consentement doit être notifié à l'autre établissement. | H1 + H2 |
| Changer dans Oracle les deux mots de passe exposés par un ancien commit : celui du compte d'administration et celui du compte applicatif `hopital1`. La purge de l'historique Git ne remplace pas cette rotation ; les anciens clones et caches peuvent conserver les valeurs. | H1 |
| Vérifier sur chaque poste que `H1_API_TOKEN` et `H2_TOKEN` restent vides lorsque le registre de jetons est en place : ces anciens jetons partagés donnent toutes les portées du service. | H1 et H2 |

Hors périmètre du prototype, listées dans la politique de sécurité :
signature des Bundles, authentification mutuelle TLS, fournisseur d'identité
réel, collecteur de journaux externe.
