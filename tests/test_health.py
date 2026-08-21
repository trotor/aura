"""Testit resurssien saatavuustarkistukselle."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aura.database import init_db, upsert_dataset
from aura.health import (
    HealthResult,
    TokenBucket,
    check_all_resources,
    check_resource,
    get_dataset_health,
    get_health_summary,
    get_resources_to_check,
    get_unavailable_resources,
    save_health_result,
)
from aura.models import Dataset, Resource


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _sample_dataset(conn: sqlite3.Connection) -> None:
    """Lisää esimerkkidatasetti resursseineen kantaan."""
    ds = Dataset(
        id="test-ds",
        name="test-ds",
        title="Test",
        title_fi="Testi",
        source="test",
        num_resources=2,
        resources=[
            Resource(
                id="res-1",
                name="test.csv",
                format="CSV",
                url="https://example.com/test.csv",
            ),
            Resource(
                id="res-2",
                name="test.json",
                format="JSON",
                url="https://example.com/test.json",
            ),
        ],
    )
    upsert_dataset(conn, ds)
    conn.commit()


class TestTokenBucket:
    """TokenBucket rate limiterin testit."""

    @pytest.mark.asyncio
    async def test_first_acquire_instant(self):
        """Ensimmäiset tokenin kulutukset onnistuvat välittömästi."""
        bucket = TokenBucket(rate=5.0)
        import time

        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # 5 tokenia heti saatavilla

    @pytest.mark.asyncio
    async def test_rate_limiting_kicks_in(self):
        """Tokenien loppuessa joudutaan odottamaan."""
        bucket = TokenBucket(rate=10.0)
        # Kuluta kaikki
        for _ in range(10):
            await bucket.acquire()
        import time

        start = time.monotonic()
        await bucket.acquire()  # pitää odottaa refill
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # odotti ainakin vähän


class TestHealthResult:
    """HealthResult-dataluokan testit."""

    def test_defaults(self):
        r = HealthResult(resource_id="r1", dataset_id="d1", url="https://x.fi")
        assert not r.is_available
        assert r.checked_at  # auto-set

    def test_available_result(self):
        r = HealthResult(
            resource_id="r1",
            dataset_id="d1",
            url="https://x.fi",
            status_code=200,
            is_available=True,
            response_time_ms=50,
        )
        assert r.is_available
        assert r.status_code == 200


class TestCheckResource:
    """check_resource()-funktion testit."""

    @pytest.mark.asyncio
    async def test_successful_head(self):
        """HEAD 200 → saatavilla."""
        client = AsyncMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "text/csv", "content-length": "1234"}
        client.head = AsyncMock(return_value=resp)

        result = await check_resource(client, "r1", "d1", "https://example.com/data.csv")
        assert result.is_available
        assert result.status_code == 200
        assert result.content_length == 1234

    @pytest.mark.asyncio
    async def test_head_fails_get_succeeds(self):
        """HEAD 405 → GET fallback → saatavilla."""
        client = AsyncMock()
        head_resp = MagicMock()
        head_resp.status_code = 405
        head_resp.headers = {}
        client.head = AsyncMock(return_value=head_resp)

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.headers = {"content-type": "application/json"}
        client.get = AsyncMock(return_value=get_resp)

        result = await check_resource(client, "r1", "d1", "https://example.com/data.json")
        assert result.is_available

    @pytest.mark.asyncio
    async def test_404_not_available(self):
        """404 → ei saatavilla."""
        client = AsyncMock()
        head_resp = MagicMock()
        head_resp.status_code = 404
        head_resp.headers = {}
        client.head = AsyncMock(return_value=head_resp)

        get_resp = MagicMock()
        get_resp.status_code = 404
        get_resp.headers = {}
        client.get = AsyncMock(return_value=get_resp)

        result = await check_resource(client, "r1", "d1", "https://example.com/missing.csv")
        assert not result.is_available
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Timeout → ei saatavilla."""
        client = AsyncMock()
        client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        result = await check_resource(client, "r1", "d1", "https://example.com/slow")
        assert not result.is_available
        assert result.error_message == "Timeout"

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        """Virheellinen URL → ei saatavilla."""
        client = AsyncMock()
        result = await check_resource(client, "r1", "d1", "not-a-url")
        assert not result.is_available
        assert "Virheellinen" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_wfs_skips_head(self):
        """WFS-URL käyttää suoraan GET:iä."""
        client = AsyncMock()
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.headers = {"content-type": "application/xml"}
        client.get = AsyncMock(return_value=get_resp)

        result = await check_resource(
            client,
            "r1",
            "d1",
            "https://example.com/geoserver/wfs?service=WFS",
        )
        assert result.is_available
        # HEAD ei pitäisi olla kutsuttu
        client.head.assert_not_called()


