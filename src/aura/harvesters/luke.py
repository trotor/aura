"""Harvester Luonnonvarakeskuksen (LUKE) PxWeb API:lle."""

from __future__ import annotations

import logging

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

PXWEB_BASE_URL = "https://statdb.luke.fi/PxWeb/api/v1"


class LukeHarvester(BaseHarvester):
    """Kerää tilastotaulut Luonnonvarakeskuksen PxWeb API:sta.

    LUKE:n PxWeb sisältää maa-, metsä- ja kalatilastoja.
    Sama PxWeb-rajapinta kuin Tilastokeskuksella.
    """

    name = "luke"
    description = "Luonnonvarakeskus (LUKE) — maa-, metsä- ja kalatilastot"
    url = "https://statdb.luke.fi"

    async def harvest(self) -> int:
        async with self._make_client(timeout=60.0) as client:
            total = await self._crawl_folder(
                client, f"{PXWEB_BASE_URL}/fi/LUKE/", path="LUKE"
            )

        logger.info("[luke] Harvest valmis: %d taulua", total)
        return total

    async def _crawl_folder(
        self,
        client: httpx.AsyncClient,
        url: str,
        path: str,
    ) -> int:
        """Käy rekursiivisesti läpi PxWeb-puun."""
        try:
            response = await client.get(url)
            response.raise_for_status()
            items = response.json()
        except Exception as e:
            logger.warning("[luke] Virhe haettaessa %s: %s", url, e)
            return 0

        count = 0
        for item in items:
            item_id = item.get("id", "")
            item_type = item.get("type", "")

            if item_type == "l":
                sub_url = f"{url}{item_id}/"
                count += await self._crawl_folder(client, sub_url, f"{path}/{item_id}")
            elif item_type == "t":
                dataset = self._table_to_dataset(item, path, url)
                upsert_dataset(self.conn, dataset)
                count += 1

        if count > 0:
            self.conn.commit()
            logger.info("[luke] Haettu %d taulua polusta %s", count, path)

        return count

    def _table_to_dataset(self, item: dict, path: str, base_url: str) -> Dataset:
        """Muunna PxWeb-taulu Dataset-olioksi."""
        table_id = item.get("id", "")
        title = item.get("text", "")
        updated = item.get("updated", "")

        dataset_id = f"luke-{table_id}"
        table_url = f"{base_url}{table_id}"
        web_url = f"https://statdb.luke.fi/PxWeb/pxweb/fi/LUKE/{path}/{table_id}"

        return Dataset(
            id=dataset_id,
            name=f"luke-{table_id.replace('.px', '').lower()}",
            title=title,
            title_fi=title,
            notes_fi=f"Luonnonvarakeskuksen tilastotaulu. Polku: {path}/{table_id}",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            organization_id="luke",
            organization_name="luke",
            organization_title="Luonnonvarakeskus (LUKE)",
            metadata_modified=updated,
            keywords_fi=self._path_to_keywords(path),
            collection_type="Open Data",
            num_resources=2,
            resources=[
                Resource(
                    id=f"{dataset_id}-pxweb",
                    name=f"{table_id} (PxWeb API)",
                    name_fi=f"{title} — PxWeb-rajapinta",
                    format="PXWEB",
                    url=table_url,
                ),
                Resource(
                    id=f"{dataset_id}-web",
                    name=f"{table_id} (web)",
                    name_fi=f"{title} — verkkosivu",
                    format="HTML",
                    url=web_url,
                ),
            ],
            source="luke",
            estimated_size_bytes=5_000_000,  # PxWeb-taulu ~5 MB
        )

    def _path_to_keywords(self, path: str) -> list[str]:
        parts = path.split("/")
        return [p for p in parts if p and p != "LUKE"]
