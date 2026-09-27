"""Testit Kirjastot.fi-harvesterille (vuositilastot ja Kirkanta API v4).

Ulkoinen arvio 27.9.2026: "kirjastojen lainaukset kunnittain" ei löytänyt
aineistoa, jonka resurssi veisi dataan asti.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db, search_datasets
from aura.harvesters import HARVESTERS
from aura.harvesters.kirjastot import (
    FALLBACK_REPORTS,
    KIRKANTA_ID,
    STATS_ID,
    KirjastotHarvester,
    parse_yearly_reports,
)

_BASE = "https://www.kirjastot.fi/sites/default/files/content"
PAGE = f"""
<h1>Vuositilastot</h1>
Excel-tiedostoina:
<p>
<a href="{_BASE}/yleistenkirjastojen_tilastot2025.xls">2025</a><br>
<a href="{_BASE}/yleistenkirjastojen_tilastot2024_1.xls">2024</a> (päivitetty 9.4.2025)<br>
<a href="{_BASE}/YearlyReport_Y1999.xls">1999</a><br>
<a href="https://www.kirjastot.fi/ohje.pdf">Ohje</a>
"""


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


#: Alkuperäinen metodi talteen ennen kuin kiinnitys korvaa sen.
_YEARLY = KirjastotHarvester._yearly_reports


@pytest.fixture(autouse=True)
def _ei_verkkoa() -> Iterator[None]:
    with patch.object(
        KirjastotHarvester,
        "_yearly_reports",
        AsyncMock(return_value=parse_yearly_reports(PAGE)),
    ):
        yield


def test_rekisterissa() -> None:
    assert HARVESTERS["kirjastot"] is KirjastotHarvester


def test_vuositilastosivun_jasennys() -> None:
    reports = parse_yearly_reports(PAGE)
    assert [y for y, _ in reports] == [2025, 2024, 1999]
    assert reports[1][1].endswith("yleistenkirjastojen_tilastot2024_1.xls")


def test_varaluettelo_on_uusin_ensin() -> None:
    years = [y for y, _ in FALLBACK_REPORTS]
    assert years == sorted(years, reverse=True) and years[0] >= 2025


@pytest.mark.asyncio
async def test_harvest_vuositiedostot_ja_kirkanta() -> None:
    h = KirjastotHarvester(conn=_db())
    assert await h.harvest() == 2
    res = h.conn.execute(
        "SELECT id, format, url, name_fi FROM resources WHERE dataset_id = ? ORDER BY rowid",
        (STATS_ID,),
    ).fetchall()
    assert [r["format"] for r in res] == ["XLS", "XLS", "XLS", "HTML"]
    assert res[0]["name_fi"] == "Yleisten kirjastojen tilastot 2025 (Excel)"
    assert res[0]["id"] == f"{STATS_ID}-2025"
    notes = h.conn.execute("SELECT notes_fi FROM datasets WHERE id = ?", (STATS_ID,)).fetchone()
    assert "Vuodet 1999–2025." in notes[0]
    kirkanta = h.conn.execute(
        "SELECT format, url FROM resources WHERE dataset_id = ? ORDER BY rowid", (KIRKANTA_ID,)
    ).fetchall()
    assert kirkanta[0]["format"] == "JSON"
    assert kirkanta[0]["url"] == "https://api.kirjastot.fi/v4/library?limit=1000"
    lic = h.conn.execute("SELECT DISTINCT license_id FROM datasets").fetchall()
    assert [r[0].lower() for r in lic] == ["cc-by-4.0"]
    # Luokan konfiguraatio ei muutu keruussa.
    stats = next(c for c in KirjastotHarvester.datasets_config if c["id"] == STATS_ID)
    assert len(stats["resources"]) == 1


@pytest.mark.asyncio
async def test_varaluettelo_kun_sivu_ei_vastaa() -> None:
    h = KirjastotHarvester(conn=_db())
    with patch.object(h, "_fetch", AsyncMock(side_effect=RuntimeError("nurin"))):
        assert await _YEARLY(h) == list(FALLBACK_REPORTS)
    resp = MagicMock()
    resp.text = "<html>ei linkkejä</html>"
    with patch.object(h, "_fetch", AsyncMock(return_value=resp)):
        assert await _YEARLY(h) == list(FALLBACK_REPORTS)


@pytest.mark.asyncio
async def test_lainaukset_kunnittain_loytaa_tilastot() -> None:
    h = KirjastotHarvester(conn=_db())
    await h.harvest()
    hits = search_datasets(h.conn, "kirjastojen lainaukset kunnittain", limit=5)
    assert hits and hits[0]["id"] == STATS_ID
