"""Testit CkanHarvester-kantaluokalle."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.avoindata import AvoindataHarvester
from aura.harvesters.ckan import CkanHarvester
from aura.harvesters.hri import HriHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


SAMPLE_CKAN_DATASET = {
    "id": "test-dataset-1",
    "name": "test-dataset",
    "title": "Test Dataset",
    "title_translated": {"fi": "Testidatasetti", "en": "Test Dataset"},
    "notes_translated": {"fi": "Kuvaus suomeksi"},
    "notes": "Description",
    "keywords": {"fi": ["testi"], "en": ["test"]},
    "organization": {"id": "org-1", "name": "test-org", "title": "Test Org"},
    "license_id": "cc-by-4.0",
    "license_title": "CC BY 4.0",
    "metadata_created": "2024-01-01T00:00:00",
    "metadata_modified": "2024-06-01T00:00:00",
    "num_resources": 1,
    "resources": [
        {
            "id": "res-1",
            "name": "test.csv",
            "format": "CSV",
            "url": "https://example.com/test.csv",
        }
    ],
}

SAMPLE_CKAN_WITH_EXTRAS = {
    **SAMPLE_CKAN_DATASET,
    "id": "test-extras-1",
    "name": "test-extras",
    "extras": [
        {"key": "contact-email", "value": "data@example.fi"},
        {"key": "lineage", "value": "Aineisto tuotettu vuonna 2023."},
        {"key": "topic-category", "value": '["farming", "environment"]'},
        {"key": "bbox-west-long", "value": "19.5"},
        {"key": "bbox-south-lat", "value": "59.7"},
        {"key": "bbox-east-long", "value": "31.6"},
        {"key": "bbox-north-lat", "value": "70.1"},
        {"key": "temporal_coverage_from", "value": "2020-01-01"},
        {"key": "temporal_coverage_to", "value": "2023-12-31"},
    ],
}


def _mock_ckan_response(datasets: list[dict], total: int | None = None) -> dict:
    if total is None:
        total = len(datasets)
    return {"result": {"count": total, "results": datasets}}


class TestCkanHarvesterConfig:
    """CkanHarvester-konfiguraation testit."""

    def test_avoindata_inherits_ckan_harvester(self):
        assert issubclass(AvoindataHarvester, CkanHarvester)

    def test_hri_inherits_ckan_harvester(self):
        assert issubclass(HriHarvester, CkanHarvester)

    def test_avoindata_config(self):
        h = AvoindataHarvester(conn=_memory_db())
        assert h.name == "avoindata.fi"
        assert h.ckan_source == "avoindata.fi"
        assert "avoindata" in h.ckan_base_url

    def test_hri_config(self):
        h = HriHarvester(conn=_memory_db())
        assert h.name == "hri.fi"
        assert h.ckan_source == "hri.fi"
        assert "hri.fi" in h.ckan_base_url


class TestCkanHarvesterHarvest:
    """CkanHarvester.harvest()-metodin testit."""

    @pytest.mark.asyncio
    async def test_harvest_single_page(self):
        """Yksisivuinen haku palauttaa oikean lukumäärän."""
        h = AvoindataHarvester(conn=_memory_db())

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 1

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """Harvest tallentaa datasetit tietokantaan."""
        conn = _memory_db()
        h = AvoindataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute("SELECT COUNT(*) FROM datasets WHERE source = 'avoindata.fi'").fetchone()
        assert row[0] == 1

    @pytest.mark.asyncio
    async def test_harvest_sets_correct_source(self):
        """HRI-harvester asettaa source-kentän oikein."""
        conn = _memory_db()
        h = HriHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute("SELECT source FROM datasets WHERE id = 'test-dataset-1'").fetchone()
        assert row[0] == "hri.fi"


class TestCkanExtrasEnrichment:
    """CKAN extras → enrichment -testit."""

    @pytest.mark.asyncio
    async def test_extras_create_enrichments(self):
        """CKAN extras rikastuu enrichment-tauluun."""
        conn = _memory_db()
        h = AvoindataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_WITH_EXTRAS], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        enrichments = conn.execute(
            "SELECT field, value FROM enrichments WHERE dataset_id = 'test-extras-1' ORDER BY field"
        ).fetchall()
        fields = {e["field"] for e in enrichments}

        assert "access_instructions" in fields  # contact-email
        assert "description_extended" in fields  # lineage
        assert "temporal_coverage" in fields  # temporal from+to
        assert "data_fields" in fields  # bbox

    @pytest.mark.asyncio
    async def test_extras_idempotent(self):
        """Toinen harvest ei luo duplikaatti-enrichmentteja."""
        conn = _memory_db()
        h = AvoindataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_WITH_EXTRAS], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()
            await h.harvest()  # toinen kerta

        count = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE dataset_id = 'test-extras-1'"
        ).fetchone()[0]
        # Jokainen enrichment vain kerran
        unique_count = conn.execute(
            "SELECT COUNT(DISTINCT field || '|' || value) FROM enrichments "
            "WHERE dataset_id = 'test-extras-1'"
        ).fetchone()[0]
        assert count == unique_count

    @pytest.mark.asyncio
    async def test_no_extras_no_enrichments(self):
        """Dataset ilman extras:ia ei luo enrichmentteja."""
        conn = _memory_db()
        h = AvoindataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        count = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE dataset_id = 'test-dataset-1'"
        ).fetchone()[0]
        assert count == 0

    @pytest.mark.asyncio
    async def test_temporal_coverage_combined(self):
        """Temporal coverage yhdistää from ja to."""
        conn = _memory_db()
        h = AvoindataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_WITH_EXTRAS], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT value FROM enrichments "
            "WHERE dataset_id = 'test-extras-1' AND field = 'temporal_coverage'"
        ).fetchone()
        assert "2020-01-01" in row["value"]
        assert "2023-12-31" in row["value"]

    @pytest.mark.asyncio
    async def test_source_type_is_harvest(self):
        """Harvest-enrichmentit saavat source_type='harvest'."""
        conn = _memory_db()
        h = AvoindataHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_CKAN_WITH_EXTRAS], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        rows = conn.execute(
            "SELECT source_type FROM enrichments WHERE dataset_id = 'test-extras-1'"
        ).fetchall()
        assert all(r["source_type"] == "harvest" for r in rows)
