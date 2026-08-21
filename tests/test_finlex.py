"""Testit Finlex-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters import HARVESTERS
from aura.harvesters.finlex import API, OHJE, FinlexHarvester
from aura.harvesters.static import StaticHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestConfig:
    def test_inherits_static(self):
        assert issubclass(FinlexHarvester, StaticHarvester)

    def test_registered(self):
        assert HARVESTERS["finlex"] is FinlexHarvester

    def test_five_verified_collections(self):
        """Vain varmennetut list-päätteet.

        Oikeuskäytännön tyyppinimiä ei löytynyt OpenAPI-kuvauksesta eikä
        ohjesivuilta. Kuollut osoite katalogissa on pahempi kuin puuttuva
        rivi, joten niitä ei arvata mukaan.
        """
        assert len(FinlexHarvester.datasets_config) == 5

    def test_every_dataset_has_a_queryable_api_resource(self):
        """Vanha rivi oli kirjanmerkki: ei formaattia, pelkkä juuriosoite.

        Sen takia query_data ei voinut tehdä sille mitään.
        """
        for cfg in FinlexHarvester.datasets_config:
            api = [r for r in cfg["resources"] if r["format"] == "JSON"]
            assert len(api) == 1, cfg["id"]
            assert api[0]["url"].startswith(API)
            assert api[0]["url"].endswith("/list")

    def test_every_dataset_links_to_the_web_service(self):
        for cfg in FinlexHarvester.datasets_config:
            assert any(r["format"] == "HTML" for r in cfg["resources"]), cfg["id"]

    def test_usage_instructions_are_in_every_description(self):
        """describe():n pitää osata opastaa käyttöön ilman ulkoista ohjetta."""
        for cfg in FinlexHarvester.datasets_config:
            assert "titleContains" in cfg["notes_fi"], cfg["id"]
            assert "User-Agent" in cfg["notes_fi"], cfg["id"]

    def test_instructions_mention_the_paging_ceiling(self):
        """limit on enintään 10 — ilman tätä tietoa agentti yrittää enemmän."""
        assert "enintään 10" in OHJE

    def test_resource_ids_are_unique(self):
        ids = [r["id"] for cfg in FinlexHarvester.datasets_config
               for r in cfg["resources"]]
        assert len(ids) == len(set(ids))


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_writes_all_collections(self):
        conn = _memory_db()
        count = await FinlexHarvester(conn=conn).harvest()
        assert count == 5
        stored = conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'finlex'"
        ).fetchone()[0]
        assert stored == 5

    @pytest.mark.asyncio
    async def test_publisher_is_the_ministry(self):
        conn = _memory_db()
        await FinlexHarvester(conn=conn).harvest()
        rows = conn.execute(
            "SELECT DISTINCT organization_title FROM datasets WHERE source = 'finlex'"
        ).fetchall()
        assert [r[0] for r in rows] == ["Oikeusministeriö"]
