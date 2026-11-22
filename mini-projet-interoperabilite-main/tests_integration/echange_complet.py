"""Tests d'echange complets H1 <-> H2 contre les DEUX API EN MARCHE (HTTPS, jetons, consentement).

    python tests_integration/echange_complet.py                 scenarios sans risque (voir ci-dessous)
    python tests_integration/echange_complet.py --destructif    + limites : debit (429) et verrouillage apres echecs
    python tests_integration/echange_complet.py --seulement C D  ne lance que les groupes C et D

Groupes : A disponibilite/TLS . B authentification et portees . C export de Bundle . D reception de Bundle
          E erreurs de Bundle . F routes Patient . G consentement . H client d'envoi (file + reprise) . I limites

Configuration (variables d'environnement, valeurs par defaut entre crochets) :
    H1_URL [https://127.0.0.1:8000]   H2_URL [https://127.0.0.1:8002]
    SEC_CA  certificat racine de l'autorite interne [securite/certificats/ac_interop.cert.pem]
    JETON_<CLIENT>  jeton d'un client du registre, par exemple JETON_H1_CHU, ou fichier
    securite/jetons_locaux/<client>.txt. Clients : h1-chu h1-interne h1-accueil h2-clinique h2-interne h2-accueil
    H1_IPP_OK [P1-0106] H1_IPP_REFUSE [P1-0108] H1_IPP_INCONNU [P1-9999]   (cas du jeu Oracle)
    H2_ID_OK [P2-0051] H2_ID_REFUSE [P2-0054] H2_ID_INCONNU [P2-9999]       (cas du jeu MongoDB)

Un essai dont le jeton manque est ignore (SKIP), pas en echec : chaque poste n'a que ses propres jetons.
Ce que le script MODIFIE : cree des patients de test (CIN aleatoires ZT...), retire puis re-recueille le consentement
du patient nominal, et envoie des Bundles. Ne pas le lancer sur une base de production.
Sortie : tableau dans la console et rapport sortie/rapport_echange_complet.md. Code de sortie 0 = aucun echec.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from pathlib import Path

import httpx

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "hopital1"), str(RACINE / "hopital2")]

H1 = (os.getenv("H1_URL") or "https://127.0.0.1:8000").rstrip("/")
H2 = (os.getenv("H2_URL") or "https://127.0.0.1:8002").rstrip("/")
CA = os.getenv("SEC_CA") or str(RACINE / "securite" / "certificats" / "ac_interop.cert.pem")
IPP_OK, IPP_REFUSE, IPP_INCONNU = (os.getenv("H1_IPP_OK") or "P1-0106", os.getenv("H1_IPP_REFUSE") or "P1-0108",
                                   os.getenv("H1_IPP_INCONNU") or "P1-9999")
ID_OK, ID_REFUSE, ID_INCONNU = (os.getenv("H2_ID_OK") or "P2-0051", os.getenv("H2_ID_REFUSE") or "P2-0054",
                                os.getenv("H2_ID_INCONNU") or "P2-9999")
FHIR = {"Content-Type": "application/fhir+json"}
RESULTATS: list[dict] = []
GROUPE = ["?"]


class Ignore(Exception):
    """Essai impossible (jeton ou donnee manquante)."""


def jeton(client: str) -> str:
    valeur = os.getenv("JETON_" + client.upper().replace("-", "_"))
    if not valeur:
        fichier = RACINE / "securite" / "jetons_locaux" / f"{client}.txt"
        valeur = fichier.read_text(encoding="utf-8") if fichier.exists() else ""
    if not valeur.strip():
        raise Ignore(f"jeton {client} absent")
    return valeur.strip()


def appel(methode, base, chemin, client=None, *, json_=None, corps=None, entetes=None, params=None, verifier=True,
          attendre=True):
    """Une requete HTTPS. Sur 429 (limitation de debit), attend le delai annonce puis recommence, sauf attendre=False :
    une suite complete depasse SEC_DEBIT_PAR_MINUTE (120 par defaut), ce qui n'est pas ce que l'on veut mesurer."""
    for tentative in range(6):
        rep = _une_requete(methode, base, chemin, client, json_, corps, entetes, params, verifier)
        if rep.status_code != 429 or not attendre:
            return rep
        time.sleep(min(float(rep.headers.get("Retry-After") or 2), 30))
    return rep


HORODATES: list[float] = []


def calmer(max_recent: int = 30):
    """Attend que le debit des 60 dernieres secondes soit assez bas pour ne pas declencher la limitation (429)."""
    while True:
        maintenant = time.time()
        recents = [t for t in HORODATES if maintenant - t < 60]
        if len(recents) <= max_recent:
            return
        attente = 60 - (maintenant - recents[0]) + 1
        print(f"        ... {len(recents)} requetes dans la derniere minute : pause de {int(attente)} s (limitation de debit)")
        time.sleep(attente)


def _une_requete(methode, base, chemin, client, json_, corps, entetes, params, verifier):
    HORODATES.append(time.time())
    h = dict(entetes or {})
    if client:
        h["Authorization"] = "Bearer " + jeton(client)
    if corps is not None or json_ is not None:
        h.setdefault("Content-Type", "application/fhir+json")
    with httpx.Client(verify=CA if verifier else True, timeout=60.0, follow_redirects=False) as c:
        return c.request(methode, base + chemin, headers=h, params=params,
                         content=corps, json=json_ if corps is None else None)


def essai(ident, titre, attendu, fonction, condition=None):
    """Joue `fonction` (qui renvoie une Response) et compare son code a `attendu` (entier ou ensemble)."""
    attendus = {attendu} if isinstance(attendu, (int, str)) else set(attendu)
    debut, detail, statut, obtenu = time.perf_counter(), "", "OK", "-"
    try:
        rep = fonction()
        obtenu = rep.status_code if hasattr(rep, "status_code") else str(rep)
        if hasattr(rep, "status_code") and obtenu not in attendus:
            statut, detail = "ECHEC", rep.text[:160].replace("\n", " ")
        elif condition is not None and hasattr(rep, "status_code"):
            raison = condition(rep)
            if raison:
                statut, detail = "ECHEC", raison
    except Ignore as exc:
        statut, detail = "SKIP", str(exc)
    except Exception as exc:                                   # noqa: BLE001
        obtenu = type(exc).__name__
        if "exception" in attendus:
            statut = "OK"
        else:
            statut, detail = "ECHEC", f"{type(exc).__name__}: {str(exc)[:120]}"
    ms = int((time.perf_counter() - debut) * 1000)
    RESULTATS.append({"groupe": GROUPE[0], "id": ident, "titre": titre, "attendu": "/".join(map(str, sorted(attendus, key=str))),
                      "obtenu": obtenu, "statut": statut, "detail": detail, "ms": ms})
    marque = {"OK": "  OK ", "ECHEC": "ECHEC", "SKIP": " SKIP"}[statut]
    print(f"[{marque}] {ident:<4} {titre:<66} attendu {RESULTATS[-1]['attendu']:<8} obtenu {obtenu}"
          + (f"  <- {detail}" if detail else ""))


def oo(rep):
    """Condition : la reponse d'erreur est un OperationOutcome."""
    try:
        return None if rep.json().get("resourceType") == "OperationOutcome" else "pas un OperationOutcome"
    except Exception:
        return "corps non JSON"


