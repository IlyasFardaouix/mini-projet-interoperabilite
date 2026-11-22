# Interface web du personnel

Une page unique pour les deux hôpitaux. Chaque API la sert elle-même : le CHU sur
`https://127.0.0.1:8000/ui/`, la clinique sur `https://127.0.0.1:8002/ui/`. Le code de la page
est le même (`interface/static/`) ; seul l'adaptateur change : `hopital1/ui_h1.py` (Oracle) et
`hopital2/ui_h2.py` (MongoDB).

## Ce que l'on peut faire

| Section | Rôle qui la voit | Contenu |
| --- | --- | --- |
| Patients | médecin, accueil | recherche par nom, prénom, CIN ou identifiant ; dossier (allergies, séjours, diagnostics, mesures, examens) pour le médecin ; état du consentement dans un bandeau ; bouton **Envoyer à l'autre hôpital** |
| Consentement (onglet) | médecin (lecture), accueil (lecture et écriture) | consentement en vigueur, historique, recueil d'une décision, retrait avec confirmation |
| Envois | médecin | file d'attente : envoyé, en attente (avec l'heure de la prochaine tentative), échec, annulé ; bouton **Relancer les envois en attente** |
| Droit d'accès | DPO | communication de toutes les données détenues sur une personne (loi 09-08, art. 7), téléchargeable en JSON |
| Journal d'accès | DPO | derniers événements du journal de sécurité, avec la vérification du chaînage par empreintes |

Les sections affichées dépendent du rôle (`medecin`, `accueil`, `dpo`) : voir
[authentification](securite/authentification.md).

## Mise en route

1. **Comptes du personnel** (une seule fois par hôpital, sur son poste) :

   ```powershell
   .\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h1 creer dr.bennani --nom "Dr A. Bennani" --role medecin
   .\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h1 creer accueil.nour --nom "Nour Accueil" --role accueil
   .\.venv\Scripts\python.exe securite/outils/gerer_utilisateurs.py --service h1 creer dpo.salma --nom "Salma DPO" --role dpo
   ```

   Même chose avec `--service h2` pour la clinique. Le mot de passe provisoire s'affiche une seule
   fois ; la page demande de le remplacer à la première connexion.
2. **`SEC_SESSION_SECRET`** doit être dans le `.env` de chaque hôpital (`env.h1`, `env.h2` le contiennent).
3. **Envoi depuis la page** : le serveur envoie, jamais le navigateur. Il lui faut, dans son `.env` :

   | Hôpital | Variables |
   | --- | --- |
   | H1 | `H2_BASE_URL`, `H1_BASE_URL`, `H1_JETON_VERS_H2` (jeton `h1-chu`), `H1_JETON_LOCAL` (jeton `h1-interne`), `SEC_CA` |
   | H2 | `H1_BASE_URL`, `H2_BASE_URL`, `H1_API_TOKEN` (jeton `h2-clinique`), `H2_JETON_LOCAL` (jeton `h2-interne`), `SEC_CA` |

   Sans ces variables, le bouton répond « Envoi non configuré » avec le nom de la variable manquante.
4. Démarrer les API comme d'habitude (`uvicorn ... --ssl-keyfile ... --ssl-certfile ...`), puis ouvrir
   `https://127.0.0.1:8000/ui/` ou `https://127.0.0.1:8002/ui/`.
5. **Certificat dans le navigateur** : l'autorité privée n'est pas connue du navigateur, qui affiche un
   avertissement. Soit accepter l'exception pour cette adresse, soit importer
   `securite/certificats/ac_interop.cert.pem` dans les autorités de certification racines de confiance
   (Windows : double-clic sur le fichier, « Installer le certificat », magasin « Autorités de certification
   racines de confiance »).

## Interface principale : la démonstration (sans compte)

Avec `DEMO=1`, la page d'accueil de chaque hôpital (`https://127.0.0.1:8000/ui/` pour le CHU,
`https://127.0.0.1:8002/ui/` pour la clinique) est la **démonstration**, signalée par un bandeau brun
Pas de bandeau. La connexion du personnel reste sur `/ui/index.html`. Les listes se rafraîchissent toutes les 5 secondes.

