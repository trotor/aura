"""Harvester Maanmittauslaitoksen (MML) paikkatietorajapinnoille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

MML_BASE = "https://avoin-paikkatieto.maanmittauslaitos.fi"
MML_KARTTAKUVA = "https://avoin-karttakuva.maanmittauslaitos.fi"


class MmlHarvester(StaticHarvester):
    """Kerää Maanmittauslaitoksen avoimet paikkatietoaineistot.

    MML tarjoaa INSPIRE-karttapalvelut (WMS), kyselupalvelut (WFS/OGC API)
    ja WMTS-tiilipalvelut. Vaatii ilmaisen API-avaimen.
    """

    name = "mml"
    description = "Maanmittauslaitos — maasto-, kiinteistö- ja kartta-aineistot"
    url = "https://www.maanmittauslaitos.fi/rajapinnat"
    org_id = "mml"
    org_name = "maanmittauslaitos"
    org_title = "Maanmittauslaitos"
    default_update_frequency = "vuosittain"

    datasets_config = [
        {
            "id": "mml-maastotietokanta",
            "title": "Maastotietokanta",
            "notes_fi": (
                "Suomen kattavin maastoa kuvaava aineisto. Sisältää rakennukset,"
                " tiet, vesistöt, maankäytön, hallinnolliset rajat ja korkeussuhteet."
            ),
            "keywords_fi": [
                "maastotieto", "maankaytto", "rakennukset", "vesistot", "tiet",
            ],
            "estimated_size_bytes": 10 * 1024**3,
            "access_level": "registration",
            "resources": [
                {"format": "WFS", "url": f"{MML_BASE}/maastotiedot/wfs"},
                {"format": "WMS", "url": f"{MML_BASE}/maastotiedot/wms"},
                {
                    "format": "API",
                    "url": f"{MML_BASE}/maastotiedot/features/v1/",
                    "name_fi": "Maastotietokanta — OGC API Features",
                },
            ],
        },
        {
            "id": "mml-kiinteistojaotus",
            "title": "Kiinteistöjaotus",
            "notes_fi": (
                "Suomen kiinteistörajat ja -tunnukset."
                " Kiinteistörekisterikartan vektorimuotoinen aineisto."
            ),
            "keywords_fi": [
                "kiinteisto", "kiinteistorekisteri", "tontti", "rajat",
            ],
            "estimated_size_bytes": 3 * 1024**3,
            "access_level": "registration",
            "resources": [
                {"format": "WFS", "url": f"{MML_BASE}/kiinteistojaotus/wfs"},
                {"format": "WMS", "url": f"{MML_BASE}/kiinteistojaotus/wms"},
            ],
        },
        {
            "id": "mml-nimisto",
            "title": "Paikannimet",
            "notes_fi": (
                "Suomen viralliset paikannimet karttanimistörekisteristä."
                " Sisältää suomen-, ruotsin- ja saamenkieliset nimet."
            ),
            "keywords_fi": ["paikannimi", "nimisto", "karttanimi"],
            "estimated_size_bytes": 500 * 1024**2,
            "access_level": "registration",
            "resources": [
                {"format": "WFS", "url": f"{MML_BASE}/nimisto/wfs"},
                {"format": "WMS", "url": f"{MML_BASE}/nimisto/wms"},
            ],
        },
        {
            "id": "mml-peruskartta",
            "title": "Peruskartta (rasteri)",
            "notes_fi": (
                "Peruskarttarasteri 1:25 000 ja 1:50 000."
                " Yleiskäyttöinen taustakartta."
            ),
            "keywords_fi": ["peruskartta", "taustakartta", "rasteri"],
            "estimated_size_bytes": 20 * 1024**3,
            "access_level": "registration",
            "resources": [
                {
                    "format": "WMS",
                    "url": f"{MML_KARTTAKUVA}/avoin/wmts/1.0.0/WMTSCapabilities.xml",
                },
            ],
        },
        {
            "id": "mml-ortokuvat",
            "title": "Ortokuvat (ilmakuvat)",
            "notes_fi": (
                "Suomen kattavat ortoilmakuvat."
                " Maastotarkkuus 0,5 m. Päivitetään alueittain."
            ),
            "keywords_fi": ["ortokuva", "ilmakuva", "kaukokartoitus"],
            "estimated_size_bytes": 50 * 1024**3,
            "access_level": "registration",
            "resources": [
                {"format": "WMS", "url": f"{MML_KARTTAKUVA}/avoin/wmts"},
            ],
        },
        {
            "id": "mml-korkeusmalli",
            "title": "Korkeusmalli 2 m",
            "notes_fi": (
                "Suomen laserkeilauspohjainen korkeusmalli 2 m ruutukoolla."
                " Tarkin valtakunnallinen korkeusaineisto."
            ),
            "keywords_fi": [
                "korkeusmalli", "DEM", "laserkeilaus", "korkeusdata",
            ],
            "estimated_size_bytes": 100 * 1024**3,
            "access_level": "registration",
            "resources": [
                {"format": "WCS", "url": f"{MML_BASE}/korkeusmalli/wcs"},
                {"format": "WMS", "url": f"{MML_BASE}/korkeusmalli/wms"},
            ],
        },
        {
            "id": "mml-hallinnolliset-rajat",
            "title": "Hallinnolliset rajat",
            "notes_fi": (
                "Suomen kunta-, maakunta- ja valtionrajat."
                " INSPIRE Administrative Units -teema."
            ),
            "keywords_fi": [
                "hallinnollinen raja", "kuntaraja", "maakuntaraja",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "access_level": "registration",
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{MML_BASE}/hallinnolliset-aluejaot/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{MML_BASE}/hallinnolliset-aluejaot/wms",
                },
            ],
        },
    ]
