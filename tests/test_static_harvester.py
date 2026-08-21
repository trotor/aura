"""Testit StaticHarvesterin resurssitunnusten yksikäsitteisyydelle.

``save_dataset()`` kirjoittaa resurssit ``ON CONFLICT(id) DO UPDATE``
-lauseella. Jos kaksi saman datasetin resurssia saa saman tunnuksen,
jälkimmäinen kirjoittaa edellisen päälle eikä mikään huomauta siitä:
``num_resources`` kertoo neljä, kannassa on kaksi.

Oletustunnus oli ``{datasetti}-{formaatti}``, joten mikä tahansa datasetti
jolla oli kaksi saman formaatin resurssia menetti puolet niistä. Vika oli
voimassa koko katalogissa ja hävitti 48 resurssia.
"""

import sqlite3
from collections import Counter

import pytest

from aura.database import init_db
from aura.harvesters import HARVESTERS
from aura.harvesters.static import StaticHarvester


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _datasets(h: StaticHarvester) -> list:
    """Kaikki datasetit jotka harvesteri tuottaisi.

    ``harvest()`` kirjoittaa suoraan kantaan, joten konfiguraation
    laajennus (``years``) on toistettava tässä.
    """
    return [d for cfg in h.datasets_config for d in h._expand(cfg)]


def _static_harvesters() -> list[tuple[str, type]]:
    return [
        (name, cls)
        for name, cls in sorted(HARVESTERS.items())
        if isinstance(cls, type) and issubclass(cls, StaticHarvester)
    ]


class TestTunnustenYksikasitteisyys:
    """Jokainen staattinen harvesteri erikseen, jotta vika paikantuu."""

    @pytest.mark.parametrize("name,cls", _static_harvesters())
    def test_resurssitunnukset_ovat_yksikasitteiset(self, name: str, cls: type) -> None:
        h = cls(conn=_conn())
        for dataset in _datasets(h):
            ids = [r.id for r in dataset.resources]
            duplikaatit = [i for i, n in Counter(ids).items() if n > 1]
            assert not duplikaatit, f"{name}/{dataset.id}: toistuvat tunnukset {duplikaatit}"

    @pytest.mark.parametrize("name,cls", _static_harvesters())
    def test_datasettitunnukset_ovat_yksikasitteiset(self, name: str, cls: type) -> None:
        """Sama vika datasettitasolla veisi kokonaisia datasettejä."""
        h = cls(conn=_conn())
        ids = [d.id for d in _datasets(h)]
        duplikaatit = [i for i, n in Counter(ids).items() if n > 1]
        assert not duplikaatit, f"{name}: toistuvat datasettitunnukset {duplikaatit}"


class TestTallennus:
    """Lupauksen ja tallennetun on täsmättävä kannassa asti."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name,cls", _static_harvesters())
    async def test_num_resources_vastaa_tallennettua(self, name: str, cls: type) -> None:
        conn = _conn()
        h = cls(conn=conn)
        await h.harvest()
        vajaat = conn.execute(
            """
            SELECT d.id, d.num_resources, COUNT(r.id) AS todellinen
            FROM datasets d LEFT JOIN resources r ON r.dataset_id = d.id
            GROUP BY d.id HAVING d.num_resources <> COUNT(r.id)
            """
        ).fetchall()
        assert not vajaat, [
            f"{row['id']}: luvattu {row['num_resources']}, tallennettu {row['todellinen']}"
            for row in vajaat
        ]


class TestOletustunnus:
    """Tunnusmuoto on osa kannan sisältöä — se ei saa muuttua vahingossa."""

    def test_ensimmainen_formaatti_sailyttaa_entisen_tunnuksen(self) -> None:
        """Muuten koko katalogin resurssitunnukset vaihtuisivat kerralla."""

        class Testi(StaticHarvester):
            name = "testi"
            description = "testi"
            url = "https://example.invalid"
            org_id = org_name = "testi"
            org_title = "Testi"
            datasets_config = [
                {
                    "id": "testi-1",
                    "title": "Testi",
                    "resources": [
                        {"format": "JSON", "url": "https://example.invalid/a"},
                        {"format": "JSON", "url": "https://example.invalid/b"},
                        {"format": "JSON", "url": "https://example.invalid/c"},
                        {"format": "HTML", "url": "https://example.invalid/d"},
                    ],
                }
            ]

        dataset = _datasets(Testi(conn=_conn()))[0]
        assert [r.id for r in dataset.resources] == [
            "testi-1-json",
            "testi-1-json-2",
            "testi-1-json-3",
            "testi-1-html",
        ]

    def test_annettu_tunnus_voittaa_oletuksen(self) -> None:
        class Testi(StaticHarvester):
            name = "testi"
            description = "testi"
            url = "https://example.invalid"
            org_id = org_name = "testi"
            org_title = "Testi"
            datasets_config = [
                {
                    "id": "testi-1",
                    "title": "Testi",
                    "resources": [
                        {"id": "oma", "format": "JSON", "url": "https://example.invalid/a"},
                        {"format": "JSON", "url": "https://example.invalid/b"},
                    ],
                }
            ]

        dataset = _datasets(Testi(conn=_conn()))[0]
        assert [r.id for r in dataset.resources] == ["oma", "testi-1-json-2"]
