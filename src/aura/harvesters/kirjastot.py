"""Harvester Kirjastot.fi:n kirjastotilastoille ja Kirkanta-rajapinnalle.

Ulkoinen arvio 27.9.2026: kysymykseen "kirjastojen lainaukset kunnittain"
ei löytynyt käyttökelpoista aineistoa. avoindata.fi:ssä on kyllä
"Suomen yleisten kirjastojen tilastot" (``5673499d-…``) ja "Suomen
kirjastojen yhteys- ja palvelutiedot" (``e191cec3-…``), mutta ensimmäisen
resurssi on HTML-sivu ja toisen formaatiton rajapinnan juuri
(``https://api.kirjastot.fi/``) — kumpikaan ei vie dataan asti.

Tämä harvesteri kerää samat kaksi aineistoa suoraan käytettävin resurssein:

1. **Yleisten kirjastojen vuositilastot**: yksi Excel-tiedosto per vuosi
   (1999–), luettuna sivulta ``tilastot.kirjastot.fi/yearlyreports.php``.
   Jos sivu ei vastaa, käytetään viimeisintä tunnettua luetteloa
   (``FALLBACK_REPORTS``, luettu 27.9.2026).
2. **Kirkanta API v4**: kirjastojen yhteys-, aukiolo- ja palvelutiedot
   JSONina (``api.kirjastot.fi/v4/library``). ``limit=1000`` palauttaa
   kaikki 978 kirjastoa yhdellä kutsulla (tarkistettu 27.9.2026).

**Lisenssi.** Molemmat CC BY 4.0: tilastosivun alatunniste ("Creative
Commons Nimeä 4.0 Kansainvälinen") ja Kirkanta-rajapinnan dokumentaatio
("Content License … CC BY 4.0"), tarkistettu 27.9.2026.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from aura.harvesters.static import StaticHarvester

logger = logging.getLogger(__name__)

YEARLY_REPORTS_URL = "https://tilastot.kirjastot.fi/yearlyreports.php"
STATS_URL = "https://tilastot.kirjastot.fi/"
KIRKANTA = "https://api.kirjastot.fi/v4"

#: Vuositilastojen Excel-tiedostot, jos vuositilastosivu ei vastaa keruussa.
#: Osoitteiden päätteet (``_0``, ``_1``) ovat julkaisijan korjausversioita,
#: joten niitä ei voi johtaa vuodesta — siksi luettelo eikä kaava.
FALLBACK_REPORTS: tuple[tuple[int, str], ...] = tuple(
    (year, f"https://www.kirjastot.fi/sites/default/files/content/{name}.xls")
    for year, name in (
        (2025, "yleistenkirjastojen_tilastot2025"),
        (2024, "yleistenkirjastojen_tilastot2024_1"),
        (2023, "yleistenkirjastojen_tilastot2023_0"),
        (2022, "yleistenkirjastojen_tilastot2022"),
        (2021, "yleistenkirjastojen_tilastot2021_0"),
        (2020, "yleistenkirjastojen_tilastot2020"),
        (2019, "yleistenkirjastojen_tilastot2019"),
        (2018, "yleistenkirjastojen_tilastot2018"),
        (2017, "yleistenkirjastojen_tilastot2017_0"),
        (2016, "yleistenkirjastojen_tilastot2016_1"),
        (2015, "yleistenkirjastojen_tilastot2015_1"),
    )
)

_REPORT_LINK = re.compile(
    r"<a\s+href=\"(?P<url>https?://[^\"]+\.xlsx?)\"\s*>\s*(?P<year>(?:19|20)\d{2})\s*</a>",
    re.I,
)

STATS_ID = "kirjastot-yleisten-kirjastojen-tilastot"
KIRKANTA_ID = "kirjastot-kirkanta-kirjastot"


def parse_yearly_reports(html: str) -> list[tuple[int, str]]:
    """Vuositilastosivun linkit: ``[(vuosi, xls-osoite), ...]`` uusin ensin."""
    found: dict[int, str] = {}
    for m in _REPORT_LINK.finditer(html):
        found.setdefault(int(m.group("year")), m.group("url"))
    return sorted(found.items(), reverse=True)


class KirjastotHarvester(StaticHarvester):
    """Yleisten kirjastojen vuositilastot ja Kirkanta-kirjastorekisteri."""

    name = "kirjastot"
    description = "Kirjastot.fi — yleisten kirjastojen tilastot ja kirjastojen yhteystiedot"
    url = STATS_URL
    org_id = "kirjastot-fi"
    org_name = "kirjastot-fi"
    org_title = "Kirjastot.fi"
    default_update_frequency = "vuosittain"

    datasets_config: list[dict[str, Any]] = [
        {
            "id": STATS_ID,
            "title": "Suomen yleisten kirjastojen tilastot (vuositilastot)",
            "notes_fi": (
                "Yleisten kirjastojen toimintatilastot kunnittain ja koko maa: "
                "lainaukset, fyysiset ja verkkokäynnit, kokoelmat ja hankinnat, "
                "aukiolo, henkilöstö sekä toimintamenot. Yksi Excel-tiedosto "
                "vuodessa. Kuntakohtainen tilastohaku ja visualisointi: "
                "tilastot.kirjastot.fi."
            ),
            "keywords_fi": [
                "kirjasto",
                "kirjastot",
                "yleiset kirjastot",
                "kirjastotilastot",
                "lainaukset",
                "lainat",
                "kirjastokäynnit",
                "kokoelmat",
                "kunnittain",
                "kulttuuri",
            ],
            # Vuositiedostot lisätään keruussa (_stats_config).
            "resources": [
                {
                    "id": f"{STATS_ID}-html",
                    "format": "HTML",
                    "url": STATS_URL,
                    "name_fi": "Tilastohaku kunnittain ja kirjastoittain (verkkosivu)",
                },
            ],
        },
        {
            "id": KIRKANTA_ID,
            "title": "Kirjastojen yhteys- ja palvelutiedot (Kirkanta API v4)",
            "notes_fi": (
                "Suomen kirjastojen (yleiset, tieteelliset, kirjastoautot) "
                "osoitteet, yhteystiedot, aukioloajat ja palvelut. JSON-vastaus: "
                "total ja items[]. Parametrit: limit (enintään 1000; kaikki 978 "
                "kirjastoa yhdellä kutsulla), city.name (kunnan nimi, esim. "
                "Tampere), type (municipal = yleinen kirjasto, mobile = "
                "kirjastoauto, university, polytechnic, special), consortium, "
                "service.name, with (lisäkentät, esim. schedules, services), "
                "lang (fi, sv, en). Aukioloajat: /v4/schedules."
            ),
            "keywords_fi": [
                "kirjasto",
                "kirjastot",
                "kirjastoauto",
                "aukioloajat",
                "yhteystiedot",
                "osoitteet",
                "palvelut",
                "Kirkanta",
            ],
            "update_frequency": "jatkuva",
            "resources": [
                {
                    "id": f"{KIRKANTA_ID}-json",
                    "format": "JSON",
                    "url": f"{KIRKANTA}/library?limit=1000",
                    "name_fi": "Kaikki kirjastot (JSON)",
                },
                {
                    "id": f"{KIRKANTA_ID}-json-tampere",
                    "format": "JSON",
                    "url": f"{KIRKANTA}/library?city.name=Tampere&type=municipal&limit=1000",
                    "name_fi": "Esimerkki: Tampereen yleiset kirjastot (JSON)",
                },
                {
                    "id": f"{KIRKANTA_ID}-doc",
                    "format": "HTML",
                    "url": "https://api.kirjastot.fi/",
                    "name_fi": "Rajapinnan dokumentaatio",
                },
            ],
        },
    ]

    async def harvest(self) -> int:
        reports = await self._yearly_reports()
        self.datasets_config = [
            self._stats_config(cfg, reports) if cfg["id"] == STATS_ID else cfg
            for cfg in type(self).datasets_config
        ]
        return await super().harvest()

    async def _yearly_reports(self) -> list[tuple[int, str]]:
        """Vuositiedostot sivulta; varaluettelo jos sivu ei vastaa tai on muuttunut."""
        try:
            async with self._make_client(timeout=30.0) as client:
                resp = await self._fetch(client, YEARLY_REPORTS_URL)
            reports = parse_yearly_reports(resp.text)
        except Exception as exc:  # noqa: BLE001 — varaluettelo riittää, keruu ei kaadu
            logger.warning("[%s] Vuositilastosivu ei vastannut (%s); varaluettelo", self.name, exc)
            return list(FALLBACK_REPORTS)
        if not reports:
            logger.warning(
                "[%s] Vuositilastosivulta ei löytynyt tiedostoja; varaluettelo", self.name
            )
            return list(FALLBACK_REPORTS)
        return reports

    @staticmethod
    def _stats_config(cfg: dict[str, Any], reports: list[tuple[int, str]]) -> dict[str, Any]:
        out = copy.deepcopy(cfg)
        files = [
            {
                "id": f"{STATS_ID}-{year}",
                "format": "XLS",
                "url": url,
                "name": f"Yleisten kirjastojen tilastot {year} (Excel)",
                "name_fi": f"Yleisten kirjastojen tilastot {year} (Excel)",
            }
            for year, url in reports
        ]
        out["resources"] = [*files, *out["resources"]]
        if reports:
            newest, oldest = reports[0][0], reports[-1][0]
            out["notes_fi"] = f"{cfg['notes_fi']} Vuodet {oldest}–{newest}."
        return out
