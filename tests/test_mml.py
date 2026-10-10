"""Testit MML-harvesterille."""

import sqlite3

import pytest

from aura.database import init_db
from aura.harvesters.mml import _HINTA_JA_ARVO, MmlHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> MmlHarvester:
    return MmlHarvester(conn=_memory_db())


class TestConfig:
    """Konfiguraation rakenne."""

    def test_all_ids_have_prefix(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert cfg["id"].startswith("mml-")

    def test_all_datasets_have_resources(self):
        h = _harvester()
        for cfg in h.datasets_config:
            assert len(cfg["resources"]) >= 1, cfg["id"]

    def test_urls_point_to_mml(self):
        """MML:n osoitteet; kauppahintatilasto julkaistaan Tilastokeskuksen sivuilla."""
        h = _harvester()
        for cfg in h.datasets_config:
            for r in cfg["resources"]:
                assert "maanmittauslaitos.fi" in r["url"] or "stat.fi" in r["url"], r["url"]

    def test_dataset_count(self):
        h = _harvester()
        assert len(h.datasets_config) == 7 + len(_HINTA_JA_ARVO)

    def test_all_api_datasets_require_registration(self):
        """Rajapinnat vaativat API-avaimen; hinta- ja arvomerkinnät eivät ole rajapintoja."""
        h = _harvester()
        hinnat = {c["id"] for c in _HINTA_JA_ARVO}
        for cfg in h.datasets_config:
            if cfg["id"] not in hinnat:
                assert cfg.get("access_level") == "registration", cfg["id"]


class TestHarvest:
    """harvest()-metodin kokonaistoiminta."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self):
        h = _harvester()
        count = await h.harvest()
        assert count == 7 + len(_HINTA_JA_ARVO)

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self):
        h = _harvester()
        await h.harvest()
        rows = h.conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'mml'"
        ).fetchone()
        assert rows[0] == 7 + len(_HINTA_JA_ARVO)

    @pytest.mark.asyncio
    async def test_resources_saved(self):
        h = _harvester()
        await h.harvest()
        for cfg in h.datasets_config:
            actual = h.conn.execute(
                "SELECT COUNT(*) FROM resources WHERE dataset_id = ?",
                (cfg["id"],),
            ).fetchone()[0]
            assert actual == len(cfg["resources"])


class TestMetsanHintaJaArvo:
    """Metsän hinta: mikä on avointa ja mistä muu saadaan (10.10.2026).

    Puuston hakkuuarvon voi laskea avoimesta datasta, mutta toteutuneet
    kauppahinnat ja Tapion arvotaulukot eivät ole avoimia. Merkintöjen tehtävä
    on ohjata kysyjä oikeaan lähteeseen eikä luvata avointa dataa.
    """

    def _cfg(self) -> dict[str, dict[str, object]]:
        return {str(c["id"]): c for c in _harvester().datasets_config}

    def test_suljetut_aineistot_merkitty_suljetuiksi(self):
        cfg = self._cfg()
        for ds_id in ("mml-kauppahintarekisteri", "mml-metsatilakauppojen-kauppahinta-aineisto"):
            assert cfg[ds_id]["access_level"] == "restricted", ds_id
            assert "Ei avointa dataa" in str(cfg[ds_id]["license_title"])

    def test_summa_arvo_ohjaa_avoimiin_laskentatietoihin(self):
        notes = str(self._cfg()["mml-summa-arvomenetelma"]["notes_fi"])
        assert "metsakeskus-stand" in notes
        assert "luke-0100_teokau.px" in notes
        assert "kiinteistötunnus" in notes
        assert "ei siis ole tilan hinta" in notes
