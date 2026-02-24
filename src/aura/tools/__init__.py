"""Aura MCP-työkalumoduulit.

Jokainen alimoduuli rekisteröi omat @mcp.tool()-funktionsa importin yhteydessä.
preview ja query eivät enää rekisteröi omia tooleja — käytä data.query_data().
"""

from aura.tools import (  # noqa: F401
    admin,
    area,
    data,
    describe,
    enrichment,
    health,
    quality,
    reference,
    research,
    search,
)

__all__ = [
    "admin",
    "area",
    "data",
    "describe",
    "enrichment",
    "health",
    "quality",
    "reference",
    "research",
    "search",
]
