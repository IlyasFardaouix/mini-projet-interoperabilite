"""Intergiciel de securite vu depuis une vraie application FastAPI.

Chaque test passe par TestClient : c'est le comportement reellement servi aux
deux hopitaux qui est verifie, en-tetes et journal compris.
"""

import json

import pytest

from securite.intergiciels import EtatSecurite, adresse_appelante, operation_outcome
from securite.jetons import empreinte_courte
from securite.tests.conftest import (
    CLIENT_REGISTRE,
    EN_TETE,
    JETON_INCONNU,
    JETON_REGISTRE,
    ecrire_registre,
    entree_registre,
    lignes_journal,
)

ROUTE_EXPORT = "/api/patients/P2-0051/bundle"
MAUVAIS_ENTETE = {"Authorization": "Bearer " + JETON_INCONNU}

ENTETES_OBLIGATOIRES = (
    "x-content-type-options",
    "referrer-policy",
    "cache-control",
    "content-security-policy",
    "x-frame-options",
    "permissions-policy",
)


def verifier_entetes_de_securite(reponse):
    """Les en-tetes de durcissement doivent etre la, quel que soit le code HTTP."""
    for nom in ENTETES_OBLIGATOIRES:
        assert nom in reponse.headers, nom
    assert reponse.headers["x-content-type-options"] == "nosniff"
    assert reponse.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in reponse.headers["cache-control"]
    assert "default-src 'none'" in reponse.headers["content-security-policy"]


# ---------------------------------------------------------------------------
# Authentification et portees
# ---------------------------------------------------------------------------
def test_route_protegee_sans_jeton_repond_401(client):
    reponse = client().get(ROUTE_EXPORT)
    assert reponse.status_code == 401
    assert reponse.headers["www-authenticate"] == 'Bearer realm="H2"'
    assert reponse.headers["content-type"].startswith("application/fhir+json")
    corps = reponse.json()
    assert corps["resourceType"] == "OperationOutcome"
    assert corps["issue"][0]["severity"] == "error"
    assert corps["issue"][0]["code"] == "login"
    # Le motif technique reste dans le journal, pas dans la reponse.
    assert "jeton_absent" not in json.dumps(corps)


def test_jeton_inconnu_repond_401(client):
    reponse = client().get(ROUTE_EXPORT, headers=MAUVAIS_ENTETE)
    assert reponse.status_code == 401
    assert reponse.json()["issue"][0]["code"] == "login"


def test_jeton_valide_sans_la_portee_repond_403(client, chemin_journal):
    """Le jeton du registre porte h2:export et h2:import, pas h2:simulation."""
    reponse = client().post("/api/retours/simulation", headers=EN_TETE)
    assert reponse.status_code == 403
    assert reponse.json()["issue"][0]["code"] == "forbidden"
    assert "h2:simulation" in reponse.json()["issue"][0]["diagnostics"]
    assert "www-authenticate" not in reponse.headers
    ligne = lignes_journal(chemin_journal, "acces")[-1]
    assert ligne["motif"] == "portee_absente:h2:simulation"
    assert ligne["portee"] == "h2:simulation"
    assert ligne["client"] == CLIENT_REGISTRE


def test_jeton_valide_avec_la_portee_repond_200(client):
    reponse = client().get(ROUTE_EXPORT, headers=EN_TETE)
    assert reponse.status_code == 200
    assert reponse.json() == {"resourceType": "Bundle", "id": "P2-0051"}


def test_health_accessible_sans_jeton(client):
    c = client()
    assert c.get("/health").status_code == 200
    assert c.get("/health").json() == {"etat": "ok"}
    assert c.get("/metadata").status_code == 200


def test_jeton_revoque_refuse_sans_redemarrer_le_service(client, chemin_registre,
                                                         chemin_journal):
    """La revocation prend effet au prochain appel : le registre est relu."""
    c = client()
    assert c.get(ROUTE_EXPORT, headers=EN_TETE).status_code == 200
    ecrire_registre(chemin_registre,
                    entree_registre(actif=False, id="h1-chu-settat-revoque"))
    assert c.get(ROUTE_EXPORT, headers=EN_TETE).status_code == 401
    assert lignes_journal(chemin_journal, "acces")[-1]["motif"] == "jeton_revoque"


