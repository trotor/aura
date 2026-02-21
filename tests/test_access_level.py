"""Testit access_level-metatietokentälle."""

import sqlite3

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

    def test_default_and_override(self):
        """_make_dataset() asettaa access_level='open' ja sallii ohituksen."""

        class DummyHarvester(BaseHarvester):
            name = "test"

            async def harvest(self) -> int:
                return 0

        h = DummyHarvester(conn=_memory_db())
        ds_default = h._make_dataset(id="test-1", name="test-1")
        assert ds_default.access_level == "open"

        ds_restricted = h._make_dataset(id="test-2", name="test-2", access_level="restricted")
        assert ds_restricted.access_level == "restricted"


class TestUpsertAccessLevel:
    """Upsert tallentaa ja päivittää access_level."""

    def test_upsert_stores_access_level(self):
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

    def test_upsert_updates_access_level(self):
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
        conn = _memory_db()
        columns = conn.execute("PRAGMA table_info(datasets)").fetchall()
        column_names = [c["name"] for c in columns]
        assert "access_level" in column_names
