"""Testit SYKE-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.ckan import CkanHarvester
from aura.harvesters.syke import SykeHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


SAMPLE_SYKE_DATASET = {
    "id": "syke-test-1",
    "name": "pohjavesialueet",
    "title": "Pohjavesialueet",
    "title_translated": {"fi": "Pohjavesialueet", "en": "Groundwater areas"},
    "notes_translated": {"fi": "Suomen pohjavesialueet"},
    "notes": "Groundwater areas in Finland",
    "keywords": {"fi": ["pohjavesi", "ympäristö"], "en": ["groundwater"]},
    "organization": {"id": "syke", "name": "syke", "title": "SYKE"},
    "license_id": "cc-by-4.0",
    "license_title": "CC BY 4.0",
    "metadata_created": "2024-01-01T00:00:00",
    "metadata_modified": "2024-06-01T00:00:00",
    "num_resources": 1,
    "resources": [
        {
            "id": "res-syke-1",
            "name": "pohjavesialueet.shp",
            "format": "SHP",
            "url": "https://ckan.ymparisto.fi/dataset/pohjavesialueet/resource/pohjavesialueet.shp",
        }
    ],
}


def _mock_ckan_response(datasets: list[dict], total: int | None = None) -> dict:
    if total is None:
        total = len(datasets)
    return {"result": {"count": total, "results": datasets}}


class TestSykeConfig:
    """SYKE-harvesterin konfiguraatio."""

    def test_inherits_ckan_harvester(self):
        assert issubclass(SykeHarvester, CkanHarvester)

    def test_config_values(self):
        h = SykeHarvester(conn=_memory_db())
        assert h.name == "syke"
        assert h.ckan_source == "syke"
        assert "ymparisto.fi" in h.ckan_base_url
        assert h.url == "https://ckan.ymparisto.fi"


class TestSykeHarvest:
    """SYKE-harvesterin harvest()-testi."""

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """Harvest tallentaa datasetit tietokantaan oikealla source-arvolla."""
        conn = _memory_db()
        h = SykeHarvester(conn=conn)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_ckan_response(
            [SAMPLE_SYKE_DATASET], total=1
        )
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 1
        row = conn.execute(
            "SELECT source FROM datasets WHERE id = 'syke-test-1'"
        ).fetchone()
        assert row[0] == "syke"


class TestSuojelualueidenKerrokset:
    """Ulkoinen arvio 27.9.2026: suojelualueiden WFS osui rakennussuojelun kerrokseen."""

    RAW = {
        "id": "{C8FC4A42-A2C3-40C4-92CD-2299C688514E}",
        "name": "luonnonsuojelu-ja-eramaa-alueet",
        "title": "Luonnonsuojelu- ja erämaa-alueet",
        "resources": [
            {"id": "z", "name": "ZIP", "format": "ZIP", "url": "https://x.fi/a.zip"},
            {
                "id": "w",
                "name": "SuojellutAlueet WFS-latauspalvelu",
                "format": "",
                "url": "https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs",
            },
        ],
    }

    def test_kerrokset_lisataan_ensimmaisiksi(self):
        from aura.preview import _pick_resource
        from aura.wfs import type_name_from_url

        ds = SykeHarvester(conn=_memory_db())._to_dataset(self.RAW)
        layers = [type_name_from_url(r.url) for r in ds.resources[:3]]
        assert layers == [
            "inspire_ps:PS.ProtectedSitesValtionOmistamaLuonnonsuojelualue",
            "inspire_ps:PS.ProtectedSitesYksityistenMaillaOlevaLuonnonsuojelualue",
            "inspire_ps:PS.ProtectedSitesEramaaAlue",
        ]
        assert ds.resources[0].name_fi == "Valtion omistamat luonnonsuojelualueet (WFS)"
        assert ds.num_resources == 5
        picked = _pick_resource([r.model_dump() for r in ds.resources])
        assert picked is not None and "ValtionOmistama" in picked["url"]

    def test_muut_aineistot_ennallaan_ja_lisays_idempotentti(self):
        h = SykeHarvester(conn=_memory_db())
        other = h._to_dataset({**self.RAW, "id": "muu"})
        assert len(other.resources) == 2
        ds = h._to_dataset(self.RAW)
        again = h._to_dataset({**self.RAW, "resources": [r.model_dump() for r in ds.resources]})
        assert len(again.resources) == len(ds.resources)
