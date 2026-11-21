"""
stores.py — accès à la base de l'Hôpital 2 (MongoDB « hopital2 », collection « patients »)
==========================================================================================
Deux implémentations aux mêmes méthodes : le reste de l'API ne sait pas laquelle est utilisée.

  StoreMemoire   dictionnaire Python (tests, démonstration sans MongoDB)
  StoreMongo     MongoDB réel (ou mongomock dans les tests)

Un dossier patient = UN document : chaque écriture (création ou remplacement) est donc
atomique, y compris son journal d'audit (champ _audit_log, dans le même document).
"""

from __future__ import annotations

import copy
import functools
import re
from typing import Callable, Optional

SYSTEM_CIN = "urn:ma:cin"
SYSTEM_ID_H2 = "urn:clinique-al-bacar:patient"


class StoreIndisponible(Exception):
    """La base ne répond pas (ou l'écriture n'a pas pu être confirmée) → HTTP 503."""


class DejaExistant(Exception):
    """Un document avec cet identifiant existe déjà."""


def _suffixe_num(pid: str) -> int:
    m = re.fullmatch(r"P2-(\d+)", pid or "")
    return int(m.group(1)) if m else 0


def _suivant(ids) -> str:
    return f"P2-{max([_suffixe_num(p) for p in ids] + [0]) + 1:04d}"


def correspond(doc: dict, system: Optional[str], value: str) -> bool:
    """Le document porte-t-il cet identifiant ?"""
    if system in (None, SYSTEM_CIN) and doc.get("national_id") == value:
        return True
    if system in (None, SYSTEM_ID_H2) and doc.get("patient_id") == value:
        return True
    for ext in doc.get("_external_ids") or []:
        if ext.get("value") == value and system in (None, ext.get("system")):
            return True
    return False


# ═════════════════════════════════════════════════════════════════════════════
NOMS_REFERENTIELS = ("organisations", "locations", "endpoints", "devices", "practitioners", "practitioner_roles")


class StoreMemoire:
    def __init__(self, docs: Optional[list] = None, referentiels: Optional[dict] = None):
        self.refs: dict[str, list] = copy.deepcopy(referentiels or {})
        self.docs: dict[str, dict] = {d["patient_id"]: copy.deepcopy(d) for d in docs or []}

    def ping(self) -> bool:
        return True

    def referentiels(self) -> dict:
        """Annuaire de la clinique (praticiens, services, endpoints…), hors dossiers patients."""
        return copy.deepcopy(self.refs)

    def get(self, pid):
        d = self.docs.get(pid)
        return copy.deepcopy(d) if d else None

    def all(self, limit=100):
        return [copy.deepcopy(d) for d in list(self.docs.values())[:limit]]

    def find_all_by_identifier(self, system, value) -> list:
        return [copy.deepcopy(d) for d in self.docs.values() if correspond(d, system, value)]

    def find_by_identifier(self, system, value):
        r = self.find_all_by_identifier(system, value)
        return r[0] if r else None

    def next_id(self) -> str:
        return _suivant(self.docs)

    def find_by_study_uid(self, study_uid: str):
        """Patient dont une visite contient l'étude d'imagerie (passerelle DICOMweb)."""
        for d in self.docs.values():
            if any(i.get("study_uid") == study_uid
                   for v in d.get("visits", []) for i in v.get("imaging", [])):
                return copy.deepcopy(d)
        return None

    def creer(self, doc: dict, finaliser: Optional[Callable[[dict], None]] = None) -> dict:
        """Attribue P2-xxxx si patient_id est vide, appelle finaliser(doc) (ex. : audit), puis écrit."""
        attribue = not doc.get("patient_id")
        d = copy.deepcopy(doc)
        if attribue:
            d["patient_id"] = self.next_id()
        elif d["patient_id"] in self.docs:
            raise DejaExistant(d["patient_id"])
        if finaliser:
            finaliser(d)
        self.docs[d["patient_id"]] = copy.deepcopy(d)
        return d

    def remplacer(self, doc: dict) -> None:
        self.docs[doc["patient_id"]] = copy.deepcopy(doc)


# ═════════════════════════════════════════════════════════════════════════════
def _garde(fonction):
    """Toute erreur MongoDB devient StoreIndisponible (→ 503 côté API)."""
    @functools.wraps(fonction)
    def enveloppe(*args, **kwargs):
        from pymongo.errors import PyMongoError
        try:
            return fonction(*args, **kwargs)
        except (DejaExistant, StoreIndisponible):
            raise
        except PyMongoError as exc:
            raise StoreIndisponible(str(exc)) from exc
    return enveloppe


