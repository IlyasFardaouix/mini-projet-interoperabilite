"""Consentement au partage du dossier : regles communes a H1 et H2 (loi 09-08).

Avant ce module, chaque hopital verifiait seulement « statut == actif ». Le
consentement est maintenant un objet complet, evalue de la meme facon des deux
cotes :

- statut : actif, refuse, retire (retrait apres accord) ou en_attente ;
- periode de validite (debut, fin) : un consentement expire n'autorise plus rien ;
- finalite : le partage n'est autorise que pour la continuite des soins ;
- destinataires : etablissements autorises (vide = tous les partenaires) ;
- categories exclues : le patient peut refuser le partage d'une partie du
  dossier (par exemple l'imagerie) sans refuser tout l'echange ;
- preuve : date de recueil, signataire (patient ou representant legal), agent
  qui l'a recueilli, et pour un retrait sa date et son motif.

Le module ne depend d'aucune base : H1 (Oracle) et H2 (MongoDB) ont chacun un
petit adaptateur (`depuis_oracle` / `vers_oracle`, `depuis_mongo` / `vers_mongo`).
La ressource FHIR R5 `Consent` echangee dans les Bundles est produite et relue
ici (`vers_fhir`, `depuis_fhir`) pour que les deux hopitaux parlent le meme
langage.

Un changement de consentement ne remplace jamais l'ancien : chaque decision est
une nouvelle version, la plus recente fait foi, l'historique reste consultable.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Vocabulaire
# ---------------------------------------------------------------------------
ACTIF = "actif"
REFUSE = "refuse"
RETIRE = "retire"
EN_ATTENTE = "en_attente"
STATUTS = (ACTIF, REFUSE, RETIRE, EN_ATTENTE)

# Statuts lus dans les bases et dans FHIR (R5, et R4 accepte en entree).
_ALIAS_STATUT = {
    "actif": ACTIF, "active": ACTIF, "permit": ACTIF,
    "refuse": REFUSE, "refused": REFUSE, "rejected": REFUSE, "not-done": REFUSE, "deny": REFUSE,
    "retire": RETIRE, "inactive": RETIRE, "revoked": RETIRE, "withdrawn": RETIRE,
    "en_attente": EN_ATTENTE, "proposed": EN_ATTENTE, "draft": EN_ATTENTE, "propose": EN_ATTENTE,
}

FINALITE_SOINS = "soins"

# Etablissements de l'echange. Le destinataire d'un export est deduit du jeton
# de l'appelant (voir hopital2/api_h2.py, destinataire_de).
ETABLISSEMENTS = {"H1": "CHU Al Massira", "H2": "Clinique Al Baçar"}

# Categories du dossier que le patient peut exclure du partage, et les
# ressources FHIR qu'elles couvrent.
CATEGORIES = {
    "imagerie": frozenset({"ImagingStudy", "Endpoint"}),
    "comptes_rendus": frozenset({"DiagnosticReport"}),
    "allergies": frozenset({"AllergyIntolerance"}),
}

SIGNATAIRES = ("patient", "representant_legal")

# Systemes FHIR
SYS_LOINC = "http://loinc.org"
SYS_ACT_REASON = "http://terminology.hl7.org/CodeSystem/v3-ActReason"
SYS_PARTICIPATION = "http://terminology.hl7.org/CodeSystem/v3-ParticipationType"
SYS_TYPES_FHIR = "http://hl7.org/fhir/fhir-types"
SYS_ETABLISSEMENT = "urn:interop-sante:etablissement"
URL_CNDP = "https://www.cndp.ma"

_STATUT_VERS_FHIR = {ACTIF: "active", REFUSE: "not-done", RETIRE: "inactive", EN_ATTENTE: "draft"}


class ConsentementRefuse(PermissionError):
    """Le consentement n'autorise pas l'operation demandee (HTTP 403)."""

    http = 403


class ConsentementInvalide(ValueError):
    """Saisie de consentement incoherente (HTTP 422)."""

    http = 422


# ---------------------------------------------------------------------------
# Modele
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Consentement:
    statut: str
    date_recueil: Optional[date] = None
    debut: Optional[date] = None
    fin: Optional[date] = None
    finalites: tuple = (FINALITE_SOINS,)
    destinataires: tuple = ()            # () = tous les etablissements partenaires
    categories_exclues: tuple = ()
    signataire: str = "patient"
    recueilli_par: Optional[str] = None
    date_retrait: Optional[date] = None
    motif_retrait: Optional[str] = None

    def en_dict(self) -> dict:
        """Forme JSON (dates ISO), pour les reponses d'API."""
        d = asdict(self)
        for cle, valeur in d.items():
            if isinstance(valeur, date):
                d[cle] = valeur.isoformat()
            elif isinstance(valeur, tuple):
                d[cle] = list(valeur)
        return d


