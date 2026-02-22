"""Harvester Väyläviraston avoimille paikkatietoaineistoille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

VAYLA_BASE = "https://avoinapi.vaylapilvi.fi/vaylatiedot"


class VaylaHarvester(StaticHarvester):
    """Kerää Väyläviraston avoimet liikenneinfra-aineistot.

    Väylävirasto tarjoaa tie-, rata- ja vesiväylätietoja
    WMS/WFS/OGC API Features -rajapintojen kautta.
    307 WMS-tasoa / 301 WFS-featuretyyppiä.
    """

    name = "vayla"
    description = "Väylävirasto — tie-, rata- ja vesiväyläaineistot"
    url = "https://vayla.fi/vaylista/aineistot/avoindata"
    org_id = "vayla"
    org_name = "vaylavirasto"
    org_title = "Väylävirasto"
    default_update_frequency = "kuukausittain"

    datasets_config = [
        {
            "id": "vayla-tiestotiedot",
            "title": "Tiestötiedot",
            "notes_fi": (
                "Tieverkko, teiden kunto, nopeusrajoitukset,"
                " liikennemäärät, kaiteet ja sillat."
                " 168 WFS-featuretyyppiä."
            ),
            "keywords_fi": [
                "tieverkko", "kunto", "nopeusrajoitus",
                "liikennemäärä", "silta", "tiestö",
            ],
            "estimated_size_bytes": 5 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{VAYLA_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{VAYLA_BASE}/ows?service=WMS"},
                {
                    "format": "API",
                    "url": f"{VAYLA_BASE}/ogc/features/v1/",
                    "name_fi": "Tiestötiedot — OGC API Features",
                },
            ],
        },
        {
            "id": "vayla-digiroad",
            "title": "Digiroad — kansallinen tietietokanta",
            "notes_fi": (
                "Digiroad-tieverkkoaineisto: tielinkit, liittymät,"
                " liikennemerkit, joukkoliikennepysäkit ja rajoitukset."
                " 46 WFS-featuretyyppiä."
            ),
            "keywords_fi": [
                "digiroad", "tieverkko", "liikennemerkki",
                "pysäkki", "joukkoliikenne",
            ],
            "estimated_size_bytes": 3 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{VAYLA_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{VAYLA_BASE}/ows?service=WMS"},
            ],
        },
        {
            "id": "vayla-ratatiedot",
            "title": "Ratatiedot",
            "notes_fi": (
                "Rataverkko, rautatieasemat, tasoristeykset"
                " ja ratainfran kuntotiedot."
                " 30 WFS-featuretyyppiä."
            ),
            "keywords_fi": [
                "rataverkko", "rautatie", "asema",
                "tasoristeys", "raideliikenne",
            ],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {"format": "WFS", "url": f"{VAYLA_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{VAYLA_BASE}/ows?service=WMS"},
            ],
        },
        {
            "id": "vayla-vesivaylat",
            "title": "Vesiväylätiedot",
            "notes_fi": (
                "Vesiväylät, satamat, turvalait-teet,"
                " kanavat, sulut ja merenkulun turvalaitteet."
                " 25 WFS-featuretyyppiä."
            ),
            "keywords_fi": [
                "vesiväylä", "satama", "kanava",
                "merenkulku", "turvalaite",
            ],
            "estimated_size_bytes": 200 * 1024**2,
            "resources": [
                {"format": "WFS", "url": f"{VAYLA_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{VAYLA_BASE}/ows?service=WMS"},
            ],
        },
        {
            "id": "vayla-taitorakenteet",
            "title": "Taitorakenteet",
            "notes_fi": (
                "Sillat, tunnelit, sulut ja rummut."
                " Rakennustiedot ja kuntoluokitus."
            ),
            "keywords_fi": [
                "silta", "tunneli", "sulku", "taitorakenne",
            ],
            "estimated_size_bytes": 100 * 1024**2,
            "resources": [
                {"format": "WFS", "url": f"{VAYLA_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{VAYLA_BASE}/ows?service=WMS"},
            ],
        },
    ]
