"""Fichiers DICOM : creation d'etudes de demonstration, lecture, desidentification.

Les donnees du projet sont fictives : aucune image reelle de patient ne doit
entrer dans le depot. `generer_etude` fabrique des photographies du fond d'oeil
synthetiques (disque et vaisseaux dessines), au format DICOM « Ophthalmic
Photography 8 Bit Image Storage », avec les MEMES identifiants d'etude que les
ImagingStudy deja presents dans les donnees de H2 : un ImagingStudy recu par
FHIR designe donc une etude reellement recuperable par DICOMweb.
"""

from __future__ import annotations

import copy
import io
import math
import uuid
from datetime import datetime
from typing import Iterable, Optional

from pydicom import dcmread
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID

# Ophthalmic Photography 8 Bit Image Storage
SOP_PHOTO_OPHTALMO = "1.2.840.10008.5.1.4.1.1.77.1.5.1"
TAILLE_IMAGE = 128                                   # pixels : demonstration, pas diagnostic


def uid_derive(*morceaux: str) -> str:
    """UID DICOM stable (racine 2.25 = UUID), calcule a partir d'un texte."""
    return "2.25." + str(uuid.uuid5(uuid.NAMESPACE_OID, "|".join(morceaux)).int)


def uid_serie(study_uid: str, numero: int = 1) -> str:
    return uid_derive(study_uid, "serie", str(numero))


def uid_instance(study_uid: str, numero: int) -> str:
    return uid_derive(study_uid, "instance", str(numero))


def _nom_dicom(nom: str, prenom: str) -> str:
    return f"{(nom or '').upper()}^{prenom or ''}"


def _date_dicom(valeur) -> str:
    if not valeur:
        return ""
    if isinstance(valeur, datetime):
        return valeur.strftime("%Y%m%d")
    return str(valeur)[:10].replace("-", "")


def _fond_d_oeil(lateralite: str, graine: int) -> bytes:
    """Image RGB synthetique : fond orange, papille claire, quatre vaisseaux."""
    n = TAILLE_IMAGE
    centre = n / 2
    papille_x = centre + (n * 0.18 if lateralite == "R" else -n * 0.18)
    pixels = bytearray(n * n * 3)
    for y in range(n):
        for x in range(n):
            i = (y * n + x) * 3
            r = math.hypot(x - centre, y - centre)
            if r > centre - 2:
                continue                                       # hors champ : noir
            rouge, vert, bleu = 190 - int(r / 2), 80 - int(r / 4), 30
            d = math.hypot(x - papille_x, y - centre)
            if d < n * 0.07:
                rouge, vert, bleu = 250, 220, 150              # papille
            else:
                angle = math.atan2(y - centre, x - papille_x)
                for k in range(4):
                    cible = (k * math.pi / 2) + 0.6 + (graine % 7) * 0.05
                    if abs(math.sin(angle - cible)) < 0.04 and d < n * 0.45:
                        rouge, vert, bleu = 140, 20, 20        # vaisseau
            pixels[i:i + 3] = bytes((max(rouge, 0), max(vert, 0), bleu))
    return bytes(pixels)


def generer_etude(patient: dict, etude: dict, *, etablissement: str) -> list:
    """Instances DICOM d'une etude de photographie du fond d'oeil.

    patient : id, nom, prenom, naissance (AAAA-MM-JJ), sexe (M/F/O)
    etude   : study_uid, accession, description, instances (nombre), date (datetime)
    Les instances alternent oeil droit / oeil gauche.
    """
    study_uid = etude["study_uid"]
    serie = uid_serie(study_uid)
    date = etude.get("date") or datetime(2026, 1, 1, 9, 0)
    nombre = max(1, int(etude.get("instances") or 1))
    instances = []
    for numero in range(1, nombre + 1):
        lateralite = "R" if numero % 2 else "L"
        sop = uid_instance(study_uid, numero)

        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = SOP_PHOTO_OPHTALMO
        meta.MediaStorageSOPInstanceUID = sop
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

        ds = Dataset()
        ds.file_meta = meta
        ds.SOPClassUID = SOP_PHOTO_OPHTALMO
        ds.SOPInstanceUID = sop
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = serie
        ds.Modality = "OP"
        ds.PatientName = _nom_dicom(patient.get("nom"), patient.get("prenom"))
        ds.PatientID = str(patient.get("id") or "")
        ds.PatientBirthDate = _date_dicom(patient.get("naissance"))
        ds.PatientSex = {"M": "M", "F": "F"}.get(str(patient.get("sexe") or "").upper(), "O")
        ds.StudyDate = ds.SeriesDate = ds.ContentDate = date.strftime("%Y%m%d")
        ds.StudyTime = ds.SeriesTime = ds.ContentTime = date.strftime("%H%M%S")
        ds.AccessionNumber = str(etude.get("accession") or "")[:16]
        ds.StudyDescription = str(etude.get("description") or "")[:64]
        ds.SeriesDescription = "Retinographie couleur"
        ds.StudyID = "1"
        ds.SeriesNumber = 1
        ds.InstanceNumber = numero
        ds.ImageLaterality = lateralite
        ds.InstitutionName = etablissement[:64]
        ds.Manufacturer = "Donnees de demonstration"
        ds.BurnedInAnnotation = "NO"
        ds.ImageType = ["ORIGINAL", "PRIMARY"]
        ds.SamplesPerPixel = 3
        ds.PhotometricInterpretation = "RGB"
        ds.PlanarConfiguration = 0
        ds.Rows = ds.Columns = TAILLE_IMAGE
        ds.BitsAllocated = ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.PixelData = _fond_d_oeil(lateralite, numero)
        instances.append(ds)
    return instances


