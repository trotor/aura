"""Testit FMI-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.fmi import FmiHarvester

MOCK_WFS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:ListStoredQueriesResponse
    xmlns:wfs="http://www.opengis.net/wfs/2.0">
    <wfs:StoredQuery id="fmi::observations::weather::simple">
        <wfs:Title>Säähavainnot (yksinkertainen)</wfs:Title>
        <wfs:Abstract>Palauttaa yksinkertaiset säähavainnot</wfs:Abstract>
    </wfs:StoredQuery>
    <wfs:StoredQuery id="fmi::forecast::hirlam::surface::point::simple">
        <wfs:Title>HIRLAM-ennuste</wfs:Title>
        <wfs:Abstract>Pintalämpötilan ennuste</wfs:Abstract>
    </wfs:StoredQuery>
    <wfs:StoredQuery id="fmi::radar::composite::dbz">
        <wfs:Title>Tutkakuva</wfs:Title>
    </wfs:StoredQuery>
</wfs:ListStoredQueriesResponse>
"""


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestFmiHarvest:
    """FmiHarvester.harvest()-testit."""

    @pytest.mark.asyncio
    async def test_harvest_parses_stored_queries(self) -> None:
        """XML-vastaus parsitaan oikein."""
        conn = _memory_db()
        h = FmiHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.text = MOCK_WFS_XML
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 3

    @pytest.mark.asyncio
    async def test_datasets_written_to_db(self) -> None:
        conn = _memory_db()
        h = FmiHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.text = MOCK_WFS_XML
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'fmi'"
        ).fetchone()
        assert row[0] == 3


class TestQueryToDataset:
    """_query_to_dataset()-metodin testit."""

    def test_dataset_id_prefix(self) -> None:
        h = FmiHarvester(conn=_memory_db())
        ds = h._query_to_dataset("fmi::test::query", "Testikysely", "Kuvaus")
        assert ds.id == "fmi-fmi::test::query"
        assert ds.source == "fmi"

    def test_wfs_resource(self) -> None:
        h = FmiHarvester(conn=_memory_db())
        ds = h._query_to_dataset("test", "Test", "")
        assert len(ds.resources) == 1
        assert ds.resources[0].format == "WFS"
        assert "storedquery_id=test" in ds.resources[0].url

    def test_radar_size_estimate(self) -> None:
        """Tutkadata saa isomman kokoarvion."""
        h = FmiHarvester(conn=_memory_db())
        ds = h._query_to_dataset("fmi::radar::test", "Tutka", "")
        assert ds.estimated_size_bytes == 500_000_000

    def test_forecast_size_estimate(self) -> None:
        h = FmiHarvester(conn=_memory_db())
        ds = h._query_to_dataset("fmi::forecast::test", "Ennuste", "")
        assert ds.estimated_size_bytes == 100_000_000

    def test_category_keywords(self) -> None:
        h = FmiHarvester(conn=_memory_db())
        ds = h._query_to_dataset("fmi::observations::test", "Havainto", "")
        assert "havainnot" in ds.keywords_fi
