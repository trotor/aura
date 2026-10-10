"""Paikallinen kiinteistöindeksi: kiinteistötunnus → palstojen suorakaiteet.

Lähde on MML:n kiinteistörekisterikartta (vektori, CC BY 4.0), jonka
Kapsi.fi peilaa Shapefileinä 1:10 000 -karttalehdittäin
(``kartat.kapsi.fi/files/kiinteistorekisterikartta``). Peili ei vaadi
API-avainta, ja avoimen lisenssin aineistoa saa jakaa edelleen, joten tämä
on hyväksytty avaimeton reitti; MML:n omat rajapinnat vaativat avaimen.

Tunnuksesta ei näe sijaintia, joten indeksi rakennetaan kunnittain:
``aura parcels <kunta>`` hakee kunnan suorakaiteen karttalehdet ja lukee
niiden ``palstaalue``-tason. Palsta leikkautuu lehtien reunoilla, joten sen
osat yhdistetään palstan tunnisteella yhdeksi suorakaiteeksi.

Indeksi on paikallinen tiedosto (oletus ``data/boundaries/kiinteistot.sqlite``,
gitignoressa, ``AURA_KIINTEISTOT_DB``). Omistajatietoja aineistossa ei ole.
"""

from __future__ import annotations

import asyncio
import io
import os
import sqlite3
import struct
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from aura.constants import user_agent
from aura.kiinteisto import Bbox, Parcel
from aura.net import read_capped

DEFAULT_PATH = Path("data/boundaries/kiinteistot.sqlite")
KAPSI = "https://kartat.kapsi.fi/files/kiinteistorekisterikartta/avoin/karttalehdittain/tm35fin/shp"
PROVIDER = "MML kiinteistörekisterikartta (CC BY 4.0), Kapsi.fi-peili"

_LIMIT = 50 * 1024 * 1024
_CONCURRENCY = 6
_TIMEOUT = 60.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS palstat (
    palsta_id INTEGER PRIMARY KEY,
    tunnus    TEXT NOT NULL,
    kunta     TEXT NOT NULL,
    min_x REAL, min_y REAL, max_x REAL, max_y REAL
);
CREATE INDEX IF NOT EXISTS palstat_tunnus ON palstat (tunnus);
CREATE TABLE IF NOT EXISTS kunnat (
    kunta  TEXT PRIMARY KEY,
    haettu TEXT NOT NULL,
    lehtia INTEGER NOT NULL,
    palstoja INTEGER NOT NULL
);
"""


def index_path() -> Path:
    """Indeksin sijainti: ``AURA_KIINTEISTOT_DB`` tai oletus."""
    return Path(os.environ.get("AURA_KIINTEISTOT_DB") or DEFAULT_PATH)


def sheet_url(sheet: str) -> str:
    """Karttalehden zip Kapsissa: ``K2344H`` → ``…/shp/K23/K2344H.zip``."""
    return f"{KAPSI}/{sheet[:3]}/{sheet}.zip"


def sheets_for_bbox(conn: sqlite3.Connection, bbox: Bbox) -> list[str]:
    """1:10 000 -karttalehdet (``ref_map_sheets``), jotka leikkaavat suorakaidetta."""
    rows = conn.execute(
        "SELECT id FROM ref_map_sheets WHERE scale = 'utm10'"
        " AND max_x > ? AND min_x < ? AND max_y > ? AND min_y < ? ORDER BY id",
        (bbox[0], bbox[2], bbox[1], bbox[3]),
    ).fetchall()
    return [str(r[0]) for r in rows]


def _shp_bboxes(data: bytes) -> list[Bbox | None]:
    """Shapefilen tietueiden suorakaiteet; tyhjä muoto → None.

    Polygonin tietueen alussa on valmis suorakaide, joten pisteitä ei lueta.
    """
    out: list[Bbox | None] = []
    pos = 100
    while pos + 8 <= len(data):
        length = struct.unpack(">i", data[pos + 4 : pos + 8])[0] * 2
        content = data[pos + 8 : pos + 8 + length]
        pos += 8 + length
        if len(content) < 36 or struct.unpack("<i", content[:4])[0] == 0:
            out.append(None)
            continue
        x0, y0, x1, y1 = struct.unpack("<4d", content[4:36])
        out.append((x0, y0, x1, y1))
    return out


def _dbf_rows(data: bytes) -> list[dict[str, str]]:
    """dBASE-tietueet merkkijonoina; poistetuiksi merkityt mukana (järjestys)."""
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields: list[tuple[str, int]] = []
    for pos in range(32, header_len - 1, 32):
        name = data[pos : pos + 11].split(b"\0")[0].decode("latin-1")
        fields.append((name, data[pos + 16]))
    rows = []
    for i in range(count):
        pos = header_len + i * record_len + 1
        row = {}
        for name, size in fields:
            row[name] = data[pos : pos + size].decode("latin-1").strip()
            pos += size
        rows.append(row)
    return rows


def read_parcels(zip_bytes: bytes) -> list[tuple[int, str, str, Bbox]]:
    """Karttalehden palstat: (palsta_id, tunnus, kunta, suorakaide)."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        shp = next((n for n in names if n.lower().endswith("_palstaalue.shp")), None)
        if shp is None:
            return []
        dbf = shp[:-4] + ".dbf"
        if dbf not in names:
            return []
        boxes = _shp_bboxes(z.read(shp))
        rows = _dbf_rows(z.read(dbf))
    out = []
    for box, row in zip(boxes, rows, strict=False):
        tunnus = row.get("TUNNUS", "")
        if box is None or len(tunnus) != 14 or not row.get("ID", "").isdigit():
            continue
        out.append((int(row["ID"]), tunnus, row.get("KTUNNUS", "") or tunnus[:3], box))
    return out


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # WAL: palvelimella kysely lukee indeksiä samalla kun toinen kunta latautuu.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


