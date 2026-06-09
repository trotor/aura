"""Testit read-only-tietokantayhteydelle (#135)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aura.database import get_connection


def _seed(path: Path) -> None:
    conn = get_connection(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('a')")
    conn.commit()
    conn.close()


def test_readonly_connection_can_read(tmp_path: Path) -> None:
    db = tmp_path / "ro.db"
    _seed(db)
    conn = get_connection(db, readonly=True)
    try:
        assert conn.execute("SELECT v FROM t WHERE id = 1").fetchone()[0] == "a"
    finally:
        conn.close()


def test_readonly_connection_rejects_writes(tmp_path: Path) -> None:
    db = tmp_path / "ro.db"
    _seed(db)
    conn = get_connection(db, readonly=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO t (v) VALUES ('b')")
            conn.commit()
    finally:
        conn.close()
