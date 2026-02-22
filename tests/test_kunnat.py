"""Testit kuntien paikkatietoharvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.kunnat import KunnatHarvester

EXPECTED_COUNT = 36


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
        """36 kuntaa: 23 alkuperäistä + 13 uutta."""
        h = _harvester()
        assert len(h.datasets_config) == EXPECTED_COUNT

    def test_each_has_organization_title(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert "organization_title" in cfg, cfg["id"]

    def test_each_has_geographical_coverage(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert "geographical_coverage" in cfg, f"{cfg['id']} puuttuu geographical_coverage"
            assert len(cfg["geographical_coverage"]) >= 1

    def test_cities_covered(self):
        h = _harvester()
        titles = [cfg["title"] for cfg in h.datasets_config]
        for city in [
            "Helsinki", "Espoo", "Vantaa", "Tampere", "Turku", "Oulu",
            "Kuopio", "Jyväskylä", "Lahti", "Pori", "Kouvola", "Joensuu",
            "Lappeenranta", "Hämeenlinna", "Seinäjoki", "Rovaniemi",
            "Mikkeli", "Kotka", "Salo", "Kokkola", "Hyvinkää", "Rauma",
            "Kajaani", "Kauniainen", "Nurmijärvi", "Tuusula", "Vihti",
            "Naantali", "Raisio", "Kangasala", "Nokia", "Ylöjärvi",
            "Lempäälä", "Pirkkala", "Hämeenkyrö", "Orivesi",
        ]:
            assert any(city in t for t in titles), f"{city} puuttuu"

    def test_unique_ids(self):
        h = _harvester()
        ids = [cfg["id"] for cfg in h.datasets_config]
        assert len(ids) == len(set(ids)), "Duplikaatti-ID:itä löytyi"


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == EXPECTED_COUNT

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'kunnat'"
        ).fetchone()
        assert rows[0] == EXPECTED_COUNT

    @pytest.mark.asyncio
    async def test_different_organizations(self):
        """Jokaisella kunnalla on oma organisaatio."""
        h = _harvester()
        await h.harvest()
        orgs = h.conn.execute(
            "SELECT DISTINCT organization_title FROM datasets WHERE source = 'kunnat'"
        ).fetchall()
        assert len(orgs) == EXPECTED_COUNT

    @pytest.mark.asyncio
    async def test_geographical_coverage_stored(self):
        """geographical_coverage tallennetaan tietokantaan."""
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT geographical_coverage FROM datasets "
            "WHERE source = 'kunnat' AND geographical_coverage != '[]'"
        ).fetchall()
        assert len(rows) == EXPECTED_COUNT
