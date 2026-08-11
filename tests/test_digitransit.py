"""Testit Digitransit-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.digitransit import (
    GTFS_FEEDS,
    ROUTERS,
    DigitransitHarvester,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> DigitransitHarvester:
    return DigitransitHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("digitransit-"), cfg["id"]

    def test_gtfs_feeds_have_required_fields(self):
        for feed in GTFS_FEEDS:
            assert "id" in feed
            assert "name" in feed
            assert "url" in feed
            assert "region" in feed
            assert "org" in feed

    def test_routers_defined(self):
        assert "finland" in ROUTERS
        assert "hsl" in ROUTERS
        assert "waltti" in ROUTERS

    def test_dataset_count(self):
        h = _harvester()
        # 4 routing + 1 geocoding + 3 GTFS-RT + len(GTFS_FEEDS)
        expected = 4 + 1 + 3 + len(GTFS_FEEDS)
        assert len(h.datasets_config) == expected

    def test_all_have_resources(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg["resources"]) > 0, cfg["id"]

    def test_gtfs_datasets_have_geographical_coverage(self):
        h = _harvester()
        for cfg in h.datasets_config:
            if cfg["id"].startswith("digitransit-gtfs-"):
                assert "geographical_coverage" in cfg, cfg["id"]


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        expected = 4 + 1 + 3 + len(GTFS_FEEDS)
        assert count == expected

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'digitransit'"
        ).fetchone()
        assert rows[0] == len(h.datasets_config)

    @pytest.mark.asyncio
    async def test_hsl_gtfs_in_db(self):
        h = _harvester()
        await h.harvest()
        row = h.conn.execute(
            "SELECT title FROM datasets WHERE id = 'digitransit-gtfs-hsl'"
        ).fetchone()
        assert row is not None
        assert "HSL" in row[0]

    @pytest.mark.asyncio
    async def test_routing_api_in_db(self):
        h = _harvester()
        await h.harvest()
        row = h.conn.execute(
            "SELECT title FROM datasets WHERE id = 'digitransit-routing-finland'"
        ).fetchone()
        assert row is not None
