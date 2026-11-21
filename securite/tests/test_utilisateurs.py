"""Authentification du personnel : comptes, mots de passe, sessions, routes /auth."""

import json

import pytest

from securite.jetons import creer_jwt
from securite.utilisateurs import (Comptes, SaisieInvalide, controler_mdp, hacher_mdp,
                                   verifier_mdp)

from .conftest import JETON_REGISTRE, lignes_journal

SECRET = "secret-de-session-de-test-assez-long-0123456789"
MDP = "Correct-Cheval-Pile-42"


@pytest.fixture
def comptes(dossier):
    c = Comptes(dossier / "comptes" / "utilisateurs-h2.json")
    c.creer("a.bennani", "Dr A. Bennani", "medecin", MDP, provisoire=False)
    c.creer("accueil1", "Accueil poste 1", "accueil", MDP, provisoire=False)
    c.creer("nouveau", "Nouvel agent", "medecin", "Provisoire-Abc-123", provisoire=True)
    return c


@pytest.fixture
def api(client, comptes):
    return client(SEC_SESSION_SECRET=SECRET, SEC_UTILISATEURS=str(comptes.chemin))


def connecter(api, login="a.bennani", mdp=MDP):
    return api.post("/auth/connexion", json={"login": login, "mot_de_passe": mdp})


def bearer(jeton):
    return {"Authorization": "Bearer " + jeton}


# ── mots de passe ────────────────────────────────────────────────────────────
def test_empreinte_scrypt_salee_et_verifiable():
    a, b = hacher_mdp(MDP), hacher_mdp(MDP)
    assert a != b and a.startswith("scrypt$") and MDP not in a
    assert verifier_mdp(MDP, a) and not verifier_mdp(MDP + "x", a)
    assert not verifier_mdp(MDP, "md5$abc") and not verifier_mdp(MDP, "nimporte")


@pytest.mark.parametrize("mdp", ["court", "x" * 129, "a.bennani-2026!", "motdepasse123", "aaaaaaaaaaaaaaab"])
def test_politique_de_mot_de_passe(mdp):
    with pytest.raises(SaisieInvalide):
        controler_mdp(mdp, "a.bennani")


def test_fichier_des_comptes_sans_mot_de_passe_en_clair(comptes):
    contenu = comptes.chemin.read_text(encoding="utf-8")
    assert MDP not in contenu and "scrypt$" in contenu


@pytest.mark.parametrize("login, role", [("A", "medecin"), ("ok.login", "chirurgien")])
def test_creation_refusee(comptes, login, role):
    with pytest.raises(SaisieInvalide):
        comptes.creer(login, "x", role, MDP)


def test_doublon_refuse(comptes):
    with pytest.raises(SaisieInvalide):
        comptes.creer("A.Bennani", "x", "dpo", MDP)


# ── connexion ────────────────────────────────────────────────────────────────
def test_connexion_donne_les_droits_du_role(api):
    r = connecter(api)
    assert r.status_code == 200 and r.headers["cache-control"].startswith("no-store")
    j = r.json()
    assert j["token_type"] == "Bearer" and j["expires_in"] == 900
    assert "h2:export" in j["portees"] and "h2:consentement.gerer" not in j["portees"]
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(j["access_token"])).status_code == 200


def test_role_accueil_sans_acces_aux_dossiers(api):
    jeton = connecter(api, "accueil1").json()["access_token"]
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(jeton)).status_code == 403


@pytest.mark.parametrize("login, mdp", [("a.bennani", "Mauvais-Mot-De-Passe-1"), ("inconnu", MDP)])
def test_echec_meme_message_compte_connu_ou_non(api, login, mdp):
    r = connecter(api, login, mdp)
    assert r.status_code == 401
    assert r.json()["issue"][0]["diagnostics"] == "Identifiant ou mot de passe incorrect."


def test_verrouillage_du_compte_apres_echecs(api):
    for _ in range(3):                                   # SEC_ECHECS_MAX=3 dans les tests
        assert connecter(api, mdp="Mauvais-Mot-De-Passe-1").status_code == 401
    r = connecter(api)                                   # meme le bon mot de passe est refuse
    assert r.status_code == 429


def test_compte_desactive(api, comptes):
    jeton = connecter(api).json()["access_token"]
    comptes.modifier("a.bennani", actif=False)
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(jeton)).status_code == 401
    assert connecter(api).status_code == 401


def test_changement_de_role_immediat(api, comptes):
    jeton = connecter(api).json()["access_token"]
    comptes.modifier("a.bennani", role="dpo")
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(jeton)).status_code == 403


def test_sans_secret_de_session_connexion_indisponible(client, comptes):
    api = client(SEC_UTILISATEURS=str(comptes.chemin))
    assert connecter(api).status_code == 503


def test_journal_sans_mot_de_passe_ni_login_en_cas_d_echec(api, chemin_journal):
    connecter(api, "a.bennani", "Mauvais-Mot-De-Passe-1")
    connecter(api)
    brut = chemin_journal.read_text(encoding="utf-8")
    assert MDP not in brut and "Mauvais-Mot-De-Passe-1" not in brut
    acces = [l for l in lignes_journal(chemin_journal, "acces") if l.get("chemin") == "/auth/connexion"]
    assert acces[0]["resultat"] == "refus" and acces[0].get("client") is None
    assert acces[0]["ressource"].startswith("p:")
    assert acces[1]["resultat"] == "succes" and acces[1]["client"] == "utilisateur:a.bennani"


