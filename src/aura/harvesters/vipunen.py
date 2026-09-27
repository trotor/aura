"""Harvester Opetushallinnon tilastopalvelu Vipusen avoimelle rajapinnalle.

Vipunen (vipunen.fi) on opetushallinnon tilastopalvelu. Sen avoin rajapinta
(``api.vipunen.fi/api``) julkaisee noin 50 tietojoukkoa rivitasolla:
oppilaat, opiskelijat, tutkinnot, hakeneet, rahoitus ja koulutuksen
kustannukset. Rajapinta ei vaadi avainta.

**Lisenssi.** Vipusen avoimen rajapinnan tiedot julkaistaan CC BY 4.0
-lisenssillä (tarkistettu 27.9.2026).

Rajapinta kertoo jokaisesta tietojoukosta vain nimen ja kentät tyyppeineen
(``/api/resources/{nimi}``). Otsikko muodostetaan nimestä, ja kentät
tallennetaan resurssin skeemaksi — ne ovat se tieto, jonka perusteella
agentti voi päättää kannattaako tietojoukkoa kysyä. Kuntakoodikenttä
(esim. ``koulutuksenKuntaKoodi``) merkitään alueulottuvuudeksi.

Rajapinta tukee suodatusta (``filter=tilastovuosi=="2023";sektoriKoodi=="5"``)
ja lukumäärää (``/data/count``); resurssin URL esikatselee tuhat riviä.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aura.database import upsert_dataset, upsert_resource_schema
from aura.harvesters.base import BaseHarvester
from aura.models import Resource
from aura.region_levels import FIELD as REGION_FIELD
from aura.region_levels import KUNTA

logger = logging.getLogger(__name__)

API = "https://api.vipunen.fi/api"

#: Lyhenteet nimissä → kirjoitusasu otsikossa.
_WORDS = {
    "amm": "ammatillinen",
    "amk": "ammattikorkeakoulu",
    "yo": "yliopisto",
    "esi": "esi-",
    "lkm": "lukumäärä",
}

#: Kentät joissa kunnan tai maakunnan koodi on — alueulottuvuus.
_AREA_FIELD = re.compile(r"kunta|maakunta", re.I)


def title_from_name(name: str) -> str:
    """``amm_rahoitus_opiskelijavuodet`` → ``Ammatillinen rahoitus opiskelijavuodet``."""
    parts = [_WORDS.get(p, p) for p in name.split("_") if p]
    text = " ".join(parts).replace("- ja ", "- ja ")
    text = re.sub(r"koulutuksenkustannukset", "koulutuksen kustannukset", text)
    return text[:1].upper() + text[1:]


class VipunenHarvester(BaseHarvester):
    """Kerää Vipusen tietojoukot ja niiden kentät."""

    name = "vipunen"
    description = "Vipunen — opetushallinnon tilastopalvelun avoin rajapinta"
    url = "https://vipunen.fi"

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update(
            {"harvester_type": "custom", "query_protocol": "rest_json", "api_base_url": API}
        )
        return config

    async def harvest(self) -> int:
        count = 0
        async with self._make_client(timeout=60.0) as client:
            names: list[str] = (await self._fetch(client, f"{API}/resources")).json()
            for name in names:
                try:
                    fields: list[dict[str, Any]] = (
                        await self._fetch(client, f"{API}/resources/{name}")
                    ).json()
                except Exception:  # noqa: BLE001 — yksi tietojoukko ei kaada keruuta
                    logger.warning("[vipunen] Kenttien haku epäonnistui: %s", name, exc_info=True)
                    fields = []
                self._save(name, fields)
                count += 1
        self.conn.commit()
        logger.info("[vipunen] %d tietojoukkoa", count)
        return count

    def _save(self, name: str, fields: list[dict[str, Any]]) -> None:
        field_names = [f.get("name", "") for f in fields if f.get("name")]
        area_fields = [f for f in field_names if _AREA_FIELD.search(f)]
        time_fields = [
            f for f in field_names if re.search(r"vuosi|lukuvuosi|kuukausi|pvm", f, re.I)
        ]
        notes = (
            f"Opetushallinnon tilastopalvelu Vipusen tietojoukko {name}. "
            f"Kentät: {', '.join(field_names[:40])}."
        )
        if area_fields:
            notes += f" Alueulottuvuus: {', '.join(area_fields[:6])}."
        keywords = ["koulutus", "opetus", "vipunen"] + [
            _WORDS.get(p, p) for p in name.split("_") if len(p) > 3
        ]
        dataset_id = f"vipunen-{name}"
        resource = Resource(
            id=f"{dataset_id}-data",
            name=f"{name} (JSON, 1 000 riviä)",
            name_fi="Tietojoukon rivit (JSON)",
            format="JSON",
            url=f"{API}/resources/{name}/data?limit=1000",
            description_fi=(
                'Suodatus: filter-parametri, esim. filter=tilastovuosi=="2023". '
                "Lukumäärä: /data/count. Sivutus: limit ja offset."
            ),
        )
        dataset = self._make_dataset(
            id=dataset_id,
            name=dataset_id,
            title=title_from_name(name),
            title_fi=title_from_name(name),
            notes=notes,
            notes_fi=notes,
            organization_id="vipunen",
            organization_name="vipunen",
            organization_title="Opetushallitus ja opetus- ja kulttuuriministeriö (Vipunen)",
            keywords_fi=list(dict.fromkeys(keywords)),
            update_frequency="vuosittain" if "kuukausi" not in name else "kuukausittain",
            resources=[resource],
        )
        upsert_dataset(self.conn, dataset)
        types = {f.get("name", ""): f.get("type", "") for f in fields}
        upsert_resource_schema(
            self.conn, resource.id, dataset_id, [(n, types.get(n, "")) for n in field_names]
        )
        kunta_fields = [f for f in area_fields if not re.search("maakunta", f, re.I)]
        if kunta_fields:
            # Sama merkintä kuin PxWeb- ja Sotkanet-aineistoilla: kunta on
            # dimensioarvo, joten aluehaku löytää tietojoukon (region_levels).
            self._add_enrichment(
                dataset_id, REGION_FIELD, KUNTA, source_detail=", ".join(kunta_fields[:6])
            )
        if time_fields:
            self._add_enrichment(dataset_id, "temporal_coverage", f"Aikakenttä: {time_fields[0]}")
