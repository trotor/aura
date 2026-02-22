"""Testit MML-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.mml import MML_BASE, MmlHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> MmlHarvester:
    return MmlHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("mml-")

    def test_all_datasets_have_resources(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg["resources"]) >= 1, cfg["id"]

    def test_urls_point_to_mml(self):
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert "maanmittauslaitos.fi" in r["url"], r["url"]

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == 7

    def test_all_datasets_require_registration(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg.get("access_level") == "registration", cfg["id"]


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == 7

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'mml'"
        ).fetchone()
        assert rows[0] == 7

    @pytest.mark.asyncio
    async def test_resources_saved(self):
        h = _harvester()
        await h.harvest()
        for cfg in h.datasets_config:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (cfg["id"],),
            ).fetchone()[0]
            assert actual == len(cfg["resources"])
