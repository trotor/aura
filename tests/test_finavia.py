"""Testit Finavia-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters import HARVESTERS
from aura.harvesters.finavia import DOCS, FinaviaHarvester
from aura.harvesters.static import StaticHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> FinaviaHarvester:
    return FinaviaHarvester(conn=_memory_db())


class TestConfig:
    def test_inherits_static(self):
        assert issubclass(FinaviaHarvester, StaticHarvester)

    def test_registered(self):
        assert HARVESTERS["finavia"] is FinaviaHarvester

    def test_eight_datasets(self):
        assert len(FinaviaHarvester.datasets_config) == 8

    def test_covers_all_fourteen_files(self):
        """Kahdeksan datasettiä kattaa neljätoista Excel-tiedostoa.

        Kuukausiversio ja pitkä aikasarja ovat saman tilaston kaksi
        resurssia, eivät kahta datasettiä.
        """
        urls = {
            r["url"]
            for cfg in FinaviaHarvester.datasets_config
            for r in cfg["resources"]
            if r["format"] == "XLSX"
        }
        assert len(urls) == 14

    def test_every_dataset_links_to_source_page(self):
        for cfg in FinaviaHarvester.datasets_config:
            formats = {r["format"] for r in cfg["resources"]}
            assert "HTML" in formats, cfg["id"]

    def test_resource_ids_are_unique(self):
        ids = [
            r["id"]
            for cfg in FinaviaHarvester.datasets_config
            for r in cfg["resources"]
        ]
        assert len(ids) == len(set(ids))

    def test_files_come_from_finavia(self):
        for cfg in FinaviaHarvester.datasets_config:
            for r in cfg["resources"]:
                if r["format"] == "XLSX":
                    assert r["url"].startswith(DOCS), r["id"]


class TestLisenssi:
    """Finavia ei ilmoita käyttöehtoja, joten niitä ei saa väittää."""

    def test_no_license_is_claimed(self):
        for cfg in FinaviaHarvester.datasets_config:
            assert cfg["license_id"] == ""
            assert cfg["license_title"] == ""

    @pytest.mark.asyncio
    async def test_license_stays_empty_after_harvest(self):
        """_make_dataset() asettaisi oletuksena cc-by-4.0."""
        conn = _memory_db()
        h = FinaviaHarvester(conn=conn)
        await h.harvest()
        rows = conn.execute(
            "SELECT DISTINCT license_id FROM datasets WHERE source = 'finavia'"
        ).fetchall()
        assert [r[0] for r in rows] == [""]


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_writes_all_datasets(self):
        conn = _memory_db()
        h = FinaviaHarvester(conn=conn)
        count = await h.harvest()
        assert count == 8
        stored = conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'finavia'"
        ).fetchone()[0]
        assert stored == 8

    @pytest.mark.asyncio
    async def test_titles_carry_no_month(self):
        """Kuukausitiedoston otsikossa lukeva kuukausi vanhenee.

        Finavian sivulla linkin teksti on "…, heinäkuu 2026". Jos se
        kopioitaisiin otsikkoon, datasetti väittäisi ensi kuussa väärin.
        """
        kuukaudet = ("tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu",
                     "kesäkuu", "heinäkuu", "elokuu", "syyskuu", "lokakuu",
                     "marraskuu", "joulukuu")
        for cfg in FinaviaHarvester.datasets_config:
            title = cfg["title"].lower()
            assert not any(kk in title for kk in kuukaudet), cfg["id"]

    @pytest.mark.asyncio
    async def test_airport_keywords_present(self):
        """Otsikot puhuvat matkustajista ja rahdista, eivät lentoasemista.

        Ilman avainsanoja haku "lentoasema" ei osuisi puoleenkaan setistä.
        """
        conn = _memory_db()
        await FinaviaHarvester(conn=conn).harvest()
        rows = conn.execute(
            "SELECT keywords_fi FROM datasets WHERE source = 'finavia'"
        ).fetchall()
        for (keywords,) in rows:
            assert "lentoasema" in keywords
