"""Testit GTK-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.gtk import ARCGIS_BASE, REST_BASE, GtkHarvester

#: GTK:n palvelimen juuri. Molemmat rajapintakannat ovat sen alla.
GTK_HOST = "https://gtkdata.gtk.fi/arcgis/"

#: Aihealueet joiden on oltava listalla. Tarkistettu 16.8.2026 hakemalla
#: katalogista GTK:n organisaationimellä: nämä eivät tule avoindata.fi:n
#: eivätkä Paikkatietoikkunan kautta, joten ne katoaisivat katalogista
#: kokonaan jos ne poistetaan täältä.
PAKOLLISET_AIHEET = {
    "gtk-kalliopera",
    "gtk-maapera",
    "gtk-kaavoitus",
    "gtk-merenpohja",
    "gtk-kaivokset",
}


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> GtkHarvester:
    return GtkHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_wfs_datasets_have_two_resources(self):
        """WFS-datasetissä on aina myös WMS-resurssi.

        Lukumäärää ei kiinnitetä: se kasvaa aina kun aihealue lisätään,
        eikä sen muuttuminen kerro mitään vikaa. Pari sen sijaan kertoo —
        pelkkä WFS ilman WMS:ää tarkoittaisi ettei aineistoa voi katsella.
        """
        h = _harvester()
        wfs_configs = [
            c for c in h.datasets_config if any(r["format"] == "WFS" for r in c["resources"])
        ]
        assert wfs_configs, "WFS-datasetit kadonneet"
        for cfg in wfs_configs:
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"WFS", "WMS"}, cfg["id"]

    def test_wms_only_datasets_have_one_resource(self):
        """WMS-only-dataseteissä on yksi resurssi."""
        h = _harvester()
        wms_only = [
            c for c in h.datasets_config if all(r["format"] == "WMS" for r in c["resources"])
        ]
        assert wms_only, "WMS-only-datasetit kadonneet"
        for cfg in wms_only:
            assert len(cfg["resources"]) == 1

    def test_urls_point_to_arcgis(self):
        """Resurssien URL:t osoittavat GTK:n ArcGIS-palvelimelle.

        Kaksi kantaa: ``/services`` tarjoaa OGC-rajapinnat, ``/rest`` ne
        aihealueet joilla ei ole WFS/WMS-paria.
        """
        h = _harvester()
        assert ARCGIS_BASE.startswith(GTK_HOST)
        assert REST_BASE.startswith(GTK_HOST)
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["url"].startswith(GTK_HOST), (cfg["id"], r["url"])

    def test_puuttuvat_aihealueet_ovat_mukana(self):
        """Aihealueet joita ei saa mistään muusta lähteestä.

        Kallioperä ja maaperä tulevat myös avoindata.fi:n kautta, mutta
        kaavoitus, merenpohja ja kaivokset eivät tule mistään — jos ne
        poistetaan täältä, ne katoavat katalogista kokonaan.
        """
        h = _harvester()
        ids = {c["id"] for c in h.datasets_config}
        assert PAKOLLISET_AIHEET <= ids, PAKOLLISET_AIHEET - ids

    def test_all_ids_have_prefix(self):
        """Kaikkien datasettien id:t alkavat 'gtk-' -etuliitteellä."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("gtk-")


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa kaikkien konfiguroitujen datasettien määrän.

        Vertailu konfiguraatioon eikä vakioon: jos jokin datasetti putoaa
        matkalla pois — esimerkiksi id-törmäyksen takia — luku jää alle.
        """
        h = _harvester()
        count = await h.harvest()
        assert count == len(h.datasets_config)

    @pytest.mark.asyncio
    async def test_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'gtk'"
        ).fetchall()
        for ds in datasets:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()[0]
            assert ds["num_resources"] == actual
