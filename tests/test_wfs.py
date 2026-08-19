"""Testit WFS-protokollan tulkinnalle (ArcGIS Server).

Esikatselu kaatui viestiin ``Expecting value: line 2 column 1 (char 1)``:
JSON-jäsennin XML:n päällä. Syitä oli kaksi ja molemmat piti toistaa ennen
korjausta:

1. ``outputFormat=application/json`` ei kelpaa ArcGIS Serverille. Sen
   GetCapabilities mainostaa arvoja ``GEOJSON``, ``GML32``, ``CSV`` — ei
   MIME-merkkijonoa.
2. ``typeNames`` on ArcGIS:llä pakollinen. Parametriton GetFeature, joka
   toimii GeoServerillä, kaatuu tähän.

Molemmat palautuvat XML-muotoisena ExceptionReportina **HTTP 200:lla**, joten
``raise_for_status()`` päästää ne läpi eikä mikään erota virhettä datasta.

Fixturet ovat GTK:n oikeita vastauksia (``gtkdata.gtk.fi``), karsittuina
mutta muokkaamattomina. Käsin kirjoitettu XML ei olisi paljastanut vikaa:
juuri ne yksityiskohdat joissa ArcGIS eroaa GeoServeristä — nimiavaruudet,
operaatiokohtaiset AllowedValues, ``wfs:member``-kääre — olisivat
yksinkertaistuneet pois.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# aura.server ensin: pelkkä aura.tools.preview -import laukaisee kiertoimportin.
import aura.server  # noqa: F401
from aura.tools.preview import _preview_wfs
from aura.wfs import (
    exception_text,
    parse_capabilities,
    parse_gml,
    pick_output_format,
    request_params,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestVirheenTunnistus:
    """Virhe on erotettava datasta ennen kuin sitä yritetään jäsentää."""

    def test_exception_report_tunnistetaan(self) -> None:
        """Virheteksti nimeää molemmat syyt — se on paras vihje mitä on."""
        teksti = exception_text(_fixture("wfs_exception_arcgis.xml"))
        assert teksti is not None
        assert "application/json" in teksti
        assert "typeNames" in teksti

    def test_kaikki_virheet_kootaan_yhteen(self) -> None:
        """ArcGIS palauttaa monta Exceptionia; yksi niistä ei riitä syyksi."""
        teksti = exception_text(_fixture("wfs_exception_arcgis.xml")) or ""
        assert teksti.lower().count("parameter") >= 2

    def test_json_ei_ole_virhe(self) -> None:
        assert exception_text('{"type":"FeatureCollection","features":[]}') is None

    def test_featurecollection_ei_ole_virhe(self) -> None:
        assert exception_text(_fixture("wfs_features_gml32.xml")) is None

    def test_roska_ei_kaada(self) -> None:
        assert exception_text("<ei suljettu") is None

    def test_wms_service_exception_tunnistetaan(self) -> None:
        """WMS-palvelin ei kääri virhettä ExceptionReportiin vaan omaan muotoonsa.

        Ilman tätä ``exception_text`` palauttaisi None:in aidolle
        WMS-virheelle, ja kutsuja (esim. WMS-prober) joutuisi kertomaan
        geneerisen syyn palvelimen oman virheen sijaan.
        """
        xml = (
            '<ServiceExceptionReport version="1.3.0" '
            'xmlns="http://www.opengis.net/ogc">'
            '<ServiceException code="InvalidParameterValue">'
            "Layer not defined</ServiceException>"
            "</ServiceExceptionReport>"
        )
        assert exception_text(xml) == "Layer not defined"


class TestKyvyt:
    def test_featuretyypit_loytyvat(self) -> None:
        caps = parse_capabilities(_fixture("wfs_capabilities_arcgis.xml"))
        assert "Rajapinnat_GTK_Maapera_WFS:postglasiaalisiirros" in caps.feature_types

    def test_outputformatit_luetaan_getfeaturesta(self) -> None:
        """DescribeFeatureType mainostaa vain GML:ää — väärä lohko veisi harhaan."""
        caps = parse_capabilities(_fixture("wfs_capabilities_arcgis.xml"))
        assert "GEOJSON" in caps.output_formats
        assert "GML32" in caps.output_formats

    def test_tyhja_vastaus_ei_kaada(self) -> None:
        caps = parse_capabilities("")
        assert caps.feature_types == [] and caps.output_formats == []


class TestFormaatinValinta:
    def test_geojson_valitaan_gmlin_sijaan(self) -> None:
        caps = parse_capabilities(_fixture("wfs_capabilities_arcgis.xml"))
        assert pick_output_format(caps.output_formats) == "GEOJSON"

    def test_mime_muoto_voittaa_jos_tarjolla(self) -> None:
        assert pick_output_format(["GML32", "application/json", "GEOJSON"]) == (
            "application/json"
        )

    def test_pakattua_ei_valita(self) -> None:
        """GEOJSON+ZIP sisältää sanan geojson mutta on zip-tiedosto."""
        assert pick_output_format(["GEOJSON+ZIP", "GEOJSON+GZIP", "GML32"]) is None

    def test_pelkka_gml_ei_kelpaa_jsoniksi(self) -> None:
        assert pick_output_format(["GML32", "GML2"]) is None


class TestGmlJasennys:
    """Kun palvelu ei tarjoa JSONia lainkaan, GML on ainoa tie dataan."""

    def test_rivit_ja_sarakkeet_loytyvat(self) -> None:
        headers, rows = parse_gml(_fixture("wfs_features_gml32.xml"), max_rows=10)
        assert "GTK_ID" in headers
        assert len(rows) == 2

    def test_arvot_paatyvat_oikeille_sarakkeille(self) -> None:
        headers, rows = parse_gml(_fixture("wfs_features_gml32.xml"), max_rows=10)
        arvot = dict(zip(headers, rows[0], strict=False))
        assert arvot["GTK_ID"] == "PGF1000"
        assert arvot["SITE_NAME"] == "Vaalajärvi"

    def test_max_rows_rajaa(self) -> None:
        _headers, rows = parse_gml(_fixture("wfs_features_gml32.xml"), max_rows=1)
        assert len(rows) == 1

    def test_geometria_ei_tulvi_taulukkoon(self) -> None:
        """Koordinaattilista tekisi taulukosta lukukelvottoman."""
        headers, _rows = parse_gml(_fixture("wfs_features_gml32.xml"), max_rows=10)
        assert not any("posList" in h or "Shape" in h for h in headers)

    def test_tyhja_vastaus_ei_kaada(self) -> None:
        assert parse_gml("", max_rows=5) == ([], [])


class TestPyynnonRakennus:
    def test_typename_sailyy_urlista(self) -> None:
        base, params = request_params(
            "https://example.test/ows?service=wfs&request=GetFeature&typeName=kunnat",
            max_rows=5,
        )
        assert base == "https://example.test/ows"
        assert params["typeName"] == "kunnat"
        assert params["count"] == "5"

    def test_typenames_monikko_sailyy(self) -> None:
        _base, params = request_params(
            "https://example.test/wfs?TYPENAMES=ns:kohteet", max_rows=1
        )
        assert params["TYPENAMES"] == "ns:kohteet"

    def test_getcapabilities_ei_kulkeudu_lapi(self) -> None:
        _base, params = request_params(
            "https://example.test/wfs?request=getcapabilities", max_rows=1
        )
        assert params["request"] == "GetFeature"

    def test_annettu_typename_taydentaa_puuttuvan(self) -> None:
        _base, params = request_params(
            "https://example.test/wfs", max_rows=1, type_name="ns:kerros"
        )
        assert params["typeNames"] == "ns:kerros"

    def test_urlin_typename_voittaa_annetun(self) -> None:
        """URL:n kerros on aineiston oma valinta, ei kyvyistä arvattu."""
        _base, params = request_params(
            "https://example.test/wfs?typeName=urlista", max_rows=1, type_name="arvattu"
        )
        assert params["typeName"] == "urlista"
        assert "typeNames" not in params

    @pytest.mark.parametrize("fmt", ["GEOJSON", "application/json"])
    def test_annettu_outputformat_korvaa_oletuksen(self, fmt: str) -> None:
        _base, params = request_params(
            "https://example.test/wfs", max_rows=1, output_format=fmt
        )
        assert params["outputFormat"] == fmt

    def test_bbox_menee_omana_parametrinaan(self) -> None:
        _base, params = request_params(
            "https://example.test/wfs", max_rows=1, bbox="1,2,3,4,EPSG:3067"
        )
        assert params["bbox"] == "1,2,3,4,EPSG:3067"


class TestEsikatseluUudelleenyritys:
    """``_preview_wfs`` ei saa kaatua XML-vastaukseen vaan neuvotella.

    Ensimmäinen yritys on optimistinen (``application/json``, ei ylimääräistä
    verkkokutsua), koska se toimii GeoServerillä eli valtaosalla. Vasta kun
    vastaus ei ole JSONia, kysytään kyvyt ja yritetään uudelleen.
    """

    @staticmethod
    def _client(responses: list[str]) -> tuple[object, list[dict]]:
        calls: list[dict] = []

        async def _get(url, params=None, **kwargs):
            calls.append({"url": url, "params": dict(params or {})})
            body = responses[min(len(calls) - 1, len(responses) - 1)]
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.text = body
            resp.json = MagicMock(side_effect=lambda: json.loads(body))
            return resp

        client = AsyncMock()
        client.get = AsyncMock(side_effect=_get)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        return client, calls

    @pytest.mark.anyio
    async def test_xml_virhe_johtaa_neuvotteluun(self) -> None:
        """Tämä on itse vika: JSON-jäsennin kaatui ExceptionReportiin."""
        geojson = (
            '{"type":"FeatureCollection","features":'
            '[{"properties":{"GTK_ID":"PGF1000"}}],"totalFeatures":154}'
        )
        client, calls = self._client([
            _fixture("wfs_exception_arcgis.xml"),      # 1. optimistinen yritys
            _fixture("wfs_capabilities_arcgis.xml"),   # 2. kyvyt
            geojson,                                    # 3. uusi yritys
        ])
        with patch("aura.tools.preview.httpx.AsyncClient", return_value=client):
            out = await _preview_wfs("https://example.test/wfs", 3)

        assert "PGF1000" in out, out
        assert len(calls) == 3, [c["params"] for c in calls]
        assert calls[1]["params"]["request"] == "GetCapabilities"
        assert calls[2]["params"]["outputFormat"] == "GEOJSON"
        assert calls[2]["params"]["typeNames"].endswith("postglasiaalisiirros")

    @pytest.mark.anyio
    async def test_toimiva_palvelu_ei_kysy_kykyja(self) -> None:
        client, calls = self._client([
            '{"type":"FeatureCollection","features":[{"properties":{"nimi":"X"}}]}'
        ])
        with patch("aura.tools.preview.httpx.AsyncClient", return_value=client):
            out = await _preview_wfs("https://example.test/wfs", 3)

        assert "X" in out
        assert len(calls) == 1, "turha GetCapabilities-kutsu jokaiselle palvelulle"

    @pytest.mark.anyio
    async def test_pelkka_gml_jasennetaan(self) -> None:
        """Palvelu joka ei tarjoa JSONia lainkaan on silti luettavissa."""
        caps = _fixture("wfs_capabilities_arcgis.xml").replace("GEOJSON", "GMLONLY")
        client, _calls = self._client([
            _fixture("wfs_exception_arcgis.xml"),
            caps,
            _fixture("wfs_features_gml32.xml"),
        ])
        with patch("aura.tools.preview.httpx.AsyncClient", return_value=client):
            out = await _preview_wfs("https://example.test/wfs", 3)

        assert "PGF1000" in out, out

    @pytest.mark.anyio
    async def test_virhe_kerrotaan_palvelimen_sanoin(self) -> None:
        """'Expecting value: line 2 column 1' ei kertonut käyttäjälle mitään."""
        client, _calls = self._client([_fixture("wfs_exception_arcgis.xml")] * 3)
        with patch("aura.tools.preview.httpx.AsyncClient", return_value=client):
            out = await _preview_wfs("https://example.test/wfs", 3)

        assert "typeNames" in out or "application/json" in out
        assert "Expecting value" not in out


class TestKokonaismaaranRehellisyys:
    """Kokonaismäärää ei saa keksiä palautettujen rivien määrästä.

    ArcGIS:n GEOJSON-vastaus ei kerro montako kohdetta palvelussa on. Jos
    puuttuva luku korvataan rivimäärällä, esikatselu väittää palvelussa
    olevan kolme kohdetta vaikka niitä on 154 — ja agentti päättelee siitä
    aineiston olevan tyhjä.
    """

    def test_gml_kertoo_numbermatchedin(self) -> None:
        from aura.wfs import _read_body

        result = _read_body(_fixture("wfs_features_gml32.xml"), max_rows=2)
        assert result is not None
        assert result.total == "154"

    def test_geojson_ilman_lukua_ei_valehtele(self) -> None:
        from aura.wfs import _read_body

        body = '{"type":"FeatureCollection","features":[{"properties":{"a":1}}]}'
        result = _read_body(body, max_rows=5)
        assert result is not None
        assert result.total is None

    def test_geojson_luku_kaytetaan_kun_se_on(self) -> None:
        from aura.wfs import _read_body

        body = (
            '{"type":"FeatureCollection","numberMatched":42,'
            '"features":[{"properties":{"a":1}}]}'
        )
        result = _read_body(body, max_rows=5)
        assert result is not None
        assert result.total == "42"


class TestNeuvottelunEpaonnistuminen:
    """Jos kyvyt eivät vastaa, alkuperäinen syy on silti paras tieto."""

    @pytest.mark.anyio
    async def test_kaatunut_getcapabilities_ei_peita_alkuperaista_syyta(self) -> None:
        from aura.wfs import fetch_features

        calls: list[str] = []

        async def _get(url, params=None, **kwargs):
            calls.append((params or {}).get("request", ""))
            if calls[-1] == "GetCapabilities":
                raise httpx.ConnectError("kyvyt eivät vastaa")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.text = _fixture("wfs_exception_arcgis.xml")
            return resp

        client = AsyncMock()
        client.get = AsyncMock(side_effect=_get)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("aura.wfs.httpx.AsyncClient", return_value=client):
            result = await fetch_features("https://example.test/wfs", 3)

        assert result.error is not None
        assert "typeNames" in result.error, result.error
