"use strict";
/* Page de demonstration : liste des patients, envoyes, recus ; consentement oui/non ; envoi ; contenu du Bundle.
   Aucun jeton dans le navigateur, aucun stockage. Tout contenu venu de l'API est insere comme du TEXTE. */

let empreinte = "";                       // signature des dernières données affichées
const racine = document.getElementById("app");
const e = { donnees: null, onglet: "patients", filtre: "", choix: null, detail: null, detailEnCours: false,
            resultat: null, occupe: false, erreur: "", info: "" };
const ICONE = { ok: "✓", echec: "✕", attente: "…", saute: "–" };
const STATUT_ENVOI = { envoye: "Envoyé", en_attente: "En attente", echec: "Échec", annule: "Annulé" };

function h(balise, props, ...enfants) {
  const el = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(props || {})) {
    if (valeur === null || valeur === undefined || valeur === false) continue;
    if (cle.startsWith("on")) el.addEventListener(cle.slice(2), valeur);
    else if (cle === "class") el.className = valeur;
    else el.setAttribute(cle, valeur === true ? "" : valeur);
  }
  for (const f of enfants.flat(Infinity)) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return el;
}

async function appel(methode, chemin) {
  const rep = await fetch(chemin, { method: methode, headers: { Accept: "application/json" }, cache: "no-store" });
  let corps = {};
  try { corps = await rep.json(); } catch (_) { /* corps vide */ }
  if (!rep.ok) {
    throw new Error(rep.status === 404 && !corps.erreur ? "La démonstration est désactivée. Ajoutez DEMO=1 dans l'environnement de l'API."
      : rep.status === 403 && !corps.erreur ? "La démonstration n'est accessible que depuis ce poste."
      : corps.erreur || ("Erreur " + rep.status));
  }
  return corps;
}

// ------------------------------------------------------------------ données
const patient = () => (e.donnees ? e.donnees.patients.find((p) => p.id === e.choix) : null);
const parId = (id) => (e.donnees ? e.donnees.patients.find((p) => p.id === id) : null);
const nom = (p) => (p ? [p.prenom, (p.nom || "").toUpperCase()].filter(Boolean).join(" ") || p.id : "");
const ouiNon = (p) => {
  const s = p && p.consentement ? p.consentement.statut : "aucun";
  return s === "actif" ? "oui" : s === "aucun" ? "?" : "non";
};
const LIBELLE_OUI_NON = { oui: "Oui", non: "Non", "?": "Non renseigné" };
const jour = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || "")); return m ? `${m[3]}/${m[2]}/${m[1]}` : (s || ""); };
const quand = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(String(s || "")); return m ? `${m[3]}/${m[2]} ${m[4]}` : jour(s); };

async function charger() {
  try { e.donnees = await appel("GET", "/api/demo/patients"); e.erreur = ""; empreinte = JSON.stringify(e.donnees); }
  catch (x) { e.erreur = x.message; }
  dessiner();
}

// Rafraîchissement automatique des listes (toutes les 5 s) : un dossier reçu de l'autre hôpital
// apparaît sans recharger la page. On ne redessine que si quelque chose a changé, et jamais
// pendant une action de l'utilisateur ou quand l'onglet du navigateur est caché.
const PERIODE_MS = 5000;
async function actualiser() {
  if (document.hidden || e.occupe || !e.donnees) return;
  try {
    const frais = await appel("GET", "/api/demo/patients");
    if (e.occupe) return;                                   // une action a démarré pendant la requête
    const signature = JSON.stringify(frais);
    if (signature === empreinte) return;
    empreinte = signature;
    e.donnees = frais; e.erreur = "";
    dessiner();
  } catch (_) { /* une coupure passagère ne doit pas effacer l'écran : on réessaie au prochain tour */ }
}
setInterval(actualiser, PERIODE_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) actualiser(); });

async function chargerDetail(id) {
  e.detail = null; e.detailEnCours = true; dessiner();
  try {
    const d = await appel("GET", `/api/demo/patient/${encodeURIComponent(id)}`);
    if (e.choix === id) e.detail = d;
  } catch (x) { if (e.choix === id) e.detail = { erreur: x.message }; }
  if (e.choix === id) { e.detailEnCours = false; dessiner(); }
}

function choisir(id) {
  e.choix = id; e.resultat = null; e.info = ""; e.erreur = "";
  chargerDetail(id);
}

