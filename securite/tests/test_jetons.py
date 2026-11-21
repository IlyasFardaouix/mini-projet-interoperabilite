"""Jetons d'acces : en-tete Authorization, registre, JWT, anti-force-brute.

Regle de lecture : un refus se traduit toujours par une exception AccesRefuse
portant (http, type_fhir, motif). Le motif est destine au journal, jamais au
client ; le message, lui, reste volontairement generique.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest

from securite.config import charger
from securite.jetons import (
    AccesRefuse,
    Appelant,
    CompteurEchecs,
    Registre,
    Verificateur,
    creer_jwt,
    empreinte_complete,
    empreinte_courte,
    verifier_jwt,
)
from securite.tests.conftest import (
    CLIENT_REGISTRE,
    JETON_INCONNU,
    JETON_PARTAGE,
    JETON_REGISTRE,
    ecrire_registre,
    entree_registre,
)

SECRET = "secret-hs256-de-test-0123456789abcdef"
ISS = "interop-sante"
AUD = "H2"


def _b64(donnees):
    return base64.urlsafe_b64encode(donnees).decode("ascii").rstrip("=")


def fabriquer_jwt(entete, charge, secret=SECRET, signature=None, algo=hashlib.sha256):
    """Fabrique un JWT a la main : seul moyen de tester un en-tete malveillant."""
    partie_entete = _b64(json.dumps(entete, separators=(",", ":")).encode("utf-8"))
    partie_charge = _b64(json.dumps(charge, separators=(",", ":")).encode("utf-8"))
    if signature is None:
        signature = hmac.new(secret.encode("utf-8"),
                             (partie_entete + "." + partie_charge).encode("ascii"),
                             algo).digest()
    return partie_entete + "." + partie_charge + "." + _b64(signature)


# ---------------------------------------------------------------------------
# En-tete Authorization
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("autorisation", [
    None,                       # en-tete absent
    "",                         # en-tete vide
    "   ",                      # en-tete blanc
    "Bearer",                   # schema sans jeton
    "Bearer ",                  # jeton vide
    "Basic aDE6bW90ZGVwYXNzZQ==",   # autre schema
    "Token " + JETON_REGISTRE,       # schema inconnu
    JETON_REGISTRE,                  # jeton nu, sans schema
])
def test_jeton_absent_ou_mal_forme_refuse(conf, registre, autorisation):
    """401 jeton_absent des que l'en-tete n'est pas un Bearer porteur d'un jeton."""
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(conf).verifier(autorisation)
    assert refus.value.http == 401
    assert refus.value.type_fhir == "login"
    assert refus.value.motif == "jeton_absent"


def test_schema_bearer_insensible_a_la_casse(conf, registre):
    """« bearer » en minuscules reste un Bearer valide (RFC 6750)."""
    assert Verificateur(conf).verifier("bearer " + JETON_REGISTRE).source == "registre"


def test_jeton_inconnu_refuse(conf, registre):
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(conf).verifier("Bearer " + JETON_INCONNU)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_invalide")


def test_sans_aucune_source_de_jetons_repond_503(reglages, chemin_registre):
    """Fail-closed : sans source de jetons, on refuse tout, on ne laisse rien passer."""
    conf = reglages()
    assert not chemin_registre.exists()
    verificateur = Verificateur(conf)
    assert verificateur.configure() is False
    for autorisation in (None, "Bearer " + JETON_REGISTRE, "Bearer " + JETON_INCONNU):
        with pytest.raises(AccesRefuse) as refus:
            verificateur.verifier(autorisation)
        assert refus.value.http == 503
        assert refus.value.motif == "auth_non_configuree"
        assert refus.value.type_fhir == "transient"


# ---------------------------------------------------------------------------
# Registre de jetons
# ---------------------------------------------------------------------------
def test_jeton_du_registre_reconnu_avec_ses_portees(conf, registre):
    appelant = Verificateur(conf).verifier("Bearer " + JETON_REGISTRE)
    assert appelant.client == CLIENT_REGISTRE
    assert appelant.source == "registre"
    assert appelant.portees == frozenset({"h2:export", "h2:import"})
    assert appelant.empreinte == empreinte_courte(JETON_REGISTRE)
    assert appelant.avertissements == ()


