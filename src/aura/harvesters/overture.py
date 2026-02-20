"""Harvester Overture Maps -aineistoille (GeoParquet S3:ssä)."""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

OVERTURE_RELEASE = "2026-02-18.0"
S3_BASE = f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme"
SOURCE_COOP_BASE = f"https://data.source.coop/overture/overture-{OVERTURE_RELEASE}"

THEMES: list[dict[str, Any]] = [
    {
        "id": "buildings",
        "title": "Overture Maps: Rakennukset",
        "description": (
            "Maailmanlaajuinen rakennusaineisto GeoParquet-muodossa."
            " Sisältää rakennusten geometriat ja attribuutit.\n\n"
            "DuckDB-esimerkki Suomen rajauksella:\n"
            "```sql\n"
            "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
            f"{OVERTURE_RELEASE}/theme=buildings/type=building/*')\n"
            "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
            "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
            "```"
        ),
        "keywords": ["rakennus", "Overture Maps", "GeoParquet", "globaali"],
        "estimated_size_gb": 50,
    },
    {
        "id": "transportation",
        "title": "Overture Maps: Liikenneverkko",
        "description": (
            "Maailmanlaajuinen liikenneverkkoaineisto GeoParquet-muodossa."
            " Tiet, polut, rautatiet ja muut kulkuväylät.\n\n"
            "DuckDB-esimerkki Suomen rajauksella:\n"
            "```sql\n"
            "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
            f"{OVERTURE_RELEASE}/theme=transportation/type=segment/*')\n"
            "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
            "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
            "```"
        ),
        "keywords": ["liikenne", "tieverkko", "Overture Maps", "GeoParquet", "globaali"],
        "estimated_size_gb": 80,
    },
    {
        "id": "places",
        "title": "Overture Maps: Paikat (POI)",
        "description": (
            "Maailmanlaajuinen paikka- ja POI-aineisto GeoParquet-muodossa."
            " Ravintolat, kaupat, palvelut ja muut kiinnostavat kohteet.\n\n"
            "DuckDB-esimerkki Suomen rajauksella:\n"
            "```sql\n"
            "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
            f"{OVERTURE_RELEASE}/theme=places/type=place/*')\n"
            "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
            "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
            "```"
        ),
        "keywords": ["paikka", "POI", "Overture Maps", "GeoParquet", "globaali"],
        "estimated_size_gb": 10,
    },
    {
        "id": "addresses",
        "title": "Overture Maps: Osoitteet",
        "description": (
            "Maailmanlaajuinen osoiteaineisto GeoParquet-muodossa."
            " Strukturoidut osoitteet geokoodauksineen.\n\n"
            "DuckDB-esimerkki Suomen rajauksella:\n"
            "```sql\n"
            "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
            f"{OVERTURE_RELEASE}/theme=addresses/type=address/*')\n"
            "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
            "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
            "```"
        ),
        "keywords": ["osoite", "geokoodaus", "Overture Maps", "GeoParquet", "globaali"],
        "estimated_size_gb": 30,
    },
    {
        "id": "divisions",
        "title": "Overture Maps: Hallinnolliset alueet",
        "description": (
            "Maailmanlaajuinen hallinnollisten alueiden aineisto GeoParquet-muodossa."
            " Valtiot, maakunnat, kunnat ja muut hallintoalueet.\n\n"
            "DuckDB-esimerkki Suomen rajauksella:\n"
            "```sql\n"
            "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
            f"{OVERTURE_RELEASE}/theme=divisions/type=division_area/*')\n"
            "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
            "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
            "```"
        ),
        "keywords": ["hallinto", "alue", "kunta", "Overture Maps", "GeoParquet", "globaali"],
        "estimated_size_gb": 5,
    },
    {
        "id": "base",
        "title": "Overture Maps: Perusgeometria",
        "description": (
            "Maailmanlaajuinen perusgeometria-aineisto GeoParquet-muodossa."
            " Vesistöt, maasto, maankäyttöalueet ja infrastruktuuri.\n\n"
            "DuckDB-esimerkki Suomen rajauksella:\n"
            "```sql\n"
            "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
            f"{OVERTURE_RELEASE}/theme=base/type=land_use/*')\n"
            "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
            "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
            "```"
        ),
        "keywords": ["maasto", "vesistö", "maankäyttö", "Overture Maps", "GeoParquet", "globaali"],
        "estimated_size_gb": 40,
    },
]


class OvertureHarvester(BaseHarvester):
    """Kerää Overture Maps Foundation -aineistojen metatiedot.

    Overture Maps on Linux Foundationin alainen hanke joka tuottaa
    avoimen, maailmanlaajuisen kartta-aineiston GeoParquet-muodossa.
    Data on saatavilla S3:ssä ja source.coop:ssa.
    """

    name = "overture"
    description = "Overture Maps — globaali avoin kartta-aineisto (GeoParquet)"
    url = "https://overturemaps.org"

    async def harvest(self) -> int:
        count = 0

        for theme in THEMES:
            dataset = self._theme_to_dataset(theme)
            upsert_dataset(self.conn, dataset)
            count += 1

        self.conn.commit()
        logger.info("[overture] Harvest valmis: %d datasettiä", count)
        return count

    def _theme_to_dataset(self, theme: dict[str, Any]) -> Dataset:
        theme_id = theme["id"]
        size_bytes = int(theme["estimated_size_gb"] * 1024 * 1024 * 1024)

        return Dataset(
            id=f"overture-{theme_id}",
            name=f"overture-{theme_id}",
            title=theme["title"],
            title_fi=theme["title"],
            notes_fi=theme["description"],
            organization_id="overture",
            organization_name="overture",
            organization_title="Overture Maps Foundation",
            keywords_fi=theme.get("keywords", ["Overture Maps"]),
            license_id="ODbL-1.0",
            license_title="ODbL",
            collection_type="Open Data",
            geographical_coverage=["Maailma"],
            source=self.name,
            num_resources=2,
            resources=[
                Resource(
                    id=f"overture-{theme_id}-s3",
                    name=f"{theme['title']} (S3 GeoParquet)",
                    name_fi=f"{theme['title']} — S3 GeoParquet",
                    format="GeoParquet",
                    url=f"{S3_BASE}={theme_id}/",
                ),
                Resource(
                    id=f"overture-{theme_id}-https",
                    name=f"{theme['title']} (source.coop)",
                    name_fi=f"{theme['title']} — HTTPS-lataus",
                    format="GeoParquet",
                    url=f"{SOURCE_COOP_BASE}/theme={theme_id}/",
                ),
            ],
            estimated_size_bytes=size_bytes,
        )
