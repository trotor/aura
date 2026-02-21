"""Harvester Ilmatieteen laitoksen (FMI) WFS-rajapinnalle."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

WFS_BASE = "https://opendata.fmi.fi/wfs"
LIST_QUERIES_URL = f"{WFS_BASE}?service=WFS&version=2.0.0&request=ListStoredQueries"

# FMI-kyselyiden kategoriat tunnisteen perusteella
CATEGORY_MAP = {
    "observations": "havainnot",
    "forecast": "ennusteet",
    "radar": "tutka",
    "lightning": "salamat",
    "radiation": "säteily",
    "airquality": "ilmanlaatu",
    "sealevel": "meritaso",
    "wave": "aallot",
    "satellite": "satelliitti",
}


class FmiHarvester(BaseHarvester):
    """Kerää Ilmatieteen laitoksen avoimet datakyselyt WFS-rajapinnasta.

    FMI:n WFS tarjoaa stored query -mekanismin, jossa kukin kysely
    on käytännössä oma datasettinsä (sää, ennuste, tutka jne.).
    """

    name = "fmi"
    description = "Ilmatieteen laitos (FMI) — sää-, ilmasto- ja merihavaintodata"
    url = "https://www.ilmatieteenlaitos.fi"

    async def harvest(self) -> int:
        async with self._make_client(timeout=60.0) as client:
            response = await self._fetch(client, LIST_QUERIES_URL)
            xml_text = response.text

        root = ET.fromstring(xml_text)
        ns = {"wfs": "http://www.opengis.net/wfs/2.0"}

        count = 0
        for sq in root.findall("wfs:StoredQuery", ns):
            query_id = sq.get("id", "")
            if not query_id:
                continue

            title_el = sq.find("wfs:Title", ns)
            title = title_el.text if title_el is not None and title_el.text else query_id

            abstract_el = sq.find("wfs:Abstract", ns)
            abstract = abstract_el.text if abstract_el is not None and abstract_el.text else ""

            dataset = self._query_to_dataset(query_id, title, abstract)
            upsert_dataset(self.conn, dataset)
            count += 1

        self.conn.commit()
        logger.info("[fmi] Harvest valmis: %d stored query -datasettiä", count)
        return count

    def _query_to_dataset(self, query_id: str, title: str, abstract: str) -> Dataset:
        dataset_id = f"fmi-{query_id}"
        wfs_url = (
            f"{WFS_BASE}?service=WFS&version=2.0.0"
            f"&request=GetFeature&storedquery_id={query_id}"
        )

        keywords = ["sää", "ilmasto"]
        for key, category in CATEGORY_MAP.items():
            if key in query_id.lower():
                keywords.append(category)
                break

        # Arvioi koko: säädata on usein isoa aikasarja-dataa
        size = 50_000_000  # 50 MB oletus
        if "radar" in query_id:
            size = 500_000_000  # 500 MB tutka
        elif "satellite" in query_id:
            size = 1_000_000_000  # 1 GB satelliitti
        elif "forecast" in query_id:
            size = 100_000_000  # 100 MB ennuste

        return self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=title,
            title_fi=title,
            notes_fi=abstract,
            organization_id="fmi",
            organization_name="fmi",
            organization_title="Ilmatieteen laitos",
            keywords_fi=keywords,
            num_resources=1,
            resources=[
                Resource(
                    id=f"{dataset_id}-wfs",
                    name=f"{query_id} (WFS)",
                    name_fi=f"{title} — WFS-rajapinta",
                    format="WFS",
                    url=wfs_url,
                ),
            ],
            estimated_size_bytes=size,
        )
