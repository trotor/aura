"""Testit saatavuustarkistuksen OGC-mittausosoitteelle.

Paljas GET OGC-päätepisteeseen palauttaa HTTP 400:n myös silloin kun
palvelu toimii: mitattuna sekä ``kartta.hel.fi/ws/geoserver/avoindata/wfs``
että ``inspire.ruokavirasto-awsa.com/geoserver/wfs`` vastasivat 400:lla
ilman parametreja, vaikka molemmat palvelevat GetCapabilitiesiin
normaalisti.

Useimmat palvelimet sietävät paljaan GET:in, joten vaikutus on
maltillinen: 120 OGC-resurssin otoksessa saatavuus nousi 92 %:sta
97 %:iin. Ne viisi ovat kuitenkin vääriä hälytyksiä, ja väärä hälytys
raportissa on kalliimpi kuin sen koko: raporttia jonka rivejä ei voi
uskoa ei lueta, jolloin oikeasti kuolleet osoitteet jäävät huomaamatta.
"""

import sqlite3

import httpx
import pytest

from aura.database import init_db
from aura.health import check_resource, get_resources_to_check, probe_url


class TestProbeUrl:
    """Mittausosoitteen muodostus."""

    @pytest.mark.parametrize("fmt", ["WFS", "WMS", "WCS"])
    def test_ogc_saa_getcapabilities(self, fmt: str) -> None:
        url = probe_url("https://example.invalid/geoserver/ows", fmt)
        assert f"service={fmt}" in url
        assert "request=GetCapabilities" in url

    def test_formaatti_ei_ole_kirjainkokoherkka(self) -> None:
        assert "request=GetCapabilities" in probe_url("https://example.invalid/ows", "wfs")

    def test_olemassa_oleva_kysely_sailyy(self) -> None:
        """Erotin on & kun osoitteessa on jo kyselyosa."""
        url = probe_url("https://example.invalid/ows?key=abc", "WFS")
        assert url == "https://example.invalid/ows?key=abc&service=WFS&request=GetCapabilities"

    def test_valmis_pyynto_jatetaan_rauhaan(self) -> None:
        """Harvesteri on voinut jo rakentaa toimivan pyynnön.

        Ruokaviraston WFS-resurssit ovat valmiita GetFeature-kyselyitä;
        niiden päälle liimattu GetCapabilities rikkoisi osoitteen.
        """
        alkuperainen = "https://example.invalid/wfs?service=WFS&request=GetFeature&typeNames=a:b"
        assert probe_url(alkuperainen, "WFS") == alkuperainen

    @pytest.mark.parametrize("fmt", ["CSV", "JSON", "HTML", "GeoJSON", "", None])
    def test_muut_formaatit_mitataan_sellaisenaan(self, fmt: str | None) -> None:
        url = "https://example.invalid/data.csv"
        assert probe_url(url, fmt) == url


class TestCheckResource:
    """Mittausosoite ei saa vuotaa tallennettuun tulokseen."""

    @pytest.mark.asyncio
    async def test_tulokseen_tallennetaan_alkuperainen_osoite(self) -> None:
        """Muuten katalogin osoite ja raportin osoite eroaisivat."""
        pyydetyt: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            pyydetyt.append(str(request.url))
            return httpx.Response(200, headers={"content-type": "text/xml"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tulos = await check_resource(
                client, "r1", "d1", "https://example.invalid/geoserver/ows", "WFS"
            )

        assert tulos.is_available
        assert tulos.url == "https://example.invalid/geoserver/ows"
        assert "request=GetCapabilities" in pyydetyt[0]

    @pytest.mark.asyncio
    async def test_formaatti_puuttuu_ei_kaada(self) -> None:
        """Formaatti on vapaaehtoinen argumentti vanhoille kutsujille."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tulos = await check_resource(client, "r1", "d1", "https://example.invalid/x.csv")
        assert tulos.is_available


class TestKyselyPalauttaaFormaatin:
    """Formaatti on haettava kannasta asti, muuten mittaus ei muutu."""

    def test_get_resources_to_check_sisaltaa_formaatin(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
        )
        conn.execute(
            "INSERT INTO resources (id, dataset_id, format, url)"
            " VALUES ('r1','d1','WFS','https://example.invalid/ows')"
        )
        rows = get_resources_to_check(conn)
        assert rows and rows[0]["format"] == "WFS"
