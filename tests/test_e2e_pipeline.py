"""End-to-end testit: harvest → search → describe -putkilinja.

Testaa koko tietoputkiston in-memory-tietokannalla:
upsert → FTS5-indeksi → search → describe → enrich → quality.
"""

import json
import sqlite3
from unittest.mock import patch

import pytest

from aura.database import (
    init_db,
    search_datasets,
    upsert_dataset,
)
from aura.models import Dataset, Resource
from aura.quality import score_all_datasets
from aura.server import (
    describe,
    enrich,
    get_enrichments_tool,
    search_structured,
)


def _create_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvest_mock_datasets(conn: sqlite3.Connection) -> None:
    """Simuloi harvestointi: tallenna datasettejä eri lähteistä."""
    datasets = [
        Dataset(
            id="avoindata-vaesto-001",
            name="helsingin-vaestotilasto",
            title="Helsingin väestötilasto",
            title_fi="Helsingin väestötilasto",
            notes_fi=(
                "Helsingin kaupungin väestötilasto sisältää tiedot "
                "väestön määrästä, ikärakenteesta ja muuttoliikkeestä "
                "vuosittain alueittain."
            ),
            organization_title="Helsingin kaupunki",
            organization_name="helsinki",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            keywords_fi=["väestö", "helsinki", "tilasto"],
            collection_type="Open Data",
            source="avoindata.fi",
            update_frequency="vuosittain",
            metadata_modified="2026-01-15T10:30:00",
            num_resources=2,
            resources=[
                Resource(
                    id="res-vaesto-csv",
                    name="vaesto_2025.csv",
                    format="CSV",
                    url="https://example.com/vaesto.csv",
                ),
                Resource(
                    id="res-vaesto-json",
                    name="vaesto_2025.json",
                    format="JSON",
                    url="https://example.com/vaesto.json",
                ),
            ],
        ),
        Dataset(
            id="hri-liikenne-002",
            name="hsl-joukkoliikenne-reitit",
            title="HSL joukkoliikenteen reitit",
            title_fi="HSL joukkoliikenteen reitit",
            notes_fi="Helsingin seudun joukkoliikenteen reittitiedot GTFS-muodossa.",
            organization_title="HSL",
            organization_name="hsl",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            keywords_fi=["joukkoliikenne", "hsl", "reitit", "gtfs"],
            collection_type="Open Data",
            source="hri.fi",
            metadata_modified="2026-02-01T08:00:00",
            num_resources=1,
            resources=[
                Resource(
                    id="res-gtfs",
                    name="gtfs.zip",
                    format="GTFS",
                    url="https://example.com/gtfs.zip",
                ),
            ],
        ),
        Dataset(
            id="statfin-tulot-003",
            name="tulot-ja-verotus",
            title="Tulot ja verotus",
            title_fi="Tulot ja verotus",
            notes_fi="Tilastokeskuksen tulonjakotilasto kunnittain.",
            organization_title="Tilastokeskus",
            organization_name="stat",
            license_id="cc-by-4.0",
            license_title="CC BY 4.0",
            keywords_fi=["tulot", "verotus", "tilasto"],
            collection_type="Open Data",
            source="statfin",
            metadata_modified="2025-06-01T00:00:00",
            num_resources=1,
            resources=[
                Resource(
                    id="res-pxweb",
                    name="tulot.px",
                    format="PX",
                    url="https://example.com/tulot.px",
                ),
            ],
        ),
    ]
    for ds in datasets:
        upsert_dataset(conn, ds)
    conn.commit()


