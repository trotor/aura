"""Testit laatupisteytysmoduulille."""

import sqlite3

import pytest

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.quality import (
    calculate_accessibility,
    calculate_completeness,
    calculate_documentation,
    calculate_quality,
    calculate_timeliness,
    get_quality_scores,
    save_quality_scores,
    score_all_datasets,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _complete_dataset() -> dict:
    """Datasetti jossa kaikki kentät täytetty."""
    return {
        "id": "test-complete",
        "name": "test-complete",
        "title": "Test Dataset",
        "title_fi": "Testidatasetti",
        "title_en": "Test Dataset",
        "title_sv": "Testdatasätt",
        "notes": "Description",
        "notes_fi": "Tämä on riittävän pitkä kuvaus jotta se ylittää 50 merkin rajan helposti.",
        "notes_en": "This is a long enough description to pass the 50 char threshold easily.",
        "notes_sv": "",
        "license_id": "cc-by-4.0",
        "license_title": "CC BY 4.0",
        "organization_title": "Testorganisaatio",
        "metadata_modified": "2026-02-01T12:00:00",
        "keywords_fi": '["testi", "data", "avoin"]',
        "update_frequency": "kuukausittain",
        "access_level": "open",
        "num_resources": 3,
    }


def _empty_dataset() -> dict:
    """Datasetti jossa vain pakolliset kentät."""
    return {
        "id": "test-empty",
        "name": "test-empty",
        "title": "",
        "title_fi": "",
        "title_en": "",
        "title_sv": "",
        "notes": "",
        "notes_fi": "",
        "notes_en": "",
        "notes_sv": "",
        "license_id": "",
        "license_title": "",
        "organization_title": "",
        "metadata_modified": "",
        "keywords_fi": "[]",
        "update_frequency": "",
        "access_level": "",
        "num_resources": 0,
    }


def _resources() -> list[dict]:
    return [
        {"format": "CSV", "url": "https://example.com/data.csv"},
        {"format": "JSON", "url": "https://example.com/data.json"},
        {"format": "PDF", "url": "https://example.com/docs.pdf"},
    ]


class TestCompleteness:
    def test_complete_dataset_scores_100(self):
        score, details = calculate_completeness(_complete_dataset())
        assert score == pytest.approx(100.0)
        assert all(details.values())

    def test_empty_dataset_scores_0(self):
        score, details = calculate_completeness(_empty_dataset())
        assert score == pytest.approx(0.0)
        assert not any(details.values())

    def test_partial_dataset(self):
        d = _empty_dataset()
        d["title_fi"] = "Otsikko"
        d["organization_title"] = "Org"
        d["license_id"] = "cc-by-4.0"
        score, details = calculate_completeness(d)
        assert 40 < score < 60  # 3/6 fields = 50%
        assert details["title"] is True
        assert details["description"] is False


class TestTimeliness:
    def test_recent_scores_high(self):
        d = _complete_dataset()
        d["metadata_modified"] = "2026-02-20T12:00:00"
        score, _ = calculate_timeliness(d)
        assert score >= 85

    def test_old_scores_low(self):
        d = _complete_dataset()
        d["metadata_modified"] = "2020-01-01T12:00:00"
        score, _ = calculate_timeliness(d)
        assert score <= 10

    def test_missing_modified_scores_minimum(self):
        d = _empty_dataset()
        score, _ = calculate_timeliness(d)
        assert score == 10.0


class TestAccessibility:
    def test_open_with_machine_readable(self):
        d = _complete_dataset()
        score, details = calculate_accessibility(d, _resources())
        assert score > 80
        assert details["access_score"] == 100
        assert "CSV" in details["machine_readable"]

    def test_restricted_no_resources(self):
        d = _empty_dataset()
        d["access_level"] = "restricted"
        score, details = calculate_accessibility(d, [])
        assert score < 20

    def test_only_pdf_resources(self):
        d = _complete_dataset()
        resources = [{"format": "PDF", "url": "https://example.com/doc.pdf"}]
        _, details = calculate_accessibility(d, resources)
        assert details["format_score"] == 40  # not machine readable


class TestDocumentation:
    def test_multilingual_with_enrichments(self):
        d = _complete_dataset()
        score, details = calculate_documentation(d, enrichment_count=5)
        assert score > 80
        assert "fi" in details["languages"]
        assert "en" in details["languages"]

    def test_no_documentation(self):
        d = _empty_dataset()
        score, _ = calculate_documentation(d, enrichment_count=0)
        assert score == 0.0

    def test_finnish_only(self):
        d = _empty_dataset()
        d["title_fi"] = "Otsikko"
        _, details = calculate_documentation(d, enrichment_count=0)
        assert details["languages"] == ["fi"]
        assert details["language_score"] == 40


class TestOverallQuality:
    def test_complete_dataset_high_score(self):
        d = _complete_dataset()
        d["metadata_modified"] = "2026-02-20T12:00:00"
        scores = calculate_quality(d, _resources(), enrichment_count=3)
        assert "overall" in scores
        overall = scores["overall"][0]
        assert overall > 70

    def test_empty_dataset_low_score(self):
        scores = calculate_quality(_empty_dataset(), [], enrichment_count=0)
        overall = scores["overall"][0]
        assert overall < 15

    def test_all_dimensions_present(self):
        scores = calculate_quality(_complete_dataset(), _resources(), 0)
        for dim in ["completeness", "timeliness", "accessibility",
                     "documentation", "overall"]:
            assert dim in scores


class TestDatabase:
    def test_save_and_get(self):
        conn = _memory_db()
        scores = calculate_quality(_complete_dataset(), _resources(), 0)
        save_quality_scores(conn, "test-complete", scores)
        conn.commit()

        result = get_quality_scores(conn, "test-complete")
        assert result is not None
        assert "overall" in result
        assert result["overall"]["score"] > 0

    def test_get_missing_returns_none(self):
        conn = _memory_db()
        assert get_quality_scores(conn, "nonexistent") is None

    def test_score_all_datasets(self):
        conn = _memory_db()
        ds = Dataset(
            id="test-ds", name="test-ds", title="Test",
            title_fi="Testi", source="test",
            resources=[Resource(id="r1", name="R1", format="CSV", url="http://x")],
        )
        upsert_dataset(conn, ds)
        conn.commit()

        count = score_all_datasets(conn)
        assert count == 1

        result = get_quality_scores(conn, "test-ds")
        assert result is not None
        assert result["overall"]["score"] > 0
