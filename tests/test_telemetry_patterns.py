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


async def test_kaytto_ja_kysytyt_kasitteet(telemetry: Path) -> None:
    """Päivälaskuri, argumenttien arvot ja virhekoodi — ei istuntoa eikä kellonaikaa."""
    from aura.server import mcp
    from aura.telemetry import usage_report

    async with Client(mcp) as client:
        await client.call_tool("find_data", {"query": "metsä", "region": "Tampere"})
        await client.call_tool("find_data", {"query": "metsä"})
        await client.call_tool(
            "inspect_dataset", {"dataset_id": "ei-ole-olemassa"}, raise_on_error=False
        )
    report = usage_report()
    tools = {r["tool"]: r for r in report["per_tool"]}  # type: ignore[union-attr]
    assert tools["find_data"]["calls"] == 2
    assert tools["inspect_dataset"]["errors"] == 1
    assert report["query"][0] == {  # type: ignore[index]
        "pattern": "metsä", "count": 2, "last_seen": report["query"][0]["last_seen"]  # type: ignore[index]
    }
    assert [r["pattern"] for r in report["area"]] == ["Tampere"]  # type: ignore[union-attr]
    assert report["error"][0]["pattern"] == "inspect_dataset:dataset_not_found"  # type: ignore[index]
    assert report["per_client"][0]["client"] == "stdio"  # type: ignore[index]
    dump = "\n".join(sqlite3.connect(telemetry).iterdump())
    assert "T" not in {c for row in report["per_day"] for c in str(row["day"])}  # type: ignore[union-attr]
    assert "session" not in dump.lower()


def test_asiakasohjelman_nimi() -> None:
    from aura.telemetry import client_kind

    assert client_kind("claude-user/1.0 (+https://claude.ai)") == "claude-user"
    assert client_kind("Mozilla/5.0 (Macintosh)") == "mozilla"
    assert client_kind("\x1b[2Kpaha/1") == "2kpaha"