def test_sans_source_de_jetons_la_route_protegee_repond_503(client, chemin_registre):
    """Fail-closed de bout en bout : plus de registre, plus aucune donnee servie."""
    c = client()
    chemin_registre.unlink()
    reponse = c.get(ROUTE_EXPORT, headers=EN_TETE)
    assert reponse.status_code == 503
    assert reponse.json()["issue"][0]["code"] == "transient"
    assert c.get("/health").status_code == 200


def test_verrouillage_apres_echecs_repetes_renvoie_429(client, chemin_journal):
    """Force brute sur le jeton : passe SEC_ECHECS_MAX, l'adresse est verrouillee."""
    c = client(SEC_ECHECS_MAX="2", SEC_VERROU_SECONDES="300")
    assert c.get(ROUTE_EXPORT, headers=MAUVAIS_ENTETE).status_code == 401
    assert c.get(ROUTE_EXPORT, headers=MAUVAIS_ENTETE).status_code == 401
    refus = c.get(ROUTE_EXPORT, headers=MAUVAIS_ENTETE)
    assert refus.status_code == 429
    assert refus.json()["issue"][0]["code"] == "throttled"
    assert lignes_journal(chemin_journal, "acces")[-1]["motif"] == "verrouille"
    # Pendant le verrou, meme le jeton valide est refuse.
    assert c.get(ROUTE_EXPORT, headers=EN_TETE).status_code == 429


# ---------------------------------------------------------------------------
# En-tetes de securite
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code", [200, 401, 403, 404, 400, 413])
def test_entetes_de_securite_sur_toutes_les_reponses(client, code):
    c = client()
    appels = {
        200: lambda: c.get(ROUTE_EXPORT, headers=EN_TETE),
        401: lambda: c.get(ROUTE_EXPORT),
        403: lambda: c.post("/api/retours/simulation", headers=EN_TETE),
        404: lambda: c.get("/api/route-inexistante", headers=EN_TETE),
        400: lambda: c.post("/api/retours", headers=EN_TETE, content=b"pas du json"),
        413: lambda: c.post("/api/retours",
                            headers=dict(EN_TETE, **{"content-length": "9999999"}),
                            content=b"{}"),
    }
    reponse = appels[code]()
    assert reponse.status_code == code
    verifier_entetes_de_securite(reponse)


def test_entetes_de_securite_sur_le_refus_de_debit(client):
    c = client(SEC_DEBIT_PAR_MINUTE="1")
    for _ in range(c.app.state.securite.seau.rafale + 1):
        reponse = c.get(ROUTE_EXPORT, headers=EN_TETE)
    assert reponse.status_code == 429
    verifier_entetes_de_securite(reponse)


def test_hsts_absent_en_http(client):
    assert "strict-transport-security" not in client().get("/health").headers


def test_hsts_present_en_https(client):
    c = client(base_url="https://testserver")
    reponse = c.get(ROUTE_EXPORT, headers=EN_TETE)
    assert reponse.status_code == 200
    assert "max-age=31536000" in reponse.headers["strict-transport-security"]


def test_entetes_techniques_retires_de_la_reponse(client):
    """Ni « server » ni « x-powered-by » : pas d'annonce de la pile technique."""
    reponse = client().get("/api/entetes-techniques")
    assert reponse.status_code == 200
    assert "server" not in reponse.headers
    assert "x-powered-by" not in reponse.headers
    # Les autres en-tetes de la route sont conserves.
    assert reponse.headers["x-trace-test"] == "a-garder"


def test_un_seul_exemplaire_de_chaque_en_tete_de_securite(client):
    """L'en-tete de la politique remplace celui de la route, il ne s'y ajoute pas."""
    reponse = client().get("/api/entetes-techniques")
    valeurs = reponse.headers.get_list("cache-control")
    assert len(valeurs) == 1
    assert "no-store" in valeurs[0]


# ---------------------------------------------------------------------------
# Taille du corps
# ---------------------------------------------------------------------------
def test_content_length_au_dela_de_la_limite_refuse_413(client):
    """Le refus a lieu avant toute lecture du corps, et avant le jeton."""
    reponse = client().post("/api/retours",
                            headers=dict(EN_TETE, **{"content-length": "9999999"}),
                            content=b'{"a":1}')
    assert reponse.status_code == 413
    assert reponse.json()["issue"][0]["code"] == "too-costly"
    assert "4096" in reponse.json()["issue"][0]["diagnostics"]