def test_jeton_revoque_refuse(reglages, chemin_registre):
    """Une entree « actif: false » ne doit plus ouvrir l'acces."""
    ecrire_registre(chemin_registre, entree_registre(actif=False))
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(reglages()).verifier("Bearer " + JETON_REGISTRE)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_revoque")


def test_jeton_expire_refuse(reglages, chemin_registre):
    ecrire_registre(chemin_registre, entree_registre(expire_le="2020-01-01T00:00:00Z"))
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(reglages()).verifier("Bearer " + JETON_REGISTRE)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_expire")


def test_expiration_illisible_refuse(reglages, chemin_registre):
    """Une date d'expiration incomprehensible est traitee comme perimee."""
    ecrire_registre(chemin_registre, entree_registre(expire_le="la-semaine-prochaine"))
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(reglages()).verifier("Bearer " + JETON_REGISTRE)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_expire")


def test_expiration_future_acceptee(reglages, chemin_registre):
    ecrire_registre(chemin_registre, entree_registre(expire_le="2099-12-31T23:59:59Z"))
    appelant = Verificateur(reglages()).verifier("Bearer " + JETON_REGISTRE)
    assert appelant.expire_le == "2099-12-31T23:59:59Z"


@pytest.mark.parametrize("empreinte", [
    "",                                     # empreinte absente
    "sha256:tropcourte",                    # longueur invalide
    "sha256:" + "z" * 64,                   # 64 caracteres mais pas l'empreinte
])
def test_empreinte_invalide_dans_le_registre_ne_reconnait_rien(reglages, chemin_registre,
                                                               empreinte):
    ecrire_registre(chemin_registre, entree_registre(empreinte=empreinte),
                    entree_registre(JETON_PARTAGE, id="autre"))
    assert Registre(chemin_registre).chercher(JETON_REGISTRE) is None


@pytest.mark.parametrize("contenu", [
    "",                                  # fichier vide
    "{ceci n'est pas du json",           # JSON invalide
    "[]",                                # aucune entree
    '{"clients": "pas une liste"}',      # structure inattendue
    '{"clients": [12, null, "texte"]}',  # entrees qui ne sont pas des objets
])
def test_registre_illisible_ne_reconnait_aucun_jeton(reglages, chemin_registre, contenu):
    """Un registre casse ne doit ni ouvrir l'acces, ni faire tomber le service."""
    chemin_registre.write_text(contenu, encoding="utf-8")
    verificateur = Verificateur(reglages(H2_TOKEN=JETON_PARTAGE))
    assert verificateur.registre.entrees() == []
    with pytest.raises(AccesRefuse) as refus:
        verificateur.verifier("Bearer " + JETON_REGISTRE)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_invalide")


def test_registre_absent_ne_reconnait_aucun_jeton(reglages, chemin_registre):
    verificateur = Verificateur(reglages(H2_TOKEN=JETON_PARTAGE))
    assert not chemin_registre.exists()
    assert verificateur.registre.entrees() == []
    assert verificateur.registre.chercher(JETON_REGISTRE) is None


def test_registre_qui_est_un_dossier_ne_fait_pas_tomber_le_service(reglages,
                                                                   chemin_registre):
    """Chemin de registre illisible (ici un dossier) : aucune entree, aucune erreur."""
    chemin_registre.mkdir()
    assert Verificateur(reglages(H2_TOKEN=JETON_PARTAGE)).registre.entrees() == []


def test_registre_recharge_apres_modification_du_fichier(chemin_registre):
    """Le registre est relu quand le fichier change (detection mtime + taille).

    Les deux versions n'ont pas la meme taille : le changement est donc visible
    meme si l'horodatage du systeme de fichiers n'a pas eu le temps de bouger.
    """
    ecrire_registre(chemin_registre, entree_registre(JETON_REGISTRE, id="premier"))
    registre = Registre(chemin_registre)
    assert registre.chercher(JETON_REGISTRE)["id"] == "premier"
    assert registre.chercher(JETON_INCONNU) is None

    ecrire_registre(chemin_registre,
                    entree_registre(JETON_INCONNU, id="second-client-apres-rotation"))
    assert registre.chercher(JETON_INCONNU)["id"] == "second-client-apres-rotation"
    assert registre.chercher(JETON_REGISTRE) is None


