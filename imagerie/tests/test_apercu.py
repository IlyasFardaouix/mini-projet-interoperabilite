"""Aperçu PNG des images DICOM (écran de démonstration)."""
import struct
import zlib
from datetime import datetime

import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, JPEGBaseline8Bit

from imagerie.apercu import ErreurApercu, SIGNATURE_PNG, png_depuis_dicom
from imagerie.dicom import generer_etude, vers_octets

PATIENT = {"id": "P2-0051", "nom": "Alaoui", "prenom": "Youssef", "naissance": "1968-04-12", "sexe": "M"}


def etude():
    return [vers_octets(ds) for ds in generer_etude(
        PATIENT, {"study_uid": "2.25.1", "instances": 2, "date": datetime(2026, 9, 20)}, etablissement="Clinique")]


def lire_png(png):
    assert png.startswith(SIGNATURE_PNG)
    morceaux, i = {}, len(SIGNATURE_PNG)
    while i < len(png):
        n, type_ = struct.unpack(">I4s", png[i:i + 8])
        donnees = png[i + 8:i + 8 + n]
        assert struct.unpack(">I", png[i + 8 + n:i + 12 + n])[0] == zlib.crc32(type_ + donnees) & 0xFFFFFFFF
        morceaux.setdefault(type_, b"")
        morceaux[type_] += donnees
        i += 12 + n
    largeur, hauteur, profondeur, couleur = struct.unpack(">IIBB", morceaux[b"IHDR"][:10])
    return largeur, hauteur, profondeur, couleur, zlib.decompress(morceaux[b"IDAT"])


def test_image_de_demonstration_donne_un_png_valide():
    largeur, hauteur, profondeur, couleur, brut = lire_png(png_depuis_dicom(etude()[0]))
    assert (largeur, hauteur, profondeur, couleur) == (128, 128, 8, 2)
    assert len(brut) == 128 * (1 + 128 * 3)


def test_le_png_ne_contient_aucune_information_du_dossier():
    png = png_depuis_dicom(etude()[0])
    for secret in (b"ALAOUI", b"Alaoui", b"Youssef", b"1968", b"P2-0051"):
        assert secret not in png


def fichier(*, bits=16, photo="MONOCHROME2", canaux=1, pixels=None, syntaxe=ExplicitVRLittleEndian, lignes=4, colonnes=4):
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = syntaxe
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.file_meta.MediaStorageSOPInstanceUID = "2.25.2"
    ds.SOPClassUID, ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPClassUID, "2.25.2"
    ds.Rows, ds.Columns, ds.SamplesPerPixel, ds.BitsAllocated = lignes, colonnes, canaux, bits
    ds.BitsStored, ds.HighBit, ds.PixelRepresentation, ds.PhotometricInterpretation = bits, bits - 1, 0, photo
    if syntaxe.is_compressed:
        from pydicom.encaps import encapsulate
        ds.PixelData = encapsulate([b"\xff\xd8\xff\xd9"])
        ds["PixelData"].VR = "OB"
    else:
        ds.PixelData = pixels if pixels is not None else bytes(lignes * colonnes * canaux * bits // 8)
    return vers_octets(ds)


def test_gris_16_bits_etire_sur_0_255():
    pixels = struct.pack("<16H", *range(0, 4000, 250))
    _, _, profondeur, couleur, brut = lire_png(png_depuis_dicom(fichier(pixels=pixels)))
    assert (profondeur, couleur) == (8, 0)
    lignes = [brut[i * 5 + 1:(i + 1) * 5] for i in range(4)]
    assert lignes[0][0] == 0 and lignes[3][3] == 255


def test_monochrome1_est_inverse():
    gris = fichier(bits=8, photo="MONOCHROME1", pixels=bytes([0] * 15 + [255]))
    brut = lire_png(png_depuis_dicom(gris))[4]
    assert brut[1] == 255 and brut[-1] == 0


@pytest.mark.parametrize("octets, motif", [
    (b"pas du dicom", "illisible"),
    (fichier(syntaxe=JPEGBaseline8Bit), "compress"),
    (fichier(bits=8, pixels=b"\x00" * 3), "incomplets"),
    (fichier(bits=32, canaux=1), "non géré"),
    (fichier(lignes=5000, colonnes=5000, bits=8), "dimensions"),
])
def test_images_non_affichables_levent_une_erreur_claire(octets, motif):
    with pytest.raises(ErreurApercu, match=motif):
        png_depuis_dicom(octets)
