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

import pytest

from aura.probe.types import ProbeStatus
from aura.probe.wms import parse_layers, probe

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_layerit_loytyvat_nimineen(self=None) -> None:
    layers = parse_layers(_fixture("wms_capabilities.xml"))
    assert layers, "yhtään layeria ei löytynyt"
    assert all("name" in lay for lay in layers)


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
