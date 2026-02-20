"""Testit PxWebHarvester-kantaluokalle."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from aura.database import init_db
from aura.harvesters.luke import LukeHarvester
from aura.harvesters.pxweb import PxWebHarvester
from aura.harvesters.statfin import StatfinHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


SAMPLE_FOLDER_ITEMS = [
    {"id": "alue", "type": "l", "text": "Alue"},
    {"id": "testi.px", "type": "t", "text": "Testitaulu", "updated": "2024-01-15T12:00:00"},
]

SAMPLE_SUBFOLDER_ITEMS = [
    {"id": "data.px", "type": "t", "text": "Aluetaulu", "updated": "2024-02-01T10:00:00"},
]


class TestPxWebConfig:
    """PxWebHarvester-konfiguraation testit."""

    def test_statfin_inherits_pxweb(self):
        assert issubclass(StatfinHarvester, PxWebHarvester)

    def test_luke_inherits_pxweb(self):
        assert issubclass(LukeHarvester, PxWebHarvester)

    def test_statfin_config(self):
        h = StatfinHarvester(conn=_memory_db())
        assert h.name == "statfin"
        assert h.root_path == "StatFin"
        assert h.dataset_id_prefix == "statfin"
        assert "statfin.stat.fi" in h.pxweb_base_url

    def test_luke_config(self):
        h = LukeHarvester(conn=_memory_db())
        assert h.name == "luke"
        assert h.root_path == "LUKE"
        assert h.dataset_id_prefix == "luke"
        assert "statdb.luke.fi" in h.pxweb_base_url


class TestTableToDataset:
    """_table_to_dataset()-metodin testit."""

    def test_dataset_id_has_prefix(self):
        h = StatfinHarvester(conn=_memory_db())
        item = {"id": "testi.px", "text": "Testitaulu", "updated": "2024-01-01"}
        ds = h._table_to_dataset(item, "StatFin/alue", "https://example.com/api/")
        assert ds.id == "statfin-testi.px"

    def test_luke_dataset_id_has_prefix(self):
        h = LukeHarvester(conn=_memory_db())
        item = {"id": "data.px", "text": "Datataulu", "updated": "2024-01-01"}
        ds = h._table_to_dataset(item, "LUKE/metsa", "https://example.com/api/")
        assert ds.id == "luke-data.px"

    def test_dataset_has_two_resources(self):
        h = StatfinHarvester(conn=_memory_db())
        item = {"id": "testi.px", "text": "Taulu", "updated": ""}
        ds = h._table_to_dataset(item, "StatFin", "https://example.com/")
        assert len(ds.resources) == 2
        assert ds.resources[0].format == "PXWEB"
        assert ds.resources[1].format == "HTML"

    def test_dataset_source_matches_harvester(self):
        h = LukeHarvester(conn=_memory_db())
        item = {"id": "test.px", "text": "Test", "updated": ""}
        ds = h._table_to_dataset(item, "LUKE", "https://example.com/")
        assert ds.source == "luke"

    def test_dataset_organization(self):
        h = StatfinHarvester(conn=_memory_db())
        item = {"id": "test.px", "text": "Test", "updated": ""}
        ds = h._table_to_dataset(item, "StatFin", "https://example.com/")
        assert ds.organization_id == "tilastokeskus"
        assert ds.organization_title == "Tilastokeskus"


class TestPathToKeywords:
    """_path_to_keywords()-metodin testit."""

    def test_filters_root_path(self):
        h = StatfinHarvester(conn=_memory_db())
        assert h._path_to_keywords("StatFin") == []

    def test_extracts_subfolders(self):
        h = StatfinHarvester(conn=_memory_db())
        assert h._path_to_keywords("StatFin/vaesto/synt") == ["vaesto", "synt"]

    def test_luke_filters_root(self):
        h = LukeHarvester(conn=_memory_db())
        assert h._path_to_keywords("LUKE/metsa") == ["metsa"]


class TestCrawl:
    """_crawl_folder()-metodin testit."""

    @pytest.mark.asyncio
    async def test_crawl_tables_only(self):
        """Taulu-itemit (type=t) tallennetaan tietokantaan."""
        conn = _memory_db()
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "testi.px", "type": "t", "text": "Taulu", "updated": "2024-01-01"},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        count = await h._crawl_folder(mock_client, "https://example.com/", "StatFin")
        assert count == 1

        row = conn.execute("SELECT COUNT(*) FROM datasets WHERE source = 'statfin'").fetchone()
        assert row[0] == 1

    @pytest.mark.asyncio
    async def test_crawl_handles_error(self):
        """Virheelliset kansiot ohitetaan."""
        conn = _memory_db()
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("HTTP 400"))

        count = await h._crawl_folder(mock_client, "https://example.com/bad/", "StatFin")
        assert count == 0
