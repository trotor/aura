"""Testit Väylävirasto-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.vayla import VAYLA_BASE, VaylaHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> VaylaHarvester:
    return VaylaHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("vayla-")

    def test_urls_point_to_vayla(self):
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["url"].startswith(VAYLA_BASE), r["url"]

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == 5

    def test_all_have_wfs_and_wms(self):
        h = _harvester()
        for cfg in h.datasets_config:
            formats = {r["format"] for r in cfg["resources"]}
            assert "WFS" in formats, cfg["id"]
            assert "WMS" in formats, cfg["id"]


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == 5

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'vayla'"
        ).fetchone()
        assert rows[0] == 5
