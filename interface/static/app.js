"use strict";
/* Interface du personnel (H1 et H2). Un seul code pour les deux hopitaux.
   - Les jetons de session restent en memoire : rien dans le stockage du navigateur, rien dans l'URL.
   - Tout contenu venu de l'API est insere comme du TEXTE (noeuds DOM), jamais comme du HTML. */

const racine = document.getElementById("app");
const etat = { config: null, session: null, vue: null, minuteur: null };
const pv = { q: "", resultats: [], selection: null, dossier: null, consentement: null, droit: null,
             onglet: null, envoi: null, chargement: false };

// ------------------------------------------------------------------ outils DOM
function h(balise, props, ...enfants) {
  const el = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(props || {})) {
    if (valeur === null || valeur === undefined || valeur === false) continue;
    if (cle.startsWith("on")) el.addEventListener(cle.slice(2), valeur);
    else if (cle === "class") el.className = valeur;
    else if (valeur === true) el.setAttribute(cle, "");
    else el.setAttribute(cle, valeur);
  }
  ajouter(el, enfants);
  return el;
}
function ajouter(el, enfants) {
  for (const e of enfants.flat(Infinity)) {
    if (e === null || e === undefined || e === false) continue;
    el.append(e instanceof Node ? e : document.createTextNode(String(e)));
  }
}
function vider(el) { while (el.firstChild) el.removeChild(el.firstChild); }
function annoncer(message, erreur) {
  const zone = document.getElementById("annonces");
  const a = h("div", { class: "annonce" + (erreur ? " erreur" : "") }, message);
  zone.append(a);
  setTimeout(() => a.remove(), erreur ? 8000 : 4000);
}

