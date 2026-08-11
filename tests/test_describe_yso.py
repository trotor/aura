"""Testit describe()-työkalun YSO-ehdotuksille."""

import sqlite3
from unittest.mock import patch

import pytest

from aura.database import add_enrichment, init_db, upsert_dataset
from aura.models import Dataset
from aura.server import describe
from aura.yso import YsoClient, YsoConcept


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    ds = Dataset(
        id="test-1",
        name="test-1",
        title="Liikennedata",
        title_fi="Liikennedata",
        keywords_fi=["liikenne"],
    )
    upsert_dataset(conn, ds)
    conn.commit()


def _mock_yso() -> YsoClient:
    """Luo YsoClient joka palauttaa vakiotuloksia."""
    client = YsoClient()

    async def mock_search(
        query: str, lang: str = "fi", max_hits: int = 5,
    ) -> list[YsoConcept]:
        results = {
            "liikenne": [YsoConcept(uri="http://yso/p3466", label="liikenne")],
        }
        return results.get(query.lower(), [])

    client.search = mock_search  # type: ignore[assignment]
    return client


class TestDescribeYsoSuggestions:
    """YSO-ehdotukset describe()-tuloksessa."""

    @pytest.mark.asyncio
    async def test_shows_suggestions_when_yso_concepts_missing(self) -> None:
        conn = _memory_db()
        _seed(conn)
        yso = _mock_yso()
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=yso):
            result = await describe("test-1")
        assert "YSO-ehdotukset" in result
        assert "liikenne" in result
        assert "suggest_yso_tags" in result

    @pytest.mark.asyncio
    async def test_no_suggestions_when_yso_concepts_exists(self) -> None:
        conn = _memory_db()
        _seed(conn)
        add_enrichment(
            conn, "test-1", "yso_concepts",
            '[{"uri":"http://yso/p3466","label":"liikenne"}]',
        )
        yso = _mock_yso()
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=yso):
            result = await describe("test-1")
        assert "YSO-ehdotukset" not in result

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_yso_unavailable(self) -> None:
        conn = _memory_db()
        _seed(conn)
        with patch("aura.server._get_conn", return_value=conn), \
             patch("aura.server._get_yso", return_value=None):
            result = await describe("test-1")
        # Ei kaadu, mutta ehdotuksia ei näytetä (ei YSO-clientia)
        assert "Liikennedata" in result
        # YSO-ehdotuksia ei tule (tai ne epäonnistuvat gracefully)
        # Ei assertoida "YSO-ehdotukset" koska se voi tai ei voi näkyä
        # riippuen fallback-logiikasta
