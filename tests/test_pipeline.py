"""Testit jaetulle harvestointiputkelle (aura.pipeline).

Moduuli on olemassa siksi, että harvestointi tapahtui aiemmin kahdessa
paikassa: `aura harvest` ja `aura refresh`. Ne ehtivät jo eriytyä — vain
toisessa oli määrävertailu, eikä kumpikaan indeksoinut lemmoja.
"""

import sqlite3
from typing import Any

import pytest

from aura.database import init_db, upsert_dataset
from aura.harvesters.static import StaticHarvester
from aura.models import Dataset
from aura.pipeline import harvest_sources


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class _FakeHarvester:
    """Minimaalinen harvesteri, joka lisää sovitun määrän datasettejä."""

    name = "fake"
    description = "Testiharvesteri"
    url = "https://example.invalid"

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self.conn = conn

    async def harvest(self) -> int:
        assert self.conn is not None
        for index in range(self._count):
            upsert_dataset(
                self.conn,
                Dataset(
                    id=f"{self.name}-{index}",
                    name=f"{self.name}-{index}",
                    title=f"Aineisto {index}",
                    organization_id="org",
                    organization_name="org",
                    organization_title="Org",
                    source=self.name,
                ),
            )
        self.conn.commit()
        return self._count

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        return {"name": cls.name, "description": cls.description, "url": cls.url}


def _make(name: str, count: int, static: bool = False) -> type:
    base = (StaticHarvester,) if static else ()
    namespace = {"name": name, "_count": count}
    if static:
        # StaticHarvester vaatii datasets_config-attribuutin
        namespace["datasets_config"] = []
    return type(
        f"Fake{name.title()}",
        (_FakeHarvester, *base),
        namespace,
    )


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, type]:
    sources: dict[str, type] = {}
    monkeypatch.setattr("aura.pipeline.get_all_harvesters", lambda: sources)
    monkeypatch.setattr("aura.pipeline.get_harvester", lambda name: sources[name])
    return sources


class TestHarvestSources:
    async def test_aggregates_counts(
        self, registry: dict[str, type]
    ) -> None:
        registry["a"] = _make("a", 3)
        registry["b"] = _make("b", 2)

        outcome = await harvest_sources(_db())
        assert outcome.total == 5
        assert outcome.counts == {"a": 3, "b": 2}

    async def test_static_skipped_by_default(
        self, registry: dict[str, type]
    ) -> None:
        registry["dyn"] = _make("dyn", 1)
        registry["stat"] = _make("stat", 1, static=True)

        outcome = await harvest_sources(_db())
        assert outcome.skipped == ["stat"]
        assert outcome.total == 1

    async def test_static_included_on_request(
        self, registry: dict[str, type]
    ) -> None:
        registry["stat"] = _make("stat", 1, static=True)

        outcome = await harvest_sources(_db(), include_static=True)
        assert outcome.skipped == []
        assert outcome.total == 1

    async def test_single_source(self, registry: dict[str, type]) -> None:
        registry["a"] = _make("a", 3)
        registry["b"] = _make("b", 2)

        outcome = await harvest_sources(_db(), source="a")
        assert outcome.counts == {"a": 3}
        assert outcome.total == 3

    async def test_updates_sources_table(
        self, registry: dict[str, type]
    ) -> None:
        registry["a"] = _make("a", 4)
        conn = _db()

        await harvest_sources(conn)
        row = conn.execute(
            "SELECT dataset_count, last_harvested_at FROM sources WHERE name = 'a'"
        ).fetchone()
        assert row["dataset_count"] == 4
        assert row["last_harvested_at"]

    async def test_warns_on_silent_zero(
        self, registry: dict[str, type]
    ) -> None:
        """Hiljainen nolla on se vika joka puri Valtiokonttoriin."""
        conn = _db()
        registry["a"] = _make("a", 5)
        await harvest_sources(conn)

        registry["a"] = _make("a", 0)
        outcome = await harvest_sources(conn)
        assert outcome.warnings
        assert "0 datasettiä" in outcome.warnings[0]

    async def test_no_warning_on_stable_count(
        self, registry: dict[str, type]
    ) -> None:
        conn = _db()
        registry["a"] = _make("a", 5)
        await harvest_sources(conn)
        outcome = await harvest_sources(conn)
        assert outcome.warnings == []

    async def test_progress_callback(self, registry: dict[str, type]) -> None:
        registry["a"] = _make("a", 1)
        seen: list[tuple[str, int | None]] = []

        await harvest_sources(_db(), on_progress=lambda n, c: seen.append((n, c)))
        assert ("a", None) in seen
        assert ("a", 1) in seen

    async def test_shared_connection_is_used(
        self, registry: dict[str, type]
    ) -> None:
        """Harvesterit kirjoittavat annettuun yhteyteen, eivät omaansa."""
        registry["a"] = _make("a", 2)
        conn = _db()

        await harvest_sources(conn)
        assert conn.execute("SELECT count(*) FROM datasets").fetchone()[0] == 2
