"""Testit MapSheetPopulator-luokalle."""

from __future__ import annotations

import io
import sqlite3
import struct
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import run_migrations
from aura.populators.map_sheets import MapSheetPopulator


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


def _create_mini_gpkg(path: str) -> None:
    """Luo minimaalinen GeoPackage-tiedosto testausta varten.

    Luo SQLite-tietokanta jossa on utm200- ja utm50-taulut
    yksinkertaisilla polygon-geometrioilla.
    """
    conn = sqlite3.connect(path)

    # GeoPackage vaatii gpkg_contents-taulun
    conn.execute("""
        CREATE TABLE gpkg_contents (
            table_name TEXT PRIMARY KEY,
            data_type TEXT NOT NULL DEFAULT 'features'
        )
    """)

    # Luodaan utm200 ja utm50 tasot testitiedoilla
    for scale, sheets in [
        ("utm200", [("K3", 100000, 6600000, 200000, 6800000)]),
        ("utm50", [
            ("K31", 100000, 6600000, 150000, 6700000),
            ("K32", 150000, 6600000, 200000, 6700000),
        ]),
    ]:
        conn.execute(f"""
            CREATE TABLE "{scale}" (
                fid INTEGER PRIMARY KEY,
                lehtitunnus TEXT,
                geometry BLOB
            )
        """)  # noqa: S608
        conn.execute(
            "INSERT INTO gpkg_contents (table_name) VALUES (?)",
            (scale,),
        )

        for i, (sheet_id, minx, miny, maxx, maxy) in enumerate(sheets, 1):
            # Luo minimaalinen GeoPackage binary geometry (GPKG standard header + WKB polygon)
            geom = _make_gpkg_polygon(minx, miny, maxx, maxy)
            conn.execute(
                f'INSERT INTO "{scale}" (fid, lehtitunnus, geometry) VALUES (?, ?, ?)',  # noqa: S608
                (i, sheet_id, geom),
            )

    conn.commit()
    conn.close()


def _make_gpkg_polygon(
    minx: float, miny: float, maxx: float, maxy: float,
) -> bytes:
    """Luo GeoPackage binary geometry (GP header + WKB Polygon)."""
    # GeoPackage binary geometry header (8 bytes)
    # Magic: GP, version: 0, flags: 1 (little-endian, envelope type 1)
    # srs_id: 3067
    gp_header = b"GP"  # magic
    gp_header += struct.pack("<B", 0)  # version
    gp_header += struct.pack("<B", 0b00000011)  # flags: little-endian, envelope type 1 (xxyy)
    gp_header += struct.pack("<i", 3067)  # srs_id
    # Envelope: minx, maxx, miny, maxy
    gp_header += struct.pack("<dddd", minx, maxx, miny, maxy)

    # WKB Polygon — rectangle from bbox corners
    wkb = struct.pack("<B", 1)  # byte order: little-endian
    wkb += struct.pack("<I", 3)  # type: Polygon
    wkb += struct.pack("<I", 1)  # num rings
    wkb += struct.pack("<I", 5)  # num points (closed ring)
    # 5 points forming a rectangle
    for x, y in [
        (minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny),
    ]:
        wkb += struct.pack("<dd", x, y)

    return gp_header + wkb


def _create_mini_gpkg_zip() -> bytes:
    """Luo zip-tiedosto joka sisältää mini-GeoPackagen."""
    import tempfile

    buf = io.BytesIO()

    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
        tmp_name = tmp.name

    _create_mini_gpkg(tmp_name)

    with open(tmp_name, "rb") as f:
        gpkg_bytes = f.read()

    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("TM35_karttalehtijako.gpkg", gpkg_bytes)

    return buf.getvalue()


class TestMapSheetPopulatorConfig:
    def test_name(self) -> None:
        p = MapSheetPopulator(conn=_memory_db())
        assert p.name == "map_sheets"

    def test_description(self) -> None:
        p = MapSheetPopulator(conn=_memory_db())
        assert "karttaleht" in p.description.lower()


