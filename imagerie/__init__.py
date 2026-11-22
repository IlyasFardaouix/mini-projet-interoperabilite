"""Imagerie DICOM commune a H1 et H2.

Les Bundles FHIR ne transportent que les metadonnees d'imagerie (ImagingStudy).
Les images elles-memes sont des fichiers DICOM conserves dans un PACS (Orthanc)
et echangees en DICOMweb :

    H2 : PACS Orthanc <-- passerelle /dicom-web (jeton + portee + consentement) <-- H1
                                                                                  |
    H1 : PACS Orthanc <------------------- recuperer_imagerie.py ------------------+

- `dicom.py`     : creation d'etudes DICOM de demonstration, lecture,
                   desidentification (profil de base PS3.15).
- `dicomweb.py`  : multipart DICOMweb, entrepots (Orthanc, memoire) et client
                   de la passerelle de l'autre hopital.
- `passerelle.py`: routes /dicom-web protegees, branchees sur chaque API.

Le PACS n'est jamais expose directement : il ecoute sur la boucle locale, avec
authentification, et seule la passerelle de l'API y accede.
"""
