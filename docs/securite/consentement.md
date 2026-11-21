# Consentement au partage du dossier

Règles communes à H1 (Oracle) et H2 (MongoDB), code dans
[`securite/consentement.py`](../../securite/consentement.py). Ce document sert
aussi de contrat pour l'interface graphique : routes, corps attendus, réponses.

## Pourquoi

La loi 09-08 classe les données de santé parmi les données sensibles : leur
partage entre établissements repose sur le consentement de la personne. Jusqu'ici
chaque hôpital vérifiait seulement « statut = actif ». Il manquait :

| Manque | Conséquence | Correction |
| --- | --- | --- |
| Aucune durée de validité | un accord donné il y a des années valait pour toujours | période `debut` / `fin`, contrôlée à chaque échange |
| Aucun destinataire | impossible d'autoriser le CHU sans autoriser tout partenaire | liste `destinataires` (vide = tous) |
| Tout ou rien | refuser l'imagerie obligeait à refuser tout le dossier | `categories_exclues`, retirées du Bundle |
| Aucun retrait ni historique | droit d'opposition impossible à exercer et à prouver | route de retrait ; une version par changement, jamais d'écrasement |
| H1 n'envoyait pas de `Consent` | H2 refusait (403) **tout** dossier venu du CHU | H1 joint un `Consent` R5 complet à chaque Bundle |
| Règles écrites deux fois | risque de divergence entre H1 et H2 | un seul module, utilisé des deux côtés |

## Modèle

| Champ | Valeurs | Défaut |
| --- | --- | --- |
| `statut` | `actif`, `refuse`, `retire`, `en_attente` | — |
| `debut`, `fin` | dates AAAA-MM-JJ, bornes incluses | début = jour du recueil, pas de fin |
| `finalites` | `soins` (continuité des soins) | `soins` |
| `destinataires` | `H1`, `H2` | vide = tous les partenaires |
| `categories_exclues` | `imagerie` (ImagingStudy, Endpoint), `comptes_rendus` (DiagnosticReport), `allergies` (AllergyIntolerance) | aucune |
| `signataire` | `patient`, `representant_legal` | `patient` |
| `recueilli_par` | agent qui a recueilli le consentement ou le retrait | obligatoire |
| `date_retrait`, `motif_retrait` | renseignés par un retrait | — |

Les données existantes restent valides sans migration de contenu : un
consentement sans les nouveaux champs vaut « actif, sans limite de durée, tous
destinataires, rien d'exclu ».

## Décision de partage

Le partage est refusé (403, `OperationOutcome` code `forbidden`) dans l'ordre :

1. aucun consentement ;
2. statut autre que `actif` (refusé, retiré, en attente) ;
3. date du jour avant `debut` ou après `fin` ;
4. finalité demandée non couverte ;
5. destinataire absent de `destinataires`.

Sinon le partage est autorisé et les catégories exclues sont retirées du Bundle,
ainsi que les références qui pointaient vers elles.

Où la règle s'applique :

| Moment | H1 | H2 |
| --- | --- | --- |
| Export d'un dossier | `h1_to_fhir.dossier_vers_bundle` (destinataire H2) | `echange.construire_bundle` (destinataire déduit du jeton) |
| Réception : `Consent` du Bundle | contrôlé s'il est présent, puis retiré avant l'import (`retour_api.extraire_consentement`) | obligatoire (403 sinon), conservé dans le dossier |
| Réception : consentement local | `oracle_repo.verifier_patient_retour` | `echange.importer` |
| Reprise d'un envoi en file | — | `client_envoi.reprendre(..., h2=...)` : annulé si retiré entre-temps ; si non vérifiable, rien ne part |

## Routes (contrat pour l'interface)

Identiques sur les deux API ; `{id}` = IPP (H1) ou identifiant H2.

| Route | Portée | Corps | Réponse |
| --- | --- | --- | --- |
| `GET /api/patients/{id}/consentement` | `consentement.lire` | — | 200 état |
| `POST /api/patients/{id}/consentement` | `consentement.gerer` | voir ci-dessous | 201 état |
| `POST /api/patients/{id}/consentement/retrait` | `consentement.gerer` | `{"recueilli_par": "...", "motif": "..."}` | 200 état |

Recueil :

