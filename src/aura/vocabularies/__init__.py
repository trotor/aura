"""Domain-sanastot hakutermien laajentamiseen.

Sanastot ovat JSON-tiedostoja jotka mappaavat hakutermejä synonyymeihin
ja alakäsitteisiin. Tämä on nopea, paikallinen laajennus (ei API-kutsuja)
joka täydentää YSO-ontologialaajennusta.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VOCAB_DIR = Path(__file__).parent
_loaded_vocabs: list[dict[str, Any]] | None = None


def load_all() -> list[dict[str, Any]]:
    """Lataa kaikki sanastot JSON-tiedostoista.

    Välimuistittaa tuloksen prosessin ajaksi.
    """
    global _loaded_vocabs
    if _loaded_vocabs is not None:
        return _loaded_vocabs

    vocabs: list[dict[str, Any]] = []
    for path in sorted(_VOCAB_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            vocabs.append(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("[vocabularies] Virhe ladattaessa %s: %s", path.name, e)

    _loaded_vocabs = vocabs
    return vocabs


def expand_with_vocabularies(query: str) -> list[str]:
    """Laajenna hakutermi domain-sanastoilla.

    Palauttaa listan lisätermejä jotka vastaavat hakusanoja.
    Case-insensitive haku. Ei sisällä alkuperäistä termiä.

    Args:
        query: Hakusanat (yksi tai useampi sana).

    Returns:
        Lista laajennustermeistä (tyhjä jos ei osumia).
    """
    vocabs = load_all()
    query_lower = query.lower()
    query_tokens = query_lower.split()
    expansions: list[str] = []
    seen: set[str] = set()

    for vocab in vocabs:
        mappings = vocab.get("mappings", {})
        for term, synonyms in mappings.items():
            term_lower = term.lower()
            # Tarkka osuma koko hakuun tai yksittäiseen sanaan
            if term_lower == query_lower or term_lower in query_tokens:
                for syn in synonyms:
                    syn_lower = syn.lower()
                    if syn_lower not in seen and syn_lower != query_lower:
                        seen.add(syn_lower)
                        expansions.append(syn)

    return expansions


#: Muunnelmien enimmäismäärä yhdelle kyselylle. Jokainen muunnelma on oma
#: tiukka FTS-haku, joten määrä rajaa kyselyn hinnan.
MAX_VARIANTS = 6


def _lemma_key(text: str) -> str:
    from aura.lemmatize import lemma, tokenize

    return " ".join(lemma(t) or t for t in tokenize(text))


def synonym_variants(query: str, lexicon: object | None = None) -> list[str]:
    """Muunnelmat tekstinä (ks. ``synonym_variants_ranked``)."""
    return [v for v, _ in synonym_variants_ranked(query, lexicon)]


def synonym_variants_ranked(
    query: str, lexicon: object | None = None
) -> list[tuple[str, bool]]:
    """Kysely, jossa arkisana on korvattu sanaston termillä.

    Eroaa ``expand_with_vocabularies``ista kahdella tavalla, ja kumpikin on
    syy siihen, miksi arkisanat eivät löytäneet mitään (ulkoinen arvio
    27.9.2026: "päiväkotipaikat", "kirjastojen lainaukset kunnittain"):

    1. Sanaa verrataan **perusmuotoon ja yhdyssanan osiin**, ei vain
       pintamuotoon: "päiväkotipaikat" → päiväkoti + paikka → varhaiskasvatus.
    2. Tulos on **kokonainen kysely** jossa yksi sana on vaihdettu, joten se
       voidaan hakea tiukasti (kaikki sanat osuvat) heti tiukan vaiheen
       jälkeen — ei vasta viimeisenä OR-hakuna, jossa se ei ehtinyt mukaan.
    """
    from aura.decompound import split_compound
    from aura.lemmatize import lemma, tokenize

    by_key: dict[str, list[str]] = {}
    # Vain arkisanasto: muut sanastot ovat aihealueen laajennuksia ("koulu" →
    # kouluverkko, oppilaaksiottoalue), ja tiukkana hakuna ne toivat
    # kysymyssetteihin kohinaa (mitattu 27.9.2026). Arkisanaston jokainen rivi
    # on sama asia eri sanoin.
    for vocab in load_all():
        if vocab.get("domain") != "everyday":
            continue
        for term, synonyms in vocab.get("mappings", {}).items():
            by_key.setdefault(_lemma_key(term), []).extend(synonyms)
    tokens = tokenize(query)
    if not tokens:
        return []
    variants: list[tuple[str, bool]] = []

    def add(text: str, strong: bool = False) -> None:
        if text and text != query and all(text != v for v, _ in variants):
            variants.append((text, strong))

    # Monisanainen avain ("uudet yritykset") on vahva: se on sama asia eri
    # sanoin eikä yksittäisen sanan tulkinta, joten se haetaan aina.
    whole = _lemma_key(query)
    for syn in by_key.get(whole, [])[:3]:
        add(syn, strong=" " in whole)
    for i, tok in enumerate(tokens):
        base = lemma(tok) or tok
        keys = [tok.lower(), base]
        parts = split_compound(base, lexicon) if lexicon is not None else None  # type: ignore[arg-type]
        if parts:
            keys += parts
        for key in keys:
            for syn in by_key.get(key, [])[:3]:
                add(" ".join([*tokens[:i], syn, *tokens[i + 1 :]]))
        # Kahden sanan avaimet ("asuntojen hinnat", "uudet yritykset")
        if i + 1 < len(tokens):
            pair = f"{base} {lemma(tokens[i + 1]) or tokens[i + 1]}"
            for syn in by_key.get(pair, [])[:3]:
                add(" ".join([*tokens[:i], syn, *tokens[i + 2 :]]), strong=True)
    return sorted(variants, key=lambda v: not v[1])[:MAX_VARIANTS]


def reset_cache() -> None:
    """Tyhjennä välimuisti (testejä varten)."""
    global _loaded_vocabs
    _loaded_vocabs = None
