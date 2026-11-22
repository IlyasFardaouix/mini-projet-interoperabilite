"""
Validation de structure FHIR R5 avec la bibliothèque fhir.resources.
Usage : python valider.py sortie/bundle_AB123456.json
(Validation complète officielle : https://validator.fhir.org, version R5.)
"""
import json
import sys

from fhir.resources import get_fhir_model_class


def valider_ressource(res):
    """Renvoie la liste des erreurs (vide si la ressource est valide)."""
    try:
        get_fhir_model_class(res["resourceType"]).model_validate(res)
        return []
    except Exception as e:                       # pydantic.ValidationError
        return [f"{res.get('resourceType')} : {ligne}" for ligne in str(e).splitlines()[:6]]


def valider_bundle(bundle):
    # Valider aussi les entrees (request, fullUrl...), pas seulement l'enveloppe.
    erreurs = valider_ressource(bundle)
    if erreurs:
        return erreurs
    for e in bundle.get("entry", []):
        erreurs += valider_ressource(e["resource"])
    return erreurs


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    erreurs = valider_bundle(data) if data.get("resourceType") == "Bundle" else valider_ressource(data)
    if erreurs:
        print("NON VALIDE :")
        print("\n".join("  - " + e for e in erreurs))
        sys.exit(1)
    n = len(data.get("entry", [])) if data.get("resourceType") == "Bundle" else 1
    print(f"OK : {n} ressource(s) FHIR R5 valides")
