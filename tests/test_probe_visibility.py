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
