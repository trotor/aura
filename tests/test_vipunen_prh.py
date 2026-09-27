"""Vipunen- ja PRH-harvesterit."""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from aura.database import init_db
from aura.harvesters.prh import CODE_LISTS, PrhHarvester
from aura.harvesters.vipunen import VipunenHarvester, title_from_name


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c


SCHEMAS: dict[str, list[dict[str, str]]] = {
    "koulutuksenkustannukset": [
        {"name": "tilastovuosi", "type": "string"},
        {"name": "koulutuksenKuntaKoodi", "type": "string"},
        {"name": "koulutuksenMaakuntaKoodi", "type": "string"},
        {"name": "summa", "type": "number"},
    ],
    "lukio_opiskelijat_kuukausi_maakunta": [
        {"name": "tilastovuosi", "type": "string"},
        {"name": "oppilaitoksenMaakunta", "type": "string"},
    ],
}


async def _fake_fetch(self: Any, client: Any, url: str, **kw: Any) -> httpx.Response:
    req = httpx.Request("GET", url)
    if url.endswith("/resources"):
        return httpx.Response(200, json=list(SCHEMAS), request=req)
    name = url.rsplit("/", 1)[-1]
    return httpx.Response(200, json=SCHEMAS[name], request=req)


def test_otsikko_nimesta() -> None:
    assert (
        title_from_name("amm_rahoitus_opiskelijavuodet") == "Ammatillinen rahoitus opiskelijavuodet"
    )
    assert title_from_name("koulutuksenkustannukset") == "Koulutuksen kustannukset"


@pytest.mark.asyncio
async def test_vipunen_tietojoukot_kentat_ja_aluetaso() -> None:
    h = VipunenHarvester(conn=_db())
    with patch.object(VipunenHarvester, "_fetch", _fake_fetch):
        assert await h.harvest() == 2
    row = h.conn.execute(
        "SELECT title_fi, license_id FROM datasets WHERE id = 'vipunen-koulutuksenkustannukset'"
    ).fetchone()
    assert (
        row["title_fi"] == "Koulutuksen kustannukset" and row["license_id"].lower() == "cc-by-4.0"
    )
    fields = [
        r[0]
        for r in h.conn.execute(
            "SELECT field_name FROM resource_schema"
            " WHERE dataset_id = 'vipunen-koulutuksenkustannukset'"
        )
    ]
    assert "koulutuksenKuntaKoodi" in fields and "summa" in fields
    levels = {
        r[0]: r[1]
        for r in h.conn.execute(
            "SELECT dataset_id, value FROM enrichments WHERE field = 'region_level'"
        )
    }
    # Kuntakoodi → kunta on dimensio; pelkkä maakunta ei merkitse kuntatasoa.
    assert levels == {"vipunen-koulutuksenkustannukset": "kunta"}


@pytest.mark.asyncio
async def test_prh_koodistot_eivat_toista_avoindatan_aineistoja() -> None:
    h = PrhHarvester(conn=_db())
    assert await h.harvest() == 3
    urls = [r[0] for r in h.conn.execute("SELECT url FROM resources")]
    assert len([u for u in urls if "description?code=" in u]) == len(CODE_LISTS)
    # Koko rekisteri on jo avoindata.fi:n kautta: ei bulk-resurssia.
    assert not any("all_companies" in u for u in urls)
    # Yrityshaku on poikkeus: avoindata.fi:n resurssi osoittaa sivuston juureen.
    assert len([u for u in urls if "/companies?" in u]) == 1


def test_prh_yrityshaun_kuvaus_nimeaa_parametrit() -> None:
    cfg = next(c for c in PrhHarvester.datasets_config if c["id"] == "prh-ytj-yrityshaku")
    for param in ("location", "mainBusinessLine", "companyForm", "businessId", "page"):
        assert param in cfg["notes_fi"]
    assert cfg["resources"][0]["format"] == "JSON"


def test_vipusen_suodatin_palvelimelle() -> None:
    from urllib.parse import parse_qs, urlsplit

    from aura.fetch import vipunen_filter_url

    url = vipunen_filter_url(
        "https://api.vipunen.fi/api/resources/x/data?limit=1000",
        {"oppilaitos": ["Apollon yhteiskoulu"], "lukuvuosi": ["2024/2025", "2023/2024"]},
    )
    q = parse_qs(urlsplit(url).query)
    assert q["limit"] == ["1000"]
    assert q["filter"] == [
        'oppilaitos=="Apollon yhteiskoulu";lukuvuosi=in=("2024/2025","2023/2024")'
    ]


@pytest.mark.asyncio
async def test_vipunen_json_suodatetaan_palvelimella() -> None:
    from aura import fetch

    seen: list[str] = []

    async def fake_download(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        seen.append(url)
        return b'[{"lukuvuosi": "2024/2025", "oppilaatLukuvuosiLkm": 236}]', False

    with patch.object(fetch, "_download", fake_download):
        table = await fetch.fetch_json(
            "https://api.vipunen.fi/api/resources/x/data?limit=1000",
            {"lukuvuosi": ["2024/2025"]},
            50,
        )
    assert "filter=" in seen[0]
    assert table.rows and table.rows[0]["oppilaatLukuvuosiLkm"] == 236
    assert any("palvelimella" in n for n in table.notes)


@pytest.mark.asyncio
async def test_sivutetun_jsonin_kokonaismaara_lahteesta() -> None:
    """YTJ kertoo totalResults; sivun 100 riviä ei ole lähteen koko."""
    from aura import fetch

    async def fake_download(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        return b'{"totalResults": 1889, "companies": [{"businessId": {"value": "1"}}]}', False

    with patch.object(fetch, "_download", fake_download):
        table = await fetch.fetch_json(
            "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?location=Tampere", None, 50
        )
    assert table.total == 1889 and table.truncated is True
    assert any("1889 osumaa" in n for n in table.notes)
