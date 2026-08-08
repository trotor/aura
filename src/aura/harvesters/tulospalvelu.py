"""Harvester oikeusministeriön vaalitulospalvelulle."""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

BASE = "https://tulospalvelu.vaalit.fi"

# Tulostasot: ehdokkaat, puolueet ja valitsijayhdistykset, alueet
_LEVELS = [
    ("ehd", "ehdokaskohtaiset tulokset"),
    ("puo", "puolueiden ja valitsijayhdistysten tulokset"),
    ("alu", "aluekohtaiset tulokset"),
]

_FORMATS = ["csv", "xml"]

# Sivuston oma käyttöehto sanatarkasti. Ei CC BY 4.0: se olisi väite jota
# lähde ei tue. _make_dataset() asettaisi oletuksena cc-by-4.0, joten
# oletus ohitetaan tässä.
LICENSE_ID = "other-open"
LICENSE_TITLE = "Tiedot ovat julkisia ja vapaasti käytettävissä"

# Vain vaalit joilla on varmennettu lataus. Etusivu listaa 15 vaalia,
# mutta EKV-2011:llä on sivu ilman CSV:tä ja presidentinvaaleilla (TPV)
# ei ole latauksia lainkaan. Varmennettu 2026-07-29 HTTP-vastauksista.
_ELECTIONS: list[dict[str, Any]] = [
    {
        "code": "EKV-2019",
        "title": "Eduskuntavaalit 2019",
        "keywords": ["eduskuntavaalit", "2019"],
    },
    {
        "code": "EKV-2023",
        "title": "Eduskuntavaalit 2023",
        "keywords": ["eduskuntavaalit", "2023"],
    },
    {
        "code": "KV-2012",
        "title": "Kuntavaalit 2012",
        "keywords": ["kuntavaalit", "2012"],
    },
    {
        "code": "KV-2017",
        "title": "Kuntavaalit 2017",
        "keywords": ["kuntavaalit", "2017"],
    },
    {
        "code": "KV-2021",
        "title": "Kuntavaalit 2021",
        "keywords": ["kuntavaalit", "2021"],
    },
    {
        "code": "KV-2025",
        "title": "Kuntavaalit 2025",
        "keywords": ["kuntavaalit", "2025"],
    },
    {
        "code": "AV-2022",
        "title": "Aluevaalit 2022",
        "keywords": ["aluevaalit", "hyvinvointialue", "2022"],
    },
    {
        "code": "AV-2025",
        "title": "Aluevaalit 2025",
        "keywords": ["aluevaalit", "hyvinvointialue", "2025"],
    },
    {
        "code": "EPV-2014",
        "title": "Europarlamenttivaalit 2014",
        "keywords": ["europarlamenttivaalit", "EU-vaalit", "2014"],
    },
    {
        "code": "EPV-2019",
        "title": "Europarlamenttivaalit 2019",
        "keywords": ["europarlamenttivaalit", "EU-vaalit", "2019"],
    },
    {
        "code": "EPV-2024",
        "title": "Europarlamenttivaalit 2024",
        "keywords": ["europarlamenttivaalit", "EU-vaalit", "2024"],
    },
]


def _election_dataset(election: dict[str, Any]) -> dict[str, Any]:
    """Luo yhden vaalin tulosdatasetin konfiguraatio."""
    code = election["code"]
    low = code.lower()
    title = election["title"]

    # Tiedostot ovat vaalihakemiston juuressa. fi/-alihakemisto sisältää
    # vain HTML-sivut ja palauttaa latauksille 404.
    resources = [
        {
            "id": f"tulospalvelu-{low}-{level}-{fmt}",
            "name": f"{title} — {label} ({fmt.upper()})",
            "name_fi": f"{title} — {label} ({fmt.upper()})",
            "format": "ZIP",
            "url": f"{BASE}/{code}/{low}_{level}_maa.{fmt}.zip",
        }
        for level, label in _LEVELS
        for fmt in _FORMATS
    ]

    return {
        "id": f"tulospalvelu-{low}",
        "title": f"{title} — viralliset tulokset",
        "notes_fi": (
            f"{title}: oikeusministeriön viralliset vaalitulokset "
            "ehdokas-, puolue- ja aluetasolla. Aluetason tulokset ulottuvat "
            "äänestysaluetasolle asti. Saatavilla sekä CSV- että "
            "XML-muodossa zipattuna. Skeemakuvaukset ja kenttäselitteet "
            "löytyvät tulospalvelun ohjesivulta. "
            "Lähde: tulospalvelu.vaalit.fi (oikeusministeriö)."
        ),
        "keywords_fi": [
            "vaalitulokset",
            "vaalit",
            "äänestys",
            "ehdokkaat",
            "puolueet",
            "oikeusministeriö",
            *election["keywords"],
        ],
        "license_id": LICENSE_ID,
        "license_title": LICENSE_TITLE,
        "resources": resources,
    }


class TulospalveluHarvester(StaticHarvester):
    """Kerää oikeusministeriön vaalitulospalvelun tulostiedostot.

    Tulospalvelu julkaisee jokaisen vaalin viralliset tulokset kolmella
    tasolla (ehdokkaat, puolueet, alueet) sekä CSV- että XML-muodossa.
    Aineisto täydentää Tilastokeskuksen vaalitilastoja alkuperäisillä
    tulostiedostoilla.

    Käyttöehto sivustolla: "Tiedot ovat julkisia ja vapaasti käytettävissä."
    """

    name = "tulospalvelu"
    description = "Oikeusministeriön vaalitulospalvelu — viralliset vaalitulokset"
    url = "https://tulospalvelu.vaalit.fi"
    default_update_frequency = "vaaleittain"
    org_id = "oikeusministerio"
    org_name = "oikeusministerio"
    org_title = "Oikeusministeriö"

    datasets_config = [_election_dataset(e) for e in _ELECTIONS]
