"""Testit area_profile- ja compare_municipalities-työkaluille."""

import sqlite3

import aura.server  # noqa: F401 — import server first to avoid circular import
from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.tools.area import (
    _categorize_datasets,
    _compute_area_stats,
    _compute_freshness,
    _detect_gaps,
    _normalize_title,
    area_profile,
    compare_municipalities,
)


def _memory_db() -> sqlite3.Connection:
    """Luo muistitietokanta testausta varten."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _make_dataset(
    ds_id: str,
    title: str,
    source: str = "avoindata.fi",
    coverage: list[str] | None = None,
    keywords: list[str] | None = None,
    modified: str = "2025-06-01T00:00:00",
) -> Dataset:
    return Dataset(
        id=ds_id,
        name=ds_id,
        title=title,
        title_fi=title,
        notes_fi=f"Kuvaus: {title}",
        source=source,
        organization_id="org-1",
        organization_name="org",
        organization_title="Testiorganisaatio",
        license_id="cc-by-4.0",
        geographical_coverage=coverage or ["Suomi"],
        keywords_fi=keywords or ["testi"],
        num_resources=1,
        metadata_modified=modified,
        resources=[
            Resource(
                id=f"res-{ds_id}",
                name="data.csv",
                format="CSV",
                url="https://example.com/data.csv",
            )
        ],
    )


class TestCategorizeDatasets:
    """Testit kategorisointifunktiolle."""

    def test_categorize_by_source(self) -> None:
        datasets = [
            {"title_fi": "Väestö", "source": "statfin", "keywords_fi": "[]"},
            {"title_fi": "Tieliikenne", "source": "digitraffic", "keywords_fi": "[]"},
        ]
        result = _categorize_datasets(datasets)
        assert "Tilastot" in result
        assert "Liikenne" in result
        assert len(result["Tilastot"]) == 1
        assert len(result["Liikenne"]) == 1

    def test_categorize_by_keyword(self) -> None:
        datasets = [
            {"title_fi": "Ilmanlaatu Helsinki", "source": "hri.fi", "keywords_fi": '["ympäristö"]'},
        ]
        result = _categorize_datasets(datasets)
        assert "Ympäristö" in result

    def test_uncategorized_goes_to_muu(self) -> None:
        datasets = [
            {"title_fi": "Jokin tuntematon aineisto", "source": "unknown", "keywords_fi": "[]"},
        ]
        result = _categorize_datasets(datasets)
        assert "Muu" in result


class TestDetectGaps:
    """Testit puuteiden tunnistamiselle."""

    def test_detects_missing_topics(self) -> None:
        datasets = [
            {"title_fi": "Väestötilasto", "keywords_fi": '["väestö"]'},
        ]
        gaps = _detect_gaps(datasets)
        # Väestö should NOT be a gap
        assert "Väestö" not in gaps
        # Other topics should be gaps
        assert "Talous" in gaps
        assert "Kaavoitus" in gaps

    def test_no_gaps_when_all_covered(self) -> None:
        datasets = [
            {"title_fi": "väestö asukas", "keywords_fi": "[]"},
            {"title_fi": "talous budjetti", "keywords_fi": "[]"},
            {"title_fi": "asemakaava", "keywords_fi": "[]"},
            {"title_fi": "joukkoliikenne", "keywords_fi": "[]"},
            {"title_fi": "ilmanlaatu ympäristö", "keywords_fi": "[]"},
            {"title_fi": "koulu oppilas", "keywords_fi": "[]"},
            {"title_fi": "terveys hyvinvointi", "keywords_fi": "[]"},
        ]
        gaps = _detect_gaps(datasets)
        assert gaps == []


class TestComputeFreshness:
    """Testit tuoreusanalyysille."""

    def test_fresh_datasets(self) -> None:
        datasets = [
            {"metadata_modified": "2025-06-01T00:00:00"},
            {"metadata_modified": "2025-12-01T00:00:00"},
        ]
        fresh, total = _compute_freshness(datasets)
        assert total == 2
        assert fresh == 2

    def test_old_datasets(self) -> None:
        datasets = [
            {"metadata_modified": "2020-01-01T00:00:00"},
        ]
        fresh, total = _compute_freshness(datasets)
        assert total == 1
        assert fresh == 0

    def test_no_date(self) -> None:
        datasets = [{"metadata_modified": ""}]
        fresh, total = _compute_freshness(datasets)
        assert total == 0
        assert fresh == 0


class TestAreaProfile:
    """Testit area_profile MCP-työkalulle."""

    def test_area_profile_returns_report(self) -> None:
        conn = _memory_db()
        upsert_dataset(conn, _make_dataset("ds-1", "Helsinki väestödata", coverage=["Helsinki"]))
        upsert_dataset(conn, _make_dataset(
            "ds-2", "Helsinki liikennedata", source="digitraffic", coverage=["Helsinki"],
        ))
        conn.commit()

        # Aseta _module_conn suoraan testissä (ei ctx)
        import aura.server as _server
        old = _server._module_conn
        _server._module_conn = conn
        try:
            result = area_profile("Helsinki")
        finally:
            _server._module_conn = old

        assert "Helsinki" in result
        assert "2 datasettiä" in result
        assert "Aiheittain" in result
        assert "Yhteenveto" in result

    def test_area_profile_no_results(self) -> None:
        conn = _memory_db()
        conn.commit()

        import aura.server as _server
        old = _server._module_conn
        _server._module_conn = conn
        try:
            result = area_profile("Tuntematon")
        finally:
            _server._module_conn = old

        assert "ei löytynyt" in result

    def test_area_profile_shows_gaps(self) -> None:
        conn = _memory_db()
        # Only statfin data — many topics should be missing
        upsert_dataset(conn, _make_dataset(
            "ds-stat", "Väestö 31.12.", source="statfin",
            coverage=["Tampere"], keywords=["väestö"],
        ))
        conn.commit()

        import aura.server as _server
        old = _server._module_conn
        _server._module_conn = conn
        try:
            result = area_profile("Tampere")
        finally:
            _server._module_conn = old

        assert "Puutteet" in result

    def test_area_profile_with_region_suomi(self) -> None:
        """Datasets with geographical_coverage=Suomi match any region fallback."""
        conn = _memory_db()
        upsert_dataset(conn, _make_dataset("ds-fi", "Koko Suomen data", coverage=["Suomi"]))
        conn.commit()

        import aura.server as _server
        old = _server._module_conn
        _server._module_conn = conn
        try:
            result = area_profile("Suomi")
        finally:
            _server._module_conn = old

        assert "1 datasettiä" in result


class TestNormalizeTitle:
    """Testit otsikon normalisoinnille."""

    def test_strips_municipality_names(self) -> None:
        ds = {"title_fi": "Tampere väestödata"}
        result = _normalize_title(ds, municipality_names=["Tampere", "Turku"])
        assert "tampere" not in result
        assert "väestödata" in result

    def test_strips_year_numbers(self) -> None:
        ds = {"title_fi": "Väestödata 2024"}
        result = _normalize_title(ds)
        assert "2024" not in result
        assert "väestödata" in result

    def test_same_dataset_different_municipality(self) -> None:
        """Two equivalent datasets from different municipalities should normalize the same."""
        ds_a = {"title_fi": "Tampere väestödata 2024"}
        ds_b = {"title_fi": "Turku väestödata 2025"}
        names = ["Tampere", "Turku"]
        assert _normalize_title(ds_a, names) == _normalize_title(ds_b, names)

    def test_normalizes_punctuation(self) -> None:
        ds = {"title_fi": "Pysäköinti - automaatit (reaaliaikainen)"}
        result = _normalize_title(ds)
        assert "-" not in result
        assert "(" not in result

    def test_empty_title(self) -> None:
        ds = {"title_fi": "", "title": "", "name": ""}
        assert _normalize_title(ds) == ""


class TestComputeAreaStats:
    """Testit _compute_area_stats-apufunktiolle."""

    def test_returns_expected_keys(self) -> None:
        conn = _memory_db()
        upsert_dataset(conn, _make_dataset("ds-1", "Testi", coverage=["Helsinki"]))
        conn.commit()

        rows = conn.execute("SELECT * FROM datasets").fetchall()
        datasets = [dict(row) for row in rows]

        stats = _compute_area_stats(conn, datasets)
        assert stats["total"] == 1
        assert "avg_quality" in stats
        assert "mr_pct" in stats
        assert "fresh_pct" in stats
        assert "gaps" in stats
        assert "categorized" in stats
        assert "dimension_avgs" in stats
        assert "org_count" in stats

    def test_empty_datasets(self) -> None:
        conn = _memory_db()
        stats = _compute_area_stats(conn, [])
        assert stats["total"] == 0
        assert stats["avg_quality"] == 0.0
        assert stats["mr_pct"] == 0
        assert stats["org_count"] == 0
        assert all(v == 0.0 for v in stats["dimension_avgs"].values())


class TestCompareMunicipalities:
    """Testit compare_municipalities-työkalulle."""

    def _setup_conn(self) -> tuple[sqlite3.Connection, object]:
        """Luo tietokanta ja aseta _module_conn."""
        import aura.server as _server
        conn = _memory_db()
        old = _server._module_conn
        _server._module_conn = conn
        return conn, old

    def _teardown(self, old: object) -> None:
        import aura.server as _server
        _server._module_conn = old

    def test_basic_comparison(self) -> None:
        conn, old = self._setup_conn()
        try:
            upsert_dataset(conn, _make_dataset(
                "ds-tre-1", "Tampere väestödata", coverage=["Tampere"],
            ))
            upsert_dataset(conn, _make_dataset(
                "ds-tku-1", "Turku väestödata", coverage=["Turku"],
            ))
            upsert_dataset(conn, _make_dataset(
                "ds-tku-2", "Turku liikennedata", source="digitraffic", coverage=["Turku"],
            ))
            conn.commit()

            result = compare_municipalities(["Tampere", "Turku"])

            assert "Kuntavertailu" in result
            assert "Tampere" in result
            assert "Turku" in result
            assert "Datasettejä" in result
            assert "Koneluettavia" in result
            assert "Organisaatioita" in result
            # Dimension labels should appear
            assert "Täydellisyys" in result
            assert "Ajantasaisuus" in result
            assert "Saavutettavuus" in result
            assert "Dokumentointi" in result
        finally:
            self._teardown(old)

    def test_too_few_municipalities(self) -> None:
        result = compare_municipalities(["Tampere"])
        assert "vähintään 2" in result

    def test_too_many_municipalities(self) -> None:
        result = compare_municipalities(["A", "B", "C", "D", "E", "F"])
        assert "korkeintaan 5" in result

    def test_shows_differences(self) -> None:
        conn, old = self._setup_conn()
        try:
            upsert_dataset(conn, _make_dataset(
                "ds-tre-1", "Kantakartta WFS", coverage=["Tampere"],
            ))
            upsert_dataset(conn, _make_dataset(
                "ds-tku-1", "Pysäköintiautomaatit", coverage=["Turku"],
            ))
            conn.commit()

            result = compare_municipalities(["Tampere", "Turku"])

            assert "Erot" in result
        finally:
            self._teardown(old)

    def test_normalize_deduplicates_same_dataset(self) -> None:
        """Same dataset with different municipality name should not show as diff."""
        conn, old = self._setup_conn()
        try:
            upsert_dataset(conn, _make_dataset(
                "ds-tre-1", "Tampere väestödata 2024", coverage=["Tampere"],
            ))
            upsert_dataset(conn, _make_dataset(
                "ds-tku-1", "Turku väestödata 2025", coverage=["Turku"],
            ))
            conn.commit()

            result = compare_municipalities(["Tampere", "Turku"])

            # Both have "väestödata" so after normalization no differences
            assert "samat datasetit" in result
        finally:
            self._teardown(old)

    def test_theme_filter(self) -> None:
        conn, old = self._setup_conn()
        try:
            upsert_dataset(conn, _make_dataset(
                "ds-tre-1", "Tampere liikennedata",
                coverage=["Tampere"], keywords=["liikenne"],
            ))
            upsert_dataset(conn, _make_dataset(
                "ds-tre-2", "Tampere väestödata",
                coverage=["Tampere"], keywords=["väestö"],
            ))
            upsert_dataset(conn, _make_dataset(
                "ds-tku-1", "Turku liikennedata",
                coverage=["Turku"], keywords=["liikenne"],
            ))
            conn.commit()

            result = compare_municipalities(["Tampere", "Turku"], theme="liikenne")

            assert "liikenne" in result
            # väestödata should be filtered out
            assert "väestö" not in result.lower().split("erot")[0] if "Erot" in result else True
        finally:
            self._teardown(old)

    def test_no_datasets_for_municipality(self) -> None:
        conn, old = self._setup_conn()
        try:
            upsert_dataset(conn, _make_dataset(
                "ds-tre-1", "Tampere data", coverage=["Tampere"],
            ))
            conn.commit()

            result = compare_municipalities(["Tampere", "Tuntematon"])

            assert "Kuntavertailu" in result
            assert "0" in result  # Tuntematon should have 0 datasets
        finally:
            self._teardown(old)
