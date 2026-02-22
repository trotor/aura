"""TM35-karttalehtijako — MML:n karttalehtijako GeoPackagesta."""

from __future__ import annotations

import io
import logging
import sqlite3
import struct
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from aura.populators.base import BasePopulator

logger = logging.getLogger(__name__)

GPKG_PATH = Path("data/boundaries/karttalehtijako.gpkg")

DOWNLOAD_URL = (
    "https://kartat.kapsi.fi/files/karttalehtijako_ruudukko"
    "/kaikki/etrs89/gpkg/TM35_karttalehtijako_GeoPackage.zip"
)

# Tasot jotka luetaan — riittävä kattavuus (~31k riviä)
SCALES = ("utm200", "utm50", "utm25", "utm10")

BATCH_SIZE = 5000


def _parse_gpkg_envelope(
    blob: bytes,
) -> tuple[float, float, float, float] | None:
    """Parsii GeoPackage binary geometrian envelope (bbox).

    Palauttaa (min_x, min_y, max_x, max_y) tai None.
    """
    if blob is None or len(blob) < 8:
        return None

    # GeoPackage binary header: "GP" + version(1) + flags(1) + srs_id(4)
    magic = blob[0:2]
    if magic != b"GP":
        return None

    flags = blob[3]
    byte_order = "<" if (flags & 0x01) else ">"
    envelope_type = (flags >> 1) & 0x07

    if envelope_type == 0:
        return None

    # Envelope alkaa offsetista 8
    # Tyyppi 1: minx, maxx, miny, maxy (4 doublea)
    envelope_start = 8
    if envelope_type in (1, 2, 3, 4):
        if len(blob) < envelope_start + 32:
            return None
        minx, maxx, miny, maxy = struct.unpack_from(
            f"{byte_order}dddd", blob, envelope_start,
        )
        return (minx, miny, maxx, maxy)

    return None


class MapSheetPopulator(BasePopulator):
    """Populoi TM35-karttalehtijako ref_map_sheets-tauluun."""

    name = "map_sheets"
    description = "TM35-karttalehtijako — karttalehdet bbox-tiedoilla"
    source_url = (
        "https://kartat.kapsi.fi/files/karttalehtijako_ruudukko/"
    )

    async def populate(self) -> int:
        """Lataa GeoPackage ja tallenna karttalehdet tietokantaan."""
        await self._ensure_gpkg()
        return self._load_sheets()

    async def _ensure_gpkg(self) -> None:
        """Lataa GeoPackage jos sitä ei ole paikallisesti."""
        if GPKG_PATH.exists():
            logger.info(
                "[%s] GeoPackage löytyy: %s", self.name, GPKG_PATH,
            )
            return

        GPKG_PATH.parent.mkdir(parents=True, exist_ok=True)

        logger.info("[%s] Ladataan %s", self.name, DOWNLOAD_URL)
        async with self._make_client(timeout=120.0) as client:
            resp = await self._fetch(client, DOWNLOAD_URL)

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            gpkg_names = [
                n for n in zf.namelist() if n.endswith(".gpkg")
            ]
            if not gpkg_names:
                msg = "Zip-tiedosto ei sisällä .gpkg-tiedostoa"
                raise ValueError(msg)

            gpkg_name = gpkg_names[0]
            logger.info(
                "[%s] Puretaan %s → %s",
                self.name, gpkg_name, GPKG_PATH,
            )
            with zf.open(gpkg_name) as src, open(GPKG_PATH, "wb") as dst:
                dst.write(src.read())

    def _load_sheets(self) -> int:
        """Lue karttalehdet GeoPackagesta ja upsertoi tietokantaan."""
        gpkg_conn = sqlite3.connect(str(GPKG_PATH))
        total = 0

        try:
            for scale in SCALES:
                table_exists = gpkg_conn.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name=?",
                    (scale,),
                ).fetchone()
                if not table_exists:
                    logger.debug(
                        "[%s] Taso %s puuttuu", self.name, scale,
                    )
                    continue

                rows = gpkg_conn.execute(
                    f'SELECT lehtitunnus, geometry FROM "{scale}" '  # noqa: S608
                    "WHERE lehtitunnus IS NOT NULL",
                ).fetchall()

                batch: list[
                    tuple[
                        str, str,
                        float, float, float, float,
                        float, float,
                    ]
                ] = []
                for sheet_id, geom_blob in rows:
                    bbox = _parse_gpkg_envelope(geom_blob)
                    if bbox is None:
                        continue
                    min_x, min_y, max_x, max_y = bbox
                    cx = (min_x + max_x) / 2.0
                    cy = (min_y + max_y) / 2.0
                    batch.append((
                        sheet_id, scale,
                        min_x, min_y, max_x, max_y, cx, cy,
                    ))

                    if len(batch) >= BATCH_SIZE:
                        self._upsert_batch(batch)
                        batch = []

                if batch:
                    self._upsert_batch(batch)

                total += len(rows)
                logger.info(
                    "[%s] %s: %d lehteä", self.name, scale, len(rows),
                )
        finally:
            gpkg_conn.close()

        version = datetime.now(UTC).strftime("%Y-%m-%d")
        self._update_metadata(total, version=version)
        logger.info(
            "[%s] Tallennettu %d lehteä yhteensä", self.name, total,
        )
        return total

    def _upsert_batch(
        self,
        batch: list[
            tuple[str, str, float, float, float, float, float, float]
        ],
    ) -> None:
        """Upsertoi erä karttalehtia tietokantaan."""
        self.conn.executemany(
            """
            INSERT INTO ref_map_sheets
                (id, scale, min_x, min_y, max_x, max_y,
                 centroid_x, centroid_y)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                scale = excluded.scale,
                min_x = excluded.min_x,
                min_y = excluded.min_y,
                max_x = excluded.max_x,
                max_y = excluded.max_y,
                centroid_x = excluded.centroid_x,
                centroid_y = excluded.centroid_y,
                updated_at = datetime('now')
            """,
            batch,
        )
        self.conn.commit()

    def is_populated(self) -> bool:
        """Tarkista sekä metadata että gpkg-tiedoston olemassaolo."""
        if not super().is_populated():
            return False
        return GPKG_PATH.exists()
