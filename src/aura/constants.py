"""Yhteiset vakiot."""

from aura import __version__

MACHINE_READABLE_FORMATS: frozenset[str] = frozenset({
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "WCS", "OData",
    "XML", "API", "Parquet", "GeoParquet", "GPKG", "SQLite",
})


def user_agent(suffix: str = "") -> str:
    """Palauta User-Agent-merkkijono yhteisellä versiolla."""
    base = f"Aura/{__version__} (https://github.com/trotor/aura)"
    return f"{base} {suffix}".rstrip() if suffix else base
