"""Testit sille että epäonnistunut probe näkyy siellä missä sitä katsotaan.

"Ei saatu selville" on agentille tietoa, ei tyhjä. Ilman tätä puuttuva
skeema näyttää samalta kuin skeema jota ei ole yritettykään hakea, ja
agentti päättelee aineiston olevan käyttökelvoton.
"""

from __future__ import annotations

import sqlite3

import pytest

# Import server first to avoid circular import when importing from tools
import aura.server  # noqa: F401
from aura.database import init_db, upsert_probe_result
from aura.tools.describe import _format_probe_failure


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    c.commit()
    return c


def test_epaonnistuminen_nakyy_syineen(conn: sqlite3.Connection) -> None:
    upsert_probe_result(
        conn, "r1", "d1", "wfs", "http_error", "HTTP 404", "2026-08-19T10:00:00"
    )
    conn.commit()
    teksti = _format_probe_failure(conn, "d1")
    assert "HTTP 404" in teksti
    assert "2026-08-19" in teksti


def test_onnistunut_probe_ei_lisaa_rivia(conn: sqlite3.Connection) -> None:
    upsert_probe_result(conn, "r1", "d1", "wfs", "ok", "", "2026-08-19T10:00:00")
    conn.commit()
    assert _format_probe_failure(conn, "d1") == ""


def test_probaamaton_ei_lisaa_rivia(conn: sqlite3.Connection) -> None:
    assert _format_probe_failure(conn, "d1") == ""


def test_paljon_epaonnistumisia_rajataan_ja_kertoo_lopun(
    conn: sqlite3.Connection,
) -> None:
    """(I5) 428 probattavaa resurssia ei saa listautua yhtenä pötkönä.

    Katkaisu ei saa olla hiljainen: lopun määrä on näyttävä lukuna.
    """
    for i in range(15):
        upsert_probe_result(
            conn, f"r{i}", "d1", "wfs", "http_error", f"HTTP {400 + i}",
            f"2026-08-{i + 1:02d}T10:00:00",
        )
    conn.commit()
    teksti = _format_probe_failure(conn, "d1")
    rivit = [r for r in teksti.splitlines() if r.startswith("- ")]
    # 10 näytettyä riviä + yksi "... ja N muuta" -rivi.
    assert len(rivit) == 11
    assert "5 muuta epäonnistunutta resurssia" in teksti
