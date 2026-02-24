"""Testit suggest_questions-työkalulle."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import suggest_questions
from aura.tools.suggest import _count_theme_datasets


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_db(conn: sqlite3.Connection) -> None:
    """Lisää testidatasetit."""
    upsert_dataset(
        conn,
        Dataset(
            id="test-vaesto-1",
            name="vaesto-1",
            title="Väestörakenne",
            title_fi="Väestörakenne",
            source="statfin",
            keywords_fi=["väestö", "asukas"],
            geographical_coverage=["Tampere"],
            organization_title="Tilastokeskus",
            resources=[
                Resource(id="r1", name="data", format="PXWEB", url="https://example.com"),
            ],
        ),
    )
    upsert_dataset(
        conn,
        Dataset(
            id="test-liikenne-1",
            name="liikenne-1",
            title="Liikennemäärät",
            title_fi="Liikennemäärät",
            source="digitraffic",
            keywords_fi=["liikenne", "tie"],
            geographical_coverage=["Tampere"],
            organization_title="Digitraffic",
            resources=[
                Resource(id="r2", name="data", format="JSON", url="https://example.com"),
            ],
        ),
    )
    conn.commit()


def test_suggest_questions_basic() -> None:
    """Perusehdotukset ilman suodattimia."""
    conn = _memory_db()
    _seed_db(conn)

    with patch("aura.server._get_conn", return_value=conn):
        result = suggest_questions()

    assert "Esimerkkikysymyksiä" in result
    assert "Väestö" in result
    assert "Liikenne" in result
    assert "Yleiset työkalut" in result


def test_suggest_questions_with_region() -> None:
    """Ehdotukset aluerajattuina."""
    conn = _memory_db()
    _seed_db(conn)

    with patch("aura.server._get_conn", return_value=conn):
        result = suggest_questions(region="Tampere")

    assert "Tampere" in result
    assert "search_by_region" in result


def test_suggest_questions_with_theme() -> None:
    """Ehdotukset teemarajattuina."""
    conn = _memory_db()
    _seed_db(conn)

    with patch("aura.server._get_conn", return_value=conn):
        result = suggest_questions(theme="liikenne")

    assert "Liikenne" in result
    assert "Yleiset työkalut" in result


def test_suggest_questions_unknown_region() -> None:
    """Tuntematon alue."""
    conn = _memory_db()
    _seed_db(conn)

    with patch("aura.server._get_conn", return_value=conn):
        result = suggest_questions(region="Ei-Ole-Kunta")

    assert "Esimerkkikysymyksiä" in result


def test_count_theme_datasets() -> None:
    """Datasettien laskenta toimii."""
    conn = _memory_db()
    _seed_db(conn)

    count = _count_theme_datasets(conn, ["väestö", "asukas"], None)
    assert count >= 1

    count_region = _count_theme_datasets(conn, ["väestö"], ["Tampere"])
    assert count_region >= 1

    count_empty = _count_theme_datasets(conn, ["tuntematon_sana_xyz"], None)
    assert count_empty == 0
