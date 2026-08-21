"""Testit probe-kirjanpidolle.

Nykyinen infer-schemas tulostaa virheen ja unohtaa sen, joten sama
rikkinäinen resurssi yritetään uudestaan joka ajolla eikä kukaan tiedä mikä
on rikki. Kirjanpito on se ero: epäonnistuminen on tulos, ei tyhjä.
"""

from __future__ import annotations

import sqlite3

import pytest

from aura.database import get_probe_result, init_db, upsert_probe_result


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c


def test_tulos_tallentuu_ja_loytyy(conn: sqlite3.Connection) -> None:
    upsert_probe_result(conn, "r1", "d1", "wfs", "ok", "", "2026-08-19T10:00:00")
    row = get_probe_result(conn, "r1")
    assert row is not None
    assert row["status"] == "ok"
    assert row["probe_type"] == "wfs"


def test_uusi_tulos_korvaa_vanhan(conn: sqlite3.Connection) -> None:
    """Taulu kantaa viimeisimmän tilan, ei historiaa."""
    upsert_probe_result(conn, "r1", "d1", "wfs", "http_error", "HTTP 404", "2026-08-01T00:00:00")
    upsert_probe_result(conn, "r1", "d1", "wfs", "ok", "", "2026-08-19T00:00:00")
    row = get_probe_result(conn, "r1")
    assert row is not None
    assert row["status"] == "ok"
    assert row["detail"] == ""
    assert conn.execute("SELECT COUNT(*) FROM probe_results").fetchone()[0] == 1


def test_epaonnistuminen_kantaa_syyn(conn: sqlite3.Connection) -> None:
    upsert_probe_result(conn, "r2", "d1", "csv", "http_error", "HTTP 404", "2026-08-19T00:00:00")
    row = get_probe_result(conn, "r2")
    assert row is not None
    assert row["detail"] == "HTTP 404"


def test_tuntematon_resurssi_on_none(conn: sqlite3.Connection) -> None:
    assert get_probe_result(conn, "ei-ole") is None


def test_prune_siivoaa_taulun() -> None:
    """Kadonneen datasetin rivit eivät saa jäädä roikkumaan."""
    from aura.prune import RELATED_TABLES

    assert "probe_results" in RELATED_TABLES
