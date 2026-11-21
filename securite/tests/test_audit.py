"""Journal de securite : JSONL chaine, pseudonymisation, masquage des valeurs.

Le journal est une piece de conformite (loi 09-08) : il doit tracer chaque
requete SANS contenir de donnee de sante, et une retouche ponctuelle doit se
voir. Les tests ci-dessous verifient ces deux exigences.
"""

import json
import threading

import pytest

from securite.audit import (
    ENTETES_INTERDITES,
    PARAMETRES_SENSIBLES,
    JournalSecurite,
    empreinte_entree,
    horodatage,
    verifier_chaine,
)


def fabriquer(chemin, sel="sel-de-test", service="H2", **options):
    return JournalSecurite(chemin, sel=sel, service=service, **options)


def lignes_brutes(chemin):
    """Lignes du journal, en octets : aucune traduction de fin de ligne."""
    return [ligne for ligne in chemin.read_bytes().split(b"\n") if ligne.strip()]


def reecrire(chemin, lignes):
    chemin.write_bytes(b"\n".join(lignes) + b"\n")


def recanoniser(entree):
    return json.dumps(entree, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def remplir(journal, nombre):
    for numero in range(nombre):
        journal.enregistrer("acces", http=200, methode="GET", numero=numero)


# ---------------------------------------------------------------------------
# Ecriture
# ---------------------------------------------------------------------------
def test_une_ligne_json_par_appel(chemin_journal):
    journal = fabriquer(chemin_journal)
    journal.enregistrer("acces", http=200, methode="GET")
    journal.enregistrer("acces", http=401, motif="jeton_absent")
    lignes = lignes_brutes(chemin_journal)
    assert len(lignes) == 2
    premiere = json.loads(lignes[0])
    assert premiere["evenement"] == "acces"
    assert premiere["service"] == "H2"
    assert premiere["http"] == 200
    assert premiere["horodatage"].endswith("Z")
    assert json.loads(lignes[1])["motif"] == "jeton_absent"


def test_champs_vides_ne_sont_pas_journalises(chemin_journal):
    """Une ligne de journal ne porte que des informations utiles."""
    entree = fabriquer(chemin_journal).enregistrer("acces", http=200, client=None,
                                                   motif="", portee=None)
    assert "client" not in entree
    assert "motif" not in entree
    assert "portee" not in entree


def test_dossier_de_journal_cree_a_la_demande(dossier):
    chemin = dossier / "journaux" / "sous-dossier" / "securite.jsonl"
    fabriquer(chemin).enregistrer("demarrage", resultat="succes")
    assert chemin.exists()
    assert verifier_chaine(chemin)["lignes"] == 1


def test_aucun_entete_sensible_dans_une_ligne_de_journal(chemin_journal):
    journal = fabriquer(chemin_journal)
    journal.enregistrer("acces", http=200, jeton="abcdef012345", client="h1-chu")
    entree = json.loads(lignes_brutes(chemin_journal)[0])
    assert "authorization" in ENTETES_INTERDITES
    assert ENTETES_INTERDITES.isdisjoint(entree)


def test_horodatage_en_utc_avec_millisecondes():
    valeur = horodatage()
    assert valeur.endswith("Z")
    assert len(valeur) == len("2026-01-01T00:00:00.000Z")


def test_empreinte_entree_independante_de_l_ordre_des_cles():
    assert empreinte_entree({"a": 1, "b": 2}) == empreinte_entree({"b": 2, "a": 1})
    assert empreinte_entree({"a": 1}) != empreinte_entree({"a": 2})


# ---------------------------------------------------------------------------
# Chainage
# ---------------------------------------------------------------------------
def test_chaine_intacte_sur_un_journal_normal(chemin_journal):
    journal = fabriquer(chemin_journal)
    remplir(journal, 5)
    assert verifier_chaine(chemin_journal) == {
        "lignes": 5, "intact": True, "premiere_rupture": None,
        "illisibles": 0, "absent": False}
    assert json.loads(lignes_brutes(chemin_journal)[0])["prec"] == "genesis"


def test_alteration_du_chainage_detectee_sur_la_ligne_touchee(chemin_journal):
    """Reecrire le champ « prec » d'une ligne : rupture sur cette ligne meme."""
    journal = fabriquer(chemin_journal)
    remplir(journal, 4)
    lignes = lignes_brutes(chemin_journal)
    entree = json.loads(lignes[1])
    entree["prec"] = "0" * 64
    lignes[1] = recanoniser(entree)
    reecrire(chemin_journal, lignes)
    rapport = verifier_chaine(chemin_journal)
    assert rapport["intact"] is False
    assert rapport["premiere_rupture"] == 2
    assert rapport["lignes"] == 4


def test_alteration_du_contenu_detectee_sur_la_ligne_suivante(chemin_journal):
    """Maquiller un refus en succes casse l'empreinte portee par la ligne d'apres.

    Chaque ligne porte l'empreinte de la precedente : une retouche en ligne 2
    se voit donc en ligne 3. C'est ce qui rend le maquillage visible.
    """
    journal = fabriquer(chemin_journal)
    remplir(journal, 4)
    lignes = lignes_brutes(chemin_journal)
    entree = json.loads(lignes[1])
    entree["http"] = 200
    entree["resultat"] = "succes"
    lignes[1] = recanoniser(entree)
    reecrire(chemin_journal, lignes)
    rapport = verifier_chaine(chemin_journal)
    assert rapport["intact"] is False
    assert rapport["premiere_rupture"] == 3


def test_suppression_d_une_ligne_detectee(chemin_journal):
    journal = fabriquer(chemin_journal)
    remplir(journal, 4)
    lignes = lignes_brutes(chemin_journal)
    reecrire(chemin_journal, lignes[:1] + lignes[2:])
    rapport = verifier_chaine(chemin_journal)
    assert rapport["lignes"] == 3
    assert rapport["intact"] is False
    assert rapport["premiere_rupture"] == 2


def test_ligne_illisible_comptee_et_signalee(chemin_journal):
    journal = fabriquer(chemin_journal)
    remplir(journal, 2)
    with chemin_journal.open("ab") as fichier:
        fichier.write(b"ceci n'est pas du json\n")
    rapport = verifier_chaine(chemin_journal)
    assert rapport["lignes"] == 3
    assert rapport["illisibles"] == 1
    assert rapport["intact"] is False
    assert rapport["premiere_rupture"] == 3


def test_journal_absent_rapporte_absent(dossier):
    rapport = verifier_chaine(dossier / "jamais-ecrit.jsonl")
    assert rapport["absent"] is True
    assert rapport["lignes"] == 0
    assert rapport["intact"] is True


def test_reprise_de_la_chaine_sur_un_journal_existant(chemin_journal):
    """Au redemarrage du service, la chaine reprend ou le fichier s'arretait."""
    premier = fabriquer(chemin_journal)
    premier.enregistrer("demarrage", resultat="succes")
    premier.enregistrer("acces", http=200)
    second = fabriquer(chemin_journal)                 # nouveau processus
    second.enregistrer("acces", http=201)
    second.enregistrer("acces", http=202)
    rapport = verifier_chaine(chemin_journal)
    assert (rapport["lignes"], rapport["intact"]) == (4, True)
    troisieme = json.loads(lignes_brutes(chemin_journal)[2])
    assert troisieme["prec"] == empreinte_entree(json.loads(
        lignes_brutes(chemin_journal)[1]))


def test_ecritures_concurrentes_gardent_la_chaine_intacte(chemin_journal):
    """Huit fils d'execution ecrivent en meme temps : la chaine reste verifiable."""
    journal = fabriquer(chemin_journal)

    def ecrire(numero):
        for index in range(20):
            journal.enregistrer("acces", http=200, fil=numero, index=index)

    fils = [threading.Thread(target=ecrire, args=(numero,)) for numero in range(8)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()
    rapport = verifier_chaine(chemin_journal)
    assert rapport["lignes"] == 160
    assert rapport["intact"] is True


def test_rotation_archive_le_journal_et_repart_sur_une_chaine_verifiable(chemin_journal):
    """Apres rotation, le nouveau fichier doit etre verifiable a lui seul.

    La chaine repart de « genesis » : sinon `verifier_chaine` signalerait une
    rupture des la premiere ligne du journal courant, a chaque rotation.
    """
    journal = fabriquer(chemin_journal, taille_rotation=400)
    for _ in range(500):
        if chemin_journal.exists() and chemin_journal.stat().st_size >= 400:
            break
        journal.enregistrer("acces", http=200)
    else:
        pytest.fail("la taille de rotation n'a jamais ete atteinte")

    lignes_archivees = verifier_chaine(chemin_journal)["lignes"]
    journal.enregistrer("acces", http=201)             # declenche la rotation

    archives = [chemin for chemin in chemin_journal.parent.iterdir()
                if chemin.name.startswith(chemin_journal.name + ".")]
    assert len(archives) == 1
    archive = verifier_chaine(archives[0])
    assert (archive["lignes"], archive["intact"]) == (lignes_archivees, True)

    courant = verifier_chaine(chemin_journal)
    assert courant["lignes"] == 1
    assert courant["intact"] is True
    assert json.loads(lignes_brutes(chemin_journal)[0])["prec"] == "genesis"


# ---------------------------------------------------------------------------
# Pseudonymisation
# ---------------------------------------------------------------------------
def test_pseudonyme_stable_et_non_reversible(chemin_journal):
    journal = fabriquer(chemin_journal)
    assert journal.pseudonyme("P2-0051") == journal.pseudonyme("P2-0051")
    assert journal.pseudonyme("P2-0051") != journal.pseudonyme("P2-0052")
    assert journal.pseudonyme("P2-0051").startswith("p:")
    assert "P2-0051" not in journal.pseudonyme("P2-0051")
    assert "0051" not in journal.pseudonyme("P2-0051")
    assert journal.pseudonyme(None) is None
    assert journal.pseudonyme("") is None


def test_pseudonyme_change_avec_le_sel(chemin_journal):
    """Deux postes aux sels differents ne peuvent pas correler leurs journaux."""
    hopital1 = fabriquer(chemin_journal, sel="sel-hopital-1")
    hopital2 = fabriquer(chemin_journal, sel="sel-hopital-2")
    assert hopital1.pseudonyme("P2-0051") != hopital2.pseudonyme("P2-0051")


@pytest.mark.parametrize("chemin, gabarit, identifiant", [
    ("/api/patients/P2-0051/bundle", "/api/patients/{id}/bundle", "P2-0051"),
    ("/Patient/123456", "/Patient/{id}", "123456"),
    ("/Patient/AB123456", "/Patient/{id}", "AB123456"),
    ("/api/patients/ABC123/bundle", "/api/patients/{id}/bundle", "ABC123"),
    ("/Patient/nom-patient", "/Patient/{id}", "nom-patient"),
])
def test_normaliser_chemin_remplace_l_identifiant(chemin_journal, chemin, gabarit,
                                                  identifiant):
    journal = fabriquer(chemin_journal)
    obtenu, pseudonyme = journal.normaliser_chemin(chemin)
    assert obtenu == gabarit
    assert pseudonyme == journal.pseudonyme(identifiant)
    assert pseudonyme.startswith("p:")
    assert identifiant not in obtenu


@pytest.mark.parametrize("chemin", ["/health", "/metadata", "/api/retours",
                                    "/api/retours/simulation", "/"])
def test_normaliser_chemin_laisse_les_routes_sans_identifiant(chemin_journal, chemin):
    assert fabriquer(chemin_journal).normaliser_chemin(chemin) == (chemin, None)


def test_normaliser_chemin_tolere_un_chemin_vide(chemin_journal):
    assert fabriquer(chemin_journal).normaliser_chemin("") == ("/", None)


# ---------------------------------------------------------------------------
# Masquage des parametres de recherche
# ---------------------------------------------------------------------------
def test_masquer_parametres_masque_la_valeur_sensible(chemin_journal):
    masques = fabriquer(chemin_journal).masquer_parametres(
        "identifier=urn:ma:cin|AB123456&_count=5")
    assert masques == {"identifier": "***", "_count": "5"}


def test_valeur_sensible_absente_de_la_ligne_de_journal(chemin_journal):
    """Un CIN passe en parametre ne doit apparaitre nulle part dans le journal."""
    journal = fabriquer(chemin_journal)
    requete = "identifier=urn:ma:cin|AB123456&family=ALAMI&_count=5"
    journal.enregistrer("acces", http=200, chemin="/Patient",
                        parametres=journal.masquer_parametres(requete))
    ligne = chemin_journal.read_text(encoding="utf-8")
    assert "AB123456" not in ligne
    assert "ALAMI" not in ligne
    assert '"identifier":"***"' in ligne
    assert '"family":"***"' in ligne
    assert '"_count":"5"' in ligne


@pytest.mark.parametrize("nom", sorted(PARAMETRES_SENSIBLES))
def test_tous_les_parametres_sensibles_sont_masques(chemin_journal, nom):
    masques = fabriquer(chemin_journal).masquer_parametres(nom + "=valeur-privee")
    assert masques == {nom: "***"}


def test_masquage_insensible_a_la_casse_du_parametre(chemin_journal):
    assert fabriquer(chemin_journal).masquer_parametres("IDENTIFIER=x") == {
        "IDENTIFIER": "***"}


def test_parametre_inconnu_ne_conserve_pas_de_donnee(chemin_journal):
    assert fabriquer(chemin_journal).masquer_parametres("commentaire=donnee-clinique") == {
        "commentaire": "***"}


@pytest.mark.parametrize("requete, attendu", [
    ("", {}),
    ("&&", {}),
    ("=valeur-sans-nom", {}),
    ("drapeau", {"drapeau": ""}),
    ("_count=5&_count=9", {"_count": "9"}),
])
def test_masquer_parametres_tolere_les_formes_etranges(chemin_journal, requete, attendu):
    assert fabriquer(chemin_journal).masquer_parametres(requete) == attendu


def test_valeur_non_sensible_tronquee(chemin_journal):
    """Une valeur tres longue est coupee : le journal reste lisible."""
    masques = fabriquer(chemin_journal).masquer_parametres("_count=" + "9" * 100)
    assert masques["_count"] == "9" * 60


# ---------------------------------------------------------------------------
# Adresses IP
# ---------------------------------------------------------------------------
def test_ip_v4_anonymisee_en_24(chemin_journal):
    assert fabriquer(chemin_journal, anonymiser_ip=True).ip("192.168.1.42") == \
        "192.168.1.0/24"


def test_ip_v6_anonymisee_en_48(chemin_journal):
    assert fabriquer(chemin_journal, anonymiser_ip=True).ip(
        "2001:db8:85a3::8a2e:370:7334") == "2001:db8:85a3::/48"


def test_ip_conservee_entiere_quand_l_option_est_desactivee(chemin_journal):
    journal = fabriquer(chemin_journal, anonymiser_ip=False)
    assert journal.ip("192.168.1.42") == "192.168.1.42"
    assert journal.ip("2001:db8:85a3::8a2e:370:7334") == "2001:db8:85a3::8a2e:370:7334"


def test_ip_absente_reste_absente(chemin_journal):
    journal = fabriquer(chemin_journal, anonymiser_ip=True)
    assert journal.ip(None) is None
    assert journal.ip("") is None


def test_valeur_non_ip_laissee_telle_quelle(chemin_journal):
    assert fabriquer(chemin_journal, anonymiser_ip=True).ip("inconnu") == "inconnu"


def test_option_d_anonymisation_lue_dans_l_environnement(monkeypatch, chemin_journal):
    monkeypatch.setenv("SEC_ANONYMISER_IP", "1")
    journal = fabriquer(chemin_journal)
    assert journal.anonymiser_ip is True
    assert journal.ip("10.1.2.3") == "10.1.2.0/24"


# ---------------------------------------------------------------------------
# Robustesse
# ---------------------------------------------------------------------------
def test_journal_impossible_a_ecrire_n_interrompt_pas_l_appel(dossier):
    """Un journal injoignable est compte comme incident, sans casser l'appel."""
    obstacle = dossier / "pas-un-dossier.txt"
    obstacle.write_text("je suis un fichier, pas un dossier", encoding="utf-8")
    journal = fabriquer(obstacle / "journal.jsonl")
    entree = journal.enregistrer("acces", http=200, methode="GET")
    assert entree["http"] == 200
    assert entree["prec"] == "genesis"
    assert journal.erreurs_ecriture == 1
    journal.enregistrer("acces", http=200)
    assert journal.erreurs_ecriture == 2
