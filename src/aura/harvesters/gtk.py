"""Harvester Geologian tutkimuskeskuksen (GTK) paikkatietorajapinnoille."""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

ARCGIS_BASE = "https://gtkdata.gtk.fi/arcgis/services/Rajapinnat"

# WFS-palvelut (tukevat feature-kyselyjä)
WFS_SERVICES: list[dict[str, Any]] = [
    {
        "id": "kalliopera",
        "endpoint": "GTK_Kalliopera_WFS/MapServer/WFSServer",
        "title": "Kallioperäkartta",
        "description": (
            "Suomen kallioperän geologinen kartta-aineisto."
            " Kivilajitiedot, rakennegeologia ja malmihavainnot."
        ),
        "keywords": ["geologia", "kallioperä", "kivilaji", "GTK"],
        "estimated_size_gb": 2,
    },
    {
        "id": "maapera",
        "endpoint": "GTK_Maapera_WFS/MapServer/WFSServer",
        "title": "Maaperäkartta",
        "description": (
            "Suomen maaperäkartta-aineisto."
            " Maalajitiedot, kerrostumien paksuus ja pohjavesialueet."
        ),
        "keywords": ["geologia", "maaperä", "maalaji", "GTK"],
        "estimated_size_gb": 3,
    },
    {
        "id": "kiviainesvarannot",
        "endpoint": "GTK_Kiviainesvarannot_WFS/MapServer/WFSServer",
        "title": "Kiviainesvarannot",
        "description": (
            "Kiviainesten (sora, hiekka, kalliokiviaines) varannot ja ottopaikat."
        ),
        "keywords": ["geologia", "kiviaines", "sora", "hiekka", "GTK"],
        "estimated_size_gb": 0.5,
    },
]

# WMS-only-palvelut (vain karttakuvia, ei feature-dataa)
WMS_SERVICES: list[dict[str, Any]] = [
    {
        "id": "geofysiikka",
        "title": "Geofysikaaliset kartat",
        "description": (
            "Geofysikaaliset mittausaineistot: magneettiset, gravimetriset"
            " ja sähköiset kartat."
        ),
        "keywords": ["geofysiikka", "magneettikenttä", "gravimetria", "GTK"],
        "estimated_size_gb": 1,
    },
    {
        "id": "pohjatutkimukset",
        "title": "Pohjatutkimukset",
        "description": (
            "Pohjatutkimusaineistot: kairaukset, näytteenotot"
            " ja laboratoriotulokset."
        ),
        "keywords": ["pohjatutkimus", "kairaus", "geotekniikka", "GTK"],
        "estimated_size_gb": 0.5,
    },
]


class GtkHarvester(BaseHarvester):
    """Kerää GTK:n avoimet geologiset paikkatietoaineistot.

    Geologian tutkimuskeskus (GTK) tarjoaa Suomen kallioperä-, maaperä-
    ja kiviainestietoja ArcGIS-rajapintojen kautta.
    """

    name = "gtk"
    description = "Geologian tutkimuskeskus — kallioperä-, maaperä- ja kiviainestiedot"
    url = "https://www.gtk.fi/palvelut/aineistot-ja-myynti/avoimet-aineistot/"

    async def harvest(self) -> int:
        count = 0

        for svc in WFS_SERVICES:
            dataset = self._wfs_to_dataset(svc)
            upsert_dataset(self.conn, dataset)
            count += 1

        for svc in WMS_SERVICES:
            dataset = self._wms_to_dataset(svc)
            upsert_dataset(self.conn, dataset)
            count += 1

        self.conn.commit()
        logger.info("[gtk] Harvest valmis: %d datasettiä", count)
        return count

    def _wfs_to_dataset(self, svc: dict[str, Any]) -> Dataset:
        svc_id = svc["id"]
        endpoint_url = f"{ARCGIS_BASE}/{svc['endpoint']}"
        size_bytes = int(svc.get("estimated_size_gb", 1) * 1024 * 1024 * 1024)

        return self._make_dataset(
            id=f"gtk-{svc_id}",
            name=f"gtk-{svc_id}",
            title=svc["title"],
            title_fi=svc["title"],
            notes_fi=svc["description"],
            organization_id="gtk",
            organization_name="gtk",
            organization_title="Geologian tutkimuskeskus",
            keywords_fi=svc.get("keywords", ["geologia"]),
            num_resources=2,
            resources=[
                Resource(
                    id=f"gtk-{svc_id}-wfs",
                    name=f"{svc['title']} (WFS)",
                    name_fi=f"{svc['title']} — WFS-rajapinta",
                    format="WFS",
                    url=endpoint_url,
                ),
                Resource(
                    id=f"gtk-{svc_id}-wms",
                    name=f"{svc['title']} (WMS)",
                    name_fi=f"{svc['title']} — WMS-karttapalvelu",
                    format="WMS",
                    url=endpoint_url.replace("WFSServer", "WMSServer"),
                ),
            ],
            estimated_size_bytes=size_bytes,
        )

    def _wms_to_dataset(self, svc: dict[str, Any]) -> Dataset:
        svc_id = svc["id"]
        size_bytes = int(svc.get("estimated_size_gb", 1) * 1024 * 1024 * 1024)

        return self._make_dataset(
            id=f"gtk-{svc_id}",
            name=f"gtk-{svc_id}",
            title=svc["title"],
            title_fi=svc["title"],
            notes_fi=svc["description"],
            organization_id="gtk",
            organization_name="gtk",
            organization_title="Geologian tutkimuskeskus",
            keywords_fi=svc.get("keywords", ["geologia"]),
            num_resources=1,
            resources=[
                Resource(
                    id=f"gtk-{svc_id}-wms",
                    name=f"{svc['title']} (WMS)",
                    name_fi=f"{svc['title']} — WMS-karttapalvelu",
                    format="WMS",
                    url=f"{ARCGIS_BASE}/{svc_id}",
                ),
            ],
            estimated_size_bytes=size_bytes,
        )
