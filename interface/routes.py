"""Routes de l'interface web : page statique, config publique, et routes d'appui.

Les routes d'appui n'existent que pour ce que l'interface ne peut pas faire seule :

    GET  /api/ui/patients?q=            recherche (nom, prenom, CIN, identifiant)   patient.chercher
    GET  /api/ui/dossier/{id}           dossier lisible (medecin)                    export
    POST /api/ui/envoi/{id}             envoi a l'autre hopital, via la file          export
    GET  /api/ui/envois                 etat de la file d'attente                    export
    POST /api/ui/envois/reprendre       relance les envois en attente                export
    GET  /api/ui/journal                journal d'acces recent + chainage            audit

Le consentement et le droit d'acces utilisent les routes deja existantes de chaque API.
Le navigateur n'a JAMAIS le jeton d'echange entre hopitaux : l'envoi est fait par le
serveur, avec les jetons de son environnement, au nom d'une session identifiee.

Pas de `from __future__ import annotations` : FastAPI doit voir les vraies classes.
"""

import json
import os
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from securite import exiger_portee, operation_outcome, verifier_chaine

STATIQUE = Path(__file__).resolve().parent / "static"


class ErreurInterface(Exception):
    """Erreur metier de l'adaptateur, traduite en OperationOutcome (HTTP `code`)."""

    def __init__(self, code: int, message: str, type_fhir: str = "invalid"):
        super().__init__(message)
        self.code, self.message, self.type_fhir = code, message, type_fhir


def _json(contenu, code: int = 200) -> Response:
    return Response(json.dumps(contenu, ensure_ascii=False, default=str), status_code=code,
                    media_type="application/json")


def _erreur(code: int, type_fhir: str, message: str) -> Response:
    return Response(json.dumps(operation_outcome(type_fhir, message), ensure_ascii=False),
                    status_code=code, media_type="application/fhir+json")


def _dernieres_lignes(chemin: Path, limite: int) -> list:
    """Les `limite` dernieres lignes JSON d'un journal (la plus recente d'abord)."""
    gardees = deque(maxlen=limite)
    try:
        with Path(chemin).open("rb") as fichier:
            for brut in fichier:
                if brut.strip():
                    gardees.append(brut)
    except OSError:
        return []
    evenements = []
    for brut in reversed(gardees):
        try:
            entree = json.loads(brut)
        except ValueError:
            continue
        entree.pop("prec", None)          # empreinte du chainage : inutile a l'ecran
        evenements.append(entree)
    return evenements


def installer_interface(app, *, service: str, adaptateur) -> None:
    """Branche la page et les routes d'appui. A appeler apres installer_securite()."""
    routeur = APIRouter(tags=["Interface"])

    def pseudo(requete: Request, identifiant: str):
        return requete.app.state.securite.journal.pseudonyme(identifiant)

    def tracer_ressource(requete: Request, identifiant: str) -> None:
        from securite import tracer
        tracer(requete, ressource=pseudo(requete, identifiant))

    # -- configuration publique : de quoi afficher l'ecran de connexion ------------
    @routeur.get("/ui/config.json", include_in_schema=False)
    def configuration():
        return _json({"service": service, "etablissement": adaptateur.etablissement,
                      "autre": adaptateur.autre, "autre_etablissement": adaptateur.autre_etablissement,
                      "demo": os.getenv("DEMO") == "1"})

    @routeur.get("/ui", include_in_schema=False)
    @routeur.get("/ui/", include_in_schema=False)
    def accueil():
        """Page d'accueil : la demonstration si DEMO=1, sinon la connexion du personnel.
        La connexion du personnel reste toujours accessible sur /ui/index.html."""
        page = "demo.html" if os.getenv("DEMO") == "1" else "index.html"
        return FileResponse(STATIQUE / page, media_type="text/html; charset=utf-8")

    # -- routes d'appui (toutes protegees par une portee) ---------------------------
    @routeur.get("/api/ui/patients", dependencies=[Depends(exiger_portee("patient.chercher"))])
    def patients(q: str = Query(default="", max_length=80)):
        try:
            return _json({"service": service, "resultats": adaptateur.rechercher(q.strip())})
        except ErreurInterface as exc:
            return _erreur(exc.code, exc.type_fhir, exc.message)

    @routeur.get("/api/ui/dossier/{identifiant}", dependencies=[Depends(exiger_portee("export"))])
    def dossier(identifiant: str, requete: Request):
        try:
            contenu = adaptateur.dossier(identifiant)
        except LookupError:
            return _erreur(404, "not-found", "Patient introuvable.")
        except ErreurInterface as exc:
            return _erreur(exc.code, exc.type_fhir, exc.message)
        tracer_ressource(requete, contenu["patient"]["id"])
        return _json(contenu)

    @routeur.post("/api/ui/envoi/{identifiant}", dependencies=[Depends(exiger_portee("export"))])
    def envoyer(identifiant: str, requete: Request):
        tracer_ressource(requete, identifiant)
        try:
            return _json(adaptateur.envoyer(identifiant))
        except ErreurInterface as exc:
            return _erreur(exc.code, exc.type_fhir, exc.message)

    @routeur.get("/api/ui/envois", dependencies=[Depends(exiger_portee("export"))])
    def envois():
        try:
            return _json({"envois": adaptateur.lister_envois()})
        except ErreurInterface as exc:
            return _erreur(exc.code, exc.type_fhir, exc.message)

    @routeur.post("/api/ui/envois/reprendre", dependencies=[Depends(exiger_portee("export"))])
    def reprendre(forcer: bool = Query(default=False,
                                       description="vrai : ne pas attendre l'heure de reprise")):
        try:
            return _json({"resultats": adaptateur.reprendre(forcer=forcer)})
        except ErreurInterface as exc:
            return _erreur(exc.code, exc.type_fhir, exc.message)

    @routeur.get("/api/ui/journal", dependencies=[Depends(exiger_portee("audit"))])
    def journal(requete: Request, limite: int = Query(default=100, ge=1, le=500)):
        chemin = requete.app.state.securite.journal.chemin
        return _json({"service": service, "chaine": verifier_chaine(chemin),
                      "evenements": _dernieres_lignes(chemin, limite)})

    app.include_router(routeur)
    from .demo import installer_demo           # routes /api/demo/* : actives seulement si DEMO=1
    installer_demo(app, service=service, adaptateur=adaptateur)
    # Fichiers de la page : js, css. Montes apres les routes /ui precises ci-dessus.
    app.mount("/ui", StaticFiles(directory=STATIQUE, html=True), name="interface")
