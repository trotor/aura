"""Testit Tilastokeskuksen paikkatietoaineistojen harvesterille."""

import sqlite3
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.statfin_geo import (
    GEOSERVER_BASE,
    PAAVO_FALLBACK_YEAR,
    StatfinGeoHarvester,
)

#: Alkuperäinen metodi talteen ennen kuin kiinnitys korvaa sen.
_LATEST_YEAR = StatfinGeoHarvester._latest_paavo_year


@pytest.fixture(autouse=True)
def _ei_verkkoa() -> Iterator[None]:
    """Paavon uusin vuosi luetaan kyvyistä; testeissä se on kiinteä."""
    with patch.object(StatfinGeoHarvester, "_latest_paavo_year", AsyncMock(return_value=2026)):
        yield


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> StatfinGeoHarvester:
    return StatfinGeoHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_all_ids_have_prefix(self):
        """Kaikkien datasettien id:t alkavat 'statfin-geo-' -etuliitteellä."""
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("statfin-geo-")

    def test_all_datasets_have_wfs_and_wms(self):
        """Jokaisessa datasetissä on sekä WFS- että WMS-resurssi."""
        h = _harvester()
        for cfg in h.datasets_config:
            formats = {r["format"] for r in cfg["resources"]}
            assert formats == {"WFS", "WMS"}, f"{cfg['id']}: {formats}"

    def test_urls_point_to_geoserver(self):
        """Resurssien URL:t osoittavat geo.stat.fi GeoServerille."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert r["url"].startswith(GEOSERVER_BASE), r["url"]

    def test_dataset_count(self):
        """Datasettejä on 9 kpl."""
        h = _harvester()
        assert len(h.datasets_config) == 9


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        """harvest() palauttaa oikean datasettien lukumäärän (9)."""
        h = _harvester()
        count = await h.harvest()
        assert count == 9

    @pytest.mark.asyncio
    async def test_num_resources_matches(self):
        """num_resources vastaa resurssien todellista määrää."""
        h = _harvester()
        await h.harvest()

        datasets = h.conn.execute(
            "SELECT id, num_resources FROM datasets WHERE source = 'statfin-geo'"
        ).fetchall()
        for ds in datasets:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (ds["id"],),
            ).fetchone()[0]
            assert ds["num_resources"] == actual


class TestPaavoTilastokerros:
    """Ulkoinen arvio 27.9.2026: Paavon WFS osui rajakerrokseen, ei tunnuslukuihin."""

    @pytest.mark.asyncio
    async def test_tilastokerros_on_ensimmainen_resurssi(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT id, name_fi, format, url FROM resources"
            " WHERE dataset_id = 'statfin-geo-paavo' ORDER BY rowid"
        ).fetchall()
        first = rows[0]
        assert first["id"] == "statfin-geo-paavo-wfs-tilasto"
        assert first["name_fi"] == "Paavo-tunnusluvut 2026 (WFS)"
        assert first["url"].endswith("typeName=postialue:pno_tilasto_2026")
        # Rajakerroksen resurssi säilyttää tunnuksensa ja osoitteensa.
        ids = {r["id"]: r["url"] for r in rows}
        assert ids["statfin-geo-paavo-wfs"] == f"{GEOSERVER_BASE}/postialue/wfs"
        notes = h.conn.execute(
            "SELECT notes_fi FROM datasets WHERE id = 'statfin-geo-paavo'"
        ).fetchone()[0]
        assert "he_vakiy" in notes and "pno_tilasto_2026" in notes

    @pytest.mark.asyncio
    async def test_luokan_konfiguraatio_ei_muutu(self):
        h = _harvester()
        await h.harvest()
        paavo = next(
            c for c in StatfinGeoHarvester.datasets_config if c["id"] == "statfin-geo-paavo"
        )
        assert len(paavo["resources"]) == 2


class TestUusinVuosi:
    @staticmethod
    def _caps(names: list[str]) -> str:
        types = "".join(f"<FeatureType><Name>{n}</Name></FeatureType>" for n in names)
        return f"<WFS_Capabilities><FeatureTypeList>{types}</FeatureTypeList></WFS_Capabilities>"

    @pytest.mark.asyncio
    async def test_uusin_vuosi_kyvyista(self):
        h = _harvester()
        resp = MagicMock()
        resp.text = self._caps(
            [
                "postialue:pno",
                "postialue:pno_tilasto",
                "postialue:pno_tilasto_2024",
                "postialue:pno_tilasto_2027",
                "postialue:pno_meri_2030",
            ]
        )
        with patch.object(h, "_fetch", AsyncMock(return_value=resp)):
            assert await _LATEST_YEAR(h) == 2027

    @pytest.mark.asyncio
    async def test_varavuosi_kun_palvelu_ei_vastaa(self):
        h = _harvester()
        with patch.object(h, "_fetch", AsyncMock(side_effect=RuntimeError("nurin"))):
            assert await _LATEST_YEAR(h) == PAAVO_FALLBACK_YEAR
