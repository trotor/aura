"""Testit enrichment-järjestelmälle."""

import sqlite3

from aura.database import (
    add_enrichment,
    export_enrichments,
    get_conflicting_enrichments,
    get_enrichment_count,
    get_enrichments,
    get_latest_enrichments,
    get_stale_enrichments,
    import_enrichments,
    init_db,
    prune_enrichments,
    search_datasets,
    upsert_dataset,
)
from aura.models import Dataset
from aura.search import (
    format_conflicts,
    format_dataset_detail,
    format_enrichments,
)


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
        assert rows[0]["confidence"] == "medium"
        assert rows[0]["source_type"] == "mcp_session"

    def test_allows_enrichment_without_existing_dataset(self):
        """Enrichment voi viitata datasettiin jota ei ole kannassa."""
        conn = _memory_db()
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


class TestEnrichmentCount:
    """get_enrichment_count()."""

    def test_counts_unique_fields(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "v1")
        add_enrichment(conn, "test-1", "quality_notes", "v2")
        add_enrichment(conn, "test-1", "use_case", "tapaus")

        assert get_enrichment_count(conn, "test-1") == 2


class TestExportImport:
    """export_enrichments() ja import_enrichments()."""

    def test_export_filter_by_source_type(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "hyvä")
        add_enrichment(
            conn, "test-1", "use_case", "analyysi",
            source_type="web_research",
        )

        exported = export_enrichments(conn)
        assert len(exported) == 2

        exported_filtered = export_enrichments(conn, source_type="web_research")
        assert len(exported_filtered) == 1
        assert exported_filtered[0]["field"] == "use_case"

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
        count1 = import_enrichments(conn, enrichments)
        count2 = import_enrichments(conn, enrichments)
        assert count1 == 1
        assert count2 == 0

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

    def test_format_shows_field_label_and_confidence(self):
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
        assert "mcp_session" not in result  # mcp_session piilotetaan

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

    def test_format_list_fields_as_comma_list(self):
        """keywords, tags ja data_fields näytetään pilkkulistoina."""
        enrichments = [
            {
                "field": "keywords",
                "value": '["maatalous", "peltolohko"]',
                "confidence": "high",
                "source_type": "mcp_session",
            },
            {
                "field": "tags",
                "value": '["paikkatietoaineisto", "avoin data"]',
                "confidence": "medium",
                "source_type": "mcp_session",
            },
            {
                "field": "data_fields",
                "value": '["id", "nimi", "pinta_ala"]',
                "confidence": "high",
                "source_type": "web_research",
            },
        ]
        result = format_enrichments(enrichments)
        assert "maatalous, peltolohko" in result
        assert "paikkatietoaineisto, avoin data" in result
        assert "id, nimi, pinta_ala" in result

    def test_probe_vaiheen_kentat_saavat_labelit_ja_service_layers_listautuu(self):
        """(I5) service_layers/example_request/use_case_suggested eivät saa

        näkyä raa'alla kenttänimellä eivätkä yhtenä JSON-pötkönä.
        """
        enrichments = [
            {
                "field": "service_layers",
                "value": '[{"name": "kunnat", "title": "Kunnat"}]',
                "confidence": "high",
                "source_type": "probe",
            },
            {
                "field": "example_request",
                "value": "https://example.test/wfs?outputFormat=GEOJSON",
                "confidence": "high",
                "source_type": "probe",
            },
            {
                "field": "use_case_suggested",
                "value": "Kuntarajojen visualisointi",
                "confidence": "medium",
                "source_type": "ai_analysis",
            },
        ]
        result = format_enrichments(enrichments)
        assert "service_layers:" not in result
        assert "example_request:" not in result
        assert "use_case_suggested:" not in result
        assert "WMS-layerit" in result
        assert "Esimerkkikutsu" in result
        assert "Ehdotettu käyttötapaus" in result
        # service_layers on _LIST_FIELDSissä: raaka JSON-taulukko ei saa
        # näkyä sellaisenaan yhtenä pötkönä.
        assert '[{"name"' not in result


class TestConflictingEnrichments:
    """get_conflicting_enrichments()."""

    def test_detects_conflicting_values(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "hyvä")
        add_enrichment(conn, "test-1", "quality_notes", "huono")
        add_enrichment(conn, "test-1", "use_case", "yksi arvo")  # ei ristiriita

        conflicts = get_conflicting_enrichments(conn, "test-1")
        assert len(conflicts) == 2
        values = {c["value"] for c in conflicts}
        assert values == {"hyvä", "huono"}

    def test_conflicts_sorted_by_confidence(self):
        conn = _memory_db()
        _seed_dataset(conn)
        add_enrichment(conn, "test-1", "quality_notes", "low", confidence="low")
        add_enrichment(conn, "test-1", "quality_notes", "high", confidence="high")

        conflicts = get_conflicting_enrichments(conn, "test-1")
        assert conflicts[0]["confidence"] == "high"

    def test_format_shows_field_and_values(self):
        conflicts = [
            {
                "field": "quality_notes",
                "value": "hyvä",
                "confidence": "high",
                "created_at": "2025-01-01",
            },
            {
                "field": "quality_notes",
                "value": "huono",
                "confidence": "low",
                "created_at": "2025-02-01",
            },
        ]
        result = format_conflicts(conflicts)
        assert "Ristiriitaiset" in result
        assert "Laatuhuomiot" in result
        assert "hyvä" in result
        assert "huono" in result

    def test_detail_shows_conflicts(self):
        dataset = {"title_fi": "Testi", "name": "testi-1"}
        conflicts = [
            {
                "field": "quality_notes",
                "value": "arvo1",
                "confidence": "high",
                "created_at": "2025-01-01",
            },
            {
                "field": "quality_notes",
                "value": "arvo2",
                "confidence": "medium",
                "created_at": "2025-02-01",
            },
        ]
        result = format_dataset_detail(dataset, conflicts=conflicts)
        assert "Ristiriitaiset" in result


