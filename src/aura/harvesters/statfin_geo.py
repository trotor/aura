"""Harvester Tilastokeskuksen paikkatietoaineistoille (GeoServer WMS/WFS)."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

GEOSERVER_BASE = "https://geo.stat.fi/geoserver"


class StatfinGeoHarvester(StaticHarvester):
    """Kerää Tilastokeskuksen avoimet paikkatietoaineistot.

    Tilastokeskus tarjoaa väestö-, alue- ja tilastoruutuaineistoja
    GeoServer-rajapinnan (WFS/WMS) kautta osoitteessa geo.stat.fi.
    """

    name = "statfin-geo"
    description = "Tilastokeskus — paikkatietoaineistot (WMS/WFS)"
    url = "https://www.stat.fi/org/avoindata/paikkatietoaineistot.html"
    org_id = "tilastokeskus"
    org_name = "tilastokeskus"
    org_title = "Tilastokeskus"
    default_update_frequency = "vuosittain"

    datasets_config = [
        {
            "id": "statfin-geo-tilastointialueet",
            "title": "Kuntapohjaiset tilastointialueet",
            "notes_fi": (
                "Suomen kuntapohjaiset tilastolliset aluejaot: seutukunnat,"
                " maakunnat, suuralue, ELY-keskukset ja AVI-alueet."
                " Aluejaot muuttuvat kuntaliitoksissa."
            ),
            "keywords_fi": [
                "tilastointialue",
                "aluejako",
                "seutukunta",
                "maakunta",
                "hallinnollinen raja",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-vaestoalue",
            "title": "Väestö tilastointialueittain",
            "notes_fi": (
                "Väestötiedot tilastollisilla aluejaotuksilla:"
                " ikärakenne, sukupuoli ja kieli alueittain."
            ),
            "keywords_fi": [
                "väestö",
                "tilastointialue",
                "ikärakenne",
                "sukupuolijakauma",
            ],
            "estimated_size_bytes": 100 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/vaestoalue/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/vaestoalue/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-paavo",
            "title": "Paavo — postinumeroalueittainen avoin tieto",
            "notes_fi": (
                "Paavo-aineisto sisältää postinumeroalueittain väestörakenteen,"
                " koulutusasteen, tulotason, asumisen ja työllisyyden tietoja."
            ),
            "keywords_fi": [
                "paavo",
                "postinumero",
                "postinumeroalue",
                "väestörakenne",
                "tulotaso",
            ],
            "estimated_size_bytes": 200 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/postialue/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/postialue/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-vaestoruutu-1km",
            "title": "Väestöruutuaineisto 1 km x 1 km",
            "notes_fi": (
                "Väestötiedot 1 km x 1 km tilastoruuduissa."
                " Asukasmäärä, ikärakenne ja asuntokunnat ruuduittain."
            ),
            "keywords_fi": [
                "väestöruutu",
                "ruutudata",
                "1km",
                "väestötiheys",
                "asuntokunnat",
            ],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-vaestoruutu-5km",
            "title": "Väestöruutuaineisto 5 km x 5 km",
            "notes_fi": (
                "Väestötiedot 5 km x 5 km tilastoruuduissa."
                " Karkea ruutukoko koko Suomen kattaviin analyyseihin."
            ),
            "keywords_fi": [
                "väestöruutu",
                "ruutudata",
                "5km",
                "väestötiheys",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-tilastoruudukko-1km",
            "title": "Tilastoruudukko 1 km x 1 km",
            "notes_fi": (
                "Tilastoruudukko 1 km x 1 km: työpaikat, rakennukset"
                " ja yritystoimipaikat ruuduittain."
            ),
            "keywords_fi": [
                "tilastoruudukko",
                "ruutudata",
                "1km",
                "työpaikat",
                "rakennukset",
            ],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-tilastoruudukko-5km",
            "title": "Tilastoruudukko 5 km x 5 km",
            "notes_fi": (
                "Tilastoruudukko 5 km x 5 km: työpaikat, rakennukset"
                " ja yritystoimipaikat karkeammalla ruutujaolla."
            ),
            "keywords_fi": [
                "tilastoruudukko",
                "ruutudata",
                "5km",
                "työpaikat",
                "rakennukset",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-tieliikenne",
            "title": "Tieliikenneonnettomuudet",
            "notes_fi": (
                "Poliisin tietoon tulleet tieliikenneonnettomuudet"
                " sijaintitietoineen. Sisältää onnettomuustyypin,"
                " osalliset ja vakavuuden."
            ),
            "keywords_fi": [
                "tieliikenne",
                "onnettomuus",
                "liikenneonnettomuus",
                "liikenneturvallisuus",
            ],
            "estimated_size_bytes": 100 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tieliikenne/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tieliikenne/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-oppilaitokset",
            "title": "Oppilaitokset",
            "notes_fi": (
                "Suomen oppilaitosten sijaintitiedot."
                " Kattaa peruskoulut, lukiot, ammatilliset oppilaitokset"
                " ja korkeakoulut."
            ),
            "keywords_fi": [
                "oppilaitokset",
                "koulut",
                "koulutus",
                "sijaintitieto",
            ],
            "estimated_size_bytes": 10 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/oppilaitokset/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/oppilaitokset/wms",
                },
            ],
        },
    ]
