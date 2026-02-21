"""Testit taustakartat-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.taustakartat import TaustakartatHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> TaustakartatHarvester:
    return TaustakartatHarvester(conn=_memory_db())


def _cfg(harvester: TaustakartatHarvester, dataset_id: str) -> dict:
    return next(c for c in harvester.datasets_config if c["id"] == dataset_id)


class TestConfig:
    """Konfiguraation rakenne."""

    def test_tms_format(self):
        """Kaikki resurssit ovat TMS-formaatissa."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["format"] == "TMS"

    def test_url_template_contains_xyz(self):
        """URL-template sisältää {z}/{x}/{y} -muuttujat."""
        h = _harvester()
        for cfg in h.datasets_config:
            url = cfg["resources"][0]["url"]
            assert "{z}" in url
            assert "{x}" in url
            assert "{y}" in url

    def test_osm_has_odbl_license(self):
        """OSM-tiilipalvelulla on ODbL-lisenssi."""
        cfg = _cfg(_harvester(), "taustakartat-osm-standard")
        assert cfg["license_title"] == "ODbL"

    def test_osm_coverage_is_global(self):
        """OSM-datasetin kattavuus on Maailma."""
        cfg = _cfg(_harvester(), "taustakartat-osm-standard")
        assert cfg["geographical_coverage"] == ["Maailma"]


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (4)."""
        h = _harvester()
        count = await h.harvest()
        assert count == 4

    @pytest.mark.asyncio
    async def test_osm_gets_odbl_in_db(self):
        """OSM-datasetti saa ODbL-lisenssin tietokantaan."""
        h = _harvester()
        await h.harvest()

        row = h.conn.execute(
            "SELECT license_title FROM datasets WHERE id = 'taustakartat-osm-standard'"
        ).fetchone()
        assert row["license_title"] == "ODbL"

    @pytest.mark.asyncio
    async def test_kapsi_gets_cc_by_in_db(self):
        """Kapsi-datasetti saa CC BY 4.0 -lisenssin tietokantaan."""
        h = _harvester()
        await h.harvest()

        row = h.conn.execute(
            "SELECT license_title FROM datasets WHERE id = 'taustakartat-kapsi-peruskartta'"
        ).fetchone()
        assert row["license_title"] == "CC BY 4.0"