class StoreMongo:
    """Collection « patients » : un document H2 par patient."""

    def __init__(self, uri: Optional[str] = None, nom_base: str = "hopital2", client=None):
        from pymongo import MongoClient
        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[nom_base]
        self.col = self.db["patients"]
        try:                                       # base éteinte au démarrage : on réessaiera plus tard
            self.col.create_index("patient_id", unique=True)
            self.col.create_index("national_id")
        except Exception:
            pass

    @_garde
    def ping(self) -> bool:
        self.client.admin.command("ping")
        return True

    @_garde
    def referentiels(self) -> dict:
        return {n: list(self.db[n].find({}, {"_id": 0})) for n in NOMS_REFERENTIELS}

    @_garde
    def get(self, pid):
        return self.col.find_one({"patient_id": pid}, {"_id": 0})

    @_garde
    def all(self, limit=100):
        return list(self.col.find({}, {"_id": 0}).limit(limit))

    @_garde
    def find_all_by_identifier(self, system, value) -> list:
        filtres = []
        if system in (None, SYSTEM_CIN):
            filtres.append({"national_id": value})
        if system in (None, SYSTEM_ID_H2):
            filtres.append({"patient_id": value})
        filtres.append({"_external_ids": {"$elemMatch": {"value": value,
                                                         **({"system": system} if system else {})}}})
        return list(self.col.find({"$or": filtres}, {"_id": 0}))

    def find_by_identifier(self, system, value):
        r = self.find_all_by_identifier(system, value)
        return r[0] if r else None

    @_garde
    def next_id(self) -> str:
        return _suivant(d["patient_id"] for d in self.col.find({}, {"patient_id": 1, "_id": 0}))

    @_garde
    def find_by_study_uid(self, study_uid: str):
        """Patient dont une visite contient l'étude d'imagerie (passerelle DICOMweb)."""
        return self.col.find_one({"visits.imaging.study_uid": study_uid}, {"_id": 0})

    @_garde
    def creer(self, doc: dict, finaliser: Optional[Callable[[dict], None]] = None) -> dict:
        from pymongo.errors import DuplicateKeyError
        attribue = not doc.get("patient_id")
        for _ in range(5):                         # deux créations simultanées : on retente avec l'id suivant
            d = copy.deepcopy(doc)
            if attribue:
                d["patient_id"] = self.next_id()
            if finaliser:
                finaliser(d)
            try:
                self.col.insert_one(copy.deepcopy(d))
                return d
            except DuplicateKeyError:
                if not attribue:
                    raise DejaExistant(d["patient_id"])
        raise StoreIndisponible("Impossible d'attribuer un identifiant patient (conflits répétés).")

    @_garde
    def remplacer(self, doc: dict) -> None:
        self.col.replace_one({"patient_id": doc["patient_id"]}, copy.deepcopy(doc), upsert=True)


