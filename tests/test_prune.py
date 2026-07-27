"""Testit vanhentuneiden datasettien poistolle (aura.prune).

Prune on ainoa kohta, jossa Aura poistaa dataa pysyvästi, joten testit
painottuvat siihen mitä *ei* saa poistaa.
"""

import sqlite3

import pytest

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.prune import (
    STALE_AFTER_DAYS,
    check_count_regression,
    curated_enrichments,
    find_stale,
    prune_datasets,
    stale_dataset_ids,
)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _add(
    conn: sqlite3.Connection, ds_id: str, source: str, harvested: str
) -> None:
    dataset = Dataset(
        id=ds_id,
        name=ds_id,
        title=f"Aineisto {ds_id}",
        title_fi=f"Aineisto {ds_id}",
        organization_id="org-1",
        organization_name="org",
        organization_title="Org",
        source=source,
        num_resources=1,
        resources=[
            Resource(id=f"res-{ds_id}", name="data.csv", format="CSV", url="https://x/1")
        ],
    )
    upsert_dataset(conn, dataset)
    conn.execute(
        "UPDATE datasets SET harvested_at = ? WHERE id = ?", (harvested, ds_id)
    )
    conn.commit()


class TestStaleDatasetIds:
    def test_old_row_is_stale(self) -> None:
        conn = _db()
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        _add(conn, "vanha", "statfin", "2026-05-31 10:00:00")
        assert stale_dataset_ids(conn) == ["vanha"]

    def test_same_day_row_is_not_stale(self) -> None:
        """Yhden ajon aikana pudonnut sivu ei saa johtaa poistoon.

        Tämä on prunen tärkein turvasääntö: CkanHarvester ohittaa
        HTTP-virheen sattuessa kokonaisen sivun, jolloin sata täysin
        kelvollista datasettiä jää päivittämättä. Ikäraja antaa niiden
        palata seuraavassa ajossa.
        """
        conn = _db()
        _add(conn, "uusi", "syke", "2026-07-26 10:00:00")
        _add(conn, "ohittui", "syke", "2026-07-26 09:00:00")
        assert stale_dataset_ids(conn) == []

    def test_recent_miss_within_threshold_is_kept(self) -> None:
        conn = _db()
        _add(conn, "uusi", "syke", "2026-07-26 10:00:00")
        _add(conn, "eilinen", "syke", "2026-07-20 10:00:00")
        assert stale_dataset_ids(conn) == []

    def test_threshold_is_measured_from_source_latest_not_now(self) -> None:
        """Lähde jota ei ole harvestoitu puoleen vuoteen ei saa tyhjentyä."""
        conn = _db()
        _add(conn, "a", "gtk", "2026-01-01 10:00:00")
        _add(conn, "b", "gtk", "2026-01-01 10:00:00")
        assert stale_dataset_ids(conn) == []

    def test_sources_are_independent(self) -> None:
        conn = _db()
        _add(conn, "statfin-uusi", "statfin", "2026-07-26 10:00:00")
        _add(conn, "statfin-vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "luke-vanha", "luke", "2026-01-01 10:00:00")
        assert stale_dataset_ids(conn) == ["statfin-vanha"]

    def test_source_filter(self) -> None:
        conn = _db()
        _add(conn, "statfin-uusi", "statfin", "2026-07-26 10:00:00")
        _add(conn, "statfin-vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "luke-uusi", "luke", "2026-07-26 10:00:00")
        _add(conn, "luke-vanha", "luke", "2026-01-01 10:00:00")
        assert stale_dataset_ids(conn, source="luke") == ["luke-vanha"]

    def test_custom_threshold(self) -> None:
        conn = _db()
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        _add(conn, "vanha", "statfin", "2026-07-20 10:00:00")
        assert stale_dataset_ids(conn, days=3) == ["vanha"]
        assert stale_dataset_ids(conn, days=30) == []

    def test_default_threshold_is_conservative(self) -> None:
        assert STALE_AFTER_DAYS >= 14


class TestFindStale:
    def test_reports_per_source(self) -> None:
        conn = _db()
        _add(conn, "a", "statfin", "2026-07-26 10:00:00")
        _add(conn, "b", "statfin", "2026-01-01 10:00:00")
        reports = find_stale(conn)
        assert len(reports) == 1
        assert reports[0].source == "statfin"
        assert reports[0].stale == 1
        assert reports[0].remaining == 1

    def test_sources_without_stale_rows_are_omitted(self) -> None:
        conn = _db()
        _add(conn, "a", "luke", "2026-07-26 10:00:00")
        assert find_stale(conn) == []


class TestCuratedEnrichments:
    def test_harvest_enrichments_are_not_curated(self) -> None:
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type) "
            "VALUES ('vanha', 'crs', 'EPSG:3067', 'harvest')"
        )
        conn.commit()
        assert curated_enrichments(conn, ["vanha"]) == []

    def test_session_enrichments_are_curated(self) -> None:
        """Ihmisen tai agentin kirjaama tieto ei saa kadota hiljaa."""
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type) "
            "VALUES ('vanha', 'use_case', 'Tärkeä havainto', 'mcp_session')"
        )
        conn.commit()
        rows = curated_enrichments(conn, ["vanha"])
        assert len(rows) == 1
        assert rows[0]["value"] == "Tärkeä havainto"


