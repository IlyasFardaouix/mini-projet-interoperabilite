"""
Tests des deux adaptateurs H1 <-> FHIR, SANS Oracle.
Lancer depuis le dossier adaptateur_h1 :   python -m pytest -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C                                     # noqa: E402
import fhir_to_h1 as RET                               # noqa: E402
import h1_to_fhir as ALL                               # noqa: E402
from donnees import dossier                            # noqa: E402
from valider import valider_bundle                     # noqa: E402

EXEMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "exemples", "retour_clinique_youssef.json")


def ressources(bundle, t):
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == t]


# ============================ ALLER : H1 -> FHIR ============================
def test_S1_bundle_valide_fhir_r5():
    bundle, alertes, rejets = ALL.dossier_vers_bundle(dossier("S1"))
    assert bundle["type"] == "transaction"
    assert valider_bundle(bundle) == []
    assert rejets == []


def test_S1_patient_conforme_au_contrat():
    bundle, _, _ = ALL.dossier_vers_bundle(dossier("S1"))
    p = ressources(bundle, "Patient")[0]
    assert {"system": C.SYS_CIN, "value": "AB123456", "use": "official"} in p["identifier"]
    assert p["gender"] == "male"
    assert p["birthDate"] == "1968-04-12"
    assert p["telecom"][0]["value"] == "+212612345678"
    assert p["address"] == [{"use": "home", "city": "Settat", "country": "MA"}]  # pas de rue
    assert p["meta"]["source"] == C.CHU["source"]


def test_S1_encounter_observation_servicerequest():
    bundle, _, _ = ALL.dossier_vers_bundle(dossier("S1"))
    enc = ressources(bundle, "Encounter")[0]
    assert enc["class"][0]["coding"][0]["code"] == "AMB"
    assert enc["diagnosis"][0]["condition"][0]["concept"]["coding"][0]["code"] == "E11"
    assert enc["admission"]["destination"]["display"] == C.CLINIQUE["nom"]
    obs = {o["code"]["coding"][0]["code"]: o for o in ressources(bundle, "Observation")}
    pression = obs["85354-9"]
    composants = {c["code"]["coding"][0]["code"]: c for c in pression["component"]}
    assert composants["8480-6"]["valueQuantity"]["value"] == 138
    assert composants["8462-4"]["valueQuantity"]["value"] == 85
    assert obs["4548-4"]["interpretation"][0]["coding"][0]["code"] == "H"   # HbA1c 8.2 %
    assert C.LOINC_GROUPE_SANGUIN in obs
    sr = ressources(bundle, "ServiceRequest")[0]
    assert sr["intent"] == "order" and sr["performer"][0]["display"] == C.CLINIQUE["nom"]


def test_references_internes_resolues():
    """Chaque référence 'urn:uuid:...' pointe vers une entrée du Bundle."""
    bundle, _, _ = ALL.dossier_vers_bundle(dossier("S1"))
    urls = {e["fullUrl"] for e in bundle["entry"]}
    texte = json.dumps(bundle)
    import re
    for ref in re.findall(r'"reference": "(urn:uuid:[^"]+)"', texte):
        assert ref in urls


def test_export_rejouable_sans_doublon():
    """Cas D15 : deux exports du même dossier => mêmes fullUrl / ifNoneExist."""
    b1, _, _ = ALL.dossier_vers_bundle(dossier("S1"), maintenant="2026-11-20T10:00:00+00:00")
    b2, _, _ = ALL.dossier_vers_bundle(dossier("S1"), maintenant="2026-11-20T10:00:00+00:00")
    assert b1 == b2
    assert all("ifNoneExist" in e["request"] for e in b1["entry"])


def test_S1_allergie_transmise():
    bundle, _, _ = ALL.dossier_vers_bundle(dossier("S1"))
    al = ressources(bundle, "AllergyIntolerance")[0]
    assert al["code"]["text"] == "Fluorescéine" and al["criticality"] == "high"


def test_D1_consentement_refuse():
    with pytest.raises(ALL.ConsentementRefuse) as e:
        ALL.dossier_vers_bundle(dossier("D1"))
    oo = ALL.vers_operation_outcome(e.value)
    assert oo["issue"][0]["code"] == "forbidden" and e.value.http == 403


def test_D4_sans_cin_identifiant_ipp_et_alerte():
    bundle, alertes, _ = ALL.dossier_vers_bundle(dossier("D4"))
    p = ressources(bundle, "Patient")[0]
    assert [i["system"] for i in p["identifier"]] == [C.SYS_IPP_CHU]
    assert any("pas de CIN" in a for a in alertes)
    assert valider_bundle(bundle) == []


def test_D7_mineure():
    _, alertes, _ = ALL.dossier_vers_bundle(dossier("D7"))
    assert any("mineur" in a for a in alertes)


def test_D8_date_naissance_manquante():
    with pytest.raises(ALL.DonneeInvalide):
        ALL.dossier_vers_bundle(dossier("D8"))


def test_D9_code_inconnu_texte_seul():
    bundle, alertes, _ = ALL.dossier_vers_bundle(dossier("D9"))
    concept = ressources(bundle, "Encounter")[0]["diagnosis"][0]["condition"][0]["concept"]
    assert all(c["system"] != C.ICD10 for c in concept["coding"])
    assert concept["text"]
    assert any("file de revue" in a for a in alertes)


def test_D10_mesure_sans_unite_rejetee():
    bundle, _, rejets = ALL.dossier_vers_bundle(dossier("D10"))
    assert any("sans unité" in r for r in rejets)
    assert all(o["code"]["coding"][0]["code"] != "2339-0" for o in ressources(bundle, "Observation"))


def test_D11_valeur_impossible_rejetee():
    bundle, _, rejets = ALL.dossier_vers_bundle(dossier("D11"))
    assert any("hors plage" in r for r in rejets)
    codes = [o["code"]["coding"][0]["code"] for o in ressources(bundle, "Observation")]
    assert "59408-5" not in codes and "8867-4" in codes      # la FC, elle, passe


def test_D12_sortie_avant_admission():
    bundle, _, rejets = ALL.dossier_vers_bundle(dossier("D12"))
    assert ressources(bundle, "Encounter") == []
    assert any("sortie avant" in r for r in rejets)


# ============================ RETOUR : FHIR -> H1 ===========================
def charger_exemple():
    with open(EXEMPLE, encoding="utf-8") as f:
        return json.load(f)


def test_retour_exemple_valide_fhir_r5():
    assert valider_bundle(charger_exemple()) == []


def test_retour_vers_tables_h1():
    res = RET.bundle_vers_lignes(charger_exemple(),
                                 trouver_ipp=lambda cin, ipp, l: "P1-0106" if cin == "AB123456" else None)
    assert len(res["sejour"]) == 1
    s = res["sejour"][0]
    assert s["ipp"] == "P1-0106" and s["etablissement"] == "Clinique Al Baçar"
    assert s["type_sejour"] == "CONS" and s["medecin"] == "Dr Samir Kabbaj"
    assert len(s["id_sejour"]) <= 12
    assert res["diagnostic"][0]["code_local"] == "H36.0"
    # PIO et acuité par œil
    ro = {(r["code_examen"].split("|")[1], r["oeil"]): r for r in res["resultat_ophtalmo"]}
    assert ro[("79892-6", "OD")]["valeur"] == 18
    assert ro[("VA-OD", "OD")]["valeur_texte"] == "8/10"
    assert any("anormal" in a and "OG" in a for a in res["alertes"])          # PIO OG 23 mmHg
    # glycémie convertie mg/dL -> g/L
    gly = res["mesure"][0]
    assert gly["code_local"] == "GLY" and gly["valeur"] == 1.6 and gly["unite"] == "g/L"
    # imagerie + compte rendu liés
    im = res["etude_imagerie"][0]
    assert im["lateralites"] == "OD,OG" and im["url_pacs"].startswith("https://")
    cr = res["compte_rendu"][0]
    assert cr["id_etude"] == im["id_etude"] and "Rétinopathie" in cr["conclusion"]
    assert res["groupes_sanguins_recus"]["P1-0106"] == "A+"


def test_retour_patient_inconnu_cree():
    res = RET.bundle_vers_lignes(charger_exemple(), trouver_ipp=lambda *a: None,
                                 nouvel_ipp=lambda: "P1-0121")
    p = res["patient"][0]
    assert p["ipp"] == "P1-0121" and p["sexe"] == "M" and p["telephone"] == "06 12 34 56 78"


def test_retour_rejouable_memes_cles():
    f = lambda cin, ipp, l: "P1-0106"
    r1 = RET.bundle_vers_lignes(charger_exemple(), f)
    r2 = RET.bundle_vers_lignes(charger_exemple(), f)
    for t in ("sejour", "diagnostic", "mesure", "resultat_ophtalmo", "compte_rendu", "etude_imagerie"):
        assert r1[t] == r2[t]


# ====================== ALLER-RETOUR : H1 -> FHIR -> H1 =====================
@pytest.mark.parametrize("cas", ["S1", "D4", "D9", "D11"])
def test_aller_retour_sans_perte(cas):
    """Ce qui sort d'Oracle et revient doit être identique (hors champs minimisés)."""
    d = dossier(cas)
    bundle, _, _ = ALL.dossier_vers_bundle(d, adressage=False)
    res = RET.bundle_vers_lignes(bundle, trouver_ipp=lambda *a: d["patient"]["ipp"],
                                 ignorer_propres=False)
    s_orig, s_ret = d["sejours"][0], res["sejour"][0]
    for champ in ("id_sejour", "type_sejour", "service", "date_admission", "medecin", "motif"):
        assert s_ret[champ] == s_orig[champ], champ
    assert ({(x["code_local"], x["libelle"]) for x in res["diagnostic"]}
            == {(x["code_local"], x["libelle"]) for x in s_orig["diagnostics"]})
    envoyees = {m["id_mesure"]: m for m in s_orig["mesures"]}
    for m in res["mesure"]:
        o = envoyees[m["id_mesure"]]
        assert (m["code_local"], float(m["valeur"]), m["unite"], m["date_mesure"]) == \
               (o["code_local"], float(o["valeur"]), o["unite"], o["date_mesure"])
    p_ret = RET.patient_vers_ligne(ressources(bundle, "Patient")[0])
    p = d["patient"]
    for champ in ("nom", "prenom", "sexe", "date_naissance", "cin", "telephone", "ville"):
        assert p_ret[champ] == p[champ], champ
