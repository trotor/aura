"""Paikallinen kiinteistöindeksi Kapsi.fi:n MML-peilistä (ei API-avainta).

Kapsi jakaa MML:n kiinteistörekisterikartan (CC BY 4.0) Shapefileinä
1:10 000 -karttalehdittäin. Palstat leikkautuvat lehtien reunoilla, joten
saman palstan osat yhdistetään yhdeksi suorakaiteeksi.
"""

from __future__ import annotations

import io
import sqlite3
import struct
import zipfile
from pathlib import Path

import httpx
import pytest

from aura import kiinteisto
from aura.kiinteisto import Parcel
from aura.kiinteisto_index import (
    load_municipality,
    lookup,
    read_parcels,
    sheet_url,
    sheets_for_bbox,
)


def _shp(boxes: list[tuple[float, float, float, float] | None]) -> bytes:
    records = b""
    for i, box in enumerate(boxes, start=1):
        if box is None:
            content = struct.pack("<i", 0)
        else:
            # Polygoni: tyyppi, bbox, osat=1, pisteet=1, osan alku, yksi piste.
            content = struct.pack("<i4dii", 5, *box, 1, 1) + struct.pack("<i2d", 0, box[0], box[1])
        records += struct.pack(">ii", i, len(content) // 2) + content
    header = struct.pack(">i", 9994) + b"\0" * 20 + struct.pack(">i", (100 + len(records)) // 2)
    header += struct.pack("<ii", 1000, 5) + b"\0" * 64
    return header + records


def _dbf(rows: list[tuple[int, str, str]]) -> bytes:
    fields = [("ID", "N", 9), ("TPTEKSTI", "C", 20), ("TUNNUS", "C", 20), ("KTUNNUS", "C", 3)]
    rlen = 1 + sum(f[2] for f in fields)
    hlen = 32 + 32 * len(fields) + 1
    out = struct.pack("<BBBBIHH", 3, 126, 1, 1, len(rows), hlen, rlen) + b"\0" * 20
    for name, kind, size in fields:
        out += name.encode().ljust(11, b"\0") + kind.encode() + b"\0" * 4 + bytes([size])
        out += b"\0" * 15
    out += b"\r"
    for pid, tunnus, kunta in rows:
        values = [
            str(pid).rjust(9),
            kiinteisto.format_tunnus(tunnus).ljust(20),
            tunnus.ljust(20),
            kunta,
        ]
        out += b" " + "".join(values).encode("latin-1")
    return out + b"\x1a"


def _zip(
    sheet: str,
    boxes: list[tuple[float, float, float, float] | None],
    rows: list[tuple[int, str, str]],
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{sheet}_palstaalue.shp", _shp(boxes))
        z.writestr(f"{sheet}_palstaalue.dbf", _dbf(rows))
        z.writestr(f"{sheet}_kiinteistoraja.shp", _shp([]))
    return buf.getvalue()


T1 = "43540100030006"
T2 = "43540100040001"


def test_shapefilen_palstat_ja_suorakaiteet() -> None:
    data = _zip(
        "K1111A",
        [(0, 0, 10, 10), None, (20, 20, 30, 30)],
        [(1, T1, "435"), (9, T1, "435"), (2, T2, "435")],
    )
    parcels = read_parcels(data)
    assert parcels == [
        (1, T1, "435", (0.0, 0.0, 10.0, 10.0)),
        (2, T2, "435", (20.0, 20.0, 30.0, 30.0)),
    ]


@pytest.fixture()
def aura_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE ref_map_sheets (id TEXT, scale TEXT,"
        " min_x REAL, min_y REAL, max_x REAL, max_y REAL)"
    )
    conn.executemany(
        "INSERT INTO ref_map_sheets VALUES (?, 'utm10', ?, ?, ?, ?)",
        [
            ("K1111A", 0, 0, 6000, 6000),
            ("K1111B", 6000, 0, 12000, 6000),
            ("K9999A", 90000, 0, 96000, 6000),
        ],
    )
    conn.execute(
        "CREATE TABLE ref_municipalities (code TEXT, name_fi TEXT,"
        " min_x REAL, min_y REAL, max_x REAL, max_y REAL)"
    )
    conn.execute("INSERT INTO ref_municipalities VALUES ('435', 'Luhanka', 100, 100, 11000, 5000)")
    conn.execute("CREATE TABLE ref_areas (code TEXT, level TEXT, name_fi TEXT)")
    return conn


def test_kunnan_karttalehdet(aura_db: sqlite3.Connection) -> None:
    assert sheets_for_bbox(aura_db, (100, 100, 11000, 5000)) == ["K1111A", "K1111B"]
    assert sheet_url("K1111A").endswith("/tm35fin/shp/K11/K1111A.zip")


class _Kapsi(httpx.AsyncBaseTransport):
    """K1111A ja K1111B jakavat palstan 1 (leikattu lehden reunalla)."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        name = request.url.path.rsplit("/", 1)[-1]
        if name == "K1111A.zip":
            body = _zip("K1111A", [(5000, 100, 6000, 900)], [(1, T1, "435")])
        elif name == "K1111B.zip":
            body = _zip(
                "K1111B",
                [(6000, 200, 6500, 800), (7000, 7000, 7100, 7100)],
                [(1, T1, "435"), (2, T2, "435")],
            )
        else:
            return httpx.Response(404, request=request)
        return httpx.Response(200, content=body, request=request)


@pytest.mark.asyncio
async def test_lataus_yhdistaa_lehtien_reunalla_leikatut_palstat(
    aura_db: sqlite3.Connection, tmp_path: Path
) -> None:
    index = tmp_path / "kiinteistot.sqlite"
    summary = await load_municipality(aura_db, "435", path=index, transport=_Kapsi())
    assert summary.sheets == 2 and summary.parcels == 2
    assert lookup(index, T1) == [Parcel(bbox=(5000.0, 100.0, 6500.0, 900.0))]
    assert lookup(index, "00000000000000") == []


@pytest.mark.asyncio
async def test_find_parcels_kayttaa_indeksia_ensin(
    aura_db: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = tmp_path / "kiinteistot.sqlite"
    await load_municipality(aura_db, "435", path=index, transport=_Kapsi())
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(index))
    result = await kiinteisto.find_parcels(T2)
    assert result.parcels == [Parcel(bbox=(7000.0, 7000.0, 7100.0, 7100.0))]
    assert "Kapsi" in (result.provider or "")


@pytest.mark.asyncio
async def test_ilman_indeksia_ohje_nimeaa_kunnan_ja_komennon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(tmp_path / "puuttuu.sqlite"))
    result = await kiinteisto.find_parcels(T1)
    assert result.parcels == []
    assert "aura parcels 435" in result.hint


# --- Lataus tarvittaessa (julkinen palvelin, 10.10.2026) ------------------


@pytest.mark.asyncio
async def test_puuttuva_kunta_ladataan_ensimmaisella_kyselylla(
    aura_db: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = tmp_path / "kiinteistot.sqlite"
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(index))
    monkeypatch.setattr(kiinteisto, "_successor", lambda conn, code: code)
    import aura.kiinteisto_index as ki

    real = ki.load_municipality
    calls: list[str] = []

    async def load(conn: sqlite3.Connection, kunta: str, **kw: object) -> ki.LoadSummary:
        calls.append(kunta)
        return await real(conn, kunta, transport=_Kapsi(), **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(ki, "load_municipality", load)
    result = await kiinteisto.find_parcels(T2, conn=aura_db)
    assert result.parcels == [Parcel(bbox=(7000.0, 7000.0, 7100.0, 7100.0))]
    assert "ladattiin" in result.note
    # Toinen kysely käyttää valmista indeksiä.
    await kiinteisto.find_parcels(T1, conn=aura_db)
    assert calls == ["435"]


@pytest.mark.asyncio
async def test_lakkautetun_kunnan_tunnus_ladataan_seuraajan_rajoilla(
    aura_db: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(tmp_path / "k.sqlite"))
    monkeypatch.setattr(kiinteisto, "_successor", lambda conn, code: "435")
    import aura.kiinteisto_index as ki

    seen: dict[str, object] = {}

    async def load(conn: sqlite3.Connection, kunta: str, **kw: object) -> ki.LoadSummary:
        seen.update(kunta=kunta, aliases=kw.get("aliases"))
        return ki.LoadSummary(kunta=kunta, sheets=0, parcels=0, missing=0)

    monkeypatch.setattr(ki, "load_municipality", load)
    await kiinteisto.find_parcels("53240100030006", conn=aura_db)
    assert seen == {"kunta": "435", "aliases": ("532",)}


@pytest.mark.asyncio
async def test_automaattilatauksen_voi_kytkea_pois(
    aura_db: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(tmp_path / "k.sqlite"))
    monkeypatch.setenv("AURA_KIINTEISTOT_AUTO", "0")
    result = await kiinteisto.find_parcels(T1, conn=aura_db)
    assert result.parcels == [] and "aura parcels 435" in result.hint


@pytest.mark.asyncio
async def test_kirjoitusvirhe_ei_kaada_kyselya(
    aura_db: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(tmp_path / "k.sqlite"))
    monkeypatch.setattr(kiinteisto, "_successor", lambda conn, code: code)
    import aura.kiinteisto_index as ki

    async def load(conn: sqlite3.Connection, kunta: str, **kw: object) -> ki.LoadSummary:
        raise OSError("read-only file system")

    monkeypatch.setattr(ki, "load_municipality", load)
    result = await kiinteisto.find_parcels(T1, conn=aura_db)
    assert result.parcels == []
    assert result.error and "OSError" in result.error
    assert "aura parcels 435" in result.hint