# ───────────────────────── donnees de depart ─────────────────────────
ETAT: dict = {}


def bundle_h1() -> dict:
    if "b_h1" not in ETAT:
        r = appel("GET", H1, f"/api/patients/{IPP_OK}/bundle", "h1-interne")
        if r.status_code != 200:
            raise Ignore(f"export H1 de {IPP_OK} impossible ({r.status_code})")
        ETAT["b_h1"] = r.json()
    return copy.deepcopy(ETAT["b_h1"])


def bundle_h2() -> dict:
    if "b_h2" not in ETAT:
        r = appel("GET", H2, f"/api/patients/{ID_OK}/bundle", "h2-interne")
        if r.status_code != 200:
            raise Ignore(f"export H2 de {ID_OK} impossible ({r.status_code})")
        ETAT["b_h2"] = r.json()
    return copy.deepcopy(ETAT["b_h2"])


def avec_nouveau_cin(bundle: dict, cin: str, ipp: str | None = "auto") -> dict:
    """Meme dossier, autre CIN ET autre IPP : devient un patient entierement inconnu de l'autre hopital.
    (Garder l'IPP d'origine ferait correspondre deux dossiers a la fois : 409, voir D12.)"""
    ancien = None
    for e in bundle["entry"]:
        res = e["resource"]
        if res["resourceType"] == "Patient":
            for i in res["identifier"]:
                if i.get("system") == "urn:ma:cin":
                    ancien, i["value"] = i["value"], cin
                elif ipp and i.get("system") == "https://chu-almassira.ma/ipp":
                    i["value"] = "P1-T" + cin[2:] if ipp == "auto" else ipp
    for e in bundle["entry"]:
        req = e.get("request") or {}
        if ancien and req.get("ifNoneExist"):
            req["ifNoneExist"] = req["ifNoneExist"].replace(ancien, cin)
    return bundle


def octets(b: dict) -> bytes:
    return json.dumps(b).encode("utf-8")


def cin_test() -> str:
    return "ZT" + "".join(random.choices("0123456789", k=6))


def patient_fhir(cin: str, **extra) -> dict:
    p = {"resourceType": "Patient", "identifier": [{"system": "urn:ma:cin", "value": cin}],
         "name": [{"family": "TestInterop", "given": ["Zoe"]}], "gender": "female", "birthDate": "1991-02-03"}
    p.update(extra)
    return p


# ───────────────────────── groupes ─────────────────────────
def groupe_A():
    essai("A1", "H1 /health sans jeton", 200, lambda: appel("GET", H1, "/health"))
    essai("A2", "H2 /health sans jeton", 200, lambda: appel("GET", H2, "/health"))
    for nom, base in (("H1", H1), ("H2", H2)):
        essai("A3", f"{nom} /metadata public : CapabilityStatement R5", 200, lambda b=base: appel("GET", b, "/metadata"),
              lambda r: None if r.json().get("resourceType") == "CapabilityStatement" and r.json().get("fhirVersion") == "5.0.0"
              else "CapabilityStatement R5 attendu")
    essai("A4", "H1 en http:// sur le port TLS : refuse", "exception", lambda: appel("GET", H1.replace("https", "http"), "/health"))
    essai("A5", "H2 en http:// sur le port TLS : refuse", "exception", lambda: appel("GET", H2.replace("https", "http"), "/health"))
    essai("A6", "H1 : certificat d'une autorite inconnue refuse", "exception",
          lambda: httpx.get(H1 + "/health", timeout=10.0))                     # sans notre CA : verification systeme
    essai("A7", "H2 : certificat d'une autorite inconnue refuse", "exception",
          lambda: httpx.get(H2 + "/health", timeout=10.0))


