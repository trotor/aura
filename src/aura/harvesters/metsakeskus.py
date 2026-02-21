"""Harvester Suomen metsäkeskuksen aineistoille."""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

GEOSERVER_BASE = "https://avoin.metsakeskus.fi/rajapinnat/v1"
DOWNLOAD_BASE = "https://avoin.metsakeskus.fi/aineistot"
INFO_PAGE_URL = "https://avoin.metsakeskus.fi"


# --- Apufunktiot konfiguraation generointiin ---


def _svc(
    endpoint: str,
    title: str,
    description: str,
    keywords: list[str],
    size_gb: float,
    download_dir: str = "",
    fmt: str = "WFS",
) -> dict[str, Any]:
    """Luo pääpalvelun konfiguraatio."""
    ep = endpoint.lower()
    resources: list[dict[str, Any]] = [
        {"format": fmt, "url": f"{GEOSERVER_BASE}/{endpoint}/ows"},
    ]
    if download_dir:
        resources.append(
            {"format": "ZIP", "url": f"{DOWNLOAD_BASE}/{download_dir}/"}
        )
    else:
        resources.append({"format": "HTML", "url": INFO_PAGE_URL})
    return {
        "id": f"metsakeskus-{ep}",
        "name": f"metsakeskus-{ep.replace('_', '-')}",
        "title": title,
        "notes_fi": description,
        "keywords_fi": keywords,
        "estimated_size_bytes": int(size_gb * 1024**3),
        "resources": resources,
    }


def _kemera(endpoint: str, title: str) -> dict[str, Any]:
    """Luo Kemera-endpointin konfiguraatio."""
    ep = endpoint.lower()
    return {
        "id": f"metsakeskus-{ep}",
        "name": f"metsakeskus-{ep.replace('_', '-')}",
        "title": title,
        "notes_fi": f"Kemera-rahoituslain mukainen tukitieto. Endpoint: {endpoint}",
        "keywords_fi": ["metsä", "kemera", "tuki", "metsänhoito"],
        "estimated_size_bytes": 500 * 1024 * 1024,
        "resources": [
            {"format": "WFS", "url": f"{GEOSERVER_BASE}/{endpoint}/ows"},
            {"format": "ZIP", "url": f"{DOWNLOAD_BASE}/Kemera/"},
        ],
    }


# --- Konfiguraatiot ---

_MAIN_SERVICES = [
    _svc("stand", "Metsävarakuviot",
         "Kuviotason metsävaratiedot: puulaji, tilavuus, ikä, pituus, läpimitta, kasvupaikka",
         ["metsä", "kuviotiedot", "puusto", "metsävarat"], 50, "Metsavarakuviot"),
    _svc("gridcell", "Hilatiedot (16m ruutudata)",
         "Laserkeilauspohjaiset metsävaratiedot 16m ruuduissa: puulajikohtaiset tiedot",
         ["metsä", "hila", "laserkeilaus", "LiDAR"], 200, "Hila"),
    _svc("habitat", "Erityisen tärkeät elinympäristöt",
         "Metsälain 10 §:n mukaiset erityisen tärkeät elinympäristöt",
         ["metsä", "elinympäristö", "luonnonsuojelu", "metsälaki"], 5,
         "Erityisen_tarkeat_elinymparistokuviot"),
    _svc("forestusedeclaration", "Metsänkäyttöilmoitukset",
         "Hakkuu- ja muut metsänkäyttöilmoitukset",
         ["metsä", "hakkuu", "metsänkäyttöilmoitus"], 10, "Metsankayttoilmoitukset"),
    _svc("forestmask", "Metsämaski",
         "Metsä/ei-metsä-luokitus",
         ["metsä", "maankäyttö", "luokitus"], 5, "Metsamaski"),
    _svc("inventory_sampleplot", "Inventointikoealat",
         "Maastoinventoinnin koealat metsävarojen kalibrointiin",
         ["metsä", "inventointi", "koeala"], 1, "Inventointikoealat"),
    _svc("sampleplot", "Kaukokartoituskoealat",
         "Kaukokartoituksen referenssikoealat",
         ["metsä", "kaukokartoitus", "koeala"], 1, "Kaukokartoituskoealat"),
    # WCS-palvelut (ei tiedostolatausta)
    _svc("CHM_newest", "Latvusmalli (uusin)",
         "Laserkeilauspohjainen latvuston korkeusmalli, uusin versio",
         ["metsä", "latvusmalli", "CHM", "LiDAR"], 100, fmt="WCS"),
    _svc("Pintavesien_virtausmalli", "Pintavesien virtausmalli",
         "Hydrologinen pintavesien virtausmalli",
         ["hydrologia", "vesistö", "virtaus"], 20, fmt="WCS"),
    _svc("D8_flow_direction", "Virtaussuuntamalli (D8)",
         "D8-algoritmin mukainen virtaussuuntamalli",
         ["hydrologia", "virtaus", "D8"], 20, fmt="WCS"),
    _svc("FA_flow_accumulation", "Valunta-aluemalli",
         "Veden kertymämalli (flow accumulation)",
         ["hydrologia", "valunta", "vesistö"], 20, fmt="WCS"),
]

