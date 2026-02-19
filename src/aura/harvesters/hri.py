"""Harvester Helsinki Region Infoshare (HRI) CKAN API:lle."""

from __future__ import annotations

import logging

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset

logger = logging.getLogger(__name__)

CKAN_BASE_URL = "https://hri.fi/data/api/3/action"
DEFAULT_BATCH_SIZE = 100


class HriHarvester(BaseHarvester):
    """Kerää datasetit Helsinki Region Infoshare -portaalista.

    HRI on pääkaupunkiseudun avoimen datan portaali (Helsinki, Espoo, Vantaa, Kauniainen).
    Käyttää samaa CKAN-rajapintaa kuin avoindata.fi.
    """

    name = "hri.fi"
    description = "Helsinki Region Infoshare — pääkaupunkiseudun avoin data"
    url = "https://hri.fi"

    async def harvest(self) -> int:
        total_harvested = 0

        async with self._make_client() as client:
            result = await self._fetch_page(client, rows=1, start=0)
            total_count = result["result"]["count"]
            logger.info("[hri.fi] Datasettejä yhteensä: %d", total_count)

            start = 0
            while start < total_count:
                result = await self._fetch_page(client, rows=DEFAULT_BATCH_SIZE, start=start)
                datasets = result["result"]["results"]

                for raw in datasets:
                    dataset = Dataset.from_ckan(raw, source="hri.fi")
                    upsert_dataset(self.conn, dataset)
                    total_harvested += 1

                self.conn.commit()
                start += DEFAULT_BATCH_SIZE
                logger.info(
                    "[hri.fi] Haettu %d / %d",
                    min(start, total_count),
                    total_count,
                )

        logger.info("[hri.fi] Harvest valmis: %d datasettiä", total_harvested)
        return total_harvested

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        rows: int = DEFAULT_BATCH_SIZE,
        start: int = 0,
    ) -> dict:
        response = await client.get(
            f"{CKAN_BASE_URL}/package_search",
            params={"rows": rows, "start": start, "sort": "metadata_modified desc"},
        )
        response.raise_for_status()
        return response.json()
