"""Harvester Finap/NAP-liikennepalvelukatalogille.

Finap (finap.fi) on Traficomin ylläpitämä kansallinen yhteyspiste (NAP),
johon liikennepalvelujen tarjoajat ilmoittavat palvelutietonsa
(reitit, aikataulut, hinnat, saavutettavuus). Valtioneuvoston
asetus 643/2017 velvoittaa tietojen ilmoittamiseen.

Finap-rajapinnat vaativat kirjautumisen, joten tämä harvester
kerää palvelukategorioiden metatiedot staattisesti.
"""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

# NAP-palvelukategoriat ja niiden kuvaukset
NAP_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "finap-henkiloliikenne",
        "title": "NAP — Henkilöliikennepalvelut",
        "title_fi": "NAP — Henkilöliikennepalvelut",
        "notes_fi": (
            "Kansallisen yhteyspisteen (NAP) henkilöliikennepalvelut: "
            "taksit, linja-autot, lautat ja muu tilausliikenne. "
            "Palveluntarjoajat ilmoittavat reitit, aikataulut, hinnat "
            "ja saavutettavuustiedot GTFS-, NeTEx- tai JSON-formaatissa."
        ),
        "keywords_fi": [
            "joukkoliikenne", "henkilöliikenne", "taksi",
            "linja-auto", "lautta", "nap",
        ],
        "resources": [
            {
                "id": "finap-henkiloliikenne-portal",
                "name": "Finap — henkilöliikennepalvelut",
                "name_fi": "Finap — henkilöliikennepalvelut",
                "format": "HTML",
                "url": "https://finap.fi/#/services",
            },
        ],
    },
    {
        "id": "finap-terminaalit",
        "title": "NAP — Terminaalit ja asemat",
        "title_fi": "NAP — Terminaalit ja asemat",
        "notes_fi": (
            "Lentokenttien, satamien, rautatieasemien ja "
            "linja-autoasemien tiedot: sijainnit, palvelut, "
            "saavutettavuus ja aukioloajat."
        ),
        "keywords_fi": [
            "terminaalit", "asemat", "lentokenttä",
            "satama", "rautatieasema", "nap",
        ],
        "resources": [
            {
                "id": "finap-terminaalit-portal",
                "name": "Finap — terminaalit",
                "name_fi": "Finap — terminaalit ja asemat",
                "format": "HTML",
                "url": "https://finap.fi/#/services",
            },
        ],
    },
    {
        "id": "finap-pysakointi",
        "title": "NAP — Pysäköintipalvelut",
        "title_fi": "NAP — Pysäköintipalvelut",
        "notes_fi": (
            "Kaupallisten pysäköintilaitosten ja -alueiden tiedot: "
            "sijainnit, hinnat, kapasiteetti, reaaliaikaiset "
            "paikkamäärät ja sähkölatausmahdollisuudet."
        ),
        "keywords_fi": [
            "pysäköinti", "parkkihallit", "sähkölataus", "nap",
        ],
        "resources": [
            {
                "id": "finap-pysakointi-portal",
                "name": "Finap — pysäköintipalvelut",
                "name_fi": "Finap — pysäköintipalvelut",
                "format": "HTML",
                "url": "https://finap.fi/#/services",
            },
        ],
    },
    {
        "id": "finap-vuokraus-jakaminen",
        "title": "NAP — Vuokraus- ja yhteiskäyttöpalvelut",
        "title_fi": "NAP — Vuokraus- ja yhteiskäyttöpalvelut",
        "notes_fi": (
            "Autojen, polkupyörien, sähköpotkulautojen ja muiden "
            "ajoneuvojen vuokraus- ja yhteiskäyttöpalvelut. "
            "Sisältää tiedot saatavuudesta, hinnoista ja asemista."
        ),
        "keywords_fi": [
            "yhteiskäyttö", "vuokraus", "kaupunkipyörät",
            "sähköpotkulaudat", "nap",
        ],
        "resources": [
            {
                "id": "finap-vuokraus-portal",
                "name": "Finap — vuokraus- ja yhteiskäyttöpalvelut",
                "name_fi": "Finap — vuokraus- ja yhteiskäyttöpalvelut",
                "format": "HTML",
                "url": "https://finap.fi/#/services",
            },
        ],
    },
    {
        "id": "finap-valityspalvelut",
        "title": "NAP — Välityspalvelut (MaaS)",
        "title_fi": "NAP — Välityspalvelut (MaaS)",
        "notes_fi": (
            "Liikkumisen välityspalvelut (MaaS): matkaketjujen "
            "yhdistäminen, lipunmyynti ja multimodaalinen reititys. "
            "Sisältää myös matkahuollon ja muiden välittäjien rajapinnat."
        ),
        "keywords_fi": [
            "maas", "välityspalvelu", "matkaketju",
            "multimodaalinen", "nap",
        ],
        "resources": [
            {
                "id": "finap-valityspalvelut-portal",
                "name": "Finap — välityspalvelut",
                "name_fi": "Finap — välityspalvelut (MaaS)",
                "format": "HTML",
                "url": "https://finap.fi/#/services",
            },
        ],
    },
]


class FinapHarvester(StaticHarvester):
    """Kerää Finap/NAP-liikennepalvelukatalogin metatiedot.

    Finap on Traficomin kansallinen yhteyspiste (National Access Point),
    johon liikennepalvelujen tarjoajat ilmoittavat olennaistiedot
    palveluistaan. Palvelukategoriat:

    - Henkilöliikenne (taksit, bussit, lautat)
    - Terminaalit ja asemat
    - Pysäköinti
    - Vuokraus ja yhteiskäyttö
    - Välityspalvelut (MaaS)
    """

    name = "finap"
    description = "Finap/NAP — kansallinen liikennepalvelukatalogi"
    url = "https://finap.fi"

    org_id = "traficom"
    org_name = "traficom"
    org_title = "Liikenne- ja viestintävirasto Traficom"
    default_update_frequency = "jatkuva"

    datasets_config = NAP_CATEGORIES

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "static",
            "query_protocol": "portal",
            "api_base_url": "https://finap.fi",
        })
        return config
