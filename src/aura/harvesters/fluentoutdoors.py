"""Harvester Fluent Outdoors -latupalvelulle.

Fluent Outdoors (FluentProgress Oy) on SaaS-palvelu, jota 24+ suomalaista
kuntaa käyttää latujen ja ulkoliikuntapaikkojen kunnossapitotietojen
julkaisemiseen. Palvelu tarjoaa avoimen JSON API:n latukoneiden
reaaliaikaiseen seurantaan — niissä kunnissa jotka ovat julkaisseet
rajapinnan osoitteen, ks. :data:`VERIFIED_API_PATHS`.

API-dokumentaatio: https://oulu.fluentprogress.fi/LatuOulu/v1/snowplow/api-doc
Lisenssi: Avoin rajapinta (ei virallista lisenssiä dokumentoitu)
"""

from __future__ import annotations

import logging
from typing import Any

from aura.harvesters.static import StaticHarvester

logger = logging.getLogger(__name__)

# Fluent Outdoors -kunnat ja niiden API-polut
# Format: (subdomain, map_path, municipality_name_fi)
# map_path on karttanäkymän polku; rajapinnan polku on eri asia
# eikä sitä voi johtaa tästä — ks. VERIFIED_API_PATHS.
FLUENT_MUNICIPALITIES: list[tuple[str, str, str]] = [
    # Suuret kaupungit
    ("oulu", "LatuOulu", "Oulu"),
    ("jyvaskyla", "outdoors", "Jyväskylä"),
    ("kuopio", "outdoors", "Kuopio"),
    ("joensuu", "outdoors", "Joensuu"),
    ("rovaniemi", "outdoors", "Rovaniemi"),
    ("mikkeli", "outdoors", "Mikkeli"),
    ("kajaani", "outdoors", "Kajaani"),
    ("kouvola", "outdoors", "Kouvola"),
    # Keskikokoiset kaupungit
    ("hyvinkaa", "outdoors", "Hyvinkää"),
    ("porvoo", "outdoors", "Porvoo"),
    ("raasepori", "outdoors", "Raasepori"),
    ("iisalmi", "outdoors", "Iisalmi"),
    ("ylivieska", "outdoors", "Ylivieska"),
    ("kemi", "outdoors", "Kemi"),
    ("tornio", "outdoors", "Tornio"),
    ("kuusamo", "outdoors", "Kuusamo"),
    # Pienemmät kunnat
    ("suomussalmi", "outdoors", "Suomussalmi"),
    ("nurmes", "outdoors", "Nurmes"),
    ("nivala", "outdoors", "Nivala"),
    ("haapavesi", "outdoors", "Haapavesi"),
    ("taivalkoski", "outdoors", "Taivalkoski"),
    ("liminka", "outdoors", "Liminka"),
    ("paltamo", "outdoors", "Paltamo"),
    ("vaala", "outdoors", "Vaala"),
]


#: Kunnat joilla ``/v1/snowplow``-rajapinta on **todennettu vastaavaksi**.
#:
#: ``outdoors``-polku oli listalla 22 kunnalle, mutta se vastaa kaikilla
#: HTTP 404:llä (``"These are not the droids you are looking for"``).
#: Kunnan karttasivu latautuu, joten palvelu on olemassa — vain avoimen
#: rajapinnan polkua ei ole julkaistu. Mitattu 16.8.2026.
#:
#: Rikkinäinen rajapintalinkki on katalogissa pahempi kuin puuttuva: se
#: lupaa koneluettavan lähteen, ja lupaus pettää vasta käyttäjän kädessä.
#: Siksi JSON-resurssit syntyvät vain tästä sanakirjasta.
VERIFIED_API_PATHS: dict[str, str] = {
    "oulu": "LatuOulu",
}


