"""Testit Lajitietokeskus-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.lajitietokeskus import LajitietokeskusHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> LajitietokeskusHarvester:
    return LajitietokeskusHarvester(conn=_memory_db())


class TestConfig:
    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("lajifi-"), f"ID {cfg['id']} ei ala 'lajifi-'"

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == 11

    def test_all_have_resources(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg.get("resources", [])) > 0, (
                f"Datasetti {cfg['id']} ilman resursseja"
            )

    def test_all_have_keywords(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg.get("keywords_fi", [])) > 0, (
                f"Datasetti {cfg['id']} ilman avainsanoja"
            )

    def test_org_info(self):
        h = _harvester()
        assert h.org_id == "lajitietokeskus"
        assert "Luomus" in h.org_title

    def test_api_datasets_noted_as_registration(self):
        """REST API datasetti pitää olla merkitty rekisteröitymistä vaativaksi."""
        h = _harvester()
        api_cfg = next(c for c in h.datasets_config if c["id"] == "lajifi-rest-api")
        assert api_cfg.get("access_level") == "registration"


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == 11

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'lajitietokeskus'"
        ).fetchone()
        assert rows[0] == 11

    @pytest.mark.asyncio
    async def test_resources_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM resources r JOIN datasets d ON r.dataset_id = d.id "
            "WHERE d.source = 'lajitietokeskus'"
        ).fetchone()
        assert rows[0] > 11  # Most datasets have multiple resources
