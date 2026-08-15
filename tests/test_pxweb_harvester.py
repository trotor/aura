"""Testit PxWebHarvester-kantaluokalle."""

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import get_enrichments, init_db
from aura.harvesters.luke import LukeHarvester
from aura.harvesters.pxweb import PxWebHarvester
from aura.harvesters.statfin import StatfinHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


SAMPLE_FOLDER_ITEMS = [
    {"id": "alue", "type": "l", "text": "Alue"},
    {"id": "testi.px", "type": "t", "text": "Testitaulu", "updated": "2024-01-15T12:00:00"},
]

SAMPLE_SUBFOLDER_ITEMS = [
    {"id": "data.px", "type": "t", "text": "Aluetaulu", "updated": "2024-02-01T10:00:00"},
]


class TestPxWebConfig:
    """PxWebHarvester-konfiguraation testit."""

    def test_statfin_inherits_pxweb(self):
        assert issubclass(StatfinHarvester, PxWebHarvester)

    def test_luke_inherits_pxweb(self):
        assert issubclass(LukeHarvester, PxWebHarvester)

    def test_statfin_config(self):
        h = StatfinHarvester(conn=_memory_db())
        assert h.name == "statfin"
        assert h.root_path == "StatFin"
        assert h.dataset_id_prefix == "statfin"
        assert "statfin.stat.fi" in h.pxweb_base_url

    def test_luke_config(self):
        h = LukeHarvester(conn=_memory_db())
        assert h.name == "luke"
        assert h.root_path == "LUKE"
        assert h.dataset_id_prefix == "luke"
        assert "statdb.luke.fi" in h.pxweb_base_url


class TestTableToDataset:
    """_table_to_dataset()-metodin testit."""

    def test_dataset_id_has_prefix(self):
        h = StatfinHarvester(conn=_memory_db())
        item = {"id": "testi.px", "text": "Testitaulu", "updated": "2024-01-01"}
        ds = h._table_to_dataset(item, "StatFin/alue", "https://example.com/api/")
        assert ds.id == "statfin-testi.px"

    def test_luke_dataset_id_has_prefix(self):
        h = LukeHarvester(conn=_memory_db())
        item = {"id": "data.px", "text": "Datataulu", "updated": "2024-01-01"}
        ds = h._table_to_dataset(item, "LUKE/metsa", "https://example.com/api/")
        assert ds.id == "luke-data.px"

    def test_dataset_has_two_resources(self):
        h = StatfinHarvester(conn=_memory_db())
        item = {"id": "testi.px", "text": "Taulu", "updated": ""}
        ds = h._table_to_dataset(item, "StatFin", "https://example.com/")
        assert len(ds.resources) == 2
        assert ds.resources[0].format == "PXWEB"
        assert ds.resources[1].format == "HTML"

    def test_dataset_source_matches_harvester(self):
        h = LukeHarvester(conn=_memory_db())
        item = {"id": "test.px", "text": "Test", "updated": ""}
        ds = h._table_to_dataset(item, "LUKE", "https://example.com/")
        assert ds.source == "luke"

    def test_dataset_organization(self):
        h = StatfinHarvester(conn=_memory_db())
        item = {"id": "test.px", "text": "Test", "updated": ""}
        ds = h._table_to_dataset(item, "StatFin", "https://example.com/")
        assert ds.organization_id == "tilastokeskus"
        assert ds.organization_title == "Tilastokeskus"


class TestWebUrl:
    """Selainkäyttöliittymän osoitteen muoto.

    PxWeb koodaa kansiopolun kaksoisalaviivoilla, ei kauttaviivoilla.
    Kauttaviivamuoto vastaa 404:llä, ja se oli tuotannossa 2 186 datasetin
    HTML-resurssissa — mikään mittari ei huomannut, koska haku ja query_data
    käyttävät PXWEB-resurssia.
    """

    def _web_url(self, harvester, path: str, table: str) -> str:
        item = {"id": table, "text": "Taulu", "updated": ""}
        ds = harvester._table_to_dataset(item, path, "https://example.com/api/")
        return next(r.url for r in ds.resources if r.format == "HTML")

    def test_statfin_uses_double_underscore(self):
        h = StatfinHarvester(conn=_memory_db())
        url = self._web_url(h, "StatFin/adopt", "11lv.px")
        assert url.endswith("/fi/StatFin/StatFin__adopt/11lv.px")

    def test_deep_path_joins_all_levels(self):
        h = LukeHarvester(conn=_memory_db())
        url = self._web_url(h, "LUKE/maa/elalan", "0100_elalan.px")
        assert url.endswith("/fi/LUKE/LUKE__maa__elalan/0100_elalan.px")

    def test_root_level_table_has_no_separator(self):
        h = StatfinHarvester(conn=_memory_db())
        url = self._web_url(h, "StatFin", "11lv.px")
        assert url.endswith("/fi/StatFin/StatFin/11lv.px")

    def test_no_slash_inside_folder_segment(self):
        """Vanha muoto tuotti .../StatFin/StatFin/adopt/… — se on 404."""
        h = StatfinHarvester(conn=_memory_db())
        url = self._web_url(h, "StatFin/adopt", "11lv.px")
        assert "/StatFin/StatFin/adopt/" not in url