@dataclass(frozen=True)
class LoadSummary:
    kunta: str
    sheets: int
    parcels: int
    missing: int


async def _fetch_sheet(
    client: httpx.AsyncClient, sheet: str, gate: asyncio.Semaphore
) -> list[tuple[int, str, str, Bbox]] | None:
    """Lehden palstat, tai None jos lehteä ei ole (merialue, ei kiinteistöjä).

    Jäsennys heti latauksen perään ja säikeessä: koko kunnan zipit eivät ole
    yhtä aikaa muistissa, eikä jäsennys pysäytä palvelimen tapahtumasilmukkaa.
    """
    async with gate:
        response, body = await read_capped(client, sheet_url(sheet), limit=_LIMIT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return await asyncio.to_thread(read_parcels, body)


def _write_index(
    path: Path, merged: dict[int, tuple[str, str, Bbox]], kunnat: Sequence[str], sheets: int
) -> None:
    """Kirjoita palstat ja ladatut kunnat indeksiin (erillinen tiedosto, ei aura.db)."""
    db = _connect(path)
    try:
        with db:
            db.executemany(
                """
                INSERT INTO palstat (palsta_id, tunnus, kunta, min_x, min_y, max_x, max_y)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(palsta_id) DO UPDATE SET
                    tunnus = excluded.tunnus, kunta = excluded.kunta,
                    min_x = min(palstat.min_x, excluded.min_x),
                    min_y = min(palstat.min_y, excluded.min_y),
                    max_x = max(palstat.max_x, excluded.max_x),
                    max_y = max(palstat.max_y, excluded.max_y)
                """,
                [(pid, t, k, *b) for pid, (t, k, b) in merged.items()],
            )
            today = datetime.now(UTC).date().isoformat()
            db.executemany(
                "INSERT OR REPLACE INTO kunnat (kunta, haettu, lehtia, palstoja)"
                " VALUES (?, ?, ?, ?)",
                [(code, today, sheets, len(merged)) for code in kunnat],
            )
    finally:
        db.close()


async def load_municipality(
    conn: sqlite3.Connection,
    kunta: str,
    *,
    path: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    aliases: Sequence[str] = (),
) -> LoadSummary:
    """Lataa kunnan kiinteistöjen palstat indeksiin. ``kunta`` = kuntakoodi.

    ``aliases`` kirjataan ladatuiksi samalla: lakkautetun kunnan koodi, jonka
    alue ladattiin seuraajakunnan rajoilla.
    """
    row = conn.execute(
        "SELECT min_x, min_y, max_x, max_y FROM ref_municipalities WHERE code = ?", (kunta,)
    ).fetchone()
    if row is None or row[0] is None:
        raise ValueError(
            f"Kunnan {kunta} rajoja ei ole kannassa. Aja: aura populate municipality_bbox"
        )
    sheets = sheets_for_bbox(conn, (row[0], row[1], row[2], row[3]))
    gate = asyncio.Semaphore(_CONCURRENCY)
    # Osoite on kiinteä (Kapsi), ei käyttäjän antama.
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": user_agent()}, transport=transport
    ) as client:
        sheet_parcels = await asyncio.gather(*(_fetch_sheet(client, s, gate) for s in sheets))

    merged: dict[int, tuple[str, str, Bbox]] = {}
    for parcels in sheet_parcels:
        for pid, tunnus, kunta_code, box in parcels or ():
            if pid in merged:
                old = merged[pid][2]
                box = (
                    min(old[0], box[0]),
                    min(old[1], box[1]),
                    max(old[2], box[2]),
                    max(old[3], box[3]),
                )
            merged[pid] = (tunnus, kunta_code, box)

    _write_index(path or index_path(), merged, (kunta, *aliases), len(sheets))
    missing = sum(1 for b in sheet_parcels if b is None)
    return LoadSummary(
        kunta=kunta, sheets=len(sheets) - missing, parcels=len(merged), missing=missing
    )


def loaded(path: Path, kunta: str) -> bool:
    """Onko kunnan kiinteistöt ladattu indeksiin."""
    if not path.exists():
        return False
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return db.execute("SELECT 1 FROM kunnat WHERE kunta = ?", (kunta,)).fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        db.close()


def lookup(path: Path, tunnus: str) -> list[Parcel]:
    """Tunnuksen palstat indeksistä; tyhjä jos indeksiä tai tunnusta ei ole."""
    if not path.exists():
        return []
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT min_x, min_y, max_x, max_y FROM palstat WHERE tunnus = ? ORDER BY palsta_id",
            (tunnus,),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()
    return [Parcel(bbox=(r[0], r[1], r[2], r[3])) for r in rows]