@dataclass(frozen=True)
class Decision:
    autorise: bool
    motif: str
    categories_exclues: frozenset = field(default=frozenset())

    @property
    def types_exclus(self) -> frozenset:
        return types_exclus(self.categories_exclues)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def normaliser_statut(valeur: Any) -> str:
    if valeur is None:
        return EN_ATTENTE
    return _ALIAS_STATUT.get(str(valeur).strip().lower(), str(valeur).strip().lower())


def normaliser_finalite(valeur: Any) -> str:
    """« Partage soins » (H1), « care-continuity » (H2), « TREAT » (FHIR) -> soins."""
    texte = str(valeur or "").strip().lower()
    if not texte or "soin" in texte or "care" in texte or texte == "treat":
        return FINALITE_SOINS
    return texte


def _date(valeur: Any) -> Optional[date]:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    texte = str(valeur).strip()
    try:
        return date.fromisoformat(texte[:10])
    except ValueError as exc:
        raise ConsentementInvalide(f"Date invalide : « {texte} » (format AAAA-MM-JJ attendu).") from exc


def _liste(valeur: Any) -> tuple:
    """Liste, ou texte separe par des virgules (colonnes Oracle)."""
    if valeur in (None, ""):
        return ()
    if isinstance(valeur, str):
        valeur = valeur.split(",")
    return tuple(sorted({str(v).strip() for v in valeur if str(v).strip()}))


def _destinataires(valeur: Any) -> tuple:
    return tuple(sorted({v.upper() for v in _liste(valeur)}))


def _signataire(valeur: Any) -> str:
    texte = str(valeur or "patient").strip().lower()
    if "repr" in texte or "legal" in texte or "tuteur" in texte:
        return "representant_legal"
    return "patient"


# ---------------------------------------------------------------------------
# Regles
# ---------------------------------------------------------------------------
def evaluer(consentement: Optional[Consentement], *, destinataire: Optional[str] = None,
            finalite: str = FINALITE_SOINS, aujourd_hui: Optional[date] = None) -> Decision:
    """Dit si le partage est autorise, et quelles categories en sont exclues."""
    if consentement is None:
        return Decision(False, "aucun consentement enregistre pour ce patient")
    jour = aujourd_hui or date.today()
    c = consentement
    if c.statut != ACTIF:
        libelle = {REFUSE: "refuse", RETIRE: "retire", EN_ATTENTE: "en attente de recueil"}
        motif = "consentement " + libelle.get(c.statut, f"« {c.statut} »")
        if c.statut == RETIRE and c.date_retrait:
            motif += f" le {c.date_retrait.isoformat()}"
        return Decision(False, motif)
    if c.debut and jour < c.debut:
        return Decision(False, f"consentement pas encore en vigueur (debut le {c.debut.isoformat()})")
    if c.fin and jour > c.fin:
        return Decision(False, f"consentement expire le {c.fin.isoformat()}")
    if normaliser_finalite(finalite) not in c.finalites:
        return Decision(False, f"finalite « {finalite} » non couverte par le consentement")
    if destinataire and c.destinataires and destinataire.upper() not in c.destinataires:
        return Decision(False, f"partage vers {destinataire.upper()} non autorise par le patient")
    return Decision(True, "consentement actif", frozenset(c.categories_exclues))


def verifier(consentement: Optional[Consentement], *, operation: str = "Transfert",
             **criteres) -> Decision:
    """Comme `evaluer`, mais leve ConsentementRefuse si le partage est interdit."""
    decision = evaluer(consentement, **criteres)
    if not decision.autorise:
        raise ConsentementRefuse(f"{operation} refuse : {decision.motif} (loi 09-08).")
    return decision


def types_exclus(categories: Iterable[str]) -> frozenset:
    exclus: set = set()
    for categorie in categories:
        exclus |= CATEGORIES.get(categorie, frozenset())
    return frozenset(exclus)


