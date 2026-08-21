"""Testit Sotkanetin aluetunnussillalle.

Sotkanet ei tunne kuntakoodia: Kuopio on kuntakoodiltaan 297 mutta
Sotkanetissa alue 161. Ilman siltaa Sotkanetin indikaattorit ovat
kuntatasolla saavuttamattomia, koska kysyjän on ensin haettava
``/rest/1.1/regions`` itse ja etsittävä kunta nimellä.

Toinen vartioitava asia on ohjeen totuudenmukaisuus. Sotkanetin
data-rajapinnassa **ei ole aluesuodatinta**: mitattuna 16.8.2026 se
palauttaa 467 riviä riippumatta siitä annetaanko ``regions``,
``region``, ``areas`` vai ei mitään. ``regions=161`` näyttäisi
suodattimelta, ja siihen luottava lukisi Kuopion sijaan ensimmäisen
rivin alueen — hiljainen virhe joka tuottaa väärän luvun eikä
virheilmoitusta.
"""

import sqlite3

import pytest

import aura.server as _server
from aura.database import init_db
from aura.tools.reference import lookup_municipality


@pytest.fixture
def conn(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO ref_metadata (name, record_count, version, populated_at)"
        " VALUES ('municipalities', 308, '20260101', '2026-01-01 00:00:00')"
    )
    c.execute(
        "INSERT INTO ref_municipalities"
        " (code, name_fi, name_sv, region_code, region_name_fi,"
        "  wellbeing_area_code, wellbeing_area_name_fi,"
        "  sotkanet_id, sotkanet_region_id, sotkanet_wellbeing_area_id)"
        " VALUES ('297','Kuopio','Kuopio','11','Pohjois-Savo',"
        "         '13','Pohjois-Savon hyvinvointialue', 161, 497, 974)"
    )
    # Kunta jolle tunnusta ei ole populoitu — rivien on jäätävä pois.
    c.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv) VALUES ('999','Testilä','Testilä')"
    )
    c.commit()
    monkeypatch.setattr(_server, "_get_conn", lambda ctx=None: c)
    return c


class TestSilta:
    def test_aluetunnus_nakyy(self, conn: sqlite3.Connection) -> None:
        tulos = lookup_municipality("Kuopio")
        assert "161" in tulos

    def test_kertoo_etta_tunnus_eroaa_kuntakoodista(self, conn: sqlite3.Connection) -> None:
        """Ilman tätä lukija olettaisi kuntakoodin kelpaavan."""
        tulos = lookup_municipality("Kuopio")
        assert "eri kuin kuntakoodi 297" in tulos

    def test_maakunta_ja_hyvinvointialue_mukana(self, conn: sqlite3.Connection) -> None:
        tulos = lookup_municipality("Kuopio")
        assert "497" in tulos
        assert "974" in tulos

    def test_populoimaton_kunta_ei_saa_sotkanet_rivia(self, conn: sqlite3.Connection) -> None:
        tulos = lookup_municipality("Testilä")
        assert "Sotkanet" not in tulos


class TestOhjeEiValehtele:
    """Ohje ei saa esittää suodatinta jota rajapinnassa ei ole."""

    def test_ei_lupaa_aluesuodatinta(self, conn: sqlite3.Connection) -> None:
        tulos = lookup_municipality("Kuopio")
        assert "regions=161" not in tulos, "ohje esittää suodatinta jota ei ole"
        assert "region=161" not in tulos

    def test_kertoo_etta_kaikki_alueet_palautuvat(self, conn: sqlite3.Connection) -> None:
        tulos = lookup_municipality("Kuopio")
        assert "kaikki alueet" in tulos

    def test_neuvoo_suodattamaan_vastauksesta(self, conn: sqlite3.Connection) -> None:
        tulos = lookup_municipality("Kuopio")
        assert "region == 161" in tulos


class TestVanhaKanta:
    """Migraatiota edeltävä kanta ei saa kaataa työkalua."""

    def test_puuttuva_sarake_ei_kaada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        init_db(c)
        c.execute(
            "INSERT INTO ref_metadata (name, record_count, version, populated_at)"
            " VALUES ('municipalities', 1, '1', '2026-01-01 00:00:00')"
        )
        c.execute(
            "INSERT INTO ref_municipalities (code, name_fi, name_sv)"
            " VALUES ('297','Kuopio','Kuopio')"
        )
        # Indeksi viittaa sarakkeeseen, joten se on purettava ensin.
        c.execute("DROP INDEX idx_ref_municipalities_sotkanet")
        c.execute("ALTER TABLE ref_municipalities DROP COLUMN sotkanet_id")
        c.commit()
        monkeypatch.setattr(_server, "_get_conn", lambda ctx=None: c)

        tulos = lookup_municipality("Kuopio")
        assert "Kuopio" in tulos
        assert "Sotkanet" not in tulos
