"""Adaptateur de l'interface web pour H1 (CHU Al Massira, Oracle).

Rend au module commun `interface` : la recherche, un dossier lisible, et l'envoi a la clinique
par la file d'attente de `client_envoi_h1`. Le serveur utilise les jetons de SON environnement
(H1_JETON_VERS_H2, H1_JETON_LOCAL) : le navigateur ne les voit jamais.
"""

import os
import time
from datetime import datetime

import httpx
import oracledb

import oracle_repo as repo
from client_envoi_h1 import Outbox, client_h2, client_local, envoyer_dossier, reprendre
from interface import ErreurInterface
from interface.demo import lire_reponse_bundle, resume_consentement


def _iso(valeur):
    return valeur.isoformat(sep=" ", timespec="minutes") if hasattr(valeur, "isoformat") else valeur


def _instance_pacs(pacs, study_uid, rang):
    """`rang`-ieme instance d'une etude du PACS local, ou l'erreur d'interface qui convient."""
    from imagerie.dicomweb import ErreurPacs
    if pacs is None:
        raise ErreurInterface(503, "PACS non configure (ORTHANC_URL).", "transient")
    try:
        instances = pacs.etude(study_uid)
    except ErreurPacs as exc:
        raise ErreurInterface(503, str(exc), "transient") from exc
    if not instances or not 0 <= rang < len(instances):
        raise LookupError(study_uid)
    return instances[rang]


