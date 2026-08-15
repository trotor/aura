"""Testit nollatuloskirjaukselle.

Tärkein testi on ``TestVikasietoisuus``: telemetria ei ole syy jonka takia
haku saa kaatua.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from aura.telemetry import (
    MAX_QUERY_LENGTH,
    TELEMETRY_DB_ENV,
    clear_zero_results,
    record_zero_result,
    telemetry_path,
    zero_result_gaps,
)


def _env(path: Path | str) -> dict[str, str]:
    return {TELEMETRY_DB_ENV: str(path)}


class TestOletuksenaPoisPaalta:
    """Kyselytekstin tallentaminen on tietosuojapäätös, ei oletusarvo."""

    def test_no_env_means_disabled(self) -> None:
        assert telemetry_path({}) is None

    def test_empty_value_means_disabled(self) -> None:
        assert telemetry_path({TELEMETRY_DB_ENV: "   "}) is None

    def test_recording_is_a_no_op_when_disabled(self) -> None:
        assert record_zero_result("mitä tahansa", {}) is False

    def test_gaps_are_empty_when_disabled(self) -> None:
        assert zero_result_gaps(env={}) == []


class TestKirjaus:
    def test_records_a_query(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "t.db")
        assert record_zero_result("hevosten kavionhoito", env) is True
        rows = zero_result_gaps(env=env)
        assert [r["query"] for r in rows] == ["hevosten kavionhoito"]
        assert rows[0]["count"] == 1

    def test_same_query_increments_instead_of_appending(self, tmp_path: Path) -> None:
        """Laskuri, ei tapahtumaloki.

        Yksi rivi per kysely on sekä yksityisyydensuoja (ei
        tapahtumakohtaisia aikaleimoja) että käyttökelpoisempi muoto:
        aukot halutaan yleisyysjärjestyksessä.
        """
        env = _env(tmp_path / "t.db")
        for _ in range(3):
            record_zero_result("sama kysely", env)
        rows = zero_result_gaps(env=env)
        assert len(rows) == 1
        assert rows[0]["count"] == 3

    def test_gaps_are_ordered_by_frequency(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "t.db")
        record_zero_result("harvinainen", env)
        for _ in range(4):
            record_zero_result("yleinen", env)
        assert [r["query"] for r in zero_result_gaps(env=env)] == [
            "yleinen", "harvinainen",
        ]

    def test_whitespace_is_normalised(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "t.db")
        record_zero_result("  kaksi   sanaa \n", env)
        assert zero_result_gaps(env=env)[0]["query"] == "kaksi sanaa"

    def test_empty_query_is_not_recorded(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "t.db")
        assert record_zero_result("   ", env) is False

    def test_overlong_query_is_truncated(self, tmp_path: Path) -> None:
        """Ylipitkä kysely on liite, ei hakusana.

        Katkaisu rajaa myös vahingossa mukaan tulevan henkilötiedon määrää.
        """
        env = _env(tmp_path / "t.db")
        record_zero_result("a" * (MAX_QUERY_LENGTH + 500), env)
        assert len(zero_result_gaps(env=env)[0]["query"]) == MAX_QUERY_LENGTH

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "syva" / "polku" / "t.db")
        assert record_zero_result("kysely", env) is True


class TestOhjausmerkit:
    """Kysely tulee etäkäyttäjältä ja päätyy ylläpitäjän terminaaliin.

    Ilman suodatusta hakuun voi upottaa ANSI-koodeja, jotka terminaali
    tottelee: ``\\x1b[2K`` pyyhkii rivin ja sen perään kirjoitettu teksti
    näyttää työkalun omalta tulosteelta.
    """

    def test_escape_sequences_are_stripped_on_write(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "t.db")
        record_zero_result("aito\x1b[2K\x1b[1;31mVÄÄRENNÖS\x1b[0m", env)
        stored = zero_result_gaps(env=env)[0]["query"]
        assert "\x1b" not in str(stored)
        assert "aito" in str(stored)

    def test_control_characters_never_reach_the_database(
        self, tmp_path: Path
    ) -> None:
        """Suodatus tehdään kirjoitettaessa, joten kanta on aina puhdas."""
        path = tmp_path / "t.db"
        record_zero_result("rivinvaihto\r\nja\x00nolla", _env(path))
        with sqlite3.connect(path) as conn:
            raw = conn.execute("SELECT query FROM zero_results").fetchone()[0]
        assert all(ord(ch) >= 0x20 and ord(ch) != 0x7F for ch in raw)

    def test_old_rows_are_sanitised_on_read(self, tmp_path: Path) -> None:
        """Ennen korjausta kirjatut rivit eivät saa vuotaa tulosteeseen."""
        path = tmp_path / "t.db"
        record_zero_result("siisti", _env(path))
        with sqlite3.connect(path) as conn:
            conn.execute(
                "INSERT INTO zero_results (query, count, first_seen, last_seen) "
                "VALUES (?, 9, '2026-01-01', '2026-01-01')",
                ("vanha\x1b[31mrivi",),
            )
        assert all("\x1b" not in str(r["query"]) for r in zero_result_gaps(env=_env(path)))

    def test_query_of_only_control_characters_is_not_recorded(
        self, tmp_path: Path
    ) -> None:
        assert record_zero_result("\x1b\x00\x07", _env(tmp_path / "t.db")) is False


class TestVikasietoisuus:
    """Telemetria ei ole syy jonka takia haku saa kaatua."""

    def test_unwritable_path_does_not_raise(self, tmp_path: Path) -> None:
        """Tuotannossa tiedostojärjestelmä on **tarkoituksella** read-only."""
        blocked = tmp_path / "lukittu"
        blocked.mkdir()
        blocked.chmod(0o500)
        try:
            assert record_zero_result("kysely", _env(blocked / "t.db")) is False
        finally:
            blocked.chmod(0o700)

    def test_corrupt_database_does_not_raise(self, tmp_path: Path) -> None:
        path = tmp_path / "rikki.db"
        path.write_bytes(b"tama ei ole sqlite-kanta")
        assert record_zero_result("kysely", _env(path)) is False
        assert zero_result_gaps(env=_env(path)) == []

    def test_reading_a_missing_database_is_empty(self, tmp_path: Path) -> None:
        assert zero_result_gaps(env=_env(tmp_path / "ei-ole.db")) == []


class TestSailytys:
    def test_clear_removes_everything(self, tmp_path: Path) -> None:
        env = _env(tmp_path / "t.db")
        record_zero_result("a", env)
        record_zero_result("b", env)
        assert clear_zero_results(env) == 2
        assert zero_result_gaps(env=env) == []

    def test_clear_on_missing_database_is_zero(self, tmp_path: Path) -> None:
        assert clear_zero_results(_env(tmp_path / "ei-ole.db")) == 0

    def test_only_query_and_counts_are_stored(self, tmp_path: Path) -> None:
        """Ei istuntoa, ei tunnistetta, ei IP:tä.

        Jos tähän tauluun lisätään sarake, se on tietosuojapäätös ja tämän
        testin pitää kaatua siitä.
        """
        path = tmp_path / "t.db"
        record_zero_result("kysely", _env(path))
        with sqlite3.connect(path) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(zero_results)")]
        assert cols == ["query", "count", "first_seen", "last_seen"]
