"""Harvester Digitraffic REST API:lle."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

# Digitraffic-rajapinnat
APIS = {
    "tie": {
        "name": "Tieliikenne",
        "base_url": "https://tie.digitraffic.fi",
        "swagger_url": "https://tie.digitraffic.fi/swagger/openapi.json",
    },
    "rata": {
        "name": "Rautatieliikenne",
        "base_url": "https://rata.digitraffic.fi",
        "swagger_url": "https://rata.digitraffic.fi/swagger/openapi.json",
    },
    "meri": {
        "name": "Meriliikenne",
        "base_url": "https://meri.digitraffic.fi",
        "swagger_url": "https://meri.digitraffic.fi/swagger/openapi.json",
    },
}


class DigitrafficHarvester(BaseHarvester):
    """Kerää Digitraffic-rajapintojen metatiedot OpenAPI-spekseistä.

    Digitraffic tarjoaa reaaliaikaista liikennedataa tie-, rautatie- ja meriliikenteestä.
    Kukin API-endpoint on oma datasettinsä.
    """

    name = "digitraffic"
    description = "Digitraffic — reaaliaikainen liikennedatan rajapinta"
    url = "https://www.digitraffic.fi"

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "openapi",
            "query_protocol": "rest_json",
            "api_base_url": "https://tie.digitraffic.fi",
        })
        return config

    async def harvest(self) -> int:
        total = 0

        async with self._make_client(timeout=30.0) as client:
            for api_key, api_info in APIS.items():
                count = await self._harvest_api(client, api_key, api_info)
                total += count

        logger.info("[digitraffic] Harvest valmis: %d datasettiä", total)
        return total

    async def _harvest_api(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        api_info: dict[str, str],
    ) -> int:
        """Hae yhden Digitraffic-rajapinnan OpenAPI-speksi ja luo datasetit."""
        try:
            response = await self._fetch(
                client,
                api_info["swagger_url"],
                headers={"Accept-Encoding": "gzip"},
            )
            spec = response.json()
        except Exception as e:
            logger.warning("[digitraffic] Virhe haettaessa %s: %s", api_key, e)
            return 0

        count = 0
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            # Ota vain GET-endpointit (datan luku)
            if "get" not in methods:
                continue

            get_info = methods["get"]
            summary = get_info.get("summary", "")
            description = get_info.get("description", "")
            tags = get_info.get("tags", [])

            endpoint_url = f"{api_info['base_url']}{path}"
            dataset_id = f"digitraffic-{api_key}-{path.strip('/').replace('/', '-')}"

            title_text = (
                f"{api_info['name']}: {summary}" if summary
                else f"{api_info['name']}: {path}"
            )
            dataset = self._make_dataset(
                id=dataset_id,
                name=dataset_id,
                title=title_text,
                title_fi=title_text,
                notes_fi=description or summary or "",
                organization_id="digitraffic",
                organization_name="digitraffic",
                organization_title="Fintraffic / Digitraffic",
                update_frequency="reaaliaikainen",
                keywords_fi=["liikenne", api_info["name"].lower()]
                + [t.lower() for t in tags],
                num_resources=1,
                resources=[
                    Resource(
                        id=f"{dataset_id}-api",
                        name=path,
                        name_fi=summary or path,
                        format="API",
                        url=endpoint_url,
                    ),
                ],
                estimated_size_bytes=10_000_000,
            )

            upsert_dataset(self.conn, dataset)

            # Enrichment: OpenAPI-skeeman kentät
            self._enrich_from_openapi(dataset_id, get_info)
            count += 1

        self.conn.commit()
        logger.info("[digitraffic/%s] %d endpointia", api_key, count)
        return count

    def _enrich_from_openapi(
        self, dataset_id: str, get_info: dict[str, Any]
    ) -> None:
        """Rikasta datasetti OpenAPI-speksin tiedoilla."""
        # Response-skeeman kentät
        responses = get_info.get("responses", {})
        ok_resp = responses.get("200", responses.get("2XX", {}))
        content = ok_resp.get("content", {})
        json_schema = content.get("application/json", {}).get("schema", {})

        # Suora properties tai items.properties (taulukko)
        props = json_schema.get("properties", {})
        if not props and "items" in json_schema:
            props = json_schema["items"].get("properties", {})

        if props:
            fields = sorted(props.keys())[:30]  # max 30 kenttää
            self._add_enrichment(
                dataset_id, "data_fields",
                json.dumps(fields, ensure_ascii=False),
                confidence="verified",
                source_detail="OpenAPI schema",
            )

        # Parametrit → access_instructions
        params = get_info.get("parameters", [])
        if params:
            param_names = [
                f"{p.get('name', '')} ({p.get('in', '')})"
                for p in params[:10]
            ]
            self._add_enrichment(
                dataset_id, "access_instructions",
                f"Query-parametrit: {', '.join(param_names)}",
                source_detail="OpenAPI parameters",
            )
