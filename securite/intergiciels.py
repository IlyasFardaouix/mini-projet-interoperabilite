"""Intergiciel ASGI de securite, et branchement sur une application FastAPI.

Un seul intergiciel, volontairement : l'ordre des controles compte et il est
plus facile a relire ici qu'eparpille dans cinq classes empilees.

Ordre des controles, du plus exterieur au plus interieur :

1. **TLS exige** : une requete en clair est refusee (sauf `/health`).
2. **Limitation de debit** par adresse appelante.
3. **Taille du corps** : un corps annonce trop gros est refuse avant lecture.
4. **Appel de la route**, qui verifie le jeton et la portee via `exiger_portee`.
5. **En-tetes de securite** poses sur la reponse, en-tetes techniques retires.
6. **Journal d'acces** ecrit avec le code HTTP final, meme pour un refus.

L'intergiciel est du pur ASGI : il ne depend d'aucune classe interne de
Starlette, donc il ne cassera pas a la prochaine montee de version.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from .audit import JournalSecurite
from .config import Configuration, charger
from .debit import CHEMINS_EXEMPTES, SeauAJetons
from .entetes import ENTETES_A_RETIRER, entetes_pour
from .jetons import AccesRefuse, Appelant, Verificateur

CLE_CONTEXTE = "securite_contexte"
FHIR_JSON = "application/fhir+json"

# Routes servies sans jeton : elles ne renvoient aucune donnee de patient.
CHEMINS_PUBLICS = ("/health", "/metadata", "/docs", "/redoc", "/openapi.json")


def operation_outcome(type_fhir: str, message: str, gravite: str = "error") -> dict:
    """Erreur au format FHIR, identique a celle des deux API."""
    return {"resourceType": "OperationOutcome",
            "issue": [{"severity": gravite, "code": type_fhir, "diagnostics": message}]}


# ---------------------------------------------------------------------------
# Etat partage
# ---------------------------------------------------------------------------
class EtatSecurite:
    """Objets de securite du service, accessibles via `app.state.securite`."""

    def __init__(self, conf: Configuration):
        self.conf = conf
        self.verificateur = Verificateur(conf)
        self.journal = JournalSecurite(conf.journal, sel=conf.sel_audit, service=conf.service)
        self.seau = SeauAJetons(conf.debit_par_minute)

    # -- authentification --------------------------------------------------
    def authentifier(self, requete) -> Appelant:
        """Verifie le jeton une seule fois par requete et met le resultat en cache."""
        contexte = requete.scope.setdefault(CLE_CONTEXTE, {})
        if "appelant" in contexte:
            return contexte["appelant"]
        try:
            appelant = self.verificateur.verifier(
                requete.headers.get("authorization"),
                cle_verrou=adresse_appelante(requete.scope, self.conf))
        except AccesRefuse as refus:
            contexte["motif"] = refus.motif
            raise
        contexte["appelant"] = appelant
        contexte["client"] = appelant.client
        contexte["jeton"] = appelant.empreinte
        contexte["source_jeton"] = appelant.source
        return appelant

    def exiger(self, requete, *suffixes: str) -> Appelant:
        """Authentifie puis verifie que l'appelant detient toutes les portees."""
        appelant = self.authentifier(requete)
        contexte = requete.scope.setdefault(CLE_CONTEXTE, {})
        demandees = [self.conf.portee(s) for s in suffixes]
        contexte["portee"] = " ".join(demandees)
        manquantes = [p for p in demandees if not appelant.autorise(p)]
        if manquantes:
            contexte["motif"] = "portee_absente:" + ",".join(manquantes)
            raise AccesRefuse(
                403, "forbidden",
                "Ce jeton n'a pas le droit necessaire pour cette route (" + manquantes[0] + ").",
                contexte["motif"])
        return appelant

    def demarrage(self) -> list:
        """Journalise l'etat de la configuration au lancement du service."""
        anomalies = self.verificateur.diagnostic()
        self.journal.enregistrer(
            "demarrage",
            resultat="avertissement" if anomalies else "succes",
            mode=self.conf.mode,
            tls_requis=self.conf.tls_requis,
            jetons=len(self.verificateur.registre.entrees()),
            jwt=bool(self.conf.jwt_secret),
            jeton_partage=bool(self.conf.jeton_historique),
            anomalies=anomalies or None)
        return anomalies


# ---------------------------------------------------------------------------
# Adresse appelante
# ---------------------------------------------------------------------------
def adresse_appelante(scope: dict, conf: Configuration) -> str:
    """Adresse IP de l'appelant.

    `X-Forwarded-For` n'est lu que si `SEC_PROXY_DE_CONFIANCE=1` : sinon
    n'importe quel client pourrait choisir son adresse et contourner la
    limitation de debit comme le verrouillage apres echecs.
    """
    import os

    if (os.getenv("SEC_PROXY_DE_CONFIANCE") or "").strip() in {"1", "true", "oui"}:
        for nom, valeur in scope.get("headers") or []:
            if nom == b"x-forwarded-for":
                premier = valeur.decode("latin-1").split(",")[0].strip()
                if premier:
                    return premier
    client = scope.get("client")
    return client[0] if client else "inconnu"