def test_registre_supprime_en_cours_de_route_ne_reconnait_plus_rien(chemin_registre):
    ecrire_registre(chemin_registre, entree_registre())
    registre = Registre(chemin_registre)
    assert registre.chercher(JETON_REGISTRE) is not None
    chemin_registre.unlink()
    assert registre.entrees() == []
    assert registre.chercher(JETON_REGISTRE) is None


@pytest.mark.parametrize("brut, attendu", [
    ("h2:export h2:import", {"h2:export", "h2:import"}),
    ("h2:export,h2:import", {"h2:export", "h2:import"}),
    (["h2:export", " h2:import "], {"h2:export", "h2:import"}),
    ("", set()),                          # entree sans portee : aucun droit
])
def test_portees_lues_en_chaine_ou_en_liste(reglages, chemin_registre, brut, attendu):
    ecrire_registre(chemin_registre, entree_registre(portees=brut))
    appelant = Verificateur(reglages()).verifier("Bearer " + JETON_REGISTRE)
    assert appelant.portees == frozenset(attendu)


def test_portee_inconnue_signalee_en_avertissement(reglages, chemin_registre):
    ecrire_registre(chemin_registre, entree_registre(portees="h2:export h2:tout-faire"))
    appelant = Verificateur(reglages()).verifier("Bearer " + JETON_REGISTRE)
    assert appelant.autorise("h2:export")
    assert appelant.avertissements and "tout-faire" in appelant.avertissements[0]


# ---------------------------------------------------------------------------
# Empreintes
# ---------------------------------------------------------------------------
def test_empreinte_courte_fait_douze_caracteres_hexadecimaux():
    court = empreinte_courte(JETON_REGISTRE)
    assert len(court) == 12
    assert court == empreinte_complete(JETON_REGISTRE)[:12]
    assert all(caractere in "0123456789abcdef" for caractere in court)


def test_empreinte_ne_permet_pas_de_retrouver_le_jeton():
    """L'empreinte ne laisse filtrer aucun morceau du jeton : que de l'hexadecimal."""
    for empreinte in (empreinte_courte(JETON_REGISTRE), empreinte_complete(JETON_REGISTRE)):
        assert JETON_REGISTRE not in empreinte
        assert all(caractere in "0123456789abcdef" for caractere in empreinte)
    assert len(empreinte_complete(JETON_REGISTRE)) == 64
    assert empreinte_complete(JETON_REGISTRE) != empreinte_complete(JETON_INCONNU)
    # Deux jetons voisins donnent des empreintes sans rapport (effet d'avalanche).
    voisin = JETON_REGISTRE[:-1] + "z"
    assert empreinte_courte(voisin) != empreinte_courte(JETON_REGISTRE)


# ---------------------------------------------------------------------------
# Jeton partage historique
# ---------------------------------------------------------------------------
def test_jeton_partage_historique_recoit_la_portee_joker(reglages):
    """H2_TOKEN : toutes les portees du service, et un avertissement de migration."""
    appelant = Verificateur(reglages(H2_TOKEN=JETON_PARTAGE)).verifier(
        "Bearer " + JETON_PARTAGE)
    assert appelant.source == "historique"
    assert appelant.client == "jeton-partage"
    assert appelant.portees == frozenset({"h2:*"})
    assert appelant.autorise("h2:import")
    assert appelant.autorise("h2:export")
    assert appelant.avertissements and "a remplacer" in appelant.avertissements[0]


def test_jeton_partage_du_service_h1_ne_vaut_que_pour_h1(reglages):
    appelant = Verificateur(reglages(service="H1", H1_API_TOKEN=JETON_PARTAGE)).verifier(
        "Bearer " + JETON_PARTAGE)
    assert appelant.portees == frozenset({"h1:*"})
    assert appelant.autorise("h1:export")
    assert not appelant.autorise("h2:export")


