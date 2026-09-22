"""Testit sille että jaeltu kanta saa olla koodia vanhempi.

Julkinen instanssi ajaa **tilannekuvaa**: kanta on paistettu imageen ja
avataan read-only, joten migraatioita ei voi ajaa käynnistyksessä. Kun
koodi on kannan jäljessä tuoreempi, uusimman migraation taulu puuttuu.

Näin kävi tuotannossa 22.8.–18.9.2026: `probe_results` puuttui jaellusta
kannasta, ja suojaamaton kysely kaatoi ländärisivun, `stats`-työkalun ja
`describe`-työkalun **jokaisella** datasetillä neljän viikon ajan. `/health`
ei koskenut tauluun, joten mikään ei kertonut siitä.

Ydinreitin on kestettävä puuttuva valinnainen taulu — mutta ei hiljaa:
puute kirjataan lokiin kerran, koska hiljainen ohitus oli itse vika.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import server first to avoid circular import when importing from tools
import aura.server  # noqa: F401
from aura.database import (
    EXPECTED_SCHEMA_VERSION,
    MIGRATIONS_DIR,
    SchemaTooOldError,
    _warned_missing_tables,
    check_schema_freshness,
    get_stats,
    init_db,
    require_current_schema,
    schema_version,
)
from aura.quality import collect_agent_facts
from aura.tools.describe import _format_probe_failure
from aura.web.app import create_app


@pytest.fixture
def vanha_kanta() -> sqlite3.Connection:
    """Kanta josta puuttuu viimeisimmän migraation taulu."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    conn.execute("DROP TABLE probe_results")
    conn.commit()
    # Varoitus annetaan kerran per prosessi, joten testien on nollattava
    # muisti — muuten järjestys ratkaisisi kumpi testi näkee varoituksen.
    _warned_missing_tables.clear()
    return conn


def test_tilastot_toimivat_ilman_probe_taulua(vanha_kanta: sqlite3.Connection) -> None:
    """Ländärisivu ja stats-työkalu kutsuvat tätä — ne eivät saa kaatua."""
    stats = get_stats(vanha_kanta)
    assert stats["total_datasets"] == 1
    assert stats["probe_total"] == 0
    assert stats["probe_ok"] == 0


def test_describe_toimii_ilman_probe_taulua(vanha_kanta: sqlite3.Connection) -> None:
    assert _format_probe_failure(vanha_kanta, "d1") == ""


def test_laatufaktat_toimivat_ilman_probe_taulua(
    vanha_kanta: sqlite3.Connection,
) -> None:
    assert collect_agent_facts(vanha_kanta) == {}