class TestHarvestToSearch:
    """Harvestoitu data löytyy FTS5-haulla."""

    def test_fts5_finds_by_title(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        results = search_datasets(conn, "väestö")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "helsingin-vaestotilasto" in names

    def test_fts5_finds_by_description(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        results = search_datasets(conn, "vuosittain alueittain")
        assert len(results) >= 1
        assert results[0]["name"] == "helsingin-vaestotilasto"

    def test_fts5_finds_by_keyword(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        results = search_datasets(conn, "gtfs")
        assert len(results) >= 1
        assert results[0]["name"] == "hsl-joukkoliikenne-reitit"

    def test_source_filter_works(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        results = search_datasets(conn, "tilasto", source="statfin")
        assert all(r["source"] == "statfin" for r in results)

    def test_format_filter_works(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        results = search_datasets(conn, "helsinki", fmt="CSV")
        assert len(results) >= 1
        assert results[0]["name"] == "helsingin-vaestotilasto"


class TestSearchToDescribe:
    """Haettu datasetti kuvailtavissa describe()-työkalulla."""

    @pytest.mark.asyncio
    async def test_describe_shows_harvested_data(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            result = await describe("helsingin-vaestotilasto")
        assert "Helsingin väestötilasto" in result
        assert "Helsingin kaupunki" in result
        assert "CSV" in result
        assert "JSON" in result
        assert "vaesto_2025.csv" in result

    @pytest.mark.asyncio
    async def test_describe_after_search(self) -> None:
        """Haku palauttaa nimen jolla describe() löytää datasetin."""
        conn = _create_db()
        _harvest_mock_datasets(conn)
        results = search_datasets(conn, "joukkoliikenne")
        assert len(results) >= 1
        name = results[0]["name"]

        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            result = await describe(name)
        assert "HSL" in result
        assert "joukkoliikenne" in result.lower()


class TestEnrichmentPipeline:
    """Enrichmentit näkyvät describe()-tuloksissa."""

    @pytest.mark.asyncio
    async def test_enrich_visible_in_describe(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            enrich(
                dataset_id="helsingin-vaestotilasto",
                field="use_case",
                value="Väestöanalyysi ja kaupunkisuunnittelu",
            )
            result = await describe("helsingin-vaestotilasto")
        assert "Väestöanalyysi" in result

    def test_enrich_retrievable(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn):
            enrich(
                dataset_id="avoindata-vaesto-001",
                field="access_instructions",
                value="Lataa CSV REST-rajapinnasta",
            )
            result = get_enrichments_tool(
                dataset_id="avoindata-vaesto-001",
            )
        assert "Käyttöohjeet" in result
        assert "Lataa CSV" in result

    @pytest.mark.asyncio
    async def test_multiple_enrichments(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            enrich(
                dataset_id="helsingin-vaestotilasto",
                field="use_case",
                value="Väestöanalyysi",
            )
            enrich(
                dataset_id="helsingin-vaestotilasto",
                field="temporal_coverage",
                value="2000-2025",
            )
            result = await describe("helsingin-vaestotilasto")
        assert "Väestöanalyysi" in result
        assert "2000-2025" in result


class TestQualityPipeline:
    """Laatupisteytys toimii harvestoidulla datalla."""

    def test_score_all_datasets(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        count = score_all_datasets(conn)
        assert count == 3

    @pytest.mark.asyncio
    async def test_quality_in_describe(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        score_all_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            result = await describe("helsingin-vaestotilasto")
        assert "Laatuarvio" in result

    def test_enrichment_improves_quality(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)

        # Pisteytä ennen enrichmentiä
        score_all_datasets(conn)
        row_before = conn.execute(
            "SELECT score FROM quality_scores "
            "WHERE dataset_id = 'avoindata-vaesto-001' "
            "AND dimension = 'documentation'",
        ).fetchone()
        score_before = row_before["score"]

        # Lisää enrichmentejä (5 kpl → enrichment_score nousee 0 → 100)
        with patch("aura.server._get_conn", return_value=conn):
            for field, value in [
                ("use_case", "Väestöanalyysi"),
                ("access_instructions", "REST API"),
                ("temporal_coverage", "2000-2025"),
                ("data_fields", '["vuosi", "alue", "vaesto"]'),
                ("quality_notes", "Hyvälaatuinen aineisto"),
            ]:
                enrich(
                    dataset_id="avoindata-vaesto-001",
                    field=field,
                    value=value,
                )

        # Pisteytä uudelleen
        score_all_datasets(conn)
        row_after = conn.execute(
            "SELECT score FROM quality_scores "
            "WHERE dataset_id = 'avoindata-vaesto-001' "
            "AND dimension = 'documentation'",
        ).fetchone()
        score_after = row_after["score"]

        assert score_after > score_before


class TestSearchStructuredPipeline:
    """search_structured palauttaa rakenteellisen JSON:in."""

    @pytest.mark.asyncio
    async def test_full_pipeline_json(self) -> None:
        conn = _create_db()
        _harvest_mock_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn):
            result = await search_structured("helsinki")
        data = json.loads(result)
        assert data["count"] >= 1

        item = data["results"][0]
        assert item["source"] == "avoindata.fi"
        assert item["organization"] == "Helsingin kaupunki"
        assert item["num_resources"] == 2

    @pytest.mark.asyncio
    async def test_all_sources_searchable(self) -> None:
        """Kaikkien lähteiden datasetit löytyvät haulla."""
        conn = _create_db()
        _harvest_mock_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn):
            for source in ["avoindata.fi", "hri.fi", "statfin"]:
                result = await search_structured(
                    "tilasto", source=source,
                )
                json.loads(result)  # Varmista validi JSON
        # Varmista kaikki 3 löytyvät jollain haulla
        with patch("aura.server._get_conn", return_value=conn):
            r1 = await search_structured("väestö")
            r2 = await search_structured("joukkoliikenne")
            r3 = await search_structured("tulot")
        assert json.loads(r1)["count"] >= 1
        assert json.loads(r2)["count"] >= 1
        assert json.loads(r3)["count"] >= 1
