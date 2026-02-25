"""Schema introspection -apufunktiot.

Poimii kenttätiedot markdown-taulukoista ja tallentaa kantaan.
Ei importtaa aura.server:iä (välttää sirkulaariset importit).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aura.database import upsert_resource_schema

logger = logging.getLogger(__name__)

_INT_PATTERN = re.compile(r"^-?\d+$")
_FLOAT_PATTERN = re.compile(r"^-?\d+[.,]\d+$")


def infer_type(values: list[str]) -> str:
    """Päättele kentän tyyppi esimerkkiarvoista."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "string"
    if all(_INT_PATTERN.match(v) for v in non_empty):
        return "integer"
    if all(_FLOAT_PATTERN.match(v) for v in non_empty):
        return "float"
    # ISO-päivämäärä (YYYY-MM-DD tai YYYY-MM-DDTHH:MM:SS)
    if all(len(v) >= 10 and v[4:5] == "-" and v[7:8] == "-" for v in non_empty):
        return "date"
    return "string"


def parse_md_table(md: str) -> tuple[list[str], list[list[str]]]:
    """Parsitaan markdown-taulukon otsikot ja datarivit."""
    headers: list[str] = []
    rows: list[list[str]] = []
    for line in md.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        # Ohita separator-rivi (| --- | --- |)
        if cells and all(c.replace("-", "").strip() == "" for c in cells):
            continue
        if not headers:
            headers = cells
        else:
            rows.append(cells)
    return headers, rows


def save_schema_from_markdown(
    conn: Any,
    resource_id: str,
    dataset_id: str,
    body: str,
) -> None:
    """Poimi kenttätiedot markdown-taulukosta ja tallenna kantaan."""
    if not resource_id or not dataset_id:
        return
    headers, rows = parse_md_table(body)
    if not headers or len(headers) < 1:
        return
    # Päättele tyypit sarakkeittain
    fields: list[tuple[str, str]] = []
    for i, header in enumerate(headers):
        col_values = [r[i] for r in rows if i < len(r)]
        ftype = infer_type(col_values)
        fields.append((header, ftype))
    upsert_resource_schema(conn, resource_id, dataset_id, fields)
    conn.commit()
