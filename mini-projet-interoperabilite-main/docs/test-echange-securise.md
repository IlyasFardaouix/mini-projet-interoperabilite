# Test de l'échange H1 ⇄ H2 avec la sécurité réelle

Complète la fiche « mise en route pour le test complet ». Les trois blocages de sa section 6 sont corrigés :

| Blocage de la fiche | Correction |
| --- | --- |
| H2 ne résout pas les `urn:uuid:` des séjours (422) | `hopital2/adaptateur_fhir_h2.py` : même clé pour l'index et les séjours ; test de non-régression dans `test_api_h2.py` |
| Retours de H2 en `PUT`, H1 n'accepte que `POST` | `hopital1/retour_api.py` accepte `POST` et `PUT` (comme H2) |
| H1 n'a pas de client d'envoi | `hopital1/client_envoi_h1.py` (file SQLite chiffrée, reprises, consentement revérifié) |

Section 4 de la fiche : exécuter **d'abord** `@hopital1/schema_base_h1.sql` (ou `python initialiser_base_h1.py`) si la base de
base n'existe pas, puis `schema_retour_h1.sql`, puis `schema_consentement_h1.sql`.

## Vérifié avec TLS strict et le registre de jetons

Deux serveurs uvicorn séparés en HTTPS (autorité interne, `SEC_CA`), jetons du registre, `SEC_MODE=strict`.
Oracle y était remplacé par une base en mémoire ; MongoDB par le store mémoire de H2.

| Essai | Résultat |
| --- | --- |
| H1 → H2 avec `h1-chu` (client d'envoi H1) | 201 (patient créé chez H2) |
| H1 → H2, patient au consentement refusé | bloqué avant l'envoi (403) |
| H2 → H1 avec `h2-clinique` (client d'envoi H2), puis rejeu | 200 puis 200 |
| Retour clinique réel de H2 (instructions `PUT`) vers H1, simulation, `/api/retours`, `/Bundle` | 200 ; lignes converties : séjour 1, mesures 3, imagerie 1, résultats 2, compte rendu 1 |
| Sans jeton / jeton inconnu | 401 |
| `h2-clinique` qui lit un dossier H1, `h1-chu` sur H1, `h1-interne` sans portée `patient.*` | 403 |
| HTTP sans TLS ; certificat de l'autorité inconnu | connexion refusée |

Le dernier cas a révélé que `h1-interne` n'avait aucune portée `h1:patient.*` : corrigé dans
`securite/outils/generer_jetons.py`. **Relancer `generer_jetons.py` (avec `--rotation h1-interne` si le registre existe) pour
que le registre en place les contienne.**

## Lancer l'envoi H1 → H2 sur le poste du CHU

```powershell
# hopital1/.env : H2_BASE_URL, H1_JETON_VERS_H2 (= jeton h1-chu), H1_BASE_URL, H1_JETON_LOCAL (= jeton h1-interne),
#                 SEC_CA (certificat racine reçu de la clinique), H1_CLE_CHIFFREMENT
cd hopital1
..\.venv\Scripts\python.exe client_envoi_h1.py envoyer P1-0106
..\.venv\Scripts\python.exe client_envoi_h1.py reprendre      # à planifier chaque minute
..\.venv\Scripts\python.exe client_envoi_h1.py etat
```

Ce qui reste hors d'un poste unique : l'échange entre deux machines (adresses IP dans les certificats, jetons transmis
par canal séparé) et l'exécution sur le vrai Oracle.

## Tous les tests dans Docker (Oracle réel compris)

```powershell
docker compose -f docker-compose.tests.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -f docker-compose.tests.yml down -v      # nettoyage, supprime la base jetable
```

Le compose démarre un Oracle jetable (`gvenzl/oracle-free`, aucun port publié) puis un conteneur `tests` qui lance
`lancer_tests_docker.sh` : sécurité + imagerie, H2, H1 (dont les 16 tests Oracle), puis l'audit de sécurité. Code de
sortie 0 = tout vert. Premier lancement : 3 à 5 minutes (image Oracle d'environ 1 Go).
Les mots de passe du fichier sont des valeurs de test jetables ; les tests Oracle y suppriment les tables, jamais
celles du CHU.

Vérifié hors Docker : le script enchaîne bien les quatre étapes et renvoie 0 (683 tests passés, Oracle ignoré). **Le démarrage
d'Oracle et les 16 tests Oracle n'ont pas pu être exécutés** : première exécution à surveiller, notamment le DDL
de `schema_base_h1.sql`, déduit du code.