def groupe_B():
    for nom, base, chemin in (("H1", H1, f"/api/patients/{IPP_OK}/bundle"), ("H2", H2, f"/api/patients/{ID_OK}/bundle")):
        essai("B1", f"{nom} export sans jeton : 401 + OperationOutcome", 401, lambda b=base, c=chemin: appel("GET", b, c), oo)
        essai("B2", f"{nom} export jeton inconnu : 401", 401,
              lambda b=base, c=chemin: appel("GET", b, c, entetes={"Authorization": "Bearer " + "x" * 43}), oo)
        essai("B3", f"{nom} reception sans jeton : 401", 401, lambda b=base: appel("POST", b, "/api/retours", corps=b"{}"), oo)
    essai("B4", "H1 : jeton h2-clinique n'a pas h1:export -> 403", 403,
          lambda: appel("GET", H1, f"/api/patients/{IPP_OK}/bundle", "h2-clinique"), oo)
    essai("B5", "H2 : jeton h1-chu n'a pas h2:export -> 403", 403,
          lambda: appel("GET", H2, f"/api/patients/{ID_OK}/bundle", "h1-chu"), oo)
    essai("B6", "H1 : accueil n'a pas h1:export (pas d'acces medical) -> 403", 403,
          lambda: appel("GET", H1, f"/api/patients/{IPP_OK}/bundle", "h1-accueil"), oo)
    essai("B7", "H2 : accueil n'a pas h2:export -> 403", 403,
          lambda: appel("GET", H2, f"/api/patients/{ID_OK}/bundle", "h2-accueil"), oo)
    essai("B8", "H1 : h1-chu (jeton destine a H2) refuse sur H1 -> 403", 403,
          lambda: appel("POST", H1, "/api/retours", "h1-chu", corps=b"{}"), oo)
    essai("B9", "H1 : h1-interne ne peut pas gerer le consentement -> 403", 403,
          lambda: appel("POST", H1, f"/api/patients/{IPP_OK}/consentement", "h1-interne", json_={"statut": "actif"}), oo)
    essai("B10", "H1 : h1-interne ne lit pas le droit d'acces (reserve au DPO) -> 403", 403,
          lambda: appel("GET", H1, f"/api/patients/{IPP_OK}/droit-acces", "h1-interne"), oo)


def groupe_C():
    def export_ok(rep, fhir_h):
        b = rep.json()
        types = [e["resource"]["resourceType"] for e in b.get("entry", [])]
        if b.get("type") != "transaction":
            return "type != transaction"
        if not (b.get("identifier") or {}).get("value"):
            return "Bundle.identifier absent"
        if types.count("Patient") != 1 or "Consent" not in types:
            return f"Patient x1 et Consent attendus, vu {sorted(set(types))}"
        if any("request" not in e for e in b["entry"]):
            return "entree sans request"
        return None

    essai("C1", "H1 export du patient nominal : transaction + identifier + Consent", 200,
          lambda: appel("GET", H1, f"/api/patients/{IPP_OK}/bundle", "h1-interne"), lambda r: export_ok(r, "H1"))
    essai("C2", "H1 export : en-tete X-Exchange-Id = Bundle.identifier", 200,
          lambda: appel("GET", H1, f"/api/patients/{IPP_OK}/bundle", "h1-interne"),
          lambda r: None if r.headers.get("X-Exchange-Id") == r.json()["identifier"]["value"] else "X-Exchange-Id different")
    # Constat : H2 ne pose pas l'en-tete a l'export, seulement Bundle.identifier ; les deux clients d'envoi lisent
    # Bundle.identifier, donc l'echange n'en souffre pas. Voir docs/guide-test-complet.md.
    essai("C2b", "H2 export : Bundle.identifier non vide (l'en-tete X-Exchange-Id n'est pas pose par H2)", 200,
          lambda: appel("GET", H2, f"/api/patients/{ID_OK}/bundle", "h2-interne"),
          lambda r: None if (r.json().get("identifier") or {}).get("value") else "Bundle.identifier absent")
    essai("C3", "H1 export : consentement refuse -> 403 OperationOutcome (rien n'est envoye)", 403,
          lambda: appel("GET", H1, f"/api/patients/{IPP_REFUSE}/bundle", "h1-interne"), oo)
    essai("C4", "H1 export : patient inconnu -> 404", 404, lambda: appel("GET", H1, f"/api/patients/{IPP_INCONNU}/bundle", "h1-interne"), oo)
    essai("C5", "H1 alias /Patient/{ipp}/$everything", 200, lambda: appel("GET", H1, f"/Patient/{IPP_OK}/$everything", "h1-interne"))
    essai("C6", "H2 export du patient nominal : transaction + identifier + Consent", 200,
          lambda: appel("GET", H2, f"/api/patients/{ID_OK}/bundle", "h2-interne"), lambda r: export_ok(r, "H2"))
    essai("C7", "H2 export : consentement refuse -> 403 OperationOutcome", 403,
          lambda: appel("GET", H2, f"/api/patients/{ID_REFUSE}/bundle", "h2-interne"), oo)
    essai("C8", "H2 export : patient inconnu -> 404", 404, lambda: appel("GET", H2, f"/api/patients/{ID_INCONNU}/bundle", "h2-interne"), oo)
    essai("C9", "H2 alias /Patient/{id}/$everything", 200, lambda: appel("GET", H2, f"/Patient/{ID_OK}/$everything", "h2-interne"))
    essai("C10", "H2 export : pas de rue ni de personne a prevenir (minimisation 09-08)", 200,
          lambda: appel("GET", H2, f"/api/patients/{ID_OK}/bundle", "h2-interne"),
          lambda r: "rue exportee" if any("line" in a for e in r.json()["entry"] if e["resource"]["resourceType"] == "Patient"
                                        for a in e["resource"].get("address", [])) else None)


