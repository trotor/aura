"""Testit Fluent Outdoors -harvesterille.

Painopiste on siinä mitä katalogi *lupaa*. Harvesterissa oli 23 kunnalle
JSON-rajapinnan osoite joka vastasi HTTP 404:llä. Vika ei näkynyt
mitenkään: staattinen harvesteri ei kutsu osoitteitaan, joten lupaus
koneluettavasta lähteestä petti vasta käyttäjän kädessä.
"""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.fluentoutdoors import (
    FLUENT_MUNICIPALITIES,
    VERIFIED_API_PATHS,
    FluentOutdoorsHarvester,
)


def _harvester() -> FluentOutdoorsHarvester:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return FluentOutdoorsHarvester(conn=conn)


class TestRajapintalupaus:
    """JSON-resurssi vain kunnille joiden rajapinta on todennettu."""

    def test_json_vain_todennetuille(self):
        h = _harvester()
        for cfg in h.datasets_config:
            subdomain = cfg["id"].removeprefix("fluentoutdoors-")
            json_res = [r for r in cfg["resources"] if r["format"] == "JSON"]
            if subdomain in VERIFIED_API_PATHS:
                assert json_res, f"{subdomain}: todennettu rajapinta puuttuu"
            else:
                assert not json_res, f"{subdomain}: luvataan JSON-rajapinta jota ei ole todennettu"

    def test_todennettu_polku_on_urlissa(self):
        """Osoite rakennetaan todennetusta polusta, ei karttanäkymän polusta."""
        h = _harvester()
        for subdomain, api_path in VERIFIED_API_PATHS.items():
            cfg = next(c for c in h.datasets_config if c["id"].endswith(subdomain))
            urls = [r["url"] for r in cfg["resources"] if r["format"] == "JSON"]
            assert urls
            for u in urls:
                assert f"/{api_path}/v1/snowplow" in u, u

    def test_kuvaus_ei_lupaa_rajapintaa_jota_ei_ole(self):
        h = _harvester()
        for cfg in h.datasets_config:
            subdomain = cfg["id"].removeprefix("fluentoutdoors-")
            lupaa = "saatavilla JSON-rajapinnasta" in cfg["notes_fi"]
            assert lupaa == (subdomain in VERIFIED_API_PATHS), subdomain


class TestRakenne:
    def test_kaikilla_on_karttanakyma(self):
        """Karttanäkymä on ainoa resurssi jonka jokainen kunta tarjoaa."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert any(r["format"] == "HTML" for r in cfg["resources"]), cfg["id"]

    def test_jokaisella_kunnalla_on_datasetti(self):
        h = _harvester()
        assert len(h.datasets_config) == len(FLUENT_MUNICIPALITIES)

    def test_kuvauksen_kuntamaara_vastaa_listaa(self):
        """Kuvauksessa luvattu kuntamäärä ei saa jäädä jälkeen listasta."""
        assert str(len(FLUENT_MUNICIPALITIES)) in FluentOutdoorsHarvester.description


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_tallentaa_kaikki(self):
        h = _harvester()
        count = await h.harvest()
        assert count == len(h.datasets_config)

    @pytest.mark.asyncio
    async def test_num_resources_vastaa_todellista(self):
        h = _harvester()
        await h.harvest()
        for ds in h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'fluentoutdoors'"
        ).fetchall():
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?", (ds["id"],)
            ).fetchone()[0]
            assert ds["num_resources"] == actual