def test_content_length_non_numerique_refuse_400(client):
    reponse = client().post("/api/retours",
                            headers=dict(EN_TETE, **{"content-length": "beaucoup"}),
                            content=b'{"a":1}')
    assert reponse.status_code == 400
    assert reponse.json()["issue"][0]["code"] == "structure"


def test_corps_dans_la_limite_accepte(client, chemin_journal):
    reponse = client().post("/api/retours", headers=EN_TETE, json={"ok": 1})
    assert reponse.status_code == 200
    assert reponse.json()["client"] == CLIENT_REGISTRE
    assert reponse.json()["recu"] == {"ok": 1}
    assert lignes_journal(chemin_journal, "acces")[-1]["octets"] > 0


def test_json_invalide_refuse_400(client, chemin_journal):
    reponse = client().post("/api/retours", headers=EN_TETE,
                            content=b"{ceci n'est pas du json")
    assert reponse.status_code == 400
    assert reponse.json()["issue"][0]["code"] == "structure"
    assert lignes_journal(chemin_journal, "acces")[-1]["motif"] == "json_invalide"


def test_corps_au_dela_de_la_limite_de_la_route_refuse_413(client):
    """La route lit son JSON avec sa propre limite (64 octets ici)."""
    corps = b'{"donnees": "' + b"x" * 200 + b'"}'
    reponse = client().post("/api/retours", headers=EN_TETE, content=corps)
    assert reponse.status_code == 413
    assert reponse.json()["issue"][0]["code"] == "too-costly"
    assert "64" in reponse.json()["issue"][0]["diagnostics"]


# ---------------------------------------------------------------------------
# Limitation de debit
# ---------------------------------------------------------------------------
def test_limitation_de_debit_renvoie_429_avec_retry_after(client):
    c = client(SEC_DEBIT_PAR_MINUTE="1")
    rafale = c.app.state.securite.seau.rafale
    for _ in range(rafale):
        assert c.get(ROUTE_EXPORT, headers=EN_TETE).status_code == 200
    refus = c.get(ROUTE_EXPORT, headers=EN_TETE)
    assert refus.status_code == 429
    assert refus.json()["issue"][0]["code"] == "throttled"
    assert int(refus.headers["retry-after"]) >= 1


def test_health_et_metadata_ne_sont_pas_limites(client):
    """Les sondes de supervision ne doivent pas consommer le quota d'echange."""
    c = client(SEC_DEBIT_PAR_MINUTE="1")
    for _ in range(c.app.state.securite.seau.rafale + 5):
        assert c.get("/health").status_code == 200
        assert c.get("/metadata").status_code == 200
    assert c.get(ROUTE_EXPORT, headers=EN_TETE).status_code == 200


# ---------------------------------------------------------------------------
# Adresse appelante
# ---------------------------------------------------------------------------
def test_x_forwarded_for_ignore_par_defaut(conf):
    """Sinon n'importe quel client choisirait son adresse et echapperait aux quotas."""
    scope = {"client": ("10.0.0.1", 5000),
             "headers": [(b"x-forwarded-for", b"1.2.3.4")]}
    assert adresse_appelante(scope, conf) == "10.0.0.1"


