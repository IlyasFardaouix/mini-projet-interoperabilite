# Conformité à la loi 09-08

Vérification, exigence par exigence, de ce que le prototype respecte, de la
preuve correspondante dans le dépôt et de ce qui manque. Établie le 21 novembre
2026, après les lots consentement, authentification et imagerie.

Les numéros d'articles sont donnés à titre de repère : ils sont à vérifier sur
le texte publié au Bulletin officiel (loi n° 09-08, dahir n° 1-09-15 du
18 février 2009) avant toute citation dans le rapport.

Légende : ✅ respecté dans le prototype · ⚠️ partiel · ❌ absent · 🏛️ hors code
(démarche administrative ou organisationnelle).

## Synthèse

| Exigence | État |
| --- | --- |
| Consentement de la personne | ✅ |
| Données sensibles (santé) : sécurité renforcée | ✅ |
| Sécurité et confidentialité du traitement | ✅ (limites du prototype ci-dessous) |
| Traçabilité des accès | ✅ |
| Finalité et proportionnalité (minimisation) | ⚠️ adresse complète exportée par H2 |
| Durée de conservation | ⚠️ fixée pour le journal d'accès, pas pour les journaux métier |
| Droit d'opposition | ✅ retrait du consentement |
| Droit d'accès | ❌ pas de route d'extraction pour la personne |
| Droit de rectification | ⚠️ pas de route dédiée ni de trace de rectification |
| Droit à l'information | ❌ pas de notice remise au patient |
| Déclaration / autorisation CNDP | 🏛️ non faite (prototype sans données réelles) |
| Transfert vers l'étranger | ✅ aucun : tout reste sur les postes des deux établissements |

## Détail

### Consentement — art. 4 ; données sensibles — art. 1 et 21

| Exigence | Preuve dans le dépôt | État |
| --- | --- | --- |
| Consentement préalable au partage de données de santé | règle commune `securite/consentement.py`, appliquée avant chaque export, chaque réception et chaque lecture d'image par l'autre établissement | ✅ |
| Consentement libre, spécifique et limité | finalité « soins », destinataires désignés, catégories exclues (imagerie, comptes rendus, allergies), période de validité | ✅ |
| Preuve du consentement | date, signataire (patient ou représentant légal), agent qui l'a recueilli ; une version par changement, jamais d'écrasement | ✅ |
| Retrait à tout moment | `POST /api/patients/{id}/consentement/retrait` ; envois en attente annulés (`client_envoi.reprendre`) | ✅ |
| Mineurs et majeurs protégés | `signataire = representant_legal` enregistré ; l'âge n'est pas contrôlé à la saisie | ⚠️ |

Voir [`consentement.md`](consentement.md).

### Qualité des données, finalité, proportionnalité — art. 3

| Exigence | Preuve | État |
| --- | --- | --- |
| Finalité déterminée | continuité des soins entre le CHU et la clinique ; contrôlée par le consentement (`finalites`) | ✅ |
| Données adéquates et non excessives | H1 n'envoie pas la rue (`hopital1/mapping_H1_FHIR.md`) ; annuaire et journal patient exclus par défaut, chacun derrière sa portée | ⚠️ |
| Écart constaté | **H2 exporte l'adresse complète (rue) et le téléphone vers H1** (`adaptateur_h2_fhir.py`, `build_patient`). Les deux établissements n'appliquent pas la même règle | ❌ à trancher |
| Données exactes | conflits signalés, jamais d'écrasement silencieux (groupe sanguin, identité) | ✅ |
| Durée de conservation limitée | journal d'accès : 1 an (`politique-securite.md` § 8.6) ; journaux métier (`journal_echange`, `_audit_log`) : non fixée, aucune purge | ⚠️ |

### Droits de la personne — art. 5, 7, 8, 9

| Droit | Preuve | État |
| --- | --- | --- |
| Information au moment de la collecte (art. 5) | aucune notice : identité du responsable, finalité, destinataires, droits | ❌ |
| Accès (art. 7) | l'historique du consentement est consultable ; aucune route ne rassemble pour la personne les données détenues et la liste des accès à son dossier | ❌ |
| Rectification (art. 8) | données modifiables en base ; pas de route dédiée, et la rectification n'est pas propagée à l'autre établissement | ⚠️ |
| Opposition (art. 9) | retrait du consentement, effet immédiat sur les échanges suivants | ✅ |

### Sécurité et confidentialité — art. 23 à 26

| Exigence | Preuve | État |
| --- | --- | --- |
| Authentification | systèmes : registre de jetons et portées ; personnes : comptes nominatifs, rôles, scrypt, sessions courtes, verrouillage ([`authentification.md`](authentification.md)) | ✅ |
| Habilitation au besoin d'en connaître | rôles `medecin`, `accueil` (sans contenu médical), `dpo` ; portées par route ; jetons `*-accueil` sans accès aux dossiers | ✅ |
| Confidentialité du transport | HTTPS exigé, autorité interne, client sans redirection | ✅ |
| Images médicales | PACS non exposé (boucle locale, authentification), passerelle avec portée et consentement, désidentification possible ([`../imagerie.md`](../imagerie.md)) | ✅ |
| Traçabilité | journal d'accès chaîné et pseudonymisé ; journaux métier ; nom de la personne connectée | ✅ |
| Intégrité | chaînage du journal ; contrôle d'appartenance des images à l'étude ; rejeu sans doublon | ✅ |
| Confidentialité au repos | MongoDB et Oracle non chiffrés, fichiers `.env` en clair sur le poste | ❌ |
| Jetons partagés historiques | `H1_API_TOKEN` et `H2_TOKEN` encore acceptés, avec toutes les portées | ⚠️ |
| Mots de passe exposés dans un ancien commit | rotation Oracle non faite (`etat-avancement.md`) | ❌ (H1) |

### Formalités — art. 12 et suivants

| Exigence | État |
| --- | --- |
| Déclaration préalable ou autorisation de la CNDP (données de santé) | 🏛️ non faite : prototype pédagogique sans données réelles. Obligatoire avant toute donnée réelle |
| Registre des traitements, analyse d'impact | 🏛️ non faits ; la politique de sécurité et cette grille en fournissent la matière |

### Transfert vers un État étranger — art. 43 et 44

Aucun transfert : bases, PACS, journaux et comptes restent sur les postes des
deux établissements. Les images Docker (MongoDB, Orthanc) sont des logiciels
téléchargés, pas des données envoyées. ✅ Tant qu'aucun service en nuage hors
du Maroc n'est ajouté.

## Ce qu'il reste à faire, par priorité

| Priorité | Action | Pour qui |
| --- | --- | --- |
| 1 | Aligner la minimisation : ne plus exporter la rue (ni le téléphone, si non nécessaire) depuis H2, comme H1 | H2 + équipe |
| 1 | Changer les mots de passe Oracle exposés ; vider `H1_API_TOKEN` / `H2_TOKEN` une fois le registre en place | H1, H1 + H2 |
| 2 | Route de droit d'accès : données détenues + historique des accès, pour la personne | sécurité |
| 2 | Notice d'information du patient (responsable, finalité, destinataires, droits, contact) | équipe |
| 2 | Durée de conservation des journaux métier et procédure de purge tracée | équipe |
| 3 | Chiffrement au repos (volume chiffré a minima) | H1, H2 |
| 3 | Contrôle de l'âge au recueil du consentement (représentant légal pour un mineur) | sécurité |
| — | Déclaration CNDP et analyse d'impact avant toute donnée réelle | établissements |
