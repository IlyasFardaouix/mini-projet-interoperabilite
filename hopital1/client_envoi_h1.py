"""
client_envoi_h1.py — envoie un dossier du CHU (H1) vers l'API de la clinique (H2),
avec file d'attente et reprise. Équivalent de hopital2/client_envoi.py.
===========================================================================

Module appelé par l'orchestrateur de l'échange (ou en ligne de commande, voir
plus bas). Ce n'est pas une route de l'API.

  1. demande le Bundle à l'API H1          GET  /api/patients/{ipp}/bundle   (403 = consentement refusé : on s'arrête)
  2. teste chez H2 à blanc                 POST /api/retours/simulation      (refus définitif : on s'arrête)
  3. met le Bundle dans la FILE D'ATTENTE  (base SQLite : survit à un redémarrage, chiffrée si H1_CLE_CHIFFREMENT)
  4. tente l'envoi                         POST /api/retours  + en-tête X-Exchange-Id
  5. selon la réponse :
        200 / 201                   → « envoye »
        injoignable, 408, 429, 5xx  → « en_attente » : nouvel essai plus tard (1 min, 5 min, 30 min, 2 h, 6 h)
        autre 4xx (403, 409, 422…)  → « echec » : réessayer ne servirait à rien, une personne doit regarder
  6. reprendre() relance les envois en attente. Le Bundle et l'identifiant d'échange sont ceux du premier essai :
     si H2 avait en fait bien reçu l'envoi, le rejeu ne crée aucun doublon.
     Avec le client H1 (reprendre(..., h1=...)), le consentement est revérifié avant chaque reprise :
     retiré ou expiré → « annule » ; impossible à vérifier → l'envoi attend, rien ne part.

Variables : H2_BASE_URL (adresse de l'API de la clinique), H1_JETON_VERS_H2 (jeton du client h1-chu,
reçu de la clinique hors Git), H1_BASE_URL + H1_JETON_LOCAL (API du CHU, client local),
H1_CLE_CHIFFREMENT (clé de la file), H1_FILE_ENVOI (chemin SQLite, défaut file_envoi_h1.sqlite3).

Ligne de commande (depuis hopital1/) :
    python client_envoi_h1.py envoyer P1-0106     exporter, tester, mettre en file, envoyer
    python client_envoi_h1.py reprendre           relancer les envois en attente dont l'heure est venue
    python client_envoi_h1.py etat                lister la file
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

DELAIS_REPRISE = (60, 300, 1800, 7200, 21600)      # secondes, identiques à H2
MAX_TENTATIVES = 6
CODES_A_REESSAYER = {408, 425, 429, 500, 502, 503, 504}
ENTETES = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json, application/json"}

_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))


def client_h2(base_url: Optional[str] = None):
    """Client HTTP durci pour appeler l'API de la clinique (certificat vérifié, délais,
    pas de redirection, jeton lu dans l'environnement : `H1_JETON_VERS_H2`)."""
    from securite import client_securise
    return client_securise(base_url or os.getenv("H2_BASE_URL") or "https://127.0.0.1:8002",
                           variable_jeton="H1_JETON_VERS_H2")


def client_local(base_url: Optional[str] = None):
    """Client HTTP vers l'API du CHU lui-même (export du Bundle, état du consentement)."""
    from securite import client_securise
    jeton = os.getenv("H1_JETON_LOCAL") or os.getenv("H1_API_TOKEN")
    return client_securise(base_url or os.getenv("H1_BASE_URL") or "https://127.0.0.1:8000", jeton=jeton)


_PAR_DEFAUT = object()


