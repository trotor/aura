"""Kuvailu- ja vertailutyökalut: describe, compare."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.constants import format_date, parse_json_list
from aura.database import (
    get_conflicting_enrichments,
    get_dataset,
    get_datasets_by_ids,
    get_latest_enrichments,
    get_stale_enrichments,
)
from aura.quality import get_quality_scores
from aura.search import format_dataset_detail
from aura.server import mcp
from aura.tools.quality import DIMENSION_LABELS

# Enrichment-kentät prioriteettijärjestyksessä
_ENRICHMENT_PRIORITIES = [
    ("access_instructions", "Miten dataa haetaan käytännössä?"),
    ("data_fields", "Mitä kenttiä/sarakkeita data sisältää?"),
    ("use_case", "Mihin dataa voi käyttää?"),
    ("temporal_coverage", "Miltä ajanjaksolta data on?"),
    ("description_extended", "Laajempi kuvaus aineistosta"),
    ("keywords", "Lisäavainsanat haun parantamiseksi"),
    ("api_endpoint", "Rajapinnan URL"),
    ("api_format", "Rajapinnan formaatti (REST, WFS, OData)"),
    ("quality_notes", "Huomioita datan laadusta"),
    ("organization_context", "Taustatietoa julkaisijasta"),
    ("update_frequency_actual", "Havaittu päivitystiheys"),
]


@mcp.tool()
def describe(dataset_id: str, ctx: Context | None = None) -> str:
    """Kuvaa yksittäinen datasetti yksityiskohtaisesti.

    Args:
        dataset_id: Datasetin ID tai nimi (esim. "helsinkikanava-open-data")
    """
    conn = _server._get_conn(ctx)
    dataset = get_dataset(conn, dataset_id)

    if dataset is None:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    ds_id = dataset["id"]
    enrichments = get_latest_enrichments(conn, ds_id)
    stale = get_stale_enrichments(conn, ds_id)
    stale_ids = {e["id"] for e in stale}
    conflicts = get_conflicting_enrichments(conn, ds_id)
    result = format_dataset_detail(
        dataset,
        enrichments=enrichments,
        stale_ids=stale_ids,
        conflicts=conflicts,
    )

    # Laatupisteet
    quality = get_quality_scores(conn, ds_id)
    if quality and "overall" in quality:
        result += _format_quality_section(quality)

    # Resurssien saatavuus
    result += _format_health_section(conn, ds_id)

    # Enrichment-kehotus: puuttuvat kentät
    result += _format_enrichment_gaps(ds_id, enrichments)

    return result


@mcp.tool()
def compare(dataset_ids: list[str], ctx: Context | None = None) -> str:
    """Vertaile datasettejä rinnakkain.

    Args:
        dataset_ids: Lista datasetin ID:istä tai nimistä (2–5 kpl)
    """
    if len(dataset_ids) < 2:
        return "Anna vähintään 2 datasetin ID:tä vertailua varten."
    if len(dataset_ids) > 5:
        return "Vertaile korkeintaan 5 datasettiä kerrallaan."

    conn = _server._get_conn(ctx)
    datasets = get_datasets_by_ids(conn, dataset_ids)

    if not datasets:
        return "Yhtäkään datasettiä ei löytynyt annetuilla ID:illä."

    parts = [f"# Datasettien vertailu ({len(datasets)} kpl)\n"]

    for d in datasets:
        title = d.get("title_fi") or d.get("title") or d.get("name", "")
        org = d.get("organization_title", "")
        source = d.get("source", "")
        license_t = d.get("license_title", "")
        num_res = d.get("num_resources", 0) or 0
        modified = format_date(d.get("metadata_modified"))
        size = d.get("estimated_size_bytes", 0) or 0

        keywords = parse_json_list(d.get("keywords_fi", "[]"))

        # Resurssiformaatit
        formats = sorted({r.get("format", "") for r in d.get("resources", []) if r.get("format")})

        parts.append(f"## {title}")
        parts.append(f"- **Lähde:** {source}")
        parts.append(f"- **Julkaisija:** {org}")
        parts.append(f"- **Lisenssi:** {license_t}")
        parts.append(f"- **Resursseja:** {num_res}")
        parts.append(f"- **Formaatit:** {', '.join(formats) if formats else '—'}")
        parts.append(f"- **Päivitetty:** {modified or '—'}")
        if size > 0:
            size_mb = size / (1024 * 1024)
            parts.append(f"- **Arvioitu koko:** {size_mb:.1f} MB")
        if keywords:
            parts.append(f"- **Avainsanat:** {', '.join(keywords[:10])}")
        parts.append(f"- **ID:** {d.get('name', d.get('id', ''))}")
        parts.append("")

    return "\n".join(parts)


# --- Apufunktiot ---


def _format_quality_section(quality: dict[str, Any]) -> str:
    """Muotoile laatupisteet describe()-tulokseen."""
    overall = quality.get("overall", {}).get("score", 0)

    parts = [f"\n\n### Laatuarvio: {overall:.0f}/100\n"]
    for dim, label in DIMENSION_LABELS.items():
        if dim in quality:
            s = quality[dim]["score"]
            bar_len = int(s / 10)
            bar = "\u2588" * bar_len + "\u2591" * (10 - bar_len)
            parts.append(f"  {label:16s} {s:5.0f}/100 {bar}")

    return "\n".join(parts)


def _format_health_section(conn: Any, dataset_id: str) -> str:
    """Muotoile datasetin resurssien saatavuustiedot."""
    from aura.health import get_dataset_health

    health = get_dataset_health(conn, dataset_id)
    if not health:
        return ""

    total = len(health)
    avail = sum(1 for h in health if h["is_available"])
    parts = [f"\n\n### Resurssien saatavuus ({avail}/{total})\n"]

    for h in health:
        icon = "+" if h["is_available"] else "-"
        ms = f" ({h['response_time_ms']}ms)" if h.get("response_time_ms") else ""
        err = f" — {h['error_message']}" if h.get("error_message") else ""
        url = h.get("url", "")
        if len(url) > 70:
            url = url[:67] + "..."
        parts.append(f"- [{icon}] {url}{ms}{err}")

    return "\n".join(parts)


def _format_enrichment_gaps(
    dataset_id: str,
    enrichments: list[dict[str, Any]],
    max_gaps: int = 5,
) -> str:
    """Muotoile puuttuvien enrichment-kenttien kehotus."""
    existing_fields = {e.get("field", "") for e in enrichments}

    missing = [
        (field, desc)
        for field, desc in _ENRICHMENT_PRIORITIES
        if field not in existing_fields
    ]

    if not missing:
        return ""

    show = missing[:max_gaps]
    parts = ["\n\n### Puuttuvat tiedot\n"]
    for field, desc in show:
        parts.append(f"- **{field}**: {desc}")

    parts.append(
        f'\nTallenna: enrich(dataset_id="{dataset_id}", '
        'field="...", value="...")'
    )

    return "\n".join(parts)
