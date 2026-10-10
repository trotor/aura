"""Harvester Maanmittauslaitoksen (MML) paikkatietorajapinnoille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

MML_BASE = "https://avoin-paikkatieto.maanmittauslaitos.fi"
MML_KARTTAKUVA = "https://avoin-karttakuva.maanmittauslaitos.fi"
#: Maanmittauslaitoksen arviointikäytäntö (kiinteistöjen ja metsän arviointi).
MML_AK = "https://ak.maanmittauslaitos.fi"
#: Luken kantohinnat: pystykaupan hinnat hinta-alueittain ja hakkuutavoittain.
LUKE_KANTOHINNAT = "luke-0100_teokau.px"

#: Metsän hinta ja arvo. Auran kannalta tärkeintä on kertoa, mikä on avointa
#: dataa ja mikä ei: puuston hakkuuarvon voi laskea avoimesta datasta
#: (Metsäkeskuksen kuviot × Luken kantohinnat), mutta toteutuneet
#: kauppahinnat ja Tapion arvotaulukot eivät ole avoimia. Merkinnät ohjaavat
#: kysyjän oikeaan lähteeseen.
_HINTA_JA_ARVO: list[dict[str, object]] = [
    {
        "id": "mml-kauppahintarekisteri",
        "title": "Kiinteistöjen kauppahintarekisteri",
        "notes_fi": (
            "Maanmittauslaitoksen rekisteri kiinteistökaupoista: kauppahinta, pinta-ala,"
            " kunta ja kiinteistön tiedot jokaisesta kaupasta 1980-luvulta lähtien."
            " Rekisteri on julkinen, mutta yksittäiset kaupat eivät ole avointa dataa:"
            " tietoja luovutetaan Maanmittauslaitoksen asiakaspalvelun kautta."
            " Avoimesti saatavilla ovat koosteet: kiinteistöjen kauppahintatilasto"
            " (mml-kiinteistojen-kauppahintatilasto) ja metsän hintakehitys."
            " Metsätilan hinnan arvioon ks. mml-summa-arvomenetelma."
        ),
        "keywords_fi": [
            "kauppahinta", "kiinteistökauppa", "metsätilakauppa", "metsän hinta",
            "maapohjan hinta", "kiinteistön arvo",
        ],
        "access_level": "restricted",
        "update_frequency": "jatkuva",
        "license_id": "other-closed",
        "license_title": "Ei avointa dataa (luovutus MML:n asiakaspalvelusta)",
        "resources": [
            {
                "format": "HTML",
                "url": f"{MML_AK}/2026/indeksit/metsan-hintakehitys",
                "name_fi": "Metsän hintakehitys (MML:n arviointikäytäntö)",
            },
        ],
    },
    {
        "id": "mml-kiinteistojen-kauppahintatilasto",
        "title": "Kiinteistöjen kauppahintatilasto: metsätilojen hinnat",
        "notes_fi": (
            "Maanmittauslaitoksen kauppahintarekisteriin perustuva tilasto omakotitalojen,"
            " kesämökkien, peltojen ja metsien kauppojen määristä ja hinnoista."
            " Metsätiloista julkaistaan mediaanihinta euroa hehtaarilta maakunnittain"
            " (vuonna 2025 koko maassa noin 4 400 €/ha, Uusimaa noin 6 700 €/ha ja"
            " Lappi noin 1 500 €/ha). Tiedot julkaistaan vuosittain, ja kuluvan vuoden"
            " luvut kumulatiivisesti kuukausittain. Tilastojulkaisu, ei rajapintaa."
        ),
        "keywords_fi": [
            "metsän hinta", "metsätilan hinta", "metsätilakauppa", "kauppahinta",
            "euroa hehtaarilta", "peltojen hinta", "kiinteistökauppa",
        ],
        "title_en": "Real estate sales price statistics: forest prices",
        "keywords_en": ["forest price", "forest land price", "real estate sales"],
        "access_level": "open",
        "update_frequency": "kuukausittain",
        "license_id": "cc-by-4.0",
        "license_title": "CC BY 4.0",
        "resources": [
            {
                "format": "HTML",
                "url": "https://stat.fi/fi/tilasto/kkahin",
                "name_fi": "Kiinteistöjen kauppahintatilasto (Tilastokeskus ja MML)",
            },
        ],
    },
    {
        "id": "mml-metsatilakauppojen-kauppahinta-aineisto",
        "title": "Metsätilakauppojen kauppahinta-aineisto",
        "notes_fi": (
            "Maanmittauslaitoksen arviointiaineisto toteutuneista metsätilakaupoista"
            " (yli 10 ha, 2021–2023): kunta, kiinteistötunnus, metsämaan ala,"
            " puuston määrä, pyyntihinta, summa-arvo, kauppahinta, metsämaan hinta"
            " €/ha ja hintakerroin (kauppahinta / summa-arvo) Tapion"
            " summa-arvomenetelmän laskenta-alueittain. Ei avointa dataa:"
            " saatavilla pyytämällä Maanmittauslaitokselta."
        ),
        "keywords_fi": [
            "metsätilakauppa", "kauppahinta", "hintakerroin", "summa-arvo",
            "metsän hinta", "metsätilan arvo",
        ],
        "access_level": "restricted",
        "license_id": "other-closed",
        "license_title": "Ei avointa dataa (pyynnöstä MML:ltä)",
        "resources": [
            {
                "format": "HTML",
                "url": f"{MML_AK}/2026/metsatilakauppojen-kauppahinta-aineisto",
            },
        ],
    },
    {
        "id": "mml-summa-arvomenetelma",
        "title": "Metsätilan arviointi: summa-arvomenetelmä",
        "notes_fi": (
            "Suomen yleisin tapa arvioida metsätilan arvo. Kuvioittain lasketaan"
            " paljaan maan, taimikoiden ja kasvatusmetsien puuston arvot, summa"
            " korjataan kokonaisarvoon (ensisijaisesti verotukselliset ja hallinnolliset"
            " kulut, noin −19 %) ja lopuksi huomioidaan arvoa nostavat ja laskevat"
            " tekijät. Kasvatusmetsän arvo = hakkuuarvo × odotusarvokerroin."
            " Avoimesta datasta saa puuston hakkuuarvon: Metsäkeskuksen metsävarakuviot"
            " (metsakeskus-stand: tukki- ja kuitupuun m³/ha, puulajiosuudet,"
            " kehitysluokka; aluerajaukseksi kelpaa kiinteistötunnus) kerrottuna Luken"
            f" kantohinnoilla ({LUKE_KANTOHINNAT}: pystykauppa hinta-alueittain,"
            " uudistus- ja harvennushakkuu). MML suosittaa usean vuoden keskihintaa."
            " Maapohjan ja taimikoiden arvot sekä odotusarvokertoimet ovat Tapion"
            " summa-arvomenetelmän taulukoissa (13 laskenta-aluetta), jotka eivät ole"
            " avointa dataa. Hakkuuarvo ei siis ole tilan hinta."
        ),
        "keywords_fi": [
            "metsän arvo", "metsätilan arvo", "metsän hinta", "puuston arvo",
            "hakkuuarvo", "kantohinta", "odotusarvo", "summa-arvo", "metsätila-arvio",
        ],
        "title_en": "Forest property valuation: sum-of-values method",
        "keywords_en": ["forest valuation", "timber value", "stumpage price"],
        "access_level": "open",
        "collection_type": "Ohje",
        "license_id": "other-open",
        "license_title": "Julkinen ohje (MML)",
        "resources": [
            {
                "format": "HTML",
                "url": f"{MML_AK}/2026/metsatalous/arviointimenetelmat/summa-arvomenetelma",
                "name_fi": "Summa-arvomenetelmä (MML:n arviointikäytäntö)",
            },
            {
                "format": "PDF",
                "url": f"{MML_AK}/sites/default/files/2025/Soveltamisohje%202024.pdf",
                "name_fi": "Summa-arvomenetelmän taulukoiden soveltamisohje (10.6.2024)",
            },
            {
                "format": "HTML",
                "url": f"{MML_AK}/2026/tapion-summa-arvomenetelman-taulukoiden-laskenta-alueet",
                "name_fi": "Tapion summa-arvomenetelmän laskenta-alueet",
            },
        ],
    },
]


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
        *_HINTA_JA_ARVO,
    ]