class Outbox:
    """File d'attente des envois (SQLite).

    Le Bundle en attente est un dossier de santé complet : il est chiffré au repos
    (AES-256-GCM, clé H1_CLE_CHIFFREMENT, lié à l'identifiant d'échange). Sans clé,
    il reste en clair et un avertissement est affiché.
    """

    _avertie = False

    def __init__(self, chemin: str = ":memory:", chiffreur=_PAR_DEFAUT):
        if chiffreur is _PAR_DEFAUT:
            from securite.chiffrement import Chiffreur
            chiffreur = Chiffreur.depuis_env("H1_CLE_CHIFFREMENT")
            if chiffreur is None and chemin != ":memory:" and not Outbox._avertie:
                Outbox._avertie = True                      # une seule fois par processus, pas à chaque ouverture
                print("[client_envoi_h1] ATTENTION : H1_CLE_CHIFFREMENT absent, Bundles en clair sur le disque.")
        self.chiffreur = chiffreur
        self.db = sqlite3.connect(chemin)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS envois (
            id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT, echange_id TEXT UNIQUE, bundle TEXT,
            statut TEXT, tentatives INTEGER DEFAULT 0, prochaine REAL, derniere_erreur TEXT,
            code_http INTEGER, cree_le REAL, maj_le REAL)""")
        self.db.commit()

    def ajouter(self, patient_id: str, echange_id: str, bundle_json: str, maintenant: float) -> int:
        cur = self.db.execute(
            "INSERT INTO envois (patient_id, echange_id, bundle, statut, prochaine, cree_le, maj_le) "
            "VALUES (?, ?, ?, 'en_attente', ?, ?, ?)",
            (patient_id, echange_id, self._fermer(bundle_json, echange_id), maintenant, maintenant, maintenant))
        self.db.commit()
        return cur.lastrowid

    def _fermer(self, bundle_json: str, echange_id: str) -> str:
        return self.chiffreur.chiffrer_texte(bundle_json, "envoi:" + echange_id) if self.chiffreur else bundle_json

    def _ouvrir(self, contenu: str, echange_id: str) -> str:
        if self.chiffreur and not contenu.lstrip().startswith("{"):
            return self.chiffreur.dechiffrer_texte(contenu, "envoi:" + echange_id)
        return contenu                                   # ancienne ligne en clair

    def get(self, envoi_id: int) -> Optional[dict]:
        """Ligne de la file, Bundle déchiffré."""
        ligne = self.db.execute("SELECT * FROM envois WHERE id = ?", (envoi_id,)).fetchone()
        if ligne is None:
            return None
        resultat = dict(ligne)
        resultat["bundle"] = self._ouvrir(resultat["bundle"], resultat["echange_id"])
        return resultat

    def a_reprendre(self, maintenant: float) -> list:
        return self.db.execute("SELECT * FROM envois WHERE statut = 'en_attente' AND prochaine <= ? ORDER BY id",
                               (maintenant,)).fetchall()

    def lister(self) -> list:
        return self.db.execute("SELECT id, patient_id, echange_id, statut, tentatives, code_http, "
                               "derniere_erreur FROM envois ORDER BY id").fetchall()

    def maj(self, envoi_id: int, maintenant: float, **champs) -> None:
        colonnes = ", ".join(f"{k} = ?" for k in champs)
        self.db.execute(f"UPDATE envois SET {colonnes}, maj_le = ? WHERE id = ?",
                        (*champs.values(), maintenant, envoi_id))
        self.db.commit()


def _resume(reponse: httpx.Response) -> str:
    """Message lisible d'une réponse d'erreur (OperationOutcome ou texte)."""
    try:
        issue = reponse.json()["issue"][0]
        return f"{issue.get('code')}: {issue.get('diagnostics')}"
    except Exception:
        return reponse.text[:200]


def _resultat(outbox: Outbox, envoi_id: int, statut: str, http: Optional[int], detail: str) -> dict:
    ligne = outbox.get(envoi_id)
    return {"statut": statut, "http": http, "detail": detail, "envoi_id": envoi_id,
            "tentatives": ligne["tentatives"], "echange_id": ligne["echange_id"]}


def _temporaire(outbox, ligne, n, now, code, message) -> dict:
    if n >= MAX_TENTATIVES:
        outbox.maj(ligne["id"], now, statut="echec", tentatives=n, code_http=code,
                   derniere_erreur=f"Abandon après {n} tentatives. Dernière erreur : {message}")
        return _resultat(outbox, ligne["id"], "echec", code, f"Abandon après {n} tentatives : {message}")
    delai = DELAIS_REPRISE[min(n - 1, len(DELAIS_REPRISE) - 1)]
    outbox.maj(ligne["id"], now, statut="en_attente", tentatives=n, code_http=code,
               derniere_erreur=message, prochaine=now + delai)
    return _resultat(outbox, ligne["id"], "en_attente", code, f"{message} — nouvelle tentative dans {delai} s.")


def tenter(outbox: Outbox, envoi_id: int, h2, *, chemin: str = "/api/retours",
           maintenant: Optional[float] = None) -> dict:
    """Une tentative d'envoi. `h2` = httpx.Client (ou équivalent) déjà configuré avec base_url et jeton."""
    now = time.time() if maintenant is None else maintenant
    ligne = outbox.get(envoi_id)
    n = ligne["tentatives"] + 1
    try:
        rep = h2.post(chemin, content=ligne["bundle"], headers={**ENTETES, "X-Exchange-Id": ligne["echange_id"]})
    except httpx.TransportError as exc:                       # injoignable, délai dépassé…
        return _temporaire(outbox, ligne, n, now, None, f"H2 injoignable ({exc.__class__.__name__})")

    if rep.status_code in (200, 201):
        outbox.maj(envoi_id, now, statut="envoye", tentatives=n, code_http=rep.status_code, derniere_erreur=None)
        return _resultat(outbox, envoi_id, "envoye", rep.status_code, "Envoi confirmé par H2.")
    if rep.status_code in CODES_A_REESSAYER:
        return _temporaire(outbox, ligne, n, now, rep.status_code, _resume(rep))
    outbox.maj(envoi_id, now, statut="echec", tentatives=n, code_http=rep.status_code, derniere_erreur=_resume(rep))
    return _resultat(outbox, envoi_id, "echec", rep.status_code, _resume(rep))


