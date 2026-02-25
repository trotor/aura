"""Schema introspection -apufunktiot.

Poimii kenttätiedot markdown-taulukoista ja tallentaa kantaan.
Ei importtaa aura.server:iä (välttää sirkulaariset importit).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from aura.database import upsert_resource_schema

logger = logging.getLogger(__name__)

_INT_PATTERN = re.compile(r"^-?\d+$")
_FLOAT_PATTERN = re.compile(r"^-?\d+[.,]\d+$")

# Suomalaiset avaintunnisteet kenttänimen perusteella (#117)
# (pattern, key_name, key_standard)
_KEY_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"kunta.?(koodi|numero|code)", re.I), "kuntakoodi", "Tilastokeskus 3-num"),
    (re.compile(r"municipality.?code", re.I), "kuntakoodi", "Tilastokeskus 3-num"),
    (re.compile(r"^kunta$", re.I), "kuntakoodi", "Tilastokeskus"),
    (re.compile(r"maakunta.?(koodi|code)", re.I), "maakuntakoodi", "Tilastokeskus 2-num"),
    (re.compile(r"region.?code", re.I), "maakuntakoodi", "Tilastokeskus 2-num"),
    (re.compile(r"postin(umero|ro)|postal.?code|zipcode", re.I), "postinumero", "Posti 5-num"),
    (re.compile(r"vuosi|year|^v$", re.I), "vuosi", "4-num"),
    (re.compile(r"ely.?(koodi|code|keskus)", re.I), "ELY-koodi", "Tilastokeskus"),
    (re.compile(r"y.?tunnus|business.?id", re.I), "y-tunnus", "PRH 8-num"),
    (re.compile(r"hetu|henkilö|person.?id|ssn", re.I), "henkilötunnus", "anonymisoitu"),
    (re.compile(r"kiinteistö.?tunnus|property.?id", re.I), "kiinteistötunnus", "MML"),
]


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


def detect_joinable_keys(field_names: list[str]) -> list[dict[str, str]]:
    """Tunnista yhteiset avaimet kenttänimistä (#117).

    Returns:
        Lista tunnistettuja avaimia: [{"field": ..., "key": ..., "standard": ...}]
    """
    keys: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in field_names:
        for pattern, key_name, standard in _KEY_PATTERNS:
            if key_name in seen:
                continue
            if pattern.search(name):
                keys.append({
                    "field": name,
                    "key": key_name,
                    "standard": standard,
                })
                seen.add(key_name)
                break
    return keys


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

    # Tunnista yhteiset avaimet ja tallenna enrichmentiksi (#117)
    keys = detect_joinable_keys(headers)
    if keys:
        _save_joinable_keys(conn, dataset_id, keys)

    conn.commit()


def _save_joinable_keys(
    conn: Any,
    dataset_id: str,
    keys: list[dict[str, str]],
) -> None:
    """Tallenna tunnistetut avaimet joinable_keys-enrichmentiksi."""
    from aura.database import add_enrichment

    value = json.dumps(keys, ensure_ascii=False)
    # Tarkista onko jo olemassa
    existing = conn.execute(
        "SELECT 1 FROM enrichments "
        "WHERE dataset_id = ? AND field = 'joinable_keys' LIMIT 1",
        (dataset_id,),
    ).fetchone()
    if existing:
        return
    add_enrichment(
        conn, dataset_id, "joinable_keys", value,
        confidence="medium",
        source_type="schema_analysis",
        source_detail="Auto-detected from field names",
    )
