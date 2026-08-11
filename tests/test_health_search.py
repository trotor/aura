"""Testit saatavuustiedolle hakutuloksissa (#121) ja auth-enrichmenteille (#118)."""

import json
import sqlite3
from unittest.mock import patch

import pytest

import aura.server  # noqa: F401 — resolve circular import before tools
from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.tools.enrichment import VALID_ENRICHMENT_FIELDS


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_with_health(conn: sqlite3.Connection) -> None:
    ds = Dataset(
        id="ds-1",
        name="test-dataset",
        title_fi="Testiaineisto",
        resources=[
            Resource(id="res-1", name="CSV", format="CSV", url="https://example.com/data.csv"),
            Resource(id="res-2", name="WFS", format="WFS", url="https://example.com/wfs"),
        ],
    )
    upsert_dataset(conn, ds)
    # Lisää health-tiedot
    conn.execute(
        """INSERT OR REPLACE INTO resource_health
           (resource_id, dataset_id, url, status_code, response_time_ms,
            is_available, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("res-1", "ds-1", "https://example.com/data.csv", 200, 150, 1, "2026-02-25T10:00:00"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO resource_health
           (resource_id, dataset_id, url, status_code, response_time_ms,
            is_available, error_message, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("res-2", "ds-1", "https://example.com/wfs", 500, 50, 0, "Internal Server Error",
         "2026-02-25T09:00:00"),
    )
    conn.commit()


class TestHealthInSearchStructured:
    """Saatavuustieto search_structured-tuloksissa (#121)."""

    @pytest.mark.asyncio
    async def test_includes_health_when_available(self) -> None:
        from aura.tools.search import search_structured

        conn = _memory_db()
        _seed_with_health(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._expand_query", return_value="test"):
            result = await search_structured("test")

        data = json.loads(result)
        assert data["count"] >= 1
        first = data["results"][0]
        assert "health" in first
        health = first["health"]
        assert health["is_available"] is True  # MAX(1, 0) = 1
        assert health["last_checked"] == "2026-02-25T10:00:00"
        assert health["avg_response_time_ms"] == 100  # AVG(150, 50) = 100

    @pytest.mark.asyncio
    async def test_health_null_when_not_checked(self) -> None:
        from aura.tools.search import search_structured

        conn = _memory_db()
        ds = Dataset(id="ds-2", name="unchecked", title_fi="Ei tarkistettu")
        upsert_dataset(conn, ds)
        conn.commit()

        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._expand_query", return_value="unchecked"):
            result = await search_structured("unchecked")

        data = json.loads(result)
        assert data["count"] >= 1
        first = data["results"][0]
        assert first["health"] is None


class TestBatchHealthStatus:
    """_batch_health_status yksikkötestit."""

    def test_returns_aggregated_data(self) -> None:
        from aura.tools.search import _batch_health_status

        conn = _memory_db()
        _seed_with_health(conn)
        result = _batch_health_status(conn, ["ds-1"])
        assert "ds-1" in result
        assert result["ds-1"]["is_available"] is True
        assert result["ds-1"]["avg_response_time_ms"] == 100

    def test_empty_ids(self) -> None:
        from aura.tools.search import _batch_health_status

        conn = _memory_db()
        assert _batch_health_status(conn, []) == {}

    def test_unknown_dataset(self) -> None:
        from aura.tools.search import _batch_health_status

        conn = _memory_db()
        result = _batch_health_status(conn, ["nonexistent"])
        assert result == {}

    def test_all_unavailable(self) -> None:
        from aura.tools.search import _batch_health_status

        conn = _memory_db()
        ds = Dataset(
            id="ds-down", name="down",
            resources=[Resource(id="res-down", name="X", format="CSV", url="https://x.com")],
        )
        upsert_dataset(conn, ds)
        conn.execute(
            """INSERT INTO resource_health
               (resource_id, dataset_id, url, is_available, response_time_ms, checked_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("res-down", "ds-down", "https://x.com", 0, 5000, "2026-02-25"),
        )
        conn.commit()
        result = _batch_health_status(conn, ["ds-down"])
        assert result["ds-down"]["is_available"] is False


class TestAuthEnrichmentFields:
    """Auth-enrichment-kenttien validointi (#118)."""

    def test_auth_fields_in_valid_set(self) -> None:
        assert "auth_method" in VALID_ENRICHMENT_FIELDS
        assert "auth_registration_url" in VALID_ENRICHMENT_FIELDS
        assert "auth_notes" in VALID_ENRICHMENT_FIELDS

    def test_enrich_with_auth_method(self) -> None:
        from aura.server import enrich

        conn = _memory_db()
        ds = Dataset(id="ds-auth", name="auth-test", title_fi="Auth test")
        upsert_dataset(conn, ds)
        conn.commit()

        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("ds-auth", "auth_method", "apikey")
        assert "tallennettu" in result

    def test_enrich_with_registration_url(self) -> None:
        from aura.server import enrich

        conn = _memory_db()
        ds = Dataset(id="ds-auth2", name="auth-test2", title_fi="Auth test 2")
        upsert_dataset(conn, ds)
        conn.commit()

        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("ds-auth2", "auth_registration_url", "https://example.com/register")
        assert "tallennettu" in result
