"""Testit WMS-proberille.

WMS ei tarjoa sarakkeita lainkaan — vain layereita. Siksi tulos ei mene
resource_schemaan vaan omaan service_layers-kenttäänsä: layer-listan
esittäminen kenttätietona antaisi lukijalle väärän kuvan siitä mitä
aineistosta saa irti.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aura.probe.types import ProbeStatus
from aura.probe.wms import parse_layers, probe

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_layerit_loytyvat_nimineen() -> None:
    """Koko layer-lista täsmälleen: pelkkä ei-tyhjyys ei paljasta suodatuksen katoamista.

    Fixture sisältää kolme <Layer>-elementtiä (nimetön juuri, nimetön ryhmä
    "Kantakartat" ja yksi nimetty lehtikerros). Jos nimettömien layerien
    suodatus katoaisi, ``assert layers`` ja ``assert all("name" in lay ...)``
    menisivät silti läpi — vain täsmällinen vertailu paljastaa sen.
    """
    layers = parse_layers(_fixture("wms_capabilities.xml"))
    assert layers == [{"name": "avoindata:Kantakartta", "title": "Kantakartta"}]


def test_nimeton_kokoava_layer_ohitetaan() -> None:
    """WMS-juuri on nimetön kääre, ei kysyttävä kerros."""
    xml = (
        '<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability>'
        "<Layer><Title>Kaikki</Title>"
        "<Layer><Name>kunnat</Name><Title>Kunnat</Title></Layer>"
        "</Layer></Capability></WMS_Capabilities>"
    )
    assert parse_layers(xml) == [{"name": "kunnat", "title": "Kunnat"}]


def test_tyhja_vastaus_ei_kaada() -> None:
    assert parse_layers("") == []


@pytest.mark.anyio
async def test_probe_tuottaa_service_layers_enrichmentin() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.text = _fixture("wms_capabilities.xml")
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.OK
    assert tulos.fields == [], "WMS ei tuota sarakkeita"
    arvot = dict(tulos.enrichments)
    layers = json.loads(arvot["service_layers"])
    assert layers and "name" in layers[0]


@pytest.mark.anyio
async def test_timeout_kirjautuu_omana_tilanaan() -> None:
    client = AsyncMock()
    client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.TIMEOUT
    assert tulos.detail == "GetCapabilities"


@pytest.mark.anyio
async def test_http_virhe_kirjautuu_koodina() -> None:
    resp = MagicMock()
    resp.status_code = 404
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.HTTP_ERROR
    assert tulos.detail == "HTTP 404"
    assert tulos.http_status == 404


@pytest.mark.anyio
async def test_yhteysvirhe_kirjautuu_http_errorina_ei_parse_errorina() -> None:
    """ConnectError ei ole timeout eikä statuskoodi.

    Ks. tabular.py:n vastaava testi
    ``test_muu_verkkovirhe_kirjautuu_http_errorina``. Ilman erillistä
    ``except httpx.HTTPError`` -haaraa tämä olisi pudonnut run_probe():n
    yleiseen except Exceptioniin parse_erroriksi (TTL 30 vrk oikean 7
    vrk:n sijaan).
    """
    client = AsyncMock()
    client.get = AsyncMock(side_effect=httpx.ConnectError("nimenselvitys epäonnistui"))

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.HTTP_ERROR
    assert "nimenselvitys" in tulos.detail
    assert tulos.http_status is None


@pytest.mark.anyio
async def test_service_layers_rajataan_ja_kertoo_kokonaismaaran() -> None:
    """475 layeria (Helsingin WMS) ei saa mennä kantaan yhtenä isona pötkönä.

    Katkaisu ei saa olla hiljainen: rajattu lista kertoo kokonaismäärän.
    """
    monta_layeria = "".join(
        f"<Layer><Name>l{i}</Name><Title>Layer {i}</Title></Layer>" for i in range(75)
    )
    xml = (
        '<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability>'
        f"<Layer><Title>Kaikki</Title>{monta_layeria}</Layer>"
        "</Capability></WMS_Capabilities>"
    )
    resp = MagicMock()
    resp.status_code = 200
    resp.text = xml
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.OK
    layers = json.loads(dict(tulos.enrichments)["service_layers"])
    assert len(layers) == 51, "50 layeria + yksi katkaisuilmoitus"
    assert layers[49]["name"] == "l49"
    assert "75" in layers[-1]["title"]
    assert "25" in layers[-1]["title"]


@pytest.mark.anyio
async def test_tyhja_capabilities_kirjautuu_yleisena_syyna() -> None:
    """Ei layereita eikä tunnistettavaa virhettä — geneerinen syy kelpaa."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = (
        '<WMS_Capabilities xmlns="http://www.opengis.net/wms">'
        "<Capability><Layer><Title>Tyhjä</Title></Layer></Capability>"
        "</WMS_Capabilities>"
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.EMPTY
    assert tulos.detail == "GetCapabilities ei sisältänyt layereita"
    assert tulos.http_status == 200


@pytest.mark.anyio
async def test_palvelimen_oma_virhe_kirjautuu_syyna() -> None:
    """WMS:n ServiceExceptionReport-muoto (ei OWS:n ExceptionReport) on tunnistuttava.

    Tämä on aidon kieltäytymisen tavallisin muoto WMS-palvelimilla —
    geneerinen "ei sisältänyt layereita" hukkaisi palvelimen oman syyn,
    vaikka se oli saatavilla.
    """
    resp = MagicMock()
    resp.status_code = 200
    resp.text = (
        '<ServiceExceptionReport version="1.3.0" '
        'xmlns="http://www.opengis.net/ogc">'
        '<ServiceException code="InvalidParameterValue">'
        "Layer not defined</ServiceException>"
        "</ServiceExceptionReport>"
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.EMPTY
    assert tulos.detail == "Layer not defined"
