"""Kuntatiedot Tilastokeskuksen luokituspalvelusta."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from aura.populators.base import BasePopulator

logger = logging.getLogger(__name__)

API_BASE = "https://data.stat.fi/api/classifications/v2"

#: Sotkanetin aluerekisteri. Antaa 540 aluetta 15 kategoriassa; meitä
#: kiinnostavat KUNTA, MAAKUNTA ja HYVINVOINTIALUE, joissa ``code`` on
#: Tilastokeskuksen koodi ja ``id`` Sotkanetin oma tunnus.
SOTKANET_REGIONS_URL = "https://sotkanet.fi/rest/1.1/regions"


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

            # 3. Hae vastaavuustaulut (osaa puuttua uusimmasta versiosta)
            region_map = await self._fetch_correspondence(
                client,
                "kunta",
                "maakunta",
                version,
            )
            region_names = (
                await self._fetch_items(client, "maakunta", version, "fi") if region_map else {}
            )

            ely_map = await self._fetch_correspondence(
                client,
                "kunta",
                "ely",
                version,
            )
            ely_names = await self._fetch_items(client, "ely", version, "fi") if ely_map else {}

            hva_map = await self._fetch_correspondence(
                client,
                "kunta",
                "hyvinvointialue",
                version,
            )
            hva_names = (
                await self._fetch_items(client, "hyvinvointialue", version, "fi") if hva_map else {}
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
                    code,
                    name_fi,
                    name_sv,
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

        # Sotkanet-tunnukset omana vaiheenaan: ne ovat lisätieto, ei
        # kuntataulun ydin. Jos Sotkanet on nurin, kuntien nimet ja
        # aluejaot on silti tallennettava.
        await self._populate_sotkanet_ids()

        self._update_metadata(count, version=version)
        logger.info("[%s] Tallennettu %d kuntaa", self.name, count)
        return count

    async def _populate_sotkanet_ids(self) -> int:
        """Liitä Sotkanetin omat aluetunnukset kuntariveille.

        Sotkanet ei kysele kuntakoodilla vaan omalla tunnuksellaan:
        Kuopio on kuntakoodiltaan 297 mutta Sotkanetissa alue 161.

        Palauttaa päivitettyjen rivien määrän; 0 jos haku epäonnistui.
        """
        try:
            async with self._make_client(timeout=60.0) as client:
                resp = await self._fetch(client, SOTKANET_REGIONS_URL)
                regions: list[dict[str, Any]] = resp.json()
        except Exception as exc:  # noqa: BLE001 — lisätieto ei saa kaataa ajoa
            logger.warning(
                "[%s] Sotkanet-aluetunnuksia ei saatu (%s); kuntataulu on muuten ajan tasalla",
                self.name,
                exc,
            )
            return 0

        by_category: dict[str, dict[str, int]] = {}
        for r in regions:
            code, rid = r.get("code"), r.get("id")
            if code and rid is not None:
                by_category.setdefault(str(r.get("category")), {})[str(code)] = int(rid)

        kunnat = by_category.get("KUNTA", {})
        maakunnat = by_category.get("MAAKUNTA", {})
        hvat = by_category.get("HYVINVOINTIALUE", {})

        updated = 0
        for row in self.conn.execute(
            "SELECT code, region_code, wellbeing_area_code FROM ref_municipalities"
        ).fetchall():
            self.conn.execute(
                "UPDATE ref_municipalities SET sotkanet_id = ?,"
                " sotkanet_region_id = ?, sotkanet_wellbeing_area_id = ?"
                " WHERE code = ?",
                (
                    kunnat.get(row["code"]),
                    maakunnat.get(row["region_code"]) if row["region_code"] else None,
                    hvat.get(row["wellbeing_area_code"]) if row["wellbeing_area_code"] else None,
                    row["code"],
                ),
            )
            updated += 1
        self.conn.commit()
        logger.info(
            "[%s] Sotkanet-tunnukset: %d kuntaa, %d maakuntaa, %d hyvinvointialuetta",
            self.name,
            len(kunnat),
            len(maakunnat),
            len(hvat),
        )
        return updated

    async def _find_latest_version(self, client: httpx.AsyncClient) -> str:
        """Hae uusin kunta-luokitusversio listaamalla kaikki luokitukset."""
        resp = await self._fetch(
            client,
            f"{API_BASE}/classifications",
            params={"format": "json"},
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
            client,
            url,
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

        Palauttaa tyhjän dictin jos vastaavuustaulua ei löydy (404).
        """
        source_id = f"{source_cls}_1_{version}"
        target_id = f"{target_cls}_1_{version}"
        # # on URL-fragmentin erotin — enkoodataan %23
        table_id = f"{source_id}%23{target_id}"
        url = f"{API_BASE}/correspondenceTables/{table_id}/maps"

        try:
            resp = await self._fetch(
                client,
                url,
                params={"format": "json"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning(
                    "[%s] Vastaavuustaulu %s -> %s ei löytynyt versiolle %s",
                    self.name,
                    source_cls,
                    target_cls,
                    version,
                )
                return {}
            raise

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