def test_x_forwarded_for_lu_derriere_un_proxy_de_confiance(monkeypatch, conf):
    monkeypatch.setenv("SEC_PROXY_DE_CONFIANCE", "1")
    scope = {"client": ("10.0.0.1", 5000),
             "headers": [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")]}
    assert adresse_appelante(scope, conf) == "1.2.3.4"


def test_adresse_inconnue_quand_le_client_est_absent(conf):
    assert adresse_appelante({}, conf) == "inconnu"


def test_x_forwarded_for_ne_contourne_pas_la_limitation_de_debit(client):
    """Une adresse inventee par requete ne doit pas rendre le quota inoperant."""
    c = client(SEC_DEBIT_PAR_MINUTE="1")
    for numero in range(c.app.state.securite.seau.rafale):
        entetes = dict(EN_TETE, **{"X-Forwarded-For": "9.9.9." + str(numero)})
        assert c.get(ROUTE_EXPORT, headers=entetes).status_code == 200
    entetes = dict(EN_TETE, **{"X-Forwarded-For": "9.9.9.200"})
    assert c.get(ROUTE_EXPORT, headers=entetes).status_code == 429


# ---------------------------------------------------------------------------
# TLS exige
# ---------------------------------------------------------------------------
def test_tls_exige_refuse_une_requete_en_clair(client, chemin_journal):
    c = client(SEC_TLS_REQUIS="1")
    reponse = c.get(ROUTE_EXPORT, headers=EN_TETE)
    assert reponse.status_code == 403
    assert reponse.json()["issue"][0]["code"] == "security"
    assert "HTTPS" in reponse.json()["issue"][0]["diagnostics"]
    assert lignes_journal(chemin_journal, "acces")[-1]["motif"] == "tls_absent"


def test_tls_exige_laisse_passer_health_en_clair(client):
    """La sonde de supervision doit rester joignable sans certificat."""
    c = client(SEC_TLS_REQUIS="1")
    assert c.get("/health").status_code == 200
    assert c.get("/metadata", headers=EN_TETE).status_code == 403


def test_tls_exige_accepte_le_https(client):
    c = client(base_url="https://testserver", SEC_TLS_REQUIS="1")
    assert c.get(ROUTE_EXPORT, headers=EN_TETE).status_code == 200


# ---------------------------------------------------------------------------
# Journal d'acces
# ---------------------------------------------------------------------------
def test_une_ligne_de_journal_par_requete_avec_le_code_final(client, chemin_journal):
    c = client()
    c.get(ROUTE_EXPORT)                                   # 401
    c.post("/api/retours/simulation", headers=EN_TETE)    # 403
    c.get(ROUTE_EXPORT, headers=EN_TETE)                  # 200
    acces = lignes_journal(chemin_journal, "acces")
    assert [ligne["http"] for ligne in acces] == [401, 403, 200]
    assert [ligne["methode"] for ligne in acces] == ["GET", "POST", "GET"]
    assert acces[0]["motif"] == "jeton_absent"
    assert acces[2]["client"] == CLIENT_REGISTRE
    assert acces[2]["source_jeton"] == "registre"
    assert all("duree_ms" in ligne for ligne in acces)
    assert all(ligne["service"] == "H2" for ligne in acces)


@pytest.mark.parametrize("code, resultat", [(200, "succes"), (401, "refus"),
                                            (403, "refus"), (400, "echec")])
def test_un_refus_n_est_jamais_journalise_comme_un_succes(client, chemin_journal,
                                                          code, resultat):
    """Un auditeur doit pouvoir compter les refus sans relire tous les codes HTTP."""
    c = client()
    appels = {
        200: lambda: c.get(ROUTE_EXPORT, headers=EN_TETE),
        401: lambda: c.get(ROUTE_EXPORT),
        403: lambda: c.post("/api/retours/simulation", headers=EN_TETE),
        400: lambda: c.post("/api/retours", headers=EN_TETE, content=b"pas du json"),
    }
    assert appels[code]().status_code == code
    ligne = lignes_journal(chemin_journal, "acces")[-1]
    assert ligne["http"] == code
    assert ligne["resultat"] == resultat


def test_journal_enregistre_le_gabarit_pas_l_identifiant(client, chemin_journal):
    client().get(ROUTE_EXPORT, headers=EN_TETE)
    ligne = lignes_journal(chemin_journal, "acces")[-1]
    assert ligne["chemin"] == "/api/patients/{id}/bundle"
    assert ligne["ressource"].startswith("p:")
    assert "P2-0051" not in json.dumps(ligne)


def test_journal_ne_contient_ni_le_jeton_ni_l_entete_authorization(client,
                                                                   chemin_journal):
    client().get(ROUTE_EXPORT, headers=EN_TETE)
    texte = chemin_journal.read_text(encoding="utf-8")
    assert JETON_REGISTRE not in texte
    assert "authorization" not in texte.lower()
    assert "bearer" not in texte.lower()
    ligne = lignes_journal(chemin_journal, "acces")[-1]
    assert ligne["jeton"] == empreinte_courte(JETON_REGISTRE)
    assert len(ligne["jeton"]) == 12


def test_parametres_de_recherche_masques_dans_le_journal(client, chemin_journal):
    """Un CIN passe en parametre de recherche ne doit pas atterrir dans le journal."""
    client().get(ROUTE_EXPORT, headers=EN_TETE,
                 params={"identifier": "urn:ma:cin|AB123456", "_count": "5"})
    texte = chemin_journal.read_text(encoding="utf-8")
    assert "AB123456" not in texte
    ligne = lignes_journal(chemin_journal, "acces")[-1]
    assert ligne["parametres"] == {"identifier": "***", "_count": "5"}
