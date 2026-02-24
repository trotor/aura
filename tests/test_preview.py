"""Testit preview/query_data MCP-työkalulle."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import preview_data, query_data
from aura.tools.preview import (
    _format_md_table,
    _pick_resource,
    _preview_csv,
    _preview_json,
    _preview_pxweb,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_dataset(
    conn: sqlite3.Connection,
    ds_id: str = "test-1",
    source: str = "avoindata.fi",
    resources: list[Resource] | None = None,
) -> None:
    if resources is None:
        resources = [
            Resource(id=f"{ds_id}-csv", name="test.csv", format="CSV", url="https://example.com/test.csv"),
        ]
    ds = Dataset(
        id=ds_id,
        name=ds_id,
        title="Test Dataset",
        source=source,
        resources=resources,
    )
    upsert_dataset(conn, ds)
    conn.commit()


class TestPickResource:
    """Testit resurssin valinnalle."""

    def test_returns_none_for_empty(self):
        assert _pick_resource([]) is None

    def test_returns_by_index(self):
        resources = [
            {"format": "CSV", "url": "a.csv"},
            {"format": "JSON", "url": "b.json"},
        ]
        assert _pick_resource(resources, resource_index=1)["url"] == "b.json"

    def test_returns_none_for_invalid_index(self):
        resources = [{"format": "CSV", "url": "a.csv"}]
        assert _pick_resource(resources, resource_index=5) is None

    def test_prefers_format_hint(self):
        resources = [
            {"format": "HTML", "url": "page.html"},
            {"format": "CSV", "url": "data.csv"},
        ]
        assert _pick_resource(resources, format_hint="CSV")["url"] == "data.csv"

    def test_prefers_machine_readable(self):
        resources = [
            {"format": "HTML", "url": "page.html"},
            {"format": "JSON", "url": "data.json"},
        ]
        assert _pick_resource(resources)["url"] == "data.json"

    def test_skips_wms(self):
        resources = [
            {"format": "WMS", "url": "wms.xml"},
            {"format": "CSV", "url": "data.csv"},
        ]
        assert _pick_resource(resources)["url"] == "data.csv"


class TestFormatMdTable:
    """Testit markdown-taulukon muodostukselle."""

    def test_basic_table(self):
        result = _format_md_table(["A", "B"], [["1", "2"], ["3", "4"]])
        assert "| A | B |" in result
        assert "| 1 | 2 |" in result
        assert "| 3 | 4 |" in result

    def test_empty_headers(self):
        assert _format_md_table([], []) == ""

    def test_escapes_pipes(self):
        result = _format_md_table(["Col"], [["val|ue"]])
        assert "val\\|ue" in result


async def _async_iter(chunks: list[bytes]):
    """Apugeneraattori async for -mockkausta varten."""
    for chunk in chunks:
        yield chunk


class TestPreviewCsv:
    """Testit CSV-esikatselulle."""

    @pytest.mark.anyio
    async def test_basic_csv(self):
        csv_content = b"nimi,arvo\nHelsinki,100\nTampere,200\n"

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = MagicMock(return_value=_async_iter([csv_content]))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client):
            result = await _preview_csv("https://example.com/test.csv", 10)

        assert "nimi" in result
        assert "Helsinki" in result
        assert "Tampere" in result

    @pytest.mark.anyio
    async def test_semicolon_delimiter(self):
        csv_content = b"nimi;arvo\nHelsinki;100\n"

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = MagicMock(return_value=_async_iter([csv_content]))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client):
            result = await _preview_csv("https://example.com/test.csv", 10)

        assert "nimi" in result
        assert "Helsinki" in result


class TestPreviewJson:
    """Testit JSON-esikatselulle."""

    @pytest.mark.anyio
    async def test_json_array(self):
        data = [{"nimi": "Helsinki", "arvo": 100}, {"nimi": "Tampere", "arvo": 200}]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = json.dumps(data)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client):
            result = await _preview_json("https://example.com/data.json", 10)

        assert "Helsinki" in result
        assert "Tampere" in result

    @pytest.mark.anyio
    async def test_geojson(self):
        data = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"nimi": "Helsinki"}, "geometry": {}},
            ],
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = json.dumps(data)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client):
            result = await _preview_json("https://example.com/data.geojson", 10)

        assert "GeoJSON" in result
        assert "Helsinki" in result


class TestPreviewPxweb:
    """Testit PxWeb-esikatselulle."""

    @pytest.mark.anyio
    async def test_from_enrichment(self):
        dataset = {"id": "test-1", "name": "test-1"}
        enrichments = [
            {
                "field": "data_fields",
                "value": json.dumps([
                    {"code": "Alue", "name": "Alue", "value_count": 310, "examples": ["Helsinki", "Tampere"]},
                    {"code": "Vuosi", "name": "Vuosi", "value_count": 20, "examples": ["2020", "2021"]},
                ]),
            },
        ]

        result = await _preview_pxweb("https://example.com/api", dataset, enrichments)

        assert "Alue" in result
        assert "Helsinki" in result
        assert "Vuosi" in result

    @pytest.mark.anyio
    async def test_from_api(self):
        dataset = {"id": "test-1", "name": "test-1"}
        meta = {
            "title": "Testtaulu",
            "variables": [
                {"code": "Alue", "text": "Alue", "values": ["KU091"], "valueTexts": ["Helsinki"]},
            ],
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=meta)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client):
            result = await _preview_pxweb("https://example.com/api", dataset, [])

        assert "Testtaulu" in result
        assert "Alue" in result
        assert "Helsinki" in result


class TestPreviewDataTool:
    """Testit preview_data/query_data MCP-työkalulle."""

    @pytest.mark.anyio
    async def test_dataset_not_found(self):
        conn = _memory_db()
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await query_data("nonexistent")
        assert "ei löytynyt" in result

    @pytest.mark.anyio
    async def test_no_resources(self):
        conn = _memory_db()
        _seed_dataset(conn, resources=[])
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await query_data("test-1")
        assert "ei ole resursseja" in result

    @pytest.mark.anyio
    async def test_wms_returns_link(self):
        conn = _memory_db()
        _seed_dataset(
            conn,
            resources=[
                Resource(id="r1", name="WMS", format="WMS", url="https://example.com/wms"),
            ],
        )
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await query_data("test-1")
        assert "WMS" in result
        assert "ei tue suoraa esikatselua" in result

    @pytest.mark.anyio
    async def test_html_returns_link(self):
        conn = _memory_db()
        _seed_dataset(
            conn,
            resources=[
                Resource(id="r1", name="Web", format="HTML", url="https://example.com/page"),
            ],
        )
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await query_data("test-1")
        assert "Verkkosivu" in result

    @pytest.mark.anyio
    async def test_timeout_error(self):
        conn = _memory_db()
        _seed_dataset(conn)

        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("test-1")
        assert "Aikakatkaisu" in result

    @pytest.mark.anyio
    async def test_max_rows_capped(self):
        conn = _memory_db()
        _seed_dataset(conn)

        with patch("aura.tools.data._server._get_conn", return_value=conn):
            with patch("aura.tools.data._preview_csv", new_callable=AsyncMock) as mock_csv:
                mock_csv.return_value = "mock csv"
                result = await query_data("test-1", max_rows=1000)
                # Varmistetaan että max_rows rajattiin 500:een
                mock_csv.assert_called_once_with("https://example.com/test.csv", 500)

    @pytest.mark.anyio
    async def test_backward_compat_preview_data(self):
        """preview_data() on backward-compat alias query_data:lle."""
        conn = _memory_db()
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await preview_data("nonexistent")
        assert "ei löytynyt" in result
