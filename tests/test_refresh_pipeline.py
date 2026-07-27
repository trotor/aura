"""Testit refresh-pipeline-issuille (#125, #119, #127, #124, #126, #123)."""

import inspect
import sqlite3

import aura.server  # noqa: F401 — resolve circular import before tools
from aura.database import add_enrichment, init_db, upsert_dataset
from aura.models import Dataset


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestSpdxNormalization:
    """SPDX-lisenssien normalisointi (#119)."""

    def test_cc_by_4_normalizes(self) -> None:
        from aura.constants import normalize_license

        spdx_id, title = normalize_license("cc-by-4.0")
        assert spdx_id == "CC-BY-4.0"
        assert "Creative Commons" in title

    def test_cc_zero_normalizes(self) -> None:
        from aura.constants import normalize_license

        spdx_id, title = normalize_license("cc-zero")
        assert spdx_id == "CC0-1.0"

    def test_odbl_normalizes(self) -> None:
        from aura.constants import normalize_license

        spdx_id, _ = normalize_license("ODbL-1.0")
        assert spdx_id == "ODbL-1.0"

    def test_unknown_returns_original(self) -> None:
        from aura.constants import normalize_license

        spdx_id, title = normalize_license("custom-license")
        assert spdx_id == "custom-license"
        assert title == ""

    def test_case_insensitive(self) -> None:
        from aura.constants import normalize_license

        spdx_id, _ = normalize_license("CC-BY-4.0")
        assert spdx_id == "CC-BY-4.0"

    def test_upsert_normalizes_license(self) -> None:
        conn = _memory_db()
        ds = Dataset(
            id="ds-lic",
            name="license-test",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
        )
        upsert_dataset(conn, ds)
        conn.commit()

        row = conn.execute(
            "SELECT license_id, license_title FROM datasets WHERE id = 'ds-lic'"
        ).fetchone()
        assert row["license_id"] == "CC-BY-4.0"
        assert "Creative Commons" in row["license_title"]

    def test_empty_license_not_changed(self) -> None:
        conn = _memory_db()
        ds = Dataset(id="ds-nolic", name="no-license", license_id="", license_title="")
        upsert_dataset(conn, ds)
        conn.commit()

        row = conn.execute(
            "SELECT license_id FROM datasets WHERE id = 'ds-nolic'"
        ).fetchone()
        assert row["license_id"] == ""


class TestAuthDetection:
    """Auth-vaatimuksen automaattinen tunnistus (#126)."""

    def test_detects_401(self) -> None:
        from aura.health import HealthResult, _detect_auth_from_results

        conn = _memory_db()
        ds = Dataset(id="ds-auth", name="auth-test", title_fi="Auth test")
        upsert_dataset(conn, ds)
        conn.commit()

        results = [
            HealthResult(
                resource_id="res-1",
                dataset_id="ds-auth",
                url="https://example.com/api",
                status_code=401,
                is_available=False,
            ),
        ]
        _detect_auth_from_results(conn, results)

        enr = conn.execute(
            "SELECT value FROM enrichments WHERE dataset_id = 'ds-auth' AND field = 'auth_method'"
        ).fetchone()
        assert enr is not None
        assert enr["value"] == "registration"

    def test_detects_403(self) -> None:
        from aura.health import HealthResult, _detect_auth_from_results

        conn = _memory_db()
        ds = Dataset(id="ds-403", name="forbidden", title_fi="Forbidden")
        upsert_dataset(conn, ds)
        conn.commit()

        results = [
            HealthResult(
                resource_id="res-1",
                dataset_id="ds-403",
                url="https://example.com/api",
                status_code=403,
            ),
        ]
        _detect_auth_from_results(conn, results)

        enr = conn.execute(
            "SELECT 1 FROM enrichments WHERE dataset_id = 'ds-403' AND field = 'auth_method'"
        ).fetchone()
        assert enr is not None

    def test_no_duplicate_enrichment(self) -> None:
        from aura.health import HealthResult, _detect_auth_from_results

        conn = _memory_db()
        ds = Dataset(id="ds-dup", name="dup-test")
        upsert_dataset(conn, ds)
        add_enrichment(conn, "ds-dup", "auth_method", "apikey")
        conn.commit()

        results = [
            HealthResult(
                resource_id="res-1",
                dataset_id="ds-dup",
                url="https://example.com",
                status_code=401,
            ),
        ]
        _detect_auth_from_results(conn, results)

        count = conn.execute(
            "SELECT COUNT(*) as c FROM enrichments "
            "WHERE dataset_id = 'ds-dup' AND field = 'auth_method'",
        ).fetchone()["c"]
        # Pitäisi olla 1, ei 2
        assert count == 1

    def test_ignores_200(self) -> None:
        from aura.health import HealthResult, _detect_auth_from_results

        conn = _memory_db()
        ds = Dataset(id="ds-ok", name="ok-test")
        upsert_dataset(conn, ds)
        conn.commit()

        results = [
            HealthResult(
                resource_id="res-1",
                dataset_id="ds-ok",
                url="https://example.com",
                status_code=200,
                is_available=True,
            ),
        ]
        _detect_auth_from_results(conn, results)

        enr = conn.execute(
            "SELECT 1 FROM enrichments WHERE dataset_id = 'ds-ok' AND field = 'auth_method'"
        ).fetchone()
        assert enr is None


