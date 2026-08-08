"""Harvester eduskunnan avoimelle datalle."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

API = "https://avoindata.eduskunta.fi/api/v1/tables"

# Sivutuksen oletuskoko rajapinnan normaalikäytössä (dokumentaatioarvo —
# resurssien URL:t eivät sisällä sivutusparametreja).
PAGE_SIZE = 100

# Koon mittauksessa haetaan pienin mahdollinen sivu. Kysymys on vain
# "onko tällä sivulla rivejä", joten rivien sisältöä ei tarvita.
#
# Tämä ei ole mikro-optimointi. VaskiDatan rivit ovat kokonaisia
# XML-asiakirjoja, ja mitattuna 2026-08-08:
#     perPage=100 → 3,4 MB ja 5,6 s per pyyntö
#     perPage=1   → 0,019 MB ja 0,1 s per pyyntö
# Täysillä sivuilla bisektointi latasi satoja megatavuja asiakirjoja
# pelkkään laskemiseen ja koko ajo kesti yli puoli tuntia.
PROBE_SIZE = 1

# Bisektoinnin yläraja riveinä.
#
# Speksi oletti VaskiDatan (~348 000 riviä) suurimmaksi tauluksi. Se oli
# väärin: liitostauluissa rivit kertautuvat, ja mitattuna 2026-08-08
# SaliDBAanestysAsiakirjalla on rivi vielä sivulla 5 000 000.
#
# Rajaa EI silti nosteta kattamaan niitä. Yksi koetin maksaa 2–7 s, joten
# kymmenkertainen raja maksaisi ~7 lisäpyyntöä per taulu ja koko ajon
# venyminen puoleen tuntiin — pelkän tarkkuuden vuoksi luvussa jota
# katalogi ei tarvitse tarkkana.
#
# Ratkaisu on rehellisyys eikä tarkkuus: kattoon osunut mittaus kirjataan
# muodossa "yli N riviä" (ks. harvest). Väärä tasaluku olisi ollut vika,
# alarajaksi merkitty ei ole.
MAX_ROWS = 1_000_000

# Kuratoidut aineistot. Aineisto vastaa käyttötarkoitusta, ei API:n
# taulurakennetta: 19 taulusta 16 on sisällöllisiä, ja ne ryhmitellään
# seitsemäksi aineistoksi.
#
# Pois jätetyt: HetekaData ja SaliDBMessageLog ovat aidosti tyhjiä
# (varmennettu hakemalla sivu 0), PrimaryKeys (23 riviä) on teknistä
# metatietoa.
DATASETS: list[dict[str, Any]] = [
    {
        "id": "eduskunta-kansanedustajat",
        "title": "Kansanedustajat",
        "tables": ["MemberOfParliament", "SeatingOfParliament"],
        "notes_fi": (
            "Kansanedustajien perustiedot: nimi, eduskuntaryhmä, "
            "ministeriys sekä laaja XML-muotoinen henkilökuvaus "
            "(elämäkerta, toimikaudet, valiokuntajäsenyydet). Mukana myös "
            "istuntosalin istumajärjestys."
        ),
        "keywords_fi": [
            "kansanedustajat",
            "eduskunta",
            "edustajat",
            "eduskuntaryhmät",
            "ministerit",
            "politiikka",
        ],
    },
    {
        "id": "eduskunta-aanestykset",
        "title": "Täysistuntojen äänestykset",
        "tables": [
            "SaliDBAanestys",
            "SaliDBAanestysJakauma",
            "SaliDBAanestysAsiakirja",
            "SaliDBAanestysKieli",
        ],
        "notes_fi": (
            "Täysistuntojen äänestykset vuodesta 1996 alkaen: äänestyksen "
            "otsikko, käsittelyvaihe, tulos (jaa/ei/tyhjiä/poissa) sekä "
            "linkki pöytäkirjaan ja valtiopäiväasiaan. Äänijakaumat "
            "eduskuntaryhmittäin omana tauluna."
        ),
        "keywords_fi": [
            "äänestykset",
            "täysistunto",
            "eduskunta",
            "äänestystulokset",
            "politiikka",
            "lainsäädäntö",
        ],
    },
    {
        "id": "eduskunta-aanestykset-edustajittain",
        "title": "Äänestykset edustajittain",
        "tables": ["SaliDBAanestysEdustaja"],
        "notes_fi": (
            "Yksittäisen kansanedustajan ääni jokaisessa täysistunnon "
            "äänestyksessä: edustajan nimi, henkilönumero, "
            "eduskuntaryhmä ja annettu ääni. Yhdistettävissä "
            "äänestysaineistoon AanestysId-kentällä."
        ),
        "keywords_fi": [
            "äänestykset",
            "kansanedustajat",
            "äänestyskäyttäytyminen",
            "eduskunta",
            "politiikka",
        ],
    },
    {
        "id": "eduskunta-puheenvuorot",
        "title": "Täysistuntojen puheenvuorot",
        "tables": ["SaliDBPuheenvuoro"],
        "notes_fi": (
            "Täysistuntojen puheenvuorot: puhuja, eduskuntaryhmä, "
            "ministeriys, puheenvuoron tyyppi ja ajankohta sekä "
            "XML-muotoinen puheen sisältö."
        ),
        "keywords_fi": [
            "puheenvuorot",
            "täysistunto",
            "eduskunta",
            "puheet",
            "kansanedustajat",
            "politiikka",
        ],
    },
    {
        "id": "eduskunta-istunnot",
        "title": "Täysistunnot ja käsittelykohdat",
        "tables": [
            "SaliDBIstunto",
            "SaliDBKohta",
            "SaliDBKohtaAanestys",
            "SaliDBKohtaAsiakirja",
            "SaliDBTiedote",
        ],
        "notes_fi": (
            "Täysistuntojen rakenne: istunnot, käsittelykohdat ja niiden "
            "kytkennät äänestyksiin ja asiakirjoihin. Mukana myös "
            "täysistuntotiedotteet."
        ),
        "keywords_fi": [
            "täysistunto",
            "istunnot",
            "eduskunta",
            "esityslista",
            "valtiopäivät",
            "politiikka",
        ],
    },
    {
        "id": "eduskunta-asiakirjat",
        "title": "Valtiopäiväasiakirjat",
        "tables": ["VaskiData"],
        "notes_fi": (
            "Kaikki valtiopäiväasiakirjat XML-muodossa: hallituksen "
            "esitykset, valiokuntamietinnöt, kirjalliset kysymykset, "
            "lakialoitteet ja pöytäkirjat. Jokaisella asiakirjalla on "
            "eduskuntatunnus (esim. 'HE 1/2023 vp')."
        ),
        "keywords_fi": [
            "valtiopäiväasiakirjat",
            "hallituksen esitykset",
            "kirjalliset kysymykset",
            "lakialoitteet",
            "valiokunnat",
            "eduskunta",
            "lainsäädäntö",
        ],
    },
    {
        "id": "eduskunta-liitteet",
        "title": "Asiakirjojen liitteet",
        "tables": ["Attachment", "AttachmentGroup"],
        "notes_fi": (
            "Valtiopäiväasiakirjoihin liittyvät liitetiedostot ja niiden "
            "ryhmittely. Kytkeytyy asiakirja-aineistoon "
            "AttachmentGroupId-kentällä."
        ),
        "keywords_fi": [
            "liitteet",
            "valtiopäiväasiakirjat",
            "eduskunta",
        ],
    },
]


class EduskuntaHarvester(BaseHarvester):
    """Kerää eduskunnan avoimen datan rajapinnan aineistot.

    Eduskunta julkaisee täysistuntojen äänestykset, puheenvuorot,
    kansanedustajatiedot ja kaikki valtiopäiväasiakirjat sivutettuna
    JSON-rajapintana. Rajapinta ei vaadi avainta.

    Rivimäärät mitataan bisektoimalla sivutusta — katso ``_measure_rows``.
    """

    name = "eduskunta"
    description = "Eduskunnan avoin data — äänestykset, puheenvuorot, asiakirjat"
    url = "https://avoindata.eduskunta.fi"

    DATASETS = DATASETS

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update(
            {
                "harvester_type": "api",
                "query_protocol": "rest",
                "api_base_url": API,
            }
        )
        return config

    async def _page_rows(
        self,
        client: httpx.AsyncClient,
        table: str,
        page: int,
        per_page: int = PROBE_SIZE,
    ) -> int:
        """Palauta rivimäärä yhdeltä sivulta."""
        url = f"{API}/{table}/rows?perPage={per_page}&page={page}"
        response = await self._fetch(client, url)
        data = response.json()
        rows = data.get("rowData") or []
        return len(rows)

    async def _measure_rows(self, client: httpx.AsyncClient, table: str) -> int:
        """Mittaa taulun rivimäärä bisektoimalla sivunumeroa.

        Koetin käyttää ``PROBE_SIZE``-kokoista sivua, jolloin sivunumero
        vastaa rivin indeksiä ja rivimäärä on suurin löytynyt indeksi + 1.

        ÄLÄ korvaa tätä /api/v1/tables/counts -kutsulla. Se on yksi pyyntö
        parinkymmenen sijaan, mutta se ei palauta taulun rivimäärää: se
        väitti SaliDBAanestys-taulun kooksi 96 (todellinen ~43 500) ja
        SeatingOfParliament-taulua tyhjäksi (todellisuudessa rivejä on).
        Todennäköisesti se kertoo viimeksi tuoduista riveistä.
        """
        if await self._page_rows(client, table, 0) == 0:
            return 0

        # Etsi suurin rivi-indeksi jolla on rivi. Invariantti: lo:lla on
        # rivejä, hi:llä ei.
        lo = 0
        hi = MAX_ROWS
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if await self._page_rows(client, table, mid) > 0:
                lo = mid
            else:
                hi = mid

        return lo + 1

    async def harvest(self) -> int:
        count = 0
        async with self._make_client() as client:
            for cfg in self.DATASETS:
                sizes: dict[str, int] = {}
                for table in cfg["tables"]:
                    try:
                        sizes[table] = await self._measure_rows(client, table)
                    except (httpx.HTTPError, ValueError, KeyError) as exc:
                        # Yksittäisen taulun mittaus ei saa kaataa koko ajoa,
                        # mutta se ei myöskään saa kadota hiljaisesti.
                        logger.warning(
                            "[%s] Taulun %s koon mittaus epäonnistui: %s",
                            self.name,
                            table,
                            exc,
                        )

                resources = [
                    Resource(
                        id=f"{cfg['id']}-{table.lower()}",
                        name=f"{table} (JSON-rajapinta)",
                        name_fi=f"{table} — JSON-rajapinta",
                        format="API",
                        url=f"{API}/{table}/rows",
                    )
                    for table in cfg["tables"]
                ]

                # Kattoon osunut mittaus on alaraja, ei mittaus. Se on
                # sanottava ääneen: uskottavan näköinen tasaluku olisi
                # juuri se hiljainen väärä tulos jota vastaan tässä
                # projektissa on rakennettu check_count_regression.
                parts = []
                for t, n in sizes.items():
                    if n >= MAX_ROWS:
                        logger.warning(
                            "[%s] Taulun %s koko osui bisektoinnin kattoon "
                            "(%d) — todellinen määrä on suurempi",
                            self.name,
                            t,
                            MAX_ROWS,
                        )
                        parts.append(f"{t}: yli {n:,} riviä".replace(",", " "))
                    else:
                        parts.append(f"{t}: {n:,} riviä".replace(",", " "))
                measured = ", ".join(parts)
                notes = cfg["notes_fi"]
                if measured:
                    notes = f"{notes} Mitatut rivimäärät: {measured}."

                dataset = self._make_dataset(
                    id=cfg["id"],
                    name=cfg["id"],
                    title=cfg["title"],
                    title_fi=cfg["title"],
                    notes_fi=notes,
                    organization_id="eduskunta",
                    organization_name="eduskunta",
                    organization_title="Eduskunta",
                    keywords_fi=cfg["keywords_fi"],
                    update_frequency="päivittäin",
                    num_resources=len(resources),
                    resources=resources,
                )
                upsert_dataset(self.conn, dataset)
                count += 1

        self.conn.commit()
        logger.info("[%s] Harvest valmis: %d datasettiä", self.name, count)
        return count
