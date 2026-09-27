"""Aikomustason työkalupinta: profiilit, outputSchema ja strukturoidut vastaukset (TP4).

Jokainen julkisen profiilin työkalu kutsutaan oikean MCP-asiakkaan kautta,
ja vastauksen ``structuredContent`` validoidaan julkaistua ``outputSchema``a
vasten. Testi joka vain tarkistaa että skeema on olemassa ei huomaisi, jos
työkalu palauttaisi jotain muuta kuin lupaa.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest
from fastmcp import Client

from aura import extensions
from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import (
    DEPRECATED_TOOLS,
    apply_tool_profile,
    build_instructions,
    mcp,
    reset_tool_profile,
)

PUBLIC_TOOLS = {"find_data", "inspect_dataset", "query_source", "area_snapshot", "find_related"}


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_db(c)
    upsert_dataset(
        c,
        Dataset(
            id="statfin-11ra.px",
            name="statfin-11ra.px",
            title="11ra -- Tunnuslukuja väestöstä alueittain",
            title_fi="11ra -- Tunnuslukuja väestöstä alueittain",
            notes_fi="Väestö, keski-ikä ja huoltosuhde kunnittain.",
            organization_title="Tilastokeskus",
            license_title="CC BY 4.0",
            keywords_fi=["väestö", "väkiluku"],
            source="statfin",
            geographical_coverage=["Suomi"],
            resources=[
                Resource(
                    id="r1",
                    name="PxWeb",
                    format="PXWEB",
                    url="https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/vaerak/11ra.px",
                )
            ],
        ),
    )
    upsert_dataset(
        c,
        Dataset(
            id="tre-vaesto",
            name="tampereen-vaesto",
            title="Tampereen väestö",
            title_fi="Tampereen väestö",
            notes_fi="Tampereen väkiluku alueittain.",
            organization_title="Tampereen kaupunki",
            license_title="CC BY 4.0",
            keywords_fi=["väestö", "väkiluku"],
            source="avoindata.fi",
            geographical_coverage=["Tampere"],
            resources=[Resource(id="r2", name="CSV", format="CSV", url="https://example.fi/v.csv")],
        ),
    )
    c.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv, region_code, region_name_fi)"
        " VALUES ('837', 'Tampere', 'Tammerfors', '06', 'Pirkanmaa')"
    )
    c.execute("INSERT INTO ref_metadata (name, record_count) VALUES ('municipalities', 1)")
    c.executemany(
        "INSERT INTO ref_areas (level, code, name_fi, name_sv, vintage) VALUES (?, ?, ?, ?, 2026)",
        [("kunta", "837", "Tampere", "Tammerfors"), ("maakunta", "06", "Pirkanmaa", "Birkaland")],
    )
    c.execute("INSERT INTO ref_area_membership VALUES ('837', 'maakunta', '06', 2026)")
    c.commit()
    return c


@pytest.fixture()
def public(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    apply_tool_profile(mcp, profile="public")
    try:
        with patch("aura.server._get_conn", return_value=conn):
            yield conn
    finally:
        reset_tool_profile(mcp)


async def _call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        result = await client.call_tool(name, args, raise_on_error=False)
    schema = tools[name].outputSchema
    assert schema, f"{name}: outputSchema puuttuu"
    data = result.structured_content
    assert isinstance(data, dict), f"{name}: structuredContent puuttuu"
    jsonschema.validate(data, schema)
    text = result.content[0].text  # type: ignore[union-attr]
    assert 0 < len(text.splitlines()) <= 5, f"{name}: tekstiyhteenveto yli 5 riviä"
    return data


async def test_julkisessa_profiilissa_enintaan_8_tyokalua(public: sqlite3.Connection) -> None:
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
        prompts = {p.name for p in await client.list_prompts()}
        templates = {t.uriTemplate for t in await client.list_resource_templates()}
    assert names == PUBLIC_TOOLS
    assert len(names) <= 8
    assert {"kuntavertailu", "loyda-ja-hae", "aluekatsaus"} <= prompts
    assert "aura://kunta/{koodi}" in templates


async def test_jokaisella_julkisella_on_output_schema(public: sqlite3.Connection) -> None:
    async with Client(mcp) as client:
        for tool in await client.list_tools():
            assert tool.outputSchema, tool.name


async def test_admin_profiili_nayttaa_kaiken_ja_merkitsee_vanhentuneet() -> None:
    reset_tool_profile(mcp)
    apply_tool_profile(mcp, profile="admin")
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert PUBLIC_TOOLS <= set(tools)
    for old, new in DEPRECATED_TOOLS.items():
        assert tools[old].description.startswith(f"Vanhentunut: käytä {new}"), old


def test_julkinen_ohje_alle_1500_merkkia() -> None:
    text = build_instructions(readonly=True, profile="public")
    assert len(text) < 1500
    for tool in ("find_data", "inspect_dataset", "query_source", "area_snapshot"):
        assert tool in text


async def test_find_data(public: sqlite3.Connection) -> None:
    data = await _call("find_data", {"query": "väkiluku", "region": "Tampere"})
    ids = [r["id"] for r in data["results"]]
    assert "tre-vaesto" in ids
    assert data["region"]["statfin_code"] == "KU837"
    own = next(r for r in data["results"] if r["id"] == "tre-vaesto")
    assert own["coverage"] == "own" and own["license"] == "CC BY 4.0"
    assert data["next_actions"][0]["tool"] == "inspect_dataset"


async def test_find_data_indikaattorikoukku(public: sqlite3.Connection) -> None:
    def hook(conn: Any, query: str, region: Any) -> list[dict[str, Any]]:
        return [{"id": "vakiluku", "name": "Väkiluku", "unit": "henkeä", "tool": "get_facts"}]

    extensions.register("find_data.indicators", hook)
    try:
        data = await _call("find_data", {"query": "väkiluku", "region": "Tampere"})
    finally:
        extensions.clear("find_data.indicators")
    assert data["indicators"][0]["id"] == "vakiluku"
    assert data["next_actions"][0] == {
        "tool": "get_facts",
        "args": {"indicator": "vakiluku", "areas": ["837"]},
        "why": "Valmis tunnusluku: arvo suoraan",
    }


async def test_find_data_ilman_parametreja(public: sqlite3.Connection) -> None:
    data = await _call("find_data", {})
    assert data["results"] == [] and data["notes"]


async def test_inspect_dataset(public: sqlite3.Connection) -> None:
    data = await _call("inspect_dataset", {"dataset_id": "statfin-11ra.px"})
    assert data["dataset"]["license"] == "CC BY 4.0"
    assert data["resources"][0]["queryable"] is True
    assert data["next_actions"][0]["tool"] == "query_source"


async def test_inspect_dataset_virhe_on_strukturoitu(public: sqlite3.Connection) -> None:
    data = await _call("inspect_dataset", {"dataset_id": "ei-ole"})
    assert data["error"]["code"] == "dataset_not_found"
    assert data["error"]["suggested_call"]["tool"] == "find_data"


async def test_query_source_tuntematon_formaatti(public: sqlite3.Connection) -> None:
    upsert_dataset(
        public,
        Dataset(
            id="pdf-only",
            name="pdf-only",
            title="PDF",
            source="avoindata.fi",
            resources=[Resource(id="r3", name="R", format="PDF", url="https://x/a.pdf")],
        ),
    )
    data = await _call("query_source", {"dataset_id": "pdf-only"})
    assert data["error"]["code"] == "unsupported_format"


async def test_query_source_pxweb_rivit_ja_lahde(public: sqlite3.Connection) -> None:
    meta = {
        "title": "Tunnuslukuja",
        "variables": [
            {
                "code": "Alue",
                "text": "Alue",
                "values": ["SSS", "KU837"],
                "valueTexts": ["KOKO MAA", "Tampere"],
            },
            {"code": "Tiedot", "text": "Tiedot", "values": ["vaesto"], "valueTexts": ["Väestö"]},
            {
                "code": "Vuosi",
                "text": "Vuosi",
                "values": ["2023", "2024"],
                "valueTexts": ["2023", "2024"],
                "time": True,
            },
        ],
    }
    stat = {
        "id": ["Alue", "Tiedot", "Vuosi"],
        "size": [1, 1, 1],
        "dimension": {
            "Alue": {
                "label": "Alue",
                "category": {"index": {"KU837": 0}, "label": {"KU837": "Tampere"}},
            },
            "Tiedot": {
                "label": "Tiedot",
                "category": {"index": {"vaesto": 0}, "label": {"vaesto": "Väestö"}},
            },
            "Vuosi": {
                "label": "Vuosi",
                "category": {"index": {"2024": 0}, "label": {"2024": "2024"}},
            },
        },
        "value": [260180],
    }

    class _Resp:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.payload, self.status_code, self.text = payload, 200, ""

        def json(self) -> dict[str, Any]:
            return self.payload

        def raise_for_status(self) -> None:
            return None

    async def fake_get(self: Any, url: str, **kw: Any) -> _Resp:
        return _Resp(meta)

    async def fake_post(self: Any, url: str, **kw: Any) -> _Resp:
        body = kw["json"]["query"]
        assert {"code": "Alue", "selection": {"filter": "item", "values": ["KU837"]}} in body
        assert {"code": "Vuosi", "selection": {"filter": "item", "values": ["2024"]}} in body
        return _Resp(stat)

    with patch("httpx.AsyncClient.get", fake_get), patch("httpx.AsyncClient.post", fake_post):
        data = await _call(
            "query_source",
            {
                "dataset_id": "statfin-11ra.px",
                "filters": {"Tiedot": ["Väestö"], "Vuosi": ["uusin"]},
                "area": "837",
            },
        )
    assert data["rows"] == [
        {"Alue": "Tampere", "Tiedot": "Väestö", "Vuosi": "2024", "value": 260180}
    ]
    assert data["codes"]["Alue"] == {"Tampere": "KU837"}
    prov = data["provenance"]
    assert prov["license"] == "CC BY 4.0" and prov["source"] == "Tilastokeskus"
    assert prov["query"]["query"] and prov["source_url"].endswith("11ra.px")


async def test_area_snapshot(public: sqlite3.Connection) -> None:
    data = await _call("area_snapshot", {"region": "Tampere"})
    assert data["area"]["code"] == "837"
    assert data["parents"]["maakunta"]["name_fi"] == "Pirkanmaa"
    assert data["codes"]["statfin"] == "KU837"
    assert data["datasets_local"] == 1


async def test_area_snapshot_tuntematon(public: sqlite3.Connection) -> None:
    data = await _call("area_snapshot", {"region": "Atlantis"})
    assert data["error"]["code"] == "unknown_area"


async def test_find_related(public: sqlite3.Connection) -> None:
    data = await _call("find_related", {"dataset_id": "tre-vaesto"})
    assert data["dataset_id"] == "tre-vaesto"
