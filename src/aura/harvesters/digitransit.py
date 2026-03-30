"""Harvester Digitransit-joukkoliikennepalvelulle.

Digitransit on Fintrafficin kansallinen reitityspalvelu, joka kokoaa
GTFS-syötteet yli 30 joukkoliikenneoperaattorilta yhteen GraphQL-rajapintaan.

Tämä harvester kerää metatiedot kaikista GTFS-syötteistä ja
Digitransit-rajapinnoista (Routing, Geocoding, GTFS-RT).
"""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

# Digitransit Routing API -endpointit (GraphQL)
ROUTERS = {
    "finland": "Koko Suomi ja Viro",
    "hsl": "Helsingin seutu (HSL)",
    "waltti": "Waltti-kaupungit",
    "varely": "Varsinais-Suomen ELY",
}

# GTFS-syötteet Digitransitin Finland-reitittimestä
# Lähde: HSLdevcom/OpenTripPlanner-data-container finland/config.js
GTFS_FEEDS: list[dict[str, Any]] = [
    {
        "id": "HSL",
        "name": "HSL — pääkaupunkiseutu",
        "url": "https://infopalvelut.storage.hsldev.com/gtfs/hsl_google_transit.zip",
        "region": "Helsinki",
        "org": "Helsingin seudun liikenne (HSL)",
    },
    {
        "id": "MATKA",
        "name": "Matka.fi / Fintraffic — valtakunnallinen",
        "url": "https://mobility.mobility-database.fintraffic.fi/static/digitransit_new.zip",
        "region": "Suomi",
        "org": "Fintraffic",
    },
    {
        "id": "flixbus",
        "name": "FlixBus — kaukoliikenne",
        "url": "https://mobility.mobility-database.fintraffic.fi/static/flixbus_only.zip",
        "region": "Suomi",
        "org": "FlixBus",
    },
    {
        "id": "CAR_FERRIES",
        "name": "Autolauttareitit",
        "url": "https://mobility.mobility-database.fintraffic.fi/static/ferries_cars.zip",
        "region": "Suomi",
        "org": "Fintraffic",
    },
    {
        "id": "tampere",
        "name": "Nysse — Tampere",
        "url": "https://ekstrat.tampere.fi/ekstrat/ptdata/tamperefeed_deprecated.zip",
        "region": "Tampere",
        "org": "Tampereen joukkoliikenne Nysse",
    },
    {
        "id": "LINKKI",
        "name": "Linkki — Jyväskylä",
        "url": "https://tvv.fra1.digitaloceanspaces.com/209.zip",
        "region": "Jyväskylä",
        "org": "Jyväskylän Liikenne Oy",
    },
    {
        "id": "OULU",
        "name": "Oulu — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/229.zip",
        "region": "Oulu",
        "org": "Oulun kaupunki",
    },
    {
        "id": "digitraffic",
        "name": "VR — junaliikenne (Digitraffic GTFS)",
        "url": "https://rata.digitraffic.fi/api/v1/trains/gtfs-passenger-stops.zip",
        "region": "Suomi",
        "org": "VR-Yhtymä Oyj",
    },
    {
        "id": "Rauma",
        "name": "Rauma — kaupunkiliikenne",
        "url": "https://raumaadmin.mattersoft.fi/feeds/233.zip",
        "region": "Rauma",
        "org": "Rauman kaupunki",
    },
    {
        "id": "Hameenlinna",
        "name": "Hämeenlinna — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/203.zip",
        "region": "Hämeenlinna",
        "org": "Hämeenlinnan kaupunki",
    },
    {
        "id": "Kotka",
        "name": "Kotka — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/217.zip",
        "region": "Kotka",
        "org": "Kotkan kaupunki",
    },
    {
        "id": "Kouvola",
        "name": "Kouvola — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/219.zip",
        "region": "Kouvola",
        "org": "Kouvolan kaupunki",
    },
    {
        "id": "Lappeenranta",
        "name": "Lappeenranta — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/225.zip",
        "region": "Lappeenranta",
        "org": "Lappeenrannan kaupunki",
    },
    {
        "id": "Mikkeli",
        "name": "Mikkeli — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/227.zip",
        "region": "Mikkeli",
        "org": "Mikkelin kaupunki",
    },
    {
        "id": "Vaasa",
        "name": "Vaasa — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/249.zip",
        "region": "Vaasa",
        "org": "Vaasan kaupunki",
    },
    {
        "id": "Joensuu",
        "name": "Joensuu — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/207.zip",
        "region": "Joensuu",
        "org": "Joensuun kaupunki",
    },
    {
        "id": "FOLI",
        "name": "Föli — Turku",
        "url": "http://data.foli.fi/gtfs/gtfs.zip",
        "region": "Turku",
        "org": "Turun seudun joukkoliikenne Föli",
    },
    {
        "id": "Lahti",
        "name": "Lahti — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/223.zip",
        "region": "Lahti",
        "org": "Lahden kaupunki",
    },
    {
        "id": "Kuopio",
        "name": "Kuopio — kaupunkiliikenne",
        "url": "https://karttapalvelu.kuopio.fi/google_transit/google_transit.zip",
        "region": "Kuopio",
        "org": "Kuopion kaupunki",
    },
    {
        "id": "Rovaniemi",
        "name": "Rovaniemi — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/237.zip",
        "region": "Rovaniemi",
        "org": "Rovaniemen kaupunki",
    },
    {
        "id": "Kajaani",
        "name": "Kajaani — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/211.zip",
        "region": "Kajaani",
        "org": "Kajaanin kaupunki",
    },
    {
        "id": "Salo",
        "name": "Salo — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/239.zip",
        "region": "Salo",
        "org": "Salon kaupunki",
    },
    {
        "id": "Pori",
        "name": "Pori — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/231.zip",
        "region": "Pori",
        "org": "Porin kaupunki",
    },
    {
        "id": "Raasepori",
        "name": "Raasepori — kaupunkiliikenne",
        "url": "https://tvv.fra1.digitaloceanspaces.com/232.zip",
        "region": "Raasepori",
        "org": "Raaseporin kaupunki",
    },
    {
        "id": "VARELY",
        "name": "Varsinais-Suomen ELY — seutuliikenne",
        "url": "https://varelyadmin.mattersoft.fi/feeds/102.zip",
        "region": "Varsinais-Suomi",
        "org": "Varsinais-Suomen ELY-keskus",
    },
    {
        "id": "Harma",
        "name": "Härmän Liikenne — linja-autoliikenne",
        "url": "https://harmanliikenne.bussikaista.fi/sites/harma/files/gtfs/export/latest.zip",
        "region": "Suomi",
        "org": "Härmän Liikenne Oy",
    },
    {
        "id": "PohjolanMatka",
        "name": "Pohjolan Matka — linja-autoliikenne",
        "url": "https://minfoapi.matkahuolto.fi/gtfs/458/gtfs.zip",
        "region": "Suomi",
        "org": "Pohjolan Matka Oy",
    },
    {
        "id": "Korsisaari",
        "name": "Korsisaari — linja-autoliikenne",
        "url": "https://minfoapi.matkahuolto.fi/gtfs/036/gtfs.zip",
        "region": "Suomi",
        "org": "Oy Korsisaari Ab",
    },
    {
        "id": "KoivistonAuto",
        "name": "Koiviston Auto — linja-autoliikenne",
        "url": "https://minfoapi.matkahuolto.fi/gtfs/020/gtfs.zip",
        "region": "Suomi",
        "org": "Koiviston Auto Oy",
    },
    {
        "id": "PahkakankaanLiikenne",
        "name": "Pahkakankaan Liikenne — linja-autoliikenne",
        "url": "https://minfoapi.matkahuolto.fi/gtfs/198/gtfs.zip",
        "region": "Suomi",
        "org": "Pahkakankaan Liikenne Oy",
    },
    {
        "id": "IngvesSvanback",
        "name": "Ingves & Svanbäck — linja-autoliikenne",
        "url": "https://minfoapi.matkahuolto.fi/gtfs/177/gtfs.zip",
        "region": "Suomi",
        "org": "Ingves & Svanbäck Oy",
    },
    {
        "id": "02Taksi",
        "name": "02 Taksi — tilausliikenne",
        "url": "https://resources.02taksi.fi/digitransit_02_taksi.zip",
        "region": "Suomi",
        "org": "02 Taksi Finland Oy",
    },
]


