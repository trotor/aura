"""Testit MunicipalityPopulator-luokalle."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import run_migrations
from aura.populators.municipalities import MunicipalityPopulator


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


# Tilastokeskuksen API:n simuloidut vastaukset

CLASSIFICATIONS_LIST = [
    "https://api.stat.fi/.../kunta_1_20240101",
    "https://api.stat.fi/.../kunta_1_20250101",
    "https://api.stat.fi/.../kunta_1_20260101",
    "https://api.stat.fi/.../seutukunta_1_20250101",
]

KUNTA_ITEMS_FI = [
    {
        "code": "091",
        "classificationItemNames": [{"lang": "fi", "name": "Helsinki"}],
    },
    {
        "code": "049",
        "classificationItemNames": [{"lang": "fi", "name": "Espoo"}],
    },
    {
        "code": "092",
        "classificationItemNames": [{"lang": "fi", "name": "Vantaa"}],
    },
]

KUNTA_ITEMS_SV = [
    {
        "code": "091",
        "classificationItemNames": [{"lang": "sv", "name": "Helsingfors"}],
    },
    {
        "code": "049",
        "classificationItemNames": [{"lang": "sv", "name": "Esbo"}],
    },
    {
        "code": "092",
        "classificationItemNames": [{"lang": "sv", "name": "Vanda"}],
    },
]

MAAKUNTA_ITEMS = [
    {
        "code": "01",
        "classificationItemNames": [{"lang": "fi", "name": "Uusimaa"}],
    },
]

ELY_ITEMS = [
    {
        "code": "01",
        "classificationItemNames": [{"lang": "fi", "name": "Uudenmaan ELY-keskus"}],
    },
]

HVA_ITEMS = [
    {
        "code": "01",
        "classificationItemNames": [
            {"lang": "fi", "name": "Itä-Uudenmaan hyvinvointialue"},
        ],
    },
    {
        "code": "96",
        "classificationItemNames": [
            {"lang": "fi", "name": "Helsingin kaupunki"},
        ],
    },
]

KUNTA_MAAKUNTA_MAPS = [
    "https://api.stat.fi/.../maps/091/01",
    "https://api.stat.fi/.../maps/049/01",
    "https://api.stat.fi/.../maps/092/01",
]

KUNTA_ELY_MAPS = [
    "https://api.stat.fi/.../maps/091/01",
    "https://api.stat.fi/.../maps/049/01",
    "https://api.stat.fi/.../maps/092/01",
]

KUNTA_HVA_MAPS = [
    "https://api.stat.fi/.../maps/091/96",
    "https://api.stat.fi/.../maps/049/01",
    "https://api.stat.fi/.../maps/092/01",
]


def _make_mock_response(data: object) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    return resp


def _setup_mock_client() -> AsyncMock:
    """Luo mock-client joka palauttaa oikeita vastauksia eri URL:ille."""
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        params = kwargs.get("params", {})
        assert isinstance(params, dict)

        if "/classifications?" in url or url.endswith("/classifications"):
            return _make_mock_response(CLASSIFICATIONS_LIST)

        if "classificationItems" in url:
            lang = params.get("lang", "fi")
            if "maakunta" in url:
                return _make_mock_response(MAAKUNTA_ITEMS)
            if "ely" in url:
                return _make_mock_response(ELY_ITEMS)
            if "hyvinvointialue" in url:
                return _make_mock_response(HVA_ITEMS)
            if lang == "sv":
                return _make_mock_response(KUNTA_ITEMS_SV)
            return _make_mock_response(KUNTA_ITEMS_FI)

        if "correspondenceTables" in url:
            if "maakunta" in url:
                return _make_mock_response(KUNTA_MAAKUNTA_MAPS)
            if "ely" in url:
                return _make_mock_response(KUNTA_ELY_MAPS)
            if "hyvinvointialue" in url:
                return _make_mock_response(KUNTA_HVA_MAPS)

        return _make_mock_response([])

    client.get = mock_get
    return client


class TestMunicipalityPopulatorConfig:
    def test_name(self) -> None:
        p = MunicipalityPopulator(conn=_memory_db())
        assert p.name == "municipalities"

    def test_description(self) -> None:
        p = MunicipalityPopulator(conn=_memory_db())
        assert "kunnat" in p.description.lower()


class TestMunicipalityPopulate:
    @pytest.mark.asyncio
    async def test_populate_returns_count(self) -> None:
        p = MunicipalityPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await p.populate()

        assert count == 3

    @pytest.mark.asyncio
    async def test_populate_writes_to_db(self) -> None:
        conn = _memory_db()
        p = MunicipalityPopulator(conn=conn)
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        rows = conn.execute("SELECT * FROM ref_municipalities ORDER BY code").fetchall()
        assert len(rows) == 3

        # Helsinki
        hki = conn.execute(
            "SELECT * FROM ref_municipalities WHERE code = '091'"
        ).fetchone()
        assert hki["name_fi"] == "Helsinki"
        assert hki["name_sv"] == "Helsingfors"
        assert hki["region_code"] == "01"
        assert hki["region_name_fi"] == "Uusimaa"
        assert hki["ely_code"] == "01"
        assert hki["ely_name_fi"] == "Uudenmaan ELY-keskus"
        assert hki["wellbeing_area_code"] == "96"
        assert hki["wellbeing_area_name_fi"] == "Helsingin kaupunki"

    @pytest.mark.asyncio
    async def test_populate_updates_metadata(self) -> None:
        conn = _memory_db()
        p = MunicipalityPopulator(conn=conn)
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        assert p.is_populated()
        row = conn.execute(
            "SELECT * FROM ref_metadata WHERE name = 'municipalities'"
        ).fetchone()
        assert row["record_count"] == 3
        assert row["version"] == "20260101"

    @pytest.mark.asyncio
    async def test_populate_idempotent(self) -> None:
        """Toinen populate-kutsu päivittää, ei luo duplikaatteja."""
        conn = _memory_db()
        p = MunicipalityPopulator(conn=conn)
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()
            await p.populate()

        count = conn.execute(
            "SELECT COUNT(*) FROM ref_municipalities"
        ).fetchone()[0]
        assert count == 3


class TestFindLatestVersion:
    @pytest.mark.asyncio
    async def test_finds_latest(self) -> None:
        p = MunicipalityPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        version = await p._find_latest_version(mock_client)
        assert version == "20260101"

    @pytest.mark.asyncio
    async def test_raises_on_empty(self) -> None:
        p = MunicipalityPopulator(conn=_memory_db())
        client = AsyncMock()
        resp = _make_mock_response([])
        client.get = AsyncMock(return_value=resp)

        with pytest.raises(RuntimeError, match="ei löytynyt"):
            await p._find_latest_version(client)


class TestFetchCorrespondence:
    @pytest.mark.asyncio
    async def test_parses_url_mapping(self) -> None:
        p = MunicipalityPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        mapping = await p._fetch_correspondence(
            mock_client, "kunta", "maakunta", "20250101",
        )
        assert mapping["091"] == "01"
        assert mapping["049"] == "01"
        assert len(mapping) == 3
