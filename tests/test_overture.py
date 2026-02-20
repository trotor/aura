"""Testit Overture Maps -harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.overture import THEMES, OvertureHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> OvertureHarvester:
    return OvertureHarvester(conn=_memory_db())


class TestThemeDataset:
    """Teema-datasettien rakenne."""

    def test_geoparquet_format(self):
        """Resurssien formaatti on GeoParquet."""
        h = _harvester()
        for theme in THEMES:
            ds = h._theme_to_dataset(theme)
            for r in ds.resources:
                assert r.format == "GeoParquet"

    def test_two_resources_per_theme(self):
        """Jokaisella teemalla on 2 resurssia (S3 + HTTPS)."""
        h = _harvester()
        for theme in THEMES:
            ds = h._theme_to_dataset(theme)
            assert len(ds.resources) == 2
            assert ds.num_resources == 2

    def test_s3_url(self):
        """Ensimmäinen resurssi on S3 GeoParquet."""
        h = _harvester()
        ds = h._theme_to_dataset(THEMES[0])
        assert ds.resources[0].url.startswith("s3://")

    def test_https_url(self):
        """Toinen resurssi on source.coop HTTPS."""
        h = _harvester()
        ds = h._theme_to_dataset(THEMES[0])
        assert ds.resources[1].url.startswith("https://")

    def test_odbl_license(self):
        """Kaikki datasetit käyttävät ODbL-lisenssiä."""
        h = _harvester()
        for theme in THEMES:
            ds = h._theme_to_dataset(theme)
            assert ds.license_title == "ODbL"

    def test_global_coverage(self):
        """Kaikki datasetit kattavat koko maailman."""
        h = _harvester()
        for theme in THEMES:
            ds = h._theme_to_dataset(theme)
            assert ds.geographical_coverage == ["Maailma"]

    def test_dataset_id_prefix(self):
        """Datasetin id alkaa 'overture-' -etuliitteellä."""
        h = _harvester()
        for theme in THEMES:
            ds = h._theme_to_dataset(theme)
            assert ds.id.startswith("overture-")
            assert ds.source == "overture"


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (6)."""
        h = _harvester()
        count = await h.harvest()
        assert count == 6

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """harvest() tallentaa datasetit tietokantaan."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'overture'"
        ).fetchone()
        assert rows[0] == 6

    @pytest.mark.asyncio
    async def test_harvest_datasets_have_resources(self):
        """Jokaisella datasetillä on 2 resurssia."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id FROM datasets WHERE source = 'overture'"
        ).fetchall()
        for ds in datasets:
            resources = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()
            assert resources[0] == 2