def test_le_registre_a_la_priorite_sur_le_jeton_partage(reglages, chemin_registre):
    """Un jeton present dans le registre garde SES portees, pas le joker."""
    ecrire_registre(chemin_registre, entree_registre(JETON_PARTAGE, id="declare",
                                                     portees="h2:export"))
    appelant = Verificateur(reglages(H2_TOKEN=JETON_PARTAGE)).verifier(
        "Bearer " + JETON_PARTAGE)
    assert appelant.source == "registre"
    assert appelant.portees == frozenset({"h2:export"})
    assert not appelant.autorise("h2:import")


def test_jeton_partage_revoque_dans_le_registre_reste_refuse(reglages, chemin_registre):
    """Fail-closed : la revocation ne doit pas etre contournee par H2_TOKEN."""
    ecrire_registre(chemin_registre, entree_registre(JETON_PARTAGE, actif=False))
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(reglages(H2_TOKEN=JETON_PARTAGE)).verifier("Bearer " + JETON_PARTAGE)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_revoque")


# ---------------------------------------------------------------------------
# Portees d'un appelant
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("portees, portee, attendu", [
    (["h2:export"], "h2:export", True),                 # portee exacte
    (["h2:export"], "h2:import", False),
    (["h2:*"], "h2:import", True),                      # joker du service
    (["h2:*"], "h2:export", True),
    (["h2:*"], "h1:import", False),                     # un joker ne traverse pas
    (["h2:*"], "h1:*", False),
    (["*"], "h1:import", True),                         # joker total
    (["*"], "h2:export", True),
    ([], "h2:export", False),                           # aucune portee : aucun droit
    (["h1:*", "h2:export"], "h2:export", True),
    (["h1:*"], "h2:export", False),
])
def test_autorise_respecte_les_jokers_par_service(portees, portee, attendu):
    appelant = Appelant(client="c", portees=frozenset(portees),
                        empreinte="0" * 12, source="registre")
    assert appelant.autorise(portee) is attendu


# ---------------------------------------------------------------------------
# Anti-force-brute : CompteurEchecs (horloge injectee, aucun sleep)
# ---------------------------------------------------------------------------
def test_compteur_verrouille_apres_le_maximum_d_echecs():
    compteur = CompteurEchecs(maximum=3, verrou_s=60)
    assert compteur.secondes_restantes("ip", maintenant=0.0) == 0
    assert compteur.echec("ip", maintenant=0.0) == 1
    assert compteur.secondes_restantes("ip", maintenant=0.0) == 0
    assert compteur.echec("ip", maintenant=1.0) == 2
    assert compteur.secondes_restantes("ip", maintenant=1.0) == 0
    assert compteur.echec("ip", maintenant=2.0) == 3
    assert compteur.secondes_restantes("ip", maintenant=2.0) == 61


def test_verrou_libere_apres_la_duree():
    compteur = CompteurEchecs(maximum=2, verrou_s=30)
    compteur.echec("ip", maintenant=100.0)
    compteur.echec("ip", maintenant=100.0)
    assert compteur.secondes_restantes("ip", maintenant=100.0) == 31
    assert compteur.secondes_restantes("ip", maintenant=129.0) == 2
    assert compteur.secondes_restantes("ip", maintenant=130.0) == 0
    # Le compteur est oublie : un nouvel echec repart de 1.
    assert compteur.echec("ip", maintenant=131.0) == 1


def test_succes_reinitialise_le_compteur():
    compteur = CompteurEchecs(maximum=2, verrou_s=60)
    compteur.echec("ip", maintenant=0.0)
    compteur.succes("ip")
    assert compteur.echec("ip", maintenant=0.0) == 1
    assert compteur.secondes_restantes("ip", maintenant=0.0) == 0


def test_verrous_independants_par_adresse():
    compteur = CompteurEchecs(maximum=1, verrou_s=60)
    compteur.echec("10.0.0.1", maintenant=0.0)
    assert compteur.secondes_restantes("10.0.0.1", maintenant=0.0) == 61
    assert compteur.secondes_restantes("10.0.0.2", maintenant=0.0) == 0


def test_maximum_et_verrou_valent_au_moins_un():
    compteur = CompteurEchecs(maximum=0, verrou_s=0)
    assert (compteur.maximum, compteur.verrou_s) == (1, 1)


