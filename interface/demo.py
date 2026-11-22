"""Mode demonstration : une page sans compte pour montrer l'echange de bout en bout.

    DEMO=1   active la page /ui/demo.html et les routes /api/demo/*

Ce que fait la page : choisir un patient, voir et changer son consentement, cliquer sur
« Envoyer », puis suivre l'echange etape par etape. Les etapes sont deduites de la VRAIE
reponse du circuit d'envoi (export, controle, envoi), rien n'est simule.

Garde-fous : desactive par defaut (404), reserve aux appels venant de CE poste (boucle
locale). La page montre le dossier et le contenu du Bundle : donnees de test uniquement.
Le navigateur ne recoit toujours aucun jeton : l'envoi est fait par le serveur.

Pas de `from __future__ import annotations` : FastAPI doit voir les vraies classes.
"""

import json
import logging
import os
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

JOURNAL = logging.getLogger("uvicorn.error")
HOTES_LOCAUX = {"127.0.0.1", "::1", "localhost", "testclient"}
STATUTS = ("actif", "refuse", "retire")
LIBELLES = {"actif": "accord", "refuse": "refus", "retire": "retrait", "aucun": "aucun consentement"}


def resume_consentement(etat: dict) -> dict:
    """Forme commune aux deux hopitaux, a partir de `etat_consentement`."""
    actuel = etat.get("actuel") or {}
    return {"statut": str(actuel.get("statut") or "aucun").lower(), "partage": bool(etat.get("partage_autorise")),
            "motif": etat.get("motif") or ""}


def _texte_ressource(r: dict) -> str:
    """Une ligne lisible pour une ressource FHIR (sans interpreter le contenu : texte seulement)."""
    def code(c):
        if not isinstance(c, dict):
            return ""
        return c.get("text") or next((x.get("display") or x.get("code") for x in c.get("coding") or []
                                      if isinstance(x, dict) and (x.get("display") or x.get("code"))), "") or ""
    t = r.get("resourceType")
    if t == "Patient":
        n = (r.get("name") or [{}])[0]
        return " ".join([*(n.get("given") or []), str(n.get("family") or "")]).strip()
    if t == "Observation":
        v = r.get("valueQuantity") or {}
        val = (" : " + " ".join(str(x) for x in (v.get("value"), v.get("unit")) if x is not None)) if v else ""
        return code(r.get("code")) + val
    if t == "Consent":
        return "consentement " + str(r.get("status") or "")
    if t == "Encounter":
        return code((r.get("type") or [{}])[0]) or str((r.get("class") or [{}])[0].get("display") or "")
    return code(r.get("code")) or code(r.get("type")) or str(r.get("description") or r.get("name") or "")


def resumer_bundle(bundle: dict) -> dict:
    """Contenu d'un Bundle pour l'ecran : nombre de ressources par type, et chaque ressource (texte + JSON)."""
    entrees = []
    comptes: dict = {}
    for e in (bundle.get("entry") or []):
        r = (e or {}).get("resource") or {}
        t = str(r.get("resourceType") or "?")
        comptes[t] = comptes.get(t, 0) + 1
        entrees.append({"type": t, "id": str(r.get("id") or ""), "resume": _texte_ressource(r)[:160],
                        "methode": str(((e or {}).get("request") or {}).get("method") or ""),
                        "json": json.dumps(r, ensure_ascii=False, indent=2, default=str)})
    return {"disponible": True, "type": str(bundle.get("type") or ""), "total": len(entrees),
            "comptes": [{"type": k, "n": v} for k, v in sorted(comptes.items(), key=lambda kv: (-kv[1], kv[0]))],
            "entrees": entrees}


def lire_reponse_bundle(reponse) -> dict:
    """Reponse de GET /api/patients/{id}/bundle -> `resumer_bundle`, ou le motif de l'indisponibilite."""
    if reponse.status_code == 200:
        return resumer_bundle(reponse.json())
    try:
        motif = reponse.json()["issue"][0]["diagnostics"]
    except Exception:
        motif = "HTTP %d" % reponse.status_code
    return {"disponible": False, "http": reponse.status_code, "motif": motif}


def _json(contenu, code: int = 200) -> Response:
    return Response(json.dumps(contenu, ensure_ascii=False, default=str), status_code=code,
                    media_type="application/json", headers={"Cache-Control": "no-store"})


def exiger_demo(requete: Request) -> None:
    """404 si la demo n'est pas activee (elle n'existe pas), 403 hors du poste local."""
    if os.getenv("DEMO") != "1":
        raise HTTPException(404, "Mode demonstration desactive.")
    hote = requete.client.host if requete.client else ""
    if hote not in HOTES_LOCAUX:
        raise HTTPException(403, "Mode demonstration reserve au poste local.")


