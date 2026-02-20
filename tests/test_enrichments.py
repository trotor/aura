"""Testit enrichment-järjestelmälle."""

import sqlite3

from aura.database import (
    add_enrichment,
    export_enrichments,
    get_enrichment_count,
    get_enrichments,
    get_latest_enrichments,
    import_enrichments,
    init_db,
    upsert_dataset,
)
from aura.models import Dataset
from aura.search import format_dataset_detail, format_enrichments


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_dataset(conn: sqlite3.Connection, ds_id: str = "test-1") -> None:
    """Lisää testidatasetti kantaan."""
    ds = Dataset(id=ds_id, name=ds_id, title="Test Dataset")
    upsert_dataset(conn, ds)
    conn.commit()


class TestAddEnrichment:
    """add_enrichment()-funktion testit."""

    def test_returns_uuid(self):
        conn = _memory_db()
        _seed_dataset(conn)
        eid = add_enrichment(
            conn, "test-1", "quality_notes", "Hyvälaatuista dataa"
        )
        assert len(eid) == 36  # UUID4 format

    def test_stores_enrichment(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(
            conn, "test-1", "description_extended",
            "Laajempi kuvaus datasetistä",
        )
        rows = conn.execute(
            "SELECT * FROM enrichments WHERE dataset_id = 'test-1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["field"] == "description_extended"
        assert rows[0]["value"] == "Laajempi kuvaus datasetistä"

    def test_default_confidence_is_medium(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "use_case", "Esimerkki")
        row = conn.execute(
            "SELECT confidence FROM enrichments"
        ).fetchone()
        assert row["confidence"] == "medium"

    def test_default_source_type_is_mcp_session(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "use_case", "Esimerkki")
        row = conn.execute(
            "SELECT source_type FROM enrichments"
        ).fetchone()
        assert row["source_type"] == "mcp_session"

    def test_allows_enrichment_without_existing_dataset(self):
        """Enrichment voi viitata datasettiin jota ei ole kannassa."""
        conn = _memory_db()
        # Ei seed_dataset — pitää silti toimia
        eid = add_enrichment(
            conn, "nonexistent-ds", "quality_notes", "Testirikastus"
        )
        assert len(eid) == 36


class TestGetEnrichments:
    """get_enrichments() ja get_latest_enrichments()."""

    def test_returns_all_enrichments(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "versio 1")
        add_enrichment(conn, "test-1", "quality_notes", "versio 2")
        add_enrichment(conn, "test-1", "use_case", "käyttötapaus")

        results = get_enrichments(conn, "test-1")
        assert len(results) == 3

    def test_latest_returns_one_per_field(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "vanha")
        add_enrichment(conn, "test-1", "quality_notes", "uusi")
        add_enrichment(conn, "test-1", "use_case", "tapaus")

        results = get_latest_enrichments(conn, "test-1")
        assert len(results) == 2

        fields = {r["field"]: r["value"] for r in results}
        assert fields["quality_notes"] == "uusi"
        assert fields["use_case"] == "tapaus"

    def test_empty_for_unknown_dataset(self):
        conn = _memory_db()
        results = get_enrichments(conn, "unknown")
        assert results == []


class TestEnrichmentCount:
    """get_enrichment_count()."""

    def test_counts_unique_fields(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "v1")
        add_enrichment(conn, "test-1", "quality_notes", "v2")
        add_enrichment(conn, "test-1", "use_case", "tapaus")

        assert get_enrichment_count(conn, "test-1") == 2

    def test_zero_for_no_enrichments(self):
        conn = _memory_db()
        assert get_enrichment_count(conn, "nope") == 0


class TestExportImport:
    """export_enrichments() ja import_enrichments()."""

    def test_export_returns_all(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "hyvä")
        add_enrichment(
            conn, "test-1", "use_case", "analyysi",
            source_type="web_research",
        )

        exported = export_enrichments(conn)
        assert len(exported) == 2

    def test_export_filter_by_source_type(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "hyvä")
        add_enrichment(
            conn, "test-1", "use_case", "analyysi",
            source_type="web_research",
        )

        exported = export_enrichments(conn, source_type="web_research")
        assert len(exported) == 1
        assert exported[0]["field"] == "use_case"

    def test_import_inserts_new(self):
        conn = _memory_db()
        enrichments = [
            {
                "id": "aaaa-bbbb-cccc",
                "dataset_id": "test-1",
                "field": "quality_notes",
                "value": "tuotu",
                "confidence": "high",
                "source_type": "manual",
                "source_detail": "",
                "created_at": "2025-01-01T00:00:00",
            }
        ]
        count = import_enrichments(conn, enrichments)
        assert count == 1

    def test_import_skips_duplicates(self):
        conn = _memory_db()
        enrichments = [
            {
                "id": "same-id",
                "dataset_id": "test-1",
                "field": "quality_notes",
                "value": "tuotu",
                "source_type": "manual",
            }
        ]
        import_enrichments(conn, enrichments)
        count = import_enrichments(conn, enrichments)
        assert count == 0

    def test_roundtrip(self):
        """Export → import -kierto säilyttää datan."""
        conn1 = _memory_db()
        _seed_dataset(conn1)
        add_enrichment(
            conn1, "test-1", "quality_notes", "hyvä",
            confidence="high", source_type="web_research",
            source_detail="https://example.com",
        )

        exported = export_enrichments(conn1)

        conn2 = _memory_db()
        count = import_enrichments(conn2, exported)
        assert count == 1

        results = get_enrichments(conn2, "test-1")
        assert len(results) == 1
        assert results[0]["value"] == "hyvä"
        assert results[0]["confidence"] == "high"
        assert results[0]["source_type"] == "web_research"


class TestFormatEnrichments:
    """format_enrichments() ja format_dataset_detail()."""

    def test_format_empty(self):
        assert format_enrichments([]) == ""

    def test_format_shows_field_label(self):
        enrichments = [
            {
                "field": "quality_notes",
                "value": "Erittäin hyvä",
                "confidence": "high",
                "source_type": "mcp_session",
            }
        ]
        result = format_enrichments(enrichments)
        assert "Laatuhuomiot" in result
        assert "Erittäin hyvä" in result
        assert "[varma]" in result

    def test_format_shows_source_type_if_not_mcp(self):
        enrichments = [
            {
                "field": "use_case",
                "value": "Analyysi",
                "confidence": "medium",
                "source_type": "web_research",
            }
        ]
        result = format_enrichments(enrichments)
        assert "web_research" in result

    def test_format_hides_mcp_session_source(self):
        enrichments = [
            {
                "field": "use_case",
                "value": "Analyysi",
                "confidence": "medium",
                "source_type": "mcp_session",
            }
        ]
        result = format_enrichments(enrichments)
        assert "mcp_session" not in result

    def test_detail_includes_enrichments(self):
        dataset = {
            "title_fi": "Testi",
            "name": "testi-1",
            "notes_fi": "Kuvaus",
        }
        enrichments = [
            {
                "field": "quality_notes",
                "value": "Hyvä laatu",
                "confidence": "medium",
                "source_type": "mcp_session",
            }
        ]
        result = format_dataset_detail(dataset, enrichments=enrichments)
        assert "Rikastukset" in result
        assert "Hyvä laatu" in result

    def test_detail_without_enrichments(self):
        dataset = {
            "title_fi": "Testi",
            "name": "testi-1",
        }
        result = format_dataset_detail(dataset)
        assert "Rikastukset" not in result


class TestMigration:
    """Migraatio luo enrichments-taulun."""

    def test_table_exists(self):
        conn = _memory_db()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "enrichments" in table_names

    def test_indexes_exist(self):
        conn = _memory_db()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [i["name"] for i in indexes]
        assert "idx_enrichments_dataset" in index_names
        assert "idx_enrichments_dataset_field" in index_names
