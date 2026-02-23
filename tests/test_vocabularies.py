"""Testit domain-sanastoille ja hakutermien laajennukselle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aura.vocabularies import expand_with_vocabularies, load_all, reset_cache


class TestLoadAll:
    """load_all() lataa sanastot JSON-tiedostoista."""

    def setup_method(self) -> None:
        reset_cache()

    def test_loads_vocabularies(self) -> None:
        vocabs = load_all()
        assert len(vocabs) >= 4
        domains = {v["domain"] for v in vocabs}
        assert "agriculture" in domains
        assert "environment" in domains
        assert "transport" in domains
        assert "geospatial" in domains

    def test_caches_result(self) -> None:
        v1 = load_all()
        v2 = load_all()
        assert v1 is v2


class TestExpandWithVocabularies:
    """expand_with_vocabularies() laajentaa hakutermejä."""

    def setup_method(self) -> None:
        reset_cache()

    def test_expands_known_term(self) -> None:
        terms = expand_with_vocabularies("ilmanlaatu")
        assert len(terms) > 0
        # Tarkista joitain tunnettuja laajennuksia
        lower_terms = [t.lower() for t in terms]
        assert "hiukkaset" in lower_terms or "pienhiukkaset" in lower_terms

    def test_expands_transport(self) -> None:
        terms = expand_with_vocabularies("liikenne")
        assert len(terms) > 0
        lower_terms = [t.lower() for t in terms]
        assert "tieliikenne" in lower_terms

    def test_unknown_term_returns_empty(self) -> None:
        terms = expand_with_vocabularies("xyznonexistent")
        assert terms == []

    def test_case_insensitive(self) -> None:
        terms_lower = expand_with_vocabularies("ilmanlaatu")
        terms_upper = expand_with_vocabularies("ILMANLAATU")
        terms_mixed = expand_with_vocabularies("Ilmanlaatu")
        assert len(terms_lower) > 0
        assert set(t.lower() for t in terms_lower) == set(t.lower() for t in terms_upper)
        assert set(t.lower() for t in terms_lower) == set(t.lower() for t in terms_mixed)

    def test_no_duplicates(self) -> None:
        terms = expand_with_vocabularies("liikenne")
        lower = [t.lower() for t in terms]
        assert len(lower) == len(set(lower))

    def test_does_not_include_original_query(self) -> None:
        terms = expand_with_vocabularies("liikenne")
        assert "liikenne" not in [t.lower() for t in terms]

    def test_multi_word_query_matches_single_word(self) -> None:
        """Monen sanan haussa yksittäinen sana matchaa."""
        terms = expand_with_vocabularies("helsingin liikenne")
        assert len(terms) > 0  # "liikenne" matchaa


class TestExpandQuery:
    """_expand_query() yhdistää sanastot ja YSO:n."""

    @pytest.mark.asyncio
    async def test_combines_vocab_and_yso(self) -> None:
        from aura.server import _expand_query

        # Mock YSO palauttamaan omia termejä
        mock_yso = AsyncMock()
        mock_yso.expand_query.return_value = ["ilmanlaatu", "ilmansaastuminen"]

        with patch("aura.server._get_yso", return_value=mock_yso):
            result = await _expand_query("ilmanlaatu", ctx=None)

        # Tulos sisältää sekä sanastolaajennukset että YSO-termit
        assert "ilmanlaatu" in result
        assert "ilmansaastuminen" in result
        # Sanastoista tulevia termejä
        assert "hiukkaset" in result or "pienhiukkaset" in result

    @pytest.mark.asyncio
    async def test_works_without_yso(self) -> None:
        from aura.server import _expand_query

        with patch("aura.server._get_yso", return_value=None):
            result = await _expand_query("liikenne", ctx=None)

        # Sanastolaajennukset toimivat ilman YSO:ta
        assert "tieliikenne" in result

    @pytest.mark.asyncio
    async def test_deduplicates(self) -> None:
        from aura.server import _expand_query

        # Mock YSO palauttamaan saman termin kuin sanasto
        mock_yso = AsyncMock()
        mock_yso.expand_query.return_value = ["liikenne", "tieliikenne"]

        with patch("aura.server._get_yso", return_value=mock_yso):
            result = await _expand_query("liikenne", ctx=None)

        # "tieliikenne" esiintyy vain kerran
        assert result.count("tieliikenne") == 1

    @pytest.mark.asyncio
    async def test_unknown_term_with_no_yso(self) -> None:
        from aura.server import _expand_query

        with patch("aura.server._get_yso", return_value=None):
            result = await _expand_query("xyzabc", ctx=None)

        # Ei laajennuksia → tyhjä merkkijono
        assert result == ""
