"""Harvester Suomen Lajitietokeskuksen (FinBIF) tietovarannoille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

LAJI_API = "https://api.laji.fi/v0"
LAJI_FI = "https://laji.fi"


class LajitietokeskusHarvester(StaticHarvester):
    """Kerää Suomen Lajitietokeskuksen (FinBIF) tietovarannot.

    Lajitietokeskus (laji.fi) kerää ja yhdistää suomalaisen eliölajitiedon
    yhtenäiseksi ja avoimeksi kokonaisuudeksi. Palvelussa on tietoja yli
    45 000 lajista sekä yli 45 miljoonaa havaintoa.

    Rajapinnat:
    - REST API (api.laji.fi) — vaatii rekisteröitymisen (access token)
    - OGC API Features — paikkatietorajapinta
    - WMS — karttapalvelu

    API-avain: rekisteröidy osoitteessa https://api.laji.fi/v0/api-user
    """

    name = "lajitietokeskus"
    description = "Suomen Lajitietokeskus (FinBIF) — lajitiedot ja havaintodata"
    url = "https://laji.fi"
    org_id = "lajitietokeskus"
    org_name = "lajitietokeskus"
    org_title = "Suomen Lajitietokeskus ja Luonnontieteellinen keskusmuseo Luomus"

    datasets_config = [
        # --- Havaintodata ---
        {
            "id": "lajifi-havaintodata",
            "title": "Laji.fi havaintodata",
            "title_fi": "Laji.fi havaintodata",
            "notes_fi": (
                "Suomen kattavin eliölajien havaintoaineisto. Sisältää yli"
                " 45 miljoonaa havaintoa sadoista eri lähteistä: kansalaishavainnot,"
                " museokokoelmat, tutkimusaineistot ja viranomaisseurannat."
                " Data on haettavissa REST API:n ja OGC API:n kautta."
            ),
            "keywords_fi": [
                "lajihavainnot", "eliölajit", "biodiversiteetti",
                "luontohavainnot", "kansalaistiede", "seuranta",
                "ympäristö", "luonto",
            ],
            "update_frequency": "päivittäin",
            "estimated_size_bytes": 10 * 1024**3,
            "resources": [
                {
                    "id": "lajifi-havaintodata-api",
                    "format": "API",
                    "url": f"{LAJI_API}/warehouse/query/unit/list",
                    "name_fi": "Havaintodata — REST API (vaatii API-avaimen)",
                },
                {
                    "id": "lajifi-havaintodata-ogc",
                    "format": "API",
                    "url": "https://geo.laji.fi/",
                    "name_fi": "Havaintodata — OGC API Features",
                },
                {
                    "id": "lajifi-havaintodata-portaali",
                    "format": "HTML",
                    "url": f"{LAJI_FI}/observation/list",
                    "name_fi": "Havaintodata — laji.fi-portaali",
                },
            ],
        },
        # --- Taksonomia ---
        {
            "id": "lajifi-taksonomia",
            "title": "Suomen lajien taksonomiatietokanta",
            "title_fi": "Suomen lajien taksonomiatietokanta",
            "notes_fi": (
                "Suomen eliölajien taksonominen luokittelu ja nimistö."
                " Sisältää tieteelliset nimet, suomenkieliset nimet,"
                " synonyymit ja luokitteluhierarkian yli 45 000 lajille."
            ),
            "keywords_fi": [
                "taksonomia", "lajinimet", "eliölajit", "luokittelu",
                "biologia", "luonnontieteet",
            ],
            "update_frequency": "jatkuva",
            "resources": [
                {
                    "id": "lajifi-taksonomia-api",
                    "format": "API",
                    "url": f"{LAJI_API}/taxa",
                    "name_fi": "Taksonomia — REST API (vaatii API-avaimen)",
                },
                {
                    "id": "lajifi-taksonomia-portaali",
                    "format": "HTML",
                    "url": f"{LAJI_FI}/taxon",
                    "name_fi": "Taksonomia — laji.fi-portaali",
                },
            ],
        },
        # --- Kokoelmat ---
        {
            "id": "lajifi-kokoelmat",
            "title": "Luonnontieteelliset kokoelmat",
            "title_fi": "Luonnontieteelliset kokoelmat",
            "notes_fi": (
                "Suomalaisten museoiden ja tutkimuslaitosten"
                " luonnontieteelliset eliökokoelmat. Sisältää tiedot"
                " kokoelmista, niiden laajuudesta ja digitointiasteesta."
                " Kokoelmat kattavat kasvi-, eläin- ja sieninäytteitä."
            ),
            "keywords_fi": [
                "kokoelmat", "museot", "näytteet", "luonnontieteet",
                "eliölajit", "digitointi",
            ],
            "resources": [
                {
                    "id": "lajifi-kokoelmat-api",
                    "format": "API",
                    "url": f"{LAJI_API}/collections",
                    "name_fi": "Kokoelmat — REST API (vaatii API-avaimen)",
                },
            ],
        },
        # --- Kasviatlas ---
        {
            "id": "lajifi-kasviatlas",
            "title": "Kasviatlas — Suomen putkilokasvien levinneisyys",
            "title_fi": "Kasviatlas — Suomen putkilokasvien levinneisyys",
            "notes_fi": (
                "Suomen putkilokasvien levinneisyyskartasto."
                " Sisältää karttoja ja tilastotietoja putkilokasvien"
                " levinneisyydestä Suomessa yhtenäiskoordinaattiruuduittain."
            ),
            "keywords_fi": [
                "kasvit", "putkilokasvit", "levinneisyys", "kasvitiede",
                "kartasto", "atlas", "luonto",
            ],
            "license_id": "cc-by-4.0",
            "license_title": "Creative Commons Attribution 4.0",
            "resources": [
                {
                    "id": "lajifi-kasviatlas-portaali",
                    "format": "HTML",
                    "url": "https://kasviatlas.fi",
                    "name_fi": "Kasviatlas — verkkopalvelu",
                },
                {
                    "id": "lajifi-kasviatlas-api",
                    "format": "API",
                    "url": f"{LAJI_API}/warehouse/query/unit/aggregate",
                    "name_fi": "Kasviatlas — data REST API:n kautta",
                },
            ],
        },
        # --- Lintuatlas ---
        {
            "id": "lajifi-lintuatlas",
            "title": "Suomen Lintuatlas — pesimälintulajien levinneisyys",
            "title_fi": "Suomen Lintuatlas — pesimälintulajien levinneisyys",
            "notes_fi": (
                "Lintuatlaksen tavoitteena on selvittää Suomen pesimälintulajien"
                " levinneisyydet sekä tutkia lajien levinneisyyksien muutoksia."
                " Lintulajien esiintymistieto on kerätty 10x10 km²"
                " yhtenäiskoordinaatistoruuduista koko Suomesta."
                " Atlaskartoitukset: 1974–79, 1986–89, 2006–2010, 2022–2025."
            ),
            "keywords_fi": [
                "linnut", "pesimälinnut", "levinneisyys", "atlas",
                "lintukartoitus", "eläintiede", "seuranta", "luonto",
            ],
            "license_id": "cc-by-4.0",
            "license_title": "Creative Commons Attribution 4.0",
            "resources": [
                {
                    "id": "lajifi-lintuatlas-portaali",
                    "format": "HTML",
                    "url": f"{LAJI_FI}/map",
                    "name_fi": "Lintuatlas — laji.fi-karttapalvelu",
                },
                {
                    "id": "lajifi-lintuatlas-api",
                    "format": "API",
                    "url": f"{LAJI_API}/warehouse/query/unit/aggregate",
                    "name_fi": "Lintuatlas — data REST API:n kautta",
                },
            ],
        },
        # --- Uhanalaisarviointi ---
        {
            "id": "lajifi-uhanalaisarviointi",
            "title": "Suomen lajien uhanalaisarviointi (Punainen kirja)",
            "title_fi": "Suomen lajien uhanalaisarviointi (Punainen kirja)",
            "notes_fi": (
                "Suomen lajien uhanalaisuuden arviointi IUCN-kriteerein."
                " Sisältää uhanalaisluokitukset, arviointiperusteet ja"
                " lajien elinympäristötiedot. Punainen lista kattaa"
                " kaikki arvioidut eliöryhmät."
            ),
            "keywords_fi": [
                "uhanalaisuus", "punainen lista", "IUCN",
                "luonnonsuojelu", "lajiensuojelu", "biodiversiteetti",
                "eliölajit",
            ],
            "resources": [
                {
                    "id": "lajifi-uhanalaisarviointi-api",
                    "format": "API",
                    "url": f"{LAJI_API}/red-list-evaluation-groups",
                    "name_fi": (
                        "Uhanalaisarviointi — REST API (vaatii API-avaimen)"
                    ),
                },
                {
                    "id": "lajifi-uhanalaisarviointi-portaali",
                    "format": "HTML",
                    "url": "https://punainenkirja.laji.fi",
                    "name_fi": "Punainen kirja — verkkopalvelu",
                },
            ],
        },
        # --- Vieraslajit ---
        {
            "id": "lajifi-vieraslajit",
            "title": "Suomen vieraslajiportaali",
            "title_fi": "Suomen vieraslajiportaali",
            "notes_fi": (
                "Tietoa Suomen haitallisista vieraslajeista,"
                " niiden tunnistamisesta, levinneisyydestä ja torjunnasta."
                " Sisältää EU:n vieraslajiluettelon ja kansallisen"
                " vieraslajistrategian lajit."
            ),
            "keywords_fi": [
                "vieraslajit", "haitalliset vieraslajit",
                "invasiiviset lajit", "luonnonsuojelu", "torjunta",
            ],
            "resources": [
                {
                    "id": "lajifi-vieraslajit-portaali",
                    "format": "HTML",
                    "url": "https://vieraslajit.fi",
                    "name_fi": "Vieraslajiportaali — verkkopalvelu",
                },
            ],
        },
        # --- Paikkatietotuotteet ---
        {
            "id": "lajifi-paikkatietotuotteet",
            "title": "Lajitietokeskuksen paikkatietotuotteet",
            "title_fi": "Lajitietokeskuksen paikkatietotuotteet",
            "notes_fi": (
                "Lajitietokeskuksen tuottamia paikkatietoaineistoja:"
                " elinympäristöennustekartat, yhtenäiskoordinaatisto (YKJ),"
                " VIRVA-paikkatietotuote ja eliömaakuntarajat."
                " Aineistot ovat saatavilla GeoPackage-, GeoJSON-"
                " ja WMS-muodoissa."
            ),
            "keywords_fi": [
                "paikkatieto", "GIS", "elinympäristö", "ennustekartat",
                "YKJ", "koordinaatisto", "eliömaakunnat",
            ],
            "resources": [
                {
                    "id": "lajifi-paikkatieto-ogc",
                    "format": "API",
                    "url": "https://geo.laji.fi/",
                    "name_fi": "Paikkatietotuotteet — OGC API Features",
                },
                {
                    "id": "lajifi-paikkatieto-info",
                    "format": "HTML",
                    "url": "https://info.laji.fi/etusivu/paikkatieto/",
                    "name_fi": "Paikkatietotuotteet — dokumentaatio",
                },
            ],
        },
        # --- GBIF-integraatio ---
        {
            "id": "lajifi-gbif",
            "title": "Suomen lajitiedot GBIF-palvelussa",
            "title_fi": "Suomen lajitiedot GBIF-palvelussa",
            "notes_fi": (
                "Global Biodiversity Information Facility (GBIF) jakaa"
                " suomalaista eliölajien havainto- ja esiintymistietoa"
                " kansainvälisesti. Lajitietokeskus toimii Suomen"
                " GBIF-solmupisteenä ja välittää aineistoja GBIF:iin."
            ),
            "keywords_fi": [
                "GBIF", "kansainvälinen", "biodiversiteetti",
                "havainnot", "esiintymistieto", "avoin data",
            ],
            "license_id": "cc-by-4.0",
            "license_title": "Creative Commons Attribution 4.0",
            "resources": [
                {
                    "id": "lajifi-gbif-portaali",
                    "format": "HTML",
                    "url": "https://www.gbif.org/country/FI/summary",
                    "name_fi": "GBIF — Suomen maasivu",
                },
                {
                    "id": "lajifi-gbif-api",
                    "format": "API",
                    "url": "https://api.gbif.org/v1/occurrence/search?country=FI",
                    "name_fi": "GBIF API — Suomen havainnot",
                },
            ],
        },
        # --- REST API (kehittäjille) ---
        {
            "id": "lajifi-rest-api",
            "title": "Laji.fi REST API",
            "title_fi": "Laji.fi REST API",
            "notes_fi": (
                "Lajitietokeskuksen REST-rajapinta kehittäjille."
                " 172 endpointia: lajitiedot, havainnot, kokoelmat,"
                " taksonomia, uhanalaisarvioinnit, lomakkeet ja"
                " Data Warehouse -aggregaattikyselyt."
                " Rekisteröidy: https://api.laji.fi/v0/api-user"
            ),
            "keywords_fi": [
                "API", "rajapinta", "REST", "kehittäjät",
                "avoin data", "lajitiedot",
            ],
            "update_frequency": "jatkuva",
            "access_level": "registration",
            "resources": [
                {
                    "id": "lajifi-rest-api-docs",
                    "format": "HTML",
                    "url": "https://api.laji.fi/explorer/",
                    "name_fi": "REST API — dokumentaatio (Swagger)",
                },
                {
                    "id": "lajifi-rest-api-register",
                    "format": "HTML",
                    "url": f"{LAJI_API}/api-user",
                    "name_fi": "REST API — rekisteröityminen",
                },
            ],
        },
        # --- R-paketti ---
        {
            "id": "lajifi-r-paketti",
            "title": "FinBIF R-paketti (finbif)",
            "title_fi": "FinBIF R-paketti (finbif)",
            "notes_fi": (
                "R-ohjelmointikielen paketti laji.fi-datan hakemiseen."
                " Mahdollistaa havaintojen, lajitietojen ja kokoelmien"
                " haun suoraan R-ympäristöön tilastollista analyysia varten."
            ),
            "keywords_fi": [
                "R", "tilastointi", "data-analyysi", "ohjelmointi",
                "lajitiedot", "tutkimus",
            ],
            "resources": [
                {
                    "id": "lajifi-r-paketti-cran",
                    "format": "HTML",
                    "url": "https://luomus.github.io/finbif/",
                    "name_fi": "finbif R-paketti — dokumentaatio",
                },
            ],
        },
    ]