const MOIS = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/;
function date(s) {
  if (!s) return "";
  const m = MOIS.exec(String(s));
  if (!m) return String(s);
  return `${m[3]}/${m[2]}/${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
}
function periode(a) {
  const d = jour(a.debut), f = jour(a.fin);
  if (d && f) return "du " + d + " au " + f;
  if (d) return "depuis le " + d + ", sans date de fin";
  if (f) return "jusqu'au " + f;
  return "sans limite de durée";
}
function jour(s) { return date(s).slice(0, 10); }
function nomComplet(p) { return [p.prenom, (p.nom || "").toUpperCase()].filter(Boolean).join(" "); }
function peut(suffixe) {
  return !!etat.session && etat.session.portees.includes(etat.config.service.toLowerCase() + ":" + suffixe);
}

// ------------------------------------------------------------------ appels API
class ErreurApi extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
function messageErreur(code, donnees, rep) {
  const diag = donnees && donnees.issue && donnees.issue[0] && donnees.issue[0].diagnostics;
  if (code === 429) {
    const attente = rep.headers.get("Retry-After");
    return "Trop de requêtes. Réessayez" + (attente ? ` dans ${attente} s.` : " dans un instant.");
  }
  if (diag) return diag;
  if (code === 401) return "Session expirée. Reconnectez-vous.";
  if (code === 403) return "Votre rôle n'autorise pas cette action.";
  if (code === 404) return "Introuvable.";
  if (code >= 500) return "Le service ne répond pas correctement. Réessayez plus tard.";
  return "Requête refusée (" + code + ").";
}
async function api(chemin, { methode = "GET", corps, sansSession = false } = {}) {
  const lancer = () => {
    const entetes = { Accept: "application/json" };
    if (!sansSession && etat.session) entetes.Authorization = "Bearer " + etat.session.acces;
    if (corps !== undefined) entetes["Content-Type"] = "application/json";
    return fetch(chemin, { method: methode, headers: entetes, body: corps === undefined ? undefined : JSON.stringify(corps),
                           cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer" });
  };
  let rep;
  try { rep = await lancer(); } catch (e) { throw new ErreurApi(0, "Le serveur est injoignable."); }
  if (rep.status === 401 && !sansSession && etat.session && await renouveler()) rep = await lancer();
  const texte = await rep.text();
  let donnees = null;
  try { donnees = texte ? JSON.parse(texte) : null; } catch (e) { donnees = null; }
  if (!rep.ok) {
    if (rep.status === 401 && !sansSession) deconnecterLocalement("Votre session a expiré. Reconnectez-vous.");
    throw new ErreurApi(rep.status, messageErreur(rep.status, donnees, rep));
  }
  return donnees;
}

// ------------------------------------------------------------------ session
function ouvrirSession(jetons) {
  etat.session = { acces: jetons.access_token, renouvellement: jetons.refresh_token,
                   utilisateur: jetons.utilisateur, portees: jetons.portees || [] };
  clearTimeout(etat.minuteur);
  const delai = Math.max(30, (jetons.expires_in || 900) - 60) * 1000;
  etat.minuteur = setTimeout(renouveler, delai);
}
async function renouveler() {
  if (!etat.session) return false;
  try {
    const j = await api("/auth/renouvellement", { methode: "POST", sansSession: true,
                                                  corps: { refresh_token: etat.session.renouvellement } });
    ouvrirSession(j);
    return true;
  } catch (e) {
    deconnecterLocalement("Votre session a expiré. Reconnectez-vous.");
    return false;
  }
}
function deconnecterLocalement(message) {
  clearTimeout(etat.minuteur);
  etat.session = null;
  Object.assign(pv, { q: "", resultats: [], selection: null, dossier: null, consentement: null, droit: null, envoi: null });
  etat.vue = null;
  if (message) annoncer(message, true);
  ecranConnexion();
}
async function seDeconnecter() {
  try { await api("/auth/deconnexion", { methode: "POST" }); } catch (e) { /* session deja invalide */ }
  deconnecterLocalement();
}

// ------------------------------------------------------------------ connexion
function ecranConnexion() {
  document.title = "Connexion · " + etat.config.etablissement;
  const erreur = h("p", { class: "erreur-form", role: "alert" });
  const login = h("input", { type: "text", id: "login", autocomplete: "username", required: true, autocapitalize: "none", spellcheck: "false" });
  const mdp = h("input", { type: "password", id: "mdp", autocomplete: "current-password", required: true });
  const bouton = h("button", { class: "btn", type: "submit" }, "Se connecter");
  const formulaire = h("form", { novalidate: true, onsubmit: async (ev) => {
      ev.preventDefault();
      erreur.textContent = "";
      bouton.disabled = true;
      try {
        const j = await api("/auth/connexion", { methode: "POST", sansSession: true,
                                                 corps: { login: login.value, mot_de_passe: mdp.value } });
        mdp.value = "";
        ouvrirSession(j);
        if (j.changement_mdp_requis || (j.utilisateur && j.utilisateur.doit_changer_mdp)) ecranChangementMdp(true);
        else demarrer();
      } catch (e) {
        erreur.textContent = e.code === 401 ? "Identifiant ou mot de passe incorrect." : e.message;
      } finally { bouton.disabled = false; }
    } },
    h("h2", null, "Connexion du personnel"),
    h("label", null, "Identifiant", login),
    h("label", null, "Mot de passe", mdp),
    erreur, bouton);
  vider(racine);
  racine.append(h("div", { class: "entree" },
    h("section", { class: "entree-marque" },
      h("h1", null, etat.config.etablissement),
      h("p", null, "Consultez les dossiers, vérifiez le consentement du patient et envoyez le dossier à " +
                   etat.config.autre_etablissement + ".")),
    h("main", { class: "entree-form" }, formulaire)));
  login.focus();
}

function ecranChangementMdp(obligatoire) {
  document.title = "Nouveau mot de passe";
  const erreur = h("p", { class: "erreur-form", role: "alert" });
  const ancien = h("input", { type: "password", id: "ancien", autocomplete: "current-password", required: true });
  const nouveau = h("input", { type: "password", id: "nouveau", autocomplete: "new-password", required: true, minlength: "12" });
  const conf = h("input", { type: "password", id: "conf", autocomplete: "new-password", required: true });
  const formulaire = h("form", { novalidate: true, onsubmit: async (ev) => {
      ev.preventDefault();
      erreur.textContent = "";
      if (nouveau.value !== conf.value) { erreur.textContent = "Les deux mots de passe ne sont pas identiques."; return; }
      try {
        const j = await api("/auth/mot-de-passe", { methode: "POST", corps: { ancien: ancien.value, nouveau: nouveau.value } });
        ouvrirSession(j);
        annoncer("Mot de passe changé.");
        demarrer();
      } catch (e) { erreur.textContent = e.message; }
    } },
    h("h2", null, obligatoire ? "Choisissez votre mot de passe" : "Changer le mot de passe"),
    obligatoire ? h("p", null, "Le mot de passe provisoire doit être remplacé avant d'accéder aux dossiers.") : null,
    h("label", null, "Mot de passe actuel", ancien),
    h("label", null, "Nouveau mot de passe", h("span", { class: "aide" }, "12 caractères au moins, sans votre identifiant."), nouveau),
    h("label", null, "Répétez le nouveau mot de passe", conf),
    erreur,
    h("div", { class: "barre" },
      h("button", { class: "btn", type: "submit" }, "Enregistrer"),
      obligatoire ? h("button", { class: "btn secondaire", type: "button", onclick: seDeconnecter }, "Annuler")
                  : h("button", { class: "btn secondaire", type: "button", onclick: demarrer }, "Retour")));
  vider(racine);
  racine.append(h("div", { class: "entree" },
    h("section", { class: "entree-marque" }, h("h1", null, etat.config.etablissement)),
    h("main", { class: "entree-form" }, formulaire)));
  ancien.focus();
}

// ------------------------------------------------------------------ coque
const VUES = [
  { id: "patients", titre: "Patients", portee: "patient.chercher" },
  { id: "envois", titre: "Envois", portee: "export" },
  { id: "droit", titre: "Droit d'accès", portee: "droit_acces" },
  { id: "journal", titre: "Journal d'accès", portee: "audit" },
];
function demarrer() {
  const dispo = VUES.filter((v) => peut(v.portee));
  if (!dispo.length) {
    vider(racine);
    racine.append(h("main", { class: "principal" }, h("h1", null, "Aucun accès"),
      h("p", null, "Votre rôle ne donne accès à aucune fonction de cette interface."),
      h("button", { class: "btn secondaire", onclick: seDeconnecter }, "Se déconnecter")));
    return;
  }
  if (!etat.vue || !dispo.some((v) => v.id === etat.vue)) etat.vue = dispo[0].id;
  rendreCoque();
}
function allerA(id) { etat.vue = id; rendreCoque(); }

const ROLES = { medecin: "Médecin", accueil: "Accueil", dpo: "Délégué à la protection des données" };
function rendreCoque() {
  const u = etat.session.utilisateur;
  const nav = h("nav", { "aria-label": "Sections" },
    VUES.filter((v) => peut(v.portee)).map((v) =>
      h("button", { type: "button", "aria-current": etat.vue === v.id ? "page" : null, onclick: () => allerA(v.id) }, v.titre)));
  const contenu = h("main", { class: "principal", id: "contenu" });
  vider(racine);
  racine.append(h("div", { class: "coque" },
    h("aside", { class: "rail" },
      h("div", null, h("div", { class: "rail-nom" }, etat.config.etablissement),
                     h("div", { class: "rail-sous" }, "Dossiers partagés avec " + etat.config.autre_etablissement)),
      nav,
      h("div", { class: "rail-bas" },
        h("div", null, h("b", null, u.nom || u.login), h("br"), ROLES[u.role] || u.role),
        h("button", { class: "lien", type: "button", onclick: () => ecranChangementMdp(false) }, "Changer le mot de passe"),
        h("button", { class: "lien", type: "button", onclick: seDeconnecter }, "Se déconnecter"))),
    contenu));
  const titre = VUES.find((v) => v.id === etat.vue).titre;
  document.title = titre + " · " + etat.config.etablissement;
  if (etat.vue === "patients") vuePatients(contenu);
  else if (etat.vue === "envois") vueEnvois(contenu);
  else if (etat.vue === "droit") vueDroit(contenu);
  else vueJournal(contenu);
}

// ------------------------------------------------------------------ patients
let minuterieRecherche = null;
function vuePatients(contenu) {
  const liste = h("ul", { "aria-label": "Résultats" });
  const compteur = h("p", { class: "vide", role: "status" });
  const champ = h("input", { type: "search", id: "q", value: pv.q, autocomplete: "off",
    placeholder: "Nom, prénom, CIN ou identifiant", "aria-label": "Rechercher un patient",
    oninput: () => { pv.q = champ.value; clearTimeout(minuterieRecherche); minuterieRecherche = setTimeout(chercher, 250); } });
  const fiche = h("section", { id: "fiche", "aria-live": "polite" });
  contenu.append(h("h1", null, "Patients"),
    h("div", { class: "deux" },
      h("section", { class: "liste" }, h("div", { class: "liste-tete" }, champ), compteur, liste),
      fiche));
  pv.refListe = liste; pv.refCompteur = compteur; pv.refFiche = fiche;
  chercher();
  rendreFiche();
}
async function chercher() {
  try {
    const r = await api("/api/ui/patients?q=" + encodeURIComponent(pv.q));
    pv.resultats = r.resultats;
  } catch (e) { annoncer(e.message, true); pv.resultats = []; }
  rendreListe();
}
function rendreListe() {
  if (!pv.refListe) return;
  vider(pv.refListe);
  pv.refCompteur.textContent = !pv.resultats.length ? "Aucun patient ne correspond à cette recherche."
    : pv.resultats.length >= 50 ? "Les 50 premiers résultats. Précisez la recherche pour en voir d'autres." : "";
  pv.refCompteur.hidden = !pv.refCompteur.textContent;
  for (const p of pv.resultats) {
    pv.refListe.append(h("li", null, h("button", { type: "button", "aria-current": pv.selection && pv.selection.id === p.id ? "true" : null,
        onclick: () => choisir(p) },
      h("span", { class: "nom" }, nomComplet(p)),
      h("span", { class: "meta" }, [p.id, p.cin, p.date_naissance ? "né(e) le " + jour(p.date_naissance) : ""].filter(Boolean).join("  ·  ")))));
  }
}
async function choisir(resume) {
  pv.selection = resume; pv.dossier = null; pv.consentement = null; pv.droit = null; pv.envoi = null;
  pv.onglet = peut("export") ? "dossier" : (peut("consentement.lire") ? "consentement" : "droit");
  pv.chargement = true;
  rendreListe(); rendreFiche();
  const id = encodeURIComponent(resume.id);
  const [d, c] = await Promise.allSettled([
    peut("export") ? api("/api/ui/dossier/" + id) : Promise.resolve(null),
    peut("consentement.lire") ? api("/api/patients/" + id + "/consentement") : Promise.resolve(null)]);
  if (!pv.selection || pv.selection.id !== resume.id) return;       // une autre selection a pris le relais
  pv.dossier = d.status === "fulfilled" ? d.value : null;
  pv.consentement = c.status === "fulfilled" ? c.value : null;
  if (d.status === "rejected") annoncer(d.reason.message, true);
  pv.chargement = false;
  rendreFiche();
}
async function rechargerConsentement() {
  try { pv.consentement = await api("/api/patients/" + encodeURIComponent(pv.selection.id) + "/consentement"); }
  catch (e) { annoncer(e.message, true); }
  rendreFiche();
}

function bandeauConsentement() {
  const c = pv.consentement;
  const autre = etat.config.autre_etablissement;
  if (!c) return h("div", { class: "bandeau", "data-etat": "inconnu" },
    h("div", null, h("strong", null, "Consentement non vérifié"),
      h("span", null, peut("consentement.lire") ? "L'état du consentement n'a pas pu être lu." : "Votre rôle ne lit pas le consentement.")));
  const a = c.actuel || {};
  const periodeTexte = "Valable " + periode(a) + ". ";
  const dest = a.destinataires && a.destinataires.length ? "Réservé à : " + a.destinataires.join(", ") + ". " : "";
  const bloque = !c.partage_autorise;
  const peutEnvoyer = peut("export");
  const bouton = peutEnvoyer ? h("button", { class: "btn", type: "button", id: "btn-envoi", disabled: bloque || pv.envoiEnCours,
      onclick: envoyerDossier }, "Envoyer à " + autre) : null;
  return h("div", { class: "bandeau", "data-etat": bloque ? "bloque" : "ok" },
    h("div", null,
      h("strong", null, bloque ? "Partage bloqué" : "Partage autorisé"),
      h("span", null, (bloque ? c.motif : periodeTexte + dest + (c.motif || "")) )),
    bouton);
}
const TEXTES_ENVOI = {
  envoye: (r) => "Dossier envoyé. " + etat.config.autre_etablissement + " a confirmé la réception (HTTP " + r.http + ").",
  en_attente: (r) => etat.config.autre_etablissement + " ne répond pas pour l'instant. L'envoi est en file d'attente et sera retenté. " + (r.detail || ""),
  bloque: (r) => "Envoi bloqué : " + r.detail,
  refuse_simulation: (r) => etat.config.autre_etablissement + " refuse ce dossier : " + r.detail,
  export_impossible: (r) => "Le dossier n'a pas pu être préparé : " + r.detail,
  echec: (r) => "L'envoi a échoué : " + r.detail,
  annule: (r) => "Envoi annulé : " + r.detail,
};
async function envoyerDossier() {
  pv.envoiEnCours = true; rendreFiche();
  try {
    pv.envoi = await api("/api/ui/envoi/" + encodeURIComponent(pv.selection.id), { methode: "POST" });
  } catch (e) { pv.envoi = { statut: "echec", detail: e.message }; }
  pv.envoiEnCours = false;
  await rechargerConsentement();
}

function rendreFiche() {
  const zone = pv.refFiche;
  if (!zone) return;
  vider(zone);
  if (!pv.selection) {
    zone.append(h("div", { class: "fiche" }, h("p", { class: "vide" }, "Choisissez un patient dans la liste pour ouvrir son dossier.")));
    return;
  }
  const p = pv.dossier ? pv.dossier.patient : pv.selection;
  const onglets = [];
  if (peut("export")) onglets.push(["dossier", "Dossier"]);
  if (peut("consentement.lire")) onglets.push(["consentement", "Consentement"]);
  if (peut("droit_acces")) onglets.push(["droit", "Droit d'accès"]);
  const barre = h("div", { class: "onglets", role: "tablist" }, onglets.map(([id, titre]) =>
    h("button", { type: "button", role: "tab", "aria-selected": pv.onglet === id ? "true" : "false",
      onclick: () => { pv.onglet = id; rendreFiche(); if (id === "droit" && !pv.droit) chargerDroit(); } }, titre)));
  const volet = h("div", { class: "volet", role: "tabpanel" });
  if (pv.chargement) volet.append(h("p", { class: "vide" }, "Chargement du dossier…"));
  else if (pv.onglet === "dossier") voletDossier(volet);
  else if (pv.onglet === "consentement") voletConsentement(volet);
  else voletDroit(volet);
  zone.append(h("div", { class: "fiche" },
    h("div", { class: "fiche-tete" },
      h("h2", null, nomComplet(p)),
      h("div", { class: "fiche-id" },
        h("span", null, "Identifiant ", h("b", null, p.id)),
        p.cin ? h("span", null, "CIN ", h("b", null, p.cin)) : null,
        p.date_naissance ? h("span", null, "Né(e) le ", h("b", null, jour(p.date_naissance))) : null,
        p.sexe ? h("span", null, "Sexe ", h("b", null, p.sexe)) : null,
        p.groupe_sanguin ? h("span", null, "Groupe ", h("b", null, p.groupe_sanguin)) : null)),
    bandeauConsentement(),
    pv.envoi ? h("div", { class: "resultat-envoi", "data-etat": pv.envoi.statut, role: "status" },
      (TEXTES_ENVOI[pv.envoi.statut] || ((r) => r.statut + " : " + r.detail))(pv.envoi)) : null,
    onglets.length ? barre : null, volet));
}

function voletDossier(volet) {
  const d = pv.dossier;
  if (!d) { volet.append(h("p", { class: "vide" }, "Le dossier n'a pas pu être chargé.")); return; }
  const p = d.patient;
  volet.append(h("section", null, h("h3", null, "Identité"),
    h("dl", { class: "paires" },
      p.telephone ? [h("dt", null, "Téléphone"), h("dd", null, p.telephone)] : null,
      p.adresse ? [h("dt", null, "Adresse"), h("dd", null, p.adresse)] : null)));
  volet.append(h("section", null, h("h3", null, "Allergies"),
    d.allergies.length ? h("ul", { class: "puces" }, d.allergies.map((a) => h("li", null, a.libelle,
        a.gravite ? h("span", { class: "etiquette " + (a.gravite === "ELEVEE" ? "refus" : "") }, a.gravite === "ELEVEE" ? "Élevée" : a.gravite === "FAIBLE" ? "Faible" : a.gravite) : null,
        a.detail ? h("div", { class: "meta" }, a.detail) : null)))
      : h("p", { class: "vide" }, "Aucune allergie connue.")));
  volet.append(h("section", null, h("h3", null, "Séjours et consultations"),
    d.sejours.length ? d.sejours.map((s) => carteSejour(s)) : h("p", { class: "vide" }, "Aucun séjour enregistré.")));
  const recus = Object.entries(d.recu_de_l_autre_hopital || {});
  if (recus.length) volet.append(h("section", null, h("h3", null, "Reçu de " + etat.config.autre_etablissement),
    recus.map(([table, lignes]) => tableauGenerique(table.replace(/_/g, " "), lignes))));
}
function carteSejour(s) {
  const lignes = [];
  if (s.diagnostics.length) lignes.push(h("div", null, h("b", null, "Diagnostics"),
    h("ul", { class: "puces" }, s.diagnostics.map((x) => h("li", null, x.libelle, x.code ? h("span", { class: "etiquette" }, x.code) : null)))));
  if (s.mesures.length) lignes.push(h("div", null, h("b", null, "Mesures"),
    h("div", { class: "tableau" }, h("table", null,
      h("thead", null, h("tr", null, h("th", null, "Mesure"), h("th", { class: "num" }, "Valeur"), h("th", null, "Date"))),
      h("tbody", null, s.mesures.map((m) => h("tr", null, h("td", null, m.libelle), h("td", { class: "num" }, [m.valeur, m.unite].filter((v) => v !== null && v !== undefined).join(" ")), h("td", null, date(m.date)))))))));
  if ((s.examens || []).length) lignes.push(h("div", null, h("b", null, "Examens et comptes rendus"),
    h("ul", { class: "puces" }, s.examens.map((x) => h("li", null, x.libelle, x.detail ? h("div", { class: "meta" }, x.detail) : null)))));
  if (!lignes.length) lignes.push(h("p", { class: "vide" }, "Rien d'autre n'est enregistré pour ce séjour."));
  return h("details", { class: "sejour" },
    h("summary", null, date(s.debut), s.type ? h("span", { class: "etiquette" }, s.type) : null,
      h("span", null, [s.service, s.medecin].filter(Boolean).join(" – ")),
      s.origine ? h("span", { class: "etiquette alerte" }, "reçu de " + s.origine) : null),
    h("div", null, s.motif ? h("p", null, s.motif) : null, lignes));
}
function tableauGenerique(titre, lignes) {
  const colonnes = Object.keys(lignes[0]).filter((c) => c !== "ipp");
  return h("div", null, h("b", null, titre),
    h("div", { class: "tableau" }, h("table", null,
      h("thead", null, h("tr", null, colonnes.map((c) => h("th", null, c.replace(/_/g, " "))))),
      h("tbody", null, lignes.map((l) => h("tr", null, colonnes.map((c) => h("td", null, l[c] === null || l[c] === undefined ? "" : l[c]))))))));
}

// ---- consentement
const STATUTS = { actif: ["Actif", "ok"], refuse: ["Refusé", "refus"], retire: ["Retiré", "alerte"] };
function etiquetteStatut(s) {
  const [texte, classe] = STATUTS[String(s).toLowerCase()] || [s, ""];
  return h("span", { class: "etiquette " + classe }, texte);
}
function voletConsentement(volet) {
  const c = pv.consentement;
  if (!c) { volet.append(h("p", { class: "vide" }, "L'état du consentement n'a pas pu être lu.")); return; }
  const a = c.actuel;
  volet.append(h("section", null, h("h3", null, "Consentement en vigueur"),
    a ? h("dl", { class: "paires" },
      h("dt", null, "Statut"), h("dd", null, etiquetteStatut(a.statut)),
      h("dt", null, "Période"), h("dd", null, periode(a)),
      h("dt", null, "Destinataires"), h("dd", null, a.destinataires && a.destinataires.length ? a.destinataires.join(", ") : "Tous les établissements partenaires"),
      h("dt", null, "Catégories exclues"), h("dd", null, a.categories_exclues && a.categories_exclues.length ? a.categories_exclues.join(", ") : "Aucune"),
      h("dt", null, "Recueilli par"), h("dd", null, a.recueilli_par || "non renseigné"),
      a.date_retrait ? [h("dt", null, "Retiré le"), h("dd", null, jour(a.date_retrait) + (a.motif_retrait ? " : " + a.motif_retrait : ""))] : null)
      : h("p", { class: "vide" }, "Aucun consentement n'a été recueilli : le partage est interdit.")));
  if (peut("consentement.gerer")) volet.append(formulaireConsentement(a));
  const histo = c.historique || [];
  volet.append(h("section", null, h("h3", null, "Historique"),
    histo.length ? h("ul", { class: "puces histo" }, histo.map((v) => h("li", null, etiquetteStatut(v.statut),
        " ", jour(v.date_recueil || v.debut), v.recueilli_par ? " · " + v.recueilli_par : "",
        v.motif_retrait ? h("div", { class: "meta" }, v.motif_retrait) : null)))
      : h("p", { class: "vide" }, "Aucune version enregistrée.")));
}
function formulaireConsentement(actuel) {
  const u = etat.session.utilisateur;
  const statut = h("select", { id: "c-statut" }, h("option", { value: "actif" }, "Le patient accepte le partage"), h("option", { value: "refuse" }, "Le patient refuse le partage"));
  const par = h("input", { type: "text", id: "c-par", value: u.nom || u.login, required: true });
  const debut = h("input", { type: "date", id: "c-debut" });
  const fin = h("input", { type: "date", id: "c-fin" });
  const limite = h("input", { type: "checkbox", id: "c-dest" });
  const imagerie = h("input", { type: "checkbox", id: "c-img" });
  const erreur = h("p", { class: "erreur-form", role: "alert" });
  const dialogue = dialogueRetrait();
  const actif = actuel && String(actuel.statut).toLowerCase() === "actif";
  return h("section", null, h("h3", null, "Enregistrer une décision"),
    h("form", { class: "formulaire", novalidate: true, onsubmit: async (ev) => {
        ev.preventDefault(); erreur.textContent = "";
        const corps = { statut: statut.value, recueilli_par: par.value.trim() };
        if (debut.value) corps.debut = debut.value;
        if (fin.value) corps.fin = fin.value;
        if (limite.checked) corps.destinataires = [etat.config.autre];
        if (imagerie.checked) corps.categories_exclues = ["imagerie"];
        try {
          await api("/api/patients/" + encodeURIComponent(pv.selection.id) + "/consentement", { methode: "POST", corps });
          annoncer("Consentement enregistré.");
          await rechargerConsentement();
        } catch (e) { erreur.textContent = e.message; }
      } },
      h("label", null, "Décision du patient", statut),
      h("label", null, "Recueilli par", par),
      h("div", { class: "deux-champs" }, h("label", null, "Début", debut), h("label", null, "Fin", fin)),
      h("label", { class: "case" }, limite, "Limiter le partage à " + etat.config.autre_etablissement),
      h("label", { class: "case" }, imagerie, "Exclure l'imagerie"),
      erreur,
      h("div", { class: "barre" },
        h("button", { class: "btn", type: "submit" }, "Enregistrer le consentement"),
        h("button", { class: "btn danger", type: "button", disabled: !actif, onclick: () => dialogue.showModal() }, "Retirer le consentement"))),
    dialogue);
}
function dialogueRetrait() {
  const u = etat.session.utilisateur;
  const motif = h("textarea", { id: "r-motif", placeholder: "Motif indiqué par le patient (facultatif)" });
  const erreur = h("p", { class: "erreur-form", role: "alert" });
  const d = h("dialog", { "aria-labelledby": "r-titre" },
    h("form", { method: "dialog", onsubmit: async (ev) => {
        if (ev.submitter && ev.submitter.value !== "oui") return;
        ev.preventDefault(); erreur.textContent = "";
        try {
          await api("/api/patients/" + encodeURIComponent(pv.selection.id) + "/consentement/retrait",
            { methode: "POST", corps: { recueilli_par: u.nom || u.login, motif: motif.value.trim() } });
          d.close(); annoncer("Consentement retiré. Les envois en attente seront annulés.");
          await rechargerConsentement();
        } catch (e) { erreur.textContent = e.message; }
      } },
      h("h3", { id: "r-titre" }, "Retirer le consentement ?"),
      h("p", null, "Plus aucun dossier ne sera envoyé à " + etat.config.autre_etablissement + ". Les envois en attente seront annulés."),
      h("label", null, "Motif", motif), erreur,
      h("div", { class: "actions" },
        h("button", { class: "btn secondaire", value: "non", formmethod: "dialog" }, "Garder le consentement"),
        h("button", { class: "btn danger", value: "oui" }, "Retirer le consentement"))));
  return d;
}

// ---- droit d'acces
async function chargerDroit() {
  try { pv.droit = await api("/api/patients/" + encodeURIComponent(pv.selection.id) + "/droit-acces"); }
  catch (e) { annoncer(e.message, true); }
  rendreFiche();
}
function voletDroit(volet) {
  if (!pv.droit) {
    volet.append(h("p", { class: "vide" }, "Cette communication rassemble tout ce que l'établissement détient sur la personne. Chaque demande est tracée."),
      h("div", null, h("button", { class: "btn", type: "button", onclick: chargerDroit }, "Établir la communication")));
    return;
  }
  const r = pv.droit;
  const blob = () => new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
  volet.append(
    h("section", null, h("h3", null, r.objet || "Droit d'accès"),
      h("dl", { class: "paires" },
        h("dt", null, "Établi le"), h("dd", null, date(r.etabli_le)),
        h("dt", null, "Responsable"), h("dd", null, r.responsable_du_traitement ? r.responsable_du_traitement.etablissement : ""),
        h("dt", null, "Destinataires"), h("dd", null, (r.destinataires || []).length ? r.destinataires.map((x) => x.etablissement || x.code || JSON.stringify(x)).join(", ") : "Aucun envoi"),
        h("dt", null, "Origine des données"), h("dd", null, (r.origine_des_donnees || []).length ? r.origine_des_donnees.map((x) => (x.etablissement || x.code) + " (" + x.elements + ")").join(", ") : "Établissement seul"))),
    h("section", null, h("h3", null, "Historique des accès"),
      (r.historique_des_acces || []).length ? h("div", { class: "tableau" }, h("table", null,
        h("thead", null, h("tr", null, h("th", null, "Date"), h("th", null, "Événement"), h("th", null, "Par"), h("th", null, "Résultat"))),
        h("tbody", null, r.historique_des_acces.map((a) => h("tr", null, h("td", null, date(a.date)), h("td", null, a.evenement || a.action), h("td", null, a.par || ""), h("td", null, a.resultat || ""))))))
        : h("p", { class: "vide" }, "Aucun accès enregistré.")),
    h("div", null, h("button", { class: "btn secondaire", type: "button", onclick: () => {
        const a = h("a", { href: URL.createObjectURL(blob()), download: "droit-acces-" + pv.selection.id + ".json" });
        document.body.append(a); a.click(); a.remove();
      } }, "Télécharger la communication (JSON)")));
}

// ------------------------------------------------------------------ droit d'acces (DPO)
function vueDroit(contenu) {
  const zone = h("div", { "aria-live": "polite" });
  const champ = h("input", { type: "text", id: "id-droit", autocomplete: "off", required: true,
                             placeholder: etat.config.service === "H1" ? "Par exemple P1-0106" : "Par exemple P2-0051" });
  const erreur = h("p", { class: "erreur-form", role: "alert" });
  contenu.append(h("h1", null, "Droit d'accès"),
    h("form", { class: "formulaire", novalidate: true, onsubmit: async (ev) => {
        ev.preventDefault(); erreur.textContent = ""; vider(zone);
        const id = champ.value.trim();
        if (!id) { erreur.textContent = "Saisissez l'identifiant du patient."; return; }
        try {
          pv.droit = await api("/api/patients/" + encodeURIComponent(id) + "/droit-acces");
          pv.selection = { id };
          zone.append(h("div", { class: "fiche" }, (() => { const v = h("div", { class: "volet" }); voletDroit(v); return v; })()));
        } catch (e) { erreur.textContent = e.code === 404 ? "Aucun patient avec cet identifiant." : e.message; }
      } },
      h("p", null, "Établit la communication de toutes les données détenues sur une personne (loi 09-08, art. 7). Chaque demande est tracée."),
      h("label", null, "Identifiant du patient", champ), erreur,
      h("div", { class: "barre" }, h("button", { class: "btn", type: "submit" }, "Établir la communication"))),
    zone);
}

// ------------------------------------------------------------------ envois
const STATUTS_ENVOI = { envoye: ["Envoyé", "ok"], en_attente: ["En attente", "alerte"], echec: ["Échec", "refus"], annule: ["Annulé", "refus"] };
let minuterieEnvois = null;
function vueEnvois(contenu) {
  const corps = h("div");
  const relancer = h("button", { class: "btn", type: "button", onclick: async () => {
      relancer.disabled = true;
      try {
        const r = await api("/api/ui/envois/reprendre?forcer=true", { methode: "POST" });
        annoncer(r.resultats.length ? r.resultats.length + " envoi(s) relancé(s)." : "Aucun envoi en attente.");
      } catch (e) { annoncer(e.message, true); }
      relancer.disabled = false; charger();
    } }, "Relancer les envois en attente");
  contenu.append(h("h1", null, "Envois vers " + etat.config.autre_etablissement),
    h("div", { class: "barre" }, relancer, h("button", { class: "btn secondaire", type: "button", onclick: () => charger() }, "Actualiser"),
      h("span", { class: "meta espace" }, "La liste se met à jour toutes les 10 secondes.")), corps);
  async function charger() {
    try {
      const r = await api("/api/ui/envois");
      vider(corps);
      if (!r.envois.length) { corps.append(h("p", { class: "vide" }, "Aucun envoi pour l'instant. Ouvrez un dossier et choisissez Envoyer à " + etat.config.autre_etablissement + ".")); return; }
      corps.append(h("div", { class: "tableau" }, h("table", null,
        h("thead", null, h("tr", null, h("th", null, "Patient"), h("th", null, "État"), h("th", { class: "num" }, "Tentatives"), h("th", null, "Dernière mise à jour"), h("th", null, "Détail"))),
        h("tbody", null, r.envois.map((e) => {
          const [texte, classe] = STATUTS_ENVOI[e.statut] || [e.statut, ""];
          const maj = e.maj_le ? new Date(e.maj_le * 1000).toISOString() : "";
          const suite = e.statut === "en_attente" && e.prochaine ? "Prochaine tentative " + date(new Date(e.prochaine * 1000).toISOString()) : "";
          return h("tr", null, h("td", null, e.patient_id), h("td", null, h("span", { class: "etiquette " + classe }, texte)),
            h("td", { class: "num" }, e.tentatives), h("td", null, date(maj)),
            h("td", null, [e.derniere_erreur, suite].filter(Boolean).join(" · "), h("div", { class: "mono" }, e.echange_id)));
        })))));
    } catch (e) { vider(corps); corps.append(h("p", { class: "erreur-form" }, e.message)); }
  }
  charger();
  clearInterval(minuterieEnvois);
  minuterieEnvois = setInterval(() => { if (etat.vue === "envois" && etat.session) charger(); else clearInterval(minuterieEnvois); }, 10000);
}

// ------------------------------------------------------------------ journal
function vueJournal(contenu) {
  const corps = h("div");
  let seulementRefus = false;
  let derniere = null;
  const filtre = h("input", { type: "checkbox", id: "refus", onchange: () => { seulementRefus = filtre.checked; afficher(); } });
  contenu.append(h("h1", null, "Journal d'accès"),
    h("div", { class: "barre" }, h("label", { class: "case" }, filtre, "Afficher seulement les refus"),
      h("button", { class: "btn secondaire", type: "button", onclick: () => charger() }, "Actualiser")), corps);
  function qui(e) {
    if (e.client) return e.client.replace(/^utilisateur:/, "");
    if (e.evenement === "demarrage") return "service";
    return e.chemin && e.chemin.startsWith("/ui") ? "navigateur (page)" : "sans jeton";
  }
  function afficher() {
    if (!derniere) return;
    vider(corps);
    const c = derniere.chaine;
    corps.append(h("p", { class: "chaine " + (c.intact ? "ok" : "refus"), role: "status" },
      c.absent ? "Aucun journal pour l'instant." : c.intact ? "Chaînage intact : " + c.lignes + " lignes vérifiées, aucune n'a été modifiée."
        : "Chaînage rompu à la ligne " + c.premiere_rupture + " : le journal a été modifié."));
    const lignes = derniere.evenements.filter((e) => !seulementRefus || e.resultat === "refus");
    corps.append(h("div", { class: "barre" }));
    corps.append(h("div", { class: "tableau" }, h("table", null,
      h("thead", null, h("tr", null, h("th", null, "Heure"), h("th", null, "Qui"), h("th", null, "Action"), h("th", { class: "num" }, "Code"), h("th", null, "Résultat"))),
      h("tbody", null, lignes.map((e) => h("tr", null,
        h("td", null, date(e.horodatage)),
        h("td", null, qui(e)),
        h("td", null, e.evenement === "acces" ? [e.methode, " ", h("span", { class: "mono" }, e.chemin)] : e.evenement),
        h("td", { class: "num" }, e.http || ""),
        h("td", null, h("span", { class: "etiquette " + (e.resultat === "refus" ? "refus" : e.resultat === "succes" ? "ok" : "") }, e.resultat === "refus" ? "Refusé" : e.resultat === "succes" ? "Réussi" : (e.resultat || "")),
          e.motif ? h("div", { class: "meta" }, e.motif) : null)))))));
  }
  async function charger() {
    try { derniere = await api("/api/ui/journal?limite=200"); afficher(); }
    catch (e) { vider(corps); corps.append(h("p", { class: "erreur-form" }, e.message)); }
  }
  charger();
}

// ------------------------------------------------------------------ demarrage
(async function () {
  try {
    etat.config = await (await fetch("/ui/config.json", { cache: "no-store" })).json();
  } catch (e) {
    racine.append(h("main", { class: "principal" }, h("h1", null, "Service injoignable"),
      h("p", null, "Impossible de charger la configuration. Vérifiez que l'API est démarrée.")));
    return;
  }
  document.documentElement.dataset.service = etat.config.service;
  ecranConnexion();
})();
