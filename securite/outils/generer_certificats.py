"""Cree l'autorite de certification interne et les certificats des deux API.

    py securite/outils/generer_certificats.py
    py securite/outils/generer_certificats.py --ip 192.168.1.20 --dns poste-h1
    py securite/outils/generer_certificats.py --service h2 --ip 192.168.1.31
    py securite/outils/generer_certificats.py --decrire

Resultat dans `securite/certificats/` :

    ac_interop.cert.pem    certificat racine : a transmettre a l'autre hopital
    ac_interop.key.pem     cle privee de l'autorite : ne sort JAMAIS du poste
    h1.cert.pem h1.key.pem certificat serveur de H1
    h2.cert.pem h2.key.pem certificat serveur de H2

Les clients modernes ne regardent que le SubjectAlternativeName : il faut y
mettre l'adresse reellement utilisee pour joindre le service. Sur un reseau
local, c'est l'adresse IP du poste, pas 127.0.0.1 (qui ne designe que la machine
qui execute la commande). D'ou les options --ip et --dns.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

from securite.tls import (                                        # noqa: E402
    OutilsTlsAbsents,
    decrire,
    generer_autorite,
    generer_certificat_serveur,
)

CERTIFICATS = RACINE / "securite" / "certificats"
PORTS = {"h1": 8000, "h2": 8002}


def adresses_locales() -> list:
    """Adresses IPv4 du poste, pour les proposer dans le certificat."""
    trouvees = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            adresse = info[4][0]
            if adresse not in trouvees and not adresse.startswith("127."):
                trouvees.append(adresse)
    except OSError:
        pass
    return trouvees


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Genere l'autorite interne et les certificats TLS des deux API.")
    analyseur.add_argument("--service", choices=["h1", "h2", "les-deux"], default="les-deux")
    analyseur.add_argument("--dns", action="append", default=[],
                           help="nom de machine supplementaire (repetable)")
    analyseur.add_argument("--ip", action="append", default=[],
                           help="adresse IP supplementaire (repetable)")
    analyseur.add_argument("--jours", type=int, default=365)
    analyseur.add_argument("--forcer", action="store_true",
                           help="remplacer des certificats existants")
    analyseur.add_argument("--decrire", action="store_true",
                           help="afficher les certificats deja presents et leur echeance")
    arguments = analyseur.parse_args(argv)

    try:
        if arguments.decrire:
            if not CERTIFICATS.exists():
                print("Aucun certificat : lancer l'outil sans --decrire.")
                return 1
            for chemin in sorted(CERTIFICATS.glob("*.cert.pem")):
                details = decrire(chemin)
                print("\n" + chemin.name)
                print("  sujet          : " + details["sujet"])
                print("  emetteur       : " + details["emetteur"])
                print("  expire le      : " + details["valide_au"])
                print("  jours restants : " + str(details["jours_restants"]))
                print("  noms couverts  : " + (", ".join(details["noms"]) or "aucun"))
                if details["jours_restants"] < 30:
                    print("  ATTENTION : a renouveler (--forcer).")
            return 0

        CERTIFICATS.mkdir(parents=True, exist_ok=True)
        ac = generer_autorite(CERTIFICATS, forcer=arguments.forcer)
        print("Autorite interne : " + str(ac[1]))
        print("  cle privee     : " + str(ac[0]) + "   (ne jamais transmettre)")

        dns = ["localhost", socket.gethostname().lower()] + list(arguments.dns)
        ips = ["127.0.0.1", "::1"] + list(arguments.ip) + adresses_locales()
        dns = list(dict.fromkeys(n for n in dns if n))
        ips = list(dict.fromkeys(i for i in ips if i))

        services = ["h1", "h2"] if arguments.service == "les-deux" else [arguments.service]
        for service in services:
            cle, cert = generer_certificat_serveur(
                CERTIFICATS, service, noms_dns=dns, adresses_ip=ips,
                jours=arguments.jours, ac=ac, forcer=arguments.forcer)
            print("\nCertificat " + service.upper() + " : " + str(cert))
            print("  noms couverts : " + ", ".join(dns + ips))
            print("  lancement     : uvicorn --ssl-keyfile " + str(cle)
                  + " --ssl-certfile " + str(cert) + " --port " + str(PORTS[service]))

        print("\nA faire ensuite :")
        print("  1. transmettre " + str(ac[1]) + " a l'autre hopital (le certificat SEUL)")
        print("  2. chez l'appelant : SEC_CA=<chemin du certificat racine recu>")
        print("  3. detail de la procedure : docs/securite/tls-https.md")
        return 0
    except OutilsTlsAbsents as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
