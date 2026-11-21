"""Generation des certificats TLS du prototype (HTTPS entre les deux hopitaux).

Les deux API echangent des donnees de sante : le trafic doit etre chiffre, et
chaque hopital doit pouvoir verifier qu'il parle bien a l'autre et pas a un
intermediaire. Un vrai deploiement utiliserait des certificats delivres par une
autorite reconnue. Pour un prototype sur reseau local, on cree une petite
autorite de certification interne :

    ac_interop.cert.pem     certificat racine, a installer chez les DEUX hopitaux
    ac_interop.key.pem      cle privee de l'autorite, ne quitte jamais le poste
    h1.cert.pem / h1.key.pem    certificat serveur de H1
    h2.cert.pem / h2.key.pem    certificat serveur de H2

H1 demarre uvicorn avec son certificat, H2 appelle H1 en pointant `SEC_CA` sur
le certificat racine : la verification reussit alors sans desactiver TLS.

Cles ECDSA P-256 : plus courtes que RSA pour une solidite equivalente, et
acceptees par httpx, uvicorn et les navigateurs.
"""

from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path
from typing import Iterable, Optional

JOURS_AC = 1825                    # 5 ans pour l'autorite interne
JOURS_SERVEUR = 365                # 1 an pour un certificat serveur
NOM_AC = "Interop Sante - autorite de test"


class OutilsTlsAbsents(RuntimeError):
    """La bibliotheque `cryptography` n'est pas installee."""


def _modules():
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
    except ImportError as exc:                       # pragma: no cover
        raise OutilsTlsAbsents(
            "Installer la dependance : py -m pip install \"cryptography>=43\"") from exc
    return x509, hashes, serialization, ec, NameOID


def _ecrire_cle(chemin: Path, cle) -> None:
    """Ecrit une cle privee en PEM non chiffre, avec des droits restreints."""
    _, _, serialization, _, _ = _modules()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(cle.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    try:
        chemin.chmod(0o600)                          # sans effet reel sous Windows
    except OSError:
        pass


def _ecrire_cert(chemin: Path, certificat) -> None:
    _, _, serialization, _, _ = _modules()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(certificat.public_bytes(serialization.Encoding.PEM))


def _nom(NameOID, x509, commun: str, organisation: str = "Projet interoperabilite"):
    return x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "MA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organisation),
        x509.NameAttribute(NameOID.COMMON_NAME, commun),
    ])


def generer_autorite(dossier: Path, *, nom: str = NOM_AC, jours: int = JOURS_AC,
                     forcer: bool = False) -> tuple:
    """Cree l'autorite de certification interne. Renvoie (cle, certificat)."""
    x509, hashes, _, ec, NameOID = _modules()
    dossier = Path(dossier)
    chemin_cle = dossier / "ac_interop.key.pem"
    chemin_cert = dossier / "ac_interop.cert.pem"
    if chemin_cert.exists() and not forcer:
        return chemin_cle, chemin_cert               # jamais de remplacement silencieux

    cle = ec.generate_private_key(ec.SECP256R1())
    sujet = _nom(NameOID, x509, nom)
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    certificat = (
        x509.CertificateBuilder()
        .subject_name(sujet)
        .issuer_name(sujet)
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(maintenant - datetime.timedelta(minutes=5))
        .not_valid_after(maintenant + datetime.timedelta(days=jours))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(cle.public_key()),
                       critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(cle.public_key()),
                       critical=False)
        .sign(cle, hashes.SHA256())
    )
    _ecrire_cle(chemin_cle, cle)
    _ecrire_cert(chemin_cert, certificat)
    return chemin_cle, chemin_cert


def _charger_ac(chemin_cle: Path, chemin_cert: Path):
    x509, _, serialization, _, _ = _modules()
    cle = serialization.load_pem_private_key(Path(chemin_cle).read_bytes(), password=None)
    certificat = x509.load_pem_x509_certificate(Path(chemin_cert).read_bytes())
    return cle, certificat


def generer_certificat_serveur(dossier: Path, prefixe: str, *,
                               noms_dns: Iterable = ("localhost",),
                               adresses_ip: Iterable = ("127.0.0.1",),
                               jours: int = JOURS_SERVEUR,
                               ac: Optional[tuple] = None,
                               forcer: bool = False) -> tuple:
    """Cree un certificat serveur signe par l'autorite interne.

    `noms_dns` et `adresses_ip` alimentent le SubjectAlternativeName : un client
    moderne ne regarde QUE cette extension, pas le Common Name. Il faut donc y
    mettre l'adresse reellement utilisee par l'autre hopital (nom de machine ou
    adresse IP du poste sur le reseau local).
    """
    x509, hashes, _, ec, NameOID = _modules()
    dossier = Path(dossier)
    chemin_cle = dossier / (prefixe + ".key.pem")
    chemin_cert = dossier / (prefixe + ".cert.pem")
    if chemin_cert.exists() and not forcer:
        return chemin_cle, chemin_cert

    ac_cle_chemin, ac_cert_chemin = ac or generer_autorite(dossier)
    ac_cle, ac_cert = _charger_ac(ac_cle_chemin, ac_cert_chemin)

    autres_noms = [x509.DNSName(str(n)) for n in noms_dns]
    for brute in adresses_ip:
        try:
            autres_noms.append(x509.IPAddress(ipaddress.ip_address(str(brute))))
        except ValueError:
            autres_noms.append(x509.DNSName(str(brute)))
    if not autres_noms:
        raise ValueError("au moins un nom DNS ou une adresse IP est requis")

    cle = ec.generate_private_key(ec.SECP256R1())
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    certificat = (
        x509.CertificateBuilder()
        .subject_name(_nom(NameOID, x509, prefixe))
        .issuer_name(ac_cert.subject)
        .public_key(cle.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(maintenant - datetime.timedelta(minutes=5))
        .not_valid_after(maintenant + datetime.timedelta(days=jours))
        .add_extension(x509.SubjectAlternativeName(autres_noms), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(cle.public_key()),
                       critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ac_cle.public_key()),
                       critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([
            x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
            x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(ac_cle, hashes.SHA256())
    )
    _ecrire_cle(chemin_cle, cle)
    _ecrire_cert(chemin_cert, certificat)
    return chemin_cle, chemin_cert


def decrire(chemin_cert: Path) -> dict:
    """Resume lisible d'un certificat : sujet, validite, noms couverts."""
    x509, _, _, _, _ = _modules()
    certificat = x509.load_pem_x509_certificate(Path(chemin_cert).read_bytes())
    try:
        san = certificat.extensions.get_extension_for_class(
            x509.SubjectAlternativeName).value
        noms = [str(n.value) for n in san]
    except x509.ExtensionNotFound:
        noms = []
    fin = certificat.not_valid_after_utc
    return {
        "sujet": certificat.subject.rfc4514_string(),
        "emetteur": certificat.issuer.rfc4514_string(),
        "valide_du": certificat.not_valid_before_utc.isoformat(),
        "valide_au": fin.isoformat(),
        "jours_restants": (fin - datetime.datetime.now(datetime.timezone.utc)).days,
        "noms": noms,
    }