async function regler(statut) {
  const p = patient(); if (!p || e.occupe) return;
  e.occupe = true; e.erreur = ""; e.resultat = null; dessiner();
  try {
    const r = await appel("POST", `/api/demo/consentement/${encodeURIComponent(p.id)}/${statut}`);
    p.consentement = r.consentement;
  } catch (x) { e.erreur = x.message; }
  e.occupe = false; dessiner();
  chargerDetail(p.id);                         // le Bundle n'existe qu'avec un consentement « oui »
}

async function envoyer() {
  const p = patient(); if (!p || e.occupe) return;
  e.occupe = true; e.erreur = ""; e.resultat = null; dessiner();
  try {
    e.resultat = await appel("POST", `/api/demo/envoi/${encodeURIComponent(p.id)}`);
    p.consentement = e.resultat.consentement;
    e.donnees.en_attente = e.resultat.en_attente;
    e.donnees.envoyes = e.resultat.envoyes;
  } catch (x) { e.erreur = x.message; }
  e.occupe = false; dessiner();
}

async function reprendre() {
  if (e.occupe) return;
  e.occupe = true; e.erreur = ""; e.info = ""; dessiner();
  try {
    const r = await appel("POST", "/api/demo/reprendre");
    e.info = r.resultats.length ? r.resultats.map((x) => `${x.patient || "?"} : ${x.statut}`).join(" · ") : "Aucun envoi en attente.";
    e.donnees.en_attente = r.en_attente; e.donnees.envoyes = r.envoyes;
  } catch (x) { e.erreur = x.message; }
  e.occupe = false; dessiner();
}

// ------------------------------------------------------------------ colonne de gauche
function onglets() {
  const d = e.donnees;
  const t = [["patients", `Patients (${d.patients.length})`], ["envoyes", `Envoyés (${d.envoyes.length})`], ["recus", `Reçus (${d.recus.length})`]];
  return h("div", { class: "onglets", role: "tablist" }, t.map(([cle, texte]) =>
    h("button", { type: "button", role: "tab", "aria-selected": String(e.onglet === cle),
                  onclick: () => { e.onglet = cle; dessiner(); } }, texte)));
}

function ligne(id, titre, sous, puce) {
  return h("li", {}, h("button", { class: "demo-patient", type: "button", "aria-pressed": String(id === e.choix), onclick: () => choisir(id) },
    h("span", {}, titre, h("small", {}, sous)), puce));
}

function colonne() {
  const d = e.donnees;
  const f = e.filtre.trim().toLowerCase();
  // Même filtre sur les trois listes : par nom, prénom ou identifiant.
  const correspond = (id, p) => !f || ((p ? nom(p) : "") + " " + (id || "")).toLowerCase().includes(f);
  const corps = [h("div", { class: "demo-recherche" }, h("input", { type: "search", placeholder: "Chercher par nom ou par identifiant",
    "aria-label": "Chercher par nom ou par identifiant", value: e.filtre,
    oninput: (ev) => { e.filtre = ev.target.value; const pos = ev.target.selectionStart; dessiner(); const c = document.querySelector(".demo-recherche input"); c.focus(); c.setSelectionRange(pos, pos); } }))];
  const aucun = (vide) => h("div", { class: "demo-vide petit" }, f ? "Aucun résultat pour cette recherche." : vide);
  if (e.onglet === "patients") {
    const liste = d.patients.filter((p) => correspond(p.id, p));
    corps.push(liste.length ? h("ul", { class: "demo-liste" }, liste.map((p) =>
      ligne(p.id, nom(p), p.id, h("span", { class: "puce " + (ouiNon(p) === "oui" ? "actif" : ouiNon(p) === "non" ? "refuse" : "aucun") }, LIBELLE_OUI_NON[ouiNon(p)]))))
      : aucun("Aucun patient."));
  } else if (e.onglet === "envoyes") {
    const liste = d.envoyes.filter((x) => correspond(x.patient, parId(x.patient)));
    corps.push(liste.length ? h("ul", { class: "demo-liste" }, liste.map((x) =>
      ligne(x.patient, nom(parId(x.patient)) || x.patient, `${x.patient} · ${quand(x.quand)} → ${d.autre_etablissement}`,
        h("span", { class: "puce " + x.statut }, STATUT_ENVOI[x.statut] || x.statut))))
      : aucun(`Aucun envoi pour l'instant. Choisissez un patient et envoyez son dossier à ${d.autre_etablissement}.`));
  } else {
    const liste = d.recus.filter((x) => correspond(x.patient, parId(x.patient)));
    corps.push(liste.length ? h("ul", { class: "demo-liste" }, liste.map((x) =>
      ligne(x.patient, nom(parId(x.patient)) || x.patient, `${x.patient} · reçu le ${quand(x.quand)} de ${d.autre_etablissement}`,
        h("span", { class: "puce envoye" }, "Reçu"))))
      : aucun(`Aucun dossier reçu de ${d.autre_etablissement} pour l'instant.`));
  }
  return h("section", { class: "demo-carte", "aria-label": "Listes" }, onglets(), corps);
}