# ── jetons de session ────────────────────────────────────────────────────────
def test_session_d_un_autre_hopital_refusee(api, client, comptes):
    jeton = connecter(api).json()["access_token"]
    autre = client(service="H1", SEC_SESSION_SECRET=SECRET, SEC_UTILISATEURS=str(comptes.chemin))
    assert autre.get("/api/patients/X/bundle", headers=bearer(jeton)).status_code == 401


def test_session_expiree(api):
    expire = creer_jwt({"iss": "interop-sante", "aud": "h2-session", "sub": "a.bennani",
                        "jti": "j", "fam": "f"}, SECRET, duree_s=-120)
    r = api.get("/api/patients/P2-0051/bundle", headers=bearer(expire))
    assert r.status_code == 401 and "expiree" in r.json()["issue"][0]["diagnostics"]


def test_jeton_forge_refuse(api):
    faux = creer_jwt({"iss": "interop-sante", "aud": "h2-session", "sub": "a.bennani",
                      "jti": "j", "fam": "f"}, "pas-le-bon-secret")
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(faux)).status_code == 401


def test_jetons_de_registre_toujours_acceptes(api):
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(JETON_REGISTRE)).status_code == 200


# ── renouvellement et deconnexion ────────────────────────────────────────────
def test_renouvellement_a_usage_unique_et_detection_de_rejeu(api):
    premier = connecter(api).json()
    r = api.post("/auth/renouvellement", json={"refresh_token": premier["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != premier["refresh_token"]
    # Rejeu de l'ancien jeton : toute la session est fermee, y compris le nouveau.
    assert api.post("/auth/renouvellement", json={"refresh_token": premier["refresh_token"]}).status_code == 401
    assert api.post("/auth/renouvellement", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_deconnexion_ferme_acces_et_renouvellement(api):
    j = connecter(api).json()
    assert api.post("/auth/deconnexion", headers=bearer(j["access_token"])).status_code == 204
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(j["access_token"])).status_code == 401
    assert api.post("/auth/renouvellement", json={"refresh_token": j["refresh_token"]}).status_code == 401


def test_routes_de_session_refusees_aux_jetons_de_systeme(api):
    assert api.get("/auth/moi", headers=bearer(JETON_REGISTRE)).status_code == 403


def test_moi(api):
    j = connecter(api).json()
    r = api.get("/auth/moi", headers=bearer(j["access_token"]))
    assert r.status_code == 200 and r.json()["utilisateur"]["role"] == "medecin"
    assert "empreinte_mdp" not in json.dumps(r.json())


# ── mot de passe provisoire ──────────────────────────────────────────────────
def test_mot_de_passe_provisoire_sans_droits_puis_changement(api):
    j = connecter(api, "nouveau", "Provisoire-Abc-123").json()
    assert j["changement_mdp_requis"] is True and j["portees"] == []
    assert api.get("/api/patients/P2-0051/bundle", headers=bearer(j["access_token"])).status_code == 403
    r = api.post("/auth/mot-de-passe", headers=bearer(j["access_token"]),
                 json={"ancien": "Provisoire-Abc-123", "nouveau": "Autre-Secret-Solide-7"})
    assert r.status_code == 200 and r.json()["changement_mdp_requis"] is False
    assert api.get("/api/patients/P2-0051/bundle",
                   headers=bearer(r.json()["access_token"])).status_code == 200
    # l'ancienne session est fermee
    assert api.get("/auth/moi", headers=bearer(j["access_token"])).status_code == 401
    assert connecter(api, "nouveau", "Provisoire-Abc-123").status_code == 401


def test_changement_refuse_si_ancien_faux_ou_nouveau_faible(api):
    jeton = connecter(api).json()["access_token"]
    assert api.post("/auth/mot-de-passe", headers=bearer(jeton),
                    json={"ancien": "Faux-Mot-De-Passe-9", "nouveau": "Autre-Secret-Solide-7"}).status_code == 401
    assert api.post("/auth/mot-de-passe", headers=bearer(jeton),
                    json={"ancien": MDP, "nouveau": "court"}).status_code == 422
    assert api.post("/auth/mot-de-passe", headers=bearer(jeton),
                    json={"ancien": MDP, "nouveau": MDP}).status_code == 422


# ── outil d'administration ───────────────────────────────────────────────────
def test_outil_creer_lister_desactiver(dossier, monkeypatch, capsys):
    from securite.outils import gerer_utilisateurs as outil

    monkeypatch.setenv("SEC_UTILISATEURS", str(dossier / "comptes" / "u.json"))
    assert outil.main(["--service", "h1", "creer", "m.alaoui", "--nom", "Dr M. Alaoui", "--role", "medecin"]) == 0
    sortie = capsys.readouterr().out
    provisoire = sortie.split("une seule fois) : ")[1].strip()
    c = Comptes(dossier / "comptes" / "u.json").authentifier("m.alaoui", provisoire)
    assert c is not None and c.doit_changer_mdp
    assert outil.main(["--service", "h1", "desactiver", "m.alaoui"]) == 0
    assert Comptes(dossier / "comptes" / "u.json").authentifier("m.alaoui", provisoire) is None
    assert outil.main(["--service", "h1", "role", "inconnu", "dpo"]) == 2
