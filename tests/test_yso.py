"""Testit YSO-integraatiolle."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aura.yso import YsoClient, build_fts5_query


# --- build_fts5_query ---


class TestBuildFts5Query:
    """build_fts5_query()-funktion testit."""

    def test_single_term(self) -> None:
        assert build_fts5_query(["liikenne"]) == "liikenne"

    def test_multiple_terms(self) -> None:
        result = build_fts5_query(["liikenne", "tieliikenne", "vesiliikenne"])
        assert result == "liikenne OR tieliikenne OR vesiliikenne"

    def test_multi_word_term_quoted(self) -> None:
        result = build_fts5_query(["liikenne", "kevyt liikenne"])
        assert result == 'liikenne OR "kevyt liikenne"'

    def test_empty_list(self) -> None:
        assert build_fts5_query([]) == ""

    def test_single_multi_word(self) -> None:
        assert build_fts5_query(["kevyt liikenne"]) == '"kevyt liikenne"'

    def test_quotes_escaped(self) -> None:
        result = build_fts5_query(['termi "lainaus"'])
        assert result == '"termi ""lainaus"""'

    def test_fts5_operator_quoted(self) -> None:
        result = build_fts5_query(["NOT", "liikenne"])
        assert result == '"NOT" OR liikenne'

    def test_operator_case_insensitive(self) -> None:
        result = build_fts5_query(["and", "or"])
        assert result == '"and" OR "or"'


# --- YsoClient.search ---


def _mock_search_response(results: list[dict]) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"results": results}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_narrower_response(narrower: list[dict]) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"narrower": narrower}
    resp.raise_for_status = MagicMock()
    return resp


SEARCH_LIIKENNE = [
    {
        "uri": "http://www.yso.fi/onto/yso/p3466",
        "prefLabel": "liikenne",
        "lang": "fi",
        "vocab": "yso",
    },
]

NARROWER_LIIKENNE = [
    {"uri": "http://www.yso.fi/onto/yso/p6120", "prefLabel": "tieliikenne"},
    {"uri": "http://www.yso.fi/onto/yso/p6121", "prefLabel": "raideliikenne"},
    {"uri": "http://www.yso.fi/onto/yso/p6122", "prefLabel": "vesiliikenne"},
    {"uri": "http://www.yso.fi/onto/yso/p6123", "prefLabel": "lentoliikenne"},
]


