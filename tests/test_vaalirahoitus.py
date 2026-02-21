"""Testit vaalirahoitus-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.vaalirahoitus import VaalirahoitusHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> VaalirahoitusHarvester:
    return VaalirahoitusHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_election_datasets_exist(self):
        """Jokaiselle vaalille on datasetti."""
        h = _harvester()
        ids = [c["id"] for c in h.datasets_config]
        assert "vaalirahoitus-eduskuntavaalit2023" in ids
        assert "vaalirahoitus-kuntavaalit2025" in ids

    def test_party_datasets_exist(self):
        """Puoluerahoitukselle on vuosikohtaiset datasetit."""
        h = _harvester()
        ids = [c["id"] for c in h.datasets_config]
        assert "vaalirahoitus-puoluerahoitus-2010" in ids
        assert "vaalirahoitus-puoluerahoitus-2026" in ids

    def test_election_has_four_csv_resources(self):
        """Vaalirahoitusdatasetillä on 4 CSV-resurssia."""
        h = _harvester()
        cfg = next(
            c for c in h.datasets_config
            if c["id"] == "vaalirahoitus-eduskuntavaalit2023"
        )
        assert len(cfg["resources"]) == 4
        for r in cfg["resources"]:
            assert r["format"] == "CSV"

    def test_party_2024_has_one_resource(self):
        """Puoluerahoitus ennen 2025 — yksi CSV-resurssi."""
        h = _harvester()
        cfg = next(
            c for c in h.datasets_config
            if c["id"] == "vaalirahoitus-puoluerahoitus-2024"
        )
        assert len(cfg["resources"]) == 1

    def test_party_2025_has_loan_resource(self):
        """Puoluerahoitus 2025+ — myös lainatiedosto."""
        h = _harvester()
        cfg = next(
            c for c in h.datasets_config
            if c["id"] == "vaalirahoitus-puoluerahoitus-2025"
        )
        assert len(cfg["resources"]) == 2
        assert "lainat" in cfg["resources"][1]["url"]

    def test_csv_urls_are_valid(self):
        """CSV-resurssien URL:t osoittavat vaalirahoitusvalvonta.fi:hin."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["url"].startswith("https://www.vaalirahoitusvalvonta.fi")
                assert r["url"].endswith(".csv") or ".csv?" in r["url"]

    def test_org_is_vtv(self):
        """Organisaatio on VTV."""
        h = _harvester()
        assert h.org_title == "Valtiontalouden tarkastusvirasto"


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean lukumäärän."""
        h = _harvester()
        count = await h.harvest()
        # 10 vaalirahoitusta + 17 puoluerahoitusta = 27
        assert count == 27

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """Kaikki datasetit löytyvät tietokannasta harvestin jälkeen."""
        h = _harvester()
        await h.harvest()

        row = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'vaalirahoitus'"
        ).fetchone()
        assert row[0] == 27

    @pytest.mark.asyncio
    async def test_resources_in_db(self):
        """Resurssit kirjoittuvat kantaan."""
        h = _harvester()
        await h.harvest()

        row = h.conn.execute(
            """SELECT COUNT(*) FROM resources r
               JOIN datasets d ON r.dataset_id = d.id
               WHERE d.source = 'vaalirahoitus'"""
        ).fetchone()
        # 10 vaalirahoitusta × 4 + 15 puoluerahoitusta × 1 + 2 × 2 (2025,2026) = 59
        assert row[0] == 59
