"""Finto YSO -integraatio (Yleinen suomalainen ontologia).

Hakee YSO-käsitteitä ja laajentaa hakutermejä ontologiasuhteilla.
API: https://api.finto.fi/rest/v1/
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.finto.fi/rest/v1"
VOCAB = "yso"
# Välimuistin TTL sekunteina (24 h)
CACHE_TTL = 86400
# Enintään N narrower-termiä per käsite hakulaajennuksessa
MAX_NARROWER = 15


@dataclass
class YsoConcept:
    """YSO-käsite."""

    uri: str
    label: str
    lang: str = "fi"


@dataclass
class _CacheEntry:
    terms: list[str]
    timestamp: float


class YsoClient:
    """Finto YSO REST API -asiakas välimuistilla."""

    def __init__(self, cache_ttl: int = CACHE_TTL) -> None:
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl = cache_ttl

    async def search(
        self,
        query: str,
        lang: str = "fi",
        max_hits: int = 5,
    ) -> list[YsoConcept]:
        """Hae YSO-käsitteitä hakutermillä."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/{VOCAB}/search",
                params={"query": f"{query}*", "lang": lang, "maxhits": max_hits},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        return [
            YsoConcept(
                uri=r["uri"],
                label=r.get("prefLabel", ""),
                lang=r.get("lang", lang),
            )
            for r in results
            if "uri" in r
        ]

    async def get_narrower(
        self,
        uri: str,
        lang: str = "fi",
    ) -> list[YsoConcept]:
        """Hae käsitteen suppeammat alakäsitteet."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/{VOCAB}/narrower",
                params={"uri": uri, "lang": lang},
            )
            resp.raise_for_status()
            data = resp.json()

        narrower = data.get("narrower", [])
        return [
            YsoConcept(
                uri=n["uri"],
                label=n.get("prefLabel", ""),
                lang=lang,
            )
            for n in narrower
            if "uri" in n and "prefLabel" in n
        ]

    async def expand_query(self, query: str, lang: str = "fi") -> list[str]:
        """Laajenna hakutermi YSO-käsitesuhteilla.

        Hakee tarkan YSO-osuman ja palauttaa alkuperäisen termin
        sekä sen alakäsitteiden nimet.

        Returns:
            Lista termeistä: [alkuperäinen, alakäsite1, alakäsite2, ...]
            Jos YSO-osumaa ei löydy, palauttaa [query].
        """
        # Tarkista välimuisti
        cache_key = f"{query}:{lang}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached.timestamp) < self._cache_ttl:
            return cached.terms

        terms = [query]
        try:
            concepts = await self.search(query, lang=lang, max_hits=1)
            if not concepts:
                return terms

            best = concepts[0]
            # Varmista tarkka osuma (prefLabel vastaa hakua)
            if best.label.lower() != query.lower():
                return terms

            narrower = await self.get_narrower(best.uri, lang=lang)
            for n in narrower[:MAX_NARROWER]:
                if n.label and n.label.lower() != query.lower():
                    terms.append(n.label)

        except (httpx.HTTPError, httpx.TimeoutException, KeyError):
            logger.debug("[yso] API-virhe laajennettaessa '%s'", query)
            return terms

        # Tallenna välimuistiin
        self._cache[cache_key] = _CacheEntry(terms=terms, timestamp=time.time())
        return terms


def build_fts5_query(terms: list[str]) -> str:
    """Rakenna FTS5-hakulauseke termilistasta.

    Yhdistää termit OR-operaattorilla ja käärii lainausmerkkeihin
    moniosaisia termejä.

    >>> build_fts5_query(["liikenne", "tieliikenne", "kevyt liikenne"])
    'liikenne OR tieliikenne OR "kevyt liikenne"'
    """
    if len(terms) <= 1:
        return terms[0] if terms else ""

    parts: list[str] = []
    for t in terms:
        if " " in t:
            parts.append(f'"{t}"')
        else:
            parts.append(t)
    return " OR ".join(parts)
