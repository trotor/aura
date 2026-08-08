"""Testit eduskunnan avoimen datan harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.eduskunta import MAX_ROWS, EduskuntaHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester(conn: sqlite3.Connection) -> EduskuntaHarvester:
    """Harvesteri ilman pyyntöviivettä — testit eivät mene verkkoon."""
    h = EduskuntaHarvester(conn=conn)
    h.request_delay = 0.0
    return h


def _mock_client(sizes: dict[str, int]) -> AsyncMock:
    """Mock joka simuloi sivutettua API:a annetuilla taulukoilla.

    sizes: {taulun nimi: rivimäärä}
    """
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()

        table = url.split("/tables/")[1].split("/")[0]
        # Kunnioita pyydettyä sivukokoa: mittaus käyttää pientä koetinta,
        # ja mockin pitää käyttäytyä kuten oikea API.
        per_page = int(url.split("perPage=")[1].split("&")[0])
        page = int(url.split("page=")[1].split("&")[0])
        total = sizes.get(table, 0)

        start = page * per_page
        n = max(0, min(per_page, total - start))
        resp.json.return_value = {
            "columnNames": ["a", "b"],
            "rowData": [["x", "y"] for _ in range(n)],
            "hasMore": start + n < total,
        }
        return resp

    client.get = AsyncMock(side_effect=mock_get)
    return client


def _patched(h: EduskuntaHarvester, client: AsyncMock) -> object:
    """Korvaa _make_client mockatulla asynkronisella kontekstilla."""
    patcher = patch.object(h, "_make_client")
    mock_make = patcher.start()
    mock_make.return_value.__aenter__ = AsyncMock(return_value=client)
    mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher


class TestMeasureRows:
    """Bisektointi löytää todellisen rivimäärän."""

    @pytest.mark.parametrize("total", [0, 1, 99, 100, 101, 2677, 43512, 347655])
    async def test_measures_exact_size(self, total: int) -> None:
        h = _harvester(_memory_db())
        client = _mock_client({"T": total})
        assert await h._measure_rows(client, "T") == total

    async def test_does_not_call_counts_endpoint(self) -> None:
        """/counts valehtelee — sitä ei saa käyttää."""
        h = _harvester(_memory_db())
        client = _mock_client({"T": 5000})
        await h._measure_rows(client, "T")
        called = [c.args[0] for c in client.get.call_args_list]
        assert not any("counts" in u for u in called)

    async def test_bisection_is_logarithmic(self) -> None:
        """Bisektointi ei saa selata sivuja yksitellen."""
        h = _harvester(_memory_db())
        client = _mock_client({"T": 347655})
        await h._measure_rows(client, "T")
        assert client.get.call_count < 40

    async def test_probe_uses_smallest_possible_page(self) -> None:
        """Mittaus ei saa ladata sivullista dataa pelkkään laskemiseen.

        VaskiDatan rivit ovat kokonaisia XML-asiakirjoja. Mitattuna
        2026-08-08 perPage=100 painoi 3,4 MB ja kesti 5,6 s, perPage=1
        painoi 0,019 MB ja kesti 0,1 s — samaan kysymykseen "onko rivejä".
        Täysillä sivuilla koko ajo kesti yli puoli tuntia.
        """
        h = _harvester(_memory_db())
        client = _mock_client({"T": 347655})
        await h._measure_rows(client, "T")
        called = [c.args[0] for c in client.get.call_args_list]
        assert called, "mittaus ei tehnyt yhtään pyyntöä"
        assert all("perPage=1&" in u for u in called), called[:3]


class TestCeiling:
    """Kattoon osunut mittaus on alaraja, ei mittaus — sen on näyttävä."""

    async def test_capped_measurement_is_marked_as_lower_bound(self) -> None:
        conn = _memory_db()
        h = _harvester(conn)
        # Taulu joka on suurempi kuin bisektoinnin katto.
        client = _mock_client({"MemberOfParliament": MAX_ROWS * 2})

        patcher = _patched(h, client)
        try:
            await h.harvest()
        finally:
            patcher.stop()  # type: ignore[attr-defined]

        row = conn.execute(
            "SELECT notes_fi FROM datasets WHERE id = 'eduskunta-kansanedustajat'"
        ).fetchone()
        assert "yli" in row["notes_fi"], row["notes_fi"]

    async def test_normal_measurement_is_not_marked(self) -> None:
        conn = _memory_db()
        h = _harvester(conn)
        client = _mock_client({"MemberOfParliament": 2677})

        patcher = _patched(h, client)
        try:
            await h.harvest()
        finally:
            patcher.stop()  # type: ignore[attr-defined]

        row = conn.execute(
            "SELECT notes_fi FROM datasets WHERE id = 'eduskunta-kansanedustajat'"
        ).fetchone()
        assert "yli" not in row["notes_fi"]


class TestDatasets:
    def test_seven_datasets(self) -> None:
        assert len(EduskuntaHarvester.DATASETS) == 7

    def test_excludes_empty_tables(self) -> None:
        """HetekaData ja SaliDBMessageLog ovat tyhjiä, PrimaryKeys teknistä."""
        tables = {t for d in EduskuntaHarvester.DATASETS for t in d["tables"]}
        assert "HetekaData" not in tables
        assert "SaliDBMessageLog" not in tables
        assert "PrimaryKeys" not in tables

    def test_covers_sixteen_tables(self) -> None:
        tables = {t for d in EduskuntaHarvester.DATASETS for t in d["tables"]}
        assert len(tables) == 16

    def test_includes_tables_counts_endpoint_calls_empty(self) -> None:
        """/counts väitti näitä tyhjiksi mutta niissä on rivejä."""
        tables = {t for d in EduskuntaHarvester.DATASETS for t in d["tables"]}
        assert "SeatingOfParliament" in tables
        assert "SaliDBAanestysKieli" in tables


class TestHarvest:
    async def test_harvest_creates_seven_datasets(self) -> None:
        conn = _memory_db()
        h = _harvester(conn)
        client = _mock_client({"MemberOfParliament": 2677, "VaskiData": 347655})

        patcher = _patched(h, client)
        try:
            count = await h.harvest()
        finally:
            patcher.stop()  # type: ignore[attr-defined]

        assert count == 7
        row = conn.execute(
            "SELECT COUNT(*) c FROM datasets WHERE source = 'eduskunta'"
        ).fetchone()
        assert row["c"] == 7

    async def test_measured_size_appears_in_notes(self) -> None:
        conn = _memory_db()
        h = _harvester(conn)
        client = _mock_client({"MemberOfParliament": 2677})

        patcher = _patched(h, client)
        try:
            await h.harvest()
        finally:
            patcher.stop()  # type: ignore[attr-defined]

        row = conn.execute(
            "SELECT notes_fi FROM datasets WHERE id = 'eduskunta-kansanedustajat'"
        ).fetchone()
        assert "2 677" in row["notes_fi"] or "2677" in row["notes_fi"]

    async def test_resource_urls_point_at_tables(self) -> None:
        conn = _memory_db()
        h = _harvester(conn)
        client = _mock_client({})

        patcher = _patched(h, client)
        try:
            await h.harvest()
        finally:
            patcher.stop()  # type: ignore[attr-defined]

        urls = [
            r["url"]
            for r in conn.execute(
                "SELECT url FROM resources WHERE dataset_id = 'eduskunta-asiakirjat'"
            )
        ]
        assert "https://avoindata.eduskunta.fi/api/v1/tables/VaskiData/rows" in urls
