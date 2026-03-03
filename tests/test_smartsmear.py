"""Testit SmartSMEAR-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.smartsmear import SmartSmearHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> SmartSmearHarvester:
    return SmartSmearHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("smartsmear-")

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == 7

    def test_realtime_update_frequency(self):
        h = _harvester()
        assert h.default_update_frequency == "reaaliaikainen"

    def test_each_dataset_has_two_resources(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg["resources"]) == 2
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"API", "HTML"}

    def test_each_dataset_has_geographical_coverage(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert "geographical_coverage" in cfg
            assert len(cfg["geographical_coverage"]) >= 1

    def test_station_ids(self):
        h = _harvester()
        ids = {cfg["id"] for cfg in h.datasets_config}
        expected = {
            "smartsmear-hyytiaelae",
            "smartsmear-vaerrioe",
            "smartsmear-kumpula",
            "smartsmear-kuopio",
            "smartsmear-siikaneva",
            "smartsmear-kuivajaervi",
            "smartsmear-qvidja",
        }
        assert ids == expected


class TestHarvest:
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
            "SELECT COUNT(*) FROM datasets WHERE source = 'smartsmear'"
        ).fetchone()
        assert rows[0] == 7

    @pytest.mark.asyncio
    async def test_hyytiala_has_pirkanmaa_coverage(self):
        h = _harvester()
        await h.harvest()
        row = h.conn.execute(
            "SELECT geographical_coverage FROM datasets WHERE id = 'smartsmear-hyytiaelae'"
        ).fetchone()
        assert row is not None
        assert "Pirkanmaa" in row[0]

    @pytest.mark.asyncio
    async def test_organization_set(self):
        h = _harvester()
        await h.harvest()
        row = h.conn.execute(
            "SELECT organization_title FROM datasets WHERE id = 'smartsmear-kumpula'"
        ).fetchone()
        assert row is not None
        assert "INAR" in row[0]
