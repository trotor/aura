"""Testit BasePopulator-kantaluokalle."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from aura.database import run_migrations
from aura.populators.base import BasePopulator


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


class ConcretePopulator(BasePopulator):
    """Testaukseen käytettävä konkreettinen populaattori."""

    name = "test_populator"
    description = "Testipopulaattori"
    source_url = "https://example.com"

    async def populate(self) -> int:
        return 0


class TestBasePopulatorInit:
    def test_creates_with_connection(self) -> None:
        conn = _memory_db()
        p = ConcretePopulator(conn=conn)
        assert p.conn is conn

    def test_name_and_description(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        assert p.name == "test_populator"
        assert p.description == "Testipopulaattori"


class TestIsPopulated:
    def test_not_populated_initially(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        assert p.is_populated() is False

    def test_populated_after_metadata(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(42, version="20250101")
        assert p.is_populated() is True

    def test_not_populated_with_zero_count(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(0, version="20250101")
        assert p.is_populated() is False


class TestNeedsUpdate:
    def test_needs_update_when_not_populated(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        assert p.needs_update() is True

    def test_no_update_when_fresh(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(42, version="20250101")
        assert p.needs_update(max_age_days=30) is False

    def test_needs_update_when_old(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(42, version="20250101")
        # Manipuloi populated_at vanhaksi
        old_date = (datetime.now(UTC) - timedelta(days=31)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        p.conn.execute(
            "UPDATE ref_metadata SET populated_at = ? WHERE name = ?",
            (old_date, p.name),
        )
        p.conn.commit()
        assert p.needs_update(max_age_days=30) is True


class TestUpdateMetadata:
    def test_insert_metadata(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(100, version="20250101")

        row = p.conn.execute(
            "SELECT * FROM ref_metadata WHERE name = ?", (p.name,)
        ).fetchone()
        assert row["record_count"] == 100
        assert row["version"] == "20250101"
        assert row["populated_at"] is not None

    def test_upsert_metadata(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(100, version="20250101")
        p._update_metadata(200, version="20260101")

        row = p.conn.execute(
            "SELECT * FROM ref_metadata WHERE name = ?", (p.name,)
        ).fetchone()
        assert row["record_count"] == 200
        assert row["version"] == "20260101"

    def test_default_version_empty(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        p._update_metadata(50)

        row = p.conn.execute(
            "SELECT version FROM ref_metadata WHERE name = ?", (p.name,)
        ).fetchone()
        assert row["version"] == ""


class TestMakeClient:
    def test_returns_async_client(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        client = p._make_client()
        assert client is not None
        assert "Aura" in client.headers.get("user-agent", "")


class TestPopulate:
    @pytest.mark.asyncio
    async def test_abstract_populate(self) -> None:
        p = ConcretePopulator(conn=_memory_db())
        result = await p.populate()
        assert result == 0