def groupe_D():
    cin = cin_test()
    ETAT["cin_d"] = cin
    b = avec_nouveau_cin(bundle_h1(), cin)
    ech = "ech-" + cin.lower()
    entetes = {"X-Exchange-Id": ech}

    def total_h2():
        r = appel("GET", H2, "/Patient", "h2-interne", params={"identifier": "urn:ma:cin|" + cin})
        return r.json()["total"]

    essai("D1", "H1->H2 simulation (nouveau patient) : 200, simulation=true, rien d'ecrit", 200,
          lambda: appel("POST", H2, "/api/retours/simulation", "h1-chu", corps=octets(b), entetes=entetes),
          lambda r: None if r.json().get("simulation") is True and total_h2() == 0 else "simulation a ecrit ou mal etiquetee")
    essai("D2", "H1->H2 reception definitive : cree le patient (200/201)", {200, 201},
          lambda: appel("POST", H2, "/api/retours", "h1-chu", corps=octets(b), entetes=entetes),
          lambda r: None if total_h2() == 1 else f"patient absent de H2 apres import (total={total_h2()})")
    essai("D3", "H1->H2 REJEU du meme X-Exchange-Id : 200, deja traite, pas de doublon", 200,
          lambda: appel("POST", H2, "/api/retours", "h1-chu", corps=octets(b), entetes=entetes),
          lambda r: None if total_h2() == 1 and r.json().get("deja_traite") is True else "doublon ou rejeu non detecte")
    essai("D4", "H1->H2 meme contenu, NOUVEL identifiant d'echange : toujours un seul patient", {200, 201},
          lambda: appel("POST", H2, "/api/retours", "h1-chu", corps=octets(b), entetes={"X-Exchange-Id": ech + "-bis"}),
          lambda r: None if total_h2() == 1 else f"doublon : total={total_h2()}")
    essai("D5", "H1->H2 alias POST /Bundle", {200, 201}, lambda: appel("POST", H2, "/Bundle", "h1-chu", corps=octets(b),
                                                                        entetes={"X-Exchange-Id": ech + "-ter"}))
    essai("D6", "H1->H2 patient deja connu (CIN existant) : rapproche, pas de creation", {200, 201},
          lambda: appel("POST", H2, "/api/retours", "h1-chu", corps=octets(bundle_h1())),
          lambda r: None if r.json().get("patient_cree") is False else "un patient connu a ete recree")

    def ambigu():
        b2 = bundle_h1()                                                    # CIN d'un dossier (AB123456)...
        for e in b2["entry"]:
            if e["resource"]["resourceType"] == "Patient":
                for i in e["resource"]["identifier"]:
                    if i.get("system") == "https://chu-almassira.ma/ipp":
                        i["value"] = "P1-T" + cin[2:]                       # ...et IPP d'un AUTRE dossier (celui cree en D2)
        return octets(b2)
    essai("D12", "H1->H2 CIN d'un dossier + IPP d'un autre : identite ambigue -> 409 (validation humaine)", 409,
          lambda: appel("POST", H2, "/api/retours", "h1-chu", corps=ambigu()), oo)

    retour = bundle_h2()
    ech2 = "ech-h2-" + cin.lower()
    essai("D7", "H2->H1 simulation avec les PUT de H2 : 200, simulation=true", 200,
          lambda: appel("POST", H1, "/api/retours/simulation", "h2-clinique", corps=octets(retour), entetes={"X-Exchange-Id": ech2}),
          lambda r: None if r.json().get("simulation") is True else "pas une simulation")
    essai("D8", "H2->H1 reception definitive, X-Exchange-Id renvoye", 200,
          lambda: appel("POST", H1, "/api/retours", "h2-clinique", corps=octets(retour), entetes={"X-Exchange-Id": ech2}),
          lambda r: None if r.json().get("echange_id") == ech2 and r.headers.get("X-Exchange-Id") == ech2 else "echange_id non renvoye")
    essai("D9", "H2->H1 REJEU : 200 (MERGE, memes lignes)", 200,
          lambda: appel("POST", H1, "/api/retours", "h2-clinique", corps=octets(retour), entetes={"X-Exchange-Id": ech2}),
          lambda r: None if r.json().get("modifications_conservees") is True else "reponse inattendue")
    essai("D10", "H2->H1 alias POST /Bundle", 200, lambda: appel("POST", H1, "/Bundle", "h2-clinique", corps=octets(retour)))
    essai("D11", "H1 : X-Exchange-Id invalide (espaces) -> 422", 422,
          lambda: appel("POST", H1, "/api/retours", "h2-clinique", corps=octets(retour), entetes={"X-Exchange-Id": "id invalide"}), oo)