class TestMapSheetPopulate:
    @pytest.mark.asyncio
    async def test_populate_returns_count(self, tmp_path: object) -> None:
        """Populate palauttaa oikean rivimäärän."""
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            count = await p.populate()

        # 1 (utm200) + 2 (utm50) + 0 (utm25) + 0 (utm10) = 3
        assert count == 3

    @pytest.mark.asyncio
    async def test_populate_writes_to_db(self, tmp_path: object) -> None:
        """Karttalehdet tallentuvat ref_map_sheets-tauluun."""
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            await p.populate()

        rows = conn.execute("SELECT * FROM ref_map_sheets ORDER BY id").fetchall()
        assert len(rows) == 3

        # Tarkista yksittäinen rivi
        k3 = conn.execute(
            "SELECT * FROM ref_map_sheets WHERE id = 'K3'"
        ).fetchone()
        assert k3 is not None
        assert k3["scale"] == "utm200"
        assert k3["min_x"] == pytest.approx(100000.0)
        assert k3["max_x"] == pytest.approx(200000.0)
        assert k3["centroid_x"] == pytest.approx(150000.0)

    @pytest.mark.asyncio
    async def test_populate_updates_metadata(self, tmp_path: object) -> None:
        """ref_metadata päivittyy oikein."""
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            await p.populate()

        row = conn.execute(
            "SELECT * FROM ref_metadata WHERE name = 'map_sheets'"
        ).fetchone()
        assert row is not None
        assert row["record_count"] == 3
        assert row["version"]  # date string

    @pytest.mark.asyncio
    async def test_populate_idempotent(self, tmp_path: object) -> None:
        """Toinen ajo ei luo duplikaatteja."""
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            await p.populate()
            count = await p.populate()

        assert count == 3
        total = conn.execute("SELECT COUNT(*) FROM ref_map_sheets").fetchone()[0]
        assert total == 3

    @pytest.mark.asyncio
    async def test_populate_from_existing_gpkg(self, tmp_path: object) -> None:
        """Ohittaa latauksen jos gpkg on jo olemassa."""
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with (
            patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path),
            patch.object(p, "_make_client") as mock_make,
        ):
            count = await p.populate()
            # HTTP-asiakasta ei kutsuttu koska tiedosto oli jo olemassa
            mock_make.assert_not_called()

        assert count == 3

    @pytest.mark.asyncio
    async def test_downloads_if_gpkg_missing(self, tmp_path: object) -> None:
        """Lataa zipin verkosta jos gpkg puuttuu."""
        gpkg_path = tmp_path / "boundaries" / "karttalehtijako.gpkg"  # type: ignore[operator]
        zip_bytes = _create_mini_gpkg_zip()

        mock_resp = MagicMock()
        mock_resp.content = zip_bytes
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with (
            patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path),
            patch.object(p, "_make_client") as mock_make,
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await p.populate()

        assert gpkg_path.exists()
        assert count == 3

    @pytest.mark.asyncio
    async def test_http_error_raises(self, tmp_path: object) -> None:
        """HTTP-virhe nostaa poikkeuksen."""
        gpkg_path = tmp_path / "boundaries" / "karttalehtijako.gpkg"  # type: ignore[operator]

        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp,
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)
        p.max_retries = 1
        p.request_delay = 0

        with (
            patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path),
            patch.object(p, "_make_client") as mock_make,
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(httpx.HTTPStatusError):
                await p.populate()

    @pytest.mark.asyncio
    async def test_corrupt_zip_raises(self, tmp_path: object) -> None:
        """Korruptoitunut zip nostaa poikkeuksen."""
        gpkg_path = tmp_path / "boundaries" / "karttalehtijako.gpkg"  # type: ignore[operator]

        mock_resp = MagicMock()
        mock_resp.content = b"not a zip file"
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with (
            patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path),
            patch.object(p, "_make_client") as mock_make,
        ):
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(zipfile.BadZipFile):
                await p.populate()


class TestMapSheetIsPopulated:
    def test_not_populated_initially(self) -> None:
        p = MapSheetPopulator(conn=_memory_db())
        assert not p.is_populated()

    @pytest.mark.asyncio
    async def test_is_populated_after_run(self, tmp_path: object) -> None:
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            await p.populate()
            assert p.is_populated()

    @pytest.mark.asyncio
    async def test_not_populated_without_gpkg(self, tmp_path: object) -> None:
        """Metadata on ok mutta gpkg puuttuu → ei populoitu."""
        gpkg_path = tmp_path / "karttalehtijako.gpkg"  # type: ignore[operator]
        _create_mini_gpkg(str(gpkg_path))

        conn = _memory_db()
        p = MapSheetPopulator(conn=conn)

        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            await p.populate()

        # Poista gpkg, metadata on yhä paikallaan
        gpkg_path.unlink()
        with patch("aura.populators.map_sheets.GPKG_PATH", gpkg_path):
            assert not p.is_populated()
