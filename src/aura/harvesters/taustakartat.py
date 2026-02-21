"""Harvester taustakarttapalveluille (MML/Kapsi + OpenStreetMap)."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester


class TaustakartatHarvester(StaticHarvester):
    """Kerää taustakarttatiilipalvelut (MML/Kapsi + OpenStreetMap).

    Staattinen konfiguraatioharvester. Rekisteröi TMS-tiilipalvelut
    joita voi käyttää karttasovellusten pohjakarttoina.
    """

    name = "taustakartat"
    description = "Taustakartat — MML (Kapsi) ja OpenStreetMap -tiilipalvelut"
    url = "https://kartat.kapsi.fi"
    default_update_frequency = "kuukausittain"

    datasets_config = [
        {
            "id": "taustakartat-kapsi-peruskartta",
            "title": "MML Peruskartta",
            "notes_fi": (
                "Maanmittauslaitoksen peruskartta TMS-tiilipalveluna."
                " Mittakaavat z0–z18. Ylläpito: kartat.kapsi.fi (MML:n aineisto)."
            ),
            "keywords_fi": ["kartta", "peruskartta", "MML", "taustakartta"],
            "organization_id": "mml",
            "organization_name": "mml",
            "organization_title": "Maanmittauslaitos",
            "estimated_size_bytes": 5_000_000_000,
            "resources": [
                {"format": "TMS", "url": "https://tiles.kartat.kapsi.fi/peruskartta/{z}/{x}/{y}.jpg"},
            ],
        },
        {
            "id": "taustakartat-kapsi-taustakartta",
            "title": "MML Taustakartta",
            "notes_fi": (
                "Maanmittauslaitoksen taustakartta TMS-tiilipalveluna."
                " Yksinkertaistettu, vaalea pohjakartta. Mittakaavat z0–z18."
            ),
            "keywords_fi": ["kartta", "taustakartta", "MML", "pohjakartta"],
            "organization_id": "mml",
            "organization_name": "mml",
            "organization_title": "Maanmittauslaitos",
            "estimated_size_bytes": 5_000_000_000,
            "resources": [
                {"format": "TMS", "url": "https://tiles.kartat.kapsi.fi/taustakartta/{z}/{x}/{y}.jpg"},
            ],
        },
        {
            "id": "taustakartat-kapsi-ortokuva",
            "title": "MML Ortokuva",
            "notes_fi": (
                "Maanmittauslaitoksen ortokuva (ilmakuva) TMS-tiilipalveluna."
                " Koko Suomen kattava ilmakuvamosaiikki."
            ),
            "keywords_fi": ["kartta", "ortokuva", "ilmakuva", "MML"],
            "organization_id": "mml",
            "organization_name": "mml",
            "organization_title": "Maanmittauslaitos",
            "estimated_size_bytes": 5_000_000_000,
            "resources": [
                {"format": "TMS", "url": "https://tiles.kartat.kapsi.fi/ortokuva/{z}/{x}/{y}.jpg"},
            ],
        },
        {
            "id": "taustakartat-osm-standard",
            "title": "OpenStreetMap",
            "notes_fi": (
                "OpenStreetMap-standardikartta TMS-tiilipalveluna."
                " Yhteisöllisesti tuotettu maailmankartta. Mittakaavat z0–z19."
            ),
            "keywords_fi": ["kartta", "OpenStreetMap", "OSM", "taustakartta"],
            "organization_id": "osm",
            "organization_name": "osm",
            "organization_title": "OpenStreetMap Foundation",
            "license_id": "ODbL-1.0",
            "license_title": "ODbL",
            "geographical_coverage": ["Maailma"],
            "estimated_size_bytes": 5_000_000_000,
            "resources": [
                {"format": "TMS", "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png"},
            ],
        },
    ]