def groupe_E():
    h2_vers_h1 = bundle_h2()
    h1_vers_h2 = avec_nouveau_cin(bundle_h1(), cin_test())

    def les_deux(ident, titre, attendu, fabriquer_pour_h1, fabriquer_pour_h2, condition=oo):
        essai(ident + "a", f"H1 recoit : {titre}", attendu,
              lambda: appel("POST", H1, "/api/retours/simulation", "h2-clinique", corps=fabriquer_pour_h1()), condition)
        essai(ident + "b", f"H2 recoit : {titre}", attendu,
              lambda: appel("POST", H2, "/api/retours/simulation", "h1-chu", corps=fabriquer_pour_h2()), condition)

    les_deux("E1", "ce n'est pas un Bundle", {400, 422}, lambda: b'{"resourceType":"Patient"}', lambda: b'{"resourceType":"Patient"}')
    les_deux("E2", "corps qui n'est pas du JSON", {400, 422}, lambda: b"ceci n'est pas du json", lambda: b"ceci n'est pas du json")
    les_deux("E3", "corps vide", {400, 422}, lambda: b"", lambda: b"")

    def sans_consent(b):
        b["entry"] = [e for e in b["entry"] if e["resource"]["resourceType"] != "Consent"]
        return octets(b)
    essai("E4", "H2 recoit un Bundle SANS Consent -> 403 (loi 09-08)", 403,
          lambda: appel("POST", H2, "/api/retours/simulation", "h1-chu", corps=sans_consent(copy.deepcopy(h1_vers_h2))), oo)

    def consent_refuse(b):
        for e in b["entry"]:
            if e["resource"]["resourceType"] == "Consent":
                e["resource"]["decision"], e["resource"]["status"] = "deny", "rejected"
        return octets(b)
    essai("E5a", "H1 recoit un Consent refuse -> 403", 403,
          lambda: appel("POST", H1, "/api/retours/simulation", "h2-clinique", corps=consent_refuse(copy.deepcopy(h2_vers_h1))), oo)
    essai("E5b", "H2 recoit un Consent refuse -> 403", 403,
          lambda: appel("POST", H2, "/api/retours/simulation", "h1-chu", corps=consent_refuse(copy.deepcopy(h1_vers_h2))), oo)

    def deux_patients(b):
        patients = [e for e in b["entry"] if e["resource"]["resourceType"] == "Patient"]
        b["entry"].append(copy.deepcopy(patients[0]))
        return octets(b)
    les_deux("E6", "deux Patient dans le Bundle", 422, lambda: deux_patients(copy.deepcopy(h2_vers_h1)),
             lambda: deux_patients(copy.deepcopy(h1_vers_h2)))

    def instruction_delete(b):
        cible = next(e for e in b["entry"] if e["resource"]["resourceType"] not in ("Patient", "Consent"))
        cible["request"] = {"method": "DELETE", "url": cible["resource"]["resourceType"] + "/x"}
        return octets(b)
    les_deux("E7", "instruction DELETE (non supportee)", 422, lambda: instruction_delete(copy.deepcopy(h2_vers_h1)),
             lambda: instruction_delete(copy.deepcopy(h1_vers_h2)))

    def url_incoherente(b):
        cible = next(e for e in b["entry"] if e["resource"]["resourceType"] not in ("Patient", "Consent"))
        cible["request"]["url"] = "Patient/x"
        return octets(b)
    les_deux("E8", "request.url incoherent avec le type de ressource", 422, lambda: url_incoherente(copy.deepcopy(h2_vers_h1)),
             lambda: url_incoherente(copy.deepcopy(h1_vers_h2)))

    def sans_identite(b):
        for e in b["entry"]:
            if e["resource"]["resourceType"] == "Patient":
                e["resource"]["identifier"] = []
        return octets(b)
    les_deux("E9", "Patient sans CIN ni identifiant (identite insuffisante)", {409, 422},
             lambda: sans_identite(copy.deepcopy(h2_vers_h1)), lambda: sans_identite(copy.deepcopy(h1_vers_h2)))

    def date_naissance_absente(b):
        for e in b["entry"]:
            if e["resource"]["resourceType"] == "Patient":
                e["resource"].pop("birthDate", None)
        return octets(b)
    les_deux("E10", "Patient sans date de naissance", 422, lambda: date_naissance_absente(copy.deepcopy(h2_vers_h1)),
             lambda: date_naissance_absente(copy.deepcopy(h1_vers_h2)))

    def reference_cassee(b):
        for e in b["entry"]:
            if e["resource"]["resourceType"] == "Observation":
                e["resource"]["encounter"] = {"reference": "Encounter/inexistant"}
                break
        return octets(b)
    essai("E11a", "H1 recoit une reference interne qui ne se resout pas -> 422", 422,
          lambda: appel("POST", H1, "/api/retours/simulation", "h2-clinique", corps=reference_cassee(copy.deepcopy(h2_vers_h1))), oo)

    def patient_inconnu_de_h1(b):
        return octets(avec_nouveau_cin(b, "ZZ000000"))
    essai("E12", "H1 recoit un retour pour un patient inconnu du CHU -> 404 (ou 409 si ambigu)", {404, 409},
          lambda: appel("POST", H1, "/api/retours", "h2-clinique", corps=patient_inconnu_de_h1(copy.deepcopy(h2_vers_h1))), oo)

    gros = b'{"resourceType":"Bundle","type":"transaction","entry":[],"x":"' + b"a" * 6_000_000 + b'"}'
    essai("E13a", "H1 : corps de 6 Mo -> 413 (SEC_TAILLE_MAX_CORPS)", 413, lambda: appel("POST", H1, "/api/retours/simulation", "h2-clinique", corps=gros), oo)
    essai("E13b", "H2 : corps de 6 Mo -> 413", 413, lambda: appel("POST", H2, "/api/retours/simulation", "h1-chu", corps=gros), oo)
    essai("E14a", "H2 : l'accueil n'a pas la portee d'import -> 403", 403,
          lambda: appel("POST", H2, "/api/retours", "h2-accueil", corps=b"{}"), oo)
    essai("E14b", "H1 : l'accueil n'a pas la portee d'import -> 403", 403,
          lambda: appel("POST", H1, "/api/retours", "h1-accueil", corps=b"{}"), oo)


