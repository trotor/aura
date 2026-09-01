"""Yhteinen kantaluokka CKAN-pohjaisille harvestereille."""

from __future__ import annotations

import json
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

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "ckan",
            "query_protocol": "ckan",
            "api_base_url": cls.ckan_base_url,
        })
        return config

    async def harvest(self) -> int:
        total_harvested = 0
        consecutive_errors = 0
        # Hakuindeksistä saadut nimet, jotta ne voi verrata lähteen omaan
        # luetteloon ajon lopuksi.
        nahdyt: set[str] = set()
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
                    self._enrich_from_extras(dataset.id, raw)
                    self._auto_enrich_crs(dataset)
                    nahdyt.add(str(raw.get("name") or ""))
                    total_harvested += 1

                self.conn.commit()
                start += DEFAULT_BATCH_SIZE
                logger.info(
                    "[%s] Haettu %d / %d",
                    self.name,
                    min(start, total_count),
                    total_count,
                )

            total_harvested += await self._reconcile(client, nahdyt)

        logger.info("[%s] Harvest valmis: %d datasettiä", self.name, total_harvested)
        return total_harvested

    async def _reconcile(
        self, client: httpx.AsyncClient, nahdyt: set[str]
    ) -> int:
        """Nouda ne paketit joita hakuindeksi ei tunne.

        CKANin ``package_search`` palauttaa vain indeksoidut paketit, ja
        ainakin avoindata.suomi.fi:llä osa on indeksin ulkopuolella:
        mitattuna 1.9.2026 ``package_list`` tunsi 2 740 nimeä ja haku 2 561.
        Erotuksesta **74 oli WFS/WMS-palveluita joilla on resursseja** —
        muun muassa koko Ahvenanmaa.

        Kyse ei ole suodatuksesta. ``fq=+type:apiset`` palauttaa nollan, eli
        kohteita ei ole indeksissä lainkaan eikä mikään kyselyparametri tuo
        niitä esiin. Ainoa reitti on ``package_list`` + ``package_show``.

        Vertailu on samalla regressiotarkistus: aukko oli näkymätön juuri
        siksi ettei mikään verrannut harvestoitua siihen mitä lähde sanoo
        itsellään olevan.

        Kustannus on verrannollinen aukkoon eikä katalogin kokoon: jos
        luettelot täsmäävät, tämä maksaa yhden kutsun.
        """
        try:
            response = await self._fetch(client, f"{self.ckan_base_url}/package_list")
            nimet = response.json().get("result") or []
        except Exception as exc:  # vertailu on lisä, ei edellytys
            logger.warning(
                "[%s] package_list ei vastannut, vertailu ohitetaan: %s",
                self.name,
                exc,
            )
            return 0

        puuttuvat = [n for n in nimet if n not in nahdyt]
        if not puuttuvat:
            return 0
        logger.info(
            "[%s] Hakuindeksin ulkopuolella %d pakettia (%d / %d luettelossa)",
            self.name,
            len(puuttuvat),
            len(nahdyt),
            len(nimet),
        )

        lisatty = 0
        for nimi in puuttuvat:
            raw = await self._fetch_package(client, nimi)
            # Resurssiton paketti ei ole aineisto: showcase on sovellus ja
            # harvest on lähdekonfiguraatio. Kummallakin nolla resurssia.
            if not raw or not raw.get("resources"):
                continue
            dataset = Dataset.from_ckan(raw, source=self.ckan_source)
            upsert_dataset(self.conn, dataset)
            self._enrich_from_extras(dataset.id, raw)
            self._auto_enrich_crs(dataset)
            lisatty += 1

        self.conn.commit()
        logger.info("[%s] Vertailu toi %d aineistoa lisää", self.name, lisatty)
        return lisatty

    async def _fetch_package(
        self, client: httpx.AsyncClient, nimi: str
    ) -> dict[str, Any] | None:
        """Yksi paketti nimellä, tai None jos sitä ei saada."""
        try:
            response = await self._fetch(
                client,
                f"{self.ckan_base_url}/package_show",
                params={"id": nimi},
            )
            data = response.json()
        except Exception as exc:  # yksi rikkinäinen ei saa pysäyttää muita
            logger.debug("[%s] package_show %s: %s", self.name, nimi, exc)
            return None
        if not data.get("success"):
            return None
        tulos: dict[str, Any] | None = data.get("result")
        return tulos

    # CKAN extras → enrichment-kenttä
    EXTRAS_FIELD_MAP: dict[str, str] = {
        "temporal_coverage_from": "temporal_coverage",
        "temporal_coverage_to": "temporal_coverage",
        "contact-email": "access_instructions",
        "maintainer_email": "access_instructions",
        "lineage": "description_extended",
        "spatial-reference-system": "data_fields",
        "topic-category": "keywords",
    }

    def _enrich_from_extras(
        self, dataset_id: str, raw: dict[str, Any]
    ) -> None:
        """Rikasta datasetti CKAN extras -kentistä."""
        extras = raw.get("extras", [])
        if not extras:
            return

        temporal_parts: list[str] = []

        for extra in extras:
            key = extra.get("key", "")
            val = extra.get("value", "")
            if not key or not val:
                continue

            # Bbox → enrichment
            if key.startswith("bbox-"):
                continue  # kerätään alla erikseen

            # Temporal coverage: yhdistä from+to
            if key in ("temporal_coverage_from", "temporal_coverage_to"):
                temporal_parts.append(val)
                continue

            # Mappaus
            field = self.EXTRAS_FIELD_MAP.get(key)
            if field:
                # JSON-arvot: parsitaan ja muotoillaan
                display_val = self._format_extra_value(val)
                detail = f"CKAN extras: {key}"
                self._add_enrichment(
                    dataset_id, field, display_val,
                    source_detail=detail,
                )

        # Temporal coverage yhdistettynä
        if temporal_parts:
            self._add_enrichment(
                dataset_id, "temporal_coverage",
                " – ".join(sorted(temporal_parts)),
                source_detail="CKAN extras: temporal_coverage",
            )

        # Bbox → spatial enrichment
        bbox = self._extract_bbox(extras)
        if bbox:
            self._add_enrichment(
                dataset_id, "data_fields",
                f"bbox: [{bbox}]",
                source_detail="CKAN extras: bbox",
            )

    @staticmethod
    def _format_extra_value(val: str) -> str:
        """Muotoile CKAN extras -arvo luettavaksi."""
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return ", ".join(str(v) for v in parsed)
            if isinstance(parsed, dict):
                return json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
        return val

    @staticmethod
    def _extract_bbox(extras: list[dict[str, str]]) -> str:
        """Kokoa bbox-arvot CKAN extras -kentistä."""
        bbox: dict[str, str] = {}
        for extra in extras:
            key = extra.get("key", "")
            if key.startswith("bbox-"):
                bbox[key] = extra.get("value", "")
        if len(bbox) == 4:
            return (
                f"W:{bbox.get('bbox-west-long', '')}, "
                f"S:{bbox.get('bbox-south-lat', '')}, "
                f"E:{bbox.get('bbox-east-long', '')}, "
                f"N:{bbox.get('bbox-north-lat', '')}"
            )
        return ""

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        rows: int = DEFAULT_BATCH_SIZE,
        start: int = 0,
    ) -> dict[str, Any]:
        response = await self._fetch(
            client,
            f"{self.ckan_base_url}/package_search",
            params={"rows": rows, "start": start, "sort": "metadata_modified desc"},
        )
        result: dict[str, Any] = response.json()
        return result
