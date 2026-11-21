"""
client_envoi.py — envoie un dossier de H2 vers l'API de H1, avec file d'attente et reprise
=========================================================================================
Ce n'est PAS une route ni une commande autonome : c'est un module destiné à
être appelé par l'orchestrateur de l'échange entre les deux API.

  1. demande le Bundle à l'API H2           GET  /api/patients/{id}/bundle   (403 = consentement refusé : on s'arrête)
  2. teste chez H1 à blanc                  POST /api/retours/simulation     (refus définitif : on s'arrête)
  3. met le Bundle dans la FILE D'ATTENTE   (base SQLite : survit à un redémarrage)
  4. tente l'envoi                          POST /api/retours  + en-tête X-Exchange-Id
  5. selon la réponse :
        200 / 201                   → « envoye »
        injoignable, 408, 429, 5xx  → « en_attente » : on réessaiera plus tard (1 min, 5 min, 30 min, 2 h, 6 h)
        autre 4xx (403, 409, 422…)  → « echec » : réessayer ne servirait à rien, une personne doit regarder
  6. reprendre() relance les envois en attente. Le Bundle et l'identifiant d'échange sont ceux du premier essai :
     si H1 avait en fait bien reçu l'envoi, le rejeu ne crée aucun doublon.
     Avec le client H2 (reprendre(..., h2=...)), le consentement est revérifié avant chaque reprise :
     retiré ou expiré → « annule » ; impossible à vérifier → l'envoi attend, rien ne part.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

DELAIS_REPRISE = (60, 300, 1800, 7200, 21600)      # secondes
MAX_TENTATIVES = 6
CODES_A_REESSAYER = {408, 425, 429, 500, 502, 503, 504}
ENTETES = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json, application/json"}


def client_h1(base_url: Optional[str] = None):
    """Client HTTP durci pour appeler l'API de H1.

    Les fonctions ci-dessous attendent un `httpx.Client` deja configure. Celui
    que renvoie cette fabrique vient de la couche de securite commune, qui pose
    les quatre reglages faciles a oublier : verification du certificat du
    serveur, delais d'attente, pas de suivi des redirections (une redirection
    rejouerait l'en-tete Authorization sur l'adresse cible) et jeton lu dans
    l'environnement plutot qu'ecrit en dur.

    Variables utilisees : `H1_BASE_URL` (adresse de l'API de H1) et
    `H1_API_TOKEN` (jeton remis par le CHU, hors depot Git).
    """
    _racine = Path(__file__).resolve().parent.parent
    if str(_racine) not in sys.path:
        sys.path.insert(0, str(_racine))
    from securite import client_securise

    return client_securise(base_url or os.getenv("H1_BASE_URL", "https://127.0.0.1:8000"),
                           variable_jeton="H1_API_TOKEN")


class Outbox:
    """File d'attente des envois (SQLite)."""

    def __init__(self, chemin: str = ":memory:"):
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
            (patient_id, echange_id, bundle_json, maintenant, maintenant, maintenant))
        self.db.commit()
        return cur.lastrowid

    def get(self, envoi_id: int) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM envois WHERE id = ?", (envoi_id,)).fetchone()

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


def tenter(outbox: Outbox, envoi_id: int, h1, *, chemin: str = "/api/retours",
           maintenant: Optional[float] = None) -> dict:
    """Une tentative d'envoi. `h1` = httpx.Client (ou équivalent) déjà configuré avec base_url et jeton."""
    now = time.time() if maintenant is None else maintenant
    ligne = outbox.get(envoi_id)
    n = ligne["tentatives"] + 1
    try:
        rep = h1.post(chemin, content=ligne["bundle"], headers={**ENTETES, "X-Exchange-Id": ligne["echange_id"]})
    except httpx.TransportError as exc:                       # injoignable, délai dépassé…
        return _temporaire(outbox, ligne, n, now, None, f"H1 injoignable ({exc.__class__.__name__})")

    if rep.status_code in (200, 201):
        outbox.maj(envoi_id, now, statut="envoye", tentatives=n, code_http=rep.status_code, derniere_erreur=None)
        return _resultat(outbox, envoi_id, "envoye", rep.status_code, "Envoi confirmé par H1.")
    if rep.status_code in CODES_A_REESSAYER:
        return _temporaire(outbox, ligne, n, now, rep.status_code, _resume(rep))
    outbox.maj(envoi_id, now, statut="echec", tentatives=n, code_http=rep.status_code, derniere_erreur=_resume(rep))
    return _resultat(outbox, envoi_id, "echec", rep.status_code, _resume(rep))


