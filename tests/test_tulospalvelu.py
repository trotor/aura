"""Testit oikeusministeriön tulospalvelu-harvesterille."""

import sqlite3

from aura.database import init_db
from aura.harvesters.tulospalvelu import TulospalveluHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestConfig:
    def test_name(self) -> None:
        assert TulospalveluHarvester.name == "tulospalvelu"

    def test_eleven_elections(self) -> None:
        """11 vaalia joilla on varmennettu lataus — ei enempää eikä vähempää."""
        assert len(TulospalveluHarvester.datasets_config) == 11

    def test_no_presidential_elections(self) -> None:
        """TPV-vaaleilla ei ole latauksia, joten niitä ei saa olla mukana."""
        ids = " ".join(c["id"] for c in TulospalveluHarvester.datasets_config)
        assert "tpv" not in ids.lower()
        assert "presidentin" not in ids.lower()


class TestResources:
    def test_six_resources_per_election(self) -> None:
        for cfg in TulospalveluHarvester.datasets_config:
            assert len(cfg["resources"]) == 6, cfg["id"]

    def test_url_pattern(self) -> None:
        cfg = next(
            c
            for c in TulospalveluHarvester.datasets_config
            if c["id"] == "tulospalvelu-ekv-2023"
        )
        urls = {r["url"] for r in cfg["resources"]}
        assert "https://tulospalvelu.vaalit.fi/EKV-2023/ekv-2023_ehd_maa.csv.zip" in urls
        assert "https://tulospalvelu.vaalit.fi/EKV-2023/ekv-2023_alu_maa.xml.zip" in urls

    def test_files_are_not_under_fi_directory(self) -> None:
        """fi/-polku palauttaa 404 — kaava on juuressa."""
        for cfg in TulospalveluHarvester.datasets_config:
            for r in cfg["resources"]:
                assert "/fi/" not in r["url"], r["url"]

    def test_all_levels_present(self) -> None:
        cfg = TulospalveluHarvester.datasets_config[0]
        urls = " ".join(r["url"] for r in cfg["resources"])
        assert "_ehd_maa." in urls
        assert "_puo_maa." in urls
        assert "_alu_maa." in urls


class TestHarvest:
    async def test_harvest_writes_eleven_datasets(self) -> None:
        conn = _memory_db()
        h = TulospalveluHarvester(conn=conn)
        count = await h.harvest()
        assert count == 11
        rows = conn.execute(
            "SELECT COUNT(*) c FROM datasets WHERE source = 'tulospalvelu'"
        ).fetchone()
        assert rows["c"] == 11

    async def test_licence_matches_site_terms(self) -> None:
        """Sivusto sanoo 'julkisia ja vapaasti käytettävissä' — ei CC BY 4.0.

        Suunnitelma odotti tässä CC-BY-4.0:aa, mutta se olisi väite jota
        lähde ei tue. Sama periaate kuin POHTIVAn kohdalla (task 4):
        lisenssiä ei keksitä, se kirjataan sellaisena kuin lähde sen
        ilmoittaa.
        """
        conn = _memory_db()
        h = TulospalveluHarvester(conn=conn)
        await h.harvest()
        row = conn.execute(
            "SELECT license_id, license_title FROM datasets "
            "WHERE id = 'tulospalvelu-ekv-2023'"
        ).fetchone()
        assert row["license_id"] == "other-open"
        assert "vapaasti käytettävissä" in row["license_title"]