def test_verificateur_verrouille_l_adresse_apres_trop_d_echecs(reglages, registre):
    """429 verrouille : passe le seuil, on n'examine meme plus le jeton presente."""
    verificateur = Verificateur(reglages(SEC_ECHECS_MAX="3", SEC_VERROU_SECONDES="300"))
    for _ in range(3):
        with pytest.raises(AccesRefuse) as refus:
            verificateur.verifier("Bearer " + JETON_INCONNU, cle_verrou="10.0.0.9")
        assert refus.value.http == 401

    with pytest.raises(AccesRefuse) as refus:
        verificateur.verifier("Bearer " + JETON_INCONNU, cle_verrou="10.0.0.9")
    assert (refus.value.http, refus.value.motif) == (429, "verrouille")
    assert refus.value.type_fhir == "throttled"

    # Pendant le verrou, meme le bon jeton est refuse...
    with pytest.raises(AccesRefuse) as refus:
        verificateur.verifier("Bearer " + JETON_REGISTRE, cle_verrou="10.0.0.9")
    assert refus.value.http == 429
    # ... mais une autre adresse n'est pas penalisee.
    autre = verificateur.verifier("Bearer " + JETON_REGISTRE, cle_verrou="10.0.0.8")
    assert autre.client == CLIENT_REGISTRE


def test_un_succes_efface_les_echecs_precedents(reglages, registre):
    verificateur = Verificateur(reglages(SEC_ECHECS_MAX="3"))
    for _ in range(2):
        with pytest.raises(AccesRefuse):
            verificateur.verifier("Bearer " + JETON_INCONNU, cle_verrou="10.0.0.7")
    assert verificateur.verifier("Bearer " + JETON_REGISTRE,
                                 cle_verrou="10.0.0.7").source == "registre"
    for _ in range(2):
        with pytest.raises(AccesRefuse) as refus:
            verificateur.verifier("Bearer " + JETON_INCONNU, cle_verrou="10.0.0.7")
        assert refus.value.http == 401


def test_sans_cle_de_verrou_aucun_verrouillage(reglages, registre):
    """Sans adresse appelante identifiable, on ne verrouille personne."""
    verificateur = Verificateur(reglages(SEC_ECHECS_MAX="1"))
    for _ in range(4):
        with pytest.raises(AccesRefuse) as refus:
            verificateur.verifier("Bearer " + JETON_INCONNU)
        assert refus.value.http == 401


# ---------------------------------------------------------------------------
# JWT HS256
# ---------------------------------------------------------------------------
def test_jwt_aller_retour_valide():
    jeton = creer_jwt({"sub": "h1-prod", "iss": ISS, "aud": AUD, "scope": "h2:export"},
                      SECRET)
    charge = verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)
    assert charge["sub"] == "h1-prod"
    assert charge["scope"] == "h2:export"
    assert charge["exp"] > charge["iat"]
    assert charge["exp"] - charge["iat"] == 900


def test_jwt_duree_personnalisee():
    jeton = creer_jwt({"iss": ISS, "aud": AUD}, SECRET, duree_s=60)
    charge = verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)
    assert charge["exp"] - charge["iat"] == 60


def test_jwt_signature_falsifiee_refusee():
    """La charge est remplacee pour s'octroyer toutes les portees."""
    jeton = creer_jwt({"iss": ISS, "aud": AUD, "scope": "h2:export"}, SECRET)
    entete, _, signature = jeton.split(".")
    charge_truquee = _b64(json.dumps(
        {"iss": ISS, "aud": AUD, "scope": "*", "exp": int(time.time()) + 900},
        separators=(",", ":")).encode("utf-8"))
    with pytest.raises(ValueError, match="signature"):
        verifier_jwt(entete + "." + charge_truquee + "." + signature,
                     SECRET, iss=ISS, aud=AUD)