# ═════════════════════════════════════════════════════════════════════════════
class StoreMongoChiffre(StoreMongo):
    """MongoDB avec dossiers chiffrés au repos (securite/chiffrement.py, AES-256-GCM).

    Un document en base ne contient plus que :
      patient_id   identifiant technique P2-xxxx (non nominatif), en clair pour les accès directs
      _idx         index aveugles (HMAC) : CIN, identifiants externes, études d'imagerie
      _cle         identifiant de la clé utilisée
      _chiffre     le dossier COMPLET chiffré (identité, visites, consentement, audit…)

    La clé n'est pas dans la base (H2_CLE_CHIFFREMENT, .env du poste) : une copie de la
    base ou d'une sauvegarde est illisible. Le chiffre est lié au patient_id : recopié
    sur un autre dossier, il ne se déchiffre plus. Les anciens documents en clair restent
    lisibles et sont chiffrés à leur prochaine écriture (ou par chiffrer_mongo.py).
    """

    def __init__(self, uri: Optional[str] = None, nom_base: str = "hopital2", client=None, *, chiffreur):
        super().__init__(uri, nom_base, client)
        self.chiffreur = chiffreur
        try:
            for champ in ("_idx.cin", "_idx.ext", "_idx.etudes"):
                self.col.create_index(champ)
        except Exception:
            pass

    # -- conversion --------------------------------------------------------
    def _index(self, doc: dict) -> dict:
        c = self.chiffreur
        externes = set()
        for e in doc.get("_external_ids") or []:
            if e.get("value"):
                externes.add(c.index("ext", e.get("system") or "", e["value"]))
                externes.add(c.index("ext", "", e["value"]))          # recherche sans système
        etudes = {c.index("etude", i["study_uid"]) for v in doc.get("visits") or []
                  for i in v.get("imaging") or [] if i.get("study_uid")}
        return {"cin": c.index("cin", doc["national_id"]) if doc.get("national_id") else None,
                "ext": sorted(externes), "etudes": sorted(etudes)}

    def _vers_base(self, doc: dict) -> dict:
        from bson import json_util
        pid = doc["patient_id"]
        return {"patient_id": pid, "_idx": self._index(doc), "_cle": self.chiffreur.courante,
                # JSON étendu MongoDB : dates et types BSON conservés à l'identique.
                "_chiffre": self.chiffreur.chiffrer(json_util.dumps(doc).encode("utf-8"), "patient:" + pid)}

    def _depuis_base(self, brut: Optional[dict]) -> Optional[dict]:
        from bson import json_util
        from securite.chiffrement import ErreurChiffrement
        if brut is None:
            return None
        brut.pop("_id", None)
        if "_chiffre" not in brut:
            return brut                                    # ancien document en clair
        try:
            return json_util.loads(self.chiffreur.dechiffrer(brut["_chiffre"], "patient:" + brut["patient_id"]))
        except ErreurChiffrement as exc:
            raise StoreIndisponible(f"Dossier {brut.get('patient_id')} illisible : clé absente "
                                    "ou donnée altérée.") from exc

    # -- lecture -----------------------------------------------------------
    @_garde
    def get(self, pid):
        return self._depuis_base(self.col.find_one({"patient_id": pid}, {"_id": 0}))

    @_garde
    def all(self, limit=100):
        return [self._depuis_base(d) for d in self.col.find({}, {"_id": 0}).limit(limit)]

    @_garde
    def find_all_by_identifier(self, system, value) -> list:
        c = self.chiffreur
        filtres = []
        if system in (None, SYSTEM_CIN):
            filtres += [{"_idx.cin": c.index("cin", value)}, {"national_id": value}]
        if system in (None, SYSTEM_ID_H2):
            filtres.append({"patient_id": value})
        filtres += [{"_idx.ext": c.index("ext", system or "", value)},
                    {"_external_ids": {"$elemMatch": {"value": value, **({"system": system} if system else {})}}}]
        return [self._depuis_base(d) for d in self.col.find({"$or": filtres}, {"_id": 0})]

    @_garde
    def find_by_study_uid(self, study_uid: str):
        return self._depuis_base(self.col.find_one(
            {"$or": [{"_idx.etudes": self.chiffreur.index("etude", study_uid)},
                     {"visits.imaging.study_uid": study_uid}]}, {"_id": 0}))

    # -- écriture ----------------------------------------------------------
    @_garde
    def creer(self, doc: dict, finaliser: Optional[Callable[[dict], None]] = None) -> dict:
        from pymongo.errors import DuplicateKeyError
        attribue = not doc.get("patient_id")
        for _ in range(5):
            d = copy.deepcopy(doc)
            if attribue:
                d["patient_id"] = self.next_id()
            if finaliser:
                finaliser(d)
            try:
                self.col.insert_one(self._vers_base(d))
                return d
            except DuplicateKeyError:
                if not attribue:
                    raise DejaExistant(d["patient_id"])
        raise StoreIndisponible("Impossible d'attribuer un identifiant patient (conflits répétés).")

    @_garde
    def remplacer(self, doc: dict) -> None:
        self.col.replace_one({"patient_id": doc["patient_id"]}, self._vers_base(doc), upsert=True)

    @_garde
    def rechiffrer_tout(self) -> dict:
        """Chiffre les documents encore en clair et ceux d'une ancienne clé (rotation)."""
        bilan = {"chiffres": 0, "deja": 0}
        for brut in list(self.col.find({}, {"_id": 0})):
            if "_chiffre" in brut and not self.chiffreur.a_rechiffrer(brut["_chiffre"]):
                bilan["deja"] += 1
                continue
            self.remplacer(self._depuis_base(brut))
            bilan["chiffres"] += 1
        return bilan
