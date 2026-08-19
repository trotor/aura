"""Testit PxWeb-proberille.

Muoto on jo päätetty: harvesteri kirjoittaa data_fields-enrichmentin
muodossa {code, name, value_count, examples}, ja region_levels.py lukee sitä
tunnistaakseen kuntadimension. Probe tuottaa saman muodon — eri muoto
rikkoisi hakutuloksen aluelaajennuksen.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aura.probe.pxweb import parse_dimensions, probe
from aura.probe.types import ProbeStatus

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIXTURES / "pxweb_metadata.json").read_text(encoding="utf-8"))


def test_dimensiot_saavat_harvesterin_muodon() -> None:
    """Fixturen ensimmäinen muuttuja on "Kuukausi" — täsmällinen tarkistus.

    Pelkkä ``assert dims`` tai avainten olemassaolon tarkistus ei paljastaisi
    esim. väärää arvoa tai sarakkeiden vaihtumista keskenään. Fixturen
    ensimmäinen muuttuja (timeperiod_m/Kuukausi) sisältää 210 arvoa —
    value_count lasketaan values-listasta, ei valueTexts-listasta, joten
    tämä paljastaisi sekaannuksen niiden välillä.
    """
    dims = parse_dimensions(_payload())
    assert dims == [
        {
            "code": "timeperiod_m",
            "name": "Kuukausi",
            "value_count": 210,
            "examples": ["2009M01", "2009M02", "2009M03", "2009M04", "2009M05"],
        },
        {
            "code": "sukupuoli_9_20180101",
            "name": "Sukupuoli",
            "value_count": 3,
            "examples": ["Yhteensä", "Miehet", "Naiset"],
        },
        {
            "code": "ikaryhma_19_20190101",
            "name": "Ikäluokka",
            "value_count": 9,
            "examples": ["15 - 74", "15 - 64", "15 - 24", "20 - 64", "20 - 69"],
        },
        {
            "code": "contentscode",
            "name": "Tiedot",
            "value_count": 8,
            "examples": [
                "Väestö, 1000 henkilöä",
                "Työvoima, 1000 henkilöä",
                "Työlliset, 1000 henkilöä",
                "Työttömät, 1000 henkilöä",
                "Työvoiman ulkopuolella olevat, 1000 henkilöä",
            ],
        },
    ]


def test_esimerkkeja_enintaan_viisi() -> None:
    """Koko luokitus veisi tilan kertomatta enempää."""
    for dim in parse_dimensions(_payload()):
        assert len(dim["examples"]) <= 5


def test_value_count_on_koko_arvomaara_ei_esimerkkien_maara() -> None:
    """value_count kuvaa dimension todellista kokoa, ei examples-listan pituutta.

    Kuukausi-dimensiolla on 210 arvoa mutta vain 5 esimerkkiä — jos
    value_count laskettaisiin vahingossa examples-listasta, tämä paljastuisi.
    """
    dims = parse_dimensions(_payload())
    kuukausi = next(d for d in dims if d["code"] == "timeperiod_m")
    assert kuukausi["value_count"] == 210
    assert len(kuukausi["examples"]) == 5


def test_esimerkit_kayttavat_valuetexteja_ei_koodeja() -> None:
    """Sukupuoli-dimension esimerkit ovat ihmisluettavia tekstejä, ei koodeja.

    Fixturessa values=["SSS","1","2"] mutta valueTexts=["Yhteensä","Miehet",
    "Naiset"]. Jos valueTexts-käyttö unohtuisi, esimerkit olisivat koodeja.
    """
    dims = parse_dimensions(_payload())
    sukupuoli = next(d for d in dims if d["code"] == "sukupuoli_9_20180101")
    assert sukupuoli["examples"] == ["Yhteensä", "Miehet", "Naiset"]


def test_muuttujaton_vastaus_on_empty() -> None:
    assert parse_dimensions({"title": "x", "variables": []}) == []


def test_puuttuva_variables_avain_on_empty() -> None:
    assert parse_dimensions({"title": "x"}) == []


@pytest.mark.anyio
async def test_probe_tuottaa_data_fields_enrichmentin() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=_payload())
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/px"}, client)
    assert tulos.status == ProbeStatus.OK
    assert tulos.fields == [], "PxWeb-dimensiot menevät enrichmentiksi, ei fields-listaan"
    assert tulos.http_status == 200
    arvot = dict(tulos.enrichments)
    assert set(arvot) == {"data_fields"}
    dims = json.loads(arvot["data_fields"])
    assert dims == parse_dimensions(_payload())
    assert dims[0]["code"] == "timeperiod_m"


@pytest.mark.anyio
async def test_timeout_kirjautuu_omana_tilanaan() -> None:
    client = AsyncMock()
    client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    tulos = await probe({"url": "https://example.test/px"}, client)
    assert tulos.status == ProbeStatus.TIMEOUT
    assert tulos.detail == "metadata"
    assert tulos.enrichments == []


@pytest.mark.anyio
async def test_http_virhe_kirjautuu_koodina() -> None:
    resp = MagicMock()
    resp.status_code = 404
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/px"}, client)
    assert tulos.status == ProbeStatus.HTTP_ERROR
    assert tulos.detail == "HTTP 404"
    assert tulos.http_status == 404
    assert tulos.enrichments == []


@pytest.mark.anyio
async def test_ei_jsonia_on_parse_error() -> None:
    """Palvelin voi vastata HTML-virhesivulla 200-koodilla — .json() nostaa ValueErrorin."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(side_effect=ValueError("Expecting value"))
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/px"}, client)
    assert tulos.status == ProbeStatus.PARSE_ERROR
    assert tulos.detail == "Vastaus ei ole JSONia"
    assert tulos.http_status == 200
    assert tulos.enrichments == []


@pytest.mark.anyio
async def test_tyhjat_muuttujat_on_empty() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value={"title": "Tyhjä taulu", "variables": []})
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/px"}, client)
    assert tulos.status == ProbeStatus.EMPTY
    assert tulos.detail == "Taululla ei ole dimensioita"
    assert tulos.http_status == 200
    assert tulos.enrichments == []
