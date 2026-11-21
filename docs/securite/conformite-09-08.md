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
| Sécurité et confidentialité du traitement | ✅ dont chiffrement au repos côté H2 (limites ci-dessous) |
| Traçabilité des accès | ✅ |
| Finalité et proportionnalité (minimisation) | ✅ H2 aligné sur H1 : ville et pays, sans rue ni tiers |
| Durée de conservation | ⚠️ fixée pour le journal d'accès, pas pour les journaux métier |
| Droit d'opposition | ✅ retrait du consentement |
| Droit d'accès | ✅ route réservée au DPO, sur les deux établissements |
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
| Données adéquates et non excessives | ni H1 ni H2 n'envoient la rue ; H2 n'envoie plus la personne à prévenir (`echange.minimiser_patient`) ; annuaire et journal patient exclus par défaut, chacun derrière sa portée | ✅ |
| Données exactes | conflits signalés, jamais d'écrasement silencieux (groupe sanguin, identité) | ✅ |
| Durée de conservation limitée | journal d'accès : 1 an (`politique-securite.md` § 8.6) ; journaux métier (`journal_echange`, `_audit_log`) : non fixée, aucune purge | ⚠️ |

### Droits de la personne — art. 5, 7, 8, 9

| Droit | Preuve | État |
| --- | --- | --- |
| Information au moment de la collecte (art. 5) | aucune notice : identité du responsable, finalité, destinataires, droits | ❌ |
| Accès (art. 7) | `GET /api/patients/{id}/droit-acces` (portée `droit_acces`, rôle `dpo`) : données détenues, données reçues de l'autre établissement, consentement et historique, journal des accès et des échanges, destinataires, finalité, durées de conservation, voies de recours ; la demande elle-même est tracée (voir plus bas) | ✅ |
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
| Confidentialité au repos | H2 : dossiers MongoDB et file d'envoi chiffrés (AES-256-GCM, clé hors base, index aveugles) ; H1 et Orthanc : chiffrement du disque du poste ([`chiffrement.md`](chiffrement.md)) | ✅ H2 / ⚠️ H1 (à mettre en place sur le poste) |
| Jetons partagés historiques | refusés dès que le registre de jetons est en place (sauf `SEC_JETON_HISTORIQUE=1` le temps d'une migration) | ✅ |
| Mots de passe exposés dans un ancien commit | rotation Oracle non faite (`etat-avancement.md`) | ❌ (H1) |

### Réponse au droit d'accès

Mêmes rubriques sur H1 et H2 (`securite/droit_acces.py`) :

| Rubrique | H2 (clinique) | H1 (CHU) |
| --- | --- | --- |
| `donnees` | dossier complet en FHIR R5 (`Bundle` collection) | lignes Oracle du dossier et données reçues de la clinique |
| `origine_des_donnees` | éléments reçus d'un autre établissement (`_origin`) | séjours externes et lignes reçues |
| `consentement` | version en vigueur et historique | idem |
| `destinataires` | exports réussis, par établissement | envois `ALLER` réussis |
| `historique_des_acces` | `_audit_log` du patient | `journal_echange` du patient |
| `finalite`, `conservation`, `droits` | texte commun | texte commun |

Le dossier n'est filtré ni par le consentement ni par l'anti-boucle : c'est le
dossier de la personne elle-même. La demande est enregistrée dans le journal
métier (H2 : `_audit_log` ; H1 : `journal_echange`, sens `DROIT_ACCES`, ajouté
par `schema_consentement_h1.sql`) et dans le journal d'accès (pseudonyme).
Seul le rôle `dpo` porte la portée `droit_acces` : le DPO vérifie l'identité du
demandeur avant de remettre la réponse.

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
| 1 | Changer les mots de passe Oracle exposés (serveur Oracle, hors code) | H1 |
| 2 | Notice d'information du patient (responsable, finalité, destinataires, droits, contact) | équipe |
| 2 | Durée de conservation des journaux métier et procédure de purge tracée | équipe |
| 2 | Activer BitLocker sur les postes (Oracle, Orthanc) ; mettre `H2_CLE_CHIFFREMENT` et lancer `chiffrer_mongo.py` | H1, H2 |
| 3 | Contrôle de l'âge au recueil du consentement (représentant légal pour un mineur) | sécurité |
| — | Déclaration CNDP et analyse d'impact avant toute donnée réelle | établissements |
