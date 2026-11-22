"""
Dossiers de test = copies des lignes Oracle des cas de test (cas_de_test_h1.sql).
Permettent de tester les adaptateurs SANS Oracle.
"""
from copy import deepcopy
from datetime import datetime as dt


def _dossier(ipp, nom, prenom, sexe, naiss, cin, tel, ville, gs, statut="ACTIF",
             sejour=None, diags=(), mesures=(), allergies=()):
    s = dict(sejour)
    s["diagnostics"] = [dict(id_diagnostic=f"DGT-{ipp[3:]}-{i+1}", id_sejour=s["id_sejour"],
                             libelle=lib, code_local=code, date_diagnostic=s["date_admission"])
                        for i, (lib, code) in enumerate(diags)]
    s["mesures"] = [dict(id_mesure=f"MST-{ipp[3:]}-{i+1}", id_sejour=s["id_sejour"],
                         code_local=c, valeur=v, unite=u, date_mesure=s["date_admission"])
                    for i, (c, v, u) in enumerate(mesures)]
    return {
        "patient": dict(ipp=ipp, nom=nom, prenom=prenom, sexe=sexe, date_naissance=naiss,
                        cin=cin, telephone=tel, adresse="N°1, Rue Test", ville=ville,
                        groupe_sanguin=gs),
        "consentement": dict(id_consentement=f"CST-{ipp[3:]}", ipp=ipp, statut=statut,
                             finalite="Partage soins", date_consentement=dt(2026, 10, 1)),
        "sejours": [s],
        "allergies": list(allergies),
    }


def sej(ipp, service, motif, medecin="Dr Bennani", sortie=None, adm=dt(2026, 10, 5, 9, 0)):
    return dict(id_sejour=f"ST-{ipp[3:]}-1", ipp=ipp, type_sejour="CONS", service=service,
                date_admission=adm, date_sortie=sortie, medecin=medecin, motif=motif)


DOSSIERS = {
    # S1 nominal
    "S1": _dossier("P1-0106", "Alaoui", "Youssef", "M", dt(1968, 4, 12), "AB123456",
                   "06 12 34 56 78", "Settat", "A+",
                   sejour=sej("P1-0106", "Endocrinologie", "Suivi diabète type 2"),
                   diags=[("Diabète de type 2", "DIAB2")],
                   mesures=[("TA_SYS", 138, "mm[Hg]"), ("TA_DIA", 85, "mm[Hg]"),
                            ("HBA1C", 8.2, "%"), ("GLY", 1.60, "g/L")],
                   allergies=[dict(id_allergie="ALT-0106-1", ipp="P1-0106", code_allergene="ALL_FLUO",
                                   libelle="Fluorescéine", criticite="ELEVEE")]),
    # D1 consentement refusé
    "D1": _dossier("P1-0108", "Idrissi", "Omar", "M", dt(1990, 2, 17), "J778241",
                   "06 34 56 78 90", "Rabat", "B+", statut="REFUSE",
                   sejour=sej("P1-0108", "Médecine interne", "Céphalées", "Dr Tazi"),
                   diags=[("Migraine", "MIG")], mesures=[("TA_SYS", 120, "mm[Hg]")]),
    # D4 pas de CIN
    "D4": _dossier("P1-0112", "Ouazzani", "Rachid", "M", dt(1972, 7, 25), None,
                   "06 78 90 12 34", "Tanger", "A+",
                   sejour=sej("P1-0112", "Médecine interne", "Suivi diabète type 2", "Dr Tazi"),
                   diags=[("Diabète de type 2", "DIAB2")], mesures=[("GLY", 1.50, "g/L")]),
    # D7 mineure sans CIN
    "D7": _dossier("P1-0115", "Lahlou", "Yasmine", "F", dt(2010, 9, 6), None,
                   "06 11 22 33 44", "Salé", "O+",
                   sejour=sej("P1-0115", "Médecine interne", "Asthme", "Dr Idrissi"),
                   diags=[("Asthme", "ASTM")], mesures=[("SPO2", 97, "%")]),
    # D8 date de naissance manquante
    "D8": _dossier("P1-0116", "Kettani", "Mehdi", "M", None, "MK445566",
                   "06 22 33 44 55", "Meknès", "A+",
                   sejour=sej("P1-0116", "Médecine interne", "Contrôle tension", "Dr Tazi"),
                   diags=[("Hypertension artérielle essentielle", "HTA")]),
    # D9 code maladie inconnu
    "D9": _dossier("P1-0117", "Sebti", "Hassan", "M", dt(1970, 11, 11), "HS778899",
                   "06 33 44 55 66", "Tétouan", "O+",
                   sejour=sej("P1-0117", "Endocrinologie", "Diabète (saisie libre)", "Dr Alaoui"),
                   diags=[("Diabète type 2 (saisie libre)", "DT2")]),
    # D10 glycémie sans unité
    "D10": _dossier("P1-0118", "Naciri", "Latifa", "F", dt(1965, 3, 3), "LN990011",
                    "06 44 55 66 77", "Safi", "B+",
                    sejour=sej("P1-0118", "Endocrinologie", "Suivi diabète", "Dr Alaoui"),
                    diags=[("Diabète de type 2", "DIAB2")], mesures=[("GLY", 1.8, None)]),
    # D11 SpO2 impossible
    "D11": _dossier("P1-0119", "Zniber", "Adil", "M", dt(1985, 6, 6), "AZ223344",
                    "06 55 66 77 88", "Nador", "A-",
                    sejour=sej("P1-0119", "Pneumologie", "Dyspnée", "Dr Idrissi"),
                    diags=[("Asthme", "ASTM")], mesures=[("SPO2", 150, "%"), ("FC", 80, "/min")]),
    # D12 sortie avant admission
    "D12": _dossier("P1-0120", "Tahiri", "Samira", "F", dt(1977, 8, 8), "ST556677",
                    "06 66 77 88 99", "Larache", "O+",
                    sejour=sej("P1-0120", "Cardiologie", "Contrôle", "Dr Bennani",
                               sortie=dt(2026, 10, 1, 9, 0)),
                    diags=[("Hypertension artérielle essentielle", "HTA")],
                    mesures=[("TA_SYS", 150, "mm[Hg]")]),
}


def dossier(cas):
    return deepcopy(DOSSIERS[cas])
