"""Imagerie DICOM commune : generation, desidentification, multipart, Orthanc, passerelle."""

import json
from datetime import datetime

import httpx
import pytest

from imagerie.dicom import (SOP_PHOTO_OPHTALMO, TAILLE_IMAGE, depuis_octets, desidentifier,
                            generer_etude, metadonnees_json, uid_serie, verifier_etude,
                            vers_octets)
from imagerie.dicomweb import (EntrepotMemoire, EntrepotOrthanc, ErreurDistante, ErreurPacs,
                               decoder_multipart, encoder_multipart, recuperer_etude_distante)

PATIENT = {"id": "P2-0051", "nom": "Alaoui", "prenom": "Youssef", "naissance": "1968-04-12", "sexe": "M"}
ETUDE = {"study_uid": "2.25.11060236952204337488", "accession": "ACC-005185",
         "description": "Color fundus photography, both eyes", "instances": 2,
         "date": datetime(2026, 9, 20, 14, 48)}


@pytest.fixture(scope="module")
def instances():
    return generer_etude(PATIENT, ETUDE, etablissement="Clinique Al Bacar")


# ── generation ───────────────────────────────────────────────────────────────
def test_etude_conforme_et_relisible(instances):
    assert len(instances) == 2
    relues = [depuis_octets(vers_octets(ds)) for ds in instances]
    for ds in relues:
        assert ds.SOPClassUID == SOP_PHOTO_OPHTALMO and ds.Modality == "OP"
        assert ds.StudyInstanceUID == ETUDE["study_uid"] and ds.SeriesInstanceUID == uid_serie(ETUDE["study_uid"])
        assert ds.PatientID == "P2-0051" and str(ds.PatientName) == "ALAOUI^Youssef"
        assert ds.PatientBirthDate == "19680412" and ds.StudyDate == "20260920"
        assert ds.Rows == ds.Columns == TAILLE_IMAGE and ds.SamplesPerPixel == 3
        assert len(ds.PixelData) == TAILLE_IMAGE * TAILLE_IMAGE * 3
        assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
    assert [ds.ImageLaterality for ds in relues] == ["R", "L"]
    assert len({ds.SOPInstanceUID for ds in relues}) == 2


def test_uids_stables_d_une_generation_a_l_autre(instances):
    encore = generer_etude(PATIENT, ETUDE, etablissement="x")
    assert [d.SOPInstanceUID for d in encore] == [d.SOPInstanceUID for d in instances]
    assert all(len(d.SOPInstanceUID) <= 64 for d in instances)


def test_verifier_etude_detecte_une_instance_etrangere(instances):
    assert verifier_etude(instances, ETUDE["study_uid"]) is None
    autre = generer_etude(PATIENT, {**ETUDE, "study_uid": "2.25.99"}, etablissement="x")
    assert "etrangere" in verifier_etude(instances + autre, ETUDE["study_uid"])


# ── desidentification ────────────────────────────────────────────────────────
def test_desidentification_profil_de_base(instances):
    ds = instances[0]
    ds.ReferringPhysicianName = "Dr Touimi"
    anonyme = desidentifier(ds, "p:1234abcd")
    texte = str(depuis_octets(vers_octets(anonyme)))
    for trace in ("Alaoui", "ALAOUI", "Youssef", "P2-0051", "19680412", "ACC-005185", "Touimi", "Bacar"):
        assert trace not in texte, trace
    assert anonyme.PatientIdentityRemoved == "YES" and str(anonyme.PatientName) == "p:1234abcd"
    assert anonyme.StudyInstanceUID == ds.StudyInstanceUID           # option « Retain UIDs »
    assert [c.CodeValue for c in anonyme.DeidentificationMethodCodeSequence] == ["113100", "113110"]
    assert str(ds.PatientName) == "ALAOUI^Youssef"                    # l'original n'est pas modifie


def test_metadonnees_sans_pixels(instances):
    meta = metadonnees_json(instances)
    assert len(meta) == 2 and "7FE00010" not in meta[0]
    assert meta[0]["0020000D"]["Value"] == [ETUDE["study_uid"]]


# ── multipart et entrepots ───────────────────────────────────────────────────
def test_multipart_aller_retour(instances):
    octets = [vers_octets(ds) for ds in instances]
    corps, type_contenu = encoder_multipart(octets)
    assert type_contenu.startswith('multipart/related; type="application/dicom"; boundary=')
    assert decoder_multipart(corps, type_contenu) == octets


def test_multipart_sans_frontiere():
    with pytest.raises(ErreurPacs):
        decoder_multipart(b"x", "multipart/related")


def test_entrepot_memoire_sans_doublon(instances):
    e = EntrepotMemoire()
    octets = [vers_octets(ds) for ds in instances]
    e.stocker(octets)
    e.stocker(octets)
    assert len(e.etude(ETUDE["study_uid"])) == 2 and not e.existe("2.25.1")


