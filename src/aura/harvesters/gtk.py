"""Harvester Geologian tutkimuskeskuksen (GTK) paikkatietorajapinnoille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

ARCGIS_BASE = "https://gtkdata.gtk.fi/arcgis/services/Rajapinnat"


class GtkHarvester(StaticHarvester):
    """Kerää GTK:n avoimet geologiset paikkatietoaineistot.

    Geologian tutkimuskeskus (GTK) tarjoaa Suomen kallioperä-, maaperä-
    ja kiviainestietoja ArcGIS-rajapintojen kautta.
    """

    name = "gtk"
    description = "Geologian tutkimuskeskus — kallioperä-, maaperä- ja kiviainestiedot"
    url = "https://www.gtk.fi/palvelut/aineistot-ja-myynti/avoimet-aineistot/"
    org_id = "gtk"
    org_name = "gtk"
    org_title = "Geologian tutkimuskeskus"

    datasets_config = [
        # --- WFS + WMS -palvelut ---
        {
            "id": "gtk-kalliopera",
            "title": "Kallioperäkartta",
            "notes_fi": (
                "Suomen kallioperän geologinen kartta-aineisto."
                " Kivilajitiedot, rakennegeologia ja malmihavainnot."
            ),
            "keywords_fi": ["geologia", "kallioperä", "kivilaji", "GTK"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{ARCGIS_BASE}/GTK_Kalliopera_WFS/MapServer/WFSServer"},
                {"format": "WMS", "url": f"{ARCGIS_BASE}/GTK_Kalliopera_WFS/MapServer/WMSServer"},
            ],
        },
        {
            "id": "gtk-maapera",
            "title": "Maaperäkartta",
            "notes_fi": (
                "Suomen maaperäkartta-aineisto."
                " Maalajitiedot, kerrostumien paksuus ja pohjavesialueet."
            ),
            "keywords_fi": ["geologia", "maaperä", "maalaji", "GTK"],
            "estimated_size_bytes": 3 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{ARCGIS_BASE}/GTK_Maapera_WFS/MapServer/WFSServer"},
                {"format": "WMS", "url": f"{ARCGIS_BASE}/GTK_Maapera_WFS/MapServer/WMSServer"},
            ],
        },
        {
            "id": "gtk-kiviainesvarannot",
            "title": "Kiviainesvarannot",
            "notes_fi": "Kiviainesten (sora, hiekka, kalliokiviaines) varannot ja ottopaikat.",
            "keywords_fi": ["geologia", "kiviaines", "sora", "hiekka", "GTK"],
            "estimated_size_bytes": int(0.5 * 1024**3),
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{ARCGIS_BASE}/GTK_Kiviainesvarannot_WFS/MapServer/WFSServer",
                },
                {
                    "format": "WMS",
                    "url": f"{ARCGIS_BASE}/GTK_Kiviainesvarannot_WFS/MapServer/WMSServer",
                },
            ],
        },
        # --- WMS-only -palvelut ---
        {
            "id": "gtk-geofysiikka",
            "title": "Geofysikaaliset kartat",
            "notes_fi": (
                "Geofysikaaliset mittausaineistot: magneettiset, gravimetriset"
                " ja sähköiset kartat."
            ),
            "keywords_fi": ["geofysiikka", "magneettikenttä", "gravimetria", "GTK"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{ARCGIS_BASE}/geofysiikka"},
            ],
        },
        {
            "id": "gtk-pohjatutkimukset",
            "title": "Pohjatutkimukset",
            "notes_fi": (
                "Pohjatutkimusaineistot: kairaukset, näytteenotot"
                " ja laboratoriotulokset."
            ),
            "keywords_fi": ["pohjatutkimus", "kairaus", "geotekniikka", "GTK"],
            "estimated_size_bytes": int(0.5 * 1024**3),
            "resources": [
                {"format": "WMS", "url": f"{ARCGIS_BASE}/pohjatutkimukset"},
            ],
        },
    ]
