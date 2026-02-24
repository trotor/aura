"""Yhteiset vakiot."""

from aura import __version__

MACHINE_READABLE_FORMATS: frozenset[str] = frozenset({
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "WCS", "OData",
    "XML", "API", "Parquet", "GeoParquet", "GPKG", "SQLite",
    "PXWEB",
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


def format_date(iso_str: str | None, *, include_time: bool = False) -> str:
    """Turvallinen ISO-päivämäärän formatointi.

    Args:
        iso_str: ISO 8601 -aikaleima tai None.
        include_time: Jos True, palauta myös kellonaika (YYYY-MM-DD HH:MM).

    Returns:
        Formatoitu päivämäärä tai tyhjä merkkijono.
    """
    if not iso_str:
        return ""
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M" if include_time else "%Y-%m-%d")
    except (ValueError, TypeError):
        cutoff = 16 if include_time else 10
        return iso_str[:cutoff] if len(iso_str) >= cutoff else iso_str


def user_agent(suffix: str = "") -> str:
    """Palauta User-Agent-merkkijono yhteisellä versiolla."""
    base = f"Aura/{__version__} (https://github.com/trotor/aura)"
    return f"{base} {suffix}".rstrip() if suffix else base
