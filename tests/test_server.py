"""Testit MCP-palvelimelle."""

import sqlite3
from unittest.mock import patch

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import (
    compare,
    describe,
    find_related,
    list_formats,
    list_organizations,
    list_sources,
    recommend,
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

    def test_search_no_results(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = search("eioleolemassakaan")
        assert "Ei tuloksia" in result

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

    def test_stats_empty(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = stats()
        assert "0" in result

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

    def test_list_organizations_empty(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = list_organizations()
        assert "tyhjä" in result


class TestListFormats:
    """list_formats()-työkalun testit."""

    def test_list_formats(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = list_formats()
        assert "CSV" in result
        assert "JSON" in result

    def test_list_formats_empty(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = list_formats()
        assert "tyhjä" in result


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

    def test_search_with_offset(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            # Offset beyond results returns empty
            result = search("väestö", offset=100)
        assert "Ei tuloksia" in result


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

    def test_structured_empty(self) -> None:
        import json

        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = search_structured("eioleolemassakaan")
        data = json.loads(result)
        assert data["count"] == 0
        assert data["results"] == []


class TestRecommend:
    """recommend()-työkalun testit."""

    def test_recommend_finds_results(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = recommend("väestö")
        assert "Suositellut" in result
        assert "Helsingin väestö" in result

    def test_recommend_no_results(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = recommend("eioleolemassakaan")
        assert "Ei datasettejä" in result


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
            result = compare(["ei-olemassa", "ei-toinen"])
        assert "ei löytynyt" in result


class TestFindRelated:
    """find_related()-työkalun testit."""

    def test_find_related_by_keywords(self) -> None:
        conn = _memory_db()
        _seed_db(conn)
        # Lisää kolmas datasetti samalla avainsanalla
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

    def test_find_related_not_found(self) -> None:
        conn = _memory_db()
        with patch("aura.server._get_conn", return_value=conn):
            result = find_related("ei-olemassa")
        assert "ei löytynyt" in result
