"""Harvester taustakarttapalveluille (MML/Kapsi + OpenStreetMap)."""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

TILE_SERVICES: list[dict[str, Any]] = [
    {
        "id": "kapsi-peruskartta",
        "title": "MML Peruskartta",
        "description": (
            "Maanmittauslaitoksen peruskartta TMS-tiilipalveluna."
            " Mittakaavat z0–z18. Ylläpito: kartat.kapsi.fi (MML:n aineisto)."
        ),
        "url_template": "https://tiles.kartat.kapsi.fi/peruskartta/{z}/{x}/{y}.jpg",
        "keywords": ["kartta", "peruskartta", "MML", "taustakartta"],
        "organization_id": "mml",
        "organization_title": "Maanmittauslaitos",
        "license_id": "cc-by-4.0",
        "license_title": "CC BY 4.0",
    },
    {
        "id": "kapsi-taustakartta",
        "title": "MML Taustakartta",
        "description": (
            "Maanmittauslaitoksen taustakartta TMS-tiilipalveluna."
            " Yksinkertaistettu, vaalea pohjakartta. Mittakaavat z0–z18."
        ),
        "url_template": "https://tiles.kartat.kapsi.fi/taustakartta/{z}/{x}/{y}.jpg",
        "keywords": ["kartta", "taustakartta", "MML", "pohjakartta"],
        "organization_id": "mml",
        "organization_title": "Maanmittauslaitos",
        "license_id": "cc-by-4.0",
        "license_title": "CC BY 4.0",
    },
    {
        "id": "kapsi-ortokuva",
        "title": "MML Ortokuva",
        "description": (
            "Maanmittauslaitoksen ortokuva (ilmakuva) TMS-tiilipalveluna."
            " Koko Suomen kattava ilmakuvamosaiikki."
        ),
        "url_template": "https://tiles.kartat.kapsi.fi/ortokuva/{z}/{x}/{y}.jpg",
        "keywords": ["kartta", "ortokuva", "ilmakuva", "MML"],
        "organization_id": "mml",
        "organization_title": "Maanmittauslaitos",
        "license_id": "cc-by-4.0",
        "license_title": "CC BY 4.0",
    },
    {
        "id": "osm-standard",
        "title": "OpenStreetMap",
        "description": (
            "OpenStreetMap-standardikartta TMS-tiilipalveluna."
            " Yhteisöllisesti tuotettu maailmankartta. Mittakaavat z0–z19."
        ),
        "url_template": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "keywords": ["kartta", "OpenStreetMap", "OSM", "taustakartta"],
        "organization_id": "osm",
        "organization_title": "OpenStreetMap Foundation",
        "license_id": "ODbL-1.0",
        "license_title": "ODbL",
    },
]


class TaustakartatHarvester(BaseHarvester):
    """Kerää taustakarttatiilipalvelut (MML/Kapsi + OpenStreetMap).

    Staattinen konfiguraatioharvester. Rekisteröi TMS-tiilipalvelut
    joita voi käyttää karttasovellusten pohjakarttoina.
    """

    name = "taustakartat"
    description = "Taustakartat — MML (Kapsi) ja OpenStreetMap -tiilipalvelut"
    url = "https://kartat.kapsi.fi"

    async def harvest(self) -> int:
        count = 0

        for svc in TILE_SERVICES:
            dataset = self._tile_to_dataset(svc)
            upsert_dataset(self.conn, dataset)
            count += 1

        self.conn.commit()
        logger.info("[taustakartat] Harvest valmis: %d datasettiä", count)
        return count

    def _tile_to_dataset(self, svc: dict[str, Any]) -> Dataset:
        svc_id = svc["id"]
        coverage = ["Suomi"] if svc_id.startswith("kapsi") else ["Maailma"]

        return Dataset(
            id=f"taustakartat-{svc_id}",
            name=f"taustakartat-{svc_id}",
            title=svc["title"],
            title_fi=svc["title"],
            notes_fi=svc["description"],
            organization_id=svc["organization_id"],
            organization_name=svc["organization_id"],
            organization_title=svc["organization_title"],
            keywords_fi=svc.get("keywords", ["kartta"]),
            license_id=svc["license_id"],
            license_title=svc["license_title"],
            collection_type="Open Data",
            geographical_coverage=coverage,
            source=self.name,
            num_resources=1,
            resources=[
                Resource(
                    id=f"taustakartat-{svc_id}-tms",
                    name=f"{svc['title']} (TMS)",
                    name_fi=f"{svc['title']} — TMS-tiilipalvelu",
                    format="TMS",
                    url=svc["url_template"],
                ),
            ],
            estimated_size_bytes=5_000_000_000,  # ~5 GB per tiilipalvelu
        )
