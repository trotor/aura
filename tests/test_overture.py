"""Testit Overture Maps -harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.overture import OvertureHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> OvertureHarvester:
    return OvertureHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_geoparquet_format(self):
        """Kaikki resurssit ovat GeoParquet-formaatissa."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["format"] == "GeoParquet"

    def test_two_resources_per_theme(self):
        """Jokaisella teemalla on 2 resurssia (S3 + HTTPS)."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg["resources"]) == 2
            assert cfg["resources"][0]["url"].startswith("s3://")
            assert cfg["resources"][1]["url"].startswith("https://")

    def test_odbl_license(self):
        """Kaikki datasetit käyttävät ODbL-lisenssiä."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["license_title"] == "ODbL"


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (6)."""
        h = _harvester()
        count = await h.harvest()
        assert count == 6