def envoyer_dossier(ipp: str, h1, h2, outbox: Outbox, *, chemin_reception: str = "/api/retours",
                    simuler_avant: bool = True, maintenant: Optional[float] = None) -> dict:
    """Exporte le dossier depuis l'API H1, le teste chez H2, le met en file puis tente l'envoi."""
    now = time.time() if maintenant is None else maintenant

    try:
        rep = h1.get(f"/api/patients/{ipp}/bundle")
    except httpx.TransportError as exc:
        return {"statut": "export_impossible", "http": None,
                "detail": f"API H1 injoignable ({exc.__class__.__name__})"}
    if rep.status_code == 403:
        return {"statut": "bloque", "http": 403, "detail": _resume(rep)}      # consentement : rien n'est envoyé
    if rep.status_code != 200:
        return {"statut": "export_impossible", "http": rep.status_code, "detail": _resume(rep)}
    bundle = rep.json()
    echange_id = (bundle.get("identifier") or {}).get("value") or rep.headers.get("X-Exchange-Id")
    if not echange_id:
        return {"statut": "export_impossible", "http": 200,
                "detail": "Bundle sans identifiant d'échange (Bundle.identifier) : rejeu non garanti."}

    if simuler_avant:
        try:
            sim = h2.post(f"{chemin_reception}/simulation", content=rep.content,
                          headers={**ENTETES, "X-Exchange-Id": echange_id})
        except httpx.TransportError:
            sim = None                                       # H2 injoignable : on met en file, la reprise réessaiera
        if sim is not None and sim.status_code not in (200, 201) and sim.status_code not in CODES_A_REESSAYER:
            return {"statut": "refuse_simulation", "http": sim.status_code, "detail": _resume(sim)}

    envoi_id = outbox.ajouter(ipp, echange_id, rep.text, now)
    return tenter(outbox, envoi_id, h2, chemin=chemin_reception, maintenant=now)


def partage_toujours_autorise(h1, ipp: str) -> tuple[Optional[bool], str]:
    """(True | False | None, motif) d'après GET /api/patients/{ipp}/consentement.
    None : la vérification n'a pas pu se faire (H1 injoignable, portée manquante…)."""
    try:
        rep = h1.get(f"/api/patients/{ipp}/consentement")
    except httpx.TransportError as exc:
        return None, f"consentement non vérifiable (H1 injoignable : {exc.__class__.__name__})"
    if rep.status_code != 200:
        return None, f"consentement non vérifiable (HTTP {rep.status_code})"
    etat = rep.json()
    return bool(etat.get("partage_autorise")), str(etat.get("motif") or "")


def reprendre(outbox: Outbox, h2, *, h1=None, chemin: str = "/api/retours",
              maintenant: Optional[float] = None) -> list:
    """Relance les envois en attente dont l'heure de reprise est passée.

    Si `h1` est fourni, le consentement est revérifié avant chaque reprise (loi 09-08) :
    un retrait survenu depuis la mise en file annule l'envoi.
    """
    now = time.time() if maintenant is None else maintenant
    resultats = []
    for ligne in outbox.a_reprendre(now):
        if h1 is not None:
            autorise, motif = partage_toujours_autorise(h1, ligne["patient_id"])
            if autorise is False:
                detail = f"Envoi annulé : {motif} (loi 09-08)."
                outbox.maj(ligne["id"], now, statut="annule", derniere_erreur=detail)
                resultats.append(_resultat(outbox, ligne["id"], "annule", None, detail))
                continue
            if autorise is None:                     # dans le doute, rien ne part
                outbox.maj(ligne["id"], now, derniere_erreur=motif, prochaine=now + DELAIS_REPRISE[0])
                resultats.append(_resultat(outbox, ligne["id"], "en_attente", None, motif))
                continue
        resultats.append(tenter(outbox, ligne["id"], h2, chemin=chemin, maintenant=now))
    return resultats


def _principal(argv: list[str]) -> int:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    if not argv or argv[0] not in {"envoyer", "reprendre", "etat"} or (argv[0] == "envoyer" and len(argv) != 2):
        print(__doc__.split("Ligne de commande")[1])
        return 2
    outbox = Outbox(os.getenv("H1_FILE_ENVOI") or "file_envoi_h1.sqlite3")
    if argv[0] == "etat":
        for l in outbox.lister():
            print(dict(l))
        return 0
    with client_h2() as h2, client_local() as h1:
        if argv[0] == "envoyer":
            res = envoyer_dossier(argv[1], h1, h2, outbox)
            print(res)
            return 0 if res["statut"] in {"envoye", "en_attente"} else 1
        for res in reprendre(outbox, h2, h1=h1):
            print(res)
    return 0


if __name__ == "__main__":
    sys.exit(_principal(sys.argv[1:]))
