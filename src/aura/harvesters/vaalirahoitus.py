"""Harvester vaalirahoitusvalvonta.fi:n vaali- ja puoluerahoitusdatalle."""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

BASE = "https://www.vaalirahoitusvalvonta.fi/fi/index"
VR_BASE = f"{BASE}/vaalirahoitus/haetietoavaalirahoitusilmoituksista/tutkitietoaineistoja"
PR_BASE = f"{BASE}/puoluerahoitus/haetietoailmoituksista/tietoaineistot"

# --- Vaalirahoituksen CSV-tiedostotyypit ---

_CSV_TYPES = [
    ("E_EI", "Ennakkoilmoitukset"),
    ("RAHOITUSRIVIT_E_EI", "Ennakkoilmoitusten rahoitusrivit"),
    ("E_VI", "Vaalirahoitusilmoitukset"),
    ("RAHOITUSRIVIT_E_VI", "Vaalirahoitusilmoitusten rahoitusrivit"),
]

# --- Vaalit joista CSV-lataukset saatavilla ---

_ELECTIONS: list[dict[str, Any]] = [
    {
        "slug": "presidentinvaali2018",
        "title": "Presidentinvaali 2018",
        "year": 2018,
        "keywords": ["presidentinvaali", "2018"],
    },
    {
        "slug": "eduskuntavaalit2019",
        "title": "Eduskuntavaalit 2019",
        "year": 2019,
        "keywords": ["eduskuntavaalit", "2019"],
    },
    {
        "slug": "europarlamenttivaalit2019",
        "title": "Europarlamenttivaalit 2019",
        "year": 2019,
        "keywords": ["europarlamenttivaalit", "EU-vaalit", "2019"],
    },
    {
        "slug": "kuntavaalit2021",
        "title": "Kuntavaalit 2021",
        "year": 2021,
        "keywords": ["kuntavaalit", "2021"],
    },
    {
        "slug": "aluevaalit2022",
        "title": "Aluevaalit 2022",
        "year": 2022,
        "keywords": ["aluevaalit", "hyvinvointialue", "2022"],
    },
    {
        "slug": "eduskuntavaalit2023",
        "title": "Eduskuntavaalit 2023",
        "year": 2023,
        "keywords": ["eduskuntavaalit", "2023"],
    },
    {
        "slug": "presidentinvaali2024",
        "title": "Presidentinvaali 2024",
        "year": 2024,
        "keywords": ["presidentinvaali", "2024"],
    },
    {
        "slug": "europarlamenttivaalit2024",
        "title": "Europarlamenttivaalit 2024",
        "year": 2024,
        "keywords": ["europarlamenttivaalit", "EU-vaalit", "2024"],
    },
    {
        "slug": "aluevaalit2025",
        "title": "Aluevaalit 2025",
        "year": 2025,
        "keywords": ["aluevaalit", "hyvinvointialue", "2025"],
    },
    {
        "slug": "kuntavaalit2025",
        "title": "Kuntavaalit 2025",
        "year": 2025,
        "keywords": ["kuntavaalit", "2025"],
    },
]

# --- Puoluerahoituksen vuosidata (2010–2026) ---

_PARTY_YEARS = range(2010, 2027)


def _election_dataset(election: dict[str, Any]) -> dict[str, Any]:
    """Luo yksittäisen vaalin rahoitusdatasetin konfiguraatio."""
    slug = election["slug"]
    title = election["title"]
    resources = [
        {
            "id": f"vaalirahoitus-{slug}-{prefix.lower().replace('_', '-')}",
            "name": f"{title} — {label}",
            "name_fi": f"{title} — {label}",
            "format": "CSV",
            "url": f"{VR_BASE}/{slug}/{prefix}_{slug}.csv",
        }
        for prefix, label in _CSV_TYPES
    ]
    return {
        "id": f"vaalirahoitus-{slug}",
        "title": f"Vaalirahoitus: {title}",
        "notes_fi": (
            f"{title} — ehdokkaiden vaalirahoitusilmoitukset ja rahoitusrivit. "
            "CSV-aineisto sisältää kampanjakulut, rahoituslähteet ja yksittäiset "
            "tukijatiedot. Lähde: vaalirahoitusvalvonta.fi (VTV)."
        ),
        "keywords_fi": [
            "vaalirahoitus", "kampanjarahoitus", "VTV",
            *election["keywords"],
        ],
        "resources": resources,
    }


def _party_year_dataset(year: int) -> dict[str, Any]:
    """Luo puoluerahoituksen vuosidatasetin konfiguraatio."""
    resources: list[dict[str, Any]] = [
        {
            "id": f"vaalirahoitus-puoluerahoitus-{year}",
            "name": f"Puoluerahoitusilmoitukset {year}",
            "name_fi": f"Puoluerahoitusilmoitukset {year}",
            "format": "CSV",
            "url": f"{PR_BASE}/{year}_ajantasaiset_ilmoitukset.csv",
        },
    ]
    # Vuodesta 2025 lähtien myös erillinen lainatiedosto
    if year >= 2025:
        resources.append({
            "id": f"vaalirahoitus-puoluerahoitus-lainat-{year}",
            "name": f"Puoluerahoitusilmoitukset {year} — lainat",
            "name_fi": f"Puoluerahoitusilmoitukset {year} — lainat",
            "format": "CSV",
            "url": f"{PR_BASE}/{year}_ajantasaiset_ilmoitukset_lainat.csv",
        })
    return {
        "id": f"vaalirahoitus-puoluerahoitus-{year}",
        "title": f"Puoluerahoitus {year}",
        "notes_fi": (
            f"Puolueiden ja puolueyhdistysten rahoitusilmoitukset vuodelta {year}. "
            "CSV-aineisto sisältää yritys- ja henkilötukijat, tuensaajat "
            "ja tukimäärät. Lähde: vaalirahoitusvalvonta.fi (VTV)."
        ),
        "keywords_fi": [
            "puoluerahoitus", "puoluetuki", "VTV", str(year),
        ],
        "resources": resources,
    }


class VaalirahoitusHarvester(StaticHarvester):
    """Kerää vaalirahoitusvalvonta.fi:n vaali- ja puoluerahoitusdatan.

    Valtiontalouden tarkastusvirasto (VTV) ylläpitää
    vaalirahoitusvalvonta.fi-palvelua, jossa on CSV-muotoiset
    vaalirahoitus- ja puoluerahoitusilmoitukset.

    Vaalirahoitus: ehdokkaiden kampanjakulut ja rahoituslähteet (2018–).
    Puoluerahoitus: puolueiden vuosittaiset rahoitusilmoitukset (2010–).
    """

    name = "vaalirahoitus"
    description = (
        "Vaalirahoitusvalvonta — vaali- ja puoluerahoitusilmoitukset (VTV)"
    )
    url = "https://www.vaalirahoitusvalvonta.fi"
    default_update_frequency = "vuosittain"
    org_id = "vtv"
    org_name = "vtv"
    org_title = "Valtiontalouden tarkastusvirasto"

    datasets_config = [
        _election_dataset(e) for e in _ELECTIONS
    ] + [
        _party_year_dataset(y) for y in _PARTY_YEARS
    ]
