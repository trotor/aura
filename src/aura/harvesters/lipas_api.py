"""Harvester LIPAS REST API v2:lle — liikuntapaikat tyypeittäin.

LIPAS (Jyväskylän yliopisto) sisältää ~57 000 liikuntapaikkaa, ulkoilureittiä
ja virkistysaluetta. Tämä harvester käyttää REST API v2:ta ja luo datasetin
jokaiselle liikuntapaikkatyypille (~140 tyyppiä).

API: https://api.lipas.fi/v2/
Lisenssi: CC BY 4.0
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

API_BASE = "https://api.lipas.fi/v2"
GEOSERVER_BASE = "http://lipas.cc.jyu.fi/geoserver/lipas"

MAX_CONCURRENT = 10


def _parse_type(item: dict[str, Any]) -> dict[str, Any]:
    """Poimi oleelliset kentät yhdestä tyyppi-objektista."""
    return {
        "type-code": item["type-code"],
        "name": item.get("name", {}),
        "description": item.get("description", {}),
        "tags": item.get("tags", {}),
        "geometry-type": item.get("geometry-type", ""),
    }


# Tyyppikoodi → avainsanat
_TYPE_KEYWORDS: dict[int, list[str]] = {
    # Reitit ja ladut
    4401: ["kuntorata", "juoksurata", "lenkkeily"],
    4402: ["hiihtolatu", "latu", "hiihto", "murtomaahiihto"],
    4403: ["kävelyreitti", "ulkoilureitti", "kävely"],
    4404: ["luontopolku", "luonto", "retkeily"],
    4405: ["retkeilyreitti", "retkeily", "vaellus"],
    4406: ["monikäyttöreitti", "ulkoilu"],
    4407: ["rullahiihto", "rullahiihtorata"],
    4411: ["maastopyöräily", "pyöräily"],
    4412: ["pyöräilyreitti", "pyöräily"],
    4421: ["moottorikelkka", "moottorikelkkareitti"],
    4422: ["moottorikelkka", "moottorikelkkaura"],
    4430: ["hevosreitti", "ratsastus"],
    4440: ["koirahiihtolatu", "koirahiihto"],
    4441: ["koiravaljakko", "koiravaljakkoreitti"],
    4451: ["melonta", "melontareitti"],
    4452: ["vesiretkeily", "vesiretkeilyreitti"],
    # Jääurheilu
    1510: ["tekojää", "tekojääkenttä", "luistelu"],
    1520: ["luistelu", "luistelukenttä"],
    1530: ["kaukalo", "jääkiekko"],
    1550: ["luistelureitti", "luistelu"],
    # Hiihto ja laskettelu
    4110: ["laskettelu", "laskettelurinne"],
    4220: ["hiihtotunneli", "hiihto"],
    4320: ["hyppyrimäki", "mäkihyppy"],
    4610: ["ampumahiihto"],
    4620: ["ampumahiihto"],
    4630: ["maastohiihto", "hiihtokeskus"],
    4640: ["hiihtomaa", "hiihto"],
    # Uinti
    3110: ["uimahalli", "uinti"],
    3210: ["maauimala", "vesipuisto"],
    3220: ["uimaranta", "uinti"],
    3230: ["uimapaikka", "uinti"],
    3240: ["talviuinti", "avantouinti"],
    # Palloilu
    1340: ["pallokenttä", "jalkapallo"],
    1350: ["jalkapallostadion", "jalkapallo"],
    1360: ["pesäpallo", "pesäpallokenttä"],
    1370: ["tennis", "tenniskenttä"],
    1390: ["padel", "padelkenttä"],
    1180: ["frisbeegolf", "frisbeegolfrata"],
    # Sisäliikunta
    2110: ["kuntokeskus", "fitness"],
    2120: ["kuntosali", "voimaharjoittelu"],
    2150: ["liikuntasali", "koululiikunta"],
    2210: ["liikuntahalli"],
    2520: ["jäähalli", "jääkiekko"],
}


class LipasApiHarvester(BaseHarvester):
    """Kerää LIPAS-liikuntapaikat REST API v2:n kautta tyypeittäin.

    Luo yhden datasetin per liikuntapaikkatyyppi (~140 datasettiä).
    Kukin datasetti kuvaa kyseisen tyypin kaikki kohteet ja linkittää
    REST API:n ja GeoServer-rajapintaan.
    """

    name = "lipas-api"
    description = "LIPAS REST API — Suomen liikuntapaikat tyypeittäin"
    url = "https://www.lipas.fi"

    request_delay = 0.1

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
        """Hae tyyppiluokitus ja luo datasetti per tyyppi."""
        async with self._make_client(timeout=60.0) as client:
            # Vaihe 1: Hae kategoriapuu
            types = await self._fetch_types(client)
            if not types:
                logger.warning("[lipas-api] Tyyppiluokitusta ei saatu")
                return 0

            logger.info("[lipas-api] %d tyyppiä löydetty", len(types))

            # Vaihe 2: Hae lukumäärät rinnakkaisesti
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            tasks = [
                self._fetch_and_save_type(client, semaphore, t)
                for t in types
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        count = sum(1 for r in results if r is True)
        errors = sum(1 for r in results if isinstance(r, Exception))
        if errors:
            logger.warning("[lipas-api] %d virhettä %d tyypistä", errors, len(types))
        logger.info("[lipas-api] Harvest valmis: %d datasettiä", count)
        return count

    async def _fetch_types(self, client: Any) -> list[dict[str, Any]]:
        """Hae kaikki tyyppiluokat kategoria-API:sta.

        API palauttaa tasalistan tyyppi-objekteja, joista kukin sisältää
        type-code, name, description, geometry-type jne.
        """
        try:
            response = await self._fetch(client, f"{API_BASE}/sports-site-categories")
            raw_types = response.json()
            return [_parse_type(t) for t in raw_types if "type-code" in t]
        except Exception:
            logger.exception("[lipas-api] Kategoriahaku epäonnistui")
            return []

    async def _fetch_and_save_type(
        self,
        client: Any,
        semaphore: asyncio.Semaphore,
        type_info: dict[str, Any],
    ) -> bool:
        """Hae yhden tyypin lukumäärä ja tallenna datasettinä."""
        type_code = type_info["type-code"]
        async with semaphore:
            try:
                response = await self._fetch(
                    client,
                    f"{API_BASE}/sports-sites?type-codes={type_code}&limit=1",
                )
                data = response.json()
            except Exception:
                logger.warning("[lipas-api] Tyyppi %d: haku epäonnistui", type_code)
                return False

        total = data.get("pagination", {}).get("total-items", 0)
        if total == 0:
            return False

        dataset = self._build_dataset(type_info, total)
        upsert_dataset(self.conn, dataset)
        self._auto_enrich_crs(dataset)
        self.conn.commit()
        return True

    def _build_dataset(
        self, type_info: dict[str, Any], total: int,
    ) -> Any:
        """Muunna LIPAS-tyyppi Aura Dataset -olioksi."""
        type_code = type_info["type-code"]
        name_fi = type_info.get("name", {}).get("fi", f"Tyyppi {type_code}")
        name_en = type_info.get("name", {}).get("en", "")
        name_sv = type_info.get("name", {}).get("sv", "")
        desc_fi = type_info.get("description", {}).get("fi", "")
        desc_en = type_info.get("description", {}).get("en", "")
        geom_type = type_info.get("geometry-type", "")

        # Rikastettu kuvaus
        notes_parts = []
        if desc_fi:
            notes_parts.append(desc_fi)
        notes_parts.append(f"Kohteita: {total} kpl.")
        if geom_type:
            geom_label = {
                "Point": "pisteet", "LineString": "viivat", "Polygon": "alueet",
            }.get(geom_type, geom_type)
            notes_parts.append(f"Geometria: {geom_label}.")
        notes_parts.append(
            "Lähde: LIPAS-liikuntapaikkarekisteri (Jyväskylän yliopisto). "
            "Data haettavissa REST API:n ja WFS-rajapinnan kautta."
        )
        notes_fi = " ".join(notes_parts)

        notes_en_parts = []
        if desc_en:
            notes_en_parts.append(desc_en)
        notes_en_parts.append(f"Total: {total} facilities.")
        notes_en = " ".join(notes_en_parts)

        # Avainsanat
        keywords_fi = ["liikuntapaikka"]
        extra_kw = _TYPE_KEYWORDS.get(type_code, [])
        keywords_fi.extend(extra_kw)
        # Lisää nimen sanat avainsanoiksi
        for word in name_fi.lower().replace("/", " ").replace("-", " ").split():
            if len(word) > 3 and word not in keywords_fi:
                keywords_fi.append(word)

        api_url = f"{API_BASE}/sports-sites?type-codes={type_code}"

        resources = [
            Resource(
                id=f"lipas-api-{type_code}-json",
                name=f"{name_fi} (REST API)",
                name_fi=f"{name_fi} — REST API -haku",
                name_en=f"{name_en} (REST API)" if name_en else "",
                format="JSON",
                url=api_url,
                description=f"LIPAS REST API v2 — tyyppikoodi {type_code}, {total} kohdetta",
            ),
            Resource(
                id=f"lipas-api-{type_code}-wfs",
                name=f"{name_fi} (WFS)",
                name_fi=f"{name_fi} — WFS-rajapinta",
                format="WFS",
                url=f"{GEOSERVER_BASE}/ows?service=WFS",
                description="LIPAS GeoServer WFS — paikkatietorajapinta",
            ),
            Resource(
                id=f"lipas-api-{type_code}-wms",
                name=f"{name_fi} (WMS)",
                name_fi=f"{name_fi} — WMS-karttapalvelu",
                format="WMS",
                url=f"{GEOSERVER_BASE}/wms?service=WMS",
                description="LIPAS GeoServer WMS — karttakuvapalvelu",
            ),
        ]

        return self._make_dataset(
            id=f"lipas-api-{type_code}",
            name=f"lipas-api-{type_code}",
            title=f"LIPAS: {name_fi}",
            title_fi=f"LIPAS: {name_fi}",
            title_en=f"LIPAS: {name_en}" if name_en else "",
            title_sv=f"LIPAS: {name_sv}" if name_sv else "",
            notes_fi=notes_fi,
            notes_en=notes_en,
            organization_id="jyu-lipas",
            organization_name="jyu-lipas",
            organization_title="Jyväskylän yliopisto / LIPAS",
            keywords_fi=keywords_fi,
            update_frequency="jatkuva",
            num_resources=len(resources),
            resources=resources,
        )
