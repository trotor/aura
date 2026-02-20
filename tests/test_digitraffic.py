"""Testit Digitraffic-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.digitraffic import DigitrafficHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


MOCK_OPENAPI_SPEC = {
    "info": {"title": "Tieliikenne API"},
    "paths": {
        "/api/weathercam/v1/stations": {
            "get": {
                "summary": "Kelikamerat",
                "description": "Palauttaa kelikameroiden tiedot",
                "tags": ["Weathercam"],
            }
        },
        "/api/tms/v1/stations": {
            "get": {
                "summary": "LAM-asemat",
                "description": "Liikenteen automaattiset mittausasemat",
                "tags": ["TMS"],
            }
        },
        "/internal/only": {
            "post": {
                "summary": "Sisäinen endpoint",
            }
        },
    },
}


class TestDigitrafficHarvest:
    """DigitrafficHarvester.harvest()-testit."""

    @pytest.mark.asyncio
    async def test_harvest_parses_openapi_endpoints(self) -> None:
        """GET-endpointit parsitaan dataseteiksi."""
        conn = _memory_db()
        h = DigitrafficHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OPENAPI_SPEC
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        # 3 API:a * 2 GET-endpointia = 6 (POST-endpoint ohitetaan)
        assert count == 6

    @pytest.mark.asyncio
    async def test_harvest_skips_non_get_endpoints(self) -> None:
        """POST-only-endpointit ohitetaan."""
        conn = _memory_db()
        h = DigitrafficHarvester(conn=conn)

        spec_only_post = {
            "info": {"title": "Test"},
            "paths": {
                "/api/test": {"post": {"summary": "Vain POST"}}
            },
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = spec_only_post
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 0

    @pytest.mark.asyncio
    async def test_harvest_handles_api_error(self) -> None:
        """API-virhe ohitetaan ja muita API:ja haetaan."""
        conn = _memory_db()
        h = DigitrafficHarvester(conn=conn)

        call_count = 0

        async def mock_get(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("HTTP 500")
            resp = MagicMock()
            resp.json.return_value = MOCK_OPENAPI_SPEC
            resp.raise_for_status = MagicMock()
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        # 1 API virheellinen, 2 onnistunutta * 2 endpointia = 4
        assert count == 4


class TestDatasetCreation:
    """Datasettien luonnin testit."""

    @pytest.mark.asyncio
    async def test_dataset_has_correct_source(self) -> None:
        conn = _memory_db()
        h = DigitrafficHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OPENAPI_SPEC
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT DISTINCT source FROM datasets WHERE source = 'digitraffic'"
        ).fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_datasets_have_api_resources(self) -> None:
        conn = _memory_db()
        h = DigitrafficHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OPENAPI_SPEC
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        rows = conn.execute(
            "SELECT format FROM resources WHERE dataset_id LIKE 'digitraffic-%'"
        ).fetchall()
        assert all(r["format"] == "API" for r in rows)
