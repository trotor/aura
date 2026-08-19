"""Testit hakusuodattimien julkiselle sopimukselle.

``build_dataset_filters`` on ainoa paikka jossa suodatinehdot määritellään.
Sen varassa on myös hakua täydentäviä kerroksia, jotka hakevat ehdokkaita ohi
FTS-haun ja rajaavat samoilla ehdoilla. Jos jokin suodatin katoaa täältä, se
katoaa niistä kaikista yhtä aikaa — eikä mikään huomauta, koska tulos näyttää
edelleen suodatetulta.

Siksi jokainen suodatin testataan erikseen ja lopputulos ajetaan oikeaa
kantaa vasten: pelkkä ehtojen laskeminen ei kertoisi rajaavatko ne mitään.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from aura.database import build_dataset_filters, init_db


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    rows = [
        ("a", "avoindata.fi", "Kuntaliitto", "open", "CSV", '["Kuopio"]'),
        ("b", "statfin", "Tilastokeskus", "restricted", "PXWEB", '["Suomi"]'),
    ]
    for ds_id, source, org, access, fmt, coverage in rows:
        c.execute(
            "INSERT INTO datasets (id, name, title, source, organization_title,"
            " access_level, geographical_coverage) VALUES (?,?,?,?,?,?,?)",
            (ds_id, ds_id, ds_id, source, org, access, coverage),
        )
        c.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES (?,?,'r',?,'https://example.test/r')",
            (f"{ds_id}-r", ds_id, fmt),
        )
    c.commit()
    return c


def _matching(conn: sqlite3.Connection, **filters: Any) -> list[str]:
    """Aja ehdot kantaa vasten ja palauta läpi menneet tunnisteet."""
    conditions, params = build_dataset_filters(**filters)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(f"SELECT d.id FROM datasets d{where} ORDER BY d.id", params)
    return [str(r[0]) for r in rows]


class TestJokainenSuodatinRajaa:
    @pytest.mark.parametrize(
        ("filters", "odotus"),
        [
            ({"source": "statfin"}, ["b"]),
            ({"organization": "Kuntaliitto"}, ["a"]),
            ({"organization": "kunta"}, ["a"]),  # osa nimestä riittää
            ({"access_level": "open"}, ["a"]),
            ({"fmt": "PXWEB"}, ["b"]),
            ({"fmt": "pxweb"}, ["b"]),  # kirjainkoko ei ratkaise
        ],
    )
    def test_suodatin_pudottaa_muut(
        self, conn: sqlite3.Connection, filters: dict[str, Any], odotus: list[str]
    ) -> None:
        assert _matching(conn, **filters) == odotus

    def test_ilman_suodattimia_kaikki_lapi(self, conn: sqlite3.Connection) -> None:
        assert _matching(conn) == ["a", "b"]

    def test_suodattimet_yhdistyvat_and_lla(self, conn: sqlite3.Connection) -> None:
        assert _matching(conn, source="statfin", access_level="open") == []


class TestAluerajausOnPehmea:
    """Aluerajaus laajentaa tarkoituksella — se on dokumentoitava, ei korjattava.

    Toinen haara päästää läpi jokaisen aineiston jolla on region_level-
    enrichment, riippumatta pyydetystä alueesta: koko maan taulu jossa kunta
    on dimensioarvo kattaa myös Kuopion. Testi kiinnittää sen tahalliseksi,
    jotta muutos siihen näkyy diffissä eikä vain tuloksissa.
    """

    def test_oma_kattavuus_rajaa(self, conn: sqlite3.Connection) -> None:
        assert _matching(conn, region_names=["Kuopio"]) == ["a"]

    def test_region_level_ohittaa_alueen(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type)"
            " VALUES ('b', 'region_level', 'kunta', 'testi')"
        )
        conn.commit()
        assert _matching(conn, region_names=["Kuopio"]) == ["a", "b"]

    def test_tuntematon_alue_ei_tyhjenna_tulosta(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type)"
            " VALUES ('b', 'region_level', 'kunta', 'testi')"
        )
        conn.commit()
        assert _matching(conn, region_names=["Ei-mikään-kunta"]) == ["b"]
