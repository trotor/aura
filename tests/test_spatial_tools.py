"""Testit paikkatietotyökaluille (#136): map_sheet, find_map_sheets."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch


def _db_with_map_sheets() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE ref_map_sheets (
            id TEXT, scale TEXT,
            min_x REAL, min_y REAL, max_x REAL, max_y REAL,
            centroid_x REAL, centroid_y REAL, updated_at TEXT
        )
        """
    )
    rows = [
        # id, scale, minx, miny, maxx, maxy, cx, cy
        ("K2", "utm200", -76000.0, 6570000.0, 116000.0, 6666000.0, 20000.0, 6618000.0),
        ("L4133", "utm25", 340000.0, 6820000.0, 352000.0, 6826000.0, 346000.0, 6823000.0),
        ("L4133A", "utm10", 340000.0, 6820000.0, 346000.0, 6823000.0, 343000.0, 6821500.0),
        ("L4134", "utm25", 352000.0, 6820000.0, 364000.0, 6826000.0, 358000.0, 6823000.0),
    ]
    conn.executemany(
        "INSERT INTO ref_map_sheets "
        "(id, scale, min_x, min_y, max_x, max_y, centroid_x, centroid_y) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return conn


def test_map_sheet_returns_bbox_for_known_sheet() -> None:
    from aura.server import map_sheet

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = map_sheet("L4133")
    # Sisältää valmiin EPSG:3067 bbox-merkkijonon WFS/WCS-kyselyyn
    assert "340000" in out and "6820000" in out and "352000" in out and "6826000" in out
    assert "EPSG:3067" in out
    assert "utm25" in out


def test_map_sheet_is_case_insensitive() -> None:
    from aura.server import map_sheet

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = map_sheet("l4133")
    assert "340000" in out


def test_map_sheet_unknown_returns_message() -> None:
    from aura.server import map_sheet

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = map_sheet("XYZ999")
    assert "ei löytynyt" in out.lower() or "ei löydy" in out.lower()


def test_find_map_sheets_by_prefix_and_scale() -> None:
    from aura.server import find_map_sheets

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = find_map_sheets(scale="utm25", prefix="L413")
    assert "L4133" in out
    assert "L4134" in out
    assert "L4133A" not in out  # eri mittakaava (utm10)


def test_find_map_sheets_by_bbox_intersection() -> None:
    from aura.server import find_map_sheets

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = find_map_sheets(scale="utm25", bbox="345000,6821000,346000,6822000")
    assert "L4133" in out
    assert "L4134" not in out  # ei leikkaa


def test_find_map_sheets_by_point_containment() -> None:
    from aura.server import find_map_sheets

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = find_map_sheets(scale="utm25", point="358000,6823000")
    assert "L4134" in out
    assert "L4133" not in out


def test_find_map_sheets_requires_a_filter() -> None:
    from aura.server import find_map_sheets

    conn = _db_with_map_sheets()
    with patch("aura.server._get_conn", return_value=conn):
        out = find_map_sheets(scale="utm25")
    assert "anna" in out.lower() or "vähintään" in out.lower() or "bbox" in out.lower()
