"""Testit LUKE opendata.luke.fi CKAN-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.ckan import CkanHarvester
from aura.harvesters.luke_opendata import LukeOpendataHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


SAMPLE_LUKE_DATASET = {
    "id": "luke-test-mvmi",
    "name": "mvmi-metsavarakartat",
    "title": "MVMI metsävarakartat",
    "title_translated": {"fi": "MVMI metsävarakartat"},
    "notes_translated": {"fi": "Monilähteisen metsien inventoinnin kartat"},
    "notes": "Multi-source national forest inventory maps",
    "keywords": {"fi": ["metsävarat", "MVMI"], "en": ["forest"]},
    "organization": {"id": "luke", "name": "luke", "title": "Luonnonvarakeskus"},
    "license_id": "cc-by-4.0",
    "license_title": "CC BY 4.0",
    "metadata_created": "2024-01-15T00:00:00",
    "metadata_modified": "2024-11-01T00:00:00",
    "num_resources": 2,
    "resources": [
        {
            "id": "res-luke-1",
            "name": "MVMI GeoTIFF",
            "format": "GeoTIFF",
            "url": "https://opendata.luke.fi/dataset/mvmi/resource/geotiff",
        },
        {
            "id": "res-luke-2",
            "name": "MVMI WMS",
            "format": "WMS",
            "url": "https://kartta.luke.fi/geoserver/MVMI/wms",
        },
    ],
}


def _mock_ckan_response(datasets: list[dict], total: int | None = None) -> dict:
    if total is None:
        total = len(datasets)
    return {"result": {"count": total, "results": datasets}}


class TestLukeOpendataConfig:
    """LUKE opendata -harvesterin konfiguraatio."""

    def test_inherits_ckan_harvester(self):
        assert issubclass(LukeOpendataHarvester, CkanHarvester)

    def test_config_values(self):
        h = LukeOpendataHarvester(conn=_memory_db())
        assert h.name == "luke-opendata"
        assert h.ckan_source == "luke-opendata"
        assert "opendata.luke.fi" in h.ckan_base_url
        assert h.url == "https://opendata.luke.fi"


class TestLukeOpendataHarvest:
    """LUKE opendata harvest()-testi."""

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """Harvest tallentaa datasetit tietokantaan oikealla source-arvolla."""
        conn = _memory_db()
        h = LukeOpendataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_LUKE_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 1
        row = conn.execute(
            "SELECT source FROM datasets WHERE id = 'luke-test-mvmi'"
        ).fetchone()
        assert row[0] == "luke-opendata"
