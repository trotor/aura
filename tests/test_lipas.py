"""Testit LIPAS-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.lipas import LIPAS_BASE, LipasHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> LipasHarvester:
    return LipasHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("lipas-")

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == 3

    def test_urls_point_to_lipas(self):
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["url"].startswith(LIPAS_BASE), r["url"]

    def test_all_have_wfs_and_wms(self):
        h = _harvester()
        for cfg in h.datasets_config:
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"WFS", "WMS"}, cfg["id"]


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == 3

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'lipas'"
        ).fetchone()
        assert rows[0] == 3