# ---------------------------------------------------------------------------
# Saisie, retrait
# ---------------------------------------------------------------------------
def depuis_saisie(corps: Any, *, aujourd_hui: Optional[date] = None) -> Consentement:
    """Consentement recueilli via l'API (corps JSON). Leve ConsentementInvalide."""
    if not isinstance(corps, dict):
        raise ConsentementInvalide("Le corps doit etre un objet JSON.")
    statut = normaliser_statut(corps.get("statut"))
    if statut not in (ACTIF, REFUSE):
        raise ConsentementInvalide("statut doit valoir « actif » ou « refuse » "
                                   "(un retrait passe par la route /retrait).")
    jour = aujourd_hui or date.today()
    debut = _date(corps.get("debut")) or jour
    fin = _date(corps.get("fin"))
    if fin and fin < debut:
        raise ConsentementInvalide("La date de fin precede la date de debut.")
    destinataires = _destinataires(corps.get("destinataires"))
    inconnus = set(destinataires) - set(ETABLISSEMENTS)
    if inconnus:
        raise ConsentementInvalide("Destinataire(s) inconnu(s) : " + ", ".join(sorted(inconnus))
                                   + ". Valeurs possibles : " + ", ".join(sorted(ETABLISSEMENTS)) + ".")
    categories = _liste(corps.get("categories_exclues"))
    inconnues = set(categories) - set(CATEGORIES)
    if inconnues:
        raise ConsentementInvalide("Categorie(s) inconnue(s) : " + ", ".join(sorted(inconnues))
                                   + ". Valeurs possibles : " + ", ".join(sorted(CATEGORIES)) + ".")
    signataire = str(corps.get("signataire") or "patient").strip().lower()
    if signataire not in SIGNATAIRES:
        raise ConsentementInvalide("signataire doit valoir « patient » ou « representant_legal ».")
    recueilli_par = str(corps.get("recueilli_par") or "").strip()
    if not recueilli_par:
        raise ConsentementInvalide("recueilli_par (agent qui a recueilli le consentement) est obligatoire.")
    finalites = tuple(sorted({normaliser_finalite(f) for f in (corps.get("finalites") or [FINALITE_SOINS])}))
    return Consentement(statut=statut, date_recueil=jour, debut=debut, fin=fin, finalites=finalites,
                        destinataires=destinataires, categories_exclues=categories,
                        signataire=signataire, recueilli_par=recueilli_par[:100])


def retirer(consentement: Optional[Consentement], motif: Any, *, recueilli_par: Any,
            aujourd_hui: Optional[date] = None) -> Consentement:
    """Nouvelle version « retire » d'un consentement actif (droit d'opposition)."""
    if consentement is None or consentement.statut != ACTIF:
        raise ConsentementInvalide("Aucun consentement actif a retirer.")
    agent = str(recueilli_par or "").strip()
    if not agent:
        raise ConsentementInvalide("recueilli_par (agent qui enregistre le retrait) est obligatoire.")
    jour = aujourd_hui or date.today()
    return replace(consentement, statut=RETIRE, date_recueil=jour, recueilli_par=agent[:100],
                   date_retrait=jour, motif_retrait=(str(motif or "").strip()[:300] or None))


# ---------------------------------------------------------------------------
# Adaptateurs de stockage
# ---------------------------------------------------------------------------
_STATUT_ORACLE = {ACTIF: "ACTIF", REFUSE: "REFUSE", RETIRE: "RETIRE", EN_ATTENTE: "EN_ATTENTE"}


def depuis_oracle(ligne: Optional[dict]) -> Optional[Consentement]:
    """Ligne de la table H1 `consentement` (cles en minuscules). Colonnes ajoutees
    par schema_consentement_h1.sql facultatives : une ligne ancienne reste lisible."""
    if not ligne:
        return None
    return Consentement(
        statut=normaliser_statut(ligne.get("statut")),
        date_recueil=_date(ligne.get("date_consentement")),
        debut=_date(ligne.get("date_debut")),
        fin=_date(ligne.get("date_fin")),
        finalites=(normaliser_finalite(ligne.get("finalite")),),
        destinataires=_destinataires(ligne.get("destinataires")),
        categories_exclues=_liste(ligne.get("categories_exclues")),
        signataire=_signataire(ligne.get("signataire")),
        recueilli_par=ligne.get("recueilli_par"),
        date_retrait=_date(ligne.get("date_retrait")),
        motif_retrait=ligne.get("motif_retrait"),
    )


def vers_oracle(c: Consentement) -> dict:
    """Valeurs des colonnes H1 (sans id ni ipp)."""
    return {
        "statut": _STATUT_ORACLE[c.statut],
        "finalite": "Partage soins" if FINALITE_SOINS in c.finalites else ",".join(c.finalites),
        "date_consentement": c.date_recueil,
        "date_debut": c.debut,
        "date_fin": c.fin,
        "destinataires": ",".join(c.destinataires) or None,
        "categories_exclues": ",".join(c.categories_exclues) or None,
        "signataire": c.signataire.upper(),
        "recueilli_par": c.recueilli_par,
        "date_retrait": c.date_retrait,
        "motif_retrait": c.motif_retrait,
    }


