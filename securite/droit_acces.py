"""Droit d'acces de la personne (loi 09-08, art. 7) : forme commune de la reponse.

Une personne peut demander a chaque etablissement la communication des donnees
qu'il detient sur elle, sous une forme intelligible, avec la finalite du
traitement, les destinataires et l'origine des donnees. H1 et H2 rassemblent
chacun leurs donnees ; ce module met la reponse dans la meme forme des deux
cotes, pour que le DPO (role `dpo`, portee `droit_acces`) la remette telle quelle.

La demande elle-meme est tracee : dans le journal d'acces (pseudonyme) et dans
le journal metier du patient.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, Optional

ETABLISSEMENTS = {"H1": "CHU Al Massira", "H2": "Clinique Al Baçar"}
FINALITE = ("Continuite des soins entre le CHU Al Massira et la Clinique Al Baçar : "
            "echange du dossier du patient adresse et retour des resultats.")
DROITS = {
    "rectification": "demande ecrite au DPO de l'etablissement ; la correction est tracee "
                     "et signalee a l'autre etablissement si la donnee lui a ete transmise (art. 8)",
    "opposition": "retrait du consentement a l'accueil ; aucun echange ulterieur (art. 9)",
    "reclamation": "Commission nationale de controle de la protection des donnees a caractere "
                   "personnel (CNDP), www.cndp.ma",
}
CONSERVATION = {
    "dossier": "duree de conservation du dossier medical de l'etablissement",
    "journal_metier": "meme duree que le dossier medical",
    "journal_acces_securite": "1 an (politique de securite, 8.6)",
}


def _texte(valeur) -> Optional[str]:
    if valeur is None:
        return None
    if isinstance(valeur, datetime):
        return valeur.isoformat(timespec="seconds")
    return str(valeur)


def entree_acces(date, action, evenement, *, agent=None, resultat=None, echange_id=None,
                 destinataire=None) -> dict:
    """Une ligne de l'historique des acces, meme forme sur H1 et H2."""
    ligne = {"date": _texte(date), "action": action, "evenement": evenement,
             "par": agent, "resultat": resultat, "echange_id": echange_id,
             "destinataire": destinataire}
    return {k: v for k, v in ligne.items() if v not in (None, "")}


def destinataires(acces: Iterable[dict]) -> list:
    """Etablissements auxquels des donnees ont ete transmises avec succes."""
    envois = Counter()
    dernier = {}
    for a in acces:
        code = a.get("destinataire")
        if code and a.get("resultat") in (None, "success", "OK", "PARTIEL"):
            envois[code] += 1
            dernier[code] = max(dernier.get(code, ""), a.get("date") or "")
    return [{"etablissement": ETABLISSEMENTS.get(c, c), "code": c, "transmissions": n,
             "derniere": dernier[c] or None} for c, n in sorted(envois.items())]


def reponse(*, service: str, patient: str, donnees: dict, consentement: Optional[dict],
            acces: list, origine_des_donnees: Optional[list] = None) -> dict:
    """Reponse complete a une demande de droit d'acces."""
    acces_tries = sorted(acces, key=lambda a: a.get("date") or "")
    return {
        "objet": "Communication des donnees a caractere personnel (loi 09-08, art. 7)",
        "etabli_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "responsable_du_traitement": {"code": service, "etablissement": ETABLISSEMENTS.get(service, service)},
        "patient": patient,
        "finalite": FINALITE,
        "donnees": donnees,
        "origine_des_donnees": origine_des_donnees or [],
        "consentement": consentement,
        "destinataires": destinataires(acces_tries),
        "historique_des_acces": acces_tries,
        "conservation": CONSERVATION,
        "droits": DROITS,
    }
