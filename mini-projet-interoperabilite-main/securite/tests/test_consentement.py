"""Regles communes du consentement au partage (securite/consentement.py)."""

from datetime import date, datetime

import pytest

from securite import consentement as CONS
from securite.config import PORTEES_CONNUES

JOUR = date(2026, 11, 21)


def actif(**champs):
    base = dict(statut=CONS.ACTIF, date_recueil=date(2026, 1, 10), debut=date(2026, 1, 10))
    base.update(champs)
    return CONS.Consentement(**base)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def test_consentement_actif_autorise():
    d = CONS.evaluer(actif(), destinataire="H2", aujourd_hui=JOUR)
    assert d.autorise and d.categories_exclues == frozenset()


@pytest.mark.parametrize("consentement, attendu", [
    (None, "aucun consentement"),
    (actif(statut=CONS.REFUSE), "refuse"),
    (actif(statut=CONS.RETIRE, date_retrait=date(2026, 6, 1)), "retire le 2026-06-01"),
    (actif(statut=CONS.EN_ATTENTE), "en attente"),
    (actif(debut=date(2026, 12, 1)), "pas encore en vigueur"),
    (actif(fin=date(2026, 11, 20)), "expire le 2026-11-20"),
    (actif(destinataires=("H1",)), "vers H2 non autorise"),
    (actif(finalites=("recherche",)), "finalite"),
])
def test_refus_et_motif(consentement, attendu):
    d = CONS.evaluer(consentement, destinataire="H2", aujourd_hui=JOUR)
    assert not d.autorise and attendu in d.motif


def test_dernier_jour_de_validite_encore_autorise():
    assert CONS.evaluer(actif(fin=JOUR), aujourd_hui=JOUR).autorise


def test_destinataire_compare_sans_casse():
    assert CONS.evaluer(actif(destinataires=("H2",)), destinataire="h2", aujourd_hui=JOUR).autorise


def test_verifier_leve_403_avec_reference_a_la_loi():
    with pytest.raises(CONS.ConsentementRefuse) as e:
        CONS.verifier(actif(statut=CONS.REFUSE), operation="Export", aujourd_hui=JOUR)
    assert e.value.http == 403 and "Export refuse" in str(e.value) and "09-08" in str(e.value)


def test_categories_exclues_renvoyees_avec_les_types_fhir():
    d = CONS.evaluer(actif(categories_exclues=("imagerie",)), aujourd_hui=JOUR)
    assert d.autorise and d.types_exclus == {"ImagingStudy", "Endpoint"}


# ---------------------------------------------------------------------------
# Saisie et retrait
# ---------------------------------------------------------------------------
def test_saisie_complete():
    c = CONS.depuis_saisie({"statut": "actif", "recueilli_par": "Accueil - Mme A.",
                            "fin": "2027-11-21", "destinataires": ["h2"],
                            "categories_exclues": ["imagerie"], "signataire": "representant_legal"},
                           aujourd_hui=JOUR)
    assert c.statut == CONS.ACTIF and c.debut == JOUR and c.fin == date(2027, 11, 21)
    assert c.destinataires == ("H2",) and c.categories_exclues == ("imagerie",)
    assert c.signataire == "representant_legal" and c.date_recueil == JOUR


@pytest.mark.parametrize("corps, extrait", [
    ([], "objet JSON"),
    ({"statut": "retire", "recueilli_par": "x"}, "route /retrait"),
    ({"statut": "actif"}, "recueilli_par"),
    ({"statut": "actif", "recueilli_par": "x", "debut": "2027-01-01", "fin": "2026-01-01"}, "precede"),
    ({"statut": "actif", "recueilli_par": "x", "destinataires": ["H9"]}, "H9"),
    ({"statut": "actif", "recueilli_par": "x", "categories_exclues": ["genetique"]}, "genetique"),
    ({"statut": "actif", "recueilli_par": "x", "signataire": "voisin"}, "signataire"),
    ({"statut": "actif", "recueilli_par": "x", "fin": "21/11/2027"}, "AAAA-MM-JJ"),
])
def test_saisie_invalide_422(corps, extrait):
    with pytest.raises(CONS.ConsentementInvalide) as e:
        CONS.depuis_saisie(corps, aujourd_hui=JOUR)
    assert e.value.http == 422 and extrait in str(e.value)


