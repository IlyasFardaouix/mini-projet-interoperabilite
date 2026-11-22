"""Routes de connexion du personnel, identiques sur H1 et H2.

Branchees automatiquement par `installer_securite`. Corps et reponses JSON ;
erreurs en OperationOutcome comme le reste de l'API.

    POST /auth/connexion       {"login", "mot_de_passe"}       -> jetons
    POST /auth/renouvellement  {"refresh_token"}               -> nouveaux jetons
    POST /auth/deconnexion     Bearer                          -> 204
    GET  /auth/moi             Bearer                          -> compte et droits
    POST /auth/mot-de-passe    Bearer {"ancien", "nouveau"}    -> nouveaux jetons

Le mot de passe et les jetons ne sont jamais ecrits dans le journal : seul le
pseudonyme du compte y figure pour un echec, le login pour une connexion reussie.
"""

# Pas de « from __future__ import annotations » ici : FastAPI doit voir la vraie
# classe Request (importee localement) pour ne pas la prendre pour un parametre.
from .jetons import AccesRefuse


def _corps_objet(corps) -> dict:
    if not isinstance(corps, dict):
        raise AccesRefuse(422, "invalid", "Le corps doit etre un objet JSON.", "corps_invalide")
    return corps


def routeur_authentification():
    from fastapi import APIRouter, Depends, Request
    from fastapi.responses import JSONResponse, Response

    from .intergiciels import adresse_appelante, lire_json_securise, tracer
    from .utilisateurs import SaisieInvalide

    # Chemins complets (sans prefix=) : l'auditeur du depot les reconnait tels quels.
    routeur = APIRouter(tags=["Authentification"])
    sans_cache = {"Cache-Control": "no-store", "Pragma": "no-cache"}

    def etat(requete):
        return requete.app.state.securite

    def session_requise(requete: Request):
        """Dependance : appelant authentifie PAR UNE SESSION (pas un jeton de systeme)
        et la charge de son jeton."""
        e = etat(requete)
        appelant = e.authentifier(requete)
        if appelant.source != "session":
            raise AccesRefuse(403, "forbidden", "Route reservee aux sessions du personnel.",
                              "session_requise")
        jeton = e.verificateur.extraire(requete.headers.get("authorization"))
        return appelant, e.verificateur.charge_de_session(jeton)

    # Connexion et renouvellement sont publics par nature (on n'a pas encore de
    # jeton) : debit limite par l'intergiciel, verrouillage par compte et par adresse.
    @routeur.post("/auth/connexion")
    async def connexion(requete: Request):
        corps = _corps_objet(await lire_json_securise(requete, maximum=4096))
        login = str(corps.get("login") or "").strip().lower()
        e = etat(requete)
        try:
            jetons = e.verificateur.sessions.ouvrir(
                login, str(corps.get("mot_de_passe") or ""),
                cle_ip=adresse_appelante(requete.scope, e.conf))
        except AccesRefuse:
            tracer(requete, ressource=e.journal.pseudonyme("compte:" + login))
            raise
        tracer(requete, client="utilisateur:" + login)
        return JSONResponse(jetons, headers=sans_cache)

    @routeur.post("/auth/renouvellement")
    async def renouvellement(requete: Request):
        corps = _corps_objet(await lire_json_securise(requete, maximum=4096))
        jetons = etat(requete).verificateur.sessions.renouveler(str(corps.get("refresh_token") or ""))
        tracer(requete, client="utilisateur:" + jetons["utilisateur"]["login"])
        return JSONResponse(jetons, headers=sans_cache)

    @routeur.post("/auth/deconnexion", status_code=204)
    async def deconnexion(requete: Request, session=Depends(session_requise)):
        _, charge = session
        etat(requete).verificateur.sessions.fermer(charge)
        return Response(status_code=204, headers=sans_cache)

    @routeur.get("/auth/moi")
    async def moi(requete: Request, session=Depends(session_requise)):
        appelant, _ = session
        compte = etat(requete).verificateur.sessions.comptes.chercher(appelant.utilisateur)
        return JSONResponse({"utilisateur": compte.public(), "portees": sorted(appelant.portees),
                             "service": etat(requete).conf.service}, headers=sans_cache)

    @routeur.post("/auth/mot-de-passe")
    async def mot_de_passe(requete: Request, session=Depends(session_requise)):
        appelant, charge = session
        corps = _corps_objet(await lire_json_securise(requete, maximum=4096))
        try:
            jetons = etat(requete).verificateur.sessions.changer_mdp(
                appelant, charge, str(corps.get("ancien") or ""), str(corps.get("nouveau") or ""))
        except SaisieInvalide as exc:
            raise AccesRefuse(422, "invalid", str(exc), "mdp_non_conforme") from exc
        return JSONResponse(jetons, headers=sans_cache)

    return routeur
