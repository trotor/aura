"""Testit kuntien bbox-populaattorille (#136)."""

from __future__ import annotations

import sqlite3

from aura.populators.municipality_bbox import MunicipalityBboxPopulator


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_apply_bboxes_updates_matching_municipalities() -> None:
    pop = MunicipalityBboxPopulator(conn=_db())  # __init__ ajaa migraatiot
    pop.conn.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv) "
        "VALUES ('091','Helsinki','Helsingfors')"
    )
    pop.conn.commit()

    updated = pop._apply_bboxes({"091": (25490000.0, 6665000.0, 25515000.0, 6690000.0)})

    assert updated == 1
    row = pop.conn.execute(
        "SELECT min_x, max_y FROM ref_municipalities WHERE code = '091'"
    ).fetchone()
    assert row["min_x"] == 25490000.0
    assert row["max_y"] == 6690000.0


def test_apply_bboxes_ignores_unknown_codes() -> None:
    pop = MunicipalityBboxPopulator(conn=_db())
    pop.conn.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv) "
        "VALUES ('091','Helsinki','Helsingfors')"
    )
    pop.conn.commit()

    updated = pop._apply_bboxes({"999": (1.0, 2.0, 3.0, 4.0)})

    assert updated == 0
