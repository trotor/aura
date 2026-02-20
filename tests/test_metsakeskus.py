"""Testit Metsäkeskus-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.metsakeskus import (
    DOWNLOAD_BASE,
    DOWNLOAD_ONLY_DATASETS,
    INFO_PAGE_URL,
    SERVICES,
    MetsakeskusHarvester,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> MetsakeskusHarvester:
    return MetsakeskusHarvester(conn=_memory_db())


class TestServiceToDataset:
    """Palveluiden resurssien URL-osoitteet."""

    def test_download_url_is_specific(self):
        """Palvelut joilla on download_dir saavat spesifisen lataus-URLin."""
        h = _harvester()
        svc = next(s for s in SERVICES if s["endpoint"] == "stand")
        ds = h._service_to_dataset(svc)

        download_resources = [r for r in ds.resources if r.format == "ZIP"]
        assert len(download_resources) == 1
        assert download_resources[0].url == f"{DOWNLOAD_BASE}/Metsavarakuviot/"
        assert "Metsavarakuviot" in download_resources[0].url

    def test_no_generic_download_url(self):
        """Yksikään resurssi ei osoita geneeriseen /aineistot/ ilman alihakemistoa."""
        h = _harvester()
        for svc in SERVICES:
            ds = h._service_to_dataset(svc)
            for r in ds.resources:
                if r.format == "ZIP":
                    assert r.url != "https://avoin.metsakeskus.fi/aineistot/"
                    assert r.url != f"{DOWNLOAD_BASE}/"

    def test_service_without_download_dir_gets_html(self):
        """WCS-palvelut ilman download_dir:iä saavat HTML-infosivun."""
        h = _harvester()
        svc = next(s for s in SERVICES if s["endpoint"] == "CHM_newest")
        ds = h._service_to_dataset(svc)

        html_resources = [r for r in ds.resources if r.format == "HTML"]
        assert len(html_resources) == 1
        assert html_resources[0].url == INFO_PAGE_URL

        zip_resources = [r for r in ds.resources if r.format == "ZIP"]
        assert len(zip_resources) == 0

    def test_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        for svc in SERVICES:
            ds = h._service_to_dataset(svc)
            assert ds.num_resources == len(ds.resources)


class TestChmYearDataset:
    """CHM-vuosiversioiden datasetit."""

    def test_chm_has_zip_resource(self):
        """CHM-vuosiversion datasetissä on ZIP-resurssi."""
        h = _harvester()
        ds = h._chm_year_dataset(2020)

        zip_resources = [r for r in ds.resources if r.format == "ZIP"]
        assert len(zip_resources) == 1
        assert zip_resources[0].url == f"{DOWNLOAD_BASE}/Latvusmalli/"

    def test_chm_num_resources(self):
        """CHM-datasetissä on 2 resurssia (WCS + ZIP)."""
        h = _harvester()
        ds = h._chm_year_dataset(2015)
        assert ds.num_resources == 2
        assert len(ds.resources) == 2


class TestKemeraDataset:
    """Kemera-datasettien resurssit."""

    def test_kemera_has_zip_resource(self):
        """Kemera-datasetissä on ZIP-resurssi."""
        h = _harvester()
        ds = h._kemera_dataset("application_stand_06_16", "Kemera: taimikon varhaishoito (hakemus)")

        zip_resources = [r for r in ds.resources if r.format == "ZIP"]
        assert len(zip_resources) == 1
        assert zip_resources[0].url == f"{DOWNLOAD_BASE}/Kemera/"

    def test_kemera_num_resources(self):
        """Kemera-datasetissä on 2 resurssia (WFS + ZIP)."""
        h = _harvester()
        ds = h._kemera_dataset("application_stand_06_16", "Kemera: test")
        assert ds.num_resources == 2
        assert len(ds.resources) == 2


class TestDownloadOnlyDataset:
    """Lataus-only datasetit (ei API-endpointia)."""

    def test_korjuukelpoisuus_dataset(self):
        """Korjuukelpoisuus-datasetti luodaan oikein."""
        h = _harvester()
        cfg = DOWNLOAD_ONLY_DATASETS[0]
        ds = h._download_only_dataset(cfg)

        assert ds.id == "metsakeskus-korjuukelpoisuus"
        assert ds.title == "Korjuukelpoisuus"
        assert ds.num_resources == 1
        assert len(ds.resources) == 1
        assert ds.resources[0].format == "ZIP"
        assert ds.resources[0].url == f"{DOWNLOAD_BASE}/Korjuukelpoisuus/"


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (43)."""
        h = _harvester()
        count = await h.harvest()
        # 11 pääpalvelua + 15 CHM-vuotta + 16 Kemeraa + 1 Korjuukelpoisuus = 43
        assert count == 43
