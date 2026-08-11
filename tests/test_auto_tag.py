"""Testit auto-tag CLI-komennolle ja get_datasets_without_enrichment()."""

import sqlite3

import pytest

from aura.database import (
    add_enrichment,
    get_datasets_without_enrichment,
    init_db,
    upsert_dataset,
)
from aura.models import Dataset


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed(conn: sqlite3.Connection, ds_id: str, source: str = "test") -> None:
    ds = Dataset(id=ds_id, name=ds_id, title=f"Dataset {ds_id}", source=source)
    upsert_dataset(conn, ds)
    conn.commit()


class TestGetDatasetsWithoutEnrichment:
    """get_datasets_without_enrichment()-testit."""

    def test_returns_datasets_without_field(self):
        conn = _memory_db()
        _seed(conn, "ds-1")
        _seed(conn, "ds-2")
        add_enrichment(conn, "ds-1", "yso_concepts", '[{"uri":"x","label":"y"}]')

        result = get_datasets_without_enrichment(conn, "yso_concepts")
        ids = [d["id"] for d in result]
        assert "ds-2" in ids
        assert "ds-1" not in ids

    def test_filters_by_source(self):
        conn = _memory_db()
        _seed(conn, "ds-a", source="avoindata.fi")
        _seed(conn, "ds-b", source="statfin")

        result = get_datasets_without_enrichment(
            conn, "yso_concepts", source="avoindata.fi",
        )
        ids = [d["id"] for d in result]
        assert "ds-a" in ids
        assert "ds-b" not in ids

    def test_respects_limit(self):
        conn = _memory_db()
        for i in range(10):
            _seed(conn, f"ds-{i}")

        result = get_datasets_without_enrichment(conn, "yso_concepts", limit=3)
        assert len(result) == 3

    def test_returns_empty_when_all_tagged(self):
        conn = _memory_db()
        _seed(conn, "ds-1")
        add_enrichment(conn, "ds-1", "yso_concepts", '[{"uri":"x","label":"y"}]')

        result = get_datasets_without_enrichment(conn, "yso_concepts")
        assert result == []

    def test_enrichment_by_name_also_excluded(self):
        """Enrichment tallennettu slug-nimellä → ei tule tuloksiin."""
        conn = _memory_db()
        ds = Dataset(id="uuid-123", name="my-dataset", title="Test")
        upsert_dataset(conn, ds)
        conn.commit()
        add_enrichment(conn, "my-dataset", "yso_concepts", '[]')

        result = get_datasets_without_enrichment(conn, "yso_concepts")
        ids = [d["id"] for d in result]
        assert "uuid-123" not in ids

    def test_other_enrichment_fields_dont_exclude(self):
        """Muu enrichment-kenttä ei sulje pois yso_concepts-haussa."""
        conn = _memory_db()
        _seed(conn, "ds-1")
        add_enrichment(conn, "ds-1", "keywords", '["test"]')

        result = get_datasets_without_enrichment(conn, "yso_concepts")
        ids = [d["id"] for d in result]
        assert "ds-1" in ids


class TestAutoTagDryRun:
    """auto-tag --dry-run ei tallenna."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_save(self):
        from aura.cli import _auto_tag

        conn = _memory_db()
        _seed(conn, "ds-1")

        # Patchaa get_connection palauttamaan muisti-db

        original_get_conn = None

        # Monkey-patch database functions
        import aura.database as db_mod

        original_get_connection = db_mod.get_connection

        def mock_get_connection(**kwargs):  # noqa: ARG001
            return conn

        db_mod.get_connection = mock_get_connection  # type: ignore[assignment]

        try:
            await _auto_tag(limit=1, dry_run=True, delay=0)
        finally:
            db_mod.get_connection = original_get_connection  # type: ignore[assignment]

        # Varmista ettei enrichmenttejä tallennettu
        rows = conn.execute("SELECT * FROM enrichments").fetchall()
        assert len(rows) == 0


class TestMigration014:
    """Migraatio 014 lisää yso_concepts triggereihin."""

    def test_yso_concepts_indexed_in_fts(self):
        conn = _memory_db()
        _seed(conn, "ds-1")

        # Lisää yso_concepts enrichment
        add_enrichment(conn, "ds-1", "yso_concepts", '["liikenne", "geologia"]')

        # Tarkista että se löytyy FTS-indeksistä
        rows = conn.execute(
            "SELECT * FROM enrichments_fts WHERE enrichments_fts MATCH 'liikenne'"
        ).fetchall()
        assert len(rows) >= 1

    def test_keywords_still_indexed(self):
        """Vanhat kentät toimivat edelleen."""
        conn = _memory_db()
        _seed(conn, "ds-1")
        add_enrichment(conn, "ds-1", "keywords", '["maatalous"]')

        rows = conn.execute(
            "SELECT * FROM enrichments_fts WHERE enrichments_fts MATCH 'maatalous'"
        ).fetchall()
        assert len(rows) >= 1
