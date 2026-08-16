"""Testit Metsäkeskus-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.metsakeskus import (
    DOWNLOAD_BASE,
    INFO_PAGE_URL,
    MetsakeskusHarvester,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> MetsakeskusHarvester:
    return MetsakeskusHarvester(conn=_memory_db())


class TestMainServices:
    """Pääpalveluiden konfiguraatiot."""

    def test_download_url_is_specific(self):
        """Palvelut joilla on tiedostolataus saavat spesifisen lataus-URLin."""
        h = _harvester()
        stand = next(c for c in h.datasets_config if c["id"] == "metsakeskus-stand")
        zip_resources = [r for r in stand["resources"] if r["format"] == "ZIP"]
        assert len(zip_resources) == 1
        assert zip_resources[0]["url"] == f"{DOWNLOAD_BASE}/Metsavarakuviot/"

    def test_no_generic_download_url(self):
        """Yksikään resurssi ei osoita geneeriseen /aineistot/ ilman alihakemistoa."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                if r["format"] == "ZIP":
                    assert r["url"] != f"{DOWNLOAD_BASE}/"

    def test_service_without_download_dir_gets_html(self):
        """WCS-palvelut ilman tiedostolatausta saavat HTML-infosivun."""
        h = _harvester()
        chm = next(c for c in h.datasets_config if c["id"] == "metsakeskus-chm_newest")
        html_resources = [r for r in chm["resources"] if r["format"] == "HTML"]
        zip_resources = [r for r in chm["resources"] if r["format"] == "ZIP"]
        assert len(html_resources) == 1
        assert html_resources[0]["url"] == INFO_PAGE_URL
        assert len(zip_resources) == 0


class TestChmYears:
    """CHM-vuosiversioiden konfiguraatio."""

    def test_chm_year_config_has_years(self):
        """CHM-vuosiversion konfiguraatiossa on years-kenttä."""
        h = _harvester()
        chm_year = next(c for c in h.datasets_config if "years" in c and "chm" in c["id"])
        # Vuosivalikoima seuraa rajapinnan tarjontaa, ei kiinteää lukua:
        # 2008–2022 olivat listalla mutta vastasivat HTTP 404:llä.
        years = list(chm_year["years"])
        assert years, "latvusmallivuodet kadonneet"
        assert years == list(range(min(years), max(years) + 1)), "vuosissa aukko"

    def test_chm_has_wcs_and_zip(self):
        """CHM-vuosiversion konfiguraatiossa on WCS ja ZIP."""
        h = _harvester()
        chm_year = next(c for c in h.datasets_config if "years" in c and "chm" in c["id"])
        formats = {r["format"] for r in chm_year["resources"]}
        assert formats == {"WCS", "WMS", "ZIP"}


class TestKemera:
    """Kemera-datasettien konfiguraatio."""

    def test_kemera_has_wfs_and_zip(self):
        """Kemera-dataseteissä on WFS ja ZIP."""
        h = _harvester()
        kemera = [c for c in h.datasets_config if "kemera" in c.get("title", "").lower()]
        assert len(kemera) == 16
        for cfg in kemera:
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"WFS", "ZIP"}

    def test_kemera_zip_url_points_to_kemera_dir(self):
        """Kemera-datasettien ZIP-URL osoittaa Kemera-hakemistoon."""
        h = _harvester()
        kemera = [c for c in h.datasets_config if "kemera" in c.get("title", "").lower()]
        for cfg in kemera:
            zip_r = next(r for r in cfg["resources"] if r["format"] == "ZIP")
            assert zip_r["url"] == f"{DOWNLOAD_BASE}/Kemera/"


class TestDownloadOnly:
    """Lataus-only datasetit."""

    def test_korjuukelpoisuus(self):
        """Korjuukelpoisuus-datasetti on konfiguroitu oikein."""
        h = _harvester()
        cfg = next(c for c in h.datasets_config if c["id"] == "metsakeskus-korjuukelpoisuus")
        assert cfg["title"] == "Korjuukelpoisuus"
        assert len(cfg["resources"]) == 1
        assert cfg["resources"][0]["format"] == "ZIP"
        assert cfg["resources"][0]["url"] == f"{DOWNLOAD_BASE}/Korjuukelpoisuus/"


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa kaikkien konfiguroitujen datasettien määrän.

        Laskettu konfiguraatiosta: kiinteä luku rikkoutui aina kun
        rajapinnan vuosivalikoima muuttui, kertomatta mitään viasta.
        """
        h = _harvester()
        count = await h.harvest()
        odotettu = sum(len(list(c["years"])) if "years" in c else 1 for c in h.datasets_config)
        assert count == odotettu

    @pytest.mark.asyncio
    async def test_harvest_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'metsakeskus'"
        ).fetchall()
        for ds in datasets:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()[0]
            assert ds["num_resources"] == actual, f"Mismatch for {ds['id']}"
