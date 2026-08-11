"""Testit Finap/NAP-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.finap import NAP_CATEGORIES, FinapHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> FinapHarvester:
    return FinapHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("finap-"), cfg["id"]

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == len(NAP_CATEGORIES)

    def test_all_have_resources(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg["resources"]) > 0, cfg["id"]

    def test_categories_cover_five_types(self):
        ids = {cat["id"] for cat in NAP_CATEGORIES}
        assert "finap-henkiloliikenne" in ids
        assert "finap-terminaalit" in ids
        assert "finap-pysakointi" in ids
        assert "finap-vuokraus-jakaminen" in ids
        assert "finap-valityspalvelut" in ids


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == len(NAP_CATEGORIES)

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'finap'"
        ).fetchone()
        assert rows[0] == len(NAP_CATEGORIES)