```json
{
  "statut": "actif",
  "recueilli_par": "Accueil - poste 2",
  "debut": "2026-11-21",
  "fin": "2027-11-21",
  "destinataires": ["H2"],
  "categories_exclues": ["imagerie"],
  "signataire": "patient"
}
```

Seuls `statut` (`actif` ou `refuse`) et `recueilli_par` sont obligatoires. Un
retrait passe par la route `/retrait`, pas par `statut`.

État renvoyé :

```json
{
  "patient_id": "P2-0051",
  "partage_autorise": true,
  "motif": "consentement actif",
  "actuel": {"statut": "actif", "debut": "2026-11-21", "fin": "2027-11-21",
             "destinataires": ["H2"], "categories_exclues": ["imagerie"], "...": "..."},
  "historique": [{"statut": "actif", "...": "..."}]
}
```

H1 renvoie `patient_ipp` au lieu de `patient_id`, et un champ `id` (identifiant
de la version) dans `actuel` et dans chaque version de l'historique.

| Code | Cas |
| --- | --- |
| 401 / 403 | jeton absent ou invalide / portée insuffisante |
| 404 | patient inconnu |
| 409 | retrait demandé sans consentement actif |
| 422 | saisie incohérente (fin avant début, destinataire ou catégorie inconnus, `recueilli_par` absent…) |
| 503 | base indisponible : rien n'est modifié |

Jetons : les clients `h1-accueil` et `h2-accueil` (poste d'accueil) ont
seulement `consentement.lire` et `consentement.gerer`, et ne lisent pas les
dossiers. Les outils internes reçoivent `consentement.lire`, nécessaire à
`client_envoi.reprendre`. Voir `securite/outils/generer_jetons.py`.

## Traçabilité

Chaque recueil et chaque retrait crée une nouvelle version. Les anciennes
versions ne sont jamais modifiées ni supprimées.

- **H1** : une ligne de plus dans `consentement` (identifiant `CST-<n° patient>-<version>`)
  et une ligne `CONSENTEMENT` dans `journal_echange`, dans la même transaction.
  La ligne du patient est verrouillée (`FOR UPDATE`) pendant l'écriture.
- **H2** : l'ancienne version passe dans `consent_history`, une entrée est
  ajoutée à `_audit_log` ; tout est écrit dans le même document, donc de façon atomique.
- Le journal d'accès de la couche sécurité trace l'appel (client, portée, code HTTP)
  avec le pseudonyme du patient.

## FHIR R5

Ressource `Consent` produite par `vers_fhir` et relue par `depuis_fhir` :

| Élément | Contenu |
| --- | --- |
| `status` / `decision` | `active` + `permit` ; refus : `not-done` + `deny` ; retrait : `inactive` + `deny` |
| `period` | `debut` / `fin` (ou date du retrait) |
| `provision.purpose` | `v3-ActReason#TREAT` |
| `provision.actor` | rôle `IRCP` (destinataire), établissement `urn:interop-sante:etablissement` |
| `provision.provision.resourceType` | types exclus : la décision de base s'inverse pour eux |
| `verification` | signataire et date de recueil |
| `policyBasis.url` | `https://www.cndp.ma` |

La ressource est validée par le modèle `fhir.resources` R5 dans les tests.

## Mise en place sur H1

Exécuter une fois [`hopital1/schema_consentement_h1.sql`](../../hopital1/schema_consentement_h1.sql)
avec le compte `hopital1`. Il ajoute les colonnes, accepte le statut `RETIRE` et
le sens `CONSENTEMENT` dans `journal_echange`. Le script est rejouable et
demande Oracle 12.2 ou plus récent (`search_condition_vc`). **Il n'a pas encore
été exécuté sur une vraie base Oracle**.

## Tests

| Suite | Fichier |
| --- | --- |
| Règles communes | `securite/tests/test_consentement.py` |
| H1 (Oracle simulé) | `hopital1/tests/test_consentement.py` |
| H2 (API, file d'envoi, portées) | `hopital2/test_consentement_h2.py` |

## Limites

- La date du jour est celle du serveur qui évalue ; les deux postes doivent être à l'heure.
- Un retrait n'efface pas les données déjà transmises à l'autre établissement :
  il bloque les échanges suivants. Il faudra prévenir l'autre établissement
  du retrait (décision d'équipe, non implémentée).
- Le consentement d'un mineur par son représentant légal est enregistré
  (`signataire`), mais l'âge n'est pas contrôlé à la saisie.