def test_retrait_cree_une_nouvelle_version():
    c = CONS.retirer(actif(categories_exclues=("allergies",)), "Ne souhaite plus partager",
                     recueilli_par="Accueil", aujourd_hui=JOUR)
    assert c.statut == CONS.RETIRE and c.date_retrait == JOUR and c.motif_retrait.startswith("Ne souhaite")
    assert c.categories_exclues == ("allergies",)          # le reste de la preuve est conserve
    assert not CONS.evaluer(c, aujourd_hui=JOUR).autorise


@pytest.mark.parametrize("consentement", [None, actif(statut=CONS.REFUSE)])
def test_rien_a_retirer(consentement):
    with pytest.raises(CONS.ConsentementInvalide):
        CONS.retirer(consentement, "x", recueilli_par="Accueil")


def test_retrait_exige_l_agent():
    with pytest.raises(CONS.ConsentementInvalide):
        CONS.retirer(actif(), "x", recueilli_par=" ")


# ---------------------------------------------------------------------------
# Adaptateurs Oracle / MongoDB
# ---------------------------------------------------------------------------
def test_ligne_oracle_ancienne_reste_lisible():
    c = CONS.depuis_oracle({"id_consentement": "CST-0106", "statut": "ACTIF",
                            "finalite": "Partage soins", "date_consentement": datetime(2026, 10, 1)})
    assert c.statut == CONS.ACTIF and c.finalites == ("soins",) and c.destinataires == ()
    assert CONS.evaluer(c, destinataire="H2", aujourd_hui=JOUR).autorise


def test_aller_retour_oracle():
    c = actif(fin=date(2027, 1, 1), destinataires=("H2",), categories_exclues=("allergies", "imagerie"),
              signataire="representant_legal", recueilli_par="Accueil")
    lignes = CONS.vers_oracle(c)
    assert lignes["statut"] == "ACTIF" and lignes["categories_exclues"] == "allergies,imagerie"
    assert CONS.depuis_oracle(lignes) == c


def test_champ_mongo_historique_reste_lisible():
    c = CONS.depuis_mongo({"date": "2025-05-04", "purpose": "care-continuity",
                           "signed_by": "patient", "status": "active"})
    assert c.statut == CONS.ACTIF and c.date_recueil == date(2025, 5, 4)


def test_aller_retour_mongo_garde_les_cles_historiques():
    c = actif(fin=date(2027, 1, 1), destinataires=("H1",), categories_exclues=("imagerie",),
              recueilli_par="Accueil")
    champ = CONS.vers_mongo(c)
    assert champ["status"] == "active" and champ["purpose"] == "care-continuity"
    assert CONS.depuis_mongo(champ) == c


@pytest.mark.parametrize("brut, statut", [
    ("refused", CONS.REFUSE), ("not-done", CONS.REFUSE), ("rejected", CONS.REFUSE),
    ("inactive", CONS.RETIRE), ("draft", CONS.EN_ATTENTE), ("REFUSE", CONS.REFUSE),
])
def test_normalisation_des_statuts(brut, statut):
    assert CONS.normaliser_statut(brut) == statut


# ---------------------------------------------------------------------------
# FHIR R5
# ---------------------------------------------------------------------------
PATIENT = {"reference": "Patient/P2-0051"}


