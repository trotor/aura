"""Yhteiset vakiot."""

from aura import __version__

MACHINE_READABLE_FORMATS: frozenset[str] = frozenset({
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "WCS", "OData",
    "XML", "API", "Parquet", "GeoParquet", "GPKG", "SQLite",
})


def parse_json_list(raw: str | list[str], default: list[str] | None = None) -> list[str]:
    """Parsii JSON-listan merkkijonosta tai palauttaa listan sellaisenaan."""
    if default is None:
        default = []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else default
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def user_agent(suffix: str = "") -> str:
    """Palauta User-Agent-merkkijono yhteisellä versiolla."""
    base = f"Aura/{__version__} (https://github.com/trotor/aura)"
    return f"{base} {suffix}".rstrip() if suffix else base