def groupe_F():
    for nom, base, client_ecriture in (("H1", H1, "h1-interne"), ("H2", H2, "h2-interne")):
        cin = cin_test()
        essai("F1", f"{nom} POST /Patient : 201 + Location", 201, lambda b=base, c=client_ecriture, n=cin: appel("POST", b, "/Patient", c, json_=patient_fhir(n)),
              lambda r: None if r.headers.get("Location", "").startswith("/Patient/") else "en-tete Location absent")
        essai("F2", f"{nom} POST /Patient meme CIN : 409", 409, lambda b=base, c=client_ecriture, n=cin: appel("POST", b, "/Patient", c, json_=patient_fhir(n)), oo)
        essai("F3", f"{nom} GET /Patient?identifier=urn:ma:cin|... : 1 resultat", 200,
              lambda b=base, c=client_ecriture, n=cin: appel("GET", b, "/Patient", c, params={"identifier": "urn:ma:cin|" + n}),
              lambda r: None if r.json().get("total") == 1 else f"total={r.json().get('total')}")

        def lire(b=base, c=client_ecriture, n=cin):
            ident = appel("GET", b, "/Patient", c, params={"identifier": "urn:ma:cin|" + n}).json()["entry"][0]["resource"]["id"]
            return appel("GET", b, f"/Patient/{ident}", c)
        essai("F4", f"{nom} GET /Patient/{{id}} : 200", 200, lire)
        essai("F5", f"{nom} GET /Patient/{{id}} inconnu : 404", 404,
              lambda b=base, c=client_ecriture: appel("GET", b, "/Patient/ID-INCONNU-999", c), oo)
        essai("F6", f"{nom} POST /Patient sans nom : 422", 422,
              lambda b=base, c=client_ecriture: appel("POST", b, "/Patient", c, json_=patient_fhir(cin_test(), name=[])), oo)
        essai("F7", f"{nom} POST /Patient avec une autre ressource : 400/422", {400, 422},
              lambda b=base, c=client_ecriture: appel("POST", b, "/Patient", c, json_={"resourceType": "Observation"}), oo)
        essai("F8", f"{nom} POST /Patient avec le jeton d'accueil du registre (sans portee patient.creer) -> 403", 403,
              lambda b=base, c=("h1-accueil" if nom == "H1" else "h2-accueil"): appel("POST", b, "/Patient", c, json_=patient_fhir(cin_test())))
        essai("F9", f"{nom} patient cree sans consentement : export refuse (403)", 403,
              lambda b=base, c=client_ecriture, n=cin: appel("GET", b, "/Patient/" + appel("GET", b, "/Patient", c, params={"identifier": "urn:ma:cin|" + n}).json()["entry"][0]["resource"]["id"] + "/$everything", c), oo)


def groupe_G():
    for nom, base, accueil, interne, pid in (("H1", H1, "h1-accueil", "h1-interne", IPP_OK), ("H2", H2, "h2-accueil", "h2-interne", ID_OK)):
        route = f"/api/patients/{pid}/consentement"
        essai("G1", f"{nom} consentement : etat 200, partage_autorise", 200, lambda b=base, a=accueil, r=route: appel("GET", b, r, a),
              lambda r: None if r.json().get("partage_autorise") is True else "partage non autorise au depart : consentement du patient nominal a verifier")
        essai("G2", f"{nom} recueil sans recueilli_par : 422", 422, lambda b=base, a=accueil, r=route: appel("POST", b, r, a, json_={"statut": "actif"}), oo)
        essai("G3", f"{nom} recueil avec statut invalide : 422", 422,
              lambda b=base, a=accueil, r=route: appel("POST", b, r, a, json_={"statut": "peut-etre", "recueilli_par": "test"}), oo)
        essai("G4", f"{nom} RETRAIT du consentement : 200, partage_autorise=false", 200,
              lambda b=base, a=accueil, r=route: appel("POST", b, r + "/retrait", a, json_={"recueilli_par": "Test automatique", "motif": "test de retrait"}),
              lambda r: None if r.json().get("partage_autorise") is False else "partage encore autorise")
        essai("G5", f"{nom} apres retrait : export -> 403", 403,
              lambda b=base, i=interne, p=pid: appel("GET", b, f"/api/patients/{p}/bundle", i), oo)
        essai("G6", f"{nom} deuxieme retrait : 409 (rien a retirer)", {409, 422},
              lambda b=base, a=accueil, r=route: appel("POST", b, r + "/retrait", a, json_={"recueilli_par": "Test automatique", "motif": "x"}), oo)
        essai("G7", f"{nom} recueil limite au destinataire autre hopital : le partage vers cet hopital reste refuse", 201,
              lambda b=base, a=accueil, r=route, n=nom: appel("POST", b, r, a, json_={"statut": "actif", "recueilli_par": "Test automatique",
                                                                                      "destinataires": ["H1" if n == "H1" else "H2"]}))
        essai("G8", f"{nom} ...export du Bundle vers l'autre hopital -> 403 (destinataire non autorise)", 403,
              lambda b=base, i=interne, p=pid: appel("GET", b, f"/api/patients/{p}/bundle", i), oo)
        essai("G9", f"{nom} nouveau recueil actif (restaure l'etat de depart) : 201", 201,
              lambda b=base, a=accueil, r=route: appel("POST", b, r, a, json_={"statut": "actif", "recueilli_par": "Test automatique"}))
        essai("G10", f"{nom} apres re-recueil : export 200", 200, lambda b=base, i=interne, p=pid: appel("GET", b, f"/api/patients/{p}/bundle", i))
        essai("G11", f"{nom} l'historique garde toutes les versions", 200, lambda b=base, a=accueil, r=route: appel("GET", b, r, a),
              lambda r: None if len(r.json().get("historique") or []) >= 3 else f"historique trop court : {len(r.json().get('historique') or [])}")


