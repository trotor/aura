"""Laatuprofiili: oma pinta julkaisijoille, oma endpoint /mcp/laatu."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest
from fastmcp import Client

from aura.database import init_db, upsert_dataset
from aura.models import Dataset
from aura.server import (
    WRITE_TOOL_NAMES,
    apply_tool_profile,
    build_instructions,
    build_quality_server,
    mcp,
    reset_tool_profile,
)

QUALITY_TOOLS = {
    "quality_summary", "metadata_gaps", "availability_report",
    "find_data", "inspect_dataset", "log_finding", "list_findings",
}


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_db(c)
    for i, (org, notes) in enumerate(
        [("Espoon kaupunki", "Kuvaus"), ("Espoon kaupunki", ""), ("Vantaan kaupunki", "X")]
    ):
        upsert_dataset(
            c,
            Dataset(id=f"d{i}", name=f"d{i}", title=f"Aineisto {i}", title_fi=f"Aineisto {i}",
                    notes_fi=notes, organization_title=org, source="avoindata.fi",
                    license_id="cc-by-4.0" if i != 1 else ""),
        )
    c.executemany(
        "INSERT INTO quality_scores (dataset_id, dimension, score, details) VALUES (?, ?, ?, '{}')",
        [("d0", "overall", 82), ("d0", "documentation", 70), ("d1", "overall", 25),
         ("d1", "documentation", 10), ("d2", "overall", 60)],
    )
    c.executemany(
        "INSERT INTO resource_health (resource_id, dataset_id, url, status_code, is_available,"
        " response_time_ms, checked_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [("r0", "d0", "https://x/ok", 200, 1, 120, "2026-09-20T10:00:00"),
         ("r1", "d1", "https://x/rikki", 404, 0, 80, "2026-09-20T10:00:00")],
    )
    c.commit()
    return c


@pytest.fixture()
def laatu(conn: sqlite3.Connection) -> Iterator[None]:
    apply_tool_profile(mcp, profile="laatu")
    try:
        with patch("aura.server._get_conn", return_value=conn):
            yield
    finally:
        reset_tool_profile(mcp)


async def _call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        result = await client.call_tool(name, args, raise_on_error=False)
    jsonschema.validate(result.structured_content, tools[name].output_schema)
    data: dict[str, Any] = result.structured_content
    return data


async def test_laatuprofiilin_tyokalut(laatu: None) -> None:
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert names == QUALITY_TOOLS
    assert not names & WRITE_TOOL_NAMES, "laatuprofiilissa ei saa olla kirjoittavia työkaluja"
    assert "health_check" not in names


def test_laatuohje_alle_1500_merkkia() -> None:
    text = build_instructions(readonly=True, profile="laatu")
    assert len(text) < 1500
    for tool in ("quality_summary", "metadata_gaps", "availability_report"):
        assert tool in text


async def test_quality_summary_julkaisijalle(laatu: None) -> None:
    data = await _call("quality_summary", {"organization": "Espoo"})
    assert data["datasets"] == 2
    assert data["weakest"][0]["id"] == "d1"
    assert data["distribution"] == {"0-29": 1, "30-59": 0, "60-79": 0, "80-100": 1}
    assert data["scope"] == {"organization": "Espoo"}


async def test_quality_summary_tuntematon_julkaisija(laatu: None) -> None:
    data = await _call("quality_summary", {"organization": "Atlantis"})
    assert data["error"]["code"] == "no_scores"


async def test_metadata_gaps(laatu: None) -> None:
    data = await _call("metadata_gaps", {"organization": "Espoo"})
    assert data["datasets"] == 2
    assert data["missing"]["kuvaus"] == 1 and data["missing"]["lisenssi"] == 1
    assert data["easiest"][0]["id"] == "d1"
    assert {"kuvaus", "lisenssi"} <= set(data["easiest"][0]["missing"])


async def test_availability_report_kertoo_ian(laatu: None) -> None:
    data = await _call("availability_report", {"organization": "Espoo"})
    assert data["resources_checked"] == 2 and data["available"] == 1
    assert data["failing"][0]["url"] == "https://x/rikki"
    assert data["last_checked"].startswith("2026-09-20")


def test_erillinen_palvelin_sisaltaa_vain_laatutyokalut() -> None:
    import asyncio

    server = build_quality_server(mcp)

    async def names() -> set[str]:
        async with Client(server) as client:
            return {t.name for t in await client.list_tools()}

    assert asyncio.run(names()) == QUALITY_TOOLS


class TestLoydostenErottelu:
    """Löydökset kuuluvat istunnolle, eivät koko prosessille (8.10.2026).

    Julkisessa /mcp/laatu-profiilissa yksi lista jaettiin kaikkien käyttäjien
    kesken: A:n kirjaama teksti näkyi B:n list_findings-kutsussa, ja lista kasvoi
    rajatta.
    """

    class _Ctx:
        def __init__(self, store: dict, session: str | None) -> None:
            self.lifespan_context = {"findings": store}
            self._session = session

        @property
        def session_id(self) -> str:
            if self._session is None:
                raise RuntimeError("tilaton HTTP")
            return self._session

    def test_istunnot_eivat_nae_toisiaan(self) -> None:
        from aura.tools.research import _get_findings

        store: dict = {}
        _get_findings(self._Ctx(store, "a")).append({"finding": "A:n salaisuus"})
        assert _get_findings(self._Ctx(store, "b")) == []
        assert len(_get_findings(self._Ctx(store, "a"))) == 1

    def test_ilman_istuntoa_ei_jaeta(self) -> None:
        from aura.tools.research import _get_findings

        store: dict = {}
        _get_findings(self._Ctx(store, None)).append({"finding": "x"})
        assert _get_findings(self._Ctx(store, None)) == []

    def test_istuntojen_maara_rajattu(self) -> None:
        from aura.tools.research import MAX_SESSIONS, _get_findings

        store: dict = {}
        for i in range(MAX_SESSIONS + 5):
            _get_findings(self._Ctx(store, f"s{i}")).append({"finding": "x"})
        assert len(store) == MAX_SESSIONS


def test_read_only_poistaa_istuntomuistin_tyokalut() -> None:
    """Julkisessa palvelussa istuntotunniste on asiakkaan otsake: ei jaettua muistia."""
    import asyncio

    from fastmcp import FastMCP

    from aura.server import SESSION_MEMORY_TOOL_NAMES, apply_readonly_gating

    server = FastMCP("t")
    for name in (*SESSION_MEMORY_TOOL_NAMES, "find_data"):
        @server.tool(name=name)
        def _fn() -> str:
            return "ok"
    apply_readonly_gating(server, readonly=True)

    async def names() -> set[str]:
        async with Client(server) as client:
            return {t.name for t in await client.list_tools()}

    assert asyncio.run(names()) == {"find_data"}
    assert "log_finding" not in build_instructions(readonly=True, profile="laatu")
    assert "log_finding" not in build_instructions(readonly=True)
    assert "log_finding" in build_instructions(readonly=False, profile="laatu")