class TestPruneDatasets:
    def test_dry_run_deletes_nothing(self) -> None:
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")

        stats = prune_datasets(conn, apply=False)
        assert stats["datasets"] == 1
        assert conn.execute("SELECT count(*) FROM datasets").fetchone()[0] == 2

    def test_apply_deletes_stale_rows(self) -> None:
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")

        stats = prune_datasets(conn, apply=True)
        assert stats["datasets"] == 1
        remaining = [r[0] for r in conn.execute("SELECT id FROM datasets")]
        assert remaining == ["uusi"]

    def test_apply_removes_related_rows(self) -> None:
        """Viiteintegriteettiä ei valvota kannassa, joten se on prunen vastuulla."""
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type) "
            "VALUES ('vanha', 'crs', 'EPSG:3067', 'harvest')"
        )
        conn.commit()

        prune_datasets(conn, apply=True)
        for table in ("resources", "enrichments", "quality_scores"):
            leftover = conn.execute(
                f"SELECT count(*) FROM {table} WHERE dataset_id = 'vanha'"
            ).fetchone()[0]
            assert leftover == 0, f"{table} jäi orvoksi"

    def test_fts_index_stays_in_sync(self) -> None:
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        prune_datasets(conn, apply=True)

        hits = conn.execute(
            "SELECT count(*) FROM datasets_fts WHERE datasets_fts MATCH ?",
            ('"vanha"',),
        ).fetchone()[0]
        assert hits == 0

    def test_curated_enrichments_block_apply_without_force(self) -> None:
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type) "
            "VALUES ('vanha', 'use_case', 'Käsin kirjattu', 'mcp_session')"
        )
        conn.commit()

        with pytest.raises(ValueError, match="kuratoitua rikastusta"):
            prune_datasets(conn, apply=True)
        assert conn.execute("SELECT count(*) FROM datasets").fetchone()[0] == 2

    def test_force_allows_deleting_curated(self) -> None:
        conn = _db()
        _add(conn, "vanha", "statfin", "2026-01-01 10:00:00")
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type) "
            "VALUES ('vanha', 'use_case', 'Käsin kirjattu', 'mcp_session')"
        )
        conn.commit()

        stats = prune_datasets(conn, apply=True, force=True)
        assert stats["datasets"] == 1
        assert stats["curated_enrichments"] == 1

    def test_nothing_to_prune(self) -> None:
        conn = _db()
        _add(conn, "uusi", "statfin", "2026-07-26 10:00:00")
        stats = prune_datasets(conn, apply=True)
        assert stats["datasets"] == 0


class TestCheckCountRegression:
    """Hiljaisen nollan pyydystys — sama vika puri sekä Valtiokonttoriin
    (48 → 0) että SYKEen (642 → 542)."""

    def _with_source(self, count: int) -> sqlite3.Connection:
        conn = _db()
        conn.execute(
            "INSERT INTO sources (name, dataset_count) VALUES ('syke', ?)", (count,)
        )
        conn.commit()
        return conn

    def test_zero_after_nonzero_warns(self) -> None:
        warning = check_count_regression(self._with_source(642), "syke", 0)
        assert "0 datasettiä" in warning
        assert "642" in warning

    def test_large_drop_warns(self) -> None:
        warning = check_count_regression(self._with_source(642), "syke", 400)
        assert warning
        assert "38 %" in warning or "−38" in warning

    def test_small_drop_is_silent(self) -> None:
        """Lähteestä oikeasti poistuneet aineistot eivät saa aiheuttaa hälyä."""
        assert check_count_regression(self._with_source(642), "syke", 630) == ""

    def test_growth_is_silent(self) -> None:
        assert check_count_regression(self._with_source(642), "syke", 700) == ""

    def test_unknown_source_is_silent(self) -> None:
        assert check_count_regression(_db(), "uusi-lahde", 0) == ""

    def test_first_run_is_silent(self) -> None:
        """Ensimmäisellä ajolla ei ole mihin verrata."""
        assert check_count_regression(self._with_source(0), "syke", 0) == ""
