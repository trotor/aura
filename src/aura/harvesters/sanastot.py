"""Sanastot.suomi.fi -harvester.

Hakee Suomi.fi-yhteentoimivuusalustan terminologiat ja sanastot.
API: https://sanastot.suomi.fi/terminology-api/v2/frontend/
"""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

API_BASE = "https://sanastot.suomi.fi/terminology-api/v2"
PAGE_SIZE = 100


class SanastotHarvester(BaseHarvester):
    """Sanastot.suomi.fi -terminologiaharvester."""

    name = "sanastot"
    description = "Suomi.fi-sanastot — julkishallinnon terminologiat ja sanastot"
    url = "https://sanastot.suomi.fi"

    async def harvest(self) -> int:
        total = 0
        async with self._make_client(timeout=30.0) as client:
            # Hae organisaatiot nimien resolvointiin
            orgs = await self._fetch_organizations(client)

            # Paginoi terminologiat
            page_from = 0
            while True:
                resp = await self._fetch(
                    client,
                    f"{API_BASE}/frontend/search-terminologies",
                    params={"pageSize": PAGE_SIZE, "pageFrom": page_from},
                )
                data = resp.json()
                terminologies = data.get("terminologies", [])

                if not terminologies:
                    break

                for term in terminologies:
                    if term.get("status") != "VALID":
                        continue
                    self._process_terminology(term, orgs)
                    total += 1

                self.conn.commit()
                page_from += PAGE_SIZE
                total_hits = data.get("totalHitCount", 0)
                logger.info(
                    "[sanastot] %d / %d",
                    min(page_from, total_hits),
                    total_hits,
                )
                if page_from >= total_hits:
                    break

        logger.info("[sanastot] Harvest done: %d sanastoa", total)
        return total

    async def _fetch_organizations(
        self, client: Any,
    ) -> dict[str, dict[str, str]]:
        """Hae organisaatiot id → label -mappaus."""
        try:
            resp = await self._fetch(
                client, f"{API_BASE}/frontend/organizations",
            )
            orgs_list = resp.json()
            return {
                org["id"]: org.get("label", {})
                for org in orgs_list
                if "id" in org
            }
        except Exception:
            logger.warning("[sanastot] Organisaatioiden haku epäonnistui")
            return {}

    def _process_terminology(
        self,
        term: dict[str, Any],
        orgs: dict[str, dict[str, str]],
    ) -> None:
        """Luo Dataset yhdestä terminologiasta."""
        prefix = term.get("prefix", "")
        labels = term.get("label", {})
        title_fi = labels.get("fi", labels.get("en", prefix))
        title_en = labels.get("en", "")
        title_sv = labels.get("sv", "")

        desc = term.get("description", {}) or {}
        notes_fi = desc.get("fi", "")
        notes_en = desc.get("en", "")

        # Resolvoi organisaatio
        org_ids = term.get("organizations", [])
        org_label = {}
        if org_ids:
            org_label = orgs.get(org_ids[0], {})
        org_title = org_label.get("fi", org_label.get("en", ""))

        dataset_id = f"sanastot-{prefix}"
        modified = term.get("modified", "")
        uri = term.get("uri", f"https://sanastot.suomi.fi/terminology/{prefix}")

        # Resurssit: HTML-sivu ja JSON-LD export
        resources = [
            Resource(
                id=f"{dataset_id}-html",
                name=f"{title_fi} (HTML)",
                name_fi=f"{title_fi} — verkkosivu",
                format="HTML",
                url=f"https://sanastot.suomi.fi/terminology/{prefix}",
            ),
            Resource(
                id=f"{dataset_id}-json-ld",
                name=f"{title_fi} (JSON-LD)",
                name_fi=f"{title_fi} — JSON-LD",
                format="JSON-LD",
                url=f"https://sanastot.suomi.fi/terminology-api/v2/export/{prefix}?format=json-ld",
            ),
        ]

        dataset = self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=title_fi,
            title_fi=title_fi,
            title_en=title_en,
            title_sv=title_sv,
            notes_fi=notes_fi,
            notes_en=notes_en,
            organization_id=org_ids[0] if org_ids else "",
            organization_name=prefix,
            organization_title=org_title,
            keywords_fi=["sanasto", "terminologia", "yhteentoimivuus"],
            update_frequency="tarvittaessa",
            num_resources=len(resources),
            resources=resources,
            metadata_modified=modified,
        )
        upsert_dataset(self.conn, dataset)
