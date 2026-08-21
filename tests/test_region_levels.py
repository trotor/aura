"""Testit aluetason päättelylle ja sen vaikutukselle hakuun.

Aluehaku suodatti vain ``geographical_coverage``-kentällä, joka kertoo
mitä aluetta aineisto koskee. Se ei sano mitään siitä onko koko maan
kattavassa aineistossa kunta omana rivinään. Mitattuna 16.8.2026
``search_by_region("Kuopio", "väestö")`` palautti tyhjän, vaikka Kuopion
väkiluku on sekä StatFinissä että Sotkanetissa.

Korjaus tuo mukaan aineistot joissa kunta on dimensioarvo — mutta ne on
pidettävä erillään. Kuntatasoinen valtakunnallinen taulu ei koske tätä
kuntaa; se sisältää sen rivinä, eikä kattavuudesta ole varmuutta ilman
datan hakemista. Siksi testit kiinnittävät myös sen, ettei
``area_profile``:n otsikkoluku niele niitä: ilman erottelua Kuopion
yhdeksän datasettiä näyttäisi viideltäsadalta, vaikka yksikään uusi
rivi ei koske Kuopiota.
"""

import json
import sqlite3

import pytest

import aura.server as _server
from aura.database import init_db
from aura.region_levels import (
    FIELD,
    KUNTA,
    MIN_REGION_VALUES,
    SOURCE_TYPE,
    mark,
    pxweb_has_municipality_dimension,
    refresh,
    sotkanet_municipality_ids,
)


def _dims(name: str, count: int) -> str:
    return json.dumps([{"code": "x", "name": name, "value_count": count, "examples": []}])


class TestPxwebTunnistus:
    def test_alue_dimensio_kuntamaaralla_tunnistetaan(self) -> None:
        assert pxweb_has_municipality_dimension(_dims("Alue", 310))

    def test_maakuntajako_ei_kelpaa(self) -> None:
        """19 maakuntaa ei ole kuntajako."""
        assert not pxweb_has_municipality_dimension(_dims("Alue", 19))

    def test_seutukuntajako_ei_kelpaa(self) -> None:
        """69 seutukuntaa jäisi väärin kuntajaoksi liian matalalla rajalla."""
        assert not pxweb_has_municipality_dimension(_dims("Alue", 69))

    def test_raja_on_inklusiivinen(self) -> None:
        assert pxweb_has_municipality_dimension(_dims("Alue", MIN_REGION_VALUES))
        assert not pxweb_has_municipality_dimension(_dims("Alue", MIN_REGION_VALUES - 1))

    def test_muu_dimensio_ei_kelpaa(self) -> None:
        """Suuri arvomäärä yksin ei riitä — nimen on viitattava alueeseen."""
        assert not pxweb_has_municipality_dimension(_dims("Ikäryhmä", 300))

    @pytest.mark.parametrize("nimi", ["Alue", "Kunta", "Region", "Municipality", "Kommun"])
    def test_aluenimen_muunnelmat(self, nimi: str) -> None:
        assert pxweb_has_municipality_dimension(_dims(nimi, 300))

    @pytest.mark.parametrize("roska", ["", "ei json", "{}", "null", "[1,2,3]"])
    def test_rikkinainen_arvo_ei_kaada(self, roska: str) -> None:
        assert not pxweb_has_municipality_dimension(roska)


class TestSotkanetTunnistus:
    def test_kunta_taso_poimitaan(self) -> None:
        data = [
            {"id": 1, "classifications": {"region": {"values": ["Kunta", "Maakunta"]}}},
            {"id": 2, "classifications": {"region": {"values": ["Maakunta"]}}},
        ]
        assert sotkanet_municipality_ids(data) == {1}

    def test_puuttuvat_kentat_eivat_kaada(self) -> None:
        data = [{"id": 1}, {"classifications": {}}, {"id": 2, "classifications": None}]
        assert sotkanet_municipality_ids(data) == set()


@pytest.fixture
def conn(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO ref_metadata (name, record_count, version, populated_at)"
        " VALUES ('municipalities', 1, '1', '2026-01-01 00:00:00')"
    )
    c.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv) VALUES ('297','Kuopio','Kuopio')"
    )
    # Kuopiota koskeva aineisto
    c.execute(
        "INSERT INTO datasets (id, name, title, source, geographical_coverage)"
        " VALUES ('kuopio-1','kuopio-1','Kuopion kantakartta','kunnat','[\"Kuopio\"]')"
    )
    # Valtakunnallinen taulu jossa kunta on dimensiona
    c.execute(
        "INSERT INTO datasets (id, name, title, source, geographical_coverage)"
        " VALUES ('sotkanet-1','sotkanet-1','Väkiluku','sotkanet','[\"Suomi\"]')"
    )
    # Valtakunnallinen taulu ilman kuntajakoa — ei saa löytyä
    c.execute(
        "INSERT INTO datasets (id, name, title, source, geographical_coverage)"
        " VALUES ('statfin-1','statfin-1','Bruttokansantuote','statfin','[\"Suomi\"]')"
    )
    c.commit()
    monkeypatch.setattr(_server, "_get_conn", lambda ctx=None: c)
    return c


