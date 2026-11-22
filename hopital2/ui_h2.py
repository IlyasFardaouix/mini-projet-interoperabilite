"""Adaptateur de l'interface web pour H2 (Clinique Al Bacar, MongoDB).

Memes services que hopital1/ui_h1.py. Le serveur envoie avec les jetons de SON environnement
(H1_API_TOKEN : jeton du client h2-clinique chez H1 ; H2_JETON_LOCAL : jeton h2-interne pour
l'export de sa propre API) ; le navigateur ne les voit jamais.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

import echange
from client_envoi import Outbox, client_h1, envoyer_dossier, reprendre
from interface import ErreurInterface
from interface.demo import lire_reponse_bundle, resume_consentement
from stores import StoreIndisponible

SEXES = {1: "M", 2: "F"}
TYPES_VISITE = {1: "Urgence", 2: "Consultation", 3: "Hospitalisation"}


def _iso(valeur):
    return valeur.isoformat(sep=" ", timespec="minutes") if hasattr(valeur, "isoformat") else valeur


def _resume(doc):
    return {"id": doc["patient_id"], "nom": doc.get("last_name"), "prenom": doc.get("first_name"),
            "sexe": SEXES.get(doc.get("sex")), "date_naissance": doc.get("birth_date"),
            "cin": doc.get("national_id")}


def client_local():
    """Client vers l'API de H2 elle-meme (export du Bundle, etat du consentement)."""
    from securite import client_securise
    return client_securise(os.getenv("H2_BASE_URL") or "https://127.0.0.1:8002",
                           variable_jeton="H2_JETON_LOCAL")


