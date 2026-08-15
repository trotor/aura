"""Harvester POHTIVAlle — poliittisten ohjelmien tietovaranto."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

BASE = "https://www.fsd.tuni.fi/pohtiva"
LIST_URL = f"{BASE}/ohjelmalistat"

# Puoluekoodit listasivulta. Listasivu linkittää myös itseensä
# ("Takaisin"), joten pelkkä /ohjelmalistat ilman koodia suodatetaan pois
# vaatimalla vähintään yksi merkki koodille.
_PARTY_RE = re.compile(
    r'href="https://www\.fsd\.tuni\.fi/pohtiva/ohjelmalistat/([A-Za-zÅÄÖåäö0-9]+)"'
)

# Ohjelmarivi puoluesivun taulukosta. Sarakkeet: Otsikko (linkki), Puolue,
# Vuosi, Tyyppi, Kieli.
#
# Sivun HTML on epämuodostunutta — <tr>-elementtejä ei suljeta — joten
# regex kohdistuu solujen sarjaan eikä <tr>-lohkoon. Validoitu oikeaa
# VIHR-sivua vasten 2026-07-30: 169 osumaa, mikä täsmää sivun omaan
# ilmoitukseen "Yhteensä 169 ohjelmaa".
_PROGRAMME_RE = re.compile(
    r'<a href="[^"]*ohjelmalistat/(?P<party>[^/"]+)/(?P<pid>\d+)"\s*>\s*'
    r"(?P<title>.*?)\s*</a>\s*</td>\s*"
    r"<td>(?P<party_name>[^<]*)</td>\s*"
    r"<td>(?P<year>[^<]*)</td>\s*"
    r"<td>(?P<ptype>[^<]*)</td>\s*"
    r"<td>(?P<lang>[^<]*)</td>",
    re.S,
)


# Puolueiden vakiintuneet lyhenteet, joita POHTIVAn oma koodi ei anna.
#
# **Vain mitatut puutteet, ei kattava aliaslista.** POHTIVAn koodi ja
# puolueen nimi menevät avainsanoihin sellaisenaan, ja useimmille puolueille
# se riittää: "Kokoomus" löytää 100/100, "vasemmistoliitto" 97/97. Tähän on
# kirjattu ne tapaukset joissa mittaus näytti vajaan tuloksen:
#
#     RKP                  9/167   koodi on SFP, ei RKP
#     sosialidemokraatit   3/196   avainsanana on adjektiivi
#                                  "Sosialidemokraattinen", ei substantiivi
#
# Puhekieliset nimet (demarit, kepu, persut) antavat nollan, mutta niitä ei
# lisätä: ne eivät ole puolueiden omia nimiä, ja niiden ylläpito olisi
# päättymätön. Käyttäjän puhekieli kuuluu kyselyn laajennukseen, ei
# katalogin metatietoon.
PARTY_ALIASES: dict[str, list[str]] = {
    "SFP": ["RKP"],
    "SDP": ["sosialidemokraatit"],
}


def parse_party_codes(page: str) -> list[str]:
    """Poimi puoluekoodit listasivulta, järjestettynä ja uniikkeina."""
    return sorted(set(_PARTY_RE.findall(page)))


def parse_programmes(page: str) -> list[dict[str, str]]:
    """Poimi ohjelmat puoluesivun taulukosta."""
    programmes = []
    for match in _PROGRAMME_RE.finditer(page):
        row = {k: html.unescape(v).strip() for k, v in match.groupdict().items()}
        programmes.append(row)
    return programmes


class PohtivaHarvester(BaseHarvester):
    """Kerää POHTIVAn puolueohjelmien metatiedot.

    POHTIVA on Yhteiskuntatieteellisen tietoarkiston ylläpitämä
    poliittisten ohjelmien tietovaranto: 1 583 ohjelmaa vuosilta
    1880–2025, 95 puolueelta.

    Rajapintaa ei ole, joten metatiedot luetaan puoluesivujen
    HTML-taulukoista. Koko aineiston metatiedot saa 96 pyynnöllä —
    yksittäisiä ohjelmasivuja ei haeta.

    **Ohjelmatekstejä ei kopioida.** Aura tallentaa metatiedot ja linkin.
    """

    name = "pohtiva"
    description = "POHTIVA — poliittisten ohjelmien tietovaranto (Tietoarkisto)"
    url = LIST_URL
    # POHTIVA on pieni yliopistopalvelu, ei tuotantorajapinta. Väljempi
    # viive kuin oletus, koska peräkkäisiä pyyntöjä on lähes sata.
    request_delay = 0.5

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update(
            {
                "harvester_type": "scrape",
                "query_protocol": "html",
            }
        )
        return config

    async def harvest(self) -> int:
        count = 0
        async with self._make_client() as client:
            response = await self._fetch(client, LIST_URL)
            codes = parse_party_codes(response.text)
            logger.info("[%s] Löytyi %d puoluekoodia", self.name, len(codes))

            for code in codes:
                try:
                    page = await self._fetch(client, f"{LIST_URL}/{code}")
                except httpx.HTTPError as exc:
                    # Yksittäisen puolueen epäonnistuminen ei saa kaataa
                    # koko ajoa, mutta se ei saa myöskään kadota.
                    logger.warning(
                        "[%s] Puolueen %s sivu epäonnistui: %s",
                        self.name,
                        code,
                        exc,
                    )
                    continue

                for prog in parse_programmes(page.text):
                    self._store(prog)
                    count += 1

        self.conn.commit()
        logger.info("[%s] Harvest valmis: %d ohjelmaa", self.name, count)
        return count

    def _store(self, prog: dict[str, str]) -> None:
        """Tallenna yksi ohjelma datasettinä."""
        party = prog["party"]
        pid = prog["pid"]
        ds_id = f"pohtiva-{party.lower()}-{pid}"
        url = f"{LIST_URL}/{party}/{pid}"

        keywords = ["puolueohjelma", "politiikka", party]
        keywords.extend(PARTY_ALIASES.get(party.upper(), []))
        if prog.get("party_name"):
            keywords.append(prog["party_name"])
        if prog.get("ptype"):
            keywords.append(prog["ptype"])
        if prog.get("year"):
            keywords.append(prog["year"])

        year = prog.get("year", "")
        suffix = f" ({year})" if year else ""
        notes = (
            f"{prog['party_name']}: {prog['title']}{suffix}. "
            "Puolueohjelman metatiedot POHTIVAsta. Ohjelman teksti "
            "luettavissa linkin takaa. Tekijänoikeus on puolueella; "
            "aineistoa ylläpitää Yhteiskuntatieteellinen tietoarkisto."
        )

        dataset = self._make_dataset(
            id=ds_id,
            name=ds_id,
            title=prog["title"],
            title_fi=prog["title"],
            notes_fi=notes,
            organization_id="fsd",
            organization_name="fsd",
            organization_title="Yhteiskuntatieteellinen tietoarkisto",
            keywords_fi=keywords,
            # POHTIVA ei ilmoita uudelleenkäytön ehtoja, vain viittausohjeen.
            # _make_dataset() asettaisi oletuksena cc-by-4.0, mikä olisi
            # väite jota lähde ei tue.
            license_id="",
            license_title="",
            update_frequency="satunnaisesti",
            num_resources=1,
            resources=[
                Resource(
                    id=f"{ds_id}-html",
                    name=prog["title"],
                    name_fi=prog["title"],
                    format="HTML",
                    url=url,
                )
            ],
        )
        upsert_dataset(self.conn, dataset)