def test_consent_fhir_complet_et_relu_a_l_identique():
    c = actif(fin=date(2027, 1, 1), destinataires=("H1",), categories_exclues=("imagerie",),
              signataire="representant_legal")
    res = CONS.vers_fhir(c, id_ressource="consent-P2-0051", patient_ref=PATIENT)
    assert res["status"] == "active" and res["decision"] == "permit"
    assert res["period"] == {"start": "2026-01-10", "end": "2027-01-01"}
    prov = res["provision"][0]
    assert prov["purpose"][0]["code"] == "TREAT"
    assert prov["actor"][0]["reference"]["identifier"]["value"] == "H1"
    assert {t["code"] for t in prov["provision"][0]["resourceType"]} == {"ImagingStudy", "Endpoint"}
    relu = CONS.depuis_fhir(res)
    assert (relu.statut, relu.fin, relu.destinataires, relu.categories_exclues, relu.signataire) == \
           (CONS.ACTIF, date(2027, 1, 1), ("H1",), ("imagerie",), "representant_legal")


def test_consent_fhir_valide_par_le_modele_r5():
    modele = pytest.importorskip("fhir.resources.consent")
    res = CONS.vers_fhir(actif(fin=date(2027, 1, 1), destinataires=("H2",),
                               categories_exclues=("imagerie", "allergies")),
                         id_ressource="c1", patient_ref=PATIENT,
                         organisation_ref={"reference": "Organization/x"},
                         identifiant={"system": "urn:test", "value": "1"})
    modele.Consent.model_validate(res)


def test_consent_refuse_en_fhir():
    res = CONS.vers_fhir(actif(statut=CONS.REFUSE), patient_ref=PATIENT)
    assert res["status"] == "not-done" and res["decision"] == "deny" and "id" not in res
    assert CONS.depuis_fhir(res).statut == CONS.REFUSE


def test_decision_deny_l_emporte_sur_status_active():
    assert CONS.depuis_fhir({"resourceType": "Consent", "status": "active",
                             "decision": "deny"}).statut == CONS.REFUSE


def test_consent_r4_avec_provision_unique():
    c = CONS.depuis_fhir({"resourceType": "Consent", "status": "active",
                          "provision": {"period": {"start": "2026-01-01", "end": "2026-06-30"}}})
    assert c.fin == date(2026, 6, 30)
    assert not CONS.evaluer(c, aujourd_hui=JOUR).autorise


# ---------------------------------------------------------------------------
# Filtrage du Bundle
# ---------------------------------------------------------------------------
def _bundle():
    return {"resourceType": "Bundle", "type": "transaction", "entry": [
        {"fullUrl": "urn:uuid:p", "resource": {"resourceType": "Patient", "id": "p"}},
        {"fullUrl": "urn:uuid:img", "resource": {"resourceType": "ImagingStudy", "id": "img",
                                                 "endpoint": [{"reference": "Endpoint/ep"}]}},
        {"resource": {"resourceType": "Endpoint", "id": "ep"}},
        {"resource": {"resourceType": "DiagnosticReport", "id": "dr",
                      "subject": {"reference": "urn:uuid:p"},
                      "study": [{"reference": "ImagingStudy/img"}],
                      "result": [{"reference": "Observation/o"}]}},
    ]}


def test_filtrage_retire_la_categorie_et_ses_references():
    bundle = _bundle()
    filtre, n = CONS.filtrer_bundle(bundle, ["imagerie"])
    assert n == 2
    assert [e["resource"]["resourceType"] for e in filtre["entry"]] == ["Patient", "DiagnosticReport"]
    rapport = filtre["entry"][1]["resource"]
    assert "study" not in rapport and rapport["result"] == [{"reference": "Observation/o"}]
    assert len(bundle["entry"]) == 4                       # l'original n'est pas modifie


def test_filtrage_sans_exclusion_ne_change_rien():
    bundle = _bundle()
    assert CONS.filtrer_bundle(bundle, []) == (bundle, 0)


def test_les_portees_de_consentement_sont_connues():
    assert {"consentement.lire", "consentement.gerer"} <= PORTEES_CONNUES
