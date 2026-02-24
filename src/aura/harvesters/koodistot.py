"""Koodistot.suomi.fi -harvester.

Hakee Suomi.fi-koodistopalvelun koodirekisterit ja koodistot.
API: https://koodistot.suomi.fi/codelist-api/api/v1/
"""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

API_BASE = "https://koodistot.suomi.fi/codelist-api/api/v1"

# Rekisterit joita ei harvestoida (testi, sisäinen)
SKIP_REGISTRIES = {"test"}


class KoodistotHarvester(BaseHarvester):
    """Suomi.fi-koodistopalvelun harvester."""

    name = "koodistot"
    description = "Suomi.fi-koodistopalvelu — julkishallinnon koodistot ja luokitukset"
    url = "https://koodistot.suomi.fi"

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "custom",
            "query_protocol": "rest_json",
            "api_base_url": API_BASE,
        })
        return config

    async def harvest(self) -> int:
        total = 0
        async with self._make_client(timeout=30.0) as client:
            # Hae kaikki koodirekisterit
            resp = await self._fetch(
                client, f"{API_BASE}/coderegistries/", params={"format": "json"},
            )
            registries = resp.json().get("results", [])
            logger.info("[koodistot] %d koodirekisteriä", len(registries))

            for registry in registries:
                reg_code = registry.get("codeValue", "")
                if not reg_code or reg_code in SKIP_REGISTRIES:
                    continue

                count = await self._harvest_registry(client, registry)
                total += count

        logger.info("[koodistot] Harvest done: %d koodistoa", total)
        return total

    async def _harvest_registry(
        self,
        client: Any,
        registry: dict[str, Any],
    ) -> int:
        """Hae yksittäisen rekisterin koodistot."""
        reg_code = registry["codeValue"]
        reg_label = registry.get("prefLabel", {})
        reg_title = reg_label.get("fi", reg_label.get("en", reg_code))

        try:
            resp = await self._fetch(
                client,
                f"{API_BASE}/coderegistries/{reg_code}/codeschemes/",
                params={"format": "json", "status": "VALID"},
            )
            schemes = resp.json().get("results", [])
        except Exception:
            logger.warning("[koodistot/%s] Virhe haettaessa koodistoja", reg_code)
            return 0

        count = 0
        for scheme in schemes:
            self._process_scheme(reg_code, reg_title, scheme)
            count += 1

        if count:
            self.conn.commit()
            logger.info("[koodistot/%s] %d koodistoa", reg_code, count)
        return count

    def _process_scheme(
        self,
        reg_code: str,
        reg_title: str,
        scheme: dict[str, Any],
    ) -> None:
        """Luo Dataset yhdestä koodistosta."""
        scheme_code = scheme.get("codeValue", "")
        labels = scheme.get("prefLabel", {})
        title_fi = labels.get("fi", labels.get("en", scheme_code))
        title_en = labels.get("en", "")
        title_sv = labels.get("sv", "")

        desc = scheme.get("description", {}) or {}
        defn = scheme.get("definition", {}) or {}
        notes_fi = desc.get("fi", defn.get("fi", ""))
        notes_en = desc.get("en", defn.get("en", ""))

        dataset_id = f"koodistot-{reg_code}-{scheme_code}"

        # Resurssit: JSON ja CSV
        codes_url = scheme.get("codesUrl", "")
        resources = []
        if codes_url:
            resources.append(
                Resource(
                    id=f"{dataset_id}-json",
                    name=f"{title_fi} (JSON)",
                    name_fi=f"{title_fi} — JSON",
                    format="JSON",
                    url=f"{codes_url}?format=json",
                ),
            )
            resources.append(
                Resource(
                    id=f"{dataset_id}-csv",
                    name=f"{title_fi} (CSV)",
                    name_fi=f"{title_fi} — CSV",
                    format="CSV",
                    url=f"{codes_url}?format=csv",
                ),
            )

        modified = scheme.get("modified", "")

        dataset = self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=title_fi,
            title_fi=title_fi,
            title_en=title_en,
            title_sv=title_sv,
            notes_fi=notes_fi,
            notes_en=notes_en,
            organization_id=f"koodistot-{reg_code}",
            organization_name=reg_code,
            organization_title=reg_title,
            keywords_fi=["koodisto", "luokitus", "yhteentoimivuus"],
            update_frequency="tarvittaessa",
            num_resources=len(resources),
            resources=resources,
            metadata_modified=modified,
        )
        upsert_dataset(self.conn, dataset)

        # Rikastukset
        if notes_en:
            self._add_enrichment(
                dataset_id, "description_extended", notes_en,
                source_detail="koodistot.suomi.fi description",
            )
