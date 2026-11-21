# API FHIR R5 – Hôpital 2 (Clinique Al Baçar / MongoDB) — v3.0

Même rôle et mêmes règles que l'API de H1 (CHU / Oracle) : **chaque hôpital envoie et reçoit**.
Construite sur les adaptateurs **v3.4** (`adaptateur_h2_fhir.py` = votre `__6_`, `adaptateur_fhir_h2.py`) : v3.3 + traitement de l'identifiant manquant (voir ci-dessous),
et sur `hopital2_mongodb_v3.js` régénéré (60 patients + annuaire en 6 collections séparées).

## Démarrer

Depuis ce dossier, `python demo.py` lance la démonstration sans base et
`python -m pytest -q` lance les 147 tests. Pour démarrer l'API avec MongoDB,
configurer d'abord `hopital2/.env`, les jetons et les certificats selon le
[guide racine](../README.md#mise-en-route), puis lancer `docker compose up -d`.
MongoDB exige un compte et son port n'est accessible que sur le poste local.

Pour charger les données **fictives**, renseigner `MONGO_UTILISATEUR` et
`MONGO_MOT_DE_PASSE` dans `hopital2/.env`, puis exécuter depuis ce dossier :

```powershell
docker compose up -d mongo
python charger_mongo.py hopital2_mongodb_v3.js
docker compose up -d api
```

Le chargeur refuse une base déjà remplie. L'option `--remplacer` efface puis
recrée les collections du jeu de démonstration ; elle doit être utilisée
uniquement si cette remise à zéro est voulue. Les identifiants restent dans le
`.env` local et ne sont pas passés en ligne de commande.

Une route protégée refuse tout appel sans jeton. Si aucune source de jetons
n'est configurée, elle répond `503`. Les échanges entre postes exigent HTTPS.
Variables principales : `MONGO_UTILISATEUR`, `MONGO_MOT_DE_PASSE`, `MONGO_DB`,
`FHIR_BASE_URL`, `H1_IPP_SYSTEM` et celles de la
[couche sécurité](../docs/securite/configuration.md). `MONGO_URI` reste une
option pour une base externe ; dans le déploiement Compose local, l'API construit
l'URI à partir des identifiants du `.env`.

## Routes

| Route | Rôle | Auth |
|---|---|---|
| `GET /health` | l'API répond-elle ? (503 si la base est tombée) | non |
| `GET /metadata` | CapabilityStatement | non |
| `GET /api/patients/{id}/bundle` | **ENVOYER** : Bundle transaction du patient (id H2 ou CIN) | oui |
| `POST /api/retours/simulation` | **RECEVOIR à blanc** : tous les contrôles, aucune écriture | oui |
| `POST /api/retours` | **RECEVOIR** : crée (201) ou complète (200) ; rejeu sans doublon | oui |
| `POST /Bundle` · `GET /Patient/{id}/$everything` | alias FHIR des deux routes ci-dessus | oui |
| `POST /Patient` · `GET /Patient/{id}` · `GET /Patient?identifier=` | patient seul | oui |

En-têtes : `Authorization: Bearer <jeton>` · `Content-Type: application/fhir+json` ·
`X-Exchange-Id: <uuid>` (facultatif : identifiant d'échange, rejouer la même requête est sans danger).

| Code | Sens |
|---|---|
| 200 / 201 | reçu et complété / patient créé |
| 400 | corps illisible ou pas un Bundle exploitable |
| 401 | jeton absent ou invalide |
| 403 | consentement absent ou non actif (Bundle **ou** dossier local) |
| 404 | patient inconnu |
| 409 | identité ambiguë (les identifiants pointent vers plusieurs dossiers) ou doublon |
| 422 | Bundle non conforme : champ obligatoire, unité absente, valeur impossible, sortie avant admission, 2 Patient, DELETE… |
| 503 | base indisponible ou écriture non confirmée → renvoyer la même requête (`Retry-After: 30`) |

Les erreurs sont toujours des `OperationOutcome`. Les succès de `/api/retours` sont un rapport JSON
(même forme que celui de H1) : `simulation`, `modifications_conservees`, `echange_id`, `patient_id`, `patient_cree`,
`deja_traite`, `lignes_par_type`, `deja_presents`, `alertes`, `ignores`. Voir `exemples/`.

## Règles appliquées

- **Consentement** vérifié avant l'export et avant l'intégration (Bundle *et* dossier local), tentatives refusées tracées.
- **Anti-boucle** : tout ce qui est reçu de H1 est marqué `_origin: "H1"` et n'est jamais renvoyé à H1.
- **Rejeu sans doublon** : clés naturelles (observation = LOINC + date, visite = `visit_id`…), identifiants stables, `X-Exchange-Id`.
- **Pas d'écrasement silencieux** : une valeur H2 existante est conservée, la divergence est renvoyée dans `alertes`
  (cas D3 groupe sanguin, D5 orthographe). Seuls les champs vides sont complétés.
- **Identité** : CIN `urn:ma:cin`, identifiant H2 `urn:clinique-al-bacar:patient`, IPP du CHU conservé (`_external_ids`).
  Homonyme avec CIN différent = patient distinct (D6). Sans CIN ni IPP = 422.
- **Atomicité** : un dossier = un document MongoDB ; données et journal d'audit s'écrivent ensemble.
- **Export** : Bundle `transaction`, un seul Patient (création conditionnelle `ifNoneExist` sur le CIN), autres ressources en `PUT Type/id`,
  unités UCUM (`mmHg` → `mm[Hg]`), sans `AuditEvent` (journal propre à chaque hôpital), `Bundle.identifier` = identifiant d'échange.
- **Annuaire séparé** : praticiens, rôles, services, équipements, endpoints et organisation sont dans leurs propres collections ; à l'export l'API joint à chaque dossier ce qu'il référence (`echange.enrichir_annuaire`), avec `interpretation` (N/H…) et `referenceRange` du schéma v3.
- **Minimisation** : l'export ne garde que les éléments d'annuaire référencés par le dossier (16 ressources pour P2-0051). `?inclure_catalogue=true` ajoute SON médecin, SON rôle et SON service (19 ressources), jamais les 28 praticiens de la clinique.

## Envoi vers H1 avec file d'attente (`client_envoi.py`)

Export depuis l'API H2 → simulation chez H1 → file SQLite → envoi → reprise. Réessai à 1 min, 5 min, 30 min, 2 h, 6 h
(6 essais), uniquement pour les pannes (injoignable, 408, 429, 5xx). 403/409/422 = « echec », une personne doit regarder.
Le même Bundle et le même identifiant d'échange sont rejoués.
Ce fichier est un **module Python** (`envoyer_dossier`, `reprendre`, `Outbox`),
pas une commande autonome. `demo.py` montre son fonctionnement sans serveur ;
l'orchestration réelle entre les deux API reste à intégrer.

## Ce qui est vérifié, et ce qui ne l'est pas

Vérifié : 147 tests (API sur base mémoire **et** MongoDB simulé, client d'envoi contre une fausse API H1) ; les 60 patients
s'exportent en FHIR R5 valide (`fhir.resources`) et reviennent en base en mode strict ; des tests échouent bien quand on
désactive l'anti-boucle ou qu'on autorise l'écrasement.

**Non vérifié** : MongoDB réel (mongomock seulement — à essayer avec `docker compose`), validateur HL7 officiel
(seulement `fhir.resources`), échange HTTPS de bout en bout avec la vraie API H1, accès simultanés au même patient (dernier écrit gagne, pas de
verrou optimiste).

## Écarts constatés dans les fichiers fournis

- Le `.js` régénéré est cohérent avec le schéma v3 : 7 collections, D2 (P2-0054) `refused` (export bloqué, 403), D4 (P2-0056) sans CIN,
  D13 (P2-0059) date `13/05/1990` convertie en `1990-05-13`, PIO en `mm[Hg]`.
- Les dates sont des `ISODate` (vraies dates BSON) ; l'adaptateur les normalise en UTC.
- Glycémie : la base stocke des `mg/dL` (UCUM valide), mais l'adaptateur v3.3 convertit les imports en `g/L` → une même mesure peut
  exister dans les deux unités ; unité canonique à décider avec H1.
- `PRAC-FASSI_FIHRI` (base) devient l'id FHIR `PRAC-FASSI-FIHRI` : les références sont corrigées dans l'adaptateur v3.4.

## Points à convenir avec H1

1. Format de la réponse de succès (rapport JSON actuel des deux côtés → `transaction-response` FHIR ?).
2. `Patient` : `POST` + `ifNoneExist` (CIN) comme proposé ici, ou `PUT` conditionnel ?
3. Délais d'attente et de reprise (proposition : 10 s de timeout, reprises ci-dessus), HTTPS, partage du jeton hors dépôt.
4. Codes SNOMED œil droit/gauche (`18944008`, `8966001`) signalés inactifs par H1 : à remplacer ensemble.
5. Unité de la glycémie.

## Fichiers

`api_h2.py` routes et sécurité · `echange.py` règles d'échange · `stores.py` base (mémoire / MongoDB) ·
`client_envoi.py` envoi + file d'attente · `charger_mongo.py` chargement du `.js` · `demo.py` démonstration ·
`exemples/` requêtes et réponses fictives · `exemples_h1.py` Bundles « comme H1 » · `test_*.py` tests · `data/` les 60 patients en JSON.

## Identifiant patient manquant (« UNKNOWN »)

Géré à deux niveaux, dans les adaptateurs v3.4 :
- **Export** (`adaptateur_h2_fhir`) : un document sans `patient_id` lève `MissingPatientIdError` ; l'API répond 500 `OperationOutcome` au lieu d'émettre un faux identifiant. Les patients venant de H1 reçoivent un `P2-xxxx` à l'import, donc ce cas ne doit pas se produire en pratique.
- **Import** (`adaptateur_fhir_h2`) : un identifiant H2 « UNKNOWN » (ancien export) est traité comme absent (`patient_id = None`) ; l'API apparie par CIN / IPP puis attribue `P2-xxxx`.
- Les références `Type/ID` passent par `_safe_id` (`PRAC-FASSI_FIHRI` → `PRAC-FASSI-FIHRI`), plus de référence orpheline.
Prévenir H1 du passage en v3.4 si son équipe réutilise ces adaptateurs.
