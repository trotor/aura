"""Työkalu- ja ketjutelemetria: vain kuviot ja laskurit, ei istuntoja."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastmcp import Client

from aura.telemetry import ChainRecorder, record_pattern, top_patterns


@pytest.fixture()
def telemetry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "t.db"
    monkeypatch.setenv("AURA_TELEMETRY_DB", str(path))
    return path


def test_pois_paalta_ilman_ymparistomuuttujaa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AURA_TELEMETRY_DB", raising=False)
    assert record_pattern("tool", "find_data") is False


def test_kuvio_ja_laskuri(telemetry: Path) -> None:
    assert record_pattern("tool", "find_data")
    assert record_pattern("tool", "find_data")
    assert record_pattern("unmatched", "revontulien\x1b[2K kirkkaus")
    rows = top_patterns("tool")
    assert rows[0]["pattern"] == "find_data" and rows[0]["count"] == 2
    # Ohjausmerkit eivät päädy kantaan (ks. zero_results).
    assert "\x1b" not in top_patterns("unmatched")[0]["pattern"]


def test_ketju_ei_tallenna_istuntoa(telemetry: Path) -> None:
    rec = ChainRecorder(idle_seconds=10)
    rec.add("istunto-1", "find_data", 0.0)
    rec.add("istunto-1", "inspect_dataset", 1.0)
    rec.add("istunto-1", "query_source", 2.0)
    rec.add(None, "get_facts", 3.0)  # tilaton: vain työkalumäärä
    rec.flush_idle(100.0)
    chains = top_patterns("chain")
    assert [c["pattern"] for c in chains] == ["find_data → inspect_dataset → query_source"]
    con = sqlite3.connect(telemetry)
    dump = "\n".join(con.iterdump())
    assert "istunto-1" not in dump


async def test_middleware_kirjaa_tyokalun(telemetry: Path) -> None:
    from aura.server import mcp

    async with Client(mcp) as client:
        await client.call_tool("find_data", {}, raise_on_error=False)
    assert any(r["pattern"] == "find_data" for r in top_patterns("tool"))


def test_tyhjennys_poistaa_myos_kuviot(telemetry: Path) -> None:
    from aura.telemetry import clear_zero_results, record_zero_result

    record_zero_result("revontulet")
    record_pattern("tool", "find_data")
    assert clear_zero_results() == 2
    assert top_patterns("tool") == []
