"""Testit sille että jaeltu kanta saa olla koodia vanhempi.

Julkinen instanssi ajaa **tilannekuvaa**: kanta on paistettu imageen ja
avataan read-only, joten migraatioita ei voi ajaa käynnistyksessä. Kun
koodi on kannan jäljessä tuoreempi, uusimman migraation taulu puuttuu.

Näin kävi tuotannossa 22.8.–18.9.2026: `probe_results` puuttui jaellusta
kannasta, ja suojaamaton kysely kaatoi ländärisivun, `stats`-työkalun ja
`describe`-työkalun **jokaisella** datasetillä neljän viikon ajan. `/health`
ei koskenut tauluun, joten mikään ei kertonut siitä.

Ydinreitin on kestettävä puuttuva valinnainen taulu — mutta ei hiljaa:
puute kirjataan lokiin kerran, koska hiljainen ohitus oli itse vika.
"""

from __future__ import annotations

import logging
import sqlite3

import pytest

# Import server first to avoid circular import when importing from tools
import aura.server  # noqa: F401
from aura.database import _warned_missing_tables, get_stats, init_db
from aura.quality import collect_agent_facts
from aura.tools.describe import _format_probe_failure


@pytest.fixture
def vanha_kanta() -> sqlite3.Connection:
    """Kanta josta puuttuu viimeisimmän migraation taulu."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    conn.execute("DROP TABLE probe_results")
    conn.commit()
    # Varoitus annetaan kerran per prosessi, joten testien on nollattava
    # muisti — muuten järjestys ratkaisisi kumpi testi näkee varoituksen.
    _warned_missing_tables.clear()
    return conn


def test_tilastot_toimivat_ilman_probe_taulua(vanha_kanta: sqlite3.Connection) -> None:
    """Ländärisivu ja stats-työkalu kutsuvat tätä — ne eivät saa kaatua."""
    stats = get_stats(vanha_kanta)
    assert stats["total_datasets"] == 1
    assert stats["probe_total"] == 0
    assert stats["probe_ok"] == 0


def test_describe_toimii_ilman_probe_taulua(vanha_kanta: sqlite3.Connection) -> None:
    assert _format_probe_failure(vanha_kanta, "d1") == ""


def test_laatufaktat_toimivat_ilman_probe_taulua(
    vanha_kanta: sqlite3.Connection,
) -> None:
    assert collect_agent_facts(vanha_kanta) == {}


def test_puuttuva_taulu_ei_jaa_hiljaiseksi(
    vanha_kanta: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Puute on korjattavissa vain jos se näkyy jossain."""
    with caplog.at_level(logging.WARNING, logger="aura.database"):
        get_stats(vanha_kanta)
    assert any("probe_results" in r.message for r in caplog.records)