def etape_images(imagerie) -> tuple:
    """(etat, texte) de l'etape « Images DICOM » a partir du bilan renvoye par l'autre hopital."""
    if imagerie is None:
        return "ok", "Aucune image transférée avec cet envoi."
    if not imagerie:
        return "ok", "Aucune image dans ce dossier."
    recues = [i for i in imagerie if i.get("statut") == "RECUPEREE"]
    images = sum(int(i.get("instances") or 0) for i in recues)
    refusees = [i for i in imagerie if i.get("statut") in ("REFUSEE", "URL_REFUSEE", "INCOHERENTE", "ABSENTE")]
    attente = [i for i in imagerie if i.get("statut") == "EN_ATTENTE"]
    morceaux = []
    if recues:
        morceaux.append(f"{len(recues)} examen(s) transféré(s), {images} image(s)")
    if refusees:
        morceaux.append(f"{len(refusees)} refusé(s) (imagerie exclue par le patient, ou examen introuvable)")
    if attente:
        morceaux.append(f"{len(attente)} en attente (PACS ou passerelle indisponible, à relancer)")
    etat = "attente" if attente and not recues else "echec" if refusees and not recues else "ok"
    return etat, " ; ".join(morceaux) + "."


def etapes_envoi(resultat: dict, consentement: dict, autre: str) -> tuple:
    """(etapes, verdict) a partir du resultat reel de `envoyer_dossier`."""
    statut, http = resultat.get("statut"), resultat.get("http")
    detail = str(resultat.get("detail") or "")
    noms = ["Consentement du patient", "Dossier converti en Bundle FHIR",
            f"Pré-vérification par {autre} (rien n'est enregistré)", f"Envoi et import chez {autre}",
            "Images DICOM"]
    etats = ["saute"] * 5
    textes = [""] * 5
    if statut == "bloque":
        etats[0], textes[0] = "echec", "Refusé : " + (consentement.get("motif") or "consentement non actif") + "."
        verdict = ("bloque", "Bloqué : rien n'a quitté l'hôpital",
                   "Sans consentement actif, le dossier n'est pas exporté (loi 09-08).")
    else:
        etats[0], textes[0] = "ok", "Partage autorisé."
        if statut == "export_impossible":
            etats[1], textes[1] = "echec", detail or "Export impossible."
            verdict = ("echec", "Échec avant l'envoi", detail)
        else:
            etats[1], textes[1] = "ok", "Bundle FHIR R5 construit."
            if statut == "refuse_simulation" and "not-found" in detail:
                etats[2], textes[2] = "echec", detail
                verdict = ("echec", f"Patient inconnu chez {autre} : rien n'est transféré",
                           f"{autre} n'accepte un retour que pour un patient déjà enregistré chez lui "
                           "(rapprochement d'identité). Aucun doublon n'est créé.")
            elif statut == "refuse_simulation":
                etats[2], textes[2] = "echec", detail
                verdict = ("echec", f"Refusé par {autre} lors du contrôle", detail)
            else:
                if statut == "en_attente" and http is None:
                    etats[2], textes[2] = "attente", f"{autre} ne répond pas : contrôle impossible."
                else:
                    etats[2], textes[2] = "ok", f"{autre} a vérifié le Bundle : il est conforme."
                if statut == "envoye":
                    etats[3], textes[3] = "ok", "Importé, envoi confirmé."
                    etats[4], textes[4] = etape_images(resultat.get("imagerie"))
                    verdict = ("ok", f"Transmis à {autre}", "Le dossier est maintenant dans la base de l'autre hôpital.")
                elif statut == "en_attente":
                    etats[3], textes[3] = "attente", detail
                    verdict = ("attente", "Mis en file d'attente",
                               f"{autre} n'est pas joignable. L'envoi sera retenté, sans perte.")
                else:
                    etats[3], textes[3] = "echec", detail
                    verdict = ("echec", f"Refusé par {autre}", detail)
    return ([{"nom": n, "etat": e, "texte": t} for n, e, t in zip(noms, etats, textes)],
            {"etat": verdict[0], "titre": verdict[1], "detail": verdict[2]})


