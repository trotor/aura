"""Testit search.py formatointifunktioille."""

from __future__ import annotations

import json
import uuid

import pytest

from aura.search import (
    _enrichment_age_warning,
    _format_enrichment_value,
    format_conflicts,
    format_dataset_detail,
    format_dataset_summary,
    format_enrichments,
    format_stats,
)


# --- format_dataset_summary ---


class TestFormatDatasetSummary:
    """Testit format_dataset_summary-funktiolle."""

    def test_basic_dataset(self) -> None:
        ds = {
            "title_fi": "Väestötilasto",
            "organization_title": "Tilastokeskus",
            "notes_fi": "Kuvaus",
            "license_title": "CC BY 4.0",
            "metadata_modified": "2024-01-15T12:00:00",
            "name": "vaestotilasto",
            "keywords_fi": json.dumps(["väestö", "tilasto"]),
        }
        result = format_dataset_summary(ds)
        assert "## Väestötilasto" in result
        assert "Tilastokeskus" in result
        assert "Kuvaus" in result
        assert "CC BY 4.0" in result
        assert "2024-01-15" in result
        assert "väestö, tilasto" in result
        assert "vaestotilasto" in result

    def test_empty_fields_not_shown(self) -> None:
        ds = {"name": "test-ds", "title_fi": "Otsikko"}
        result = format_dataset_summary(ds)
        assert "Julkaisija" not in result
        assert "Kuvaus" not in result
        assert "Lisenssi" not in result
        assert "Avainsanat" not in result

    def test_long_description_truncated(self) -> None:
        ds = {"name": "test", "notes_fi": "A" * 500}
        result = format_dataset_summary(ds)
        assert "..." in result
        # Truncated to 300 chars
        assert len(result.split("Kuvaus:** ")[1].split("\n")[0]) <= 300

    def test_title_fallback_chain(self) -> None:
        """title_fi → title → name."""
        assert "## Nimi" in format_dataset_summary({"name": "x", "title_fi": "Nimi"})
        assert "## Fallback" in format_dataset_summary({"name": "x", "title": "Fallback"})
        assert "## slug" in format_dataset_summary({"name": "slug"})

    def test_restricted_access_shows_lock(self) -> None:
        ds = {"name": "x", "title_fi": "Test", "access_level": "restricted"}
        result = format_dataset_summary(ds)
        assert "\U0001f512" in result

    def test_open_access_no_lock(self) -> None:
        ds = {"name": "x", "title_fi": "Test", "access_level": "open"}
        result = format_dataset_summary(ds)
        assert "\U0001f512" not in result

    def test_keywords_as_list(self) -> None:
        ds = {"name": "x", "keywords_fi": ["a", "b"]}
        result = format_dataset_summary(ds)
        assert "a, b" in result

    def test_keywords_invalid_json(self) -> None:
        ds = {"name": "x", "keywords_fi": "not-json"}
        result = format_dataset_summary(ds)
        assert "Avainsanat" not in result

    def test_missing_keys_no_crash(self) -> None:
        result = format_dataset_summary({})
        assert "##" in result


# --- format_enrichments ---