def vers_octets(ds: Dataset) -> bytes:
    tampon = io.BytesIO()
    ds.save_as(tampon, enforce_file_format=True)
    return tampon.getvalue()


def depuis_octets(octets: bytes) -> Dataset:
    return dcmread(io.BytesIO(octets))


def resume(ds: Dataset) -> dict:
    return {"study_uid": str(ds.get("StudyInstanceUID", "")),
            "series_uid": str(ds.get("SeriesInstanceUID", "")),
            "sop_uid": str(ds.get("SOPInstanceUID", "")),
            "patient_id": str(ds.get("PatientID", "")),
            "modalite": str(ds.get("Modality", "")),
            "lateralite": str(ds.get("ImageLaterality", ""))}


# ---------------------------------------------------------------------------
# Desidentification : profil de base DICOM PS3.15 annexe E, option « Retain UIDs »
# ---------------------------------------------------------------------------
# Les UID sont conserves : ils relient l'image a l'ImagingStudy FHIR. Les dates
# d'examen aussi (utiles au suivi). Tout ce qui identifie la personne ou les
# soignants est retire ou remplace.
ATTRIBUTS_RETIRES = (
    "PatientBirthDate", "PatientBirthTime", "PatientAddress", "PatientTelephoneNumbers",
    "OtherPatientIDs", "OtherPatientIDsSequence", "OtherPatientNames", "PatientMotherBirthName",
    "MilitaryRank", "EthnicGroup", "PatientComments", "AdditionalPatientHistory",
    "ReferringPhysicianName", "PerformingPhysicianName", "NameOfPhysiciansReadingStudy",
    "OperatorsName", "PhysiciansOfRecord", "RequestingPhysician",
    "InstitutionAddress", "InstitutionalDepartmentName", "StationName", "DeviceSerialNumber",
    "AccessionNumber", "StudyID", "IssuerOfPatientID",
)


def desidentifier(ds: Dataset, pseudonyme: str) -> Dataset:
    """Copie desidentifiee : nom et identifiant remplaces par un pseudonyme."""
    copie = copy.deepcopy(ds)
    for nom in ATTRIBUTS_RETIRES:
        if nom in copie:
            delattr(copie, nom)
    copie.remove_private_tags()
    copie.PatientName = pseudonyme
    copie.PatientID = pseudonyme
    copie.InstitutionName = "DESIDENTIFIE"
    copie.PatientIdentityRemoved = "YES"
    copie.DeidentificationMethod = "PS3.15 profil de base, UID conserves"
    methodes = []
    for code, sens in (("113100", "Basic Application Confidentiality Profile"),
                       ("113110", "Retain UIDs Option")):
        item = Dataset()
        item.CodeValue, item.CodingSchemeDesignator, item.CodeMeaning = code, "DCM", sens
        methodes.append(item)
    copie.DeidentificationMethodCodeSequence = Sequence(methodes)
    return copie


def metadonnees_json(instances: Iterable[Dataset]) -> list:
    """Reponse « metadata » DICOMweb (DICOM JSON), sans les pixels."""
    sortie = []
    for ds in instances:
        sans_pixels = copy.copy(ds)
        if "PixelData" in sans_pixels:
            del sans_pixels.PixelData
        sortie.append(sans_pixels.to_json_dict())
    return sortie


def verifier_etude(instances: Iterable[Dataset], study_uid: str) -> Optional[str]:
    """Message d'erreur si une instance n'appartient pas a l'etude attendue."""
    for ds in instances:
        if str(ds.get("StudyInstanceUID", "")) != study_uid:
            return "instance etrangere a l'etude demandee (StudyInstanceUID different)"
        if not ds.get("SOPInstanceUID"):
            return "instance sans SOPInstanceUID"
    return None
