"""Testit CLI:lle."""

import sqlite3
import subprocess
import sys
from unittest.mock import patch

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_db(conn: sqlite3.Connection) -> None:
    upsert_dataset(
        conn,
        Dataset(
            id="test-1",
            name="testidatasetti",
            title="Testi",
            title_fi="Testidatasetti",
            notes_fi="Kuvaus",
            organization_title="Testiorg",
            keywords_fi=["testi"],
            source="avoindata.fi",
            num_resources=1,
            resources=[
                Resource(id="r-1", name="test.csv", format="CSV", url="https://example.com/t.csv")
            ],
        ),
    )
    conn.commit()


class TestVersion:
    """--version testit."""

    def test_version_output(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "aura.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "aura" in result.stdout


class TestHarvestList:
    """harvest --list testit."""

    def test_harvest_list(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "aura.cli", "harvest", "--list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "avoindata.fi" in result.stdout
        assert "statfin" in result.stdout
        assert "digitraffic" in result.stdout


class TestSearch:
    """search-komennon testit."""

    def test_search_with_mock_db(self) -> None:
        conn = _memory_db()
        _seed_db(conn)

        with patch("aura.database.get_connection", return_value=conn):
            from aura.cli import main

            with patch("sys.argv", ["aura", "search", "testi"]):
                main()


class TestStats:
    """stats-komennon testit."""

    def test_stats_with_mock_db(self) -> None:
        conn = _memory_db()
        _seed_db(conn)

        with patch("aura.database.get_connection", return_value=conn):
            from aura.cli import main

            with patch("sys.argv", ["aura", "stats"]):
                main()


class TestSources:
    """sources-komennon testit."""

    def test_sources_with_mock_db(self) -> None:
        conn = _memory_db()
        _seed_db(conn)

        with patch("aura.database.get_connection", return_value=conn):
            from aura.cli import main

            with patch("sys.argv", ["aura", "sources"]):
                main()
