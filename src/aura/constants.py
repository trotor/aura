"""Yhteiset vakiot."""

from aura import __version__

# Formaatit joita ohjelma osaa lukea. Käytetään laatupisteytyksessä,
# hakutulosten järjestyksessä ja alueprofiilin koneluettavuusosuudessa.
#
# Taulukkolaskentaformaatit ovat mukana, koska ne ovat koneluettavia:
# openpyxl lukee XLSX:n ja OOXML on ISO/IEC 29500 -standardi. Ilman niitä
# 422 datasettiä sai format_score 40/100 samalla kun WMS-kuvapalvelu sai
# täydet sata — Finavian lentoliikennetilastot ovat pelkkää XLSX:ää.
MACHINE_READABLE_FORMATS: frozenset[str] = frozenset({
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "WCS", "OData",
    "XML", "API", "Parquet", "GeoParquet", "GPKG", "SQLite",
    "PXWEB", "XLSX", "XLS", "ODS",
})

# Formaatit joille ``query_data`` osaa tehdä kyselyn. Tämä on **eri kysymys**
# kuin koneluettavuus: XLSX on koneluettava mutta esikatselu ei osaa avata
# sitä, ja WMS on listalla vaikka se palauttaa kuvia.
#
# Aiemmin sama joukko vastasi molempiin kysymyksiin, ja ero näkyi jo
# koodissa poikkeuksena ``fmt not in ("WMS", "WCS")``. Ilman erottelua
# XLSX:n lisääminen olisi saanut esikatselun valitsemaan tiedoston jota se
# ei osaa lukea — datasetissä jolla on sekä XLSX että CSV, jälkimmäinen on
# oikea valinta.
PREVIEWABLE_FORMATS: frozenset[str] = frozenset({
    "CSV", "JSON", "GeoJSON", "API", "WFS", "OData", "PXWEB",
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


# SPDX-lisenssimappaukset (#119)
# Avaimena CKAN/harvester license_id, arvona (spdx_id, title)
SPDX_LICENSE_MAP: dict[str, tuple[str, str]] = {
    # Creative Commons
    "cc-by-4.0": ("CC-BY-4.0", "Creative Commons Attribution 4.0"),
    "cc-by": ("CC-BY-4.0", "Creative Commons Attribution 4.0"),
    "cc-by-4": ("CC-BY-4.0", "Creative Commons Attribution 4.0"),
    "cc-by-sa-4.0": ("CC-BY-SA-4.0", "Creative Commons Attribution ShareAlike 4.0"),
    "cc-by-sa": ("CC-BY-SA-4.0", "Creative Commons Attribution ShareAlike 4.0"),
    "cc-by-nd-4.0": ("CC-BY-ND-4.0", "Creative Commons Attribution NoDerivatives 4.0"),
    "cc-by-nc-4.0": ("CC-BY-NC-4.0", "Creative Commons Attribution NonCommercial 4.0"),
    "cc-zero": ("CC0-1.0", "Creative Commons Zero v1.0 Universal"),
    "cc0-1.0": ("CC0-1.0", "Creative Commons Zero v1.0 Universal"),
    "cc-by-3.0": ("CC-BY-3.0", "Creative Commons Attribution 3.0"),
    # Open Data Commons
    "odc-by": ("ODC-By-1.0", "Open Data Commons Attribution License 1.0"),
    "odc-pddl": ("PDDL-1.0", "Open Data Commons Public Domain Dedication and License 1.0"),
    "odbl-1.0": ("ODbL-1.0", "Open Data Commons Open Database License 1.0"),
    "odc-odbl": ("ODbL-1.0", "Open Data Commons Open Database License 1.0"),
    # Other
    "mit": ("MIT", "MIT License"),
    "gpl-3.0": ("GPL-3.0-only", "GNU General Public License v3.0"),
    "apache-2.0": ("Apache-2.0", "Apache License 2.0"),
    "notspecified": ("", "Ei määritelty"),
}


def normalize_license(license_id: str) -> tuple[str, str]:
    """Normalisoi lisenssi-ID SPDX-muotoon.

    Returns:
        (spdx_id, spdx_title) tai alkuperäiset arvot jos tuntematon.
    """
    key = license_id.strip().lower()
    if key in SPDX_LICENSE_MAP:
        return SPDX_LICENSE_MAP[key]
    return (license_id, "")
