#!/bin/sh
# Lance TOUTES les suites de tests dans le conteneur `tests` (voir docker-compose.tests.yml).
# Les suites se lancent chacune depuis leur dossier : H1 et H2 ont des modules de meme nom
# (conftest, tests/...) qui ne se melangent pas dans une seule session pytest.
# Code de sortie : 0 seulement si tout passe.

echec=0
etape() {
  titre="$1"; shift
  echo ""; echo "=== $titre ==="
  "$@" || { echo ">>> ECHEC : $titre"; echec=1; }
}

etape "Securite + imagerie" python -m pytest securite/tests imagerie/tests -q
etape "Hopital 2 (API, adaptateurs, client d'envoi, chiffrement, DICOM)" sh -c 'cd hopital2 && python -m pytest -q'
if [ -n "$ORACLE_TEST_DSN" ]; then
  echo ""; echo "Oracle de test : $ORACLE_TEST_DSN (tests sur vraie base INCLUS)"
else
  echo ""; echo "ATTENTION : ORACLE_TEST_DSN absent, les tests Oracle seront ignores."
fi
etape "Hopital 1 (adaptateurs, API, client d'envoi, echange croise, Oracle reel)" sh -c 'cd hopital1 && python -m pytest tests -q -rs'
etape "Audit de securite du depot" python securite/outils/verifier_securite.py

echo ""
if [ "$echec" -eq 0 ]; then echo "=== TOUT EST VERT ==="; else echo "=== AU MOINS UNE ETAPE EN ECHEC ==="; fi
exit "$echec"
