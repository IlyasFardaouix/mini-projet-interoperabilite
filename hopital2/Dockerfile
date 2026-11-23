# Image de l'API H2 (Clinique Al Bacar).
#
# Le contexte de construction est la RACINE du depot, pas ce dossier : l'image a
# besoin du package securite/ qui vit un niveau au-dessus. Voir le service `api`
# de docker-compose.yml (context: .. / dockerfile: hopital2/Dockerfile).
FROM python:3.12-slim

# Un conteneur qui tourne en root donne les droits root sur les volumes montes.
# L'application n'a besoin d'aucun privilege : on cree un utilisateur dedie.
RUN useradd --create-home --uid 10001 api

WORKDIR /app

# Les dependances d'abord : cette couche reste en cache tant que le fichier ne
# change pas.
COPY hopital2/requirements.txt hopital2/requirements.txt
RUN pip install --no-cache-dir -r hopital2/requirements.txt

# Couche de securite commune aux deux hopitaux : jetons et portees, journal
# d'acces, en-tetes de securite, TLS.
COPY securite/ securite/
# Imagerie DICOM commune (passerelle DICOMweb), sans ses tests.
COPY imagerie/__init__.py imagerie/dicom.py imagerie/dicomweb.py imagerie/passerelle.py imagerie/
# Interface du personnel (/ui) : importee au demarrage par api_h2.py, l'API ne
# demarre pas sans elle.
COPY interface/ interface/

# Seulement les fichiers dont le service a besoin. Les fichiers test_*.py,
# demo.py et les generateurs de donnees n'ont rien a faire dans une image :
# ils agrandissent la surface d'attaque sans rien apporter en production.
COPY hopital2/api_h2.py hopital2/echange.py hopital2/stores.py \
     hopital2/adaptateur_fhir_h2.py hopital2/adaptateur_h2_fhir.py \
     hopital2/client_envoi.py hopital2/exemples_h1.py hopital2/ui_h2.py hopital2/
COPY hopital2/data/ hopital2/data/

# Le journal d'acces est ecrit par l'application : le dossier doit lui appartenir.
RUN mkdir -p /app/journaux && chown -R api:api /app/journaux

USER api
WORKDIR /app/hopital2
EXPOSE 8002

# `--host 0.0.0.0` designe ici les interfaces DU CONTENEUR : ce qui est joignable
# depuis l'exterieur est decide par le `ports:` de docker-compose.yml.
# Les certificats sont montés au lancement. Sans eux, le service ne démarre pas.
CMD ["uvicorn", "api_h2:app", "--host", "0.0.0.0", "--port", "8002", "--ssl-keyfile", "/app/securite/certificats/h2.key.pem", "--ssl-certfile", "/app/securite/certificats/h2.cert.pem"]
