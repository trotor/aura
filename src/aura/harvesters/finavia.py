"""Harvester Finavian lentoliikennetilastoille.

Suomen lentoliikennetilastot **eivät ole avoimen datan portaalissa**:
avoindata.fi tuntee Finavialta nolla datasettiä, ja hakusanoilla ``ilmailu``,
``lentoliikenne`` ja ``lentoasema`` koko portaalista löytyy seitsemän osumaa,
joista yksikään ei ole lentoliikenteen tilasto. Ainoa lähde on Finavian oma
sivu, jolla aineistot ovat Excel-tiedostoina.

Tiedostot ovat kahta lajia, ja ne on yhdistetty aiheittain samaan datasettiin:

- **kuukausittain päivittyvä** tiedosto, jonka osoite pysyy samana vaikka
  sisältö vaihtuu (otsikossa lukeva kuukausi vanhenee, siksi sitä ei kopioida
  datasetin otsikkoon);
- **pitkä aikasarja** 1998–2025 tai 2013–2025.

Käyttöehtoja ei ilmoiteta. Sivulla on vain tekijänoikeusmerkintä ja yleiset
sivuston käyttöehdot, joten lisenssikenttä jätetään tyhjäksi — cc-by-4.0 olisi
väite jota lähde ei tue.
"""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

DOCS = "https://www.finavia.fi/sites/default/files/documents"
TILASTOSIVU = (
    "https://www.finavia.fi/fi/tietoa-finaviasta/tietoa-lentoliikenteesta/"
    "liikennetilastot"
)

# Yhteiset avainsanat: haku "lentoasema" tai "lentoliikenne" ei osu näihin
# otsikoiden kautta yhtä hyvin kuin voisi kuvitella, koska otsikot puhuvat
# matkustajista ja rahdista.
AVAINSANAT = ["lentoliikenne", "lentoasema", "ilmailu", "liikennetilastot", "Finavia"]


def _xlsx(ds_id: str, suffix: str, tiedosto: str, nimi: str) -> dict[str, str]:
    return {
        "id": f"{ds_id}-{suffix}",
        "format": "XLSX",
        "name": nimi,
        "name_fi": nimi,
        "url": f"{DOCS}/{tiedosto}",
    }


def _sivu(ds_id: str) -> dict[str, str]:
    return {
        "id": f"{ds_id}-html",
        "format": "HTML",
        "name": "Finavian liikennetilastot",
        "name_fi": "Finavian liikennetilastot — verkkosivu",
        "url": TILASTOSIVU,
    }


