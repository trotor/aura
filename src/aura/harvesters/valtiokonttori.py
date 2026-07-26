"""Harvester Valtiokonttorin avoindata.tutkihallintoa.fi -rajapinnalle."""

from __future__ import annotations

import logging
import re
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

# Azure APIM:n kehittäjäportaali julkaisee taustarajapintansa osoitteen
# omassa config.json-tiedostossaan. Luetaan se ajonaikaisesti sen sijaan että
# kovakoodattaisiin: portaali siirsi datarajapinnan omalle domainilleen
# (avoindata.tutkihallintoa.fi/developer/apis → *.data.azure-api.net), mikä
# hiljensi harvesterin nollaan datasettiin.
PORTAL_CONFIG_URL = "https://avoindata.tutkihallintoa.fi/config.json"

# Varajärjestely jos config.json ei ole saatavilla (havaittu 2026-07-26).
FALLBACK_DATA_API_URL = "https://vkf-ipa-p-public-apim.data.azure-api.net"
FALLBACK_DATA_API_VERSION = "2022-04-01-preview"

API_GATEWAY_URL = "https://api.tutkihallintoa.fi"

# API-kohtaiset lisätiedot
API_METADATA: dict[str, dict[str, Any]] = {
    "valtiontalous": {
        "title_fi": "Valtion taloustiedot",
        "keywords": ["valtiontalous", "budjetti", "talousarvio", "tilinpäätös"],
        "update_frequency": "kuukausittain",
        "description_fi": (
            "Valtion talousarviotalouden tapahtumatiedot, "
            "hallinnonalat, kirjanpitoyksiköt ja momentit."
        ),
    },
    "centralgovernmentdebt": {
        "title_fi": "Valtionvelka",
        "keywords": ["valtionvelka", "velka", "BKT", "obligaatiot"],
        "update_frequency": "kuukausittain",
        "description_fi": (
            "Valtionvelan aikasarjat, velkarakenne, lainaohjelmat "
            "ja korkotiedot vuodesta 1940."
        ),
    },
    "financingandloans": {
        "title_fi": "Rahoitus ja lainat",
        "keywords": ["lainat", "rahoitus", "arava", "ASP", "takaukset"],
        "update_frequency": "kuukausittain",
        "description_fi": (
            "Valtiokonttorin hoitamat lainakannat, arava-lainat, "
            "ASP-järjestelmä ja valtiontakaukset."
        ),
    },
    "valtionhenkilosto": {
        "title_fi": "Valtion henkilöstö",
        "keywords": ["henkilöstö", "valtio", "työvuodet", "työntekijät"],
        "update_frequency": "kuukausittain",
        "description_fi": (
            "Valtion henkilöstön henkilötyövuodet ja lukumäärät "
            "kuukausittain vuodesta 2010."
        ),
    },
    "kuntatalous": {
        "title_fi": "Kuntatalous",
        "keywords": ["kunnat", "kuntatalous", "taksonomia", "tilinpäätös"],
        "update_frequency": "vuosittain",
        "description_fi": (
            "Kuntien talousraportoinnin taksonomia- ja dimensiotiedot."
        ),
    },
    "tilikartta": {
        "title_fi": "Valtion tilikartta",
        "keywords": ["tilikartta", "kirjanpito", "tililuokat"],
        "update_frequency": "vuosittain",
        "description_fi": (
            "Valtion liikekirjanpidon tilikartta: tililuokat, "
            "tililajit, tilit ja lisäjaottelut."
        ),
    },
}