Pour l'activer, ajouter `DEMO=1` dans `securite/jetons_locaux/env.h1` et `env.h2` (ou `$env:DEMO = "1"`
dans la fenêtre de l'API avant de la lancer).

**Ce que montre la page**
- Trois listes : **Patients** (avec recherche), **Envoyés** (dernier envoi de chaque patient : envoyé,
  en attente, échec, annulé) et **Reçus** (patients pour lesquels l'hôpital a accepté un dossier de l'autre).
- **Informations du patient** : identité, allergies, séjours, diagnostics, mesures, examens.
- **Contenu du Bundle FHIR** : nombre de ressources par type et le JSON de chaque ressource. Pas de Bundle
  tant que le consentement n'est pas « Oui » (l'export est refusé, la raison est affichée).
- **Consentement : Oui ou Non.** « Oui » enregistre un accord, « Non » un refus. Chaque choix ajoute une
  nouvelle version (`recueilli_par = demo`) : l'historique est conservé. Le retrait existe dans l'interface
  du personnel et dans l'API ; la démonstration ne le propose pas.
- **Envoyer à l'autre hôpital**, puis les quatre étapes (consentement, Bundle FHIR, contrôle chez l'autre
  hôpital, envoi et import) et le verdict : Transmis, Bloqué, Mis en file d'attente ou Refusé. Les étapes
  sont déduites de la réponse réelle du circuit d'envoi, rien n'est joué à l'écran.
- **Relancer les envois en attente** : reprise de la file (arrêter l'autre API, envoyer, la relancer).

**Garde-fous** : sans `DEMO=1`, les routes `/api/demo/*` répondent 404 et `/ui/` affiche la connexion du
personnel ; elles refusent (403) tout appel qui ne vient pas de ce poste ; le navigateur ne reçoit jamais de
jeton. La page montre des dossiers : **données de test uniquement**. Désactiver `DEMO` après la démonstration.

**Patient inconnu de l'autre hôpital.** La clinique crée le patient reçu du CHU. Le CHU, lui, refusait un
retour pour un patient inconnu (rapprochement d'identité prudent). Avec `DEMO=1` (ou
`H1_CREER_PATIENTS_RETOUR=1`), le CHU **crée le patient** à la réception, à deux conditions : le Bundle de la
clinique contient un consentement valide pour le CHU, et le patient a un CIN. Le patient et son consentement
(`recueilli_par = Clinique Al Baçar (consentement joint au dossier)`, catégories exclues reprises) sont écrits
dans la même transaction que le dossier : tout ou rien. Un patient déjà connu est toujours rapproché par CIN,
et son consentement local reste contrôlé. Sans ces variables, le comportement d'origine est conservé (404).

**Jeux de données.** Aucun nom de famille n'est répété : 60 noms différents à la clinique (les 10 cas de test
nommés P2-0051 à P2-0060 sont inchangés) et 8 patients différents au CHU, sans nom commun avec la clinique,
hormis les deux identités volontairement partagées (Alaoui et Idrissi, cas S1 et D1). Après mise à jour :

```powershell
python hopital1/initialiser_base_h1.py --reset --donnees      # Oracle : 8 patients
python hopital2/charger_mongo.py hopital2/hopital2_mongodb_v3.js --remplacer   # MongoDB : 60 patients
```

## Ce qui a été fait pour la sécurité

- **Jetons de session en mémoire** : ni `localStorage`, ni cookie, ni URL. Recharger la page déconnecte.
- **Le navigateur n'a jamais le jeton d'échange entre hôpitaux.** Il appelle `POST /api/ui/envoi/{id}` ;
  le serveur exporte le dossier, le teste chez l'autre hôpital, le met en file puis l'envoie avec les
  jetons de son environnement. La session de la personne est tracée au journal (`client = utilisateur:<login>`).
