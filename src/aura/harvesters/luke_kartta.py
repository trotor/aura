"""Harvester LUKE:n paikkatietopalvelulle (kartta.luke.fi GeoServer).

LUKE:n GeoServer tarjoaa INSPIRE-lajistoaineistoja, MVMI-metsävarakarttoja
ja kalastusaineistoja WFS- ja WMS-rajapintoina.
"""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

GEOSERVER = "https://kartta.luke.fi/geoserver"
INSPIRE_WFS = f"{GEOSERVER}/inspire/ows"
LUKE_WMS = f"{GEOSERVER}/wms"
MVMI_WMS = f"{GEOSERVER}/MVMI/wms"


class LukeKarttaHarvester(StaticHarvester):
    """Kerää LUKE:n paikkatietoaineistot kartta.luke.fi GeoServeriltä.

    Sisältää INSPIRE-lajistoaineistot (13 eläinlajin levinneisyys),
    MVMI-metsävarakartat (puuston tilavuus, biomassa, latvuspeittävyys)
    ja kalastusaineistot (kutualueet, kaupalliset pyyntialueet).
    """

    name = "luke-kartta"
    description = "LUKE paikkatietopalvelu — metsävarat, riistaeläimet, kalatalous"
    url = "https://kartta.luke.fi"
    org_id = "luke"
    org_name = "luke"
    org_title = "Luonnonvarakeskus (LUKE)"
    default_update_frequency = "tarvittaessa"

    datasets_config = [
        # --- INSPIRE-lajistoaineistot (WFS) ---
        {
            "id": "luke-kartta-inspire-riista",
            "title": "INSPIRE-lajistoaineistot — riistaeläimet",
            "notes_fi": (
                "INSPIRE-direktiivin mukaiset eläinlajien levinneisyystiedot "
                "WFS-rajapintana. Sisältää 13 lajin (mm. minkki, saukko, jänis, "
                "näätä, metsäkauris, kettu, orava, kärppä, valkohäntäpeura) "
                "levinneisyysalueet ja havaintotiheydet."
            ),
            "keywords_fi": [
                "INSPIRE", "lajisto", "riista", "levinneisyys", "eläimet",
                "suurpedot", "WFS", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{INSPIRE_WFS}?service=WFS&version=2.0.0&request=GetCapabilities",
                    "name_fi": "INSPIRE-lajistoaineistot — WFS-rajapinta",
                },
            ],
        },
        {
            "id": "luke-kartta-inspire-kalat",
            "title": "INSPIRE-kalavarojen arviointi",
            "notes_fi": (
                "INSPIRE-direktiivin mukainen kalavarojen arviointiaineisto. "
                "Sisältää 22 kalalajin ja 2 äyriäislajin levinneisyystiedot "
                "Suomen vesistöissä."
            ),
            "keywords_fi": [
                "INSPIRE", "kalasto", "kalat", "kalakannat", "äyriäiset",
                "levinneisyys", "WFS", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{INSPIRE_WFS}?service=WFS&version=2.0.0&request=GetCapabilities",
                    "name_fi": "INSPIRE-kalavarojen arviointi — WFS-rajapinta",
                },
            ],
        },
        # --- MVMI-metsävarakartat (WMS) ---
        {
            "id": "luke-kartta-mvmi",
            "title": "Monilähteinen valtakunnan metsien inventointi (MVMI)",
            "notes_fi": (
                "MVMI (MS-NFI) metsävarakartat 16×16 m ruudukossa. "
                "~45 teematasoa per inventointivuosi: puuston tilavuus lajeittain "
                "(mänty, kuusi, koivu, muu lehtipuu), biomassa, latvuspeittävyys, "
                "kasvupaikkaluokitus, maaluokka ja puulajivaltaisuus. "
                "Inventointivuodet: 2006, 2009, 2011, 2013, 2015, 2017, 2019, 2021."
            ),
            "keywords_fi": [
                "metsävarat", "MVMI", "metsäinventointi", "puusto", "biomassa",
                "latvuspeittävyys", "mänty", "kuusi", "koivu",
                "paikkatietoaineisto", "WMS",
            ],
            "geographical_coverage": ["Suomi"],
            "estimated_size_bytes": 50 * 1024**3,  # kymmenien GB:n rasteriaineisto
            "resources": [
                {
                    "format": "WMS",
                    "url": f"{MVMI_WMS}?service=WMS&version=1.3.0&request=GetCapabilities",
                    "name_fi": "MVMI-metsävarakartat — WMS-karttapalvelu",
                },
                {
                    "format": "GeoTIFF",
                    "url": "https://kartta.luke.fi/index-en.html",
                    "name_fi": "MVMI GeoTIFF-lataus (karttalehtijaolla)",
                },
            ],
        },
        # --- Suurpedot ja riistaeläimet ---
        {
            "id": "luke-kartta-suurpedot",
            "title": "Suurpetohavainnot — karhu, susi, ilves, ahma",
            "notes_fi": (
                "Suurpetojen (karhu, susi, ilves, ahma) havaintopisteet ja "
                "reviirialueet. Sisältää TASSU-järjestelmän havainnot."
            ),
            "keywords_fi": [
                "suurpedot", "karhu", "susi", "ilves", "ahma",
                "luontoseuranta", "riista", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WMS",
                    "url": f"{LUKE_WMS}?service=WMS&version=1.3.0&request=GetCapabilities",
                    "name_fi": "Suurpetohavainnot — WMS-karttapalvelu",
                },
            ],
        },
        {
            "id": "luke-kartta-riistakolmiot",
            "title": "Riistakolmioiden sijainnit",
            "notes_fi": (
                "Riistakolmioiden (riistaseurannan vakioalueiden) sijaintitiedot. "
                "Riistakolmiot ovat 12 km:n mittaisia tasasivuisia kolmioita, "
                "joilla seurataan riistaeläinkantoja vuosittain."
            ),
            "keywords_fi": [
                "riistakolmio", "riistaseuranta", "metsäkanalinnut",
                "jälkilaskenta", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WMS",
                    "url": f"{LUKE_WMS}?service=WMS&version=1.3.0&request=GetCapabilities",
                    "name_fi": "Riistakolmiot — WMS-karttapalvelu",
                },
                {
                    "format": "JSON",
                    "url": "https://kartta.luke.fi",
                    "name_fi": "Riistakolmiot — JSON-lataus",
                },
            ],
        },
        # --- Kalatalous ---
        {
            "id": "luke-kartta-kutualueet",
            "title": "Rannikkoalueiden kalojen kutualueet",
            "notes_fi": (
                "Kalojen poikastuotantoalueet ja kutualueet Suomen rannikolla. "
                "Sisältää tiedot hauen, lahnan, ahvenen, kuhan, silakan, kuoreen, "
                "siian ja muikun kutualueista WMS-tasoina."
            ),
            "keywords_fi": [
                "kutualue", "poikastuotanto", "kalatalous", "hauki", "kuha",
                "ahven", "silakka", "siika", "rannikko", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WMS",
                    "url": (
                        f"{GEOSERVER}/luke/wms"
                        "?service=WMS&version=1.3.0&request=GetCapabilities"
                    ),
                    "name_fi": "Rannikkoalueiden kutualueet — WMS-karttapalvelu",
                },
            ],
        },
        {
            "id": "luke-kartta-kalastusalueet",
            "title": "Kaupalliset kalastusalueet ja trooliseuranta",
            "notes_fi": (
                "Tärkeät kaupalliset kalastusalueet Itämerellä sekä "
                "troolialusten satelliittiseuranta-aineisto (VMS). "
                "Sisältää pyyntialueiden rajaukset ja pyyntiponnistustiedot."
            ),
            "keywords_fi": [
                "kaupallinen kalastus", "troolaus", "kalastusalue",
                "Itämeri", "VMS", "pyyntiponnistus", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WMS",
                    "url": (
                        f"{GEOSERVER}/luke/wms"
                        "?service=WMS&version=1.3.0&request=GetCapabilities"
                    ),
                    "name_fi": "Kalastusalueet — WMS-karttapalvelu",
                },
            ],
        },
        {
            "id": "luke-kartta-hylkeet",
            "title": "Itämeren harmaahylkeiden laskenta-aineisto",
            "notes_fi": (
                "Harmaahylkeiden (Halichoerus grypus) vuosittaiset "
                "laskenta-aineistot Itämeren alueella. Sisältää laskentapisteet "
                "ja arvioidut kannan koot."
            ),
            "keywords_fi": [
                "harmaahylje", "hylje", "merinisäkkäät", "Itämeri",
                "luontoseuranta", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WMS",
                    "url": (
                        f"{GEOSERVER}/luke/wms"
                        "?service=WMS&version=1.3.0&request=GetCapabilities"
                    ),
                    "name_fi": "Harmaahylkeiden laskenta — WMS-karttapalvelu",
                },
            ],
        },
        # --- Maaperä ja eroosio ---
        {
            "id": "luke-kartta-eroosio",
            "title": "Maa-alueiden ja peltomaiden eroosioherkkyys",
            "notes_fi": (
                "RUSLE-mallilla laskettu eroosioherkkyyden arviointi koko Suomen "
                "alueelle. Sisältää potentiaalisen eroosion ja peltomaiden "
                "eroosioherkkyysluokituksen."
            ),
            "keywords_fi": [
                "eroosio", "maaperä", "RUSLE", "pelto", "maatalous",
                "maanpeite", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "resources": [
                {
                    "format": "WMS",
                    "url": f"{LUKE_WMS}?service=WMS&version=1.3.0&request=GetCapabilities",
                    "name_fi": "Eroosioherkkyyskartrat — WMS-karttapalvelu",
                },
            ],
        },
        # --- Biomassa ja kosteusindeksit ---
        {
            "id": "luke-kartta-dtw-kosteus",
            "title": "DTW-kosteusindeksikartta",
            "notes_fi": (
                "Depth-to-water (DTW) kosteusindeksikartta 2 metrin "
                "resoluutiolla. Kuvaa etäisyyttä pohjavedenpintaan "
                "topografian ja valuma-alueiden perusteella."
            ),
            "keywords_fi": [
                "kosteusindeksi", "DTW", "pohjavesi", "topografia",
                "hydrologia", "metsämaa", "paikkatietoaineisto",
            ],
            "geographical_coverage": ["Suomi"],
            "estimated_size_bytes": 20 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": f"{LUKE_WMS}?service=WMS&version=1.3.0&request=GetCapabilities",
                    "name_fi": "DTW-kosteusindeksi — WMS-karttapalvelu",
                },
            ],
        },
    ]
