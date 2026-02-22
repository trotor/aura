"""Testit MCP-palvelimelle."""

import sqlite3
from unittest.mock import patch

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import (
    batch_enrich,
    compare,
    describe,
    enrich,
    find_related,
    get_enrichments_tool,
    list_findings,
    list_formats,
    list_organizations,
    list_sources,
    log_finding,
    quality_gaps,
    quality_overview,
    quality_ranking,
    quality_report,
    recommend,
    save_session_findings,
    search,
    search_structured,
    stats,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_db(conn: sqlite3.Connection) -> None:
    """Lisää testidatasetit tietokantaan."""
    upsert_dataset(
        conn,
        Dataset(
            id="test-1",
            name="helsingin-vaesto",
            title="Helsingin väestö",
            title_fi="Helsingin väestö",
            notes_fi="Väestötilastot",
            organization_title="Helsingin kaupunki",
            organization_name="helsinki",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            keywords_fi=["väestö", "helsinki"],
            collection_type="Open Data",
            source="avoindata.fi",
            num_resources=1,
            resources=[
                Resource(
                    id="res-1",
                    name="vaesto.csv",
                    format="CSV",
                    url="https://example.com/vaesto.csv",
                ),
            ],
        ),
    )
    upsert_dataset(
        conn,
        Dataset(
            id="test-2",
            name="joukkoliikenne",
            title="Joukkoliikenne",
            title_fi="Joukkoliikenteen reitit",
            notes_fi="HSL:n joukkoliikennedata",
            organization_title="HSL",
            organization_name="hsl",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            keywords_fi=["joukkoliikenne", "hsl"],
            collection_type="Open Data",
            source="hri.fi",
            num_resources=1,
            resources=[
                Resource(
                    id="res-2",
                    name="reitit.json",
                    format="JSON",
                    url="https://example.com/reitit.json",
                ),
            ],
        ),
    )
    conn.commit()


class TestSearch:
    """search()-työkalun testit."""

    def test_search_finds_results(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search("väestö")
        assert "Helsingin väestö" in result

    def test_search_with_limit(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search("helsinki", limit=1)
        assert "Helsingin" in result


class TestDescribe:
    """describe()-työkalun testit."""

    def test_describe_found(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = describe("test-1")
        assert "Helsingin väestö" in result
        assert "vaesto.csv" in result

    def test_describe_not_found(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = describe("ei-olemassa")
        assert "ei löytynyt" in result


class TestStats:
    """stats()-työkalun testit."""

    def test_stats_with_data(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = stats()
        assert "2" in result


class TestListOrganizations:
    """list_organizations()-työkalun testit."""

    def test_list_organizations(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = list_organizations()
        assert "Helsingin kaupunki" in result
        assert "HSL" in result


class TestListFormats:
    """list_formats()-työkalun testit."""

    def test_list_formats(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = list_formats()
        assert "CSV" in result
        assert "JSON" in result


class TestListSources:
    """list_sources()-työkalun testit."""

    def test_list_sources(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = list_sources()
        assert "avoindata.fi" in result
        assert "1 datasettiä" in result


class TestSearchFilters:
    """search()-suodattimien testit."""

    def test_search_filter_by_source(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search("helsinki", source="avoindata.fi")
        assert "Helsingin väestö" in result

    def test_search_filter_by_source_excludes(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search("joukkoliikenne", source="avoindata.fi")
        assert "Ei tuloksia" in result

    def test_search_filter_by_format(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search("väestö", format="CSV")
        assert "Helsingin väestö" in result

    def test_search_filter_by_organization(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search("joukkoliikenne", organization="HSL")
        assert "HSL" in result
        assert "joukkoliikenne" in result.lower()


class TestSearchStructured:
    """search_structured()-työkalun testit."""

    def test_returns_json(self) -> None:
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search_structured("väestö")
        data = json.loads(result)
        assert data["query"] == "väestö"
        assert data["count"] >= 1
        assert data["results"][0]["title"] == "Helsingin väestö"

    def test_structured_with_filters(self) -> None:
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = search_structured("väestö", source="avoindata.fi")
        data = json.loads(result)
        assert all(r["source"] == "avoindata.fi" for r in data["results"])


class TestRecommend:
    """recommend()-työkalun testit."""

    def test_recommend_finds_results(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = recommend("väestö")
        assert "Suositellut" in result
        assert "Helsingin väestö" in result


class TestCompare:
    """compare()-työkalun testit."""

    def test_compare_two_datasets(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = compare(["test-1", "test-2"])
        assert "vertailu" in result.lower()
        assert "Helsingin väestö" in result
        assert "joukkoliikenne" in result.lower()
        assert "CSV" in result
        assert "JSON" in result


class TestFindRelated:
    """find_related()-työkalun testit."""

    def test_find_related_by_keywords(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        upsert_dataset(
            conn,
            Dataset(
                id="test-3",
                name="espoon-vaesto",
                title="Espoon väestö",
                title_fi="Espoon väestö",
                notes_fi="Espoon väestötilastot",
                organization_title="Espoon kaupunki",
                keywords_fi=["väestö", "espoo"],
                source="avoindata.fi",
                num_resources=0,
            ),
        )
        conn.commit()
        with patch("aura.server._get_conn", return_value=conn):
            result = find_related("test-1")
        assert "Samankaltaiset" in result
        assert "Espoon väestö" in result


class TestEnrich:
    """enrich()-työkalun testit."""

    def test_enrich_valid(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("test-1", "use_case", "Tutkimus")
        assert "tallennettu" in result.lower()
        assert "test-1" in result

    def test_enrich_invalid_field(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("test-1", "invalid_field", "value")
        assert "Tuntematon kenttä" in result

    def test_enrich_invalid_confidence(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("test-1", "use_case", "x", confidence="wrong")
        assert "Virheellinen luottamustaso" in result

    def test_enrich_persists(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            enrich("test-1", "use_case", "Analyysi", confidence="high")
            result = get_enrichments_tool("test-1")
        assert "Analyysi" in result


class TestBatchEnrich:
    """batch_enrich()-työkalun testit."""

    def test_batch_enrich_multiple(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = batch_enrich([
                {"dataset_id": "test-1", "field": "use_case", "value": "Tutkimus"},
                {"dataset_id": "test-2", "field": "quality_notes", "value": "Hyvä"},
            ])
        assert "Tallennettu 2" in result

    def test_batch_enrich_with_errors(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = batch_enrich([
                {"dataset_id": "", "field": "use_case", "value": "x"},
                {"dataset_id": "test-1", "field": "bad_field", "value": "x"},
            ])
        assert "Virheet" in result
        assert "puuttuva" in result
        assert "tuntematon" in result

    def test_batch_enrich_empty(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = batch_enrich([])
        assert "Ei rikastuksia" in result


class TestGetEnrichmentsTool:
    """get_enrichments_tool()-testit."""

    def test_no_enrichments(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = get_enrichments_tool("test-1")
        assert "Ei rikastuksia" in result

    def test_with_enrichments(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            enrich("test-1", "use_case", "Kaupunkisuunnittelu")
            result = get_enrichments_tool("test-1")
        assert "Kaupunkisuunnittelu" in result


class TestQualityReport:
    """quality_report()-työkalun testit."""

    def test_quality_report_found(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = quality_report("test-1")
        assert "Laatuarvio" in result
        assert "/100" in result

    def test_quality_report_not_found(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = quality_report("ei-olemassa")
        assert "ei löytynyt" in result


class TestQualityOverview:
    """quality_overview()-työkalun testit."""

    def test_overview_no_scores(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = quality_overview()
        assert "ei löytynyt" in result.lower() or "Ei" in result

    def test_overview_with_scores(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        # Calculate quality first
        with patch("aura.server._get_conn", return_value=conn):
            quality_report("test-1")
            quality_report("test-2")
            result = quality_overview()
        assert "Keskiarvo" in result
        assert "Mediaani" in result


class TestQualityRanking:
    """quality_ranking()-työkalun testit."""

    def test_ranking_invalid_dimension(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = quality_ranking(dimension="invalid")
        assert "Tuntematon dimensio" in result

    def test_ranking_with_data(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            quality_report("test-1")
            result = quality_ranking(dimension="overall")
        assert "/100" in result


class TestQualityGaps:
    """quality_gaps()-työkalun testit."""

    def test_gaps_analysis(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = quality_gaps()
        assert "puutteet" in result.lower() or "Metatiedon" in result


class TestCompareEdgeCases:
    """compare()-reunatapausten testit."""

    def test_compare_too_few(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = compare(["test-1"])
        assert "vähintään 2" in result

    def test_compare_too_many(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = compare(["a", "b", "c", "d", "e", "f"])
        assert "korkeintaan 5" in result

    def test_compare_not_found(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = compare(["no-1", "no-2"])
        assert "ei löytynyt" in result.lower()


class TestLogFinding:
    """log_finding()-työkalun testit."""

    def test_log_finding_basic(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        with patch("aura.server._get_conn"):
            result = log_finding("test-1", "Data on CSV-muodossa")
        assert "kirjattu" in result.lower()
        assert "1 session" in result
        srv._fallback_findings.clear()

    def test_log_finding_invalid_category(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        result = log_finding("test-1", "x", category="invalid")
        assert "Tuntematon kategoria" in result
        srv._fallback_findings.clear()

    def test_log_finding_accumulates(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        log_finding("test-1", "Löydös 1")
        result = log_finding("test-1", "Löydös 2")
        assert "2 session" in result
        srv._fallback_findings.clear()


class TestListFindings:
    """list_findings()-työkalun testit."""

    def test_empty_findings(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        result = list_findings()
        assert "Ei löydöksiä" in result

    def test_list_findings_grouped(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        log_finding("ds-1", "Löydös A", category="quality")
        log_finding("ds-2", "Löydös B", category="access")
        result = list_findings()
        assert "ds-1" in result
        assert "ds-2" in result
        assert "quality" in result
        assert "access" in result
        srv._fallback_findings.clear()


class TestSaveSessionFindings:
    """save_session_findings()-työkalun testit."""

    def test_save_empty(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = save_session_findings()
        assert "Ei löydöksiä" in result

    def test_save_findings_to_enrichments(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        conn = _memory_db()
        _seed_db(conn)
        log_finding("test-1", "Datan laatu on hyvä", category="quality")
        with patch("aura.server._get_conn", return_value=conn):
            result = save_session_findings()
        assert "Tallennettu 1" in result
        assert "quality_notes" in result
        # Findings should be cleared
        assert len(srv._fallback_findings) == 0

    def test_save_deduplicates(self) -> None:
        import aura.server as srv
        srv._fallback_findings.clear()
        conn = _memory_db()
        _seed_db(conn)
        # Save once
        log_finding("test-1", "Laatu OK", category="quality")
        with patch("aura.server._get_conn", return_value=conn):
            save_session_findings()
        # Save same again
        log_finding("test-1", "Laatu OK", category="quality")
        with patch("aura.server._get_conn", return_value=conn):
            result = save_session_findings()
        assert "duplikaatti" in result.lower()
        srv._fallback_findings.clear()