// ------------------------------------------------------------------ fiche patient et Bundle
function ligneIdentite(dt, dd) { return dd ? [h("dt", {}, dt), h("dd", {}, dd)] : []; }

function infos(dos) {
  const p = dos.patient;
  const sexe = p.sexe === "M" ? "Masculin" : p.sexe === "F" ? "Féminin" : p.sexe;
  const blocs = [h("dl", { class: "identite" }, ligneIdentite("Nom", nom(p)), ligneIdentite("Sexe", sexe),
    ligneIdentite("Naissance", jour(p.date_naissance)), ligneIdentite("CIN", p.cin), ligneIdentite("Téléphone", p.telephone),
    ligneIdentite("Adresse", p.adresse), ligneIdentite("Groupe sanguin", p.groupe_sanguin))];
  blocs.push(h("div", {}, h("strong", {}, "Allergies : "), (dos.allergies || []).length
    ? dos.allergies.map((a) => [a.libelle, a.detail ? ` (${a.detail})` : "", a.gravite ? `, ${a.gravite}` : ""].join("")).join(" ; ") : "aucune"));
  for (const s of dos.sejours || []) {
    const lignes = [];
    if (s.motif) lignes.push(h("span", {}, s.motif));
    const dx = (s.diagnostics || []).map((x) => x.libelle).filter(Boolean);
    if (dx.length) lignes.push(h("span", {}, "Diagnostics : " + dx.join(", ")));
    const ms = (s.mesures || []).map((m) => `${m.libelle} ${m.valeur}${m.unite ? " " + m.unite : ""}`);
    if (ms.length) lignes.push(h("small", {}, "Mesures : " + ms.join(" · ")));
    const ex = (s.examens || []).map((x) => x.libelle).filter(Boolean);
    if (ex.length) lignes.push(h("small", {}, "Examens : " + ex.join(" · ")));
    if (s.origine) lignes.push(h("small", {}, "Reçu de " + s.origine));
    blocs.push(h("div", { class: "sejour" }, h("strong", {}, [s.type, s.service].filter(Boolean).join(" · ") || "Séjour"),
      h("small", {}, [quand(s.debut), s.fin ? "→ " + quand(s.fin) : "", s.medecin].filter(Boolean).join(" ")), lignes));
  }
  const recus = Object.entries(dos.recu_de_l_autre_hopital || {});
  if (recus.length) blocs.push(h("div", {}, h("strong", {}, "Données reçues : "), recus.map(([t, l]) => `${l.length} ${t.replace(/_/g, " ")}`).join(", ")));
  return blocs;
}

function contenuBundle(b) {
  if (!b || !b.disponible) {
    return h("p", { class: "chargement" }, "Aucun Bundle pour ce patient : " + ((b && b.motif) || "indisponible") + ".");
  }
  return [
    h("div", { class: "types" }, b.comptes.map((c) => h("span", { class: "puce" }, `${c.type} × ${c.n}`))),
    b.entrees.map((x) => h("details", { class: "entree-bundle" },
      h("summary", {}, h("b", {}, x.type), h("span", {}, x.resume || x.id || "")),
      h("pre", {}, x.json))),
  ];
}

function fiche() {
  if (e.detailEnCours && !e.detail) return h("p", { class: "chargement" }, "Chargement du dossier…");
  const d = e.detail;
  if (!d) return null;
  if (d.erreur) return h("p", { class: "demo-erreur", role: "alert" }, d.erreur);
  const b = d.bundle;
  return h("div", { class: "fiche" },
    h("details", { open: true }, h("summary", {}, "Informations du patient"), h("div", { class: "corps" }, infos(d.dossier))),
    h("details", { open: true }, h("summary", {}, b && b.disponible ? `Contenu du Bundle FHIR (${b.total} ressources)` : "Contenu du Bundle FHIR"),
      h("div", { class: "corps" }, contenuBundle(b))));
}

