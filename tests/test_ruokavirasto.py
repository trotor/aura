"""Testit Ruokavirasto-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.ruokavirasto import (
    DASHBOARDS,
    INSPIRE_TYPES,
    INSPIRE_YEARS,
    RESTRICTED_SERVICES,
    RuokavirastoHarvester,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> RuokavirastoHarvester:
    return RuokavirastoHarvester(conn=_memory_db())


class TestInspireDatasets:
    """INSPIRE-paikkatietojen datasetit."""

    def test_inspire_dataset_has_three_resources(self):
        """INSPIRE-datasetissä on WMS, WFS ja GPKG."""
        h = _harvester()
        ds = h._inspire_to_dataset(INSPIRE_TYPES[0], 2024)

        formats = {r.format for r in ds.resources}
        assert formats == {"WMS", "WFS", "GPKG"}
        assert len(ds.resources) == 3

    def test_inspire_dataset_id_contains_year(self):
        """INSPIRE-datasetin id sisältää vuoden."""
        h = _harvester()
        ds = h._inspire_to_dataset(INSPIRE_TYPES[0], 2023)
        assert "2023" in ds.id
        assert ds.id.startswith("ruokavirasto-")

    def test_inspire_dataset_is_open(self):
        """INSPIRE-datasetit ovat avoimia."""
        h = _harvester()
        ds = h._inspire_to_dataset(INSPIRE_TYPES[0], 2024)
        assert ds.access_level == "open"

    def test_inspire_total_count(self):
        """INSPIRE-datasettien kokonaismäärä on tyyppit × vuodet."""
        expected = len(INSPIRE_TYPES) * len(INSPIRE_YEARS)
        assert expected == 20


class TestDashboardDatasets:
    """Avoin tieto -dashboardien datasetit."""

    def test_dashboard_has_html_resource(self):
        """Dashboard-datasetissä on HTML-resurssi."""
        h = _harvester()
        ds = h._dashboard_to_dataset(DASHBOARDS[0])

        assert len(ds.resources) == 1
        assert ds.resources[0].format == "HTML"

    def test_dashboard_url_points_to_avointieto(self):
        """Dashboard-resurssin URL osoittaa avointieto-sivustolle."""
        h = _harvester()
        ds = h._dashboard_to_dataset(DASHBOARDS[0])

        assert "avointieto.ruokavirasto.fi" in ds.resources[0].url

    def test_dashboard_is_open(self):
        """Dashboard-datasetit ovat avoimia."""
        h = _harvester()
        for dash in DASHBOARDS:
            ds = h._dashboard_to_dataset(dash)
            assert ds.access_level == "open"


class TestRestrictedDatasets:
    """Rajoitettujen rajapintojen datasetit."""

    def test_restricted_access_level(self):
        """Rajoitetut datasetit saavat access_level='restricted'."""
        h = _harvester()
        for svc in RESTRICTED_SERVICES:
            ds = h._restricted_to_dataset(svc)
            assert ds.access_level == "restricted"

    def test_restricted_has_api_resource(self):
        """Rajoitetussa datasetissä on API-resurssi."""
        h = _harvester()
        ds = h._restricted_to_dataset(RESTRICTED_SERVICES[0])

        assert len(ds.resources) == 1
        assert ds.resources[0].format == "API"

    def test_restricted_no_open_license(self):
        """Rajoitetuilla dataseteillä ei ole avointa lisenssiä."""
        h = _harvester()
        ds = h._restricted_to_dataset(RESTRICTED_SERVICES[0])
        assert ds.license_id == ""


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (33)."""
        h = _harvester()
        count = await h.harvest()
        # 4 tyyppiä × 5 vuotta + 5 dashboardia + 8 rajoitettua = 33
        assert count == 33

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """harvest() tallentaa datasetit tietokantaan."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'ruokavirasto'"
        ).fetchone()
        assert rows[0] == 33

    @pytest.mark.asyncio
    async def test_harvest_datasets_have_resources(self):
        """Jokaisella datasetillä on vähintään yksi resurssi."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id FROM datasets WHERE source = 'ruokavirasto'"
        ).fetchall()
        for ds in datasets:
            resources = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()
            assert resources[0] >= 1

    @pytest.mark.asyncio
    async def test_harvest_restricted_in_db(self):
        """Rajoitetut datasetit tallentuvat access_level='restricted'-arvolla."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets"
            " WHERE source = 'ruokavirasto' AND access_level = 'restricted'"
        ).fetchone()
        assert rows[0] == len(RESTRICTED_SERVICES)
