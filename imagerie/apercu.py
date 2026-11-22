"""Aperçu d'une image DICOM pour l'écran de démonstration : DICOM -> PNG, sans bibliothèque d'images.

Ne sait lire que les images simples que produit ce projet (et que fournissent la plupart des appareils
de photographie du fond d'oeil) : pixels non compressés, 8 bits (gris ou RVB) ou 16 bits (gris).
Toute autre image lève `ErreurApercu` : l'écran affiche alors « aperçu indisponible », jamais d'erreur serveur.

Le fichier DICOM vient d'un PACS, donc on ne lui fait pas confiance : taille d'image bornée, lecture sans
exécution de code, aucune information du dossier (nom, date de naissance) dans l'image produite.
"""

from __future__ import annotations

import io
import struct
import zlib
from array import array

from pydicom import dcmread

TAILLE_MAX = 4096                    # pixels par côté : au-delà, on refuse (mémoire)
SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"


class ErreurApercu(ValueError):
    """Image DICOM que l'aperçu ne sait pas afficher."""


def _morceau(type_: bytes, donnees: bytes) -> bytes:
    return (struct.pack(">I", len(donnees)) + type_ + donnees
            + struct.pack(">I", zlib.crc32(type_ + donnees) & 0xFFFFFFFF))


def _png(largeur: int, hauteur: int, canaux: int, pixels: bytes) -> bytes:
    """PNG 8 bits ; canaux : 1 (gris) ou 3 (RVB). `pixels` : lignes consécutives, sans remplissage."""
    type_couleur = 0 if canaux == 1 else 2
    ligne = largeur * canaux
    brut = b"".join(b"\x00" + pixels[y * ligne:(y + 1) * ligne] for y in range(hauteur))
    return (SIGNATURE_PNG
            + _morceau(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, type_couleur, 0, 0, 0))
            + _morceau(b"IDAT", zlib.compress(brut, 6))
            + _morceau(b"IEND", b""))


def png_depuis_dicom(octets: bytes) -> bytes:
    try:
        ds = dcmread(io.BytesIO(octets), force=False)
        syntaxe = ds.file_meta.TransferSyntaxUID
        if syntaxe.is_compressed:
            raise ErreurApercu("image compressée : aperçu indisponible")
        lignes, colonnes = int(ds.Rows), int(ds.Columns)
        canaux, bits = int(ds.SamplesPerPixel), int(ds.BitsAllocated)
        photo = str(ds.PhotometricInterpretation)
        donnees = bytes(ds.PixelData)
        planaire = int(getattr(ds, "PlanarConfiguration", 0))
        image_multi = int(getattr(ds, "NumberOfFrames", 1) or 1) > 1
    except ErreurApercu:
        raise
    except Exception as exc:                                  # fichier illisible ou incomplet
        raise ErreurApercu("fichier DICOM illisible") from exc

    if not (0 < lignes <= TAILLE_MAX and 0 < colonnes <= TAILLE_MAX):
        raise ErreurApercu("dimensions d'image refusées")
    if image_multi:
        raise ErreurApercu("image à plusieurs plans : aperçu indisponible")
    if canaux == 3 and bits == 8 and photo == "RGB":
        attendu = lignes * colonnes * 3
        if len(donnees) < attendu:
            raise ErreurApercu("pixels incomplets")
        donnees = donnees[:attendu]
        if planaire == 1:                                     # plans R, V, B séparés -> entrelacés
            n = lignes * colonnes
            entrelace = bytearray(attendu)
            for c in range(3):
                entrelace[c::3] = donnees[c * n:(c + 1) * n]
            donnees = bytes(entrelace)
        return _png(colonnes, lignes, 3, donnees)
    if canaux == 1 and photo in ("MONOCHROME1", "MONOCHROME2"):
        n = lignes * colonnes
        if bits == 8:
            if len(donnees) < n:
                raise ErreurApercu("pixels incomplets")
            gris = bytearray(donnees[:n])
        elif bits == 16:
            if len(donnees) < 2 * n:
                raise ErreurApercu("pixels incomplets")
            valeurs = array("H" if int(getattr(ds, "PixelRepresentation", 0)) == 0 else "h")
            valeurs.frombytes(donnees[:2 * n])
            if struct.pack("=H", 1) != struct.pack("<H", 1):  # machine « big endian » : octets à inverser
                valeurs.byteswap()
            bas, haut = min(valeurs), max(valeurs)
            etendue = (haut - bas) or 1
            gris = bytearray((v - bas) * 255 // etendue for v in valeurs)
        else:
            raise ErreurApercu("profondeur de pixel non gérée")
        if photo == "MONOCHROME1":                            # 0 = blanc
            gris = bytearray(255 - v for v in gris)
        return _png(colonnes, lignes, 1, bytes(gris))
    raise ErreurApercu("format d'image non géré")
