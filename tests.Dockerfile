# Image de TEST : toutes les suites du depot (securite, imagerie, H1, H2) dans un conteneur.
# Contexte = racine du depot. Lancement : voir docker-compose.tests.yml et lancer_tests_docker.sh.
# Contrairement aux images des API, celle-ci embarque les tests : ne jamais la publier ni
# la deployer. Son filtre de contexte est tests.Dockerfile.dockerignore (et non .dockerignore).
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 testeur
WORKDIR /app

# Dependances d'abord : couche en cache tant que les fichiers requirements ne changent pas.
COPY securite/requirements.txt securite/requirements.txt
COPY hopital1/requirements.txt hopital1/requirements.txt
COPY hopital2/requirements.txt hopital2/requirements.txt
RUN pip install --no-cache-dir -r securite/requirements.txt -r hopital1/requirements.txt \
    -r hopital2/requirements.txt

COPY . .
RUN chown -R testeur:testeur /app
USER testeur

CMD ["sh", "lancer_tests_docker.sh"]
