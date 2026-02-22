"""Harvester LIPAS-liikuntapaikkarekisterille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

LIPAS_BASE = "http://lipas.cc.jyu.fi/geoserver/lipas"


class LipasHarvester(StaticHarvester):
    """Kerää LIPAS-liikuntapaikkarekisterin aineistot.

    LIPAS (Jyväskylän yliopisto) sisältää Suomen julkiset liikuntapaikat
    ja virkistysalueet. 210 WMS/WFS-tasoa GeoServer-rajapinnan kautta.
    """

    name = "lipas"
    description = "LIPAS — Suomen liikuntapaikat ja virkistysalueet"
    url = "https://www.jyu.fi/sport/fi/yhteistyo/lipas"
    org_id = "lipas"
    org_name = "jyu-lipas"
    org_title = "Jyväskylän yliopisto / LIPAS"
    default_update_frequency = "vuosittain"

    datasets_config = [
        {
            "id": "lipas-liikuntapaikat",
            "title": "Liikuntapaikat (kaikki)",
            "notes_fi": (
                "Suomen kaikki julkiset liikuntapaikat pistemäisinä kohteina:"
                " uimahallit, jäähallit, stadionit, kentät, kuntosalit jne."
            ),
            "keywords_fi": [
                "liikuntapaikka", "urheilupaikka", "uimahalli",
                "jäähalli", "kenttä",
            ],
            "estimated_size_bytes": 200 * 1024**2,
            "resources": [
                {"format": "WFS", "url": f"{LIPAS_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{LIPAS_BASE}/wms?service=WMS"},
            ],
        },
        {
            "id": "lipas-ulkoilureitit",
            "title": "Ulkoilureitit",
            "notes_fi": (
                "Ulkoilureitit, hiihtoladut, kävely- ja pyöräilyreitit,"
                " luontopolut, melontareitit ja moottorikelkkareitit."
            ),
            "keywords_fi": [
                "ulkoilureitti", "hiihto", "latu", "luontopolku",
                "pyöräilyreitti", "melonta",
            ],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {"format": "WFS", "url": f"{LIPAS_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{LIPAS_BASE}/wms?service=WMS"},
            ],
        },
        {
            "id": "lipas-virkistysalueet",
            "title": "Virkistysalueet",
            "notes_fi": (
                "Virkistys- ja ulkoilualueet, kansallispuistot,"
                " uimarannat ja retkeilyalueet."
            ),
            "keywords_fi": [
                "virkistysalue", "ulkoilualue", "kansallispuisto",
                "uimaranta", "retkeilyalue",
            ],
            "estimated_size_bytes": 300 * 1024**2,
            "resources": [
                {"format": "WFS", "url": f"{LIPAS_BASE}/ows?service=WFS"},
                {"format": "WMS", "url": f"{LIPAS_BASE}/wms?service=WMS"},
            ],
        },
    ]