class ValtiokonttoriHarvester(BaseHarvester):
    """Kerää Valtiokonttorin avoimet tietoaineistot APIM-rajapinnasta.

    Käyttää Azure API Managementin discovery-rajapintaa API:en ja
    operaatioiden listaamiseen. Kukin operaatio (endpoint) on oma datasettinsä.
    """

    name = "valtiokonttori"
    description = "Valtiokonttori — julkishallinnon talous- ja henkilöstödata"
    url = "https://avoindata.tutkihallintoa.fi"

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "custom",
            "query_protocol": "rest_json",
            "api_base_url": "https://avoindata.tutkihallintoa.fi",
        })
        return config

    def __init__(self, conn: Any = None) -> None:
        super().__init__(conn)
        self._data_api_url = FALLBACK_DATA_API_URL
        self._data_api_version = FALLBACK_DATA_API_VERSION

    async def harvest(self) -> int:
        total = 0

        async with self._make_client(timeout=30.0) as client:
            await self._discover_data_api(client)
            apis = await self._fetch_apis(client)
            for api in apis:
                count = await self._harvest_api(client, api)
                total += count

        logger.info("[valtiokonttori] Harvest valmis: %d datasettiä", total)
        return total

    async def _discover_data_api(self, client: Any) -> None:
        """Lue taustarajapinnan osoite portaalin config.json:sta.

        Azure APIM:n kehittäjäportaali julkaisee oman datarajapintansa
        osoitteen ja versionsa. Lukemalla ne ajonaikaisesti harvesteri kestää
        sen, että portaali siirtää rajapinnan toiseen osoitteeseen.
        """
        try:
            response = await self._fetch(client, PORTAL_CONFIG_URL)
            config: dict[str, Any] = response.json()
        except Exception as e:
            logger.warning(
                "[valtiokonttori] config.json ei saatavilla (%s), "
                "käytetään varaosoitetta %s",
                e, FALLBACK_DATA_API_URL,
            )
            return

        url = config.get("dataApiUrl")
        if isinstance(url, str) and url:
            self._data_api_url = url.rstrip("/")
        version = config.get("dataApiVersion")
        if isinstance(version, str) and version:
            self._data_api_version = version

        logger.info(
            "[valtiokonttori] Datarajapinta: %s (api-version=%s)",
            self._data_api_url, self._data_api_version,
        )

    def _data_api(self, path: str) -> str:
        """Rakenna datarajapinnan URL versioparametrilla."""
        return f"{self._data_api_url}/{path}?api-version={self._data_api_version}"

    async def _fetch_apis(self, client: Any) -> list[dict[str, Any]]:
        """Hae API-lista APIM discovery -endpointista."""
        try:
            response = await self._fetch(client, self._data_api("apis"))
            data: dict[str, Any] = response.json()
            result: list[dict[str, Any]] = data.get("value", [])
            return result
        except Exception as e:
            logger.warning("[valtiokonttori] Virhe API-listaa haettaessa: %s", e)
            return []

    async def _harvest_api(
        self,
        client: Any,
        api: dict[str, Any],
    ) -> int:
        """Hae yhden API:n operaatiot ja luo datasetit."""
        api_id = api.get("id", "")
        api_name = api.get("name", "")
        api_description = api.get("description", "")
        api_path = api.get("path", "")
        api_version = api.get("apiVersion", "v1")

        if not api_id or not api_name:
            return 0

        # Hae API:n operaatiot
        operations = await self._fetch_operations(client, api_id)
        if not operations:
            # Jos operaatioita ei saada, luo yksi datasetti koko API:lle
            self._create_api_dataset(api_id, api_name, api_description,
                                     api_path, api_version)
            self.conn.commit()
            return 1

        count = 0
        for op in operations:
            self._create_operation_dataset(
                api_id, api_name, api_description,
                api_path, api_version, op,
            )
            count += 1

        self.conn.commit()
        logger.info("[valtiokonttori/%s] %d operaatiota", api_name, count)
        return count

    async def _fetch_operations(
        self,
        client: Any,
        api_id: str,
    ) -> list[dict[str, Any]]:
        """Hae API:n operaatiot APIM:stä."""
        url = self._data_api(f"apis/{api_id}/operations")
        try:
            response = await self._fetch(client, url)
            data: dict[str, Any] = response.json()
            result: list[dict[str, Any]] = data.get("value", [])
            return result
        except Exception as e:
            logger.warning(
                "[valtiokonttori] Virhe operaatioita haettaessa %s: %s",
                api_id, e,
            )
            return []

    def _normalize_api_id(self, api_id: str) -> str:
        """Normalisoi API ID avaimeksi API_METADATA-hakuun.

        Erottimet poistetaan ja mahdollinen versiopääte katkaistaan:
        portaali on käyttänyt sekä muotoa ``valtiontalousv1`` että
        ``central-government-debt``.
        """
        key = api_id.lower().replace("-", "").replace("_", "")
        return re.sub(r"v\d+$", "", key)

    def _get_api_meta(self, api_id: str) -> dict[str, Any]:
        """Hae API-kohtaiset lisätiedot."""
        key = self._normalize_api_id(api_id)
        return API_METADATA.get(key, {})

    def _create_api_dataset(
        self,
        api_id: str,
        api_name: str,
        api_description: str,
        api_path: str,
        api_version: str,
    ) -> None:
        """Luo datasetti koko API:lle (kun operaatioita ei saatu)."""
        meta = self._get_api_meta(api_id)
        title = meta.get("title_fi", api_name)
        keywords = meta.get("keywords", ["talous", "valtio"])
        desc = meta.get("description_fi", api_description)
        freq = meta.get("update_frequency", "vuosittain")

        endpoint_url = f"{API_GATEWAY_URL}/{api_path}/{api_version}"
        dataset_id = f"valtiokonttori-{api_path}"

        dataset = self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=title,
            title_fi=title,
            notes_fi=desc,
            organization_id="valtiokonttori",
            organization_name="valtiokonttori",
            organization_title="Valtiokonttori",
            update_frequency=freq,
            keywords_fi=["talous", "julkishallinto"] + keywords,
            num_resources=1,
            resources=[
                Resource(
                    id=f"{dataset_id}-api",
                    name=api_name,
                    name_fi=title,
                    format="API",
                    url=endpoint_url,
                ),
            ],
        )
        upsert_dataset(self.conn, dataset)

    def _create_operation_dataset(
        self,
        api_id: str,
        api_name: str,
        api_description: str,
        api_path: str,
        api_version: str,
        operation: dict[str, Any],
    ) -> None:
        """Luo datasetti yhdestä API-operaatiosta."""
        op_name = operation.get("name", "")
        op_description = operation.get("description", "")
        op_url_template = operation.get("urlTemplate", "")

        if not op_name:
            return

        meta = self._get_api_meta(api_id)
        api_title = meta.get("title_fi", api_name)
        keywords = meta.get("keywords", ["talous", "valtio"])
        freq = meta.get("update_frequency", "vuosittain")

        # Muodosta dataset-tunniste
        safe_op = op_url_template.strip("/").replace("/", "-") or op_name
        dataset_id = f"valtiokonttori-{api_path}-{safe_op}"

        # Otsikko: "API-nimi: Operaation nimi"
        title = f"{api_title}: {op_name}"

        # Kuvaus operaation kuvauksesta tai API:n kuvauksesta
        desc = op_description or api_description or ""

        # Endpoint URL
        endpoint = f"{API_GATEWAY_URL}/{api_path}/{api_version}"
        if op_url_template:
            endpoint = f"{endpoint}/{op_url_template.lstrip('/')}"

        # Resurssityyppi: API palauttaa JSON tai CSV
        fmt = self._guess_format(op_url_template, op_name)

        dataset = self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=title,
            title_fi=title,
            notes_fi=desc,
            organization_id="valtiokonttori",
            organization_name="valtiokonttori",
            organization_title="Valtiokonttori",
            update_frequency=freq,
            keywords_fi=["talous", "julkishallinto"] + keywords,
            num_resources=1,
            resources=[
                Resource(
                    id=f"{dataset_id}-api",
                    name=op_url_template or op_name,
                    name_fi=op_name,
                    format=fmt,
                    url=endpoint,
                ),
            ],
        )
        upsert_dataset(self.conn, dataset)

        # Enrichment: operaation parametrit
        self._enrich_operation(dataset_id, operation)

    def _enrich_operation(
        self, dataset_id: str, operation: dict[str, Any],
    ) -> None:
        """Rikasta datasetti operaation tiedoilla."""
        # Query-parametrit → access_instructions
        params = operation.get("templateParameters", [])
        if params:
            param_names = [
                p.get("name", "") for p in params[:15] if p.get("name")
            ]
            if param_names:
                self._add_enrichment(
                    dataset_id, "access_instructions",
                    f"Query-parametrit: {', '.join(param_names)}",
                    source_detail="APIM operation parameters",
                )

        # Kuvaus → description_extended
        desc = operation.get("description", "")
        if desc and len(desc) > 50:
            self._add_enrichment(
                dataset_id, "description_extended",
                desc,
                source_detail="APIM operation description",
            )

    @staticmethod
    def _guess_format(url_template: str, op_name: str) -> str:
        """Arvaa resurssin formaatti nimestä."""
        combined = (url_template + op_name).lower()
        if "csv" in combined or "tiedosto" in combined or "file" in combined:
            return "CSV"
        return "API"
