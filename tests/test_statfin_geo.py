"""Testit Tilastokeskuksen paikkatietoaineistojen harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.statfin_geo import GEOSERVER_BASE, StatfinGeoHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> StatfinGeoHarvester:
    return StatfinGeoHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_all_ids_have_prefix(self):
        """Kaikkien datasettien id:t alkavat 'statfin-geo-' -etuliitteellä."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("statfin-geo-")

    def test_all_datasets_have_wfs_and_wms(self):
        """Jokaisessa datasetissä on sekä WFS- että WMS-resurssi."""
        h = _harvester()
        for cfg in h.datasets_config:
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"WFS", "WMS"}, f"{cfg['id']}: {formats}"

    def test_urls_point_to_geoserver(self):
        """Resurssien URL:t osoittavat geo.stat.fi GeoServerille."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["url"].startswith(GEOSERVER_BASE), r["url"]

    def test_dataset_count(self):
        """Datasettejä on 9 kpl."""
        h = _harvester()
        assert len(h.datasets_config) == 9


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (9)."""
        h = _harvester()
        count = await h.harvest()
        assert count == 9

    @pytest.mark.asyncio
    async def test_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'statfin-geo'"
        ).fetchall()
        for ds in datasets:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()[0]
            assert ds["num_resources"] == actual
