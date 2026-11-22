Salut, voici l'API H2 (Clinique Al Baçar / MongoDB), au même niveau que la tienne : jeton Bearer, `/health`, simulation, import sans doublon, anti-boucle, consentement vérifié des deux côtés, erreurs en OperationOutcome. 146 tests passent. Pas encore testée avec ta vraie API ni avec un MongoDB réel (tests sur MongoDB simulé).

## Tes six demandes

**1. URL de réception** — `POST https://<ADRESSE_IP_DU_POSTE_H2>:8002/api/retours` (alias FHIR : `POST /Bundle`). Le certificat doit contenir cette adresse IP et être vérifié par H1.
À blanc : `POST /api/retours/simulation`. Pour récupérer un dossier H2 : `GET /api/patients/{id H2 ou CIN}/bundle`. Santé : `GET /health` (sans jeton).

**2. Requête** — en-têtes : `Authorization: Bearer <JETON_H2>` · `Content-Type: application/fhir+json` · `X-Exchange-Id: <uuid>` (facultatif ; sinon `Bundle.identifier`).
Corps : un Bundle `transaction` (ou `collection`) avec **un seul Patient** (CIN `urn:ma:cin` et/ou ton IPP `https://chu-almassira.ma/ipp`), un `Consent` actif, des identifiants stables. Exemple prêt à envoyer : `exemples/aller_H1_nouveau_patient.json`.

**3. Réponses** (fichiers dans `exemples/`)
- 201 patient créé / 200 complété ou rejeu : rapport JSON `{simulation, modifications_conservees, echange_id, patient_id, patient_cree, deja_traite, lignes_par_type, deja_presents, alertes, ignores}` (comme le tien, `lignes_par_type` au lieu de `lignes_par_table`).
- Erreurs en `OperationOutcome` : 401 jeton · 403 consentement (Bundle ou dossier H2) · 404 patient inconnu · 409 identité ambiguë · 422 Bundle non conforme · 503 base indisponible (`Retry-After`).

**4. Authentification** — jeton Bearer partagé. Je te le transmets séparément, hors dépôt Git.

**5. Mon Bundle réel depuis MongoDB** — `exemples/retour_H2_P2-0051_retinopathie_imagerie.json` (16 ressources, imagerie DICOM) et `retour_H2_P2-0052_alerte_glaucome.json`. Les deux sont des Bundles `transaction` valides en FHIR R5 (vérifiés avec `fhir.resources`, pas encore avec le validateur officiel). Ils concernent des patients de H2 : dis-moi quel patient de ton CHU je dois exporter pour tester ton import.

**6. Joindre mon serveur** — l'API écoute en HTTPS sur le port 8002. Entre deux postes : même réseau local et mon adresse IP (pas `127.0.0.1`), sinon un tunnel. Le pare-feu limite l'accès au poste H1.

## Le contrat, côté H2

| Sujet | Ce que fait H2 |
|---|---|
| Version / format | FHIR R5 5.0.0, `application/fhir+json` |
| Bundle | `transaction`, un seul Patient. Patient : `POST` + `ifNoneExist: identifier=urn:ma:cin\|<CIN>` ; autres ressources : `PUT Type/id`. Je reçois aussi `collection`. |
| Identité | CIN `urn:ma:cin` ; H2 `urn:clinique-al-bacar:patient` ; ton IPP conservé et renvoyé. Sans CIN ni IPP : 422. CIN et IPP qui pointent vers deux dossiers : 409. |
| Références | `fullUrl = <FHIR_BASE_URL>/<Type>/<id>`, références relatives `Type/id` |
| Création / existant | patient inconnu → créé (P2-xxxx attribué) ; connu → seuls les champs vides sont complétés, jamais d'écrasement |
| Rejeu | identifiants stables (`Encounter = visit_id`, `obs-<visite>-<n>`…) + `X-Exchange-Id` : 2 envois = aucun doublon |
| Mesures | UCUM (`mm[Hg]`), dates ISO 8601 (H2 exporte en UTC, `Z`) ; tension = 85354-9 avec 8480-6 / 8462-4 |
| Imagerie | ImagingStudy + Endpoint, les images restent dans le PACS |
| Consentement | vérifié avant l'export et avant l'intégration |
| Conflits | signalés dans `alertes`, valeur H2 conservée |
| Anti-boucle | ce que j'ai reçu de toi ne t'est pas renvoyé (identité + consentement seulement) |
| AuditEvent | non échangés (journal propre à chaque hôpital) ; ceux que tu m'envoies sont ignorés et listés dans `ignores` |
| Pannes | `X-Exchange-Id`, 503 + `Retry-After`, client d'envoi avec file d'attente (reprises 1 min, 5 min, 30 min, 2 h, 6 h) |

## À décider ensemble

1. Réponse de succès : rapport JSON comme aujourd'hui des deux côtés, ou `transaction-response` FHIR ?
2. Patient en `POST` + `ifNoneExist` (ma proposition) ou `PUT` conditionnel ?
3. Glycémie : ma base stocke des `mg/dL`, l'adaptateur convertit les imports en `g/L`. Quelle unité canonique ?
4. Codes SNOMED œil droit/gauche (`18944008`, `8966001`) que tu signales inactifs : lesquels mettre ?
5. Délais d'attente (je propose 10 s) et reprises, HTTPS, partage du jeton.