_CHM_YEARS: list[dict[str, Any]] = [
    {
        "id": "metsakeskus-chm-{year}",
        "title": "Latvusmalli {year}",
        "notes_fi": "Laserkeilauspohjainen latvuston korkeusmalli vuodelta {year}",
        "keywords_fi": ["metsä", "latvusmalli", "CHM", "LiDAR"],
        "estimated_size_bytes": 50 * 1024**3,
        "years": range(2008, 2023),
        "resources": [
            {"format": "WCS", "url": GEOSERVER_BASE + "/CHM_{year}/ows"},
            {"format": "ZIP", "url": f"{DOWNLOAD_BASE}/Latvusmalli/"},
        ],
    },
]

_KEMERA_ENDPOINTS = [
    ("application_stand_06_16", "Kemera: taimikon varhaishoito (hakemus)"),
    ("application_stand_10_10", "Kemera: nuoren metsän hoito (hakemus)"),
    ("application_stand_10_30", "Kemera: pienpuun keräys (hakemus)"),
    ("application_stand_10_91", "Kemera: juurikäävän torjunta (hakemus)"),
    ("application_stand_11_30", "Kemera: suometsän hoito (hakemus)"),
    ("application_stand_11_50", "Kemera: metsätien tekeminen (hakemus)"),
    ("application_stand_11_90", "Kemera: ympäristötuki (hakemus)"),
    ("application_stand_11_91", "Kemera: luonnonhoitohanke (hakemus)"),
    ("application_stand_12_17", "Kemera: terveyslannoitus (hakemus)"),
    ("application_stand_13_50", "Kemera: metsätien perusparannus (hakemus)"),
    ("completiondeclaration_stand_06_16", "Kemera: taimikon varhaishoito (toteutus)"),
    ("completiondeclaration_stand_10_10", "Kemera: nuoren metsän hoito (toteutus)"),
    ("completiondeclaration_stand_10_30", "Kemera: pienpuun keräys (toteutus)"),
    ("completiondeclaration_stand_11_30", "Kemera: suometsän hoito (toteutus)"),
    ("completiondeclaration_stand_11_50", "Kemera: metsätien tekeminen (toteutus)"),
    ("completiondeclaration_stand_11_90", "Kemera: ympäristötuki (toteutus)"),
]

_KEMERA_DATASETS = [_kemera(ep, title) for ep, title in _KEMERA_ENDPOINTS]

_DOWNLOAD_ONLY: list[dict[str, Any]] = [
    {
        "id": "metsakeskus-korjuukelpoisuus",
        "title": "Korjuukelpoisuus",
        "notes_fi": "Korjuukelpoisuuskartat maakunnittain (~130 ZIP-tiedostoa)",
        "keywords_fi": ["metsä", "korjuukelpoisuus", "hakkuu"],
        "estimated_size_bytes": 10 * 1024**3,
        "resources": [
            {"format": "ZIP", "url": f"{DOWNLOAD_BASE}/Korjuukelpoisuus/"},
        ],
    },
]


class MetsakeskusHarvester(StaticHarvester):
    """Kerää Suomen metsäkeskuksen avoimet metsä- ja luontotiedot.

    Metsäkeskus ylläpitää Suomen kattavinta avointa metsävaratietokantaa.
    Data sisältää kuviotason metsävaratiedot, hiladatan, elinympäristöt,
    hakkuuilmoitukset, Kemera-tukitiedot ja latvusmallit.
    """

    name = "metsakeskus"
    description = "Suomen metsäkeskus — metsävara-, elinympäristö- ja hakkuutiedot"
    url = "https://avoin.metsakeskus.fi"
    org_id = "metsakeskus"
    org_name = "metsakeskus"
    org_title = "Suomen metsäkeskus"

    datasets_config = _MAIN_SERVICES + _CHM_YEARS + _KEMERA_DATASETS + _DOWNLOAD_ONLY