def test_jwt_signe_avec_un_autre_secret_refuse():
    jeton = creer_jwt({"iss": ISS, "aud": AUD}, "un-tout-autre-secret-de-service")
    with pytest.raises(ValueError, match="signature"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


def test_jwt_alg_none_refuse():
    """« alg: none » avec signature vide : jamais accepte."""
    jeton = fabriquer_jwt({"alg": "none", "typ": "JWT"},
                          {"iss": ISS, "aud": AUD, "scope": "*",
                           "exp": int(time.time()) + 900},
                          signature=b"")
    with pytest.raises(ValueError, match="algorithme"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


def test_jwt_alg_hs512_refuse():
    """Confusion d'algorithme : seul HS256 est accepte, meme bien signe."""
    jeton = fabriquer_jwt({"alg": "HS512", "typ": "JWT"},
                          {"iss": ISS, "aud": AUD, "exp": int(time.time()) + 900},
                          algo=hashlib.sha512)
    with pytest.raises(ValueError, match="algorithme"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


def test_jwt_type_inattendu_refuse():
    jeton = fabriquer_jwt({"alg": "HS256", "typ": "autre"},
                          {"iss": ISS, "aud": AUD, "exp": int(time.time()) + 900})
    with pytest.raises(ValueError, match="type de jeton"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


def test_jwt_expire_refuse():
    jeton = creer_jwt({"iss": ISS, "aud": AUD}, SECRET, duree_s=60)
    emis = verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)["iat"]
    with pytest.raises(ValueError, match="expire"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD, maintenant=emis + 60 + 31)


def test_jwt_tolere_une_petite_desynchronisation_d_horloge():
    """Marge de 30 s : une horloge legerement decalee ne casse pas l'echange."""
    jeton = creer_jwt({"iss": ISS, "aud": AUD}, SECRET, duree_s=60)
    emis = verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)["iat"]
    assert verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD, maintenant=emis + 80)["iat"] == emis


def test_jwt_pas_encore_valide_refuse():
    jeton = creer_jwt({"iss": ISS, "aud": AUD}, SECRET)
    emis = verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)["iat"]
    with pytest.raises(ValueError, match="pas encore valide"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD, maintenant=emis - 31)


@pytest.mark.parametrize("exp", [None, "bientot", True])
def test_jwt_sans_exp_exploitable_refuse(exp):
    """exp obligatoire : un jeton sans expiration vaut un jeton eternel."""
    charge = {"iss": ISS, "aud": AUD, "scope": "h2:export"}
    if exp is not None:
        charge["exp"] = exp
    jeton = fabriquer_jwt({"alg": "HS256", "typ": "JWT"}, charge)
    with pytest.raises(ValueError, match="exp"):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


@pytest.mark.parametrize("iss, aud, motif", [
    ("un-autre-emetteur", AUD, "emetteur"),
    (ISS, "H1", "destinataire"),
    (ISS, None, "destinataire"),
])
def test_jwt_emetteur_ou_destinataire_inattendu_refuse(iss, aud, motif):
    jeton = creer_jwt({"iss": iss, "aud": aud}, SECRET)
    with pytest.raises(ValueError, match=motif):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


def test_jwt_destinataire_en_liste_accepte():
    """aud peut etre une liste : il suffit qu'elle contienne le service."""
    jeton = creer_jwt({"iss": ISS, "aud": ["H1", "H2", "outil-audit"]}, SECRET)
    assert verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)["aud"] == ["H1", "H2",
                                                                   "outil-audit"]


@pytest.mark.parametrize("jeton", [
    "",                     # vide
    "pas-un-jeton",         # un seul segment
    "a.b",                  # deux segments
    "a.b.c.d",              # quatre segments
    "###.###.###",          # segments non base64url
])
def test_jwt_mal_forme_refuse(jeton):
    with pytest.raises(ValueError):
        verifier_jwt(jeton, SECRET, iss=ISS, aud=AUD)


@pytest.mark.parametrize("champ", ["scope", "portees"])
def test_jwt_portees_lues_dans_scope_ou_portees(reglages, champ):
    conf = reglages(SEC_JWT_SECRET=SECRET, SEC_JWT_ISS=ISS)
    jeton = creer_jwt({"sub": "h1-jwt", "iss": ISS, "aud": conf.jwt_aud,
                       champ: "h2:export h2:import"}, SECRET)
    appelant = Verificateur(conf).verifier("Bearer " + jeton)
    assert appelant.source == "jwt"
    assert appelant.client == "h1-jwt"
    assert appelant.portees == frozenset({"h2:export", "h2:import"})
    assert appelant.autorise("h2:export")
    assert not appelant.autorise("h2:audit")