class TestQualityAfterHarvest:
    """Laatupisteet harvestoinnin jälkeen (#127)."""

    def test_quality_score_all_works(self) -> None:
        """quality.score_all_datasets works on in-memory db."""
        from aura.quality import score_all_datasets

        conn = _memory_db()
        ds = Dataset(
            id="ds-q1", name="q-test", title_fi="Quality test", source="test-src",
            license_id="CC-BY-4.0",
        )
        upsert_dataset(conn, ds)
        conn.commit()

        count = score_all_datasets(conn, source="test-src")
        assert count == 1

        row = conn.execute(
            "SELECT score FROM quality_scores WHERE dataset_id = 'ds-q1' AND dimension = 'overall'"
        ).fetchone()
        assert row is not None
        assert row["score"] > 0

    def test_admin_harvest_code_calls_quality(self) -> None:
        """Verify admin.harvest source code includes quality scoring."""
        from aura.tools.admin import harvest

        source_code = inspect.getsource(harvest)
        assert "score_all_datasets" in source_code


class TestCliSourcesUpdate:
    """Harvestointi päivittää sources-taulun (#125).

    Väite kohdistuu nyt jaettuun putkeen eikä ``main``-funktion lähdekoodiin:
    harvestointi siirtyi ``aura.pipeline``-moduuliin, jotta ``harvest`` ja
    ``refresh`` eivät enää eriytyisi toisistaan. Käytös testataan
    ``tests/test_pipeline.py``:ssä oikeaa kantaa vasten.
    """

    def test_pipeline_updates_sources_table(self) -> None:
        from aura.pipeline import harvest_sources

        source_code = inspect.getsource(harvest_sources)
        assert "upsert_source" in source_code

    def test_both_cli_paths_use_the_shared_pipeline(self) -> None:
        """`harvest` ja `refresh` eivät saa harvestoida omin koodein."""
        from aura.cli import _refresh, main

        assert "_refresh" in inspect.getsource(main)
        assert "harvest_sources" in inspect.getsource(_refresh)


class TestSchemaInfer:
    """Schema introspection CLI (#124)."""

    def test_infer_schemas_function_exists(self) -> None:
        from aura.cli import _infer_schemas

        assert callable(_infer_schemas)


class TestRefreshCommand:
    """Unified refresh command (#123)."""

    def test_refresh_function_exists(self) -> None:
        from aura.cli import _refresh

        assert callable(_refresh)


async def _coro(val: int) -> int:
    return val
