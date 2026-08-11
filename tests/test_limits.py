"""Testit työkaluparametrien katoille.

MCP-endpoint on julkinen ja autentikoimaton, joten jokaisella määrää
kasvattavalla parametrilla on oltava katto. Näissä testeissä on kaksi
tarkoitusta:

1. Katto toimii — liian suuri arvo leikkautuu.
2. **Kuvaus ja toteutus eivät eriydy.** Katon numero on kirjattu työkalun
   docstringiin, jotta kutsuva agentti tietää sen ennen kutsua. Jos numeroa
   muutetaan koodissa mutta ei kuvauksessa, agentti saa väärän tiedon eikä
   mikään huomauttaisi siitä ilman tätä testiä.
"""

from __future__ import annotations

import pytest

from aura.limits import (
    MAX_COMPARE_DATASETS,
    MAX_LIST_LIMIT,
    MAX_SEARCH_LIMIT,
    clamp,
)


class TestClamp:
    def test_leikkaa_liian_suuren(self) -> None:
        assert clamp(1_000_000, MAX_SEARCH_LIMIT) == MAX_SEARCH_LIMIT

    def test_sallii_katon_alapuolella(self) -> None:
        assert clamp(10, MAX_SEARCH_LIMIT) == 10

    def test_sallii_katon_tasan(self) -> None:
        assert clamp(MAX_SEARCH_LIMIT, MAX_SEARCH_LIMIT) == MAX_SEARCH_LIMIT

    @pytest.mark.parametrize("value", [0, -1, -1000])
    def test_nollaa_ja_negatiiviset_nostetaan_minimiin(self, value: int) -> None:
        """SQLite tulkitsee negatiivisen LIMITin rajattomaksi.

        Ilman alarajaa ``limit=-1`` olisi ohittanut koko katon.
        """
        assert clamp(value, MAX_SEARCH_LIMIT) == 1


class TestKuvausVastaaToteutusta:
    """Katon numeron on löydyttävä siitä kuvauksesta jonka agentti saa.

    Kuvaus luetaan MCP:n työkalulistalta eikä funktion docstringistä:
    se on se teksti joka asiakkaalle lähtee, ja `@mcp.tool()` voi muokata
    sitä matkalla.
    """

    @staticmethod
    def _descriptions() -> dict[str, str]:
        import asyncio

        import aura.server  # noqa: F401 — rikkoo kiertoimportin oikeassa järjestyksessä
        from aura.server import mcp

        tools = asyncio.run(mcp.list_tools())
        return {t.name: (t.description or "") for t in tools}

    @pytest.mark.parametrize(
        ("tool", "cap"),
        [
            ("search", MAX_SEARCH_LIMIT),
            ("search_structured", MAX_SEARCH_LIMIT),
            ("health_check", MAX_LIST_LIMIT),
            ("compare", MAX_COMPARE_DATASETS),
        ],
    )
    def test_kuvaus_kertoo_katon(self, tool: str, cap: int) -> None:
        descriptions = self._descriptions()
        assert tool in descriptions, f"työkalua {tool} ei ole rekisteröity"
        assert str(cap) in descriptions[tool], (
            f"{tool}: katto {cap} puuttuu kuvauksesta — agentti ei tiedä rajaa"
        )


class TestKatotOvatJarkevat:
    def test_hakukatto_pienempi_kuin_listakatto(self) -> None:
        """Hakutulos on raskaampi rivi kuin listausrivi."""
        assert MAX_SEARCH_LIMIT < MAX_LIST_LIMIT

    def test_katot_ovat_positiivisia(self) -> None:
        for value in (MAX_SEARCH_LIMIT, MAX_LIST_LIMIT, MAX_COMPARE_DATASETS):
            assert value > 0


class TestLemmatisoijanEsilataus:
    """Muistiprofiilin on oltava rehellinen heti käynnistyksestä.

    simplemma lataa mallinsa laiskasti, ja lataus maksaa satoja megatavuja.
    Ilman esilatausta tuore kontti näyttää pieneltä ja todellinen työjoukko
    paljastuu vasta ensimmäisellä käyttäjän haulla.
    """

    def test_warm_lemmatizer_on_kutsuttavissa(self) -> None:
        from aura.server import warm_lemmatizer

        warm_lemmatizer()

    def test_lifespan_lampimittaa_mallin(self) -> None:
        """Vartija: jos kutsu poistetaan lifespanista, muistipiikki palaa."""
        import inspect

        from aura.server import _lifespan

        assert "warm_lemmatizer()" in inspect.getsource(_lifespan)
