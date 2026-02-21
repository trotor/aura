"""Yhteinen kantaluokka PxWeb-pohjaisille harvestereille."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)


class PxWebHarvester(BaseHarvester):
    """Kantaluokka PxWeb API -pohjaisille harvestereille.

    PxWeb-rajapinta on puumainen: juuritaso → aihealueet → alataso → taulut.
    Jokainen taulu on yksi datasetti.

    Aliluokan tarvitsee määritellä:
        - name, description, url
        - pxweb_base_url: PxWeb API:n juuri-URL
        - root_path: Juuripolun nimi (esim. "StatFin", "LUKE")
        - web_base_url: Ihmisluettavan URL:n juuri
        - org_id, org_name, org_title: Organisaatiotiedot
        - dataset_id_prefix: Datasetin ID:n etuliite (esim. "statfin", "luke")
        - notes_template: Kuvauksen pohja (esim. "Tilastokeskuksen tilastotaulu")
    """

    pxweb_base_url: str = ""
    root_path: str = ""
    web_base_url: str = ""
    org_id: str = ""
    org_name: str = ""
    org_title: str = ""
    dataset_id_prefix: str = ""
    notes_template: str = "Tilastotaulu"

    async def harvest(self) -> int:
        async with self._make_client(timeout=60.0) as client:
            total = await self._crawl_folder(
                client,
                f"{self.pxweb_base_url}/fi/{self.root_path}/",
                path=self.root_path,
            )

        logger.info("[%s] Harvest valmis: %d taulua", self.name, total)
        return total

    async def _crawl_folder(
        self,
        client: httpx.AsyncClient,
        url: str,
        path: str,
    ) -> int:
        """Käy rekursiivisesti läpi PxWeb-puun."""
        try:
            response = await self._fetch(client, url)
            items = response.json()
        except Exception as e:
            logger.warning("[%s] Virhe haettaessa %s: %s", self.name, url, e)
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
            logger.info("[%s] Haettu %d taulua polusta %s", self.name, count, path)

        return count

    def _table_to_dataset(self, item: dict[str, Any], path: str, base_url: str) -> Dataset:
        """Muunna PxWeb-taulu Dataset-olioksi."""
        table_id = item.get("id", "")
        title = item.get("text", "")
        updated = item.get("updated", "")

        dataset_id = f"{self.dataset_id_prefix}-{table_id}"
        table_url = f"{base_url}{table_id}"
        web_url = f"{self.web_base_url}/{self.root_path}/{path}/{table_id}"

        return self._make_dataset(
            id=dataset_id,
            name=f"{self.dataset_id_prefix}-{table_id.replace('.px', '').lower()}",
            title=title,
            title_fi=title,
            notes_fi=f"{self.notes_template}. Polku: {path}/{table_id}",
            organization_id=self.org_id,
            organization_name=self.org_name,
            organization_title=self.org_title,
            metadata_modified=updated,
            keywords_fi=self._path_to_keywords(path),
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
            estimated_size_bytes=5_000_000,
        )

    def _path_to_keywords(self, path: str) -> list[str]:
        """Muunna polku avainsanoiksi."""
        parts = path.split("/")
        return [p for p in parts if p and p != self.root_path]
