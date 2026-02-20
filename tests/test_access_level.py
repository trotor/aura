"""Testit access_level-metatietokentälle."""

import sqlite3

import pytest

from aura.database import get_dataset, init_db, upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestMakeDatasetDefault:
    """_make_dataset() oletusarvo."""

    def test_default_access_level_is_open(self):
        """_make_dataset() asettaa access_level='open' oletuksena."""

        class DummyHarvester(BaseHarvester):
            name = "test"

            async def harvest(self) -> int:
                return 0

        h = DummyHarvester(conn=_memory_db())
        ds = h._make_dataset(id="test-1", name="test-1")
        assert ds.access_level == "open"

    def test_access_level_can_be_overridden(self):
        """_make_dataset() sallii access_level-arvon ohittamisen."""

        class DummyHarvester(BaseHarvester):
            name = "test"

            async def harvest(self) -> int:
                return 0

        h = DummyHarvester(conn=_memory_db())
        ds = h._make_dataset(id="test-1", name="test-1", access_level="restricted")
        assert ds.access_level == "restricted"


class TestUpsertAccessLevel:
    """Upsert tallentaa ja palauttaa access_level."""

    def test_upsert_stores_access_level(self):
        """upsert_dataset tallentaa access_level-arvon tietokantaan."""
        conn = _memory_db()
        ds = Dataset(
            id="test-restricted",
            name="test-restricted",
            title="Test",
            access_level="restricted",
        )
        upsert_dataset(conn, ds)
        conn.commit()

        result = get_dataset(conn, "test-restricted")
        assert result is not None
        assert result["access_level"] == "restricted"

    def test_upsert_default_access_level(self):
        """Oletusarvoinen datasetti tallentuu access_level='open'."""
        conn = _memory_db()
        ds = Dataset(id="test-open", name="test-open", title="Test")
        upsert_dataset(conn, ds)
        conn.commit()

        result = get_dataset(conn, "test-open")
        assert result is not None
        assert result["access_level"] == "open"

    def test_upsert_updates_access_level(self):
        """access_level päivittyy upsertissä."""
        conn = _memory_db()
        ds = Dataset(id="test-update", name="test-update", access_level="open")
        upsert_dataset(conn, ds)
        conn.commit()

        ds.access_level = "registration"
        upsert_dataset(conn, ds)
        conn.commit()

        result = get_dataset(conn, "test-update")
        assert result is not None
        assert result["access_level"] == "registration"


class TestMigration:
    """Migraatio lisää access_level-sarakkeen."""

    def test_column_exists_after_init(self):
        """access_level-sarake on olemassa init_db:n jälkeen."""
        conn = _memory_db()
        columns = conn.execute("PRAGMA table_info(datasets)").fetchall()
        column_names = [c["name"] for c in columns]
        assert "access_level" in column_names

    def test_column_default_value(self):
        """access_level-sarakkeen oletusarvo on 'open'."""
        conn = _memory_db()
        columns = conn.execute("PRAGMA table_info(datasets)").fetchall()
        for col in columns:
            if col["name"] == "access_level":
                assert col["dflt_value"] == "'open'"
                break
        else:
            pytest.fail("access_level column not found")
