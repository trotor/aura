"""Testit tietokantakerrokselle."""

import sqlite3

from aura.database import get_stats, init_db, run_migrations, search_datasets, upsert_dataset
from aura.models import Dataset, Resource


def _memory_db() -> sqlite3.Connection:
    """Luo muistitietokanta testausta varten."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _sample_dataset() -> Dataset:
    return Dataset(
        id="test-1",
        name="helsingin-vaestotiedot",
        title="Helsingin väestötiedot",
        title_fi="Helsingin väestötiedot",
        title_en="Helsinki population data",
        notes_fi="Väestötilastot Helsingin kaupungilta",
        organization_id="org-helsinki",
        organization_name="helsinki",
        organization_title="Helsingin kaupunki",
        license_id="cc-by-4.0",
        license_title="CC BY 4.0",
        keywords_fi=["väestö", "helsinki", "tilasto"],
        keywords_en=["population", "helsinki"],
        num_resources=1,
        resources=[
            Resource(
                id="res-1",
                name="vaesto.csv",
                format="CSV",
                url="https://example.com/vaesto.csv",
            )
        ],
    )


def test_init_db():
    conn = _memory_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t["name"] for t in tables]
    assert "datasets" in table_names
    assert "resources" in table_names
    assert "datasets_fts" in table_names


def test_upsert_and_search():
    conn = _memory_db()
    dataset = _sample_dataset()
    upsert_dataset(conn, dataset)
    conn.commit()

    results = search_datasets(conn, "väestö")
    assert len(results) == 1
    assert results[0]["title_fi"] == "Helsingin väestötiedot"


def test_upsert_updates_existing():
    conn = _memory_db()
    dataset = _sample_dataset()
    upsert_dataset(conn, dataset)
    conn.commit()

    dataset.title_fi = "Päivitetty otsikko"
    upsert_dataset(conn, dataset)
    conn.commit()

    row = conn.execute("SELECT title_fi FROM datasets WHERE id = 'test-1'").fetchone()
    assert row["title_fi"] == "Päivitetty otsikko"


def test_get_stats_with_data():
    conn = _memory_db()
    upsert_dataset(conn, _sample_dataset())
    conn.commit()

    s = get_stats(conn)
    assert s["total_datasets"] == 1
    assert s["total_organizations"] == 1


def test_migrations_applied():
    conn = _memory_db()
    versions = conn.execute("SELECT version, name FROM schema_migrations").fetchall()
    assert len(versions) >= 1
    assert versions[0]["version"] == 1
    assert "initial" in versions[0]["name"]


def test_migrations_idempotent():
    conn = _memory_db()
    count = run_migrations(conn)
    assert count == 0