def groupe_H():
    import client_envoi as client_h2_envoi              # hopital2/client_envoi.py (envoi H2 -> H1)
    import client_envoi_h1 as client_h1_envoi           # hopital1/client_envoi_h1.py (envoi H1 -> H2)
    from securite import client_securise
    os.environ.setdefault("SEC_CA", CA)
    calmer()          # les clients d'envoi, eux, ne patientent pas sur 429 : ils mettent en file (comportement voulu)

    def clients_h1():
        return (client_securise(H1, jeton=jeton("h1-interne")), client_securise(H2, jeton=jeton("h1-chu")))

    def mort(client):
        return client_securise("https://127.0.0.1:9", jeton=jeton(client))      # personne n'ecoute sur le port 9

    def resultat(fonction):
        class R:                                             # adapte un dict de resultat au format de `essai`
            status_code = 200
            text = ""
        r = R()
        r.valeur = fonction()
        return r

    def statut_attendu(attendu):
        return lambda r: None if r.valeur["statut"] == attendu else f"statut={r.valeur['statut']} ({r.valeur.get('detail', '')[:90]})"

    ob = client_h1_envoi.Outbox(":memory:", chiffreur=None)
    essai("H1", "H1->H2 client d'envoi : export, simulation, envoi", 200,
          lambda: resultat(lambda: client_h1_envoi.envoyer_dossier(IPP_OK, *clients_h1(), ob)), statut_attendu("envoye"))
    essai("H2", "H1->H2 patient au consentement refuse : bloque avant l'envoi", 200,
          lambda: resultat(lambda: client_h1_envoi.envoyer_dossier(IPP_REFUSE, *clients_h1(), ob)), statut_attendu("bloque"))
    essai("H3", "H1->H2 patient inconnu : export impossible (404)", 200,
          lambda: resultat(lambda: client_h1_envoi.envoyer_dossier(IPP_INCONNU, *clients_h1(), ob)), statut_attendu("export_impossible"))

    ob2 = client_h1_envoi.Outbox(":memory:", chiffreur=None)
    h1c = client_securise(H1, jeton=jeton("h1-interne")) if "h1-interne" else None
    envoi = {}

    def injoignable():
        envoi["r"] = client_h1_envoi.envoyer_dossier(IPP_OK, h1c, mort("h1-chu"), ob2, maintenant=1000.0)
        return envoi["r"]
    essai("H4", "H1->H2 H2 eteint : l'envoi est mis en file (en_attente, reprise dans 60 s)", 200,
          lambda: resultat(injoignable), statut_attendu("en_attente"))
    essai("H5", "H1->H2 reprise trop tot : rien ne part", 200,
          lambda: resultat(lambda: {"statut": "rien" if client_h1_envoi.reprendre(ob2, clients_h1()[1], maintenant=1030.0) == [] else "parti"}),
          statut_attendu("rien"))
    essai("H6", "H1->H2 H2 de retour, delai ecoule : reprise reussie (meme identifiant d'echange)", 200,
          lambda: resultat(lambda: client_h1_envoi.reprendre(ob2, clients_h1()[1], maintenant=1061.0)[0]), statut_attendu("envoye"))
    essai("H7", "H1->H2 apres succes : plus rien a reprendre", 200,
          lambda: resultat(lambda: {"statut": "vide" if client_h1_envoi.reprendre(ob2, clients_h1()[1], maintenant=10**7) == [] else "reste"}),
          statut_attendu("vide"))

    ob3 = client_h1_envoi.Outbox(":memory:", chiffreur=None)
    essai("H8", "H1->H2 H2 eteint puis consentement RETIRE : la reprise est annulee", 200,
          lambda: resultat(lambda: _scenario_annulation_h1(client_h1_envoi, ob3, h1c, mort, clients_h1)), statut_attendu("annule"))

    # H2 -> H1 avec le client d'envoi de H2
    h2c = client_securise(H2, jeton=jeton("h2-interne")) if _a_jeton("h2-interne") else None
    obh2 = client_h2_envoi.Outbox(":memory:", chiffreur=None)

    def h1_pour_h2(client="h2-clinique"):
        return client_securise(H1, jeton=jeton(client))
    essai("H9", "H2->H1 client d'envoi de H2 : export, simulation, envoi", 200,
          lambda: resultat(lambda: client_h2_envoi.envoyer_dossier(ID_OK, h2c, h1_pour_h2(), obh2)), statut_attendu("envoye"))
    essai("H10", "H2->H1 patient au consentement refuse : bloque", 200,
          lambda: resultat(lambda: client_h2_envoi.envoyer_dossier(ID_REFUSE, h2c, h1_pour_h2(), obh2)), statut_attendu("bloque"))
    obh2b = client_h2_envoi.Outbox(":memory:", chiffreur=None)
    essai("H11", "H2->H1 H1 eteint : mis en file, puis reprise reussie sans doublon", 200,
          lambda: resultat(lambda: _scenario_reprise_h2(client_h2_envoi, obh2b, h2c, mort, h1_pour_h2)), statut_attendu("envoye"))