class AdaptateurH2:
    etablissement, autre, autre_etablissement = "Clinique Al Baçar", "H1", "CHU Al Massira"

    def __init__(self, store):
        self._store = store             # fonction sans argument : le magasin courant (testable)

    # -- consultation --------------------------------------------------------------
    def rechercher(self, texte, limite=50):
        try:
            docs = self._store().all(1000)
        except StoreIndisponible as exc:
            raise ErreurInterface(503, "Base indisponible.", "transient") from exc
        t = texte.lower()
        trouves = [d for d in docs if not t or any(
            t in str(d.get(c) or "").lower() for c in ("last_name", "first_name", "national_id", "patient_id"))]
        trouves.sort(key=lambda d: (str(d.get("last_name")), str(d.get("first_name"))))
        return [_resume(d) for d in trouves[:limite]]

    def dossier(self, identifiant):
        try:
            doc = echange.trouver_patient(self._store(), identifiant)
        except echange.ErreurEchange as exc:
            raise LookupError(identifiant) from exc
        except StoreIndisponible as exc:
            raise ErreurInterface(503, "Base indisponible.", "transient") from exc
        adresse = doc.get("address") or {}
        res = _resume(doc)
        res.update(telephone=doc.get("phone"), groupe_sanguin=doc.get("blood_type"),
                   adresse=", ".join(x for x in (adresse.get("street"), adresse.get("city")) if x))
        sejours = []
        for v in doc.get("visits", []):
            sejours.append({
                "id": v.get("visit_id"), "type": TYPES_VISITE.get(v.get("visit_type")),
                "service": v.get("department"), "debut": _iso(v.get("admitted_at")),
                "fin": _iso(v.get("discharged_at")), "medecin": v.get("physician"), "motif": v.get("reason"),
                "origine": v.get("_origin"),
                "diagnostics": [{"libelle": c.get("label"), "code": c.get("code")}
                                for c in v.get("conditions", [])],
                "mesures": [{"libelle": o.get("label"), "valeur": o.get("value"), "unite": o.get("unit"),
                             "date": _iso(o.get("at"))} for o in v.get("observations", [])],
                "examens": [{"libelle": i.get("description"), "detail": i.get("modality")}
                            for i in v.get("imaging", [])]
                           + [{"libelle": r.get("code_label"), "detail": r.get("conclusion")}
                              for r in v.get("reports", [])]
                           + [{"libelle": s.get("code_label"), "detail": "demande : " + str(s.get("status"))}
                              for s in v.get("service_requests", [])],
            })
        return {"service": "H2", "patient": res,
                "allergies": [{"libelle": a.get("substance"), "detail": a.get("reaction"),
                               "gravite": a.get("criticite")} for a in doc.get("allergies", [])],
                "sejours": sejours, "recu_de_l_autre_hopital": {}}

    # -- envoi vers le CHU -----------------------------------------------------------------
    def _file(self):
        return Outbox(os.getenv("H2_FILE_ENVOI") or "file_envoi_h2.sqlite3")

    def envoyer(self, identifiant):
        try:
            with client_local() as h2, client_h1() as h1:
                return envoyer_dossier(identifiant, h2, h1, self._file())
        except ValueError as exc:
            raise ErreurInterface(503, "Envoi non configure : " + str(exc), "transient") from exc

    def lister_envois(self):
        lignes = self._file().db.execute(
            "SELECT id, patient_id, echange_id, statut, tentatives, code_http, derniere_erreur, "
            "prochaine, cree_le, maj_le FROM envois ORDER BY id DESC LIMIT 100").fetchall()
        return [dict(l) for l in lignes]

    def reprendre(self, forcer=False):
        file = self._file()
        maintenant = time.time()
        if forcer:
            file.db.execute("UPDATE envois SET prochaine = ? WHERE statut = 'en_attente'", (maintenant,))
            file.db.commit()
        try:
            with client_local() as h2, client_h1() as h1:
                return reprendre(file, h1, h2=h2, maintenant=maintenant)
        except ValueError as exc:
            raise ErreurInterface(503, "Reprise non configuree : " + str(exc), "transient") from exc

    # -- demonstration (interface/demo.py) ---------------------------------------------------
    def consentement(self, identifiant):
        try:
            return resume_consentement(echange.lire_consentement(self._store(), identifiant))
        except echange.ErreurEchange as exc:
            raise LookupError(identifiant) from exc
        except StoreIndisponible as exc:
            raise ErreurInterface(503, "Base indisponible.", "transient") from exc

    def consentements(self, identifiants):
        sortie = {}
        for ident in identifiants:
            try:
                sortie[ident] = self.consentement(ident)
            except LookupError:
                sortie[ident] = None
        return sortie

    def definir_consentement(self, identifiant, statut):
        """statut : actif | refuse | retire. Une nouvelle version est ajoutee, rien n'est ecrase."""
        try:
            if statut == "retire":
                etat = echange.retirer_consentement(self._store(), identifiant,
                                                    {"recueilli_par": "demo", "motif": "demonstration"}, agent="demo")
            else:
                etat = echange.enregistrer_consentement(self._store(), identifiant,
                                                        {"statut": statut, "recueilli_par": "demo"}, agent="demo")
        except echange.ErreurEchange as exc:
            if exc.code == 404:
                raise LookupError(identifiant) from exc
            raise ErreurInterface(exc.code, exc.message, exc.type_fhir) from exc
        except StoreIndisponible as exc:
            raise ErreurInterface(503, "Base indisponible.", "transient") from exc
        return resume_consentement(etat)

    def envoyes(self, limite=50):
        """Dernier envoi de chaque patient (file d'attente locale)."""
        lignes = self._file().db.execute(
            "SELECT patient_id, statut, tentatives, derniere_erreur, maj_le FROM envois "
            "WHERE id IN (SELECT MAX(id) FROM envois GROUP BY patient_id) ORDER BY id DESC LIMIT ?",
            (int(limite),)).fetchall()
        return [{"patient": l["patient_id"], "statut": l["statut"], "tentatives": l["tentatives"],
                 "detail": l["derniere_erreur"],
                 "quand": datetime.fromtimestamp(l["maj_le"]).isoformat(sep=" ", timespec="minutes")} for l in lignes]

    def recus(self, limite=30):
        """Patients pour lesquels la clinique a recu un dossier du CHU (journal d'acces du patient)."""
        try:
            docs = self._store().all(1000)
        except StoreIndisponible as exc:
            raise ErreurInterface(503, "Base indisponible.", "transient") from exc
        trouves = []
        for d in docs:
            recu = [a for a in d.get("_audit_log", []) if a.get("event_type") == "Réception d'un dossier (Bundle)"]
            if recu:
                dernier = max(str(a.get("recorded_at") or "") for a in recu)
                trouves.append({"patient": d["patient_id"], "quand": _iso(dernier)[:16].replace("T", " "), "n": len(recu)})
        trouves.sort(key=lambda x: x["quand"], reverse=True)
        return trouves[:limite]

    def apercu_bundle(self, identifiant):
        try:
            with client_local() as h2:
                return lire_reponse_bundle(h2.get(f"/api/patients/{identifiant}/bundle"))
        except ValueError as exc:
            raise ErreurInterface(503, "Apercu non configure : " + str(exc), "transient") from exc
        except httpx.TransportError as exc:
            raise ErreurInterface(503, "API de la clinique injoignable.", "transient") from exc
