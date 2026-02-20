"""Testit SYKE-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.ckan import CkanHarvester
from aura.harvesters.syke import SykeHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


SAMPLE_SYKE_DATASET = {
    "id": "syke-test-1",
    "name": "pohjavesialueet",
    "title": "Pohjavesialueet",
    "title_translated": {"fi": "Pohjavesialueet", "en": "Groundwater areas"},
    "notes_translated": {"fi": "Suomen pohjavesialueet"},
    "notes": "Groundwater areas in Finland",
    "keywords": {"fi": ["pohjavesi", "ympäristö"], "en": ["groundwater"]},
    "organization": {"id": "syke", "name": "syke", "title": "SYKE"},
    "license_id": "cc-by-4.0",
    "license_title": "CC BY 4.0",
    "metadata_created": "2024-01-01T00:00:00",
    "metadata_modified": "2024-06-01T00:00:00",
    "num_resources": 1,
    "resources": [
        {
            "id": "res-syke-1",
            "name": "pohjavesialueet.shp",
            "format": "SHP",
            "url": "https://ckan.ymparisto.fi/dataset/pohjavesialueet/resource/pohjavesialueet.shp",
        }
    ],
}


def _mock_ckan_response(datasets: list[dict], total: int | None = None) -> dict:
    if total is None:
        total = len(datasets)
    return {"result": {"count": total, "results": datasets}}


class TestSykeConfig:
    """SYKE-harvesterin konfiguraatio."""

    def test_inherits_ckan_harvester(self):
        assert issubclass(SykeHarvester, CkanHarvester)

    def test_config_values(self):
        h = SykeHarvester(conn=_memory_db())
        assert h.name == "syke"
        assert h.ckan_source == "syke"
        assert "ymparisto.fi" in h.ckan_base_url
        assert h.url == "https://ckan.ymparisto.fi"


class TestSykeHarvest:
    """SYKE-harvesterin harvest()-testi."""

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """Harvest tallentaa datasetit tietokantaan oikealla source-arvolla."""
        conn = _memory_db()
        h = SykeHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_SYKE_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 1
        row = conn.execute(
            "SELECT source FROM datasets WHERE id = 'syke-test-1'"
        ).fetchone()
        assert row[0] == "syke"
