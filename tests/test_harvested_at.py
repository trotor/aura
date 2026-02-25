"""Testit harvested_at-näkyvyydelle (#122) ja rajapintatiedolle (#120)."""

import json
import sqlite3
from unittest.mock import patch

import pytest

from aura.database import init_db, upsert_dataset, upsert_source
from aura.models import Dataset
from aura.search import format_dataset_detail
from aura.server import describe
from aura.tools.describe import _format_source_line


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    ds = Dataset(
        id="test-1",
        name="test-1",
        title_fi="Testidata",
        source="avoindata.fi",
    )
    upsert_dataset(conn, ds)
    conn.commit()


class TestHarvestedAtInDetail:
    """harvested_at näkyvissä format_dataset_detail-tulosteessa."""

    def test_shows_harvested_at(self) -> None:
        ds = {
            "name": "test",
            "title_fi": "Testi",
            "harvested_at": "2026-02-20 12:00:00",
        }
        result = format_dataset_detail(ds)
        assert "Harvestoitu" in result
        assert "2026-02-20" in result

    def test_no_harvested_at_no_line(self) -> None:
        ds = {"name": "test", "title_fi": "Testi"}
        result = format_dataset_detail(ds)
        assert "Harvestoitu" not in result


class TestHarvestedAtInSearchStructured:
    """harvested_at näkyvissä search_structured-tuloksissa."""

    @pytest.mark.asyncio
    async def test_search_structured_includes_harvested_at(self) -> None:
        from aura.tools.search import search_structured

        conn = _memory_db()
        _seed(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._expand_query", return_value="test"):
            result = await search_structured("test")

        data = json.loads(result)
        assert data["count"] >= 1
        first = data["results"][0]
        assert "harvested_at" in first


class TestSourceLine:
    """Rajapintatieto describe()-tulosteessa (#120)."""

    def test_format_source_line_with_protocol_and_url(self) -> None:
        info = {"query_protocol": "ckan", "api_base_url": "https://api.example.com"}
        result = _format_source_line(info)
        assert "CKAN" in result
        assert "https://api.example.com" in result

    def test_format_source_line_protocol_only(self) -> None:
        info = {"query_protocol": "pxweb", "api_base_url": ""}
        result = _format_source_line(info)
        assert "PXWEB" in result

    def test_format_source_line_empty(self) -> None:
        info = {"query_protocol": "", "api_base_url": ""}
        assert _format_source_line(info) == ""

    @pytest.mark.asyncio
    async def test_describe_shows_source_info(self) -> None:
        conn = _memory_db()
        _seed(conn)
        upsert_source(conn, {
            "name": "avoindata.fi",
            "query_protocol": "ckan",
            "api_base_url": "https://www.avoindata.fi/data/api/3",
        })
        conn.commit()

        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            result = await describe("test-1")

        assert "Rajapinta" in result
        assert "CKAN" in result
