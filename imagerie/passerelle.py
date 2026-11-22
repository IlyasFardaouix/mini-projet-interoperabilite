"""Passerelle DICOMweb : seule porte d'acces au PACS depuis l'exterieur.

    GET /dicom-web/studies/{study_uid}            WADO-RS : instances (multipart)
    GET /dicom-web/studies/{study_uid}/metadata   WADO-RS : metadonnees DICOM JSON

Chaque appel exige un jeton et la portee `imagerie.lire`, puis passe par la
fonction `autoriser` fournie par l'hopital : elle retrouve le patient de
l'etude et applique ses regles (consentement, categorie « imagerie » exclue,
anti-boucle). L'option `?desidentifier=true` renvoie des images sans identite
(profil de base PS3.15), par exemple pour l'enseignement.

Le journal d'acces porte le pseudonyme du patient, jamais l'UID en clair.
"""

# Pas de « from __future__ import annotations » : FastAPI doit voir la classe Request.
import re
from typing import Callable

from securite import AccesRefuse, exiger_portee, tracer

from .dicom import depuis_octets, desidentifier, metadonnees_json, verifier_etude, vers_octets
from .dicomweb import ErreurPacs, encoder_multipart

UID = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def routeur_dicomweb(*, entrepot: Callable, autoriser: Callable):
    """`entrepot()` -> entrepot du service ou None ; `autoriser(appelant, study_uid)`
    -> pseudonyme du patient, ou leve AccesRefuse (403, 404)."""
    from fastapi import APIRouter, Depends, Query, Request
    from fastapi.responses import JSONResponse, Response

    routeur = APIRouter(tags=["Imagerie DICOM"])

    def instances(requete, appelant, study_uid: str) -> tuple:
        if len(study_uid) > 64 or not UID.match(study_uid):
            raise AccesRefuse(400, "invalid", "StudyInstanceUID invalide.", "uid_invalide")
        pseudonyme = autoriser(appelant, study_uid)
        tracer(requete, ressource=pseudonyme)
        pacs = entrepot()
        if pacs is None:
            raise AccesRefuse(503, "transient", "PACS non configure sur ce service.", "pacs_absent")
        try:
            octets = pacs.etude(study_uid)
        except ErreurPacs as exc:
            raise AccesRefuse(503, "transient", "PACS indisponible.", "pacs:" + str(exc)) from exc
        if not octets:
            raise AccesRefuse(404, "not-found", "Etude absente du PACS.", "etude_absente")
        datasets = [depuis_octets(o) for o in octets]
        if verifier_etude(datasets, study_uid):
            raise AccesRefuse(500, "exception", "Contenu du PACS incoherent.", "pacs_incoherent")
        return pseudonyme, octets, datasets

    @routeur.get("/dicom-web/studies/{study_uid}")
    def recuperer_etude(study_uid: str, requete: Request,
                        desidentifier_: bool = Query(False, alias="desidentifier"),
                        appelant=Depends(exiger_portee("imagerie.lire"))):
        pseudonyme, octets, datasets = instances(requete, appelant, study_uid)
        if desidentifier_:
            octets = [vers_octets(desidentifier(ds, pseudonyme)) for ds in datasets]
        corps, type_contenu = encoder_multipart(octets)
        return Response(corps, headers={"Content-Type": type_contenu, "Cache-Control": "no-store"})

    @routeur.get("/dicom-web/studies/{study_uid}/metadata")
    def metadonnees(study_uid: str, requete: Request,
                    desidentifier_: bool = Query(False, alias="desidentifier"),
                    appelant=Depends(exiger_portee("imagerie.lire"))):
        pseudonyme, _, datasets = instances(requete, appelant, study_uid)
        if desidentifier_:
            datasets = [desidentifier(ds, pseudonyme) for ds in datasets]
        return JSONResponse(metadonnees_json(datasets), media_type="application/dicom+json",
                            headers={"Cache-Control": "no-store"})

    return routeur
