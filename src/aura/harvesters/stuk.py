"""Harvester STUK:n (Säteilyturvakeskus) avoimille aineistoille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

FMI_GEOSERVER = "https://openwms.fmi.fi/geoserver"


class StukHarvester(StaticHarvester):
    """Kerää STUK:n säteilyvalvonta-aineistot.

    STUK:n ulkoisen säteilyn mittaustulokset ovat saatavilla
    FMI:n GeoServer-infrastruktuurin kautta WMS-palveluna
    sekä STUK:n omasta Sammio-palvelusta.
    """

    name = "stuk"
    description = "Säteilyturvakeskus — säteilyvalvonnan mittaustulokset"
    url = "https://stuk.fi/avoin-data"
    org_id = "stuk"
    org_name = "stuk"
    org_title = "Säteilyturvakeskus (STUK)"
    default_update_frequency = "reaaliaikainen"

    datasets_config = [
        {
            "id": "stuk-ulkoinen-sateilytaso",
            "title": "Ulkoisen säteilyn valvontaverkko",
            "notes_fi": (
                "Ulkoisen säteilyn reaaliaikaiset mittaustulokset"
                " noin 260 mittausasemalta ympäri Suomea."
                " Mittausarvot päivittyvät 10 minuutin välein."
            ),
            "keywords_fi": [
                "säteily", "säteilyvalvonta", "annosnopeus",
                "mittausasema", "ympäristösäteily",
            ],
            "estimated_size_bytes": 100 * 1024**2,
            "resources": [
                {
                    "format": "API",
                    "url": "https://sammio.stuk.fi",
                    "name_fi": "STUK Sammio — säteilymittausdata",
                },
            ],
        },
        {
            "id": "stuk-ymparistovalvonta",
            "title": "Ympäristön säteilyvalvonnan tulokset",
            "notes_fi": (
                "Ympäristönäytteiden radioaktiivisuusmittaukset:"
                " ilma, laskeuma, elintarvikkeet ja luonnontuotteet."
            ),
            "keywords_fi": [
                "radioaktiivisuus", "ympäristövalvonta",
                "laskeuma", "elintarvike", "säteily",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "API",
                    "url": "https://sammio.stuk.fi",
                    "name_fi": "Ympäristövalvonta — Sammio-rajapinta",
                },
            ],
        },
    ]
