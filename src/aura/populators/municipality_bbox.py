"""Kuntien bbox (EPSG:3067) — MML:n kuntajako_1000k.gpkg:sta ref_municipalities-tauluun.

Lukee Kunta-tason geometrioiden envelope-bbox:t (sama GPKG-parseri kuin
map_sheets) ja päivittää olemassa olevat kunnat natcode = code -avaimella.
Ei-destruktiivinen: ei kosketa kuntien muihin kenttiin.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from aura.populators.base import BasePopulator
from aura.populators.map_sheets import _parse_gpkg_envelope

logger = logging.getLogger(__name__)

GPKG_PATH = Path("data/boundaries/kuntajako_1000k.gpkg")

# (min_x, min_y, max_x, max_y)
Bbox = tuple[float, float, float, float]


class MunicipalityBboxPopulator(BasePopulator):
    """Populoi kuntien bbox-tiedot ref_municipalities-tauluun GeoPackagesta."""

    name = "municipality_bbox"
    description = "Kuntien bbox (EPSG:3067) aluerajauksiin"
    source_url = "MML kuntajako_1000k.gpkg"

    async def populate(self) -> int:
        """Lue kuntien bbox:t GeoPackagesta ja päivitä tietokantaan."""
        mapping = self._read_bboxes()
        return self._apply_bboxes(mapping)

    def _read_bboxes(self) -> dict[str, Bbox]:
        """Lue {kuntakoodi: bbox} kuntajako-GeoPackagen Kunta-tasolta."""
        if not GPKG_PATH.exists():
            msg = (
                f"GeoPackage puuttuu: {GPKG_PATH}. "
                "Lataa MML:n kuntajako_1000k.gpkg (ks. README)."
            )
            raise FileNotFoundError(msg)

        gpkg = sqlite3.connect(str(GPKG_PATH))
        try:
            rows = gpkg.execute(
                "SELECT natcode, multipolygon FROM Kunta WHERE natcode IS NOT NULL"
            ).fetchall()
        finally:
            gpkg.close()

        mapping: dict[str, Bbox] = {}
        for natcode, blob in rows:
            bbox = _parse_gpkg_envelope(blob)
            if bbox is None:
                continue
            mapping[str(natcode).zfill(3)] = bbox
        return mapping

    def _apply_bboxes(self, mapping: dict[str, Bbox]) -> int:
        """Päivitä kuntien bbox-sarakkeet. Palauttaa päivitettyjen rivien määrän."""
        updated = 0
        for code, (min_x, min_y, max_x, max_y) in mapping.items():
            cur = self.conn.execute(
                """
                UPDATE ref_municipalities
                SET min_x = ?, min_y = ?, max_x = ?, max_y = ?
                WHERE code = ?
                """,
                (min_x, min_y, max_x, max_y, code),
            )
            updated += cur.rowcount
        self.conn.commit()
        version = datetime.now(UTC).strftime("%Y-%m-%d")
        self._update_metadata(updated, version=version)
        logger.info("[%s] Päivitetty %d kunnan bbox", self.name, updated)
        return updated
