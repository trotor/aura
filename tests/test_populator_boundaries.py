"""Testit BoundaryPopulator-luokalle."""

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import run_migrations
from aura.populators.boundaries import BoundaryPopulator, _validate_geojson


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


SAMPLE_KUNNAT: dict = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "NATCODE": "091",
                "NAMEFIN": "Helsinki",
                "NAMESWE": "Helsingfors",
                "LANDAREA": 213.75,
                "TOTALAREA": 715.48,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[25.0, 60.2], [25.1, 60.2], [25.1, 60.1], [25.0, 60.2]]],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "NATCODE": "049",
                "NAMEFIN": "Espoo",
                "NAMESWE": "Esbo",
                "LANDAREA": 312.26,
                "TOTALAREA": 528.03,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[24.6, 60.2], [24.7, 60.2], [24.7, 60.1], [24.6, 60.2]]],
            },
        },
    ],
}

SAMPLE_MAAKUNNAT: dict = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "NATCODE": "01",
                "NAMEFIN": "Uusimaa",
                "NAMESWE": "Nyland",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[24.5, 60.5], [25.5, 60.5], [25.5, 60.0], [24.5, 60.5]]],
            },
        },
    ],
}


def _setup_mock_client() -> AsyncMock:
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        if "maakuntarajat" in url:
            resp.json.return_value = SAMPLE_MAAKUNNAT
        elif "kuntarajat" in url:
            resp.json.return_value = SAMPLE_KUNNAT
        return resp

    client.get = mock_get
    return client


class TestBoundaryPopulatorConfig:
    def test_name(self) -> None:
        p = BoundaryPopulator(conn=_memory_db())
        assert p.name == "boundaries"

    def test_description(self) -> None:
        p = BoundaryPopulator(conn=_memory_db())
        assert "rajat" in p.description.lower()


class TestBoundaryPopulate:
    @pytest.mark.asyncio
    async def test_populate_creates_files(self, tmp_path: object) -> None:
        p = BoundaryPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        data_dir = tmp_path / "rajat"  # type: ignore[operator]

        with (
            patch.object(p, "_make_client") as mock_make,
            patch("aura.populators.boundaries.DATA_DIR", data_dir),
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        assert (data_dir / "kunnat.geojson").exists()
        assert (data_dir / "maakunnat.geojson").exists()

    @pytest.mark.asyncio
    async def test_populate_returns_count(self, tmp_path: object) -> None:
        p = BoundaryPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        data_dir = tmp_path / "rajat"  # type: ignore[operator]

        with (
            patch.object(p, "_make_client") as mock_make,
            patch("aura.populators.boundaries.DATA_DIR", data_dir),
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await p.populate()

        # 2 kunnat + 1 maakunta = 3
        assert count == 3

    @pytest.mark.asyncio
    async def test_metadata_updated(self, tmp_path: object) -> None:
        conn = _memory_db()
        p = BoundaryPopulator(conn=conn)
        mock_client = _setup_mock_client()
        data_dir = tmp_path / "rajat"  # type: ignore[operator]

        with (
            patch.object(p, "_make_client") as mock_make,
            patch("aura.populators.boundaries.DATA_DIR", data_dir),
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        row = conn.execute(
            "SELECT * FROM ref_metadata WHERE name = 'boundaries'"
        ).fetchone()
        assert row is not None
        assert row["record_count"] == 3
        assert row["version"]  # date string

    @pytest.mark.asyncio
    async def test_is_populated_after_run(self, tmp_path: object) -> None:
        p = BoundaryPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        data_dir = tmp_path / "rajat"  # type: ignore[operator]

        assert not p.is_populated()

        with (
            patch.object(p, "_make_client") as mock_make,
            patch("aura.populators.boundaries.DATA_DIR", data_dir),
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        # is_populated checks both metadata and files — patch DATA_DIR for file check too
        with patch("aura.populators.boundaries.DATA_DIR", data_dir):
            assert p.is_populated()

    @pytest.mark.asyncio
    async def test_files_contain_valid_features(self, tmp_path: object) -> None:
        p = BoundaryPopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        data_dir = tmp_path / "rajat"  # type: ignore[operator]

        with (
            patch.object(p, "_make_client") as mock_make,
            patch("aura.populators.boundaries.DATA_DIR", data_dir),
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        # Kunnat
        kunnat = json.loads((data_dir / "kunnat.geojson").read_text(encoding="utf-8"))
        assert kunnat["type"] == "FeatureCollection"
        assert len(kunnat["features"]) == 2
        props = kunnat["features"][0]["properties"]
        assert "NATCODE" in props
        assert "NAMEFIN" in props

        # Maakunnat
        maakunnat = json.loads((data_dir / "maakunnat.geojson").read_text(encoding="utf-8"))
        assert maakunnat["type"] == "FeatureCollection"
        assert len(maakunnat["features"]) == 1
        assert maakunnat["features"][0]["properties"]["NAMEFIN"] == "Uusimaa"


class TestValidateGeojson:
    def test_valid(self) -> None:
        _validate_geojson(SAMPLE_KUNNAT, "test")

    def test_wrong_type(self) -> None:
        with pytest.raises(ValueError, match="FeatureCollection"):
            _validate_geojson({"type": "Feature"}, "test")

    def test_empty_features(self) -> None:
        with pytest.raises(ValueError, match="featureja"):
            _validate_geojson({"type": "FeatureCollection", "features": []}, "test")

    def test_missing_features(self) -> None:
        with pytest.raises(ValueError, match="featureja"):
            _validate_geojson({"type": "FeatureCollection"}, "test")
