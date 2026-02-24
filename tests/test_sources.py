"""Testit sources-taululle ja source_config()-metodeille."""

from __future__ import annotations

import sqlite3

from aura.database import get_all_sources, get_source, init_db, upsert_source
from aura.harvesters import HARVESTERS
from aura.harvesters.base import BaseHarvester
from aura.harvesters.ckan import CkanHarvester
from aura.harvesters.pxweb import PxWebHarvester
from aura.harvesters.static import StaticHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestSourcesTable:
    """Testit sources-taulun CRUD-operaatioille."""

    def test_upsert_and_get(self):
        conn = _memory_db()
        upsert_source(conn, {
            "name": "test-source",
            "description": "Test source",
            "url": "https://example.com",
            "harvester_type": "ckan",
            "query_protocol": "ckan",
            "api_base_url": "https://example.com/api",
            "dataset_count": 42,
            "last_harvested_at": "2024-01-01T00:00:00",
        })
        conn.commit()

        src = get_source(conn, "test-source")
        assert src is not None
        assert src["name"] == "test-source"
        assert src["description"] == "Test source"
        assert src["harvester_type"] == "ckan"
        assert src["query_protocol"] == "ckan"
        assert src["api_base_url"] == "https://example.com/api"
        assert src["dataset_count"] == 42

    def test_upsert_updates_existing(self):
        conn = _memory_db()
        upsert_source(conn, {"name": "test", "dataset_count": 10})
        conn.commit()
        upsert_source(conn, {"name": "test", "dataset_count": 20})
        conn.commit()

        src = get_source(conn, "test")
        assert src["dataset_count"] == 20

    def test_get_nonexistent(self):
        conn = _memory_db()
        assert get_source(conn, "nonexistent") is None

    def test_get_all_sources(self):
        conn = _memory_db()
        upsert_source(conn, {"name": "src-a", "dataset_count": 100})
        upsert_source(conn, {"name": "src-b", "dataset_count": 200})
        conn.commit()

        sources = get_all_sources(conn)
        assert len(sources) == 2
        # Järjestetty dataset_count DESC
        assert sources[0]["name"] == "src-b"
        assert sources[1]["name"] == "src-a"

    def test_empty_name_skipped(self):
        conn = _memory_db()
        upsert_source(conn, {"name": ""})
        conn.commit()
        assert get_all_sources(conn) == []


class TestSourceConfig:
    """Testit source_config()-classmethodille."""

    def test_base_harvester_defaults(self):
        config = BaseHarvester.source_config()
        assert config["harvester_type"] == "custom"
        assert config["query_protocol"] == "none"

    def test_ckan_harvester(self):
        config = CkanHarvester.source_config()
        assert config["harvester_type"] == "ckan"
        assert config["query_protocol"] == "ckan"

    def test_pxweb_harvester(self):
        config = PxWebHarvester.source_config()
        assert config["harvester_type"] == "pxweb"
        assert config["query_protocol"] == "pxweb"

    def test_static_harvester(self):
        config = StaticHarvester.source_config()
        assert config["harvester_type"] == "static"
        assert config["query_protocol"] == "static"

    def test_all_harvesters_have_source_config(self):
        """Kaikki rekisteröidyt harvesterit palauttavat validi config."""
        for name, cls in HARVESTERS.items():
            config = cls.source_config()
            assert config["name"] == name, f"{name}: name mismatch"
            assert config["harvester_type"], f"{name}: puuttuva harvester_type"
            assert config["query_protocol"], f"{name}: puuttuva query_protocol"

    def test_ckan_subclasses_inherit_api_base_url(self):
        """CKAN-aliluokat perivät api_base_url ckan_base_url:sta."""
        from aura.harvesters.avoindata import AvoindataHarvester

        config = AvoindataHarvester.source_config()
        assert config["harvester_type"] == "ckan"
        assert "avoindata" in config["api_base_url"]

    def test_pxweb_subclasses_inherit_api_base_url(self):
        """PxWeb-aliluokat perivät api_base_url pxweb_base_url:sta."""
        from aura.harvesters.statfin import StatfinHarvester

        config = StatfinHarvester.source_config()
        assert config["harvester_type"] == "pxweb"
        assert "statfin" in config["api_base_url"]
