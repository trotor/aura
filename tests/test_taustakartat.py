"""Testit taustakartat-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.taustakartat import TILE_SERVICES, TaustakartatHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> TaustakartatHarvester:
    return TaustakartatHarvester(conn=_memory_db())


class TestTileDataset:
    """Tiilipalveluiden datasetit."""

    def test_tms_format(self):
        """Resurssien formaatti on TMS."""
        h = _harvester()
        for svc in TILE_SERVICES:
            ds = h._tile_to_dataset(svc)
            assert ds.resources[0].format == "TMS"

    def test_url_template_contains_xyz(self):
        """URL-template sisältää {z}/{x}/{y} -muuttujat."""
        h = _harvester()
        for svc in TILE_SERVICES:
            ds = h._tile_to_dataset(svc)
            url = ds.resources[0].url
            assert "{z}" in url
            assert "{x}" in url
            assert "{y}" in url

    def test_osm_has_odbl_license(self):
        """OSM-tiilipalvelulla on ODbL-lisenssi."""
        h = _harvester()
        osm_svc = next(s for s in TILE_SERVICES if s["id"] == "osm-standard")
        ds = h._tile_to_dataset(osm_svc)
        assert ds.license_title == "ODbL"

    def test_kapsi_has_cc_by_license(self):
        """Kapsi-tiilipalvelulla on CC BY 4.0 -lisenssi."""
        h = _harvester()
        kapsi_svc = next(s for s in TILE_SERVICES if s["id"] == "kapsi-peruskartta")
        ds = h._tile_to_dataset(kapsi_svc)
        assert ds.license_title == "CC BY 4.0"

    def test_osm_coverage_is_global(self):
        """OSM-datasetin kattavuus on Maailma."""
        h = _harvester()
        osm_svc = next(s for s in TILE_SERVICES if s["id"] == "osm-standard")
        ds = h._tile_to_dataset(osm_svc)
        assert ds.geographical_coverage == ["Maailma"]

    def test_kapsi_coverage_is_finland(self):
        """Kapsi-datasetin kattavuus on Suomi."""
        h = _harvester()
        kapsi_svc = next(s for s in TILE_SERVICES if s["id"] == "kapsi-peruskartta")
        ds = h._tile_to_dataset(kapsi_svc)
        assert ds.geographical_coverage == ["Suomi"]


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (4)."""
        h = _harvester()
        count = await h.harvest()
        assert count == 4

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """harvest() tallentaa datasetit tietokantaan."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'taustakartat'"
        ).fetchone()
        assert rows[0] == 4
