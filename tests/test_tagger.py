"""Testit YSO-taggerille."""

from __future__ import annotations

import json

import pytest

from aura.tagger import (
    TagSuggestion,
    _tokenize,
    format_suggestions,
    suggest_tags,
)
from aura.yso import YsoClient, YsoConcept

# --- _tokenize ---


class TestTokenize:
    """_tokenize()-apufunktion testit."""

    def test_basic(self) -> None:
        tokens = _tokenize("Helsingin väestötiedot")
        assert "helsingin" in tokens
        assert "väestötiedot" in tokens

    def test_removes_short_words(self) -> None:
        tokens = _tokenize("yli 100 km")
        assert "yli" not in tokens
        assert "100" not in tokens

    def test_removes_stop_words(self) -> None:
        tokens = _tokenize("Suomen avoin data aineisto")
        assert "suomen" not in tokens
        assert "avoin" not in tokens
        assert "aineisto" not in tokens

    def test_removes_numbers_and_special(self) -> None:
        tokens = _tokenize("Vuoden 2024 tilasto (CSV)")
        assert "2024" not in tokens
        assert "csv" not in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == []


# --- suggest_tags ---


def _make_yso_client(
    search_results: dict[str, list[YsoConcept]] | None = None,
) -> YsoClient:
    """Luo YsoClient mock-vastauksineen."""
    client = YsoClient()
    results = search_results or {}

    async def mock_search(
        query: str, lang: str = "fi", max_hits: int = 5,
    ) -> list[YsoConcept]:
        return results.get(query.lower(), [])

    client.search = mock_search  # type: ignore[assignment]
    return client


class TestSuggestTags:
    """suggest_tags()-testit."""

    @pytest.mark.asyncio
    async def test_keyword_match(self) -> None:
        yso = _make_yso_client({
            "liikenne": [YsoConcept(uri="http://yso/p3466", label="liikenne")],
        })
        dataset = {
            "keywords_fi": json.dumps(["liikenne"]),
            "title_fi": "Liikennedata",
        }
        tags = await suggest_tags(dataset, yso)
        assert any(t.uri == "http://yso/p3466" for t in tags)
        assert any(t.source == "keyword" for t in tags)

    @pytest.mark.asyncio
    async def test_title_match(self) -> None:
        yso = _make_yso_client({
            "kallioperä": [YsoConcept(uri="http://yso/p123", label="kallioperä")],
        })
        dataset = {"title_fi": "Kallioperäkartta", "keywords_fi": "[]"}
        tags = await suggest_tags(dataset, yso)
        # "kallioperäkartta" tokenisoidaan ja "kallioperä" ei ole suoraan siellä
        # mutta "kallioperäkartta" ei matchaa koska label != token
        assert len(tags) == 0  # ei tarkkaa osumaa

    @pytest.mark.asyncio
    async def test_title_exact_match(self) -> None:
        yso = _make_yso_client({
            "geologia": [YsoConcept(uri="http://yso/p456", label="geologia")],
        })
        dataset = {"title_fi": "Suomen geologia", "keywords_fi": "[]"}
        tags = await suggest_tags(dataset, yso)
        assert any(t.uri == "http://yso/p456" for t in tags)
        assert any(t.source == "title" for t in tags)

    @pytest.mark.asyncio
    async def test_description_match(self) -> None:
        yso = _make_yso_client({
            "hydrologia": [YsoConcept(uri="http://yso/p789", label="hydrologia")],
        })
        dataset = {
            "title_fi": "Vesistödata",
            "notes_fi": "Hydrologiaan liittyviä mittauksia",
            "keywords_fi": "[]",
        }
        tags = await suggest_tags(dataset, yso)
        # "hydrologia" tokenisoidaan "hydrologiaan" → ei tarkka osuma
        # Mutta "hydrologia" ei matchaa suoraan
        # Actually "hydrologiaan" != "hydrologia" niin tämä ei osu
        assert len(tags) == 0

    @pytest.mark.asyncio
    async def test_no_matches(self) -> None:
        yso = _make_yso_client({})
        dataset = {"title_fi": "Testidata", "keywords_fi": "[]"}
        tags = await suggest_tags(dataset, yso)
        assert tags == []

    @pytest.mark.asyncio
    async def test_inexact_keyword_not_matched(self) -> None:
        """Epätarkka YSO-osuma ei tule mukaan."""
        yso = _make_yso_client({
            "liikenne": [YsoConcept(uri="http://yso/p999", label="liikenneväline")],
        })
        dataset = {"keywords_fi": json.dumps(["liikenne"])}
        tags = await suggest_tags(dataset, yso)
        assert tags == []

    @pytest.mark.asyncio
    async def test_deduplication(self) -> None:
        """Sama URI ei toistu vaikka löytyy sekä keywordista että otsikosta."""
        yso = _make_yso_client({
            "liikenne": [YsoConcept(uri="http://yso/p3466", label="liikenne")],
        })
        dataset = {
            "keywords_fi": json.dumps(["liikenne"]),
            "title_fi": "Liikenne Suomessa",
        }
        tags = await suggest_tags(dataset, yso)
        uris = [t.uri for t in tags]
        assert uris.count("http://yso/p3466") == 1

    @pytest.mark.asyncio
    async def test_max_tags_limit(self) -> None:
        results = {
            f"word{i}": [YsoConcept(uri=f"http://yso/{i}", label=f"word{i}")]
            for i in range(20)
        }
        yso = _make_yso_client(results)
        keywords = [f"word{i}" for i in range(20)]
        dataset = {"keywords_fi": json.dumps(keywords)}
        tags = await suggest_tags(dataset, yso, max_tags=5)
        assert len(tags) <= 5

    @pytest.mark.asyncio
    async def test_keywords_as_list(self) -> None:
        """keywords_fi voi olla lista (ei JSON-merkkijono)."""
        yso = _make_yso_client({
            "väestö": [YsoConcept(uri="http://yso/p1", label="väestö")],
        })
        dataset = {"keywords_fi": ["väestö", "helsinki"]}
        tags = await suggest_tags(dataset, yso)
        assert any(t.label == "väestö" for t in tags)


# --- format_suggestions ---


class TestFormatSuggestions:
    """format_suggestions()-testit."""

    def test_empty(self) -> None:
        assert "Ei YSO" in format_suggestions([])

    def test_with_suggestions(self) -> None:
        suggestions = [
            TagSuggestion(uri="http://yso/p1", label="liikenne", source="keyword"),
            TagSuggestion(uri="http://yso/p2", label="geologia", source="title"),
        ]
        result = format_suggestions(suggestions)
        assert "liikenne" in result
        assert "geologia" in result
        assert "keyword" in result
        assert "title" in result
        assert "http://yso/p1" in result


# --- TagSuggestion ---


class TestTagSuggestion:
    """TagSuggestion-dataluokan testit."""

    def test_to_dict(self) -> None:
        s = TagSuggestion(uri="http://yso/p1", label="liikenne", source="keyword")
        d = s.to_dict()
        assert d == {"uri": "http://yso/p1", "label": "liikenne"}
        assert "source" not in d