class FauxOrthanc:
    """Imite le plugin DICOMweb d'Orthanc (STOW, WADO, QIDO) avec authentification."""

    def __init__(self):
        self.memoire = EntrepotMemoire()
        self.requetes = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if requete.headers.get("authorization") != httpx.BasicAuth("pacs", "secret")._auth_header:
            return httpx.Response(401)
        chemin = requete.url.path
        if requete.method == "POST" and chemin == "/dicom-web/studies":
            self.memoire.stocker(decoder_multipart(requete.content, requete.headers["content-type"]))
            return httpx.Response(200, json={})
        if requete.method == "GET" and chemin == "/dicom-web/studies":
            uid = requete.url.params.get("StudyInstanceUID")
            return httpx.Response(200, json=[{}]) if self.memoire.existe(uid) else httpx.Response(204)
        if requete.method == "GET" and chemin.startswith("/dicom-web/studies/"):
            octets = self.memoire.etude(chemin.rsplit("/", 1)[1])
            if not octets:
                return httpx.Response(404)
            corps, type_contenu = encoder_multipart(octets)
            return httpx.Response(200, content=corps, headers={"Content-Type": type_contenu})
        return httpx.Response(400)


def _orthanc(faux, mdp="secret"):
    client = httpx.Client(transport=httpx.MockTransport(faux), auth=("pacs", mdp))
    return EntrepotOrthanc("http://127.0.0.1:8042/dicom-web", client=client)


def test_orthanc_stow_wado_qido(instances):
    faux = FauxOrthanc()
    pacs = _orthanc(faux)
    octets = [vers_octets(ds) for ds in instances]
    assert pacs.stocker(octets) == 2
    assert pacs.existe(ETUDE["study_uid"]) and not pacs.existe("2.25.1")
    assert sorted(pacs.etude(ETUDE["study_uid"])) == sorted(octets)
    assert pacs.etude("2.25.1") == []
    assert faux.requetes[1].headers["accept"] == "application/dicom+json"


def test_orthanc_identifiants_refuses():
    with pytest.raises(ErreurPacs):
        _orthanc(FauxOrthanc(), mdp="faux").etude("2.25.1")


def test_orthanc_injoignable():
    def panne(requete):
        raise httpx.ConnectError("refuse")
    pacs = EntrepotOrthanc("http://127.0.0.1:1/dicom-web",
                           client=httpx.Client(transport=httpx.MockTransport(panne)))
    with pytest.raises(ErreurPacs):
        pacs.existe("2.25.1")


def test_recuperation_distante_erreurs():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(ErreurDistante) as e:
        recuperer_etude_distante(client, "https://h2/dicom-web", "2.25.1")
    assert e.value.http == 403


# ── passerelle ───────────────────────────────────────────────────────────────
@pytest.fixture
def passerelle(instances, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from imagerie.passerelle import routeur_dicomweb
    from securite import AccesRefuse, installer_securite

    monkeypatch.setenv("H2_TOKEN", "jeton-de-test-imagerie-assez-long-0123")
    pacs = EntrepotMemoire()
    pacs.stocker([vers_octets(ds) for ds in instances])
    etat = {"pacs": pacs}

    def autoriser(appelant, study_uid):
        if study_uid == "2.25.403":
            raise AccesRefuse(403, "forbidden", "refus de test", "test")
        return "p:patient"

    app = FastAPI()
    installer_securite(app, service="H2")
    app.include_router(routeur_dicomweb(entrepot=lambda: etat["pacs"], autoriser=autoriser))
    c = TestClient(app, headers={"Authorization": "Bearer jeton-de-test-imagerie-assez-long-0123"})
    c.etat = etat
    return c


def test_passerelle_wado(passerelle):
    r = passerelle.get(f"/dicom-web/studies/{ETUDE['study_uid']}")
    assert r.status_code == 200 and r.headers["cache-control"].startswith("no-store")
    parties = decoder_multipart(r.content, r.headers["content-type"])
    assert len(parties) == 2 and depuis_octets(parties[0]).PatientID == "P2-0051"


def test_passerelle_desidentifiee(passerelle):
    r = passerelle.get(f"/dicom-web/studies/{ETUDE['study_uid']}", params={"desidentifier": "true"})
    ds = depuis_octets(decoder_multipart(r.content, r.headers["content-type"])[0])
    assert ds.PatientID == "p:patient" and ds.PatientIdentityRemoved == "YES"


def test_passerelle_metadonnees(passerelle):
    r = passerelle.get(f"/dicom-web/studies/{ETUDE['study_uid']}/metadata")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/dicom+json")
    assert len(r.json()) == 2 and "7FE00010" not in json.dumps(r.json())


@pytest.mark.parametrize("uid, code", [("2.25.403", 403), ("2.25.1", 404), ("1.2.abc", 400),
                                       ("1." + "2" * 70, 400)])
def test_passerelle_refus(passerelle, uid, code):
    r = passerelle.get(f"/dicom-web/studies/{uid}")
    assert r.status_code == code and r.json()["resourceType"] == "OperationOutcome"


def test_passerelle_sans_pacs_503(passerelle):
    passerelle.etat["pacs"] = None
    assert passerelle.get(f"/dicom-web/studies/{ETUDE['study_uid']}").status_code == 503


def test_passerelle_exige_un_jeton(passerelle):
    from fastapi.testclient import TestClient
    assert TestClient(passerelle.app).get(f"/dicom-web/studies/{ETUDE['study_uid']}").status_code == 401
