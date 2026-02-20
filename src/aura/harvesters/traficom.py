"""Harvester Traficomin OData v4 -rajapinnalle."""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

ODATA_BASE = "https://opendata.traficom.fi/api/v12"

# Tunnetut entity set -kuvaukset ja arvioidut koot
ENTITY_SETS: dict[str, dict[str, Any]] = {
    "AjoneuvorekisteriVer2": {
        "title_fi": "Ajoneuvorekisteri",
        "description": "Suomessa rekisteröidyt ajoneuvot",
        "keywords": ["ajoneuvot", "rekisteri", "liikenne"],
        "estimated_records": 5_100_000,
        "estimated_row_bytes": 500,
    },
    "AircraftRegister": {
        "title_fi": "Ilma-alusrekisteri",
        "description": "Suomessa rekisteröidyt ilma-alukset",
        "keywords": ["ilmailu", "lentokoneet", "rekisteri"],
        "estimated_records": 1_500,
        "estimated_row_bytes": 400,
    },
    "Alusrekisteri": {
        "title_fi": "Alusrekisteri",
        "description": "Suomessa rekisteröidyt alukset",
        "keywords": ["alukset", "laivat", "meriliikenne"],
        "estimated_records": 30_000,
        "estimated_row_bytes": 400,
    },
    "RautateidenKalustorekisteri": {
        "title_fi": "Rautateiden kalustorekisteri",
        "description": "Rautatiekalusto",
        "keywords": ["rautatiet", "kalusto", "junat"],
        "estimated_records": 5_000,
        "estimated_row_bytes": 300,
    },
    "Radioasematiedot": {
        "title_fi": "Radioasematiedot",
        "description": "Suomen radioasemat",
        "keywords": ["radio", "viestintä"],
        "estimated_records": 50_000,
        "estimated_row_bytes": 300,
    },
    "TVAsematiedot": {
        "title_fi": "TV-asematiedot",
        "description": "Suomen televisioasemat",
        "keywords": ["televisio", "viestintä"],
        "estimated_records": 5_000,
        "estimated_row_bytes": 300,
    },
    "RadioamatoorienKutsumerkit": {
        "title_fi": "Radioamatöörien kutsumerkit",
        "description": "Radioamatöörien myönnetyt kutsumerkit",
        "keywords": ["radioamatööri", "viestintä"],
        "estimated_records": 10_000,
        "estimated_row_bytes": 200,
    },
    "Meriradionumerot": {
        "title_fi": "Meriradionumerot",
        "description": "Meriradionumerot (MMSI)",
        "keywords": ["meriradio", "MMSI", "meriliikenne"],
        "estimated_records": 5_000,
        "estimated_row_bytes": 200,
    },
    "Taajuusjakotaulukko": {
        "title_fi": "Taajuusjakotaulukko",
        "description": "Radiotaajuuksien jakotaulukko Suomessa",
        "keywords": ["taajuudet", "radio", "viestintä"],
        "estimated_records": 1_000,
        "estimated_row_bytes": 500,
    },
    "TaajuusjakotaulukkoEN": {
        "title_fi": "Taajuusjakotaulukko (EN)",
        "description": "Frequency allocation table (English)",
        "keywords": ["taajuudet", "radio", "viestintä"],
        "estimated_records": 1_000,
        "estimated_row_bytes": 500,
    },
    "TaajuusjakotaulukkoSE": {
        "title_fi": "Taajuusjakotaulukko (SV)",
        "description": "Frekvensfördelningstabell (Svenska)",
        "keywords": ["taajuudet", "radio", "viestintä"],
        "estimated_records": 1_000,
        "estimated_row_bytes": 500,
    },
    "MatkaviestinverkkojenSuuntanumerot": {
        "title_fi": "Matkaviestinverkkojen suuntanumerot",
        "description": "Matkapuhelinverkkojen suuntanumerot",
        "keywords": ["matkapuhelin", "viestintä"],
        "estimated_records": 500,
        "estimated_row_bytes": 200,
    },
    "MNC_tunnukset": {
        "title_fi": "MNC-tunnukset",
        "description": "Mobile Network Code -tunnukset",
        "keywords": ["MNC", "matkapuhelin", "viestintä"],
        "estimated_records": 100,
        "estimated_row_bytes": 200,
    },
    "Laajakaistahankkeet": {
        "title_fi": "Laajakaistahankkeet",
        "description": "Tuetut laajakaistahankkeet",
        "keywords": ["laajakaista", "viestintä", "hankkeet"],
        "estimated_records": 1_000,
        "estimated_row_bytes": 500,
    },
    "Autoreporter": {
        "title_fi": "Autoreporter-liikennetiedot",
        "description": "Automaattinen liikenneraportointi",
        "keywords": ["liikenne", "automaattimittaus"],
        "estimated_records": 100_000,
        "estimated_row_bytes": 200,
    },
    "AutoreporterUTC": {
        "title_fi": "Autoreporter-liikennetiedot (UTC)",
        "description": "Automaattinen liikenneraportointi (UTC-aika)",
        "keywords": ["liikenne", "automaattimittaus"],
        "estimated_records": 100_000,
        "estimated_row_bytes": 200,
    },
}


class TraficomHarvester(BaseHarvester):
    """Kerää Traficomin avoimen datan OData v4 -rajapinnasta.

    Traficom tarjoaa liikenne- ja viestintärekistereitä: ajoneuvo-, ilma-alus-,
    alus- ja radiorekisterit sekä taajuustiedot.
    """

    name = "traficom"
    description = "Traficom — liikenne- ja viestintärekisterit"
    url = "https://opendata.traficom.fi"

    async def harvest(self) -> int:
        count = 0

        async with self._make_client(timeout=60.0) as client:
            # Hae saatavilla olevat entity setit
            try:
                response = await client.get(f"{ODATA_BASE}/")
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning("[traficom] Virhe haettaessa OData-juurta: %s", e)
                # Käytä tunnettua listaa
                data = {"value": [{"name": k, "url": f"{ODATA_BASE}/{k}"} for k in ENTITY_SETS]}

            entity_sets = data.get("value", [])

            for es in entity_sets:
                es_name = es.get("name", "")
                if not es_name:
                    continue

                info = ENTITY_SETS.get(es_name, {})
                title = info.get("title_fi", es_name)
                desc = info.get("description", "")
                keywords = info.get("keywords", ["liikenne", "viestintä"])
                records = info.get("estimated_records", 10_000)
                row_bytes = info.get("estimated_row_bytes", 300)

                dataset = self._make_dataset(
                    id=f"traficom-{es_name.lower()}",
                    name=f"traficom-{es_name.lower()}",
                    title=title,
                    title_fi=title,
                    notes_fi=desc,
                    organization_id="traficom",
                    organization_name="traficom",
                    organization_title="Liikenne- ja viestintävirasto Traficom",
                    keywords_fi=keywords,
                    num_resources=1,
                    resources=[
                        Resource(
                            id=f"traficom-{es_name.lower()}-odata",
                            name=f"{es_name} (OData)",
                            name_fi=f"{title} — OData-rajapinta",
                            format="API",
                            url=f"{ODATA_BASE}/{es_name}",
                        ),
                    ],
                    estimated_size_bytes=records * row_bytes,
                )
                upsert_dataset(self.conn, dataset)
                count += 1

        self.conn.commit()
        logger.info("[traficom] Harvest valmis: %d entity settiä", count)
        return count
