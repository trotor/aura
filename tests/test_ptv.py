"""Testit Palvelutietovaranto-harvesterille.

Rivin arvo on siinä että osoite on **kyselykelpoinen**. Katalogissa oli
PTV:stä ennestään yksi rivi jonka ainoa resurssi oli Swagger-sivu — se ei
kerro agentille mitään siitä miten dataa haetaan, ja juuri se ero on
tämän harvesterin koko tarkoitus.

Siksi testit vartioivat kahta asiaa. Osoitteiden on osoitettava
rajapintaan eikä dokumentaatioon, ja kuvauksen on kannettava käyttöohje.
Ilman ohjetta rivi olisi taas kirjanmerkki, vain hienommalla nimellä.
"""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters import HARVESTERS
from aura.harvesters.ptv import API, LUOKITUKSET, OHJE, PtvHarvester

#: Päätepisteet jotka todennettiin HTTP:llä 18.8.2026. Lista on tässä
#: jotta keksitty polku ei pääse konfiguraatioon huomaamatta: kuollut
#: osoite katalogissa on pahempi kuin puuttuva rivi.
TODENNETUT = {
    "/Organization",
    "/Organization/area/Municipality/code/297",
    "/Service",
    "/Service/list/area/Municipality/code/297",
    "/ServiceChannel",
    "/ServiceChannel/area/Municipality/code/297",
    "/ServiceChannel/type/ServiceLocation",
    "/ServiceCollection",
    "/GeneralDescription",
}

#: Päätepisteet jotka mitattiin ja hylättiin — nämä eivät saa palata.
#: ``/Service/active`` ja ``/ServiceChannel/active`` vastaavat 401:llä,
#: ``/Service/serviceClass`` 404:llä.
HYLATYT = {"/Service/active", "/ServiceChannel/active", "/Service/serviceClass"}


def _harvester() -> PtvHarvester:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return PtvHarvester(conn=conn)


def _api_urls(h: PtvHarvester) -> list[str]:
    return [
        r["url"] for cfg in h.datasets_config for r in cfg["resources"] if r["format"] == "JSON"
    ]


class TestPaatepisteet:
    def test_kaikki_polut_on_todennettu(self) -> None:
        h = _harvester()
        for url in _api_urls(h):
            assert url.startswith(API), url
            polku = url[len(API) :]
            assert polku in TODENNETUT, f"todentamaton polku: {polku}"

    def test_hylatyt_eivat_ole_mukana(self) -> None:
        h = _harvester()
        polut = {u[len(API) :] for u in _api_urls(h)}
        assert not (polut & HYLATYT)

    def test_jokaisella_on_rajapintaresurssi(self) -> None:
        """Pelkkä HTML-linkki tekisi rivistä taas kirjanmerkin."""
        h = _harvester()
        for cfg in h.datasets_config:
            formats = {r["format"] for r in cfg["resources"]}
            assert "JSON" in formats, cfg["id"]


class TestKayttoohje:
    def test_ohje_on_jokaisessa_kuvauksessa(self) -> None:
        h = _harvester()
        for cfg in h.datasets_config:
            assert OHJE in cfg["notes_fi"], cfg["id"]

    def test_ohje_kertoo_sivutuksen_ja_kuntarajauksen(self) -> None:
        """Nämä kaksi ovat ne joita ilman rajapintaa ei osaa käyttää."""
        assert "?page=" in OHJE
        assert "Municipality/code" in OHJE

    def test_ohje_ei_lupaa_api_avainta_vaadittavaksi(self) -> None:
        """Rajapinta on auki; väärä tieto estäisi käytön turhaan."""
        assert "ei vaadi API-avainta" in OHJE


class TestLuokitukset:
    def test_viittaa_koodistoriveihin_eika_toista_niita(self) -> None:
        """PTV:n luokitukset ovat jo katalogissa koodistot-harvesterin kautta.

        Jos ne tuotaisiin tässä uudestaan, sama sanasto olisi kahdessa
        paikassa eri tunnuksilla — juuri se päällekkäisyys jota katalogi
        kärsii muualla.
        """
        h = _harvester()
        viittaavat = [c for c in h.datasets_config if LUOKITUKSET in c["notes_fi"]]
        assert viittaavat, "yksikään rivi ei viittaa luokituksiin"
        for tunnus in ("koodistot-ptv-ptvserclass2", "koodistot-ptv-ptvkohderyhmat"):
            assert tunnus in LUOKITUKSET

    def test_ei_luo_omia_luokitusdatasettejä(self) -> None:
        h = _harvester()
        ids = {c["id"] for c in h.datasets_config}
        assert not any("luokit" in i or "koodist" in i for i in ids)


class TestKuntarajaus:
    def test_kuntarajatut_kayttavat_kuntakoodia(self) -> None:
        """Kuntakoodi on se mitä ref_municipalities tarjoaa."""
        h = _harvester()
        kunta_urlit = [u for u in _api_urls(h) if "Municipality" in u]
        assert kunta_urlit
        for u in kunta_urlit:
            assert u.endswith("/297"), u

    def test_yhteystietokanavilla_on_kuntarajaus(self) -> None:
        """Yhteystiedot ovat alueellinen kysymys — ilman rajausta rivi on 72 000 kanavaa."""
        h = _harvester()
        cfg = next(c for c in h.datasets_config if c["id"] == "ptv-palvelukanavat")
        assert any("Municipality" in r["url"] for r in cfg["resources"])


class TestRekisterointi:
    def test_loytyy_harvesterirekisterista(self) -> None:
        assert HARVESTERS.get("ptv") is PtvHarvester


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_tallentaa_kaikki(self) -> None:
        h = _harvester()
        count = await h.harvest()
        assert count == len(h.datasets_config)

    @pytest.mark.asyncio
    async def test_num_resources_vastaa_todellista(self) -> None:
        h = _harvester()
        await h.harvest()
        for ds in h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'ptv'"
        ).fetchall():
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?", (ds["id"],)
            ).fetchone()[0]
            assert ds["num_resources"] == actual
