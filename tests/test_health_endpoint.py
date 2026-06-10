"""Testit /health-endpointille ja sen payloadille (#138)."""

from __future__ import annotations

import sqlite3

from aura.server import health_payload


def _db_with_datasets(n: int) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE datasets (id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO datasets (id) VALUES (?)", [(i,) for i in range(n)])
    conn.commit()
    return conn


def test_health_payload_reports_ok_and_count() -> None:
    conn = _db_with_datasets(3)
    try:
        assert health_payload(conn) == {"status": "ok", "datasets": 3}
    finally:
        conn.close()
