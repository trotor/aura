"""Harvester Overture Maps -aineistoille (GeoParquet S3:ssä)."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

OVERTURE_RELEASE = "2026-02-18.0"
S3_BASE = f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme"
SOURCE_COOP_BASE = f"https://data.source.coop/overture/overture-{OVERTURE_RELEASE}"


def _theme(
    theme_id: str, title: str, description: str,
    keywords: list[str], size_gb: int,
) -> dict[str, object]:
    """Luo Overture-teeman konfiguraatio."""
    return {
        "id": f"overture-{theme_id}",
        "title": title,
        "notes_fi": description,
        "keywords_fi": keywords,
        "license_id": "ODbL-1.0",
        "license_title": "ODbL",
        "geographical_coverage": ["Maailma"],
        "estimated_size_bytes": size_gb * 1024**3,
        "resources": [
            {
                "id": f"overture-{theme_id}-s3",
                "name": f"{title} (S3 GeoParquet)",
                "name_fi": f"{title} — S3 GeoParquet",
                "format": "GeoParquet",
                "url": f"{S3_BASE}={theme_id}/",
            },
            {
                "id": f"overture-{theme_id}-https",
                "name": f"{title} (source.coop)",
                "name_fi": f"{title} — HTTPS-lataus",
                "format": "GeoParquet",
                "url": f"{SOURCE_COOP_BASE}/theme={theme_id}/",
            },
        ],
    }


_DUCKDB_EXAMPLE = (
    "DuckDB-esimerkki Suomen rajauksella:\n"
    "```sql\n"
    "SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/"
    f"{OVERTURE_RELEASE}/theme={{theme}}/type={{type}}/*')\n"
    "WHERE bbox.xmin > 19.5 AND bbox.xmax < 31.6\n"
    "  AND bbox.ymin > 59.7 AND bbox.ymax < 70.1;\n"
    "```"
)


class OvertureHarvester(StaticHarvester):
    """Kerää Overture Maps Foundation -aineistojen metatiedot.

    Overture Maps on Linux Foundationin alainen hanke joka tuottaa
    avoimen, maailmanlaajuisen kartta-aineiston GeoParquet-muodossa.
    Data on saatavilla S3:ssä ja source.coop:ssa.
    """

    name = "overture"
    description = "Overture Maps — globaali avoin kartta-aineisto (GeoParquet)"
    url = "https://overturemaps.org"
    org_id = "overture"
    org_name = "overture"
    org_title = "Overture Maps Foundation"

    datasets_config = [
        _theme(
            "buildings",
            "Overture Maps: Rakennukset",
            "Maailmanlaajuinen rakennusaineisto GeoParquet-muodossa."
            " Sisältää rakennusten geometriat ja attribuutit.\n\n"
            + _DUCKDB_EXAMPLE.format(theme="buildings", type="building"),
            ["rakennus", "Overture Maps", "GeoParquet", "globaali"],
            50,
        ),
        _theme(
            "transportation",
            "Overture Maps: Liikenneverkko",
            "Maailmanlaajuinen liikenneverkkoaineisto GeoParquet-muodossa."
            " Tiet, polut, rautatiet ja muut kulkuväylät.\n\n"
            + _DUCKDB_EXAMPLE.format(theme="transportation", type="segment"),
            ["liikenne", "tieverkko", "Overture Maps", "GeoParquet", "globaali"],
            80,
        ),
        _theme(
            "places",
            "Overture Maps: Paikat (POI)",
            "Maailmanlaajuinen paikka- ja POI-aineisto GeoParquet-muodossa."
            " Ravintolat, kaupat, palvelut ja muut kiinnostavat kohteet.\n\n"
            + _DUCKDB_EXAMPLE.format(theme="places", type="place"),
            ["paikka", "POI", "Overture Maps", "GeoParquet", "globaali"],
            10,
        ),
        _theme(
            "addresses",
            "Overture Maps: Osoitteet",
            "Maailmanlaajuinen osoiteaineisto GeoParquet-muodossa."
            " Strukturoidut osoitteet geokoodauksineen.\n\n"
            + _DUCKDB_EXAMPLE.format(theme="addresses", type="address"),
            ["osoite", "geokoodaus", "Overture Maps", "GeoParquet", "globaali"],
            30,
        ),
        _theme(
            "divisions",
            "Overture Maps: Hallinnolliset alueet",
            "Maailmanlaajuinen hallinnollisten alueiden aineisto GeoParquet-muodossa."
            " Valtiot, maakunnat, kunnat ja muut hallintoalueet.\n\n"
            + _DUCKDB_EXAMPLE.format(theme="divisions", type="division_area"),
            ["hallinto", "alue", "kunta", "Overture Maps", "GeoParquet", "globaali"],
            5,
        ),
        _theme(
            "base",
            "Overture Maps: Perusgeometria",
            "Maailmanlaajuinen perusgeometria-aineisto GeoParquet-muodossa."
            " Vesistöt, maasto, maankäyttöalueet ja infrastruktuuri.\n\n"
            + _DUCKDB_EXAMPLE.format(theme="base", type="land_use"),
            ["maasto", "vesistö", "maankäyttö", "Overture Maps", "GeoParquet", "globaali"],
            40,
        ),
    ]