class TestMerkinta:
    def test_uudelleenajo_ei_kerry(self, conn: sqlite3.Connection) -> None:
        """Taulussa ei ole uniikkirajoitetta; ilman poistoa rivit kertyisivät."""
        mark(conn, ["sotkanet-1"])
        mark(conn, ["sotkanet-1"])
        n = conn.execute("SELECT COUNT(*) FROM enrichments WHERE field = ?", (FIELD,)).fetchone()[0]
        assert n == 1

    def test_kasin_tehtyyn_ei_kosketa(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO enrichments (id, dataset_id, field, value, source_type)"
            " VALUES ('k1','statfin-1',?,?,'mcp_session')",
            (FIELD, KUNTA),
        )
        conn.commit()
        mark(conn, ["sotkanet-1"])
        jaljella = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE field = ? AND source_type = 'mcp_session'",
            (FIELD,),
        ).fetchone()[0]
        assert jaljella == 1

    def test_tyhja_lista_puhdistaa(self, conn: sqlite3.Connection) -> None:
        mark(conn, ["sotkanet-1"])
        assert mark(conn, []) == 0
        n = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE field = ? AND source_type = ?",
            (FIELD, SOURCE_TYPE),
        ).fetchone()[0]
        assert n == 0

    def test_refresh_yhdistaa_molemmat_lahteet(self, conn: sqlite3.Connection) -> None:
        """Kaksi erillistä mark()-kutsua pyyhkisi toisensa."""
        conn.execute(
            "INSERT INTO enrichments (id, dataset_id, field, value, source_type)"
            " VALUES ('e1','statfin-1','data_fields',?,'harvester')",
            (_dims("Alue", 300),),
        )
        conn.commit()
        indicators = [{"id": 1, "classifications": {"region": {"values": ["Kunta"]}}}]
        assert refresh(conn, indicators) == 2

        merkityt = {
            r[0]
            for r in conn.execute(
                "SELECT dataset_id FROM enrichments WHERE field = ?", (FIELD,)
            ).fetchall()
        }
        assert merkityt == {"statfin-1", "sotkanet-1"}


class TestAluehaku:
    @pytest.mark.asyncio
    async def test_kuntatasoinen_loytyy(self, conn: sqlite3.Connection) -> None:
        """Tämä haku palautti tyhjän ennen korjausta."""
        from aura.tools.search import search_by_region

        mark(conn, ["sotkanet-1"])
        tulos = await search_by_region("Kuopio", "väkiluku")
        assert "Väkiluku" in tulos

    @pytest.mark.asyncio
    async def test_merkitsematon_ei_loydy(self, conn: sqlite3.Connection) -> None:
        """Ilman merkintää valtakunnallinen taulu pysyy poissa."""
        from aura.tools.search import search_by_region

        tulos = await search_by_region("Kuopio", "bruttokansantuote")
        assert "Bruttokansantuote" not in tulos

    @pytest.mark.asyncio
    async def test_tulos_erottaa_ryhmat(self, conn: sqlite3.Connection) -> None:
        """Ilman erottelua lukija luulisi aineiston koskevan Kuopiota."""
        from aura.tools.search import search_by_region

        mark(conn, ["sotkanet-1"])
        tulos = await search_by_region("Kuopio", "väkiluku")
        assert "kunta on dimensiona" in tulos
        assert "eivät koske erityisesti" in tulos

    @pytest.mark.asyncio
    async def test_aluetta_koskevat_ensin(self, conn: sqlite3.Connection) -> None:
        from aura.tools.search import search_by_region

        mark(conn, ["sotkanet-1"])
        tulos = await search_by_region("Kuopio")
        assert tulos.index("Kuopion kantakartta") < tulos.index("Väkiluku")


class TestAlueprofiili:
    def test_otsikkoluku_ei_niele_valtakunnallisia(self, conn: sqlite3.Connection) -> None:
        """Otsikkoluku kuvaa aluetta, ei kuntatason rivien saatavuutta."""
        from aura.tools.area import area_profile

        mark(conn, ["sotkanet-1"])
        tulos = area_profile("Kuopio")
        assert "**1 datasettiä**" in tulos

    def test_puuteväite_ei_lupaa_liikaa(self, conn: sqlite3.Connection) -> None:
        """Vanha sanamuoto 'Ei avointa väestö-dataa' ei pitänyt paikkaansa."""
        from aura.tools.area import area_profile

        mark(conn, ["sotkanet-1"])
        tulos = area_profile("Kuopio")
        assert "Ei avointa" not in tulos
        if "Puutteet" in tulos:
            assert "alueelle rajatuissa aineistoissa" in tulos
