# Architecture et répartition du projet

Ce document sert de carte du dépôt. Il décrit ce qui se trouve dans chaque lot,
les fichiers à lire en premier et les responsabilités techniques visibles dans
le code. Les noms des contributeurs restent à confirmer par l'équipe :
l'auteur d'un commit de dépôt ou de mise en forme n'est pas nécessairement
l'auteur de chaque module qu'il contient.

## Vue d'ensemble

```text
CHU Al Massira (H1)                       Clinique Al Baçar (H2)
Oracle ⇄ API H1 ⇄ Bundle FHIR R5 ⇄ API H2 ⇄ MongoDB
           └──── sécurité commune : jetons, TLS, audit ────┘
```

Les deux API savent préparer un Bundle et recevoir un retour. Le client
d'envoi avec file d'attente est dans H2. L'envoi HTTP sortant depuis H1 et
un essai complet entre deux postes restent à réaliser ; voir
[`etat-avancement.md`](etat-avancement.md).

## Lire le projet par partie

| Partie | Ce qu'elle réalise | Fichiers repères | Vérification |
| --- | --- | --- | --- |
| Hôpital 1 — CHU | Accès Oracle, export et import FHIR R5, consentement, journal métier | [`app.py`](../hopital1/app.py), [`h1_to_fhir.py`](../hopital1/h1_to_fhir.py), [`fhir_to_h1.py`](../hopital1/fhir_to_h1.py), [`oracle_repo.py`](../hopital1/oracle_repo.py) | [`tests/test_adaptateurs.py`](../hopital1/tests/test_adaptateurs.py) |
| Hôpital 2 — Clinique | Accès MongoDB, export et import FHIR R5, consentement, file d'envoi et reprises | [`api_h2.py`](../hopital2/api_h2.py), [`adaptateur_h2_fhir.py`](../hopital2/adaptateur_h2_fhir.py), [`adaptateur_fhir_h2.py`](../hopital2/adaptateur_fhir_h2.py), [`client_envoi.py`](../hopital2/client_envoi.py) | [`test_api_h2.py`](../hopital2/test_api_h2.py), [`test_client_envoi.py`](../hopital2/test_client_envoi.py) |
| Sécurité commune | Jetons et portées, HTTPS, journal d'accès, limitation de débit, contrôle des commits | [`intergiciels.py`](../securite/intergiciels.py), [`jetons.py`](../securite/jetons.py), [`tls.py`](../securite/tls.py), [`audit.py`](../securite/audit.py), [`hooks/`](../securite/hooks/) | [`tests/`](../securite/tests/) |
| Documentation commune | Contrat, configuration, état du projet et procédures de sécurité | [`etat-avancement.md`](etat-avancement.md), [`securite/`](securite/) | Relecture avec les responsables des trois lots |

### Hôpital 1 : du dossier Oracle au Bundle et retour

- [`app.py`](../hopital1/app.py) expose les routes du CHU.
- [`h1_to_fhir.py`](../hopital1/h1_to_fhir.py) et
  [`fhir_to_h1.py`](../hopital1/fhir_to_h1.py) font les conversions dans les
  deux sens ; [`mapping_H1_FHIR.md`](../hopital1/mapping_H1_FHIR.md) décrit les
  correspondances.
- [`oracle_repo.py`](../hopital1/oracle_repo.py) accède à Oracle et gère
  l'enregistrement du retour. [`schema_retour_h1.sql`](../hopital1/schema_retour_h1.sql)
  définit les tables de réception présentes dans le dépôt.
- [`exporter.py`](../hopital1/exporter.py), [`importer.py`](../hopital1/importer.py)
  et [`valider.py`](../hopital1/valider.py) sont les outils en ligne de commande.

Mode d'emploi : [`hopital1/README.md`](../hopital1/README.md).

### Hôpital 2 : du dossier MongoDB au Bundle et retour

- [`api_h2.py`](../hopital2/api_h2.py) expose les routes de la clinique.
- [`adaptateur_h2_fhir.py`](../hopital2/adaptateur_h2_fhir.py) et
  [`adaptateur_fhir_h2.py`](../hopital2/adaptateur_fhir_h2.py) font les
  conversions ; [`echange.py`](../hopital2/echange.py) contient les règles
  d'échange.
- [`stores.py`](../hopital2/stores.py) porte l'accès aux données.
  [`hopital2_mongodb_v3.js`](../hopital2/hopital2_mongodb_v3.js) et
  [`charger_mongo.py`](../hopital2/charger_mongo.py) préparent les données de
  démonstration.
- [`client_envoi.py`](../hopital2/client_envoi.py) prépare et rejoue les envois
  vers H1. [`Dockerfile`](../hopital2/Dockerfile) et
  [`docker-compose.yml`](../hopital2/docker-compose.yml) servent au déploiement
  local de H2 avec MongoDB.

Mode d'emploi : [`hopital2/LISEZMOI.md`](../hopital2/LISEZMOI.md).

### Sécurité : règles partagées par H1 et H2

- [`config.py`](../securite/config.py), [`jetons.py`](../securite/jetons.py) et
  [`intergiciels.py`](../securite/intergiciels.py) lisent la configuration,
  authentifient les appels et appliquent les portées.
- [`tls.py`](../securite/tls.py) et [`client.py`](../securite/client.py) gèrent
  les certificats et les appels HTTPS sortants.
- [`audit.py`](../securite/audit.py), [`debit.py`](../securite/debit.py) et
  [`entetes.py`](../securite/entetes.py) gèrent le journal d'accès, le débit et
  les en-têtes HTTP.
- [`outils/`](../securite/outils/) contient la génération des jetons et
  certificats, l'audit statique et l'installation du garde-fou de commit.

Mode d'emploi : [`securite/README.md`](../securite/README.md). Politique et
procédures : [`securite/politique-securite.md`](securite/politique-securite.md).

## Attribution à compléter par l'équipe

| Lot | Responsable ou contributeurs | Livrables à valider ensemble |
| --- | --- | --- |
| Hôpital 1 | À confirmer | API Oracle, adaptateurs, schéma et tests H1 |
| Hôpital 2 | À confirmer | API MongoDB, adaptateurs, client, Docker et tests H2 |
| Sécurité | À confirmer | Couche commune, intégration aux deux API, politique, outils et tests de sécurité |

Pour documenter précisément les contributions, chaque personne peut ajouter
son nom, les fichiers ou fonctionnalités qu'elle a réalisés et, si utile, les
commits associés. `git log -- <chemin>` permet de consulter l'historique d'un
lot, mais un commit d'import ou de réorganisation ne prouve pas à lui seul
l'auteur initial de tous les fichiers.

## Où placer la suite du travail

- Code propre à un établissement : `hopital1/` ou `hopital2/`, avec ses tests
  et son mode d'emploi.
- Règle commune de sécurité : `securite/`, avec ses tests dans
  `securite/tests/` et sa procédure dans `docs/securite/`.
- Décision d'interface entre les deux établissements :
  [`etat-avancement.md`](etat-avancement.md), rubrique « À décider ensemble ».
- Secret, certificat, journal ou donnée réelle : hors du dépôt, selon
  [`SECURITY.md`](../SECURITY.md).