class TestPathToKeywords:
    """_path_to_keywords()-metodin testit."""

    def test_filters_root_path(self):
        h = StatfinHarvester(conn=_memory_db())
        assert h._path_to_keywords("StatFin") == []

    def test_extracts_subfolders(self):
        h = StatfinHarvester(conn=_memory_db())
        assert h._path_to_keywords("StatFin/vaesto/synt") == ["vaesto", "synt"]

    def test_luke_filters_root(self):
        h = LukeHarvester(conn=_memory_db())
        assert h._path_to_keywords("LUKE/metsa") == ["metsa"]


class TestCrawl:
    """_crawl_folder()-metodin testit."""

    @pytest.mark.asyncio
    async def test_crawl_tables_only(self):
        """Taulu-itemit (type=t) tallennetaan tietokantaan."""
        conn = _memory_db()
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "testi.px", "type": "t", "text": "Taulu", "updated": "2024-01-01"},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        count = await h._crawl_folder(mock_client, "https://example.com/", "StatFin")
        assert count == 1

        row = conn.execute("SELECT COUNT(*) FROM datasets WHERE source = 'statfin'").fetchone()
        assert row[0] == 1

    @pytest.mark.asyncio
    async def test_crawl_handles_error(self):
        """Virheelliset kansiot ohitetaan."""
        conn = _memory_db()
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("HTTP 400"))

        count = await h._crawl_folder(mock_client, "https://example.com/bad/", "StatFin")
        assert count == 0


SAMPLE_TABLE_META = {
    "title": "Testitaulu muuttujina Vuosi ja Tiedot",
    "variables": [
        {
            "code": "Vuosi",
            "text": "Vuosi",
            "values": ["2020", "2021", "2022", "2023"],
            "valueTexts": ["2020", "2021", "2022", "2023"],
        },
        {
            "code": "Tiedot",
            "text": "Tiedot",
            "values": ["val1", "val2"],
            "valueTexts": ["Arvo 1", "Arvo 2"],
        },
    ],
}


class TestHarvestDimensions:
    """harvest_dimensions()-metodin testit."""

    def _seed_dataset(self, conn: sqlite3.Connection) -> None:
        """Lisää yksi StatFin-datasetti kantaan testattavaksi."""
        h = StatfinHarvester(conn=conn)
        item = {"id": "testi.px", "type": "t", "text": "Taulu", "updated": "2024-01-01"}
        from aura.database import upsert_dataset
        ds = h._table_to_dataset(item, "StatFin", "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin/")
        upsert_dataset(conn, ds)

    @pytest.mark.asyncio
    async def test_enriches_data_fields(self):
        """Dimensiotiedot tallennetaan data_fields-rikastuksena."""
        conn = _memory_db()
        self._seed_dataset(conn)
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_TABLE_META
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest_dimensions()

        assert count == 1

        enrichments = get_enrichments(conn, "statfin-testi.px")
        fields_enr = [e for e in enrichments if e["field"] == "data_fields"]
        assert len(fields_enr) == 1
        fields = json.loads(fields_enr[0]["value"])
        assert len(fields) == 2
        assert fields[0]["code"] == "Vuosi"
        assert fields[0]["value_count"] == 4
        assert fields[1]["code"] == "Tiedot"

    @pytest.mark.asyncio
    async def test_enriches_temporal_coverage(self):
        """Aikadimensiosta lasketaan temporal_coverage."""
        conn = _memory_db()
        self._seed_dataset(conn)
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_TABLE_META
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest_dimensions()

        enrichments = get_enrichments(conn, "statfin-testi.px")
        temporal = [e for e in enrichments if e["field"] == "temporal_coverage"]
        assert len(temporal) == 1
        assert temporal[0]["value"] == "2020–2023"

    @pytest.mark.asyncio
    async def test_skips_already_enriched(self):
        """Jo rikastetut datasetit ohitetaan."""
        conn = _memory_db()
        self._seed_dataset(conn)
        h = StatfinHarvester(conn=conn)

        # Rikasta ensin
        from aura.database import add_enrichment
        add_enrichment(conn, "statfin-testi.px", "data_fields", "[]")

        mock_client = AsyncMock()
        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest_dimensions()

        assert count == 0
        # API:a ei kutsuttu
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        """API-virheet ohitetaan ilman crashia."""
        conn = _memory_db()
        self._seed_dataset(conn)
        h = StatfinHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("HTTP 500"))

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest_dimensions()

        assert count == 0

    @pytest.mark.asyncio
    async def test_limit_parameter(self):
        """limit-parametri rajoittaa rikastettavien määrää."""
        conn = _memory_db()
        h = StatfinHarvester(conn=conn)

        # Lisää kaksi datasettia
        from aura.database import upsert_dataset
        for i in range(2):
            item = {"id": f"t{i}.px", "type": "t", "text": f"Taulu {i}", "updated": ""}
            ds = h._table_to_dataset(item, "StatFin", "https://example.com/")
            upsert_dataset(conn, ds)

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_TABLE_META
        mock_resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest_dimensions(limit=1)

        assert count == 1