def _build_datasets_config() -> list[dict[str, Any]]:
    """Rakenna datasets_config GTFS-syötteistä ja Digitransit-rajapinnoista."""
    configs: list[dict[str, Any]] = []

    # 1) Digitransit-rajapinnat (Routing, Geocoding, GTFS-RT)
    for router_id, router_desc in ROUTERS.items():
        configs.append({
            "id": f"digitransit-routing-{router_id}",
            "title": f"Digitransit Routing API — {router_desc}",
            "title_fi": f"Digitransit-reititysrajapinta — {router_desc}",
            "notes_fi": (
                f"Digitransit GraphQL-reititysrajapinta: {router_desc}. "
                "Tukee reittisuunnittelua, aikataulukyselyitä, pysäkkihakuja "
                "ja reaaliaikaista liikennetietoa."
            ),
            "organization_id": "fintraffic",
            "organization_name": "fintraffic",
            "organization_title": "Fintraffic",
            "keywords_fi": [
                "joukkoliikenne", "reititys", "graphql",
                "aikataulut", "pysäkit",
            ],
            "update_frequency": "reaaliaikainen",
            "resources": [
                {
                    "id": f"digitransit-routing-{router_id}-graphql",
                    "name": f"GraphQL API ({router_id})",
                    "name_fi": f"GraphQL-rajapinta ({router_desc})",
                    "format": "API",
                    "url": f"https://api.digitransit.fi/routing/v2/{router_id}/gtfs/v1",
                },
            ],
            "access_level": "registration",
        })

    # Geocoding API
    configs.append({
        "id": "digitransit-geocoding",
        "title": "Digitransit Geocoding API",
        "title_fi": "Digitransit-geokoodausrajapinta",
        "notes_fi": (
            "Osoitehaku ja käänteinen geokoodaus. "
            "Perustuu Pelias-geokooderiin. Tukee osoitteita, paikkoja ja pysäkkejä."
        ),
        "organization_id": "fintraffic",
        "organization_name": "fintraffic",
        "organization_title": "Fintraffic",
        "keywords_fi": ["geokoodaus", "osoitehaku", "pysäkit", "paikat"],
        "update_frequency": "päivittäin",
        "resources": [
            {
                "id": "digitransit-geocoding-api",
                "name": "Geocoding API",
                "name_fi": "Geokoodausrajapinta",
                "format": "API",
                "url": "https://api.digitransit.fi/geocoding/v1/search",
            },
        ],
        "access_level": "registration",
    })

    # GTFS-RT -rajapinnat
    for rt_type, rt_desc in [
        ("service-alerts", "Häiriötiedotteet ja perutut vuorot"),
        ("trip-updates", "Aikataulupoikkeamat ja ennusteet"),
        ("vehicle-positions", "Ajoneuvojen reaaliaikaiset sijainnit"),
    ]:
        configs.append({
            "id": f"digitransit-gtfsrt-{rt_type}",
            "title": f"Digitransit GTFS-RT — {rt_desc}",
            "title_fi": f"Digitransit GTFS-RT — {rt_desc}",
            "notes_fi": (
                f"GTFS Realtime -syöte: {rt_desc.lower()}. "
                "Saatavilla HSL-, Waltti- ja Finland-reitittimille."
            ),
            "organization_id": "fintraffic",
            "organization_name": "fintraffic",
            "organization_title": "Fintraffic",
            "keywords_fi": [
                "joukkoliikenne", "gtfs-rt", "reaaliaikainen",
            ],
            "update_frequency": "reaaliaikainen",
            "resources": [
                {
                    "id": f"digitransit-gtfsrt-{rt_type}-api",
                    "name": f"GTFS-RT {rt_type}",
                    "name_fi": rt_desc,
                    "format": "API",
                    "url": "https://api.digitransit.fi/realtime/service-alerts/v2/hsl",
                },
            ],
            "access_level": "registration",
        })

    # 2) GTFS-syötteet operaattoreilta
    for feed in GTFS_FEEDS:
        feed_id = feed["id"]
        configs.append({
            "id": f"digitransit-gtfs-{feed_id.lower()}",
            "title": f"GTFS: {feed['name']}",
            "title_fi": f"GTFS-aikataulu: {feed['name']}",
            "notes_fi": (
                f"GTFS-aikatauluaineisto: {feed['name']}. "
                "Sisältää reitit, pysäkit, aikataulut ja kalenteritiedot "
                "GTFS-formaatissa. Käytetään Digitransit-reitityspalvelussa."
            ),
            "organization_id": feed["org"].lower().replace(" ", "-"),
            "organization_name": feed["org"].lower().replace(" ", "-"),
            "organization_title": feed["org"],
            "keywords_fi": [
                "joukkoliikenne", "gtfs", "aikataulut",
                "reitit", "pysäkit",
            ],
            "geographical_coverage": [feed["region"]],
            "update_frequency": "viikoittain",
            "resources": [
                {
                    "id": f"digitransit-gtfs-{feed_id.lower()}-zip",
                    "name": f"GTFS {feed['name']}",
                    "name_fi": f"GTFS-tiedosto — {feed['name']}",
                    "format": "GTFS",
                    "url": feed["url"],
                },
            ],
        })

    return configs


class DigitransitHarvester(StaticHarvester):
    """Kerää Digitransit-joukkoliikennepalvelun metatiedot.

    Digitransit on Fintrafficin kansallinen reitityspalvelu, joka kokoaa
    GTFS-syötteet yli 30 joukkoliikenneoperaattorilta:
    - HSL (pääkaupunkiseutu)
    - Waltti-kaupungit (Tampere, Oulu, Turku, Jyväskylä, Kuopio, ym.)
    - VR (junaliikenne)
    - Yksityiset operaattorit (FlixBus, Matkahuolto-liikennöitsijät)
    - GTFS-RT reaaliaikasyötteet
    """

    name = "digitransit"
    description = "Digitransit — kansallinen joukkoliikenteen reitityspalvelu"
    url = "https://digitransit.fi"

    org_id = "fintraffic"
    org_name = "fintraffic"
    org_title = "Fintraffic"
    default_update_frequency = "viikoittain"

    datasets_config = _build_datasets_config()

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "static",
            "query_protocol": "graphql",
            "api_base_url": "https://api.digitransit.fi",
        })
        return config
