"""Testit GTK-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.gtk import (
    ARCGIS_BASE,
    WFS_SERVICES,
    WMS_SERVICES,
    GtkHarvester,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> GtkHarvester:
    return GtkHarvester(conn=_memory_db())


class TestWfsDataset:
    """WFS-palveluiden datasetit."""

    def test_wfs_dataset_has_wfs_and_wms_resources(self):
        """WFS-datasetissä on sekä WFS- että WMS-resurssi."""
        h = _harvester()
        svc = WFS_SERVICES[0]  # kalliopera
        ds = h._wfs_to_dataset(svc)

        wfs = [r for r in ds.resources if r.format == "WFS"]
        wms = [r for r in ds.resources if r.format == "WMS"]
        assert len(wfs) == 1
        assert len(wms) == 1

    def test_wfs_url_points_to_arcgis(self):
        """WFS-resurssin URL osoittaa GTK:n ArcGIS-palvelimelle."""
        h = _harvester()
        svc = WFS_SERVICES[0]
        ds = h._wfs_to_dataset(svc)

        wfs_resource = next(r for r in ds.resources if r.format == "WFS")
        assert wfs_resource.url.startswith(ARCGIS_BASE)

    def test_wfs_dataset_id_prefix(self):
        """WFS-datasetin id alkaa 'gtk-' -etuliitteellä."""
        h = _harvester()
        for svc in WFS_SERVICES:
            ds = h._wfs_to_dataset(svc)
            assert ds.id.startswith("gtk-")
            assert ds.source == "gtk"

    def test_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        for svc in WFS_SERVICES:
            ds = h._wfs_to_dataset(svc)
            assert ds.num_resources == len(ds.resources)


class TestWmsDataset:
    """WMS-only-palveluiden datasetit."""

    def test_wms_dataset_has_one_resource(self):
        """WMS-only-datasetissä on yksi resurssi."""
        h = _harvester()
        svc = WMS_SERVICES[0]  # geofysiikka
        ds = h._wms_to_dataset(svc)

        assert len(ds.resources) == 1
        assert ds.resources[0].format == "WMS"

    def test_wms_dataset_id_prefix(self):
        """WMS-datasetin id alkaa 'gtk-' -etuliitteellä."""
        h = _harvester()
        for svc in WMS_SERVICES:
            ds = h._wms_to_dataset(svc)
            assert ds.id.startswith("gtk-")


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (5)."""
        h = _harvester()
        count = await h.harvest()
        # 3 WFS + 2 WMS = 5
        assert count == 5

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """harvest() tallentaa datasetit tietokantaan."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'gtk'"
        ).fetchone()
        assert rows[0] == 5

    @pytest.mark.asyncio
    async def test_harvest_datasets_have_resources(self):
        """Jokaisella datasetillä on vähintään yksi resurssi."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id FROM datasets WHERE source = 'gtk'"
        ).fetchall()
        for ds in datasets:
            resources = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()
            assert resources[0] >= 1
