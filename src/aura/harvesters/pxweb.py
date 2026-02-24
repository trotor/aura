"""Yhteinen kantaluokka PxWeb-pohjaisille harvestereille."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from aura.database import add_enrichment, get_enrichments, upsert_dataset
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

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "pxweb",
            "query_protocol": "pxweb",
            "api_base_url": cls.pxweb_base_url,
        })
        return config

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

        # PxWeb ei tarjoa päivitystaajuutta — arvioidaan polun perusteella
        freq = "vuosittain"
        path_lower = path.lower()
        if "kuukau" in path_lower or "kk" in path_lower:
            freq = "kuukausittain"
        elif "neljännes" in path_lower or "vuosinelj" in path_lower:
            freq = "neljännesvuosittain"

        return self._make_dataset(
            id=dataset_id,
            name=f"{self.dataset_id_prefix}-{table_id.replace('.px', '').lower()}",
            title=title,
            title_fi=title,
            notes_fi=f"{self.notes_template}. Polku: {path}/{table_id}",
            update_frequency=freq,
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

    async def harvest_dimensions(self, limit: int = 0) -> int:
        """Hae taulujen dimensiotiedot ja tallenna enrichmenteiksi.

        Hakee jokaisen PxWeb-taulun muuttujat (variables) API:sta ja
        tallentaa ne data_fields-rikastuksena. Ohittaa jo rikastetut.

        Args:
            limit: Enimmäismäärä tauluja (0 = kaikki).

        Returns:
            Rikastettujen taulujen lukumäärä.
        """
        # Hae kaikki tämän lähteen PxWeb-resurssit
        rows = self.conn.execute(
            """
            SELECT d.id, r.url FROM datasets d
            JOIN resources r ON r.dataset_id = d.id
            WHERE d.source = ? AND r.format = 'PXWEB'
            ORDER BY d.id
            """,
            (self.name,),
        ).fetchall()

        # Suodata jo rikastetut
        to_enrich = []
        for row in rows:
            existing = get_enrichments(self.conn, row[0])
            if any(e["field"] == "data_fields" for e in existing):
                continue
            to_enrich.append((row[0], row[1]))

        if limit > 0:
            to_enrich = to_enrich[:limit]

        if not to_enrich:
            logger.info("[%s] Kaikki taulut on jo rikastettu", self.name)
            return 0

        logger.info(
            "[%s] Rikastetaan %d / %d taulua dimensiotiedoilla",
            self.name, len(to_enrich), len(rows),
        )

        enriched = 0
        async with self._make_client(timeout=30.0) as client:
            for i, (dataset_id, api_url) in enumerate(to_enrich):
                try:
                    resp = await self._fetch(client, api_url)
                    meta = resp.json()
                except Exception as e:
                    logger.debug("[%s] Ohitetaan %s: %s", self.name, dataset_id, e)
                    continue

                variables = meta.get("variables", [])
                if not variables:
                    continue

                fields = []
                time_var = None
                for var in variables:
                    code = var.get("code", "")
                    text = var.get("text", code)
                    values = var.get("values", [])
                    value_texts = var.get("valueTexts", [])
                    field_info: dict[str, Any] = {
                        "code": code,
                        "name": text,
                        "value_count": len(values),
                    }
                    # Näytä muutama esimerkkiarvo
                    examples = value_texts[:5] if value_texts else values[:5]
                    if examples:
                        field_info["examples"] = examples
                    fields.append(field_info)

                    # Tunnista aikadimensio
                    if code.lower() in ("vuosi", "year", "kuukausi", "month",
                                         "vuosineljännes", "quarter"):
                        time_var = var

                add_enrichment(
                    self.conn,
                    dataset_id,
                    "data_fields",
                    json.dumps(fields, ensure_ascii=False),
                    confidence="verified",
                    source_type="harvest",
                    source_detail=f"PxWeb API {api_url}",
                )

                # Tallenna ajallinen kattavuus aikadimension perusteella
                if time_var:
                    time_values = time_var.get("values", [])
                    if len(time_values) >= 2:
                        temporal = f"{time_values[0]}–{time_values[-1]}"
                        add_enrichment(
                            self.conn,
                            dataset_id,
                            "temporal_coverage",
                            temporal,
                            confidence="verified",
                            source_type="harvest",
                            source_detail=f"PxWeb API {api_url}",
                        )

                enriched += 1
                if (i + 1) % 100 == 0:
                    logger.info(
                        "[%s] Rikastettu %d / %d taulua",
                        self.name, enriched, len(to_enrich),
                    )

        logger.info(
            "[%s] Dimensiorikastus valmis: %d taulua", self.name, enriched,
        )
        return enriched

    def _path_to_keywords(self, path: str) -> list[str]:
        """Muunna polku avainsanoiksi."""
        parts = path.split("/")
        return [p for p in parts if p and p != self.root_path]