def test_puuttuva_taulu_ei_jaa_hiljaiseksi(
    vanha_kanta: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Puute on korjattavissa vain jos se näkyy jossain."""
    with caplog.at_level(logging.WARNING, logger="aura.database"):
        get_stats(vanha_kanta)
    assert any("probe_results" in r.message for r in caplog.records)


class TestSkeemataso:
    """Kannan ja koodin tason ero on kerrottava numeroina, ei pääteltävä.

    Vika 22.8.–18.9.2026 syntyi siitä että image paistoi yhteen koodin
    (migraatiotaso 22) ja kannan (taso 21). Kumpikaan ei tiennyt toisestaan.
    """

    def test_odotettu_versio_vastaa_migraatiohakemistoa(self) -> None:
        """Vakio on koodissa, koska imageen ei kopioida scripts/-hakemistoa.

        Kaksi totuuden lähdettä olisi vaarallisempi kuin yksi vakio: siksi
        tämä testi pitää vakion ja hakemiston synkassa. Jos lisäät
        migraation ja unohdat vakion, tämä kaatuu.
        """
        viimeisin = max(
            int(polku.stem.split("_", 1)[0]) for polku in MIGRATIONS_DIR.glob("*.sql")
        )
        assert EXPECTED_SCHEMA_VERSION == viimeisin, (
            f"scripts/migrations/ on tasolla {viimeisin} mutta "
            f"EXPECTED_SCHEMA_VERSION on {EXPECTED_SCHEMA_VERSION}. "
            "Nosta vakio, muuten jaeltava kanta pääsee koodia vanhemmaksi "
            "ilman että mikään huomaa."
        )

    def test_ajantasainen_kanta_kertoo_saman_tason(self) -> None:
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        assert schema_version(conn) == EXPECTED_SCHEMA_VERSION
        assert check_schema_freshness(conn) == (
            EXPECTED_SCHEMA_VERSION,
            EXPECTED_SCHEMA_VERSION,
        )

    def test_vanha_kanta_kirjaa_molemmat_tasot(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Pelkkä "kanta on vanha" ei riitä: korjaaja tarvitsee luvut."""
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = ?",
            (EXPECTED_SCHEMA_VERSION,),
        )
        with caplog.at_level(logging.ERROR, logger="aura.database"):
            kannassa, koodissa = check_schema_freshness(conn)
        assert (kannassa, koodissa) == (
            EXPECTED_SCHEMA_VERSION - 1,
            EXPECTED_SCHEMA_VERSION,
        )
        viesti = " ".join(r.getMessage() for r in caplog.records)
        assert str(EXPECTED_SCHEMA_VERSION - 1) in viesti
        assert str(EXPECTED_SCHEMA_VERSION) in viesti

    def test_tuntematon_kanta_ei_valita(self, caplog: pytest.LogCaptureFixture) -> None:
        """Kanta ilman schema_migrations-taulua ei ole vanha vaan tyhjä.

        Tällaisia ovat testien minikannat ja vasta luodut kannat, joihin
        migraatiot ajetaan seuraavaksi. Väärä hälytys opettaa ohittamaan
        oikeankin.
        """
        conn = sqlite3.connect(":memory:")
        with caplog.at_level(logging.ERROR, logger="aura.database"):
            assert check_schema_freshness(conn) == (0, EXPECTED_SCHEMA_VERSION)
        assert not caplog.records

    def test_require_current_schema_kaatuu_vanhaan_kantaan(self) -> None:
        """Buildissa vanha kanta on korjattavissa, joten siellä kaadutaan."""
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = ?",
            (EXPECTED_SCHEMA_VERSION,),
        )
        with pytest.raises(SchemaTooOldError) as virhe:
            require_current_schema(conn)
        assert str(EXPECTED_SCHEMA_VERSION - 1) in str(virhe.value)
        assert str(EXPECTED_SCHEMA_VERSION) in str(virhe.value)

    def test_require_current_schema_hyvaksyy_ajantasaisen(self) -> None:
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        require_current_schema(conn)


class TestKaynnistys:
    """Ero on todettava käynnistyksessä, ei vasta rikkinäisessä vastauksessa.

    Testataan web-sovelluksen kautta, ei yhdistetyn ASGI-sovelluksen:
    ``create_asgi_app()`` poistaa read-only-tilassa kirjoittavat toolit
    prosessin globaalista MCP-singletonista, ja se vuotaisi myöhempiin
    testeihin. Sama lifespan ajetaan tuotannossa osana ketjua.
    """

    def _kanta(self, polku: Path, *, vanha: bool) -> Path:
        conn = sqlite3.connect(polku)
        init_db(conn)
        if vanha:
            conn.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (EXPECTED_SCHEMA_VERSION,),
            )
        conn.commit()
        conn.close()
        return polku

    def test_vanha_kanta_kirjataan_kaynnistyksessa(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        polku = self._kanta(tmp_path / "aura.db", vanha=True)
        monkeypatch.setenv("AURA_DB", str(polku))
        monkeypatch.setenv("AURA_READONLY", "1")
        with caplog.at_level(logging.ERROR, logger="aura.database"):
            with TestClient(create_app()) as c:
                assert c.get("/").status_code == 200
        viesti = " ".join(r.getMessage() for r in caplog.records)
        assert str(EXPECTED_SCHEMA_VERSION - 1) in viesti
        assert str(EXPECTED_SCHEMA_VERSION) in viesti

    def test_ajantasainen_kanta_ei_kirjaa_mitaan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        polku = self._kanta(tmp_path / "aura.db", vanha=False)
        monkeypatch.setenv("AURA_DB", str(polku))
        monkeypatch.setenv("AURA_READONLY", "1")
        with caplog.at_level(logging.ERROR, logger="aura.database"):
            with TestClient(create_app()) as c:
                assert c.get("/").status_code == 200
        assert not [
            r for r in caplog.records if "migraatiotasolla" in r.getMessage()
        ]
