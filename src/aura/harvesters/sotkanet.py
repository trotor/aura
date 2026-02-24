"""Harvester THL Sotkanet -indikaattoreille.

Sotkanet on THL:n ylläpitämä tilasto- ja indikaattoripankki, jossa on
~3 500 hyvinvointi- ja terveysindikaattoria kuntatasolla.

API: https://sotkanet.fi/rest/1.1/
Lisenssi: CC BY 4.0 (THL, Sotkanet)
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

API_BASE = "https://sotkanet.fi/rest/1.1"

# Rinnakkaisten pyyntöjen rajoitus (API ei dokumentoi rate limittejä,
# mutta ei kuormiteta liikaa)
MAX_CONCURRENT = 20

# HTML-tägien poisto kuvausteksteistä
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Poista HTML-tägit ja dekoodaa entiteetit."""
    if not text:
        return ""
    clean = _HTML_TAG_RE.sub("", text)
    return html.unescape(clean).strip()


class SotkanetHarvester(BaseHarvester):
    """Kerää THL Sotkanet -indikaattorit avoimena datana.

    Vaihe 1: Hae kaikki indikaattorit (/indicators) — yksi pyyntö.
    Vaihe 2: Hae jokaiselle yksityiskohtaiset metatiedot (/indicators/{id})
    rinnakkaisesti.
    """

    name = "sotkanet"
    description = "THL Sotkanet — hyvinvointi- ja terveysindikaattorit"
    url = "https://sotkanet.fi"

    # Hidastetaan yksittäisiä pyyntöjä hieman
    request_delay = 0.05

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "rest_api",
            "query_protocol": "rest_json",
            "api_base_url": API_BASE,
        })
        return config

    async def harvest(self) -> int:
        """Hae kaikki Sotkanet-indikaattorit."""
        async with self._make_client(timeout=60.0) as client:
            # Vaihe 1: Lista kaikista indikaattoreista
            indicators = await self._fetch_indicator_list(client)
            if not indicators:
                logger.warning("[sotkanet] Indikaattorilistaa ei saatu")
                return 0

            logger.info("[sotkanet] %d indikaattoria listattu", len(indicators))

            # Vaihe 2: Hae yksityiskohdat rinnakkaisesti
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            tasks = [
                self._fetch_and_save_indicator(client, semaphore, ind)
                for ind in indicators
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        count = sum(1 for r in results if r is True)
        errors = sum(1 for r in results if isinstance(r, Exception))
        if errors:
            logger.warning("[sotkanet] %d virhettä %d indikaattorista", errors, len(indicators))
        logger.info("[sotkanet] Harvest valmis: %d datasettiä", count)
        return count

    async def _fetch_indicator_list(
        self, client: httpx.AsyncClient,
    ) -> list[dict[str, Any]]:
        """Hae kaikki indikaattorit (yksi pyyntö, ~2.4 MB)."""
        try:
            response = await self._fetch(client, f"{API_BASE}/indicators")
            return response.json()
        except Exception:
            logger.exception("[sotkanet] Indikaattorilistan haku epäonnistui")
            return []

    async def _fetch_and_save_indicator(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        indicator: dict[str, Any],
    ) -> bool:
        """Hae yksittäisen indikaattorin tiedot ja tallenna."""
        ind_id = indicator["id"]
        async with semaphore:
            try:
                detail = await self._fetch_indicator_detail(client, ind_id)
            except Exception:
                logger.warning("[sotkanet] Indikaattorin %d haku epäonnistui", ind_id)
                return False

        dataset = self._build_dataset(indicator, detail)
        upsert_dataset(self.conn, dataset)
        self.conn.commit()
        return True

    async def _fetch_indicator_detail(
        self, client: httpx.AsyncClient, indicator_id: int,
    ) -> dict[str, Any]:
        """Hae indikaattorin yksityiskohtaiset metatiedot."""
        response = await self._fetch(client, f"{API_BASE}/indicators/{indicator_id}")
        return response.json()

    def _build_dataset(
        self,
        indicator: dict[str, Any],
        detail: dict[str, Any],
    ) -> Any:
        """Muunna Sotkanet-indikaattori Aura Dataset -olioksi."""
        ind_id = indicator["id"]
        title_map = indicator.get("title", {})
        title_fi = title_map.get("fi", "")
        title_en = title_map.get("en", "")
        title_sv = title_map.get("sv", "")

        # Organisaatio
        org = indicator.get("organization", {})
        org_title_map = org.get("title", {})
        org_id = str(org.get("id", "thl"))
        org_title = org_title_map.get("fi", "THL")

        # Kuvaus ja tulkinta detailista
        desc_map = detail.get("description", {})
        interp_map = detail.get("interpretation", {})
        desc_fi = _strip_html(desc_map.get("fi", ""))
        desc_en = _strip_html(desc_map.get("en", ""))
        desc_sv = _strip_html(desc_map.get("sv", ""))
        interp_fi = _strip_html(interp_map.get("fi", ""))

        notes_fi = desc_fi
        if interp_fi:
            notes_fi = f"{desc_fi}\n\nTulkinta: {interp_fi}" if desc_fi else interp_fi

        # Avainsanat (subjects)
        subjects = detail.get("subjects", [])
        keywords_fi = [s["fi"] for s in subjects if s.get("fi")]
        keywords_en = [s["en"] for s in subjects if s.get("en")]

        # Ajallinen kattavuus
        year_range = detail.get("range", {})
        start_year = year_range.get("start", "")
        end_year = year_range.get("end", "")
        temporal = f"{start_year}–{end_year}" if start_year and end_year else ""

        # Päivämäärä
        data_updated = detail.get("data-updated", "")
        if data_updated and "T" not in data_updated:
            data_updated = f"{data_updated}T00:00:00"

        # Mittayksikkö
        value_type = detail.get("primaryValueType", {})
        value_title = (value_type.get("title", {}).get("fi", "") if value_type else "")

        # Alueluokitukset — tunnista kuntadata
        classifications = indicator.get("classifications", {})
        region_values = classifications.get("region", {}).get("values", [])
        has_kunta = "Kunta" in region_values

        # Päivitystiheys
        update_frequency = "vuosittain"  # Sotkanet päivittyy tyypillisesti vuosittain

        # Resurssit
        resources = [
            Resource(
                id=f"sotkanet-{ind_id}-json",
                name=f"{title_fi} (JSON API)",
                name_fi=f"{title_fi} (JSON API)",
                format="JSON",
                url=f"{API_BASE}/json?indicator={ind_id}",
                description=f"Sotkanet REST API — indikaattori {ind_id}",
            ),
            Resource(
                id=f"sotkanet-{ind_id}-csv",
                name=f"{title_fi} (CSV)",
                name_fi=f"{title_fi} (CSV)",
                format="CSV",
                url=f"{API_BASE}/csv?indicator={ind_id}",
                description=f"Sotkanet CSV-lataus — indikaattori {ind_id}",
            ),
            Resource(
                id=f"sotkanet-{ind_id}-web",
                name=f"{title_fi} (web)",
                name_fi=f"{title_fi} (Sotkanet-selain)",
                format="HTML",
                url=f"https://sotkanet.fi/sotkanet/fi/taulukko?indicator={ind_id}",
                description="Sotkanet-verkkosivu taulukkoineen",
            ),
        ]

        # Kuvauksen lisätiedot
        extra_notes = []
        if value_title:
            extra_notes.append(f"Mittayksikkö: {value_title}")
        if temporal:
            extra_notes.append(f"Aikajakso: {temporal}")
        if has_kunta:
            extra_notes.append("Saatavilla kuntatasolla")
        if extra_notes:
            suffix = ". ".join(extra_notes) + "."
            notes_fi = f"{notes_fi}\n\n{suffix}" if notes_fi else suffix

        return self._make_dataset(
            id=f"sotkanet-{ind_id}",
            name=f"sotkanet-{ind_id}",
            title=title_fi or title_en,
            title_fi=title_fi,
            title_en=title_en,
            title_sv=title_sv,
            notes_fi=notes_fi,
            notes_en=_strip_html(desc_en),
            notes_sv=_strip_html(desc_sv),
            organization_id=f"sotkanet-org-{org_id}",
            organization_name=org_id,
            organization_title=org_title,
            keywords_fi=keywords_fi or ["hyvinvointi", "terveys", "indikaattori"],
            keywords_en=keywords_en,
            geographical_coverage=["Suomi"],
            update_frequency=update_frequency,
            metadata_modified=data_updated,
            num_resources=len(resources),
            resources=resources,
        )