class TestDatabase:
    """Tietokantaoperaatioiden testit."""

    def test_save_and_get_health(self):
        conn = _memory_db()
        _sample_dataset(conn)

        result = HealthResult(
            resource_id="res-1",
            dataset_id="test-ds",
            url="https://example.com/test.csv",
            status_code=200,
            is_available=True,
            response_time_ms=42,
        )
        save_health_result(conn, result)
        conn.commit()

        health = get_dataset_health(conn, "test-ds")
        assert len(health) == 1
        assert health[0]["is_available"]
        assert health[0]["response_time_ms"] == 42

    def test_get_resources_to_check(self):
        conn = _memory_db()
        _sample_dataset(conn)

        resources = get_resources_to_check(conn)
        assert len(resources) == 2

    def test_get_resources_excludes_checked(self):
        conn = _memory_db()
        _sample_dataset(conn)

        # Tallenna tarkistus
        result = HealthResult(
            resource_id="res-1",
            dataset_id="test-ds",
            url="https://example.com/test.csv",
            status_code=200,
            is_available=True,
        )
        save_health_result(conn, result)
        conn.commit()

        # Vain res-2 pitäisi puuttua (stale_days=7)
        resources = get_resources_to_check(conn, stale_days=7)
        assert len(resources) == 1
        assert resources[0]["resource_id"] == "res-2"

    def test_get_resources_by_source(self):
        conn = _memory_db()
        _sample_dataset(conn)

        resources = get_resources_to_check(conn, source="test")
        assert len(resources) == 2

        resources = get_resources_to_check(conn, source="other")
        assert len(resources) == 0

    def test_get_health_summary_empty(self):
        conn = _memory_db()
        summary = get_health_summary(conn)
        assert summary["total"] == 0

    def test_get_health_summary(self):
        conn = _memory_db()
        _sample_dataset(conn)

        for res_id, available in [("res-1", True), ("res-2", False)]:
            save_health_result(
                conn,
                HealthResult(
                    resource_id=res_id,
                    dataset_id="test-ds",
                    url=f"https://example.com/{res_id}",
                    status_code=200 if available else 404,
                    is_available=available,
                    response_time_ms=100,
                ),
            )
        conn.commit()

        summary = get_health_summary(conn)
        assert summary["total"] == 2
        assert summary["available"] == 1
        assert summary["unavailable"] == 1

    def test_get_unavailable_resources(self):
        conn = _memory_db()
        _sample_dataset(conn)

        save_health_result(
            conn,
            HealthResult(
                resource_id="res-1",
                dataset_id="test-ds",
                url="https://example.com/test.csv",
                status_code=404,
                is_available=False,
                error_message="HTTP 404",
            ),
        )
        conn.commit()

        unavail = get_unavailable_resources(conn)
        assert len(unavail) == 1
        assert unavail[0]["status_code"] == 404


class TestCheckAll:
    """check_all_resources()-funktion testit."""

    @pytest.mark.asyncio
    async def test_check_all_with_mock(self):
        """Kokonaistarkistus mock-resurssien kanssa."""
        conn = _memory_db()
        _sample_dataset(conn)

        # Mock check_resource palauttamaan onnistunut tulos
        async def _mock_check(
            client: object,
            res_id: str,
            ds_id: str,
            url: str,
            resource_format: str | None = None,
        ) -> HealthResult:
            return HealthResult(
                resource_id=res_id,
                dataset_id=ds_id,
                url=url,
                status_code=200,
                is_available=True,
                response_time_ms=50,
            )

        with patch("aura.health.check_resource", side_effect=_mock_check):
            summary = await check_all_resources(conn)

        assert summary.total == 2
        assert summary.available == 2
        assert summary.unavailable == 0
        assert summary.availability_pct == 100.0

    @pytest.mark.asyncio
    async def test_check_all_limit(self):
        """Limit rajoittaa tarkistettavia resursseja."""
        conn = _memory_db()
        _sample_dataset(conn)

        async def _mock_check(
            client: object,
            res_id: str,
            ds_id: str,
            url: str,
            resource_format: str | None = None,
        ) -> HealthResult:
            return HealthResult(
                resource_id=res_id,
                dataset_id=ds_id,
                url=url,
                status_code=200,
                is_available=True,
                response_time_ms=30,
            )

        with patch("aura.health.check_resource", side_effect=_mock_check):
            summary = await check_all_resources(conn, limit=1)

        assert summary.total == 1

    def test_availability_pct_zero(self):
        """Tyhjä summary → 0%."""
        s = HealthResult.__module__  # noqa: F841
        from aura.health import HealthSummary

        summary = HealthSummary()
        assert summary.availability_pct == 0.0
