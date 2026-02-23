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
        assert len(vocabs) >= 9
        domains = {v["domain"] for v in vocabs}
        assert "agriculture" in domains
        assert "environment" in domains
        assert "transport" in domains
        assert "geospatial" in domains
        assert "health_social" in domains
        assert "education" in domains
        assert "municipal_finance" in domains
        assert "urban_planning" in domains
        assert "demographics" in domains

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

    # --- Uudet domain-sanastot ---

    def test_expands_sote(self) -> None:
        terms = expand_with_vocabularies("sote")
        lower = [t.lower() for t in terms]
        assert "terveydenhuolto" in lower
        assert "sosiaalipalvelut" in lower

    def test_expands_koulu(self) -> None:
        terms = expand_with_vocabularies("koulu")
        lower = [t.lower() for t in terms]
        assert "peruskoulu" in lower or "perusopetus" in lower

    def test_expands_budjetti(self) -> None:
        terms = expand_with_vocabularies("budjetti")
        lower = [t.lower() for t in terms]
        assert "talousarvio" in lower
        assert "kuntatalous" in lower

    def test_expands_kaavoitus(self) -> None:
        terms = expand_with_vocabularies("kaavoitus")
        lower = [t.lower() for t in terms]
        assert "asemakaava" in lower
        assert "yleiskaava" in lower

    def test_expands_vaesto(self) -> None:
        terms = expand_with_vocabularies("väestö")
        lower = [t.lower() for t in terms]
        assert "väestöennuste" in lower
        assert "ikärakenne" in lower

    def test_expands_vaestoennuste(self) -> None:
        terms = expand_with_vocabularies("väestöennuste")
        lower = [t.lower() for t in terms]
        assert "muuttoliike" in lower or "väestökehitys" in lower

    def test_expands_varhaiskasvatus(self) -> None:
        terms = expand_with_vocabularies("varhaiskasvatus")
        lower = [t.lower() for t in terms]
        assert "päivähoito" in lower or "päiväkoti" in lower

    def test_expands_hyvinvointialue(self) -> None:
        terms = expand_with_vocabularies("hyvinvointialue")
        lower = [t.lower() for t in terms]
        assert "sosiaali- ja terveyspalvelut" in lower or "sote-uudistus" in lower


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

    @pytest.mark.asyncio
    async def test_multi_word_query_splits_to_or(self) -> None:
        """Monisanainen haku pilkotaan OR-tokeneiksi."""
        from aura.server import _expand_query

        with patch("aura.server._get_yso", return_value=None):
            result = await _expand_query("väestöennuste ikärakenne kunta", ctx=None)

        # Jokainen sana on mukana OR-lausekkeessa
        assert "väestöennuste" in result
        assert "ikärakenne" in result
        assert "kunta" in result
        assert "OR" in result

    @pytest.mark.asyncio
    async def test_multi_word_expands_each_token(self) -> None:
        """Monisanaisessa haussa jokainen sana laajennetaan sanastolla."""
        from aura.server import _expand_query

        with patch("aura.server._get_yso", return_value=None):
            result = await _expand_query("budjetti väestö", ctx=None)

        # "budjetti" laajennetaan → talousarvio jne.
        assert "talousarvio" in result
        # "väestö" laajennetaan → väestöennuste jne.
        assert "väestöennuste" in result
        assert "OR" in result

    @pytest.mark.asyncio
    async def test_multi_word_unknown_terms_still_or(self) -> None:
        """Tuntemattomat monisanaiset haut silti OR-yhdistettyjä."""
        from aura.server import _expand_query

        with patch("aura.server._get_yso", return_value=None):
            result = await _expand_query("xyz abc", ctx=None)

        assert "xyz" in result
        assert "abc" in result
        assert "OR" in result

    @pytest.mark.asyncio
    async def test_multi_word_yso_per_token(self) -> None:
        """YSO-laajennus kutsutaan jokaiselle tokenille erikseen."""
        from aura.server import _expand_query

        mock_yso = AsyncMock()

        async def mock_expand(query: str, lang: str = "fi") -> list[str]:
            if query == "väestö":
                return ["väestö", "väestötiede"]
            if query == "liikenne":
                return ["liikenne", "kuljetusala"]
            return [query]

        mock_yso.expand_query = mock_expand

        with patch("aura.server._get_yso", return_value=mock_yso):
            result = await _expand_query("väestö liikenne", ctx=None)

        assert "väestötiede" in result
        assert "kuljetusala" in result

    @pytest.mark.asyncio
    async def test_multi_word_max_three_yso_tokens(self) -> None:
        """YSO-laajennus rajoitetaan max 3 tokeniin."""
        from aura.server import _expand_query

        call_count = 0
        mock_yso = AsyncMock()

        async def mock_expand(query: str, lang: str = "fi") -> list[str]:
            nonlocal call_count
            call_count += 1
            return [query]

        mock_yso.expand_query = mock_expand

        with patch("aura.server._get_yso", return_value=mock_yso):
            await _expand_query("a b c d e", ctx=None)

        assert call_count == 3
