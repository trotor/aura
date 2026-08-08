"""Testit AURA_DB-ympäristömuuttujalle.

Kannan polku oli kovakoodattu paketin sijaintiin nähden, mikä esti
kontissa ajamisen: image asennetaan ``/app``:iin mutta kanta halutaan
volumeen ``/data``:aan. Ilman ohitusta pro-kantaa ei voi tarjoilla
lainkaan.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from aura.database import DEFAULT_DB_PATH, get_connection, resolve_db_path


def test_ilman_muuttujaa_kaytetaan_pakettipolkua() -> None:
    assert resolve_db_path(env={}) == DEFAULT_DB_PATH


def test_muuttuja_ohittaa_pakettipolun() -> None:
    assert resolve_db_path(env={"AURA_DB": "/data/aura-pro.db"}) == Path(
        "/data/aura-pro.db"
    )


def test_tyhja_arvo_ei_ohita() -> None:
    """Tyhjä muuttuja on yleinen vahinko (esim. ``AURA_DB=$UNSET``).

    Tulkinta tyhjänä polkuna avaisi yhteyden hakemistoon ``.`` ja
    kaatuisi hämärästi. Fallback on turvallisempi ja rehellisempi.
    """
    for value in ("", "   ", "\t"):
        assert resolve_db_path(env={"AURA_DB": value}) == DEFAULT_DB_PATH


def test_tilde_laajenee() -> None:
    result = resolve_db_path(env={"AURA_DB": "~/kannat/aura.db"})
    assert "~" not in str(result)
    assert result.is_absolute()


def test_get_connection_kayttaa_muuttujaa(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Muuttuja luetaan kutsuhetkellä, ei importtihetkellä.

    Tämä on olennaista: jos arvo sidottaisiin oletusargumenttiin, sen
    asettaminen importin jälkeen ei vaikuttaisi mihinkään ja vika
    näkyisi vasta ajossa väärän kannan muodossa.
    """
    db = tmp_path / "oma.db"
    sqlite3.connect(db).close()

    monkeypatch.setenv("AURA_DB", str(db))  # type: ignore[attr-defined]

    conn = get_connection()
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        assert Path(row["file"]).resolve() == db.resolve()
    finally:
        conn.close()


def test_eksplisiittinen_polku_voittaa_muuttujan(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Kutsuja tietää paremmin — testit ja skriptit nojaavat tähän."""
    env_db = tmp_path / "env.db"
    arg_db = tmp_path / "arg.db"
    for p in (env_db, arg_db):
        sqlite3.connect(p).close()

    monkeypatch.setenv("AURA_DB", str(env_db))  # type: ignore[attr-defined]

    conn = get_connection(arg_db)
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        assert Path(row["file"]).resolve() == arg_db.resolve()
    finally:
        conn.close()


def test_readonly_moodi_kunnioittaa_muuttujaa(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Remote-deploy käyttää molempia yhdessä, joten polku on katettava myös tässä haarassa."""
    db = tmp_path / "ro.db"
    sqlite3.connect(db).close()

    monkeypatch.setenv("AURA_DB", str(db))  # type: ignore[attr-defined]

    conn = get_connection(readonly=True)
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        assert Path(row["file"]).resolve() == db.resolve()
    finally:
        conn.close()
