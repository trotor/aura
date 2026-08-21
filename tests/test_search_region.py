"""Testit alueelliselle hakusuodattimelle (region-parametri)."""

import json
import sqlite3

from aura.database import (
    _normalize_geo_coverage,
    init_db,
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


def _dataset_with_coverage(
    ds_id: str, name: str, title: str, coverage: list[str]
) -> Dataset:
    return Dataset(
        id=ds_id,
        name=name,
        title=title,
        title_fi=title,
        notes_fi=f"Kuvaus: {title}",
        organization_id="org-1",
        organization_name="org",
        organization_title="Org",
        license_id="cc-by-4.0",
        geographical_coverage=coverage,
        keywords_fi=["testi"],
        num_resources=1,
        resources=[
            Resource(id=f"res-{ds_id}", name="data.csv", format="CSV", url="https://example.com/data.csv")
        ],
    )


class TestSearchWithRegionFilter:
    """Testit search_datasets() region_names -parametrille."""

    def test_search_with_region_filter(self) -> None:
        conn = _memory_db()
        upsert_dataset(
            conn, _dataset_with_coverage("ds-1", "hki-data", "Helsinki data", ["Helsinki"])
        )
        upsert_dataset(
            conn, _dataset_with_coverage("ds-2", "tre-data", "Tampere data", ["Tampere"])
        )
        conn.commit()

        results = search_datasets(conn, "testi", region_names=["Helsinki"])
        assert len(results) == 1
        assert results[0]["id"] == "ds-1"

    def test_region_filter_multiple_names(self) -> None:
        conn = _memory_db()
        upsert_dataset(
            conn, _dataset_with_coverage("ds-1", "hki-data", "Helsinki data", ["Helsinki"])
        )
        upsert_dataset(
            conn, _dataset_with_coverage("ds-2", "espoo-data", "Espoo data", ["Espoo"])
        )
        upsert_dataset(
            conn, _dataset_with_coverage("ds-3", "tre-data", "Tampere data", ["Tampere"])
        )
        conn.commit()

        # Simuloi maakunnan resolvointia: "Uusimaa" → [Helsinki, Espoo]
        results = search_datasets(conn, "testi", region_names=["Helsinki", "Espoo"])
        assert len(results) == 2
        result_ids = {r["id"] for r in results}
        assert result_ids == {"ds-1", "ds-2"}

    def test_empty_region_returns_all(self) -> None:
        conn = _memory_db()
        upsert_dataset(
            conn, _dataset_with_coverage("ds-1", "hki-data", "Helsinki data", ["Helsinki"])
        )
        upsert_dataset(
            conn, _dataset_with_coverage("ds-2", "tre-data", "Tampere data", ["Tampere"])
        )
        conn.commit()

        results = search_datasets(conn, "testi", region_names=None)
        assert len(results) == 2

    def test_region_case_insensitive_via_like(self) -> None:
        """LIKE on SQLitessä oletuksena case-insensitive ASCII-merkeille."""
        conn = _memory_db()
        upsert_dataset(
            conn, _dataset_with_coverage("ds-1", "hki-data", "Helsinki data", ["Helsinki"])
        )
        conn.commit()

        results = search_datasets(conn, "testi", region_names=["helsinki"])
        assert len(results) == 1

    def test_region_with_other_filters(self) -> None:
        conn = _memory_db()
        upsert_dataset(
            conn, _dataset_with_coverage("ds-1", "hki-data", "Helsinki data", ["Helsinki"])
        )
        upsert_dataset(
            conn, _dataset_with_coverage("ds-2", "tre-data", "Tampere data", ["Tampere"])
        )
        conn.commit()

        # Region + source filter
        results = search_datasets(
            conn, "testi", region_names=["Helsinki"], source="nonexistent"
        )
        assert len(results) == 0


class TestNormalizeGeoCoverage:
    """Testit geographical_coverage -normalisoinnille."""

    def test_normalize_title_case(self) -> None:
        assert _normalize_geo_coverage(["turku", "HELSINKI", "espoo"]) == [
            "Turku", "Helsinki", "Espoo"
        ]

    def test_normalize_compound_name(self) -> None:
        result = _normalize_geo_coverage(["varsinais-suomi"])
        assert result == ["Varsinais-Suomi"]

    def test_normalize_already_correct(self) -> None:
        assert _normalize_geo_coverage(["Suomi", "Helsinki"]) == ["Suomi", "Helsinki"]

    def test_normalize_strips_whitespace(self) -> None:
        assert _normalize_geo_coverage([" turku ", "  "]) == ["Turku"]

    def test_normalize_empty_list(self) -> None:
        assert _normalize_geo_coverage([]) == []

    def test_upsert_normalizes_coverage(self) -> None:
        """upsert_dataset() normalisoi geographical_coverage automaattisesti."""
        conn = _memory_db()
        ds = _dataset_with_coverage("ds-norm", "norm-test", "Norm test", ["turku", "helsinki"])
        upsert_dataset(conn, ds)
        conn.commit()

        row = conn.execute(
            "SELECT geographical_coverage FROM datasets WHERE id = 'ds-norm'"
        ).fetchone()
        coverage = json.loads(row["geographical_coverage"])
        assert coverage == ["Turku", "Helsinki"]