class TestFormatEnrichments:
    """Testit format_enrichments-funktiolle."""

    def test_empty_list(self) -> None:
        assert format_enrichments([]) == ""

    def test_basic_enrichment(self) -> None:
        enrichments = [
            {"field": "use_case", "value": "Analyysi", "confidence": "medium"}
        ]
        result = format_enrichments(enrichments)
        assert "Käyttötapaus" in result
        assert "Analyysi" in result

    def test_confidence_markers(self) -> None:
        for confidence, marker in [
            ("verified", "[vahvistettu]"),
            ("high", "[varma]"),
            ("low", "[epävarma]"),
            ("medium", ""),
        ]:
            enrichments = [{"field": "use_case", "value": "x", "confidence": confidence}]
            result = format_enrichments(enrichments)
            if marker:
                assert marker in result
            else:
                assert "[varma]" not in result
                assert "[epävarma]" not in result
                assert "[vahvistettu]" not in result

    def test_stale_marker(self) -> None:
        eid = str(uuid.uuid4())
        enrichments = [{"id": eid, "field": "use_case", "value": "x"}]
        result = format_enrichments(enrichments, stale_ids={eid})
        assert "[vanhentunut]" in result

    def test_not_stale(self) -> None:
        enrichments = [{"id": "abc", "field": "use_case", "value": "x"}]
        result = format_enrichments(enrichments, stale_ids=set())
        assert "[vanhentunut]" not in result

    def test_source_type_shown(self) -> None:
        enrichments = [
            {"field": "use_case", "value": "x", "source_type": "web_research"}
        ]
        result = format_enrichments(enrichments)
        assert "web_research" in result

    def test_mcp_session_source_hidden(self) -> None:
        enrichments = [
            {"field": "use_case", "value": "x", "source_type": "mcp_session"}
        ]
        result = format_enrichments(enrichments)
        assert "mcp_session" not in result

    def test_json_list_field_parsed(self) -> None:
        enrichments = [
            {"field": "keywords", "value": '["a", "b", "c"]'}
        ]
        result = format_enrichments(enrichments)
        assert "a, b, c" in result

    def test_unknown_field_uses_raw_name(self) -> None:
        enrichments = [{"field": "custom_field", "value": "val"}]
        result = format_enrichments(enrichments)
        assert "custom_field" in result


# --- _format_enrichment_value ---


class TestFormatEnrichmentValue:
    """Testit _format_enrichment_value-apufunktiolle."""

    def test_plain_text_field(self) -> None:
        assert _format_enrichment_value("use_case", "Analyysi") == "Analyysi"

    def test_list_field_json(self) -> None:
        result = _format_enrichment_value("data_fields", '["lat", "lon", "name"]')
        assert result == "lat, lon, name"

    def test_list_field_invalid_json(self) -> None:
        result = _format_enrichment_value("keywords", "not json")
        assert result == "not json"

    def test_list_field_non_array_json(self) -> None:
        result = _format_enrichment_value("tags", '{"key": "val"}')
        assert result == '{"key": "val"}'


# --- _enrichment_age_warning ---


class TestEnrichmentAgeWarning:
    """Testit _enrichment_age_warning-apufunktiolle."""

    def test_empty_date(self) -> None:
        assert _enrichment_age_warning("") == ""

    def test_recent_no_warning(self) -> None:
        from datetime import datetime, timedelta

        recent = (datetime.now(tz=__import__("datetime").UTC) - timedelta(days=30)).isoformat()
        assert _enrichment_age_warning(recent) == ""

    def test_old_shows_warning(self) -> None:
        from datetime import datetime, timedelta

        old = (datetime.now(tz=__import__("datetime").UTC) - timedelta(days=365)).isoformat()
        result = _enrichment_age_warning(old)
        assert "kk vanha" in result

    def test_invalid_date(self) -> None:
        assert _enrichment_age_warning("not-a-date") == ""


# --- format_conflicts ---


class TestFormatConflicts:
    """Testit format_conflicts-funktiolle."""

    def test_empty_list(self) -> None:
        assert format_conflicts([]) == ""

    def test_groups_by_field(self) -> None:
        conflicts = [
            {"field": "use_case", "value": "A", "confidence": "high", "created_at": "2024-01-01"},
            {"field": "use_case", "value": "B", "confidence": "medium", "created_at": "2024-02-01"},
        ]
        result = format_conflicts(conflicts)
        assert "Ristiriitaiset" in result
        assert "Käyttötapaus" in result
        assert "A" in result
        assert "B" in result

    def test_multiple_fields(self) -> None:
        conflicts = [
            {"field": "use_case", "value": "X", "confidence": "high", "created_at": "2024-01-01"},
            {"field": "api_format", "value": "REST", "confidence": "medium", "created_at": "2024-01-01"},
        ]
        result = format_conflicts(conflicts)
        assert "Käyttötapaus" in result
        assert "Rajapinnan formaatti" in result


# --- format_dataset_detail ---


