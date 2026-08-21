"""Testit probe-vaiheen uusille enrichment-kentille.

use_case on ainoa puuttuvista kentistä joka ei ole johdettavissa
lähteestä. Generoitu sisältö muuttuu katalogissa faktaksi seuraavalle
lukijalle, joten se ei saa asua samassa kentässä kuin ihmisen kirjoittama.
Erillinen kenttä kertoo sen **nimellä** — provenienssimetatieto ei näy
lukijalle samalla tavalla.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import aura.server  # noqa: F401 — resolve circular import before tools
from aura.database import init_db
from aura.tools.enrichment import VALID_ENRICHMENT_FIELDS


@pytest.mark.parametrize(
    "kentta", ["service_layers", "example_request", "use_case_suggested"]
)
def test_uusi_kentta_on_sallittu(kentta: str) -> None:
    assert kentta in VALID_ENRICHMENT_FIELDS


def test_use_case_sailyy_sallittuna() -> None:
    """Ihmisen kirjoittama use_case ei katoa mihinkään."""
    assert "use_case" in VALID_ENRICHMENT_FIELDS


def test_migraatio_siirtaa_ai_rivit() -> None:
    """Migraation SQL ajetaan käsin, koska init_db on jo ajanut sen.

    init_db ajaa kaikki migraatiot, joten testidata syntyy vasta migraation
    jälkeen eikä toinen run_migrations-kutsu tekisi mitään. Tässä testataan
    migraation SQL, ei migraatiokirjanpitoa.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    conn.execute(
        "INSERT INTO enrichments (dataset_id, field, value, source_type)"
        " VALUES ('d1','use_case','Generoitu kuvaus','ai_analysis')"
    )
    conn.execute(
        "INSERT INTO enrichments (dataset_id, field, value, source_type)"
        " VALUES ('d1','use_case','Ihmisen kirjoittama','mcp_session')"
    )
    conn.commit()

    sql = Path("scripts/migrations/023_use_case_suggested.sql").read_text(
        encoding="utf-8"
    )
    conn.executescript(sql)

    siirretty = conn.execute(
        "SELECT value FROM enrichments WHERE field = 'use_case_suggested'"
    ).fetchall()
    assert [r["value"] for r in siirretty] == ["Generoitu kuvaus"]

    jaljella = conn.execute(
        "SELECT value FROM enrichments WHERE field = 'use_case'"
    ).fetchall()
    assert [r["value"] for r in jaljella] == ["Ihmisen kirjoittama"]
