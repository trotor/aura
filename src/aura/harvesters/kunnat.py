"""Harvester suurimpien kaupunkien paikkatietopalveluille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester


class KunnatHarvester(StaticHarvester):
    """Kerää suurimpien kaupunkien WMS/WFS-paikkatietoaineistot.

    Helsinki, Espoo, Vantaa, Tampere, Turku ja Oulu tarjoavat
    kartta- ja paikkatietoaineistoja omien rajapintojensa kautta.
    """

    name = "kunnat"
    description = "Kaupunkien paikkatiedot — Helsinki, Espoo, Vantaa, Tampere, Turku, Oulu"
    url = "https://www.gispo.fi/blogi/avoimen-datan-wms-ja-wfs-karttapalveluita/"
    org_id = "kunnat"
    org_name = "kunnat"
    org_title = "Kuntien paikkatietopalvelut"
    default_update_frequency = "vuosittain"

    datasets_config = [
        # --- Helsinki ---
        {
            "id": "kunnat-helsinki-avoindata",
            "title": "Helsinki — avoimet paikkatiedot",
            "notes_fi": (
                "Helsingin kaupungin avoimet kartta-aineistot."
                " 461 WMS-tasoa: opaskartat, kantakartta, ortokuvat,"
                " meluselvitykset, luontotiedot, kaavahakemisto ja tilastot."
            ),
            "keywords_fi": [
                "Helsinki", "kaupunki", "kartta", "opaskartta",
                "kaava", "luonto", "meluselvitys",
            ],
            "organization_title": "Helsingin kaupunki",
            "estimated_size_bytes": 10 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
                },
                {
                    "format": "WMS",
                    "url": "https://kartta.hel.fi/ws/geoserver/avoindata/wms",
                },
            ],
        },
        # --- Espoo ---
        {
            "id": "kunnat-espoo-avoindata",
            "title": "Espoo — avoimet paikkatiedot",
            "notes_fi": (
                "Espoon kaupungin kartta-aineistot."
                " 130 WMS-tasoa: opaskartta, ortokuvat (1950–2024),"
                " kaavat, geologia, meluselvitykset ja ekologinen verkosto."
            ),
            "keywords_fi": [
                "Espoo", "kaupunki", "kartta", "kaava",
                "geologia", "ortokuva",
            ],
            "organization_title": "Espoon kaupunki",
            "estimated_size_bytes": 5 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartat.espoo.fi/teklaogcweb/wfs.ashx",
                },
                {
                    "format": "WMS",
                    "url": "https://kartat.espoo.fi/teklaogcweb/wms.ashx",
                },
            ],
        },
        # --- Vantaa ---
        {
            "id": "kunnat-vantaa-avoindata",
            "title": "Vantaa — avoimet paikkatiedot",
            "notes_fi": (
                "Vantaan kaupungin kartta-aineistot."
                " 112 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat, kiinteistöt ja palvelupisteet."
            ),
            "keywords_fi": [
                "Vantaa", "kaupunki", "kartta",
                "kaava", "kiinteisto",
            ],
            "organization_title": "Vantaan kaupunki",
            "estimated_size_bytes": 3 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://gis.vantaa.fi/geoserver/wfs",
                },
                {
                    "format": "WMS",
                    "url": "https://gis.vantaa.fi/geoserver/wms",
                },
            ],
        },
        # --- Tampere ---
        {
            "id": "kunnat-tampere-avoindata",
            "title": "Tampere — avoimet paikkatiedot",
            "notes_fi": (
                "Tampereen kaupungin kartta-aineistot."
                " 173 WMS-tasoa: maanpeite, ilmanlaatu (NO2, PM10, PM2.5),"
                " melualueet, maankäyttö, joukkoliikenne ja luontotiedot."
            ),
            "keywords_fi": [
                "Tampere", "kaupunki", "kartta", "ilmanlaatu",
                "joukkoliikenne", "maankaytto",
            ],
            "organization_title": "Tampereen kaupunki",
            "estimated_size_bytes": 5 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://geodata.tampere.fi/geoserver/ows?service=WFS",
                },
                {
                    "format": "WMS",
                    "url": "https://geodata.tampere.fi/geoserver/wms",
                },
            ],
        },
        # --- Turku ---
        {
            "id": "kunnat-turku-avoindata",
            "title": "Turku — avoimet paikkatiedot",
            "notes_fi": (
                "Turun kaupungin kartta-aineistot."
                " 68 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat ja pohjakartta."
            ),
            "keywords_fi": [
                "Turku", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Turun kaupunki",
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://opaskartta.turku.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Oulu ---
        {
            "id": "kunnat-oulu-avoindata",
            "title": "Oulu — avoimet paikkatiedot",
            "notes_fi": (
                "Oulun kaupungin kartta-aineistot."
                " 28 WMS-tasoa: opaskartta, kantakartta ja pohjakartta."
            ),
            "keywords_fi": [
                "Oulu", "kaupunki", "kartta",
            ],
            "organization_title": "Oulun kaupunki",
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://e-kartta.ouka.fi/TeklaOgcWebOpen/WMS.ashx",
                },
            ],
        },
    ]
