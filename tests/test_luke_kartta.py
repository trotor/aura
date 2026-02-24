"""Testit LUKE kartta.luke.fi GeoServer-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.luke_kartta import (
    GEOSERVER,
    INSPIRE_WFS,
    LUKE_WMS,
    MVMI_WMS,
    LukeKarttaHarvester,
)
from aura.harvesters.static import StaticHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> LukeKarttaHarvester:
    return LukeKarttaHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_inherits_static_harvester(self):
        assert issubclass(LukeKarttaHarvester, StaticHarvester)

    def test_config_values(self):
        h = _harvester()
        assert h.name == "luke-kartta"
        assert h.org_id == "luke"
        assert "kartta.luke.fi" in h.url

    def test_all_ids_have_prefix(self):
        """Kaikkien datasettien id:t alkavat 'luke-kartta-' -etuliitteellä."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("luke-kartta-"), cfg["id"]

    def test_dataset_count(self):
        """Datasettejä on 10 kappaletta."""
        h = _harvester()
        assert len(h.datasets_config) == 10

    def test_urls_point_to_geoserver(self):
        """Resurssien URL:t osoittavat kartta.luke.fi GeoServerille."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert "kartta.luke.fi" in r["url"], f"{cfg['id']}: {r['url']}"

    def test_wfs_datasets(self):
        """WFS-datasettejä on 2 kappaletta (INSPIRE-lajisto ja kalat)."""
        h = _harvester()
        wfs = [
            c for c in h.datasets_config
            if any(r["format"] == "WFS" for r in c["resources"])
        ]
        assert len(wfs) == 2

    def test_mvmi_has_two_resources(self):
        """MVMI-datasetillä on WMS ja GeoTIFF."""
        h = _harvester()
        mvmi = next(c for c in h.datasets_config if c["id"] == "luke-kartta-mvmi")
        formats = {r["format"] for r in mvmi["resources"]}
        assert formats == {"WMS", "GeoTIFF"}

    def test_all_have_geographical_coverage(self):
        """Kaikilla dataseteillä on maantieteellinen kattavuus."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert "geographical_coverage" in cfg
            assert "Suomi" in cfg["geographical_coverage"]

    def test_all_have_keywords(self):
        """Kaikilla dataseteillä on avainsanoja."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert "keywords_fi" in cfg
            assert len(cfg["keywords_fi"]) > 0


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän."""
        h = _harvester()
        count = await h.harvest()
        assert count == 10

    @pytest.mark.asyncio
    async def test_harvest_source_is_correct(self):
        """Harvestoidut datasetit saavat oikean source-arvon."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT DISTINCT source FROM datasets WHERE source = 'luke-kartta'"
        ).fetchall()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'luke-kartta'"
        ).fetchall()
        for ds in datasets:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()[0]
            assert ds["num_resources"] == actual

    @pytest.mark.asyncio
    async def test_org_title_is_luke(self):
        """Organisaation nimi on Luonnonvarakeskus."""
        h = _harvester()
        await h.harvest()

        row = h.conn.execute(
            "SELECT organization_title FROM datasets WHERE source = 'luke-kartta' LIMIT 1"
        ).fetchone()
        assert "Luonnonvarakeskus" in row[0]
