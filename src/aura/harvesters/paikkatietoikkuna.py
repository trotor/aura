"""Harvester Paikkatietoikkunan karttatasoille.

Paikkatietoikkuna on kansallinen paikkatietoportaali (Oskari-pohjainen),
jota ylläpitää Maanmittauslaitos. Se kokoaa ~2 800 karttatasoa 60+
organisaatiolta.

API: Oskari action routes (GetHierarchicalMapLayerGroups, GetCSWData)
Lisenssi: CC BY 4.0 (oletus)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

OSKARI_BASE = "https://kartta.paikkatietoikkuna.fi/action"

# Rinnakkaisten CSW-metatietopyyntöjen rajoitus
MAX_CONCURRENT = 10

# Karttatasotyypin muunnos formaatiksi
LAYER_TYPE_FORMAT: dict[str, str] = {
    "wmslayer": "WMS",
    "wfslayer": "WFS",
    "wmtslayer": "WMTS",
    "statslayer": "WFS",
    "tiles3dlayer": "3D Tiles",
    "arcgis93layer": "ArcGIS",
}


class PaikkatietoikkunaHarvester(BaseHarvester):
    """Kerää Paikkatietoikkunan karttatasot Oskari-rajapinnasta.

    Vaihe 1: Hae kaikki karttatasot, ryhmät ja tiedontuottajat
    (GetHierarchicalMapLayerGroups) — yksi pyyntö.

    Vaihe 2: Ryhmittele tasot metadataUuid:n mukaan dataseteiksi.
    Hae jokaiselle uniikille UUID:lle rikasmetatiedot (GetCSWData)
    rinnakkaisesti.
    """

    name = "paikkatietoikkuna"
    description = "Paikkatietoikkuna — kansallinen paikkatietoportaali"
    url = "https://paikkatietoikkuna.fi"

    request_delay = 0.1

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "oskari",
            "query_protocol": "oskari_action",
            "api_base_url": OSKARI_BASE,
        })
        return config

    async def harvest(self) -> int:
        """Hae kaikki Paikkatietoikkunan karttatasot."""
        async with self._make_client(timeout=60.0) as client:
            # Vaihe 1: Kaikki tasot yhdellä pyynnöllä
            data = await self._fetch_layers(client)
            if not data:
                return 0

            layers = data.get("layers", [])
            providers = data.get("providers", {})
            groups = data.get("groups", [])

            logger.info(
                "[paikkatietoikkuna] %d karttatasoa, %d tiedontuottajaa, %d ryhmää",
                len(layers), len(providers), len(groups),
            )

            # Ryhmittele tasot metadataUuid:n mukaan
            uuid_layers: dict[str, list[dict[str, Any]]] = {}
            no_uuid_layers: list[dict[str, Any]] = []

            for layer in layers:
                uuid = layer.get("metadataUuid", "")
                if uuid:
                    uuid_layers.setdefault(uuid, []).append(layer)
                else:
                    no_uuid_layers.append(layer)

            logger.info(
                "[paikkatietoikkuna] %d uniikkia metadataUuid, %d tasoa ilman UUID:tä",
                len(uuid_layers), len(no_uuid_layers),
            )

            # Luo ryhmähakemisto INSPIRE-teemoille
            group_map = self._build_group_map(groups)

            # Vaihe 2: Hae CSW-metatiedot rinnakkaisesti
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            tasks = [
                self._fetch_and_save_dataset(
                    client, semaphore, uuid, group_layers, providers, group_map,
                )
                for uuid, group_layers in uuid_layers.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        count = sum(1 for r in results if r is True)
        errors = sum(1 for r in results if isinstance(r, Exception))

        # Tasot ilman UUID:tä — luo minimidatasetit
        for layer in no_uuid_layers:
            try:
                self._save_layer_as_dataset(layer, providers, group_map)
                count += 1
            except Exception:
                errors += 1
                logger.debug(
                    "[paikkatietoikkuna] Tason %s tallennus epäonnistui",
                    layer.get("id"),
                )

        self.conn.commit()

        if errors:
            logger.warning(
                "[paikkatietoikkuna] %d virhettä %d datasetistä",
                errors, len(uuid_layers) + len(no_uuid_layers),
            )
        logger.info("[paikkatietoikkuna] Harvest valmis: %d datasettiä", count)
        return count

    async def _fetch_layers(
        self, client: Any,
    ) -> dict[str, Any]:
        """Hae kaikki karttatasot, ryhmät ja tiedontuottajat."""
        url = f"{OSKARI_BASE}?action_route=GetHierarchicalMapLayerGroups&lang=fi"
        try:
            response = await self._fetch(client, url)
            result: dict[str, Any] = response.json()
            return result
        except Exception:
            logger.exception("[paikkatietoikkuna] Karttatasojen haku epäonnistui")
            return {}

    async def _fetch_csw_metadata(
        self, client: Any, uuid: str,
    ) -> dict[str, Any]:
        """Hae CSW-metatiedot yksittäiselle datasetille."""
        url = f"{OSKARI_BASE}?action_route=GetCSWData&uuid={uuid}&lang=fi"
        response = await self._fetch(client, url)
        result: dict[str, Any] = response.json()
        return result

    async def _fetch_and_save_dataset(
        self,
        client: Any,
        semaphore: asyncio.Semaphore,
        uuid: str,
        layers: list[dict[str, Any]],
        providers: dict[str, Any],
        group_map: dict[int, str],
    ) -> bool:
        """Hae metatiedot ja tallenna datasetti."""
        async with semaphore:
            try:
                csw = await self._fetch_csw_metadata(client, uuid)
            except Exception:
                logger.debug(
                    "[paikkatietoikkuna] CSW-metatietojen haku epäonnistui: %s", uuid,
                )
                csw = {}

        dataset = self._build_dataset(uuid, layers, csw, providers, group_map)
        upsert_dataset(self.conn, dataset)
        return True

    def _save_layer_as_dataset(
        self,
        layer: dict[str, Any],
        providers: dict[str, Any],
        group_map: dict[int, str],
    ) -> None:
        """Tallenna yksittäinen taso datasettinä (ilman CSW-metatietoja)."""
        layer_id = layer.get("id", "")
        name = layer.get("name", f"Taso {layer_id}")
        layer_type = layer.get("type", "")
        fmt = LAYER_TYPE_FORMAT.get(layer_type, "WMS")
        url = layer.get("url", "")
        layer_name = layer.get("layerName", "")

        org_name, org_title = self._resolve_org(layer, providers)
        keywords = self._layer_keywords(layer, group_map)

        resources = []
        if url:
            resources.append(Resource(
                id=f"ptk-layer-{layer_id}",
                name=f"{name} ({fmt})",
                name_fi=f"{name} ({fmt})",
                format=fmt,
                url=url,
                description=layer_name,
            ))

        dataset = self._make_dataset(
            id=f"paikkatietoikkuna-layer-{layer_id}",
            name=f"paikkatietoikkuna-layer-{layer_id}",
            title=name,
            title_fi=name,
            organization_id=f"ptk-{org_name}",
            organization_name=org_name,
            organization_title=org_title,
            keywords_fi=keywords,
            num_resources=len(resources),
            resources=resources,
        )
        upsert_dataset(self.conn, dataset)

    def _build_dataset(
        self,
        uuid: str,
        layers: list[dict[str, Any]],
        csw: dict[str, Any],
        providers: dict[str, Any],
        group_map: dict[int, str],
    ) -> Any:
        """Muunna karttatasot + CSW-metatiedot Aura Dataset -olioksi."""
        # Käytä ensimmäistä tasoa oletusarvoille
        first = layers[0]

        # CSW-metatiedot
        ident = {}
        identifications = csw.get("identifications", [])
        if identifications:
            ident = identifications[0]

        title = (
            ident.get("citation", {}).get("title", "")
            or first.get("name", f"Datasetti {uuid[:8]}")
        )
        abstract = ident.get("abstractText", "")

        # Avainsanat CSW:stä (lista stringejä)
        keywords_fi: list[str] = []
        for kw in ident.get("descriptiveKeywords", []):
            if isinstance(kw, str) and kw and kw not in keywords_fi:
                keywords_fi.append(kw)
            elif isinstance(kw, dict):
                for k in kw.get("keywords", []):
                    if k and k not in keywords_fi:
                        keywords_fi.append(k)

        # Lisää INSPIRE-ryhmien nimet avainsanoihin
        for layer in layers:
            for group_id in layer.get("groups", []):
                group_name = group_map.get(group_id, "")
                if group_name and group_name not in keywords_fi:
                    keywords_fi.append(group_name)

        # Organisaatio
        org_name, org_title = self._resolve_org(first, providers)

        # Lisenssi CSW:stä
        license_title = "CC BY 4.0"
        license_id = "cc-by-4.0"
        constraints = ident.get("otherConstraints", [])
        if constraints:
            constraint_text = constraints[0] if isinstance(constraints[0], str) else ""
            if constraint_text:
                license_title = constraint_text
                if "cc" not in constraint_text.lower():
                    license_id = "other"

        # Aikaleima
        metadata_modified = csw.get("metadataDateStamp", "")
        if metadata_modified and "T" not in metadata_modified:
            metadata_modified = f"{metadata_modified}T00:00:00"

        # Resurssit — yksi per karttataso
        resources: list[Resource] = []
        for layer in layers:
            layer_id = layer.get("id", "")
            layer_name = layer.get("name", "")
            layer_type = layer.get("type", "")
            fmt = LAYER_TYPE_FORMAT.get(layer_type, "WMS")
            url = layer.get("url", "")

            if url:
                resources.append(Resource(
                    id=f"ptk-{layer_id}",
                    name=f"{layer_name} ({fmt})",
                    name_fi=f"{layer_name} ({fmt})",
                    format=fmt,
                    url=url,
                    description=layer.get("layerName", ""),
                ))

        # Paikkatietohakemiston metadatalinkki
        resources.append(Resource(
            id=f"ptk-meta-{uuid[:8]}",
            name="Metatiedot (Paikkatietohakemisto)",
            name_fi="Metatiedot (Paikkatietohakemisto)",
            format="HTML",
            url=f"https://www.paikkatietohakemisto.fi/geonetwork/srv/fin/catalog.search#/metadata/{uuid}",
        ))

        return self._make_dataset(
            id=f"paikkatietoikkuna-{uuid}",
            name=f"paikkatietoikkuna-{uuid}",
            title=title,
            title_fi=title,
            notes_fi=abstract,
            license_id=license_id,
            license_title=license_title,
            organization_id=f"ptk-{org_name}",
            organization_name=org_name,
            organization_title=org_title,
            keywords_fi=keywords_fi or ["paikkatietoikkuna", "paikkatietoaineisto"],
            metadata_modified=metadata_modified,
            num_resources=len(resources),
            resources=resources,
        )

    @staticmethod
    def _build_group_map(groups: list[dict[str, Any]]) -> dict[int, str]:
        """Rakenna ryhmä-ID → nimi -hakemisto."""
        result: dict[int, str] = {}
        for group in groups:
            gid = group.get("id")
            name = group.get("name", "")
            if gid is not None and name:
                result[gid] = name
        return result

    @staticmethod
    def _resolve_org(
        layer: dict[str, Any],
        providers: dict[str, Any],
    ) -> tuple[str, str]:
        """Palauta (org_name, org_title) karttatasolta."""
        org_name = layer.get("orgName", "")
        provider_id = str(layer.get("dataproviderId", ""))
        if provider_id and provider_id in providers:
            provider = providers[provider_id]
            org_title = provider.get("name", org_name)
        else:
            org_title = org_name
        # Käytä orgName tunnuksena
        if org_name:
            org_slug = org_name.lower().replace(" ", "-").replace(".", "")[:50]
        else:
            org_slug = "tuntematon"
        return org_slug, org_title

    @staticmethod
    def _layer_keywords(
        layer: dict[str, Any],
        group_map: dict[int, str],
    ) -> list[str]:
        """Kokoa avainsanat tasolta ja sen ryhmistä."""
        keywords = ["paikkatietoikkuna", "paikkatietoaineisto"]
        for group_id in layer.get("groups", []):
            name = group_map.get(group_id, "")
            if name and name not in keywords:
                keywords.append(name)
        return keywords