_STATUT_MONGO = {ACTIF: "active", REFUSE: "refused", RETIRE: "inactive", EN_ATTENTE: "proposed"}


def depuis_mongo(champ: Optional[dict]) -> Optional[Consentement]:
    """Champ `consent` du document patient H2."""
    if not champ:
        return None
    return Consentement(
        statut=normaliser_statut(champ.get("status")),
        date_recueil=_date(champ.get("date")),
        debut=_date(champ.get("valid_from")),
        fin=_date(champ.get("valid_until")),
        finalites=(normaliser_finalite(champ.get("purpose")),),
        destinataires=_destinataires(champ.get("recipients")),
        categories_exclues=_liste(champ.get("excluded_categories")),
        signataire=_signataire(champ.get("signed_by")),
        recueilli_par=champ.get("collected_by"),
        date_retrait=_date(champ.get("withdrawn_at")),
        motif_retrait=champ.get("withdrawal_reason"),
    )


def vers_mongo(c: Consentement) -> dict:
    """Champ `consent` H2. Les cles historiques (status, purpose, signed_by, date)
    gardent leur forme : les adaptateurs FHIR existants les lisent toujours."""
    champ = {
        "status": _STATUT_MONGO[c.statut],
        "purpose": "care-continuity" if FINALITE_SOINS in c.finalites else ",".join(c.finalites),
        "signed_by": "representative" if c.signataire == "representant_legal" else "patient",
        "date": c.date_recueil.isoformat() if c.date_recueil else None,
        "valid_from": c.debut.isoformat() if c.debut else None,
        "valid_until": c.fin.isoformat() if c.fin else None,
        "recipients": list(c.destinataires),
        "excluded_categories": list(c.categories_exclues),
        "collected_by": c.recueilli_par,
        "withdrawn_at": c.date_retrait.isoformat() if c.date_retrait else None,
        "withdrawal_reason": c.motif_retrait,
    }
    return {k: v for k, v in champ.items() if v not in (None, [])}


# ---------------------------------------------------------------------------
# FHIR R5
# ---------------------------------------------------------------------------
def _ref_etablissement(code: str) -> dict:
    return {"identifier": {"system": SYS_ETABLISSEMENT, "value": code},
            "display": ETABLISSEMENTS.get(code, code)}


def vers_fhir(c: Consentement, *, patient_ref: dict, id_ressource: Optional[str] = None,
              identifiant: Optional[dict] = None, organisation_ref: Optional[dict] = None,
              meta: Optional[dict] = None, langue: Optional[str] = None) -> dict:
    """Ressource Consent R5. Les exclusions sont des sous-provisions : la
    decision de base (permit) s'inverse pour les types de ressources listes."""
    res: dict[str, Any] = {"resourceType": "Consent"}
    if id_ressource:
        res["id"] = id_ressource
    if meta:
        res["meta"] = meta
    if langue:
        res["language"] = langue
    if identifiant:
        res["identifier"] = [identifiant]
    res.update({
        "status": _STATUT_VERS_FHIR.get(c.statut, "draft"),
        "category": [{"coding": [{"system": SYS_LOINC, "code": "59284-0",
                                  "display": "Consent Document"}]}],
        "subject": patient_ref,
        "decision": "permit" if c.statut == ACTIF else "deny",
        "policyBasis": {"url": URL_CNDP},
    })
    if c.date_recueil:
        res["date"] = c.date_recueil.isoformat()
    periode = {}
    if c.debut:
        periode["start"] = c.debut.isoformat()
    if c.fin or c.date_retrait:
        periode["end"] = (c.date_retrait or c.fin).isoformat()
    if periode:
        res["period"] = periode
    res["grantor"] = [patient_ref]
    if organisation_ref:
        res["controller"] = [organisation_ref]
    verification = {"verified": True, "verificationType": {"text": "signature"},
                    "verifiedWith": {"display": c.signataire}}
    if c.date_recueil:
        verification["verificationDate"] = [c.date_recueil.isoformat()]
    res["verification"] = [verification]

    provision: dict[str, Any] = {"purpose": [
        {"system": SYS_ACT_REASON, "code": "TREAT", "display": "treatment"}
        if f == FINALITE_SOINS else {"code": f, "display": f} for f in c.finalites]}
    if c.destinataires:
        provision["actor"] = [{
            "role": {"coding": [{"system": SYS_PARTICIPATION, "code": "IRCP",
                                 "display": "information recipient"}]},
            "reference": _ref_etablissement(code)} for code in c.destinataires]
    exclus = sorted(types_exclus(c.categories_exclues))
    if exclus:
        provision["provision"] = [{"resourceType": [
            {"system": SYS_TYPES_FHIR, "code": t} for t in exclus]}]
    res["provision"] = [provision]
    return res