class TestYsoSearch:
    """YsoClient.search()-testit."""

    @pytest.mark.asyncio
    async def test_search_returns_concepts(self) -> None:
        client = YsoClient()
        mock_resp = _mock_search_response(SEARCH_LIIKENNE)

        with patch("aura.yso.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            results = await client.search("liikenne")

        assert len(results) == 1
        assert results[0].uri == "http://www.yso.fi/onto/yso/p3466"
        assert results[0].label == "liikenne"

    @pytest.mark.asyncio
    async def test_search_empty_results(self) -> None:
        client = YsoClient()
        mock_resp = _mock_search_response([])

        with patch("aura.yso.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            results = await client.search("xyznonexistent")

        assert results == []


# --- YsoClient.get_narrower ---


class TestYsoNarrower:
    """YsoClient.get_narrower()-testit."""

    @pytest.mark.asyncio
    async def test_returns_narrower_concepts(self) -> None:
        client = YsoClient()
        mock_resp = _mock_narrower_response(NARROWER_LIIKENNE)

        with patch("aura.yso.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            results = await client.get_narrower("http://www.yso.fi/onto/yso/p3466")

        assert len(results) == 4
        labels = [c.label for c in results]
        assert "tieliikenne" in labels
        assert "lentoliikenne" in labels


# --- YsoClient.expand_query ---


class TestExpandQuery:
    """YsoClient.expand_query()-testit."""

    @pytest.mark.asyncio
    async def test_expand_with_exact_match(self) -> None:
        client = YsoClient()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p3466", label="liikenne")]

        async def mock_narrower(uri: str, lang: str = "fi"):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [
                YsoConcept(uri="http://yso/p6120", label="tieliikenne"),
                YsoConcept(uri="http://yso/p6121", label="raideliikenne"),
            ]

        client.search = mock_search  # type: ignore[assignment]
        client.get_narrower = mock_narrower  # type: ignore[assignment]

        terms = await client.expand_query("liikenne")
        assert "liikenne" in terms
        assert "tieliikenne" in terms
        assert "raideliikenne" in terms
        assert len(terms) == 3

    @pytest.mark.asyncio
    async def test_no_match_returns_original(self) -> None:
        client = YsoClient()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            return []

        client.search = mock_search  # type: ignore[assignment]

        terms = await client.expand_query("xyznonexistent")
        assert terms == ["xyznonexistent"]

    @pytest.mark.asyncio
    async def test_inexact_match_returns_original(self) -> None:
        """Jos YSO-osuma ei vastaa täsmälleen hakutermiä, ei laajenneta."""
        client = YsoClient()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p999", label="liikenneväline")]

        client.search = mock_search  # type: ignore[assignment]

        terms = await client.expand_query("liikenne")
        assert terms == ["liikenne"]

    @pytest.mark.asyncio
    async def test_api_error_returns_original(self) -> None:
        client = YsoClient()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            raise httpx.TimeoutException("timeout")

        client.search = mock_search  # type: ignore[assignment]

        terms = await client.expand_query("liikenne")
        assert terms == ["liikenne"]

    @pytest.mark.asyncio
    async def test_cache_works(self) -> None:
        client = YsoClient()
        call_count = 0

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            nonlocal call_count
            call_count += 1
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p1", label="väestö")]

        async def mock_narrower(uri: str, lang: str = "fi"):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p2", label="väestönkasvu")]

        client.search = mock_search  # type: ignore[assignment]
        client.get_narrower = mock_narrower  # type: ignore[assignment]

        terms1 = await client.expand_query("väestö")
        terms2 = await client.expand_query("väestö")
        assert terms1 == terms2
        assert call_count == 1  # Toinen kutsu tuli välimuistista

    @pytest.mark.asyncio
    async def test_max_narrower_limit(self) -> None:
        """Enintään MAX_NARROWER alakäsitettä."""
        client = YsoClient()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p1", label="testi")]

        async def mock_narrower(uri: str, lang: str = "fi"):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [
                YsoConcept(uri=f"http://yso/n{i}", label=f"alakäsite{i}")
                for i in range(50)
            ]

        client.search = mock_search  # type: ignore[assignment]
        client.get_narrower = mock_narrower  # type: ignore[assignment]

        terms = await client.expand_query("testi")
        # 1 (alkuperäinen) + MAX_NARROWER
        assert len(terms) <= 16  # 1 + 15

    @pytest.mark.asyncio
    async def test_duplicate_label_excluded(self) -> None:
        """Alkuperäinen termi ei toistu narrower-listassa."""
        client = YsoClient()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p1", label="liikenne")]

        async def mock_narrower(uri: str, lang: str = "fi"):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [
                YsoConcept(uri="http://yso/p1", label="liikenne"),  # Sama kuin haku
                YsoConcept(uri="http://yso/p2", label="tieliikenne"),
            ]

        client.search = mock_search  # type: ignore[assignment]
        client.get_narrower = mock_narrower  # type: ignore[assignment]

        terms = await client.expand_query("liikenne")
        assert terms.count("liikenne") == 1
        assert "tieliikenne" in terms

    @pytest.mark.asyncio
    async def test_concurrent_expand_no_duplicate_api_calls(self) -> None:
        """Kaksi samanaikaista kutsua samalla avaimella → API kutsutaan vain kerran."""
        client = YsoClient()
        search_count = 0
        search_event = asyncio.Event()

        async def mock_search(query: str, lang: str = "fi", max_hits: int = 5):  # noqa: ANN001, ARG001
            nonlocal search_count
            search_count += 1
            # Simuloi verkkoviive jotta toinen kutsu ehtii jonoon
            await asyncio.sleep(0.05)
            search_event.set()
            from aura.yso import YsoConcept
            return [YsoConcept(uri="http://yso/p3466", label="liikenne")]

        async def mock_narrower(uri: str, lang: str = "fi"):  # noqa: ANN001, ARG001
            from aura.yso import YsoConcept
            return [
                YsoConcept(uri="http://yso/p6120", label="tieliikenne"),
            ]

        client.search = mock_search  # type: ignore[assignment]
        client.get_narrower = mock_narrower  # type: ignore[assignment]

        results = await asyncio.gather(
            client.expand_query("liikenne"),
            client.expand_query("liikenne"),
        )

        assert search_count == 1
        assert results[0] == results[1]
        assert "tieliikenne" in results[0]
