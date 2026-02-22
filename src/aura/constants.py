"""Yhteiset vakiot."""

MACHINE_READABLE_FORMATS: frozenset[str] = frozenset({
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "WCS", "OData",
    "XML", "API", "Parquet", "GeoParquet", "GPKG", "SQLite",
})
