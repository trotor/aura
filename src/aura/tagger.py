"""YSO-pohjainen automaattitagitus dataseteille.

Analysoi datasetin avainsanat, otsikon ja kuvauksen ja ehdottaa
YSO-käsitteitä enrichmenteiksi.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from aura.constants import parse_json_list
from aura.yso import YsoClient

logger = logging.getLogger(__name__)

# Minimi sanan pituus YSO-hakuun
MIN_TOKEN_LENGTH = 4
# Stop-sanat joita ei haeta YSO:sta
STOP_WORDS = frozenset({
    "data", "aineisto", "tiedot", "tilasto", "tilastot", "rekisteri",
    "palvelu", "avoin", "suomen", "suomi", "finland", "finnish",
    "vuosi", "vuoden", "kaikki", "koko", "eri", "uusi",
    "tiedosto", "taulukko", "kartta", "luettelo",
    "sekä", "että", "joka", "joiden", "mukaan", "myös",
    "alle", "yli", "noin", "muut", "muita",
})


@dataclass
class TagSuggestion:
    """Ehdotettu YSO-tagi."""

    uri: str
    label: str
    source: str  # "keyword", "title", "description"

    def to_dict(self) -> dict[str, str]:
        return {"uri": self.uri, "label": self.label}


def _tokenize(text: str) -> list[str]:
    """Tokenisoi teksti sanoiksi YSO-hakua varten."""
    text = text.lower()
    # Poista numerot ja erikoismerkit
    text = re.sub(r"[^a-zäöåé\s-]", " ", text)
    tokens = []
    for word in text.split():
        word = word.strip("-")
        if len(word) >= MIN_TOKEN_LENGTH and word not in STOP_WORDS:
            tokens.append(word)
    return tokens


def _deduplicate(suggestions: list[TagSuggestion]) -> list[TagSuggestion]:
    """Poista duplikaatti-URI:t, säilytä ensimmäinen esiintymä."""
    seen: set[str] = set()
    result = []
    for s in suggestions:
        if s.uri not in seen:
            seen.add(s.uri)
            result.append(s)
    return result


async def suggest_tags(
    dataset: dict[str, Any],
    yso: YsoClient,
    max_tags: int = 10,
) -> list[TagSuggestion]:
    """Ehdota YSO-käsitteitä datasetille.

    Analysoi:
    1. Olemassaolevat keywords_fi → tarkka YSO-haku
    2. Otsikko → tokenisoi ja hae tarkkoja osumia
    3. Kuvaus → tokenisoi ja hae tarkkoja osumia

    Returns:
        Lista ehdotetuista tageista, deduplikoitu ja rajattu max_tags:iin.
    """
    suggestions: list[TagSuggestion] = []

    # 1. Avainsanat → YSO-haku
    keywords = parse_json_list(dataset.get("keywords_fi", "[]"))

    for kw in keywords:
        if not kw or len(kw) < MIN_TOKEN_LENGTH:
            continue
        concepts = await yso.search(kw.strip(), max_hits=1)
        if concepts and concepts[0].label.lower() == kw.strip().lower():
            suggestions.append(TagSuggestion(
                uri=concepts[0].uri,
                label=concepts[0].label,
                source="keyword",
            ))

    # 2. Otsikko → tokenisoi
    title = dataset.get("title_fi", "") or dataset.get("title", "") or ""
    for token in _tokenize(title):
        if any(s.label.lower() == token for s in suggestions):
            continue  # Jo löytynyt
        concepts = await yso.search(token, max_hits=1)
        if concepts and concepts[0].label.lower() == token:
            suggestions.append(TagSuggestion(
                uri=concepts[0].uri,
                label=concepts[0].label,
                source="title",
            ))

    # 3. Kuvaus → tokenisoi (vain top-termit)
    notes = dataset.get("notes_fi", "") or ""
    if notes and len(suggestions) < max_tags:
        desc_tokens = _tokenize(notes)
        # Ota enintään 10 uniikkia tokenia
        seen_tokens: set[str] = set()
        for token in desc_tokens:
            if token in seen_tokens:
                continue
            seen_tokens.add(token)
            if any(s.label.lower() == token for s in suggestions):
                continue
            concepts = await yso.search(token, max_hits=1)
            if concepts and concepts[0].label.lower() == token:
                suggestions.append(TagSuggestion(
                    uri=concepts[0].uri,
                    label=concepts[0].label,
                    source="description",
                ))
            if len(suggestions) >= max_tags:
                break

    return _deduplicate(suggestions)[:max_tags]


def format_suggestions(suggestions: list[TagSuggestion]) -> str:
    """Muotoile tagiehdotukset luettavaan muotoon."""
    if not suggestions:
        return "Ei YSO-käsite-ehdotuksia."

    lines = ["**YSO-käsite-ehdotukset:**\n"]
    for s in suggestions:
        lines.append(f"- **{s.label}** ({s.source}) — `{s.uri}`")
    return "\n".join(lines)