def installer_demo(app, *, service: str, adaptateur) -> None:
    from interface.routes import ErreurInterface

    routeur = APIRouter(tags=["Demonstration"], include_in_schema=False)
    garde = [Depends(exiger_demo)]

    def erreur(exc: "ErreurInterface") -> Response:
        return _json({"erreur": exc.message}, exc.code)

    def envoyes() -> list:
        try:
            return adaptateur.envoyes(50)
        except Exception:                                    # file absente : aucun envoi encore
            return []

    def en_attente() -> int:
        try:
            return sum(1 for e in adaptateur.lister_envois() if e.get("statut") == "en_attente")
        except Exception:                                    # file absente : pas d'envoi encore
            return 0

    @routeur.get("/api/demo/patients", dependencies=garde)
    def patients():
        try:
            liste = adaptateur.rechercher("", 100)
            etats = adaptateur.consentements([p["id"] for p in liste])     # une seule connexion
        except ErreurInterface as exc:
            return erreur(exc)
        sortie = [{"id": p["id"], "nom": p.get("nom"), "prenom": p.get("prenom"),
                   "consentement": etats.get(p["id"])} for p in liste]
        try:
            recus = adaptateur.recus(50)
        except ErreurInterface:
            recus = []
        return _json({"service": service, "etablissement": adaptateur.etablissement,
                      "autre": adaptateur.autre, "autre_etablissement": adaptateur.autre_etablissement,
                      "patients": sortie, "envoyes": envoyes(), "recus": recus, "en_attente": en_attente()})

    @routeur.get("/api/demo/patient/{identifiant}", dependencies=garde)
    def detail(identifiant: str):
        """Informations du patient et contenu du Bundle FHIR qui serait envoye (apercu local)."""
        t0 = time.perf_counter()
        try:
            dossier = adaptateur.dossier(identifiant)
        except LookupError:
            return _json({"erreur": "Patient introuvable."}, 404)
        except ErreurInterface as exc:
            return erreur(exc)
        try:
            bundle = adaptateur.apercu_bundle(identifiant)
        except ErreurInterface as exc:
            bundle = {"disponible": False, "motif": exc.message}
        JOURNAL.info("demo : detail %s (%d ms)", service, (time.perf_counter() - t0) * 1000)
        return _json({"dossier": dossier, "bundle": bundle})

    @routeur.get("/api/demo/image/{identifiant}/{study_uid}/{rang}", dependencies=garde)
    def image(identifiant: str, study_uid: str, rang: int):
        """Apercu PNG d'une image DICOM du patient. Le serveur lit le PACS local : le navigateur ne recoit
        qu'une image (aucune etiquette DICOM, donc ni nom ni date de naissance)."""
        from imagerie.apercu import ErreurApercu, png_depuis_dicom
        if not re.fullmatch(r"[0-9.]{1,64}", study_uid) or not 0 <= rang < 200:
            return _json({"erreur": "Identifiant d'etude invalide."}, 422)
        try:
            octets = adaptateur.image_dicom(identifiant, study_uid, rang)
            png = png_depuis_dicom(octets)
        except LookupError:
            return _json({"erreur": "Image introuvable."}, 404)
        except ErreurApercu as exc:
            return _json({"erreur": "Apercu indisponible : " + str(exc)}, 415)
        except ErreurInterface as exc:
            return erreur(exc)
        return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

    @routeur.post("/api/demo/consentement/{identifiant}/{statut}", dependencies=garde)
    def consentement(identifiant: str, statut: str):
        if statut not in STATUTS:
            return _json({"erreur": "Choix inconnu : " + statut}, 422)
        try:
            etat = adaptateur.definir_consentement(identifiant, statut)
        except LookupError:
            return _json({"erreur": "Patient introuvable."}, 404)
        except ErreurInterface as exc:
            return erreur(exc)
        JOURNAL.info("demo : consentement %s -> %s", service, LIBELLES[statut])
        return _json({"consentement": etat})

    @routeur.post("/api/demo/envoi/{identifiant}", dependencies=garde)
    def envoi(identifiant: str):
        t0 = time.perf_counter()
        try:
            avant = adaptateur.consentement(identifiant)
            t1 = time.perf_counter()
            resultat = adaptateur.envoyer(identifiant)
            t2 = time.perf_counter()
        except LookupError:
            return _json({"erreur": "Patient introuvable."}, 404)
        except ErreurInterface as exc:
            return erreur(exc)
        etapes, verdict = etapes_envoi(resultat, avant, adaptateur.autre_etablissement)
        JOURNAL.info("demo : envoi %s -> %s : %s (consentement %d ms, circuit d'envoi %d ms)", service,
                     adaptateur.autre, resultat.get("statut"), (t1 - t0) * 1000, (t2 - t1) * 1000)
        return _json({"consentement": avant, "etapes": etapes, "verdict": verdict, "en_attente": en_attente(), "envoyes": envoyes(),
                      "technique": {"statut": resultat.get("statut"), "http": resultat.get("http"),
                                    "echange_id": resultat.get("echange_id"),
                                    "tentatives": resultat.get("tentatives"),
                                    "duree_ms": round((t2 - t0) * 1000)}})

    @routeur.post("/api/demo/reprendre", dependencies=garde)
    def reprendre():
        try:
            resultats = adaptateur.reprendre(forcer=True)
        except ErreurInterface as exc:
            return erreur(exc)
        return _json({"en_attente": en_attente(), "envoyes": envoyes(), "resultats": [{"patient": r.get("patient_id") or r.get("ipp"), "statut": r.get("statut"),
                                     "detail": r.get("detail")} for r in resultats]})

    app.include_router(routeur)
