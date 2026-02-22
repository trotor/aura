"""Testit BaseHarvester-pohjaluokalle ja harvester-rekisterille."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aura.database import init_db
from aura.harvesters import HARVESTERS, get_all_harvesters, get_harvester
from aura.harvesters.base import BaseHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class ConcreteHarvester(BaseHarvester):
    """Konkreettinen harvester testejä varten."""

    name = "test-harvester"
    description = "Testi"
    url = "https://example.com"
    max_retries = 2
    request_delay = 0.0  # Nopeat testit

    async def harvest(self) -> int:
        return 0


# --- _make_dataset ---


class TestMakeDataset:
    """_make_dataset()-apumetodin testit."""

    def test_default_values(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())
        ds = h._make_dataset(id="test-1", name="test")
        assert ds.license_id == "cc-by-4.0"
        assert ds.license_title == "CC BY 4.0"
        assert ds.collection_type == "Open Data"
        assert ds.geographical_coverage == ["Suomi"]
        assert ds.source == "test-harvester"
        assert ds.access_level == "open"
        assert ds.metadata_modified != ""

    def test_override_defaults(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())
        ds = h._make_dataset(
            id="test-1",
            name="test",
            license_id="mit",
            source="custom",
        )
        assert ds.license_id == "mit"
        assert ds.source == "custom"

    def test_extra_fields(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())
        ds = h._make_dataset(
            id="test-1",
            name="test",
            title_fi="Otsikko",
            keywords_fi=["a", "b"],
        )
        assert ds.title_fi == "Otsikko"
        assert ds.keywords_fi == ["a", "b"]


# --- _add_enrichment ---


class TestAddEnrichment:
    """_add_enrichment()-apumetodin testit."""

    def test_adds_enrichment(self) -> None:
        conn = _memory_db()
        h = ConcreteHarvester(conn=conn)
        h._add_enrichment("ds-1", "use_case", "Tutkimus")
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM enrichments WHERE dataset_id = 'ds-1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["field"] == "use_case"
        assert rows[0]["value"] == "Tutkimus"
        assert rows[0]["source_type"] == "harvest"

    def test_idempotent(self) -> None:
        conn = _memory_db()
        h = ConcreteHarvester(conn=conn)
        h._add_enrichment("ds-1", "use_case", "Tutkimus")
        h._add_enrichment("ds-1", "use_case", "Tutkimus")
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE dataset_id = 'ds-1'"
        ).fetchone()[0]
        assert count == 1

    def test_empty_value_skipped(self) -> None:
        conn = _memory_db()
        h = ConcreteHarvester(conn=conn)
        h._add_enrichment("ds-1", "use_case", "")
        h._add_enrichment("ds-1", "use_case", "   ")
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE dataset_id = 'ds-1'"
        ).fetchone()[0]
        assert count == 0

    def test_different_values_not_deduplicated(self) -> None:
        conn = _memory_db()
        h = ConcreteHarvester(conn=conn)
        h._add_enrichment("ds-1", "use_case", "Tutkimus")
        h._add_enrichment("ds-1", "use_case", "Opetus")
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE dataset_id = 'ds-1'"
        ).fetchone()[0]
        assert count == 2


# --- _fetch ---


class TestFetch:
    """_fetch()-retryn testit."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await h._fetch(mock_client, "https://example.com/api")
        assert result == mock_response
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_500(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.request = MagicMock()

        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[error_response, ok_response])

        result = await h._fetch(mock_client, "https://example.com/api")
        assert result == ok_response
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 503
        error_response.request = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await h._fetch(mock_client, "https://example.com/api")
        assert mock_client.get.call_count == 2  # max_retries=2

    @pytest.mark.asyncio
    async def test_retry_on_transport_error(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())

        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=[httpx.ConnectError("fail"), ok_response]
        )

        result = await h._fetch(mock_client, "https://example.com/api")
        assert result == ok_response

    @pytest.mark.asyncio
    async def test_429_respects_retry_after(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())

        rate_limited = MagicMock(spec=httpx.Response)
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "0"}
        rate_limited.request = MagicMock()

        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[rate_limited, ok_response])

        result = await h._fetch(mock_client, "https://example.com/api")
        assert result == ok_response

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 404
        error_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=error_response,
            )
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await h._fetch(mock_client, "https://example.com/api")
        assert mock_client.get.call_count == 1


# --- _make_client ---


class TestMakeClient:
    """_make_client()-testit."""

    def test_returns_async_client(self) -> None:
        h = ConcreteHarvester(conn=_memory_db())
        client = h._make_client()
        assert isinstance(client, httpx.AsyncClient)
        assert "Aura" in client.headers.get("User-Agent", "")


# --- Harvester registry ---


class TestHarvesterRegistry:
    """Harvester-rekisterin testit."""

    def test_all_harvesters_registered(self) -> None:
        assert len(HARVESTERS) >= 20

    def test_get_harvester_valid(self) -> None:
        cls = get_harvester("avoindata.fi")
        assert issubclass(cls, BaseHarvester)

    def test_get_harvester_invalid(self) -> None:
        with pytest.raises(ValueError, match="Tuntematon"):
            get_harvester("ei-olemassa")

    def test_get_all_harvesters_returns_copy(self) -> None:
        all_h = get_all_harvesters()
        assert len(all_h) == len(HARVESTERS)
        all_h["fake"] = BaseHarvester  # type: ignore[assignment]
        assert "fake" not in HARVESTERS

    def test_all_harvesters_have_name(self) -> None:
        for key, cls in HARVESTERS.items():
            assert cls.name, f"Harvester {key} missing name"
            assert cls.description, f"Harvester {key} missing description"

    def test_all_harvesters_are_base_subclasses(self) -> None:
        for key, cls in HARVESTERS.items():
            assert issubclass(cls, BaseHarvester), f"{key} is not a BaseHarvester"

    def test_registered_names_match_keys(self) -> None:
        """Rekisteriavain vastaa harvesterin nimeä."""
        for key, cls in HARVESTERS.items():
            assert key == cls.name, (
                f"Registry key '{key}' != harvester name '{cls.name}'"
            )
