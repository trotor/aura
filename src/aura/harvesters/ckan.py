"""Yhteinen kantaluokka CKAN-pohjaisille harvestereille."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 100


class CkanHarvester(BaseHarvester):
    """Kantaluokka CKAN API -pohjaisille harvestereille.

    Aliluokan tarvitsee määritellä vain:
        - name, description, url
        - ckan_base_url: CKAN API:n juuri-URL
        - ckan_source: Dataset.from_ckan()-metodille välitettävä source-arvo
    """

    ckan_base_url: str = ""
    ckan_source: str = ""

    async def harvest(self) -> int:
        total_harvested = 0
        consecutive_errors = 0
        max_consecutive_errors = 3

        async with self._make_client() as client:
            result = await self._fetch_page(client, rows=1, start=0)
            total_count = result["result"]["count"]
            logger.info("[%s] Datasettejä yhteensä: %d", self.name, total_count)

            start = 0
            while start < total_count:
                try:
                    result = await self._fetch_page(
                        client, rows=DEFAULT_BATCH_SIZE, start=start,
                    )
                except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                    consecutive_errors += 1
                    logger.warning(
                        "[%s] HTTP-virhe sivulla start=%d: %s (%d/%d)",
                        self.name, start, exc,
                        consecutive_errors, max_consecutive_errors,
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            "[%s] Liian monta peräkkäistä virhettä, keskeytetään. "
                            "Haettu %d datasettiä ennen virhettä.",
                            self.name, total_harvested,
                        )
                        break
                    start += DEFAULT_BATCH_SIZE
                    continue

                consecutive_errors = 0
                datasets = result["result"]["results"]

                for raw in datasets:
                    dataset = Dataset.from_ckan(raw, source=self.ckan_source)
                    upsert_dataset(self.conn, dataset)
                    total_harvested += 1

                self.conn.commit()
                start += DEFAULT_BATCH_SIZE
                logger.info(
                    "[%s] Haettu %d / %d",
                    self.name,
                    min(start, total_count),
                    total_count,
                )

        logger.info("[%s] Harvest valmis: %d datasettiä", self.name, total_harvested)
        return total_harvested

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        rows: int = DEFAULT_BATCH_SIZE,
        start: int = 0,
    ) -> dict[str, Any]:
        response = await client.get(
            f"{self.ckan_base_url}/package_search",
            params={"rows": rows, "start": start, "sort": "metadata_modified desc"},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