class FinaviaHarvester(StaticHarvester):
    """Finavian lentoasemien liikennetilastot Excel-tiedostoina.

    Kahdeksan datasettiä kattaa neljätoista tiedostoa: kuukausiversio ja
    pitkä aikasarja ovat saman tilaston kaksi resurssia, eivät kaksi
    datasettiä.
    """

    name = "finavia"
    description = "Finavia — lentoasemien matkustaja-, lento- ja rahtitilastot"
    url = TILASTOSIVU
    org_id = "finavia"
    org_name = "finavia"
    org_title = "Finavia Oyj"
    default_update_frequency = "kuukausittain"

    datasets_config = [
        {
            "id": "finavia-matkustajat-lentoasemittain",
            "title": "Matkustajamäärät lentoasemittain",
            "notes_fi": (
                "Finavian lentoasemien matkustajamäärät lentoasemittain, "
                "kotimaan ja kansainvälinen liikenne eriteltyinä. "
                "Kuukausitiedosto päivittyy kuukausittain, aikasarja kattaa "
                "vuodet 1998–2025."
            ),
            "keywords_fi": [*AVAINSANAT, "matkustajamäärät"],
            "license_id": "",
            "license_title": "",
            "estimated_size_bytes": 62_000,
            "resources": [
                _xlsx(
                    "finavia-matkustajat-lentoasemittain", "kk",
                    "Matkustajat%20lentoasemittain-fi_77.xlsx",
                    "Matkustajamäärät lentoasemittain, kuukausitiedot",
                ),
                _xlsx(
                    "finavia-matkustajat-lentoasemittain", "aikasarja",
                    "Matkustajat%20lentoasemittain%201998-2025-fi-fi.xlsx",
                    "Matkustajamäärät lentoasemittain 1998–2025",
                ),
                _sivu("finavia-matkustajat-lentoasemittain"),
            ],
        },
        {
            "id": "finavia-matkustajat-helsinki-vantaa",
            "title": "Helsinki-Vantaan matkustajamäärät",
            "notes_fi": (
                "Helsinki-Vantaan lentoaseman matkustajamäärät: kotimaan ja "
                "kansainvälisen liikenteen saapuvat ja lähtevät matkustajat. "
                "Kuukausitiedosto ja aikasarja 1998–2025."
            ),
            "keywords_fi": [*AVAINSANAT, "matkustajamäärät", "Helsinki-Vantaa"],
            "license_id": "",
            "license_title": "",
            "geographical_coverage": ["Vantaa", "Suomi"],
            "estimated_size_bytes": 15_000,
            "resources": [
                _xlsx(
                    "finavia-matkustajat-helsinki-vantaa", "kk",
                    "HEL%20matk%20kuukausittain-fi_70.xlsx",
                    "Helsinki-Vantaan matkustajamäärät, kuukausitiedot",
                ),
                _xlsx(
                    "finavia-matkustajat-helsinki-vantaa", "aikasarja",
                    "HEL%20matkustajat%201998-2025-fi-fi.xlsx",
                    "Helsinki-Vantaan matkustajamäärät 1998–2025",
                ),
                _sivu("finavia-matkustajat-helsinki-vantaa"),
            ],
        },
        {
            "id": "finavia-kv-reittiliikenne",
            "title": "Kansainvälisen reittiliikenteen matkustajamäärät maittain",
            "notes_fi": (
                "Kansainvälisten reittilentojen matkustajamäärät kohdemaittain. "
                "Kuukausitiedosto ja aikasarja 2013–2025."
            ),
            "keywords_fi": [*AVAINSANAT, "reittiliikenne", "kansainvälinen liikenne"],
            "license_id": "",
            "license_title": "",
            "estimated_size_bytes": 36_000,
            "resources": [
                _xlsx(
                    "finavia-kv-reittiliikenne", "kk",
                    "Kv%20reittiliikenteen%20matk-fi_73.xlsx",
                    "Kansainvälisen reittiliikenteen matkustajat, kuukausitiedot",
                ),
                _xlsx(
                    "finavia-kv-reittiliikenne", "aikasarja",
                    "Kv%20reittiliikenteen%20matk%20maittain%202013-2025-fi-fi.xlsx",
                    "Kansainvälinen reittiliikenne maittain 2013–2025",
                ),
                _sivu("finavia-kv-reittiliikenne"),
            ],
        },
        {
            "id": "finavia-kv-tilausliikenne",
            "title": "Kansainvälisen tilausliikenteen matkustajamäärät maittain",
            "notes_fi": (
                "Kansainvälisten tilauslentojen matkustajamäärät kohdemaittain. "
                "Kuukausitiedosto ja aikasarja 2013–2025."
            ),
            "keywords_fi": [*AVAINSANAT, "tilausliikenne", "charter"],
            "license_id": "",
            "license_title": "",
            "estimated_size_bytes": 29_000,
            "resources": [
                _xlsx(
                    "finavia-kv-tilausliikenne", "kk",
                    "Kv%20tilausliikenteen%20matk-fi_71.xlsx",
                    "Kansainvälisen tilausliikenteen matkustajat, kuukausitiedot",
                ),
                _xlsx(
                    "finavia-kv-tilausliikenne", "aikasarja",
                    "Kv%20tilausliikenteen%20matk%20maittain%202013-2025-fi-fi.xlsx",
                    "Kansainvälinen tilausliikenne maittain 2013–2025",
                ),
                _sivu("finavia-kv-tilausliikenne"),
            ],
        },
        {
            "id": "finavia-lentomaarat",
            "title": "Lentojen määrät lentoasemittain",
            "notes_fi": (
                "Kaikkien lentojen laskeutumiset ja lentoonlähdöt "
                "lentoasemittain. Sisältää matkustajalentojen lisäksi mm. "
                "rahti-, koulutus- ja sotilaslennot."
            ),
            "keywords_fi": [*AVAINSANAT, "laskeutumiset", "lentoonlähdöt"],
            "license_id": "",
            "license_title": "",
            "estimated_size_bytes": 14_000,
            "resources": [
                _xlsx(
                    "finavia-lentomaarat", "kk",
                    "Lentom%C3%A4%C3%A4r%C3%A4t%20lentoasemittain-fi_74.xlsx",
                    "Lentojen määrät lentoasemittain, kuukausitiedot",
                ),
                _sivu("finavia-lentomaarat"),
            ],
        },
        {
            "id": "finavia-matkustajalentojen-maarat",
            "title": "Matkustajalentojen määrät lentoasemittain",
            "notes_fi": (
                "Liikenneilmailun eli matkustajalentojen laskeutumiset ja "
                "lentoonlähdöt lentoasemittain. Kuukausitiedosto ja "
                "laskeutumisten aikasarja 1998–2025."
            ),
            "keywords_fi": [*AVAINSANAT, "laskeutumiset", "liikenneilmailu"],
            "license_id": "",
            "license_title": "",
            "estimated_size_bytes": 28_000,
            "resources": [
                _xlsx(
                    "finavia-matkustajalentojen-maarat", "kk",
                    "Liikenneilmailun%20lentom%C3%A4%C3%A4r%C3%A4t%20"
                    "lentoasemittain-fi_86.xlsx",
                    "Matkustajalentojen määrät lentoasemittain, kuukausitiedot",
                ),
                _xlsx(
                    "finavia-matkustajalentojen-maarat", "aikasarja",
                    "Laskeutumiset%20lentoasemittain%201998-2025-fi-fi.xlsx",
                    "Matkustajalentojen laskeutumiset lentoasemittain 1998–2025",
                ),
                _sivu("finavia-matkustajalentojen-maarat"),
            ],
        },
        {
            "id": "finavia-rahti",
            "title": "Rahti- ja postimäärät lentoasemittain",
            "notes_fi": (
                "Lentorahdin ja -postin määrät lentoasemittain, kotimaan ja "
                "kansainvälinen liikenne eriteltyinä. Kuukausitiedosto ja "
                "aikasarja 1998–2025."
            ),
            "keywords_fi": [*AVAINSANAT, "lentorahti", "posti"],
            "license_id": "",
            "license_title": "",
            "estimated_size_bytes": 14_000,
            "resources": [
                _xlsx(
                    "finavia-rahti", "kk",
                    "Tavaraliikenne-fi_72.xlsx",
                    "Rahti- ja postimäärät lentoasemittain, kuukausitiedot",
                ),
                _xlsx(
                    "finavia-rahti", "aikasarja",
                    "Tavaraliikenne%201998-2025-fi-fi.xlsx",
                    "Rahti- ja postimäärät 1998–2025",
                ),
                _sivu("finavia-rahti"),
            ],
        },
        {
            "id": "finavia-rahti-helsinki-vantaa",
            "title": "Helsinki-Vantaan rahti- ja postimäärät",
            "notes_fi": (
                "Helsinki-Vantaan lentoaseman lentorahdin ja -postin määrät "
                "kuukausittain."
            ),
            "keywords_fi": [*AVAINSANAT, "lentorahti", "Helsinki-Vantaa"],
            "license_id": "",
            "license_title": "",
            "geographical_coverage": ["Vantaa", "Suomi"],
            "estimated_size_bytes": 7_000,
            "resources": [
                _xlsx(
                    "finavia-rahti-helsinki-vantaa", "kk",
                    "HEL%20tavaraliikenne-fi_70.xlsx",
                    "Helsinki-Vantaan rahti- ja postimäärät, kuukausitiedot",
                ),
                _sivu("finavia-rahti-helsinki-vantaa"),
            ],
        },
    ]
