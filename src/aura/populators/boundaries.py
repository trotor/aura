"""Hallinnolliset rajat GeoJSON-muodossa (MML / samilaine/hallinnollisetrajat)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aura.populators.base import BasePopulator

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/reference/rajat")

SOURCES: dict[str, str] = {
    "kunnat.geojson": (
        "https://raw.githubusercontent.com/samilaine/hallinnollisetrajat"
        "/main/kuntarajat.json"
    ),
    "maakunnat.geojson": (
        "https://raw.githubusercontent.com/samilaine/hallinnollisetrajat"
        "/main/maakuntarajat.json"
    ),
}


class BoundaryPopulator(BasePopulator):
    """Populoi hallinnolliset rajat GeoJSON-tiedostoina."""

    name = "boundaries"
    description = "Hallinnolliset rajat — kunta- ja maakuntarajat GeoJSON"
    source_url = "https://github.com/samilaine/hallinnollisetrajat"

    async def populate(self) -> int:
        """Lataa GeoJSON-tiedostot ja tallenna data/reference/rajat/-kansioon."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        total_features = 0

        async with self._make_client(timeout=60.0) as client:
            for filename, url in SOURCES.items():
                logger.info("[%s] Ladataan %s", self.name, url)
                resp = await self._fetch(client, url)
                geojson: dict[str, Any] = resp.json()

                _validate_geojson(geojson, url)

                features = geojson.get("features", [])
                total_features += len(features)

                target = DATA_DIR / filename
                target.write_text(
                    json.dumps(geojson, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info(
                    "[%s] %s: %d featurea → %s",
                    self.name, filename, len(features), target,
                )

        version = datetime.now(UTC).strftime("%Y-%m-%d")
        self._update_metadata(total_features, version=version)
        logger.info(
            "[%s] Tallennettu %d featurea yhteensä", self.name, total_features,
        )
        return total_features

    def is_populated(self) -> bool:
        """Tarkista sekä metadata että tiedostot."""
        if not super().is_populated():
            return False
        return all((DATA_DIR / f).exists() for f in SOURCES)


def _validate_geojson(data: dict[str, Any], url: str) -> None:
    """Varmista että data on validi GeoJSON FeatureCollection."""
    if data.get("type") != "FeatureCollection":
        msg = f"GeoJSON-tyyppi ei ole FeatureCollection: {data.get('type')} ({url})"
        raise ValueError(msg)
    features = data.get("features")
    if not isinstance(features, list) or len(features) == 0:
        msg = f"GeoJSON ei sisällä featureja: {url}"
        raise ValueError(msg)