class TestStaleEnrichments:
    """get_stale_enrichments()."""

    def test_stale_when_dataset_is_newer(self):
        conn = _memory_db()
        ds = Dataset(
            id="test-1", name="test-1", title="Test",
            metadata_modified="2020-01-01T00:00:00",
        )
        upsert_dataset(conn, ds)
        conn.commit()
        conn.execute(
            """
            INSERT INTO enrichments (id, dataset_id, field, value,
                source_type, created_at)
            VALUES ('e1', 'test-1', 'quality_notes', 'vanha',
                'mcp_session', '2019-01-01T00:00:00')
            """
        )
        conn.commit()

        stale = get_stale_enrichments(conn, "test-1")
        assert len(stale) == 1
        assert stale[0]["id"] == "e1"

    def test_format_shows_stale_marker(self):
        enrichments = [
            {
                "id": "stale-1",
                "field": "quality_notes",
                "value": "vanha",
                "confidence": "medium",
                "source_type": "mcp_session",
            }
        ]
        result = format_enrichments(enrichments, stale_ids={"stale-1"})
        assert "[vanhentunut]" in result


class TestPruneEnrichments:
    """prune_enrichments()."""

    def test_prunes_old_enrichments(self):
        conn = _memory_db()
        conn.execute(
            """
            INSERT INTO enrichments (id, dataset_id, field, value,
                source_type, created_at)
            VALUES ('old1', 'test-1', 'quality_notes', 'vanha',
                'mcp_session', '2020-01-01T00:00:00')
            """
        )
        add_enrichment(conn, "test-1", "use_case", "tuore")

        count = prune_enrichments(conn, older_than_days=365)
        assert count == 1

        remaining = conn.execute("SELECT * FROM enrichments").fetchall()
        assert len(remaining) == 1
        assert remaining[0]["field"] == "use_case"


class TestEnrichmentSearch:
    """search_datasets() löytää datasettejä enrichment-avainsanoilla."""

    def test_finds_dataset_by_enrichment_keyword(self):
        conn = _memory_db()
        _seed_dataset(conn, "ds-1")
        add_enrichment(
            conn, "ds-1", "keywords",
            '["maatalous", "peltolohko"]',
        )

        results = search_datasets(conn, "peltolohko")
        assert len(results) >= 1
        assert any(r["id"] == "ds-1" for r in results)

    def test_finds_dataset_by_enrichment_tag(self):
        conn = _memory_db()
        _seed_dataset(conn, "ds-2")
        add_enrichment(
            conn, "ds-2", "tags",
            '["paikkatietoaineisto", "INSPIRE"]',
        )

        results = search_datasets(conn, "INSPIRE")
        assert len(results) >= 1
        assert any(r["id"] == "ds-2" for r in results)

    def test_fts_results_come_before_enrichment_results(self):
        """FTS-osumat tulevat ennen enrichment-osumia."""
        conn = _memory_db()
        ds_fts = Dataset(
            id="ds-fts", name="ds-fts",
            title="peltolohko", title_fi="peltolohko",
        )
        upsert_dataset(conn, ds_fts)
        ds_enrich = Dataset(
            id="ds-enrich", name="ds-enrich", title="Muu datasetti",
        )
        upsert_dataset(conn, ds_enrich)
        conn.commit()
        add_enrichment(
            conn, "ds-enrich", "keywords", '["peltolohko"]',
        )

        results = search_datasets(conn, "peltolohko")
        ids = [r["id"] for r in results]
        assert "ds-fts" in ids
        assert "ds-enrich" in ids
        assert ids.index("ds-fts") < ids.index("ds-enrich")

    def test_no_duplicates_when_fts_and_enrichment_match(self):
        """Sama datasetti ei tule tuloksiin kahdesti."""
        conn = _memory_db()
        ds = Dataset(
            id="ds-both", name="ds-both",
            title="ilmanlaatu", title_fi="ilmanlaatu",
        )
        upsert_dataset(conn, ds)
        conn.commit()
        add_enrichment(
            conn, "ds-both", "keywords", '["ilmanlaatu"]',
        )

        results = search_datasets(conn, "ilmanlaatu")
        ds_ids = [r["id"] for r in results]
        assert ds_ids.count("ds-both") == 1


class TestMigration:
    """Migraatio luo enrichments-taulun."""

    def test_table_and_indexes_exist(self):
        conn = _memory_db()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert "enrichments" in [t["name"] for t in tables]

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [i["name"] for i in indexes]
        assert "idx_enrichments_dataset" in index_names
        assert "idx_enrichments_dataset_field" in index_names
