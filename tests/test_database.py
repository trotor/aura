"""Testit tietokantakerrokselle."""

import sqlite3

from aura.database import (
    _split_sql,
    get_stats,
    init_db,
    run_migrations,
    search_datasets,
    upsert_dataset,
)
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


def test_resource_upsert_preserves_health():
    """Resurssien UPSERT säilyttää resource_health-tietueet (#85)."""
    conn = _memory_db()

    # Datasetti kahdella resurssilla
    ds = Dataset(
        id="ds-health",
        name="health-test",
        title="Health test",
        organization_id="org-1",
        organization_name="org",
        organization_title="Org",
        license_id="cc-by-4.0",
        num_resources=2,
        resources=[
            Resource(id="r-1", name="a.csv", format="CSV", url="https://example.com/a"),
            Resource(id="r-2", name="b.csv", format="CSV", url="https://example.com/b"),
        ],
    )
    upsert_dataset(conn, ds)
    conn.commit()

    # Simuloi health-tarkistukset molemmille resursseille
    conn.execute(
        "INSERT INTO resource_health (resource_id, dataset_id, url, is_available, checked_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        ("r-1", "ds-health", "https://example.com/a", True),
    )
    conn.execute(
        "INSERT INTO resource_health (resource_id, dataset_id, url, is_available, checked_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        ("r-2", "ds-health", "https://example.com/b", True),
    )
    conn.commit()

    # Upsert uudelleen samoilla resursseilla → health säilyy
    ds.resources[0].name = "a_updated.csv"
    upsert_dataset(conn, ds)
    conn.commit()

    health_rows = conn.execute(
        "SELECT resource_id FROM resource_health ORDER BY resource_id"
    ).fetchall()
    assert [r[0] for r in health_rows] == ["r-1", "r-2"]

    # Resurssin nimi päivittyi
    res = conn.execute("SELECT name FROM resources WHERE id = 'r-1'").fetchone()
    assert res[0] == "a_updated.csv"

    # Upsert jossa r-2 poistettu → vain r-2 poistetaan, r-1 health säilyy
    ds.resources = [ds.resources[0]]
    ds.num_resources = 1
    upsert_dataset(conn, ds)
    conn.commit()

    remaining = conn.execute("SELECT id FROM resources WHERE dataset_id = 'ds-health'").fetchall()
    assert [r[0] for r in remaining] == ["r-1"]

    health_rows = conn.execute("SELECT resource_id FROM resource_health").fetchall()
    # r-1 health tietue säilyy (ei poistettu DELETE CASCADElla)
    assert any(r[0] == "r-1" for r in health_rows)


class TestSplitSql:
    """_split_sql()-apufunktion testit."""

    def test_simple_statements(self) -> None:
        sql = "CREATE TABLE a (id INT);\nCREATE TABLE b (id INT);"
        result = _split_sql(sql)
        assert len(result) == 2
        assert "CREATE TABLE a" in result[0]
        assert "CREATE TABLE b" in result[1]

    def test_trigger_block(self) -> None:
        sql = (
            "CREATE TRIGGER t AFTER INSERT ON x BEGIN\n"
            "  INSERT INTO y VALUES (NEW.id);\n"
            "END;\n"
            "CREATE TABLE z (id INT);"
        )
        result = _split_sql(sql)
        assert len(result) == 2
        assert "TRIGGER" in result[0]
        assert "INSERT INTO y" in result[0]
        assert "CREATE TABLE z" in result[1]

    def test_skips_comments_and_blanks(self) -> None:
        sql = "-- comment\n\nCREATE TABLE a (id INT);\n"
        result = _split_sql(sql)
        assert len(result) == 1
