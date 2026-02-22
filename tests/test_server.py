"""Testit MCP-palvelimelle."""

import sqlite3
from unittest.mock import patch

import pytest

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import (
    _resolve_region,
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
    lookup_municipality,
    quality_gaps,
    quality_overview,
    quality_ranking,
    quality_report,
    recommend,
    reference_status,
    reset_findings,
    save_session_findings,
    search,
    search_by_region,
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


class TestGetConn:
    """_get_conn() singleton-fallback testit."""

    def test_fallback_returns_singleton(self) -> None:
        """Ilman kontekstia _get_conn palauttaa saman yhteyden (#86)."""
        import aura.server as srv

        old = srv._module_conn
        srv._module_conn = None
        try:
            conn1 = srv._get_conn(None)
            conn2 = srv._get_conn(None)
            assert conn1 is conn2
        finally:
            if srv._module_conn is not None:
                srv._module_conn.close()
            srv._module_conn = old


class TestSearch:
    """search()-työkalun testit."""

    @pytest.mark.asyncio
    async def test_search_finds_results(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("väestö")
        assert "Helsingin väestö" in result

    @pytest.mark.asyncio
    async def test_search_with_limit(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("helsinki", limit=1)
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

    @pytest.mark.asyncio
    async def test_search_filter_by_source(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("helsinki", source="avoindata.fi")
        assert "Helsingin väestö" in result

    @pytest.mark.asyncio
    async def test_search_filter_by_source_excludes(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("joukkoliikenne", source="avoindata.fi")
        assert "Ei tuloksia" in result

    @pytest.mark.asyncio
    async def test_search_filter_by_format(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("väestö", format="CSV")
        assert "Helsingin väestö" in result

    @pytest.mark.asyncio
    async def test_search_filter_by_organization(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("joukkoliikenne", organization="HSL")
        assert "HSL" in result
        assert "joukkoliikenne" in result.lower()


class TestSearchStructured:
    """search_structured()-työkalun testit."""

    @pytest.mark.asyncio
    async def test_returns_json(self) -> None:
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured("väestö")
        data = json.loads(result)
        assert data["query"] == "väestö"
        assert data["count"] >= 1
        assert data["results"][0]["title"] == "Helsingin väestö"

    @pytest.mark.asyncio
    async def test_structured_with_filters(self) -> None:
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured("väestö", source="avoindata.fi")
        data = json.loads(result)
        assert all(r["source"] == "avoindata.fi" for r in data["results"])


class TestRecommend:
    """recommend()-työkalun testit."""

    @pytest.mark.asyncio
    async def test_recommend_finds_results(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._expand_with_yso", return_value=""):
            result = await recommend("väestö")
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

    def test_enrich_dataset_not_found(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("no-such-ds", "use_case", "x")
        assert "ei löytynyt" in result

    def test_enrich_value_too_long(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = enrich("test-1", "use_case", "x" * 10_001)
        assert "merkkiä" in result

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
        reset_findings()
        with patch("aura.server._get_conn"):
            result = log_finding("test-1", "Data on CSV-muodossa")
        assert "kirjattu" in result.lower()
        assert "1 session" in result
        reset_findings()

    def test_log_finding_invalid_category(self) -> None:
        reset_findings()
        result = log_finding("test-1", "x", category="invalid")
        assert "Tuntematon kategoria" in result
        reset_findings()

    def test_log_finding_accumulates(self) -> None:
        reset_findings()
        log_finding("test-1", "Löydös 1")
        result = log_finding("test-1", "Löydös 2")
        assert "2 session" in result
        reset_findings()


class TestListFindings:
    """list_findings()-työkalun testit."""

    def test_empty_findings(self) -> None:
        reset_findings()
        result = list_findings()
        assert "Ei löydöksiä" in result

    def test_list_findings_grouped(self) -> None:
        reset_findings()
        log_finding("ds-1", "Löydös A", category="quality")
        log_finding("ds-2", "Löydös B", category="access")
        result = list_findings()
        assert "ds-1" in result
        assert "ds-2" in result
        assert "quality" in result
        assert "access" in result
        reset_findings()


class TestSaveSessionFindings:
    """save_session_findings()-työkalun testit."""

    def test_save_empty(self) -> None:
        reset_findings()
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = save_session_findings()
        assert "Ei löydöksiä" in result

    def test_save_findings_to_enrichments(self) -> None:
        reset_findings()
        conn = _memory_db()
        _seed_db(conn)
        log_finding("test-1", "Datan laatu on hyvä", category="quality")
        with patch("aura.server._get_conn", return_value=conn):
            result = save_session_findings()
        assert "Tallennettu 1" in result
        assert "quality_notes" in result
        # Findings should be cleared
        from aura.server import _fallback_findings
        assert len(_fallback_findings) == 0

    def test_save_deduplicates(self) -> None:
        reset_findings()
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
        reset_findings()


# --- Viitedatatyökalut ---


def _seed_ref_data(conn: sqlite3.Connection) -> None:
    """Populoi viiteaineistojen testitiedot."""
    conn.execute(
        "INSERT OR REPLACE INTO ref_metadata (name, record_count, version, populated_at) VALUES (?, ?, ?, ?)",
        ("municipalities", 3, "20260101", "2026-01-01 00:00:00"),
    )
    conn.execute(
        "INSERT OR REPLACE INTO ref_metadata (name, record_count, version, populated_at) VALUES (?, ?, ?, ?)",
        ("postal_codes", 3, "20260101", "2026-01-01 00:00:00"),
    )
    for code, name_fi, name_sv, region, ely, wa in [
        ("091", "Helsinki", "Helsingfors", "Uusimaa", "Uusimaa", "Helsinki"),
        ("049", "Espoo", "Esbo", "Uusimaa", "Uusimaa", "Länsi-Uusimaa"),
        ("837", "Tampere", "Tammerfors", "Pirkanmaa", "Pirkanmaa", "Pirkanmaa"),
    ]:
        conn.execute(
            "INSERT OR REPLACE INTO ref_municipalities "
            "(code, name_fi, name_sv, region_code, region_name_fi, ely_code, ely_name_fi, wellbeing_area_code, wellbeing_area_name_fi) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code, name_fi, name_sv, "01", region, "01", ely, "01", wa),
        )
    for postal_code, name_fi, name_sv, muni_code in [
        ("00100", "Helsinki", "Helsingfors", "091"),
        ("02100", "Espoo", "Esbo", "049"),
        ("33100", "Tampere", "Tammerfors", "837"),
    ]:
        conn.execute(
            "INSERT OR REPLACE INTO ref_postal_codes (code, name_fi, name_sv, municipality_code) VALUES (?, ?, ?, ?)",
            (postal_code, name_fi, name_sv, muni_code),
        )
    conn.commit()


class TestReferenceStatus:
    """reference_status()-työkalun testit."""

    def test_status_no_data(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = reference_status()
        assert "ei ladattu" in result

    def test_status_with_data(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = reference_status()
        assert "3 tietuetta" in result
        assert "2026-01-01" in result


class TestLookupMunicipality:
    """lookup_municipality()-työkalun testit."""

    def test_lookup_not_populated(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("Helsinki")
        assert "ei ole ladattu" in result

    def test_lookup_by_name(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("Helsinki")
        assert "Helsinki" in result
        assert "091" in result
        assert "Uusimaa" in result

    def test_lookup_by_code(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("91")
        assert "Helsinki" in result

    def test_lookup_by_postal(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("33100")
        assert "Tampere" in result
        assert "33100" in result

    def test_lookup_not_found(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("Gotham")
        assert "ei löytynyt" in result

    def test_lookup_partial_name(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("Esp")
        assert "Espoo" in result

    def test_lookup_unknown_postal(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = lookup_municipality("99999")
        assert "ei löytynyt" in result


class TestResolveRegion:
    """_resolve_region()-apufunktion testit."""

    def test_resolve_no_ref_data(self) -> None:
        conn = _memory_db()
        assert _resolve_region(conn, "Helsinki") == []

    def test_resolve_postal(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        result = _resolve_region(conn, "00100")
        assert result == ["Helsinki"]

    def test_resolve_municipality_code(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        result = _resolve_region(conn, "91")
        assert result == ["Helsinki"]

    def test_resolve_region_name(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        result = _resolve_region(conn, "Uusimaa")
        assert set(result) == {"Helsinki", "Espoo"}

    def test_resolve_ely(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        result = _resolve_region(conn, "Pirkanmaa")
        assert "Tampere" in result

    def test_resolve_wellbeing_area(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        result = _resolve_region(conn, "Länsi-Uusimaa")
        assert result == ["Espoo"]

    def test_resolve_municipality_name(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        result = _resolve_region(conn, "Tampere")
        assert "Tampere" in result

    def test_resolve_unknown(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        assert _resolve_region(conn, "Atlantis") == []


class TestBuildRegionQuery:
    """_build_region_query()-apufunktion testit."""

    def test_without_fts(self) -> None:
        from aura.tools.search import _build_region_query
        sql, params = _build_region_query(["Helsinki", "Espoo"], None, 10)
        assert "LIKE ?" in sql
        assert sql.count("LIKE ?") == 2
        assert params == ["%Helsinki%", "%Espoo%", 10]
        assert "MATCH" not in sql

    def test_with_fts(self) -> None:
        from aura.tools.search import _build_region_query
        sql, params = _build_region_query(["Tampere"], "liikenne", 5)
        assert "MATCH ?" in sql
        assert "LIKE ?" in sql
        assert params == ["liikenne", "%Tampere%", "liikenne", 5]


class TestSearchByRegion:
    """search_by_region()-työkalun testit."""

    @pytest.mark.asyncio
    async def test_search_region_no_results(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_by_region("Helsinki")
        assert "Ei datasettejä" in result

    @pytest.mark.asyncio
    async def test_search_region_with_coverage(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        # Lisää datasetti jolla geographical_coverage sisältää "Helsinki"
        upsert_dataset(
            conn,
            Dataset(
                id="geo-1",
                name="hki-data",
                title="Helsinki-data",
                title_fi="Helsinki-data",
                geographical_coverage=["Helsinki"],
                source="test",
                num_resources=0,
            ),
        )
        conn.commit()
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_by_region("Helsinki")
        assert "Helsinki-data" in result

    @pytest.mark.asyncio
    async def test_search_region_with_query(self) -> None:
        conn = _memory_db()
        _seed_ref_data(conn)
        upsert_dataset(
            conn,
            Dataset(
                id="geo-2",
                name="hki-vaesto",
                title="Helsingin väestö alueella",
                title_fi="Helsingin väestö alueella",
                notes_fi="Väestötilastot",
                geographical_coverage=["Helsinki"],
                source="test",
                num_resources=0,
            ),
        )
        conn.commit()
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_by_region("Helsinki", query="väestö")
        assert "väestö" in result.lower()

    @pytest.mark.asyncio
    async def test_search_region_fallback_no_ref_data(self) -> None:
        """Tuntematon alue käyttää nimeä sellaisenaan."""
        conn = _memory_db()
        upsert_dataset(
            conn,
            Dataset(
                id="geo-3",
                name="suomi-data",
                title="Suomi-data",
                title_fi="Suomi-data",
                geographical_coverage=["Suomi"],
                source="test",
                num_resources=0,
            ),
        )
        conn.commit()
        # Ei ref-dataa → _resolve_region palauttaa [] → fallback "Suomi"-nimeen
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_by_region("Suomi")
        assert "Suomi-data" in result


class TestStructuralVerification:
    """Rakenteelliset testit — verifioivat oikeat arvot, ei pelkkiä merkkijonoja."""

    @pytest.mark.asyncio
    async def test_structured_result_count(self) -> None:
        """search_structured palauttaa oikean tulosmäärän."""
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured("väestö")
        data = json.loads(result)
        assert data["count"] == 1
        assert len(data["results"]) == 1

    @pytest.mark.asyncio
    async def test_structured_result_fields(self) -> None:
        """search_structured palauttaa kaikki odotetut kentät."""
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured("väestö")
        item = json.loads(result)["results"][0]
        assert item["title"] == "Helsingin väestö"
        assert item["source"] == "avoindata.fi"
        assert item["organization"] == "Helsingin kaupunki"
        assert item["name"] == "helsingin-vaesto"
        assert item["num_resources"] == 1

    @pytest.mark.asyncio
    async def test_structured_source_filter_exclusive(self) -> None:
        """Lähdesuodatin palauttaa vain oikean lähteen datasettejä."""
        import json

        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured(
                "helsinki", source="hri.fi",
            )
        data = json.loads(result)
        for r in data["results"]:
            assert r["source"] == "hri.fi"

    @pytest.mark.asyncio
    async def test_structured_empty_results(self) -> None:
        """Tyhjä tietokanta palauttaa 0 tulosta, ei virhettä."""
        import json

        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured("nonexistent")
        data = json.loads(result)
        assert data["count"] == 0
        assert data["results"] == []

    def test_describe_contains_resource_details(self) -> None:
        """describe() näyttää resurssien formaatit ja URL:t."""
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = describe("test-1")
        assert "CSV" in result
        assert "vaesto.csv" in result
        assert "Helsingin kaupunki" in result
        assert "cc-by-4.0" in result.lower() or "CC BY 4.0" in result

    def test_describe_enrichment_gaps_shown(self) -> None:
        """describe() näyttää puuttuvat enrichment-kentät."""
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = describe("test-1")
        assert "Puuttuvat tiedot" in result

    def test_compare_shows_all_datasets(self) -> None:
        """compare() näyttää kaikkien datasettien tiedot."""
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = compare(["test-1", "test-2"])
        assert "Helsingin väestö" in result
        assert "Joukkoliikenteen reitit" in result
        assert "avoindata.fi" in result
        assert "hri.fi" in result
        assert "2 kpl" in result

    @pytest.mark.asyncio
    async def test_search_no_results_message(self) -> None:
        """Tyhjä hakutulos antaa selkeän viestin."""
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = await search("eioleolemasskaan")
        assert "Ei tuloksia" in result

    @pytest.mark.asyncio
    async def test_recommend_empty_db(self) -> None:
        """Tyhjä tietokanta antaa selkeän viestin."""
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._expand_with_yso", return_value=""):
            result = await recommend("liikenne")
        assert "Ei datasettejä" in result

    def test_describe_by_name(self) -> None:
        """describe() löytää datasetin nimellä (ei pelkkä id)."""
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = describe("helsingin-vaesto")
        assert "Helsingin väestö" in result

    def test_enrich_validates_dataset_exists(self) -> None:
        """enrich() palauttaa virheen jos datasettiä ei ole."""
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = enrich(
                dataset_id="ei-ole",
                field="use_case",
                value="testi",
            )
        assert "ei löytynyt" in result.lower()
