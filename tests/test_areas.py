"""Aluetunnisteiden tulkinta (aura.areas)."""

from __future__ import annotations

import sqlite3

import pytest

from aura.areas import members, parents, resolve_area, resolve_areas
from aura.database import run_migrations


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    c.executemany(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv, region_code, region_name_fi)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            ("837", "Tampere", "Tammerfors", "06", "Pirkanmaa"),
            ("398", "Lahti", "Lahtis", "07", "Päijät-Häme"),
            ("020", "Akaa", "Ackas", "06", "Pirkanmaa"),
        ],
    )
    c.executemany(
        "INSERT INTO ref_areas (level, code, name_fi, name_sv, vintage) VALUES (?, ?, ?, ?, 2026)",
        [
            ("kunta", "837", "Tampere", "Tammerfors"),
            ("kunta", "398", "Lahti", "Lahtis"),
            ("kunta", "020", "Akaa", "Ackas"),
            ("seutukunta", "064", "Tampere", "Tammerfors"),
            ("maakunta", "06", "Pirkanmaa", "Birkaland"),
            ("nuts3", "FI19B", "Pirkanmaa", "Birkaland"),
            ("maakunta", "07", "Päijät-Häme", "Päijänne-Tavastland"),
            ("hyvinvointialue", "08", "Pirkanmaan hyvinvointialue", ""),
        ],
    )
    c.executemany(
        "INSERT INTO ref_area_membership (municipality_code, level, area_code, vintage)"
        " VALUES (?, ?, ?, 2026)",
        [
            ("837", "maakunta", "06"),
            ("837", "seutukunta", "064"),
            ("837", "hyvinvointialue", "08"),
            ("020", "maakunta", "06"),
            ("398", "maakunta", "07"),
        ],
    )
    c.execute(
        "INSERT INTO ref_municipality_changes VALUES"
        " ('532', 'Nastola', '398', 'Lahti', 2016, 'Tilastokeskus')"
    )
    c.execute(
        "INSERT INTO ref_postal_codes (code, name_fi, name_sv, municipality_code)"
        " VALUES ('33100', 'Tampere', 'Tammerfors', '837')"
    )
    return c


def test_kunta_voittaa_seutukunnan(conn: sqlite3.Connection) -> None:
    m = resolve_area(conn, "Tampere")
    assert m is not None
    assert (m.area.level, m.area.code, m.area.statfin_code) == ("kunta", "837", "KU837")
    assert [a.level for a in m.alternatives] == ["seutukunta"]


def test_ruotsinkielinen_nimi_ja_koodit(conn: sqlite3.Connection) -> None:
    for query in ("Tammerfors", "837", "KU837", "ku837"):
        m = resolve_area(conn, query)
        assert m is not None and m.area.code == "837", query


def test_etuliitteellinen_taso(conn: sqlite3.Connection) -> None:
    m = resolve_area(conn, "SK064")
    assert m is not None and m.area.level == "seutukunta"
    m = resolve_area(conn, "MK6")
    assert m is not None and (m.area.level, m.area.code) == ("maakunta", "06")


def test_maakunta_ennen_nuts(conn: sqlite3.Connection) -> None:
    m = resolve_area(conn, "Pirkanmaa")
    assert m is not None and m.area.level == "maakunta"
    m = resolve_area(conn, "Pirkanmaan maakunta")
    assert m is not None and m.area.level == "maakunta"


def test_lakkautettu_kunta_tulkitaan_seuraajaksi_ja_kerrotaan(conn: sqlite3.Connection) -> None:
    for query in ("Nastola", "532"):
        m = resolve_area(conn, query)
        assert m is not None and m.area.code == "398", query
        assert "2016" in m.note and "Nastola" in m.note


def test_taivutettu_nimi(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO ref_areas (level, code, name_fi, name_sv, vintage)"
        " VALUES ('kunta', '092', 'Vantaa', 'Vanda', 2026)"
    )
    for query in ("Vantaan", "Vantaalla", "Tampereella"):
        m = resolve_area(conn, query)
        assert m is not None, query
        assert m.area.name_fi in ("Vantaa", "Tampere"), query


def test_postinumero(conn: sqlite3.Connection) -> None:
    m = resolve_area(conn, "33100")
    assert m is not None and m.area.level == "postinumero"
    assert "837" in m.note


def test_koko_maa(conn: sqlite3.Connection) -> None:
    m = resolve_area(conn, "Suomi")
    assert m is not None and m.area.statfin_code == "SSS"


def test_tuntematon_ja_tasorajaus(conn: sqlite3.Connection) -> None:
    assert resolve_area(conn, "Atlantis") is None
    m = resolve_area(conn, "Tampere", levels=("seutukunta",))
    assert m is not None and m.area.level == "seutukunta"
    matched, missing = resolve_areas(conn, ["Tampere", "Atlantis"])
    assert [x.area.code for x in matched] == ["837"] and missing == ["Atlantis"]


def test_ylemmat_tasot_ja_jasenet(conn: sqlite3.Connection) -> None:
    up = parents(conn, "837")
    assert up["maakunta"].name_fi == "Pirkanmaa" and up["seutukunta"].code == "064"
    pirkanmaa = resolve_area(conn, "Pirkanmaa")
    assert pirkanmaa is not None
    assert [a.name_fi for a in members(conn, pirkanmaa.area)] == ["Akaa", "Tampere"]


def test_toimii_ilman_aluetasotauluja(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM ref_areas")
    conn.execute("DELETE FROM ref_area_membership")
    m = resolve_area(conn, "Pirkanmaa")
    assert m is not None and m.area.level == "maakunta"
    assert [a.name_fi for a in members(conn, m.area)] == ["Akaa", "Tampere"]
