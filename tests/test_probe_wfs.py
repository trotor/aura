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

    def test_arcgis_sarakkeet_ja_tyypit(self) -> None:
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_arcgis.xml")))
        assert kentat["OBJECTID"] == "integer"

    def test_geometria_merkitaan_geometriaksi(self) -> None:
        """Koordinaattikenttä ei ole sarake, mutta sen olemassaolo on tietoa."""
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_geoserver.xml")))
        assert kentat.get("geom") == "geometry"

    def test_tyyppikartta_kattaa_xsd_perustyypit(self) -> None:
        xml = (
            '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            '<xsd:element name="a" type="xsd:double"/>'
            '<xsd:element name="b" type="xsd:dateTime"/>'
            '<xsd:element name="c" type="xsd:boolean"/>'
            "</xsd:schema>"
        )
        assert dict(parse_feature_types(xml)) == {
            "a": "float", "b": "date", "c": "boolean",
        }

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