def _a_jeton(nom):
    try:
        jeton(nom)
        return True
    except Ignore:
        return False


def _scenario_annulation_h1(mod, outbox, h1c, mort, clients_h1):
    r = mod.envoyer_dossier(IPP_OK, h1c, mort("h1-chu"), outbox, maintenant=0.0)
    if r["statut"] != "en_attente":
        return r
    route = f"/api/patients/{IPP_OK}/consentement"
    try:
        appel("POST", H1, route + "/retrait", "h1-accueil", json_={"recueilli_par": "Test automatique", "motif": "retrait pendant l'attente"})
        res = mod.reprendre(outbox, clients_h1()[1], h1=h1c, maintenant=100.0)
        return res[0] if res else {"statut": "rien", "detail": "aucune reprise"}
    finally:                                                 # on remet l'etat de depart quoi qu'il arrive
        appel("POST", H1, route, "h1-accueil", json_={"statut": "actif", "recueilli_par": "Test automatique"})


def _scenario_reprise_h2(mod, outbox, h2c, mort, h1_pour_h2):
    r = mod.envoyer_dossier(ID_OK, h2c, mort("h2-clinique"), outbox, maintenant=0.0)
    if r["statut"] != "en_attente":
        return r
    return mod.reprendre(outbox, h1_pour_h2(), maintenant=61.0)[0]


def groupe_I():
    """Limites : DESTRUCTIF. Bloque l'adresse du testeur quelques minutes (SEC_VERROU_SECONDES, 300 s par defaut)."""
    essai("I1", "Debit : au-dela de SEC_DEBIT_PAR_MINUTE requetes/minute -> 429", 429,
          lambda: _inonder(H2))
    time.sleep(2)
    essai("I2", "Verrouillage : apres SEC_ECHECS_MAX jetons faux, meme un bon jeton est refuse (429)", 429,
          lambda: _echecs_puis_bon_jeton(H1))


def _inonder(base):
    """/health est exempte de la limitation : on inonde une route authentifiee (export du patient nominal de H2)."""
    dernier = None
    for _ in range(int(os.getenv("SEC_DEBIT_PAR_MINUTE") or 120) + 20):
        dernier = appel("GET", base, f"/api/patients/{ID_OK}/bundle", "h2-interne", attendre=False)
        if dernier.status_code == 429:
            return dernier
    return dernier


def _echecs_puis_bon_jeton(base):
    for _ in range(int(os.getenv("SEC_ECHECS_MAX") or 5) + 1):
        appel("GET", base, f"/api/patients/{IPP_OK}/bundle", entetes={"Authorization": "Bearer " + "f" * 43}, attendre=False)
    return appel("GET", base, f"/api/patients/{IPP_OK}/bundle", "h1-interne", attendre=False)


GROUPES = {"A": groupe_A, "B": groupe_B, "C": groupe_C, "D": groupe_D, "E": groupe_E, "F": groupe_F, "G": groupe_G,
           "H": groupe_H, "I": groupe_I}


def rapport(chemin: Path):
    ok = sum(r["statut"] == "OK" for r in RESULTATS)
    echecs = [r for r in RESULTATS if r["statut"] == "ECHEC"]
    skips = sum(r["statut"] == "SKIP" for r in RESULTATS)
    lignes = [f"# Rapport des tests d'echange complets", "",
              f"Date : {time.strftime('%Y-%m-%d %H:%M')} . H1 : {H1} . H2 : {H2}", "",
              f"**{ok} reussis . {len(echecs)} en echec . {skips} ignores** sur {len(RESULTATS)} essais.", "",
              "| Groupe | Essai | Description | Attendu | Obtenu | Resultat | ms |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in RESULTATS:
        lignes.append(f"| {r['groupe']} | {r['id']} | {r['titre']} | {r['attendu']} | {r['obtenu']} | {r['statut']}"
                      + (f" ({r['detail']})" if r["detail"] else "") + f" | {r['ms']} |")
    chemin.parent.mkdir(exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return ok, len(echecs), skips


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--destructif", action="store_true", help="ajoute le groupe I (debit, verrouillage)")
    ap.add_argument("--seulement", nargs="+", metavar="GROUPE", help="ex. --seulement C D")
    a = ap.parse_args()
    choisis = [g.upper() for g in (a.seulement or "ABCDEFGH")] + (["I"] if a.destructif and not a.seulement else [])
    print(f"H1 = {H1}\nH2 = {H2}\nCA = {CA}\n")
    for g in choisis:
        GROUPE[0] = g
        print(f"--- Groupe {g} : {GROUPES[g].__doc__ or GROUPES[g].__name__} ---")
        try:
            GROUPES[g]()
        except Ignore as exc:
            print(f"[ SKIP] groupe {g} : {exc}")
            RESULTATS.append({"groupe": g, "id": g, "titre": "groupe entier", "attendu": "-", "obtenu": "-",
                              "statut": "SKIP", "detail": str(exc), "ms": 0})
    ok, echecs, skips = rapport(RACINE / "sortie" / "rapport_echange_complet.md")
    print(f"\n=== {ok} reussis, {echecs} en echec, {skips} ignores sur {len(RESULTATS)} . rapport : sortie/rapport_echange_complet.md ===")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
