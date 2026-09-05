"""Yksi kaatuva lähde ei saa viedä koko keruuta.

Mitattu 5.9.2026: ``opendata.luke.fi`` oli lakannut olemasta CKAN-instanssi
ja vastasi 302:lla osoitteeseen ``etsin.fairdata.fi``. ``luke-opendata``
-harvesteri nosti käsittelemättömän ``HTTPStatusError``:in, ja koska
``harvest_sources`` kutsui ``harvester.harvest()`` ilman try/exceptiä,
**koko ajo päättyi siihen**.

Seuraus mitattuna: 41 harvesterista 38 aloitettiin ja 35 valmistui. Kolmea
ei yritetty lainkaan — ja yksi niistä oli **sotkanet, katalogin suurin
lähde 3 772 datasetillä**. Mikään ei kertonut siitä; ajo vain loppui.

Vikaluokka on tuttu tässä repossa mutta päinvastainen kuin aiemmin: moduulin
docstring varoittaa *hiljaisesta nollasta*, jossa epäonnistuminen näyttää
onnistumiselta. Tämä on sen peilikuva — **äänekäs epäonnistuminen joka
vaientaa kaiken jälkeensä**.

Vaatimus on siksi kaksiosainen: ajon on jatkuttava, **ja** epäonnistumisen
on jäätävä näkyviin. Pelkkä poikkeuksen nieleminen vaihtaisi vian toiseen.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from aura.database import init_db
from aura.harvesters.base import BaseHarvester
from aura.pipeline import harvest_sources


class _Toimiva(BaseHarvester):
    name = "toimiva"
    description = "Toimii aina"
    url = "https://toimiva.test"

    async def harvest(self) -> int:
        return 7


class _Kaatuva(BaseHarvester):
    name = "kaatuva"
    description = "Kaatuu aina"
    url = "https://kaatuva.test"

    async def harvest(self) -> int:
        raise RuntimeError("302 Found — lähde on muuttanut")


class _Jalkeen(BaseHarvester):
    name = "jalkeen"
    description = "Ajetaan kaatuvan jälkeen"
    url = "https://jalkeen.test"

    async def harvest(self) -> int:
        return 5


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c


@pytest.fixture
def harvesterit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kolme harvesteria järjestyksessä: toimiva, kaatuva, toimiva."""
    import aura.pipeline as p

    jarjestys: dict[str, Any] = {
        "toimiva": _Toimiva,
        "kaatuva": _Kaatuva,
        "jalkeen": _Jalkeen,
    }
    monkeypatch.setattr(p, "get_all_harvesters", lambda: jarjestys)
    monkeypatch.setattr(p, "get_harvester", lambda nimi: jarjestys[nimi])


class TestAjoJatkuu:
    @pytest.mark.anyio
    async def test_kaatuvan_jalkeiset_ajetaan(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        """Tämä on itse vika: sotkanet jäi ajamatta luken takia."""
        tulos = await harvest_sources(conn, source="all")
        assert "jalkeen" in tulos.counts, "kaatuvan jälkeiset jäivät ajamatta"
        assert tulos.counts["jalkeen"] == 5

    @pytest.mark.anyio
    async def test_kaatuvaa_edeltavat_sailyvat(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        tulos = await harvest_sources(conn, source="all")
        assert tulos.counts["toimiva"] == 7

    @pytest.mark.anyio
    async def test_kokonaismaara_ei_laske_kaatunutta(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        tulos = await harvest_sources(conn, source="all")
        assert tulos.total == 12


class TestEpaonnistuminenJaaNakyviin:
    @pytest.mark.anyio
    async def test_kaatunut_kirjataan_tulokseen(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        """Nieleminen vaihtaisi vian toiseen: ajo jatkuisi, mutta hiljaa."""
        tulos = await harvest_sources(conn, source="all")
        assert "kaatuva" in tulos.failures
        assert "302" in tulos.failures["kaatuva"]

    @pytest.mark.anyio
    async def test_kaatunut_ei_saa_nollaa_maaraksi(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        """Nolla tarkoittaisi "haettiin, ei löytynyt mitään".

        Kaatunut lähde on **mittaamaton**, ei tyhjä — sama erottelu kuin
        probe-vaiheen 429:ssä ja agenttivalmiudessa.
        """
        tulos = await harvest_sources(conn, source="all")
        assert "kaatuva" not in tulos.counts

    @pytest.mark.anyio
    async def test_sources_rivia_ei_paivitetä_kaatuneelle(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        """``last_harvested_at`` väittäisi ajon onnistuneen."""
        await harvest_sources(conn, source="all")
        rivi = conn.execute(
            "SELECT last_harvested_at FROM sources WHERE name = 'kaatuva'"
        ).fetchone()
        assert rivi is None or not rivi["last_harvested_at"]

    @pytest.mark.anyio
    async def test_yksittainen_lahde_nostaa_poikkeuksen_yha(
        self, conn: sqlite3.Connection, harvesterit: None
    ) -> None:
        """Kun lähde on nimetty, kaatuminen kuuluu näkyä heti.

        ``aura harvest kaatuva`` on eri tilanne kuin ``harvest all``: siinä
        ei ole mitään jonka puolesta jatkaa, ja hiljainen nollatulos
        näyttäisi onnistumiselta komentorivillä.
        """
        with pytest.raises(RuntimeError):
            await harvest_sources(conn, source="kaatuva")