class TestFormatDatasetDetail:
    """Testit format_dataset_detail-funktiolle."""

    def test_minimal_dataset(self) -> None:
        ds = {"name": "test", "title_fi": "Testi"}
        result = format_dataset_detail(ds)
        assert "Testi" in result

    def test_with_resources(self) -> None:
        ds = {
            "name": "test",
            "title_fi": "Testi",
            "resources": [
                {"name_fi": "CSV-tiedosto", "format": "CSV", "url": "https://example.com/data.csv"},
            ],
        }
        result = format_dataset_detail(ds)
        assert "Resurssit" in result
        assert "CSV-tiedosto" in result
        assert "CSV" in result

    def test_no_resources(self) -> None:
        ds = {"name": "test", "title_fi": "Testi", "resources": []}
        result = format_dataset_detail(ds)
        assert "Resurssit" not in result

    def test_geographical_coverage(self) -> None:
        ds = {
            "name": "test",
            "geographical_coverage": json.dumps(["Helsinki", "Espoo"]),
        }
        result = format_dataset_detail(ds)
        assert "Helsinki, Espoo" in result

    def test_geographical_coverage_as_list(self) -> None:
        ds = {"name": "test", "geographical_coverage": ["Suomi"]}
        result = format_dataset_detail(ds)
        assert "Suomi" in result

    def test_update_frequency(self) -> None:
        ds = {"name": "test", "update_frequency": "kuukausittain"}
        result = format_dataset_detail(ds)
        assert "kuukausittain" in result

    def test_restricted_access(self) -> None:
        ds = {"name": "test", "access_level": "restricted"}
        result = format_dataset_detail(ds)
        assert "Rajoitettu pääsy" in result

    def test_registration_access(self) -> None:
        ds = {"name": "test", "access_level": "registration"}
        result = format_dataset_detail(ds)
        assert "Vaatii rekisteröinnin" in result

    def test_open_access_no_label(self) -> None:
        ds = {"name": "test", "access_level": "open"}
        result = format_dataset_detail(ds)
        assert "Saatavuus" not in result

    def test_with_enrichments(self) -> None:
        ds = {"name": "test", "title_fi": "Testi"}
        enrichments = [{"field": "use_case", "value": "Tutkimus", "confidence": "high"}]
        result = format_dataset_detail(ds, enrichments=enrichments)
        assert "Rikastukset" in result
        assert "Tutkimus" in result

    def test_with_conflicts(self) -> None:
        ds = {"name": "test", "title_fi": "Testi"}
        conflicts = [
            {"field": "use_case", "value": "A", "confidence": "high", "created_at": "2024-01-01"},
            {"field": "use_case", "value": "B", "confidence": "low", "created_at": "2024-02-01"},
        ]
        result = format_dataset_detail(ds, conflicts=conflicts)
        assert "Ristiriitaiset" in result


# --- format_stats ---


class TestFormatStats:
    """Testit format_stats-funktiolle."""

    def test_empty_database(self) -> None:
        stats = {
            "total_datasets": 0,
            "total_organizations": 0,
            "total_formats": 0,
            "top_organizations": [],
            "top_formats": [],
        }
        result = format_stats(stats)
        assert "0" in result
        assert "Suurimmat julkaisijat" not in result

    def test_normal_stats(self) -> None:
        stats = {
            "total_datasets": 100,
            "total_organizations": 10,
            "total_formats": 5,
            "top_organizations": [
                {"organization_title": "Tilastokeskus", "count": 50},
                {"organization_title": "MML", "count": 30},
            ],
            "top_formats": [
                {"format": "CSV", "count": 200},
                {"format": "JSON", "count": 100},
            ],
        }
        result = format_stats(stats)
        assert "100" in result
        assert "Tilastokeskus" in result
        assert "50" in result
        assert "CSV" in result
        assert "200" in result

    def test_no_top_organizations(self) -> None:
        stats = {
            "total_datasets": 5,
            "total_organizations": 1,
            "total_formats": 2,
            "top_organizations": [],
            "top_formats": [{"format": "CSV", "count": 10}],
        }
        result = format_stats(stats)
        assert "Suurimmat julkaisijat" not in result
        assert "CSV" in result