def _build_datasets_config() -> list[dict[str, Any]]:
    """Generoi datasets_config kaikille Fluent Outdoors -kunnille."""
    datasets: list[dict[str, Any]] = []

    for subdomain, map_path, name_fi in FLUENT_MUNICIPALITIES:
        map_url = f"https://{subdomain}.fluentprogress.fi/{map_path}"
        api_path = VERIFIED_API_PATHS.get(subdomain)

        resources: list[dict[str, Any]] = []
        if api_path:
            api_url = f"https://{subdomain}.fluentprogress.fi/{api_path}/v1/snowplow"
            resources += [
                {
                    "format": "JSON",
                    "url": api_url,
                    "name": f"Latukoneet — {name_fi} (JSON API)",
                    "description": (
                        "Latukoneiden reaaliaikainen sijainti ja toimenpiteet. "
                        "Palauttaa taulukon: id, name, last_location "
                        "(timestamp, coords, events)."
                    ),
                },
                {
                    "format": "JSON",
                    "url": f"{api_url}/mt",
                    "name": f"Konetyypit — {name_fi}",
                    "description": (
                        "Kunnossapitokoneiden tyypit: latukone, moottorikelkka, traktori jne."
                    ),
                },
                {
                    "format": "JSON",
                    "url": f"{api_url}/op",
                    "name": f"Kunnossapitotoimenpiteet — {name_fi}",
                    "description": (
                        "Toimenpiteet: ladun hoito, jäädytys, auraus, kenttien kunnostus jne."
                    ),
                },
            ]
        resources.append(
            {
                "format": "HTML",
                "url": map_url,
                "name": f"Fluent Outdoors -kartta — {name_fi}",
                "description": "Karttanäkymä latujen kunnossapidosta.",
            }
        )

        rajapinta = (
            "Data on saatavilla JSON-rajapinnasta."
            if api_path
            else (
                "Kunnalle ei ole julkaistu avoimen rajapinnan osoitetta,"
                " joten tiedot ovat vain karttanäkymässä."
            )
        )
        datasets.append(
            {
                "id": f"fluentoutdoors-{subdomain}",
                "title": f"Latujen kunnossapito — {name_fi}",
                "license_id": "other-open",
                "license_title": "Avoin rajapinta",
                "notes_fi": (
                    f"{name_fi}n latujen ja ulkoliikuntapaikkojen kunnossapitotiedot "
                    f"reaaliajassa. Fluent Outdoors -palvelu näyttää latukoneiden "
                    f"sijainnin, kunnossapitotoimenpiteet (ladun hoito, jäädytys, "
                    f"auraus) ja aikaleiman. {rajapinta}"
                ),
                "keywords_fi": [
                    "latu",
                    "hiihtolatu",
                    "latujen kunnossapito",
                    "latukone",
                    "ulkoliikunta",
                    "hiihto",
                    "latutieto",
                    name_fi.lower(),
                ],
                "geographical_coverage": [name_fi],
                "update_frequency": "reaaliaikainen",
                "resources": resources,
            }
        )

    return datasets


class FluentOutdoorsHarvester(StaticHarvester):
    """Kerää Fluent Outdoors -latupalvelun kunnossapitotiedot.

    24 suomalaista kuntaa käyttää FluentProgress Oy:n Fluent Outdoors
    -palvelua latukoneiden reaaliaikaisen sijainnin ja kunnossapito-
    toimenpiteiden julkaisemiseen avoimena datana.

    API tarjoaa JSON-muotoista dataa latukoneiden sijainnista,
    konetyypeistä ja toimenpiteistä (ladun hoito, jäädytys, auraus) —
    mutta vain niille kunnille jotka ovat julkaisseet rajapinnan
    osoitteen, ks. :data:`VERIFIED_API_PATHS`. Muilla on karttanäkymä.
    """

    name = "fluentoutdoors"
    description = "Fluent Outdoors — latujen kunnossapitotiedot 24 kunnasta"
    url = "https://oulu.fluentprogress.fi/LatuOulu/"
    org_id = "fluentprogress"
    org_name = "fluentprogress"
    org_title = "FluentProgress Oy / Fluent Outdoors"
    default_update_frequency = "reaaliaikainen"

    datasets_config = _build_datasets_config()
