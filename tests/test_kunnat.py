"""Testit kuntien paikkatietoharvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.kunnat import KunnatHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> KunnatHarvester:
    return KunnatHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("kunnat-")

    def test_dataset_count(self):
        """6 kaupunkia: Helsinki, Espoo, Vantaa, Tampere, Turku, Oulu."""
        h = _harvester()
        assert len(h.datasets_config) == 6

    def test_each_has_organization_title(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert "organization_title" in cfg, cfg["id"]

    def test_cities_covered(self):
        h = _harvester()
        titles = [cfg["title"] for cfg in h.datasets_config]
        for city in ["Helsinki", "Espoo", "Vantaa", "Tampere", "Turku", "Oulu"]:
            assert any(city in t for t in titles), f"{city} puuttuu"


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == 6

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'kunnat'"
        ).fetchone()
        assert rows[0] == 6

    @pytest.mark.asyncio
    async def test_different_organizations(self):
        """Jokaisella kaupungilla on oma organisaatio."""
        h = _harvester()
        await h.harvest()
        orgs = h.conn.execute(
            "SELECT DISTINCT organization_title FROM datasets WHERE source = 'kunnat'"
        ).fetchall()
        assert len(orgs) == 6