class AdaptateurH1:
    etablissement, autre, autre_etablissement = "CHU Al Massira", "H2", "Clinique Al Baçar"

    # -- consultation --------------------------------------------------------------
    def rechercher(self, texte, limite=50):
        try:
            with repo.connexion() as conn:
                lignes = repo.rechercher_patients(conn, texte, limite)
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc
        return [{"id": p["ipp"], "nom": p["nom"], "prenom": p["prenom"], "sexe": p.get("sexe"),
                 "date_naissance": _iso(p.get("date_naissance")), "cin": p.get("cin")} for p in lignes]

    def dossier(self, identifiant):
        try:
            with repo.connexion() as conn:
                d = repo.lire_dossier(conn, ipp=identifiant) or repo.lire_dossier(conn, cin=identifiant)
                if d is None:
                    raise LookupError(identifiant)
                recus = repo.lire_recus(conn, d["patient"]["ipp"])
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc
        p = d["patient"]
        return {
            "service": "H1",
            "patient": {"id": p["ipp"], "nom": p["nom"], "prenom": p["prenom"], "sexe": p.get("sexe"),
                        "date_naissance": _iso(p.get("date_naissance")), "cin": p.get("cin"),
                        "telephone": p.get("telephone"),
                        "adresse": ", ".join(x for x in (p.get("adresse"), p.get("ville")) if x),
                        "groupe_sanguin": p.get("groupe_sanguin")},
            "allergies": [{"libelle": a.get("libelle"), "detail": a.get("code_allergene"),
                           "gravite": a.get("criticite")} for a in d.get("allergies", [])],
            "sejours": [{
                "id": s["id_sejour"], "type": s.get("type_sejour"), "service": s.get("service"),
                "debut": _iso(s.get("date_admission")), "fin": _iso(s.get("date_sortie")),
                "medecin": s.get("medecin"), "motif": s.get("motif"),
                "origine": s.get("etablissement") if s.get("id_externe") else None,
                "diagnostics": [{"libelle": x.get("libelle"), "code": x.get("code_local")}
                                for x in s.get("diagnostics", [])],
                "mesures": [{"libelle": m.get("code_local"), "valeur": m.get("valeur"),
                             "unite": m.get("unite"), "date": _iso(m.get("date_mesure"))}
                            for m in s.get("mesures", [])],
            } for s in d.get("sejours", [])],
            "recu_de_l_autre_hopital": {t: [{k: _iso(v) for k, v in l.items()} for l in lignes]
                                        for t, lignes in recus.items() if lignes},
            "imagerie": [{"study_uid": e.get("study_uid"), "description": e.get("description"),
                          "modalite": e.get("modalites"), "instances": e.get("nb_instances"),
                          "statut": e.get("statut"), "pret": e.get("statut") == "RECUPEREE"}
                         for e in recus.get("etude_imagerie", []) if e.get("study_uid")],
        }

    def _pacs(self):
        from imagerie.dicomweb import entrepot_depuis_env
        return entrepot_depuis_env("H1")

    def image_dicom(self, identifiant, study_uid, rang):
        """Octets DICOM de la `rang`-ieme image d'une etude RECUE ET RECUPEREE pour ce patient."""
        try:
            with repo.connexion() as conn:
                etudes = repo.lire_recus(conn, identifiant).get("etude_imagerie", [])
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc
        etude = next((x for x in etudes if x.get("study_uid") == study_uid), None)
        if etude is None:
            raise LookupError(study_uid)
        if etude.get("statut") != "RECUPEREE":
            raise ErreurInterface(404, "Images pas encore recuperees depuis la clinique.", "not-found")
        return _instance_pacs(self._pacs(), study_uid, rang)

    # -- envoi vers la clinique ---------------------------------------------------------
    def _file(self):
        return Outbox(os.getenv("H1_FILE_ENVOI") or "file_envoi_h1.sqlite3")

    def envoyer(self, identifiant):
        try:
            with client_h2() as h2, client_local() as h1:
                return envoyer_dossier(identifiant, h1, h2, self._file())
        except ValueError as exc:       # jeton absent : message de securite/client.py
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
            with client_h2() as h2, client_local() as h1:
                return reprendre(file, h2, h1=h1, maintenant=maintenant)
        except ValueError as exc:
            raise ErreurInterface(503, "Reprise non configuree : " + str(exc), "transient") from exc

    # -- demonstration (interface/demo.py) ---------------------------------------------------
    def consentement(self, identifiant):
        try:
            with repo.connexion() as conn:
                return resume_consentement(
                    repo.etat_consentement(identifiant, repo.lire_consentements(conn, identifiant)))
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc

    def consentements(self, identifiants):
        """Consentement de plusieurs patients avec UNE connexion Oracle (ouvrir une connexion coute cher)."""
        sortie = {}
        try:
            with repo.connexion() as conn:
                for ipp in identifiants:
                    try:
                        sortie[ipp] = resume_consentement(repo.etat_consentement(ipp, repo.lire_consentements(conn, ipp)))
                    except LookupError:
                        sortie[ipp] = None
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc
        return sortie

    def definir_consentement(self, identifiant, statut):
        """statut : actif | refuse | retire. Une nouvelle version est ajoutee, rien n'est ecrase."""
        try:
            with repo.connexion() as conn:
                if statut == "retire":
                    etat = repo.retirer_consentement(conn, identifiant, {"recueilli_par": "demo", "motif": "demonstration"},
                                                     agent="demo")
                else:
                    etat = repo.enregistrer_consentement(conn, identifiant, {"statut": statut, "recueilli_par": "demo"},
                                                         agent="demo")
        except repo.ConsentementSansObjet as exc:
            raise ErreurInterface(409, str(exc), "conflict") from exc
        except repo.CONS.ConsentementInvalide as exc:
            raise ErreurInterface(422, str(exc), "invalid") from exc
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc
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
        """Patients pour lesquels le CHU a accepte des donnees de la clinique."""
        try:
            with repo.connexion() as conn:
                lignes = repo.lister_retours(conn, limite)
        except oracledb.DatabaseError as exc:
            raise ErreurInterface(503, "Base Oracle indisponible.", "transient") from exc
        return [{"patient": l["ipp"], "quand": _iso(l.get("dernier")), "n": l.get("n")} for l in lignes]

    def apercu_bundle(self, identifiant):
        try:
            with client_local() as h1:
                return lire_reponse_bundle(h1.get(f"/api/patients/{identifiant}/bundle"))
        except ValueError as exc:
            raise ErreurInterface(503, "Apercu non configure : " + str(exc), "transient") from exc
        except httpx.TransportError as exc:
            raise ErreurInterface(503, "API du CHU injoignable.", "transient") from exc
