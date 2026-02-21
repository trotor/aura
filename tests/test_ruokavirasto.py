"""Testit Ruokavirasto-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.ruokavirasto import RuokavirastoHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> RuokavirastoHarvester:
    return RuokavirastoHarvester(conn=_memory_db())


class TestInspireConfig:
    """INSPIRE-paikkatietojen konfiguraatio."""

    def test_inspire_has_three_resource_formats(self):
        """INSPIRE-konfiguraatiossa on WMS, WFS ja GPKG."""
        h = _harvester()
        inspire = [c for c in h.datasets_config if "years" in c]
        assert len(inspire) == 4
        for cfg in inspire:
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"WMS", "WFS", "GPKG"}

    def test_inspire_total_count(self):
        """INSPIRE-datasettien kokonaismäärä on tyyppit x vuodet."""
        h = _harvester()
        inspire = [c for c in h.datasets_config if "years" in c]
        # 4 tyyppiä x 5 vuotta = 20
        total = sum(len(list(c["years"])) for c in inspire)
        assert total == 20


class TestDashboardConfig:
    """Avoin tieto -dashboardien konfiguraatio."""

    def test_dashboards_have_html(self):
        """Dashboard-konfiguraatioissa on HTML-resurssi."""
        h = _harvester()
        dashboards = [
            c for c in h.datasets_config
            if any(r["format"] == "HTML" for r in c["resources"])
            and c.get("access_level") == "open"
        ]
        assert len(dashboards) == 5
        for cfg in dashboards:
            assert "avointieto.ruokavirasto.fi" in cfg["resources"][0]["url"]


class TestRestrictedConfig:
    """Rajoitettujen rajapintojen konfiguraatio."""

    def test_restricted_access_level(self):
        """Rajoitetut konfiguraatiot saavat access_level='restricted'."""
        h = _harvester()
        restricted = [c for c in h.datasets_config if c.get("access_level") == "restricted"]
        assert len(restricted) == 8
        for cfg in restricted:
            assert cfg["license_id"] == ""
            assert len(cfg["resources"]) == 1
            assert cfg["resources"][0]["format"] == "API"


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (33)."""
        h = _harvester()
        count = await h.harvest()
        # 4 tyyppiä x 5 vuotta + 5 dashboardia + 8 rajoitettua = 33
        assert count == 33

    @pytest.mark.asyncio
    async def test_harvest_restricted_in_db(self):
        """Rajoitetut datasetit tallentuvat access_level='restricted'-arvolla."""
        h = _harvester()
        await h.harvest()

        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets"
            " WHERE source = 'ruokavirasto' AND access_level = 'restricted'"
        ).fetchone()
        assert rows[0] == 8

    @pytest.mark.asyncio
    async def test_inspire_id_contains_year(self):
        """INSPIRE-datasettien id:t sisältävät vuoden."""
        h = _harvester()
        await h.harvest()

        inspire = h.conn.execute(
            "SELECT id FROM datasets"
            " WHERE source = 'ruokavirasto' AND id LIKE 'ruokavirasto-peltolohkorekisteri-%'"
        ).fetchall()
        assert len(inspire) == 5
        years_found = {row["id"].split("-")[-1] for row in inspire}
        assert years_found == {"2020", "2021", "2022", "2023", "2024"}
