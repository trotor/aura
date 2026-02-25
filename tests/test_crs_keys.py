"""Testit CRS-tiedolle (#116) ja joinable keys -tunnistukselle (#117)."""

import json
import sqlite3

import aura.server  # noqa: F401 — resolve circular import before tools
from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _make_test_harvester(conn: sqlite3.Connection):  # type: ignore[no-untyped-def]
    """Luo konkreettinen harvester testausta varten."""
    from aura.harvesters.base import BaseHarvester

    class _TestHarvester(BaseHarvester):
        name = "test"
        description = "Test harvester"

        async def harvest(self) -> int:
            return 0

    h = _TestHarvester(conn=conn)
    return h


class TestCrsEnrichment:
    """CRS-enrichment paikkatietoresursseille (#116)."""

    def test_crs_in_valid_fields(self) -> None:
        from aura.tools.enrichment import VALID_ENRICHMENT_FIELDS

        assert "crs" in VALID_ENRICHMENT_FIELDS

    def test_auto_enrich_crs_wfs(self) -> None:
        conn = _memory_db()
        ds = Dataset(
            id="ds-wfs",
            name="wfs-test",
            resources=[
                Resource(
                    id="r1", name="WFS", format="WFS",
                    url="https://example.com/wfs",
                ),
            ],
            geographical_coverage=["Suomi"],
        )
        upsert_dataset(conn, ds)
        conn.commit()

        h = _make_test_harvester(conn)
        h._auto_enrich_crs(ds)
        conn.commit()

        enr = conn.execute(
            "SELECT value FROM enrichments "
            "WHERE dataset_id = 'ds-wfs' AND field = 'crs'",
        ).fetchone()
        assert enr is not None
        assert enr["value"] == "EPSG:3067"

    def test_auto_enrich_crs_geojson(self) -> None:
        conn = _memory_db()
        ds = Dataset(
            id="ds-geo",
            name="geojson-test",
            resources=[
                Resource(
                    id="r1", name="data", format="GeoJSON",
                    url="https://example.com/data.geojson",
                ),
            ],
            geographical_coverage=["Suomi"],
        )
        upsert_dataset(conn, ds)
        conn.commit()

        h = _make_test_harvester(conn)
        h._auto_enrich_crs(ds)
        conn.commit()

        enr = conn.execute(
            "SELECT value FROM enrichments "
            "WHERE dataset_id = 'ds-geo' AND field = 'crs'",
        ).fetchone()
        assert enr is not None
        assert enr["value"] == "EPSG:3067"

    def test_no_crs_for_csv(self) -> None:
        conn = _memory_db()
        ds = Dataset(
            id="ds-csv",
            name="csv-test",
            resources=[
                Resource(
                    id="r1", name="data", format="CSV",
                    url="https://example.com/data.csv",
                ),
            ],
        )
        upsert_dataset(conn, ds)
        conn.commit()

        h = _make_test_harvester(conn)
        h._auto_enrich_crs(ds)
        conn.commit()

        enr = conn.execute(
            "SELECT 1 FROM enrichments "
            "WHERE dataset_id = 'ds-csv' AND field = 'crs'",
        ).fetchone()
        assert enr is None

    def test_crs_label_in_search(self) -> None:
        from aura.search import ENRICHMENT_FIELD_LABELS

        assert "crs" in ENRICHMENT_FIELD_LABELS

    def test_crs_in_describe_priorities(self) -> None:
        from aura.tools.describe import _ENRICHMENT_PRIORITIES

        fields = [f for f, _ in _ENRICHMENT_PRIORITIES]
        assert "crs" in fields


class TestJoinableKeys:
    """Joinable keys -tunnistus (#117)."""

    def test_joinable_keys_in_valid_fields(self) -> None:
        from aura.tools.enrichment import VALID_ENRICHMENT_FIELDS

        assert "joinable_keys" in VALID_ENRICHMENT_FIELDS

    def test_detect_kuntakoodi(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["nimi", "kuntakoodi", "vuosi", "arvo"])
        names = [k["key"] for k in keys]
        assert "kuntakoodi" in names
        assert "vuosi" in names

    def test_detect_municipality_code(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["municipality_code", "value"])
        names = [k["key"] for k in keys]
        assert "kuntakoodi" in names

    def test_detect_postinumero(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["postinumero", "kaupunki"])
        names = [k["key"] for k in keys]
        assert "postinumero" in names

    def test_detect_ytunnus(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["y_tunnus", "yritys_nimi"])
        names = [k["key"] for k in keys]
        assert "y-tunnus" in names

    def test_no_keys_for_generic_fields(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["nimi", "kuvaus", "arvo"])
        assert keys == []

    def test_no_duplicates(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys([
            "kuntakoodi", "kuntanumero", "municipality_code",
        ])
        names = [k["key"] for k in keys]
        assert names.count("kuntakoodi") == 1

    def test_save_schema_detects_keys(self) -> None:
        from aura.tools.schema import save_schema_from_markdown

        conn = _memory_db()
        ds = Dataset(id="ds-keys", name="keys-test")
        upsert_dataset(conn, ds)
        conn.commit()

        md = (
            "| kuntakoodi | vuosi | arvo |\n"
            "| --- | --- | --- |\n"
            "| 091 | 2025 | 100 |\n"
            "| 049 | 2025 | 200 |\n"
        )
        save_schema_from_markdown(conn, "res-1", "ds-keys", md)

        enr = conn.execute(
            "SELECT value FROM enrichments "
            "WHERE dataset_id = 'ds-keys' AND field = 'joinable_keys'",
        ).fetchone()
        assert enr is not None
        keys_data = json.loads(enr["value"])
        names = [k["key"] for k in keys_data]
        assert "kuntakoodi" in names
        assert "vuosi" in names

    def test_joinable_keys_in_list_fields(self) -> None:
        from aura.search import _LIST_FIELDS

        assert "joinable_keys" in _LIST_FIELDS

    def test_detect_ely_code(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["ely_koodi", "nimi"])
        names = [k["key"] for k in keys]
        assert "ELY-koodi" in names

    def test_detect_maakuntakoodi(self) -> None:
        from aura.tools.schema import detect_joinable_keys

        keys = detect_joinable_keys(["region_code", "population"])
        names = [k["key"] for k in keys]
        assert "maakuntakoodi" in names