def test_jwt_refuse_par_le_verificateur_donne_401(reglages):
    """Le detail du refus va au journal (motif), pas au client (message)."""
    conf = reglages(SEC_JWT_SECRET=SECRET, SEC_JWT_ISS=ISS)
    jeton = creer_jwt({"sub": "x", "iss": "un-autre-emetteur", "aud": conf.jwt_aud},
                      SECRET)
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(conf).verifier("Bearer " + jeton)
    assert refus.value.http == 401
    assert refus.value.motif.startswith("jwt:")
    assert refus.value.message == "Jeton JWT refuse."


def test_jwt_ignore_quand_aucun_secret_n_est_configure(reglages, registre):
    """Sans SEC_JWT_SECRET, un JWT bien forme n'est qu'un jeton inconnu."""
    jeton = creer_jwt({"sub": "x", "iss": ISS, "aud": AUD, "scope": "*"}, SECRET)
    with pytest.raises(AccesRefuse) as refus:
        Verificateur(reglages()).verifier("Bearer " + jeton)
    assert (refus.value.http, refus.value.motif) == (401, "jeton_invalide")


# ---------------------------------------------------------------------------
# Diagnostic de configuration
# ---------------------------------------------------------------------------
def test_diagnostic_signale_l_absence_de_source_de_jetons(reglages):
    anomalies = Verificateur(reglages()).diagnostic()
    assert any("aucune source de jetons" in ligne for ligne in anomalies)


def test_diagnostic_signale_un_jeton_partage_trop_court(reglages):
    anomalies = Verificateur(reglages(H2_TOKEN="court")).diagnostic()
    assert any("entropie insuffisante" in ligne for ligne in anomalies)
    assert any("tous les droits" in ligne for ligne in anomalies)


def test_diagnostic_signale_le_mode_strict_sans_tls(reglages, registre):
    anomalies = Verificateur(reglages(SEC_MODE="strict", SEC_TLS_REQUIS="0")).diagnostic()
    assert any("SEC_TLS_REQUIS=0" in ligne for ligne in anomalies)


def test_diagnostic_signale_un_jeton_expire_du_registre(reglages, chemin_registre):
    ecrire_registre(chemin_registre,
                    entree_registre(id="poste-oublie", expire_le="2020-01-01T00:00:00Z"))
    anomalies = Verificateur(reglages()).diagnostic()
    assert any("jeton expire dans le registre" in ligne and "poste-oublie" in ligne
               for ligne in anomalies)


def test_diagnostic_vide_quand_tout_est_en_place(reglages, registre):
    assert Verificateur(reglages(SEC_MODE="strict", SEC_TLS_REQUIS="1")).diagnostic() == []


# ---------------------------------------------------------------------------
# Configuration (dataclass gelee)
# ---------------------------------------------------------------------------
def test_configuration_prefixe_les_portees_par_le_service(reglages):
    assert reglages().portee("export") == "h2:export"
    assert reglages(service="H1").portee("import") == "h1:import"


def test_configuration_est_gelee(conf):
    """Toute variante passe par l'environnement : l'objet n'est pas modifiable."""
    with pytest.raises(Exception):
        conf.mode = "local"


def test_mode_inconnu_retombe_sur_strict(reglages):
    assert reglages(SEC_MODE="n-importe-quoi").strict is True
    assert reglages(SEC_MODE="LOCAL").strict is False


def test_tls_requis_suit_le_mode_par_defaut(reglages):
    assert reglages(SEC_MODE="strict", SEC_TLS_REQUIS=None).tls_requis is True
    assert reglages(SEC_MODE="local", SEC_TLS_REQUIS=None).tls_requis is False


def test_valeur_entiere_illisible_retombe_sur_le_defaut(reglages):
    assert reglages(SEC_DEBIT_PAR_MINUTE="beaucoup").debit_par_minute == 120


def test_service_inconnu_refuse():
    with pytest.raises(ValueError, match="Service inconnu"):
        charger("H9")


def test_le_jeton_partage_n_apparait_pas_dans_le_repr(reglages):
    """repr(Configuration) peut finir dans un journal : pas de secret dedans."""
    conf = reglages(H2_TOKEN=JETON_PARTAGE)
    assert conf.jeton_historique == JETON_PARTAGE
    assert JETON_PARTAGE not in repr(conf)
