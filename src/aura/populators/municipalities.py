"""Kuntatiedot Tilastokeskuksen luokituspalvelusta."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from aura.populators.base import BasePopulator

logger = logging.getLogger(__name__)

API_BASE = "https://data.stat.fi/api/classifications/v2"


class MunicipalityPopulator(BasePopulator):
    """Populoi Suomen kuntatiedot Tilastokeskuksen luokituspalvelusta."""

    name = "municipalities"
    description = "Suomen kunnat, maakunnat, ELY-keskukset ja hyvinvointialueet"
    source_url = "https://data.stat.fi/api/classifications/v2/"

    async def populate(self) -> int:
        """Hae kuntatiedot ja tallenna ref_municipalities-tauluun."""
        async with self._make_client(timeout=60.0) as client:
            # 1. Hae uusin kunta-luokitusversio
            version = await self._find_latest_version(client)
            logger.info("[%s] Uusin versio: %s", self.name, version)

            # 2. Hae kunnat fi + sv
            names_fi = await self._fetch_items(client, "kunta", version, "fi")
            names_sv = await self._fetch_items(client, "kunta", version, "sv")

            # 3. Hae vastaavuustaulut
            region_map = await self._fetch_correspondence(
                client, "kunta", "maakunta", version,
            )
            region_names = await self._fetch_items(
                client, "maakunta", version, "fi",
            )

            ely_map = await self._fetch_correspondence(
                client, "kunta", "ely", version,
            )
            ely_names = await self._fetch_items(client, "ely", version, "fi")

            hva_map = await self._fetch_correspondence(
                client, "kunta", "hyvinvointialue", version,
            )
            hva_names = await self._fetch_items(
                client, "hyvinvointialue", version, "fi",
            )

        # 4. Yhdistä ja tallenna
        count = 0
        for code, name_fi in names_fi.items():
            name_sv = names_sv.get(code, name_fi)

            region_code = region_map.get(code)
            ely_code = ely_map.get(code)
            hva_code = hva_map.get(code)

            self.conn.execute(
                """
                INSERT INTO ref_municipalities (
                    code, name_fi, name_sv,
                    region_code, region_name_fi,
                    ely_code, ely_name_fi,
                    wellbeing_area_code, wellbeing_area_name_fi,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(code) DO UPDATE SET
                    name_fi = excluded.name_fi,
                    name_sv = excluded.name_sv,
                    region_code = excluded.region_code,
                    region_name_fi = excluded.region_name_fi,
                    ely_code = excluded.ely_code,
                    ely_name_fi = excluded.ely_name_fi,
                    wellbeing_area_code = excluded.wellbeing_area_code,
                    wellbeing_area_name_fi = excluded.wellbeing_area_name_fi,
                    updated_at = excluded.updated_at
                """,
                (
                    code, name_fi, name_sv,
                    region_code,
                    region_names.get(region_code, "") if region_code else None,
                    ely_code,
                    ely_names.get(ely_code, "") if ely_code else None,
                    hva_code,
                    hva_names.get(hva_code, "") if hva_code else None,
                ),
            )
            count += 1

        self.conn.commit()
        self._update_metadata(count, version=version)
        logger.info("[%s] Tallennettu %d kuntaa", self.name, count)
        return count

    async def _find_latest_version(self, client: httpx.AsyncClient) -> str:
        """Hae uusin kunta-luokitusversio listaamalla kaikki luokitukset."""
        resp = await self._fetch(
            client, f"{API_BASE}/classifications", params={"format": "json"},
        )
        urls: list[str] = resp.json()

        pattern = re.compile(r"/kunta_1_(\d{8})$")
        versions: list[str] = []
        for url in urls:
            m = pattern.search(url)
            if m:
                versions.append(m.group(1))

        if not versions:
            msg = "Kunta-luokitusversioita ei löytynyt"
            raise RuntimeError(msg)

        versions.sort()
        return versions[-1]

    async def _fetch_items(
        self,
        client: httpx.AsyncClient,
        classification: str,
        version: str,
        lang: str,
    ) -> dict[str, str]:
        """Hae luokituksen itemit. Palauttaa {code: name}."""
        class_id = f"{classification}_1_{version}"
        url = f"{API_BASE}/classifications/{class_id}/classificationItems"
        resp = await self._fetch(
            client, url,
            params={"content": "data", "meta": "max", "lang": lang, "format": "json"},
        )
        items: list[dict[str, Any]] = resp.json()

        result: dict[str, str] = {}
        for item in items:
            code = item["code"]
            names = item.get("classificationItemNames", [])
            name = names[0]["name"] if names else ""
            result[code] = name

        return result

    async def _fetch_correspondence(
        self,
        client: httpx.AsyncClient,
        source_cls: str,
        target_cls: str,
        version: str,
    ) -> dict[str, str]:
        """Hae vastaavuustaulu. Palauttaa {source_code: target_code}.

        Tilastokeskuksen API palauttaa listan URL:eja muodossa:
        .../maps/{source_code}/{target_code}
        """
        source_id = f"{source_cls}_1_{version}"
        target_id = f"{target_cls}_1_{version}"
        table_id = f"{source_id}#{target_id}"
        url = f"{API_BASE}/correspondenceTables/{table_id}/maps"

        resp = await self._fetch(
            client, url, params={"format": "json"},
        )
        urls: list[str] = resp.json()

        result: dict[str, str] = {}
        for map_url in urls:
            # .../maps/{source_code}/{target_code}
            parts = map_url.rstrip("/").split("/")
            if len(parts) >= 2:
                source_code = parts[-2]
                target_code = parts[-1]
                result[source_code] = target_code

        return result