// ------------------------------------------------------------------ colonne de droite
function scene() {
  const p = patient();
  const autre = e.donnees.autre_etablissement;
  if (!p) return h("div", { class: "demo-vide" }, "Choisissez un patient dans l'une des listes.");
  const s = ouiNon(p);
  const choix = (valeur, texte, classe) => h("button", { class: "btn " + classe, type: "button", disabled: e.occupe,
    "aria-pressed": String(s === valeur), onclick: () => regler(valeur === "oui" ? "actif" : "refuse") }, texte);
  const sortie = [];
  if (e.resultat) {
    sortie.push(h("ol", { class: "etapes" }, e.resultat.etapes.map((x) =>
      h("li", { class: "etape " + x.etat },
        h("span", { class: "rond", "aria-hidden": "true" }, ICONE[x.etat] || "?"),
        h("div", {}, h("strong", {}, x.nom), h("span", { class: "texte" }, x.texte || (x.etat === "saute" ? "Non exécuté." : "")))))));
    sortie.push(h("div", { class: "verdict " + e.resultat.verdict.etat, role: "status" },
      h("strong", {}, e.resultat.verdict.titre), h("span", {}, e.resultat.verdict.detail)));
    const t = e.resultat.technique || {};
    sortie.push(h("p", { class: "demo-technique" }, `Détail technique : ${t.statut}` + (t.http ? ` · HTTP ${t.http}` : "")
      + (t.echange_id ? ` · échange ${t.echange_id}` : "")
      + (t.duree_ms !== undefined ? ` · durée ${(t.duree_ms / 1000).toFixed(1).replace(".", ",")} s` : "")));
  }
  return h("div", { class: "demo-scene" },
    h("div", {}, h("h2", {}, nom(p)), h("p", { class: "demo-technique" }, p.id)),
    h("div", { class: "demo-choix demo-oui-non", role: "group", "aria-label": "Consentement du patient" },
      h("span", { class: "titre" }, `Le patient accepte le partage avec ${autre} ?`),
      choix("oui", "Oui", "oui"), choix("non", "Non", "non"),
      s === "?" ? h("span", { class: "puce aucun" }, "Non renseigné") : null),
    h("div", { class: "demo-actions" },
      h("button", { class: "btn demo-envoyer", type: "button", disabled: e.occupe, onclick: envoyer },
        e.occupe ? "En cours…" : `Envoyer à ${autre}`)),
    e.erreur ? h("p", { class: "demo-erreur", role: "alert" }, e.erreur) : null,
    sortie, fiche());
}

function dessiner() {
  const d = e.donnees;
  const enfants = [];
  if (!d) {
    enfants.push(h("div", { class: "demo-vide" }, e.erreur || "Chargement…"));
  } else {
    enfants.push(h("header", { class: "demo-tete" },
      h("div", {}, h("h1", {}, d.etablissement), h("p", {}, `Échange de dossiers avec ${d.autre_etablissement}`)),
      h("div", { class: "demo-actions" },
        h("span", { class: "demo-technique" }, `${d.en_attente} envoi(s) en attente`),
        h("button", { class: "btn secondaire", type: "button", disabled: e.occupe, onclick: reprendre }, "Relancer les envois en attente"))));
    if (e.info) enfants.push(h("p", { class: "demo-tete demo-technique", role: "status" }, e.info));
    enfants.push(h("main", { class: "demo-grille" }, colonne(), h("section", { class: "demo-carte", "aria-label": "Échange" }, scene())));
  }
  const actif = document.activeElement;
  const avait = actif && actif.closest && actif.closest(".demo-recherche");
  const defilement = Array.from(document.querySelectorAll(".demo-liste, .demo-fiche")).map((x) => x.scrollTop);
  racine.replaceChildren(...enfants);
  Array.from(document.querySelectorAll(".demo-liste, .demo-fiche")).forEach((x, i) => { if (defilement[i]) x.scrollTop = defilement[i]; });
  if (avait) { const c = document.querySelector(".demo-recherche input"); if (c) c.focus(); }
}

fetch("/ui/config.json", { cache: "no-store" }).then((r) => r.json()).then((c) => {
  document.documentElement.setAttribute("data-service", c.service);
}).catch(() => {}).finally(charger);
dessiner();