- **Aucun HTML venu de l'API n'est interprété** : tout est inséré comme du texte. Un dossier reçu de l'autre
  hôpital qui contiendrait `<script>` s'affiche tel quel. Un test échoue si le code utilise `innerHTML`,
  `eval`, `localStorage`… (`hopital2/test_interface_h2.py`).
- **Politique CSP dédiée à `/ui`** : scripts et styles de la page seulement, aucune ressource externe,
  aucun cadre. Les routes de données gardent `default-src 'none'`.
- **Routes d'appui protégées par portée** : `patient.chercher` (recherche), `export` (dossier, envoi, file),
  `audit` (journal). Seules la page et `/ui/config.json` (nom de l'établissement) sont publiques.
- Un rôle ne voit que ses sections, mais c'est le **serveur** qui refuse (403) : masquer un bouton n'est pas
  un contrôle d'accès.

## Routes ajoutées

| Route | Portée | Rôle |
| --- | --- | --- |
| `GET /ui`, `/ui/*` | — | page et fichiers statiques |
| `GET /ui/config.json` | — | `{service, etablissement, autre, autre_etablissement}` |
| `GET /api/ui/patients?q=` | `patient.chercher` | recherche (50 résultats au plus) |
| `GET /api/ui/dossier/{id}` | `export` | dossier lisible, même forme des deux côtés |
| `POST /api/ui/envoi/{id}` | `export` | envoi à l'autre hôpital par la file d'attente |
| `GET /api/ui/envois` | `export` | état de la file |
| `POST /api/ui/envois/reprendre?forcer=` | `export` | relance (`forcer=true` n'attend pas l'heure de reprise) |
| `GET /api/ui/journal?limite=` | `audit` | derniers événements + chaînage |

Le consentement et le droit d'accès réutilisent les routes existantes
(`/api/patients/{id}/consentement`, `.../consentement/retrait`, `.../droit-acces`).

## Limites

- **Oracle réel** : la recherche de H1 (`rechercher_patients`), la liste des reçus (`lister_retours`), la création
  d'un patient à la réception (`rattacher_ou_creer_patient`) et les nouveaux patients du jeu de données n'ont
  été exécutés qu'avec une base simulée ; à essayer une fois sur votre Oracle (`tests/test_oracle_reel.py`).
- Sessions en mémoire : redémarrer l'API déconnecte tout le monde (voir authentification).
- La recherche de H2 lit les 1000 premiers dossiers puis filtre : suffisant pour la démonstration, pas pour
  une vraie base.
- Pas de double authentification, pas de saisie ni de modification du dossier médical depuis la page.
- Les heures du journal sont en UTC.


## Images DICOM avec l'envoi

Quand le CHU reçoit un dossier de la clinique (`POST /api/retours`), il récupère tout de suite les images
des examens annoncés (`recuperer_imagerie.recuperer_apres_retour`), avec `DEMO=1` ou `H1_IMAGERIE_AUTO=1`.
La réponse du retour contient `imagerie` (un bilan par examen : `RECUPEREE`, `REFUSEE`, `EN_ATTENTE`...,
`null` si la fonction est inactive) et l'écran de l'expéditeur l'affiche dans la 5e étape « Images DICOM ».
Un échec d'image n'annule jamais l'import du dossier. 

### Aperçu des images

La fiche d'un patient contient une section « Imagerie DICOM » : un bloc par examen, avec une vignette par image
(clic pour agrandir). `GET /api/demo/image/{patient}/{study_uid}/{rang}` lit l'image dans le PACS local (Orthanc de
l'hôpital), la convertit en PNG (`imagerie/apercu.py`, sans bibliothèque d'images) et ne renvoie que les pixels :
aucune étiquette DICOM, donc ni nom ni date de naissance. Le serveur vérifie que l'étude appartient bien au patient
demandé ; au CHU, seules les études `RECUPEREE` s'affichent. Formats lus : pixels non compressés, 8 bits (gris ou RVB)
ou 16 bits (gris). Une image compressée ou illisible affiche « Aperçu indisponible ».