def _schema(scope: dict) -> str:
    """Schema reel de la requete, en tenant compte d'un proxy de confiance."""
    import os

    schema = scope.get("scheme") or "http"
    if (os.getenv("SEC_PROXY_DE_CONFIANCE") or "").strip() in {"1", "true", "oui"}:
        for nom, valeur in scope.get("headers") or []:
            if nom == b"x-forwarded-proto":
                declare = valeur.decode("latin-1").split(",")[0].strip().lower()
                if declare in {"http", "https"}:
                    return declare
    return schema


def _resultat(code: int) -> str:
    """Classement d'une reponse pour le journal de securite.

    « refus » est reserve aux codes que la couche de securite elle-meme produit :
    ce sont ceux qu'on relit en cas de soupcon. Un 404 ou un 422 est un echec
    fonctionnel, pas un refus d'acces : les melanger rendrait le journal
    inutilisable pour reperer une tentative d'intrusion.
    """
    if code in (401, 403, 413, 429):
        return "refus"
    if code >= 500:
        return "erreur"
    if code >= 400:
        return "echec"
    return "succes"


def _entete(scope: dict, nom: bytes) -> Optional[str]:
    for cle, valeur in scope.get("headers") or []:
        if cle == nom:
            return valeur.decode("latin-1")
    return None


# ---------------------------------------------------------------------------
# Intergiciel
# ---------------------------------------------------------------------------
class MiddlewareSecurite:
    """Garde d'entree et journal de sortie de l'application."""

    def __init__(self, app, etat: EtatSecurite):
        self.app = app
        self.etat = etat

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        conf = self.etat.conf
        chemin = scope.get("path") or "/"
        contexte = scope.setdefault(CLE_CONTEXTE, {})
        depart = time.monotonic()
        ip = adresse_appelante(scope, conf)
        https = _schema(scope) == "https"

        # 1. TLS. /health reste joignable en clair : il ne renvoie aucune donnee
        #    de patient et sert aux sondes de supervision.
        if conf.tls_requis and not https and chemin != "/health":
            return await self._refuser(
                scope, send, 403, "security",
                "Ce service n'accepte que HTTPS. Utiliser https:// (voir docs/securite/tls-https.md).",
                motif="tls_absent", ip=ip, depart=depart)

        # 2. Debit.
        if not chemin.startswith(CHEMINS_EXEMPTES):
            autorise, attendre = self.etat.seau.autoriser(ip)
            if not autorise:
                return await self._refuser(
                    scope, send, 429, "throttled",
                    "Trop de requetes. Nouvel essai dans " + str(attendre) + " s.",
                    motif="debit_depasse", ip=ip, depart=depart,
                    entetes_sup={"Retry-After": str(attendre)})

        # 3. Taille du corps annoncee.
        longueur = _entete(scope, b"content-length")
        if longueur is not None:
            try:
                octets = int(longueur)
            except ValueError:
                return await self._refuser(
                    scope, send, 400, "structure", "En-tete Content-Length invalide.",
                    motif="content_length_invalide", ip=ip, depart=depart)
            if octets > conf.taille_max_corps:
                return await self._refuser(
                    scope, send, 413, "too-costly",
                    "Corps de requete trop volumineux (limite " + str(conf.taille_max_corps)
                    + " octets).",
                    motif="corps_trop_gros", ip=ip, depart=depart)
            contexte["octets"] = octets

        # 4 a 6. Appel de la route, en-tetes de securite, journal.
        etat_reponse = {"code": 0}

        async def send_securise(message):
            if message["type"] == "http.response.start":
                etat_reponse["code"] = message.get("status", 0)
                message = dict(message)
                message["headers"] = self._entetes_finales(
                    message.get("headers") or [], chemin, https)
            await send(message)
            if message["type"] == "http.response.start":
                self._journaliser(scope, etat_reponse["code"], ip, depart)

        await self.app(scope, receive, send_securise)

    # -- en-tetes ----------------------------------------------------------
    def _entetes_finales(self, brutes, chemin: str, https: bool) -> list:
        politique = entetes_pour(chemin, https=https)
        remplacees = {nom.lower().encode("latin-1") for nom in politique}
        a_retirer = remplacees | {n.encode("latin-1") for n in ENTETES_A_RETIRER}
        finales = [(nom, valeur) for nom, valeur in brutes if nom.lower() not in a_retirer]
        for nom, valeur in politique.items():
            finales.append((nom.lower().encode("latin-1"), valeur.encode("latin-1")))
        return finales

    # -- refus -------------------------------------------------------------
    async def _refuser(self, scope, send, code: int, type_fhir: str, message: str, *,
                       motif: str, ip: str, depart: float,
                       entetes_sup: Optional[dict] = None):
        scope.setdefault(CLE_CONTEXTE, {})["motif"] = motif
        corps = json.dumps(operation_outcome(type_fhir, message), ensure_ascii=False).encode("utf-8")
        entetes = {"content-type": FHIR_JSON, "content-length": str(len(corps))}
        entetes.update({k.lower(): v for k, v in (entetes_sup or {}).items()})
        entetes.update({k.lower(): v for k, v in
                        entetes_pour(scope.get("path") or "/", https=_schema(scope) == "https").items()})
        await send({"type": "http.response.start", "status": code,
                    "headers": [(k.encode("latin-1"), v.encode("latin-1"))
                                for k, v in entetes.items()]})
        await send({"type": "http.response.body", "body": corps})
        self._journaliser(scope, code, ip, depart)

    # -- journal -----------------------------------------------------------
    def _journaliser(self, scope, code: int, ip: str, depart: float) -> None:
        contexte = scope.get(CLE_CONTEXTE) or {}
        journal = self.etat.journal
        gabarit, pseudonyme = journal.normaliser_chemin(scope.get("path") or "/")
        requete = scope.get("query_string") or b""
        resultat = _resultat(code)
        journal.enregistrer(
            "acces",
            resultat=resultat,
            http=code,
            methode=scope.get("method"),
            chemin=gabarit,
            ressource=contexte.get("ressource") or pseudonyme,
            parametres=journal.masquer_parametres(requete.decode("latin-1")) or None,
            ip=journal.ip(ip),
            client=contexte.get("client"),
            jeton=contexte.get("jeton"),
            source_jeton=contexte.get("source_jeton"),
            portee=contexte.get("portee"),
            echange_id=contexte.get("echange_id") or _entete(scope, b"x-exchange-id"),
            octets=contexte.get("octets"),
            motif=contexte.get("motif"),
            duree_ms=int((time.monotonic() - depart) * 1000))


