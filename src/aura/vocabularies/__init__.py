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


def reset_cache() -> None:
    """Tyhjennä välimuisti (testejä varten)."""
    global _loaded_vocabs
    _loaded_vocabs = None
