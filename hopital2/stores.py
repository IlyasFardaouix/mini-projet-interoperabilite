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
