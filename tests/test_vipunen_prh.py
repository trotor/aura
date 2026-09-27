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
    assert await h.harvest() == 2
    urls = [r[0] for r in h.conn.execute("SELECT url FROM resources")]
    assert len([u for u in urls if "description?code=" in u]) == len(CODE_LISTS)
    # Yritystiedot ovat jo avoindata.fi:n kautta: ei companies- eikä bulk-resurssia.
    assert not any("/companies" in u or "all_companies" in u for u in urls)
