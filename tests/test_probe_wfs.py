"""Testit WFS-proberille.

WFS on se aukko johon raportoija törmäsi: GTK:n aineistot ovat WFS:ää,
eikä niiden skeemaa kaapattu missään.

Fixturet ovat oikeita vastauksia kahdelta eri palvelintyypiltä.
Nimiavaruusprefiksi eroaa (`xsd:` / `xs:`), ja käsin kirjoitettu XML olisi
yksinkertaistanut juuri sen eron pois.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aura.probe.types import ProbeStatus
from aura.probe.wfs import parse_feature_types, probe

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestSarakkeidenLuku:
    def test_geoserver_sarakkeet_ja_tyypit(self) -> None:
        kentat = dict(_fixture("wfs_describefeaturetype_geoserver.xml") and
                      parse_feature_types(_fixture("wfs_describefeaturetype_geoserver.xml")))
        assert kentat["tietopalvelu_id"] == "integer"
        assert kentat["metroasema"] == "string"

    def test_geoserver_ei_sisalla_kaareelementtia(self) -> None:
        """Koko kenttäjoukko tarkasti: kääre-elementti ei saa livahtaa sarakkeeksi.

        GeoServer nimeää featuretyypin kääre-complexTypen kaavalla
        ``<Kerros>Type`` — ei ``<Kerros>FeatureType`` kuten ArcGIS. Pelkkä
        yksittäisten avainten tarkistus ei olisi paljastanut tätä: koko
        joukko on ainoa tapa varmistaa ettei paluu ``endswith("FeatureType")``
        -heuristiikkaan menisi läpi huomaamatta.
        """
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_geoserver.xml")))
        assert kentat == {
            "tietopalvelu_id": "integer",
            "metroasema": "string",
            "mtryhm": "integer",
            "geom": "geometry",
        }
        assert "Seutukartta_liikenne_metroasemat" not in kentat

    def test_arcgis_sarakkeet_ja_tyypit(self) -> None:
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_arcgis.xml")))
        assert kentat["OBJECTID"] == "integer"

    def test_arcgis_kaikki_yksitoista_saraketta(self) -> None:
        """Koko kenttäjoukko tarkasti: kahdeksan merkkijonokenttää ei saa kadota.

        ArcGIS ei kirjoita ``type``-attribuuttia merkkijonokentille lainkaan
        — tyyppi on vain sisäkkäisessä ``xsd:simpleType``-rajoituksessa.
        Ilman sen lukemista kentät katoaisivat äänettömästi ``if not
        raw_type: continue`` -tyyppiseen ehtoon.
        """
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_arcgis.xml")))
        assert kentat == {
            "OBJECTID": "integer",
            "GTK_ID": "string",
            "FAULT_RELIABILITY": "string",
            "UPTHROWN_SIDE": "string",
            "SITE_NAME": "string",
            "COMPLEX_NAME": "string",
            "SYSTEM_NAME": "string",
            "SEGMENT_NAME": "string",
            "REFERENCE": "string",
            "SHAPE": "geometry",
            "SHAPE.LEN": "float",
        }

    def test_geometria_merkitaan_geometriaksi(self) -> None:
        """Koordinaattikenttä ei ole sarake, mutta sen olemassaolo on tietoa."""
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_geoserver.xml")))
        assert kentat.get("geom") == "geometry"

    def test_tyyppikartta_kattaa_xsd_perustyypit(self) -> None:
        xml = (
            '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            "<xsd:sequence>"
            '<xsd:element name="a" type="xsd:double"/>'
            '<xsd:element name="b" type="xsd:dateTime"/>'
            '<xsd:element name="c" type="xsd:boolean"/>'
            "</xsd:sequence>"
            "</xsd:schema>"
        )
        assert dict(parse_feature_types(xml)) == {
            "a": "float", "b": "date", "c": "boolean",
        }

    def test_nimetty_simpletype_ei_pudota_saraketta(self) -> None:
        """INSPIRE-tyylinen koodistokenttä (esim. ``ns:TilaType``) on sarake, ei runko.

        Nimen perusteella tehty ohitus ("päättyy 'Type'-merkkijonoon")
        pudottaisi tämän kentän kokonaan, koska sillä on nimetty
        simpleType joka päättyy samalla tavalla kuin featuretyypin oma
        kääre-complexType. Sijainti (sequence-lohkon sisällä) ratkaisee.
        """
        xml = (
            '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:ns="http://example.test">'
            '<xsd:element name="Kohde" type="ns:KohdeFeatureType" '
            'substitutionGroup="gml:AbstractFeature"/>'
            '<xsd:complexType name="KohdeFeatureType">'
            "<xsd:complexContent>"
            '<xsd:extension base="gml:AbstractFeatureType">'
            "<xsd:sequence>"
            '<xsd:element name="tila" type="ns:TilaType"/>'
            '<xsd:element name="nimi" type="xsd:string"/>'
            "</xsd:sequence>"
            "</xsd:extension>"
            "</xsd:complexContent>"
            "</xsd:complexType>"
            "</xsd:schema>"
        )
        assert dict(parse_feature_types(xml)) == {"tila": "string", "nimi": "string"}

    def test_tyhja_vastaus_ei_kaada(self) -> None:
        assert parse_feature_types("") == []


def _client(responses: list[tuple[int, str]]) -> AsyncMock:
    calls: list[dict] = []

    async def _get(url, params=None, **kwargs):
        calls.append({"params": dict(params or {})})
        status, body = responses[min(len(calls) - 1, len(responses) - 1)]
        resp = MagicMock()
        resp.status_code = status
        resp.text = body
        return resp

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get)
    client.calls = calls
    return client


class TestProbe:
    @pytest.mark.anyio
    async def test_onnistunut_probe_tuottaa_kentat_ja_crs(self) -> None:
        client = _client([
            (200, _fixture("wfs_capabilities_arcgis.xml")),
            (200, _fixture("wfs_describefeaturetype_arcgis.xml")),
        ])
        tulos = await probe({"url": "https://example.test/wfs"}, client)
        assert tulos.status == ProbeStatus.OK
        assert any(nimi == "OBJECTID" for nimi, _ in tulos.fields)
        assert dict(tulos.enrichments)["crs"].endswith("3067")
        assert "typeNames=" in dict(tulos.enrichments)["example_request"]

    @pytest.mark.anyio
    async def test_url_oma_typename_voittaa_kykyjen_ensimmaisen(self) -> None:
        """Resurssin URL:n typeName ohittaa GetCapabilities-vastauksen ensimmäisen.

        GTK:n capabilities-fixture listaa kolme featuretyyppiä, joista
        ``postglasiaalisiirros`` on ensimmäinen. Resurssin oma URL osoittaa
        kuitenkin toiseen kerrokseen (``merenpohjan_naytepaikat``) —
        ``request_params()`` tekisi saman valinnan GetFeature-kutsulle,
        joten ``probe()``:n on tehtävä sama valinta DescribeFeatureTypelle.
        """
        client = _client([
            (200, _fixture("wfs_capabilities_arcgis.xml")),
            (200, _fixture("wfs_describefeaturetype_arcgis.xml")),
        ])
        url = (
            "https://example.test/wfs?service=WFS&typeName="
            "Rajapinnat_GTK_Maapera_WFS:merenpohjan_naytepaikat"
        )
        tulos = await probe({"url": url}, client)
        assert tulos.status == ProbeStatus.OK
        dft_params = client.calls[1]["params"]
        assert dft_params["typeNames"] == "Rajapinnat_GTK_Maapera_WFS:merenpohjan_naytepaikat"

    @pytest.mark.anyio
    async def test_virhevastaus_kirjautuu_syyna(self) -> None:
        """HTTP 200 + ExceptionReport on WFS:n tavallisin kieltäytyminen."""
        client = _client([(200, _fixture("wfs_exception_arcgis.xml"))])
        tulos = await probe({"url": "https://example.test/wfs"}, client)
        assert tulos.status == ProbeStatus.PARSE_ERROR
        assert "typeNames" in tulos.detail or "application/json" in tulos.detail

    @pytest.mark.anyio
    async def test_http_virhe_kirjautuu_koodina(self) -> None:
        client = _client([(404, "")])
        tulos = await probe({"url": "https://example.test/wfs"}, client)
        assert tulos.status == ProbeStatus.HTTP_ERROR
        assert tulos.detail == "HTTP 404"
        assert tulos.http_status == 404
