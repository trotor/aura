"""Harvester Tilastokeskuksen PxWeb API:lle."""

from __future__ import annotations

import logging
import uuid

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

PXWEB_BASE_URL = "https://statfin.stat.fi/PxWeb/api/v1"


class StatfinHarvester(BaseHarvester):
    """Kerää tilastotaulut Tilastokeskuksen PxWeb API:sta.

    PxWeb-rajapinta on puumainen: juuritaso → aihealueet → alataso → taulut.
    Jokainen taulu on yksi datasetti.
    """

    name = "statfin"
    description = "Tilastokeskus (Statistics Finland) — PxWeb-tilastot"
    url = "https://stat.fi"

    async def harvest(self) -> int:
        total_harvested = 0

        async with self._make_client(timeout=60.0) as client:
            # Hae suomenkielinen rakenne
            total_harvested = await self._crawl_folder(
                client, f"{PXWEB_BASE_URL}/fi/StatFin/", path="StatFin"
            )

        logger.info("[statfin] Harvest valmis: %d taulua", total_harvested)
        return total_harvested

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
            logger.warning("[statfin] Virhe haettaessa %s: %s", url, e)
            return 0

        count = 0
        for item in items:
            item_id = item.get("id", "")
            item_type = item.get("type", "")
            item_text = item.get("text", "")

            if item_type == "l":
                # Kansio — recurse
                sub_url = f"{url}{item_id}/"
                sub_count = await self._crawl_folder(client, sub_url, f"{path}/{item_id}")
                count += sub_count

            elif item_type == "t":
                # Taulu — tämä on datasetti
                dataset = self._table_to_dataset(item, path, url)
                upsert_dataset(self.conn, dataset)
                count += 1

        if count > 0:
            self.conn.commit()
            logger.info("[statfin] Haettu %d taulua polusta %s", count, path)

        return count

    def _table_to_dataset(self, item: dict, path: str, base_url: str) -> Dataset:
        """Muunna PxWeb-taulu Dataset-olioksi."""
        table_id = item.get("id", "")
        title = item.get("text", "")
        updated = item.get("updated", "")

        # Luo deterministinen ID polusta
        dataset_id = f"statfin-{table_id}"

        # PxWeb-taulu URL
        table_url = f"{base_url}{table_id}"
        # Ihmisluettava URL
        web_url = f"https://statfin.stat.fi/PxWeb/pxweb/fi/StatFin/{path}/{table_id}"

        # Englanninkielinen URL
        en_url = table_url.replace("/fi/StatFin/", "/en/StatFin/")

        return Dataset(
            id=dataset_id,
            name=f"statfin-{table_id.replace('.px', '').lower()}",
            title=title,
            title_fi=title,
            notes_fi=f"Tilastokeskuksen tilastotaulu. Polku: {path}/{table_id}",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            organization_id="tilastokeskus",
            organization_name="tilastokeskus",
            organization_title="Tilastokeskus",
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
            source="statfin",
        )

    def _path_to_keywords(self, path: str) -> list[str]:
        """Muunna polku avainsanoiksi."""
        parts = path.split("/")
        # Suodata pois geneerinen "StatFin"
        return [p for p in parts if p and p != "StatFin"]