def _temporaire(outbox, ligne, n, now, code, message) -> dict:
    if n >= MAX_TENTATIVES:
        outbox.maj(ligne["id"], now, statut="echec", tentatives=n, code_http=code,
                   derniere_erreur=f"Abandon après {n} tentatives. Dernière erreur : {message}")
        return _resultat(outbox, ligne["id"], "echec", code, f"Abandon après {n} tentatives : {message}")
    delai = DELAIS_REPRISE[min(n - 1, len(DELAIS_REPRISE) - 1)]
    outbox.maj(ligne["id"], now, statut="en_attente", tentatives=n, code_http=code,
               derniere_erreur=message, prochaine=now + delai)
    return _resultat(outbox, ligne["id"], "en_attente", code, f"{message} — nouvelle tentative dans {delai} s.")


def _resultat(outbox: Outbox, envoi_id: int, statut: str, http: Optional[int], detail: str) -> dict:
    ligne = outbox.get(envoi_id)
    return {"statut": statut, "http": http, "detail": detail, "envoi_id": envoi_id,
            "tentatives": ligne["tentatives"], "echange_id": ligne["echange_id"]}


def envoyer_dossier(patient_id: str, h2, h1, outbox: Outbox, *, chemin_reception: str = "/api/retours",
                    simuler_avant: bool = True, maintenant: Optional[float] = None) -> dict:
    """Exporte le dossier depuis l'API H2, le teste chez H1, le met en file puis tente l'envoi."""
    now = time.time() if maintenant is None else maintenant

    rep = h2.get(f"/api/patients/{patient_id}/bundle")
    if rep.status_code == 403:
        return {"statut": "bloque", "http": 403, "detail": _resume(rep)}      # consentement : rien n'est envoyé
    if rep.status_code != 200:
        return {"statut": "export_impossible", "http": rep.status_code, "detail": _resume(rep)}
    bundle = rep.json()
    echange_id = bundle["identifier"]["value"]

    if simuler_avant:
        try:
            sim = h1.post(f"{chemin_reception}/simulation", content=rep.content,
                          headers={**ENTETES, "X-Exchange-Id": echange_id})
        except httpx.TransportError:
            sim = None                                       # H1 injoignable : on met en file, la reprise réessaiera
        if sim is not None and sim.status_code not in (200, 201) and sim.status_code not in CODES_A_REESSAYER:
            return {"statut": "refuse_simulation", "http": sim.status_code, "detail": _resume(sim)}

    envoi_id = outbox.ajouter(patient_id, echange_id, rep.text, now)
    return tenter(outbox, envoi_id, h1, chemin=chemin_reception, maintenant=now)


def partage_toujours_autorise(h2, patient_id: str) -> tuple[Optional[bool], str]:
    """(True | False | None, motif) d'après GET /api/patients/{id}/consentement.
    None : la vérification n'a pas pu se faire (H2 injoignable, portée manquante…)."""
    try:
        rep = h2.get(f"/api/patients/{patient_id}/consentement")
    except httpx.TransportError as exc:
        return None, f"consentement non vérifiable (H2 injoignable : {exc.__class__.__name__})"
    if rep.status_code != 200:
        return None, f"consentement non vérifiable (HTTP {rep.status_code})"
    etat = rep.json()
    return bool(etat.get("partage_autorise")), str(etat.get("motif") or "")


def reprendre(outbox: Outbox, h1, *, h2=None, chemin: str = "/api/retours",
              maintenant: Optional[float] = None) -> list:
    """Relance les envois en attente dont l'heure de reprise est passée.

    Si `h2` est fourni, le consentement est revérifié avant chaque reprise (loi 09-08) :
    un retrait survenu depuis la mise en file annule l'envoi.
    """
    now = time.time() if maintenant is None else maintenant
    resultats = []
    for ligne in outbox.a_reprendre(now):
        if h2 is not None:
            autorise, motif = partage_toujours_autorise(h2, ligne["patient_id"])
            if autorise is False:
                detail = f"Envoi annulé : {motif} (loi 09-08)."
                outbox.maj(ligne["id"], now, statut="annule", derniere_erreur=detail)
                resultats.append(_resultat(outbox, ligne["id"], "annule", None, detail))
                continue
            if autorise is None:                     # dans le doute, rien ne part
                outbox.maj(ligne["id"], now, derniere_erreur=motif,
                           prochaine=now + DELAIS_REPRISE[0])
                resultats.append(_resultat(outbox, ligne["id"], "en_attente", None, motif))
                continue
        resultats.append(tenter(outbox, ligne["id"], h1, chemin=chemin, maintenant=now))
    return resultats
