"""Testit Traficom-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.traficom import ENTITY_SETS, TraficomHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


MOCK_ODATA_RESPONSE = {
    "value": [
        {"name": "AjoneuvorekisteriVer2", "url": "https://example.com/AjoneuvorekisteriVer2"},
        {"name": "AircraftRegister", "url": "https://example.com/AircraftRegister"},
        {"name": "TuntematonEntitySet", "url": "https://example.com/Tuntematon"},
    ]
}


class TestTraficomHarvest:
    """TraficomHarvester.harvest()-testit."""

    @pytest.mark.asyncio
    async def test_harvest_from_api(self) -> None:
        """API:sta haetut entity setit tallennetaan."""
        conn = _memory_db()
        h = TraficomHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_ODATA_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 3

    @pytest.mark.asyncio
    async def test_harvest_fallback_on_error(self) -> None:
        """Virhetilanteessa käytetään tunnettua entity set -listaa."""
        conn = _memory_db()
        h = TraficomHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("HTTP 500"))

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == len(ENTITY_SETS)

    @pytest.mark.asyncio
    async def test_datasets_have_odata_resources(self) -> None:
        conn = _memory_db()
        h = TraficomHarvester(conn=conn)

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_ODATA_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        rows = conn.execute(
            "SELECT format FROM resources WHERE dataset_id LIKE 'traficom-%'"
        ).fetchall()
        assert all(r["format"] == "API" for r in rows)


class TestEntitySetConfig:
    """ENTITY_SETS-konfiguraation testit."""

    def test_all_entity_sets_have_title(self) -> None:
        for name, info in ENTITY_SETS.items():
            assert "title_fi" in info, f"{name} puuttuu title_fi"

    def test_all_entity_sets_have_keywords(self) -> None:
        for name, info in ENTITY_SETS.items():
            assert "keywords" in info, f"{name} puuttuu keywords"
            assert len(info["keywords"]) > 0