def depuis_fhir(res: Optional[dict]) -> Optional[Consentement]:
    """Relit une ressource Consent (R5, ou R4 pour la compatibilite)."""
    if not res:
        return None
    statut = normaliser_statut(res.get("status"))
    if res.get("decision") == "deny" and statut == ACTIF:
        statut = REFUSE
    periode = res.get("period") or {}
    provisions = res.get("provision") or []
    if isinstance(provisions, dict):          # R4 : une seule provision
        provisions = [provisions]
    p0 = provisions[0] if provisions else {}
    if not periode and isinstance(p0.get("period"), dict):
        periode = p0["period"]
    finalites = tuple(sorted({normaliser_finalite(x.get("code") or x.get("display"))
                              for x in p0.get("purpose") or []})) or (FINALITE_SOINS,)
    destinataires = []
    for acteur in p0.get("actor") or []:
        ref = acteur.get("reference") or {}
        ident = ref.get("identifier") or {}
        if ident.get("system") == SYS_ETABLISSEMENT and ident.get("value"):
            destinataires.append(ident["value"])
    types = {coding.get("code") for sous in p0.get("provision") or []
             for coding in sous.get("resourceType") or []}
    categories = [nom for nom, couverts in CATEGORIES.items() if couverts & types]
    verif = (res.get("verification") or [{}])[0]
    signataire = _signataire((verif.get("verifiedWith") or {}).get("display"))
    for ext in res.get("extension") or []:
        if "legal-representative" in (ext.get("url") or ""):
            signataire = "representant_legal"
    return Consentement(
        statut=statut,
        date_recueil=_date(res.get("date") or res.get("dateTime")),
        debut=_date(periode.get("start")),
        fin=_date(periode.get("end")) if statut == ACTIF else None,
        finalites=finalites,
        destinataires=_destinataires(destinataires),
        categories_exclues=_liste(categories),
        signataire=signataire,
    )


# ---------------------------------------------------------------------------
# Filtrage d'un Bundle
# ---------------------------------------------------------------------------
def filtrer_bundle(bundle: dict, categories_exclues: Iterable[str]) -> tuple[dict, int]:
    """Retire du Bundle les ressources des categories exclues par le patient,
    puis les references qui pointaient vers elles. Renvoie (bundle, nb retirees)."""
    exclus = types_exclus(categories_exclues)
    if not exclus:
        return bundle, 0
    retires: set = set()
    gardes = []
    for entree in bundle.get("entry") or []:
        res = entree.get("resource") or {}
        if res.get("resourceType") in exclus:
            if entree.get("fullUrl"):
                retires.add(entree["fullUrl"])
            if res.get("id"):
                retires.add(f"{res['resourceType']}/{res['id']}")
        else:
            gardes.append(entree)
    if not retires and len(gardes) == len(bundle.get("entry") or []):
        return bundle, 0
    resultat = copy.copy(bundle)
    resultat["entry"] = [_sans_references(e, retires) for e in gardes]
    return resultat, len(bundle.get("entry") or []) - len(gardes)


def _pointe_vers(valeur: Any, retires: set) -> bool:
    return isinstance(valeur, dict) and isinstance(valeur.get("reference"), str) \
        and any(valeur["reference"] == r or valeur["reference"].endswith("/" + r) for r in retires)


def _sans_references(valeur: Any, retires: set) -> Any:
    if isinstance(valeur, dict):
        propre = {}
        for cle, enfant in valeur.items():
            if _pointe_vers(enfant, retires):
                continue
            enfant = _sans_references(enfant, retires)
            if isinstance(enfant, list) and not enfant and isinstance(valeur.get(cle), list) \
                    and valeur.get(cle):
                continue                      # liste videe par le filtrage : on retire la cle
            propre[cle] = enfant
        return propre
    if isinstance(valeur, list):
        return [_sans_references(v, retires) for v in valeur if not _pointe_vers(v, retires)]
    return valeur
