"""Testit laatu- ja saatavuussignaalien vaikutukselle hakujärjestykseen.

Signaalit ovat tarkoituksella heikkoja: ne ratkaisevat lähes tasaväkiset
osumat eivätkä saa nostaa epärelevanttia aineistoa relevantin ohi.
"""

import sqlite3

from aura.database import (
    BROKEN_PENALTY,
    NEUTRAL_QUALITY,
    QUALITY_WEIGHT,
    init_db,
    search_datasets,
    upsert_dataset,
)
from aura.models import Dataset, Resource


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _dataset(ds_id: str, title: str) -> Dataset:
    return Dataset(
        id=ds_id,
        name=ds_id,
        title=title,
        title_fi=title,
        notes_fi="Kuvaus vedenlaadun seurannasta järvissä ja joissa.",
        organization_id="org-1",
        organization_name="org",
        organization_title="Testivirasto",
        num_resources=1,
        resources=[
            Resource(id=f"res-{ds_id}", name="d.csv", format="CSV", url="https://x/1")
        ],
    )


def _quality(conn: sqlite3.Connection, ds_id: str, score: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO quality_scores (dataset_id, dimension, score, "
        "calculated_at) VALUES (?, 'overall', ?, '2026-07-27')",
        (ds_id, score),
    )
    conn.commit()


def _health(conn: sqlite3.Connection, ds_id: str, available: bool) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO resource_health (resource_id, dataset_id, url, "
        "is_available, checked_at) VALUES (?, ?, 'https://x/1', ?, '2026-07-27')",
        (f"res-{ds_id}", ds_id, 1 if available else 0),
    )
    conn.commit()


class TestQualitySignal:
    def test_higher_quality_ranks_first(self) -> None:
        """Kahdesta samanveroisesta osumasta parempilaatuinen nousee."""
        conn = _db()
        upsert_dataset(conn, _dataset("heikko", "Vedenlaatu järvissä A"))
        upsert_dataset(conn, _dataset("hyva", "Vedenlaatu järvissä B"))
        conn.commit()
        _quality(conn, "heikko", 20.0)
        _quality(conn, "hyva", 95.0)

        results = [r["id"] for r in search_datasets(conn, "vedenlaatu")]
        assert results.index("hyva") < results.index("heikko")

    def test_missing_quality_is_neutral(self) -> None:
        """Pisteiden puuttuminen ei saa olla rangaistus."""
        conn = _db()
        upsert_dataset(conn, _dataset("pisteeton", "Vedenlaatu järvissä A"))
        upsert_dataset(conn, _dataset("heikko", "Vedenlaatu järvissä B"))
        conn.commit()
        _quality(conn, "heikko", 10.0)

        results = [r["id"] for r in search_datasets(conn, "vedenlaatu")]
        assert results.index("pisteeton") < results.index("heikko")

    def test_quality_score_exposed_in_results(self) -> None:
        conn = _db()
        upsert_dataset(conn, _dataset("a", "Vedenlaatu järvissä"))
        conn.commit()
        _quality(conn, "a", 77.0)

        results = search_datasets(conn, "vedenlaatu")
        assert results[0]["quality_score"] == 77.0

    def test_weight_is_bounded(self) -> None:
        """Laatu ei saa kääntää selvästi parempaa tekstiosumaa."""
        assert 0 < QUALITY_WEIGHT <= 0.25
        assert NEUTRAL_QUALITY == 50.0


class TestHealthSignal:
    def test_broken_resources_demoted(self) -> None:
        conn = _db()
        upsert_dataset(conn, _dataset("rikki", "Vedenlaatu järvissä A"))
        upsert_dataset(conn, _dataset("toimii", "Vedenlaatu järvissä B"))
        conn.commit()
        _health(conn, "rikki", available=False)
        _health(conn, "toimii", available=True)

        results = [r["id"] for r in search_datasets(conn, "vedenlaatu")]
        assert results.index("toimii") < results.index("rikki")

    def test_unchecked_is_not_penalised(self) -> None:
        """Tarkistamaton resurssi ei ole sama kuin rikkinäinen.

        resource_health kattaa noin prosentin korpuksesta, joten oletuksen on
        oltava hyväntahtoinen.
        """
        conn = _db()
        upsert_dataset(conn, _dataset("rikki", "Vedenlaatu järvissä A"))
        upsert_dataset(conn, _dataset("tuntematon", "Vedenlaatu järvissä B"))
        conn.commit()
        _health(conn, "rikki", available=False)

        results = [r["id"] for r in search_datasets(conn, "vedenlaatu")]
        assert results.index("tuntematon") < results.index("rikki")

    def test_penalty_is_bounded(self) -> None:
        assert 0 < BROKEN_PENALTY < 1.0


class TestSignalsDoNotOverrideRelevance:
    def test_weak_match_stays_below_strong_match(self) -> None:
        """Laatusignaali ei saa nostaa heikkoa osumaa vahvan ohi."""
        conn = _db()
        upsert_dataset(conn, _dataset("osuva", "Vedenlaatu järvissä"))
        heikko = _dataset("sivuava", "Ilmanlaatu kaupungeissa")
        heikko.notes_fi = "Mainitsee vedenlaadun ohimennen."
        upsert_dataset(conn, heikko)
        conn.commit()
        _quality(conn, "osuva", 10.0)
        _quality(conn, "sivuava", 100.0)

        results = [r["id"] for r in search_datasets(conn, "vedenlaatu järvissä")]
        assert results[0] == "osuva"