# ---------------------------------------------------------------------------
# Branchement
# ---------------------------------------------------------------------------
def installer_securite(app, *, service: str, conf: Optional[Configuration] = None) -> EtatSecurite:
    """Branche la couche de securite sur une application FastAPI.

    A appeler juste apres la creation de `app`, avant la declaration des routes.
    Renvoie l'etat de securite, egalement disponible via `app.state.securite`.
    """
    etat = EtatSecurite(conf or charger(service))
    app.state.securite = etat

    async def refus(requete, exc: AccesRefuse):
        from fastapi.responses import JSONResponse

        requete.scope.setdefault(CLE_CONTEXTE, {}).setdefault("motif", exc.motif)
        entetes = {}
        if exc.http == 401:
            entetes["WWW-Authenticate"] = f'Bearer realm="{etat.conf.service}"'
        return JSONResponse(operation_outcome(exc.type_fhir, exc.message),
                            status_code=exc.http, media_type=FHIR_JSON, headers=entetes)

    app.add_exception_handler(AccesRefuse, refus)
    app.add_middleware(MiddlewareSecurite, etat=etat)

    anomalies = etat.demarrage()
    for anomalie in anomalies:
        print("[securite " + etat.conf.service + "] ATTENTION : " + anomalie)
    return etat


def tracer(requete, **champs) -> None:
    """Ajoute des informations a la ligne de journal de la requete en cours.

    Sert a tracer un identifiant d'echange decide par la route elle-meme :

        tracer(requete, echange_id=rapport["echange_id"])
    """
    contexte = requete.scope.setdefault(CLE_CONTEXTE, {})
    contexte.update({cle: valeur for cle, valeur in champs.items() if valeur is not None})


def exiger_portee(*suffixes: str):
    """Dependance FastAPI : `dependencies=[Depends(exiger_portee("import"))]`.

    Authentifie l'appelant puis verifie qu'il detient toutes les portees
    demandees pour le service courant (« import » devient « h2:import »).
    """
    from fastapi import Request

    async def dependance(requete):
        etat: EtatSecurite = requete.app.state.securite
        return etat.exiger(requete, *suffixes)

    # `from __future__ import annotations` transforme les annotations en chaines,
    # que FastAPI resout dans les globales du MODULE. « Request », importe
    # localement, y est introuvable : le parametre serait alors pris pour un
    # parametre de requete et la route repondrait 422 sans jamais verifier le
    # jeton. On pose donc la vraie classe, sans importer fastapi au chargement.
    dependance.__annotations__ = {"requete": Request, "return": Appelant}
    return dependance


async def lire_json_securise(requete, *, maximum: Optional[int] = None):
    """Lit le corps JSON en s'arretant des que la limite de taille est depassee.

    Complete le controle de `Content-Length` de l'intergiciel : un envoi en
    `Transfer-Encoding: chunked` n'annonce pas sa taille.
    """
    etat: EtatSecurite = requete.app.state.securite
    limite = maximum or etat.conf.taille_max_corps
    morceaux = []
    total = 0
    async for morceau in requete.stream():
        total += len(morceau)
        if total > limite:
            raise AccesRefuse(413, "too-costly",
                              "Corps de requete trop volumineux (limite " + str(limite)
                              + " octets).", "corps_trop_gros")
        morceaux.append(morceau)
    corps = b"".join(morceaux)
    try:
        return json.loads(corps)
    except ValueError as exc:
        raise AccesRefuse(400, "structure",
                          "Le corps de la requete n'est pas du JSON valide.",
                          "json_invalide") from exc
