"""Hakutoiminnot dataseteille."""

from __future__ import annotations

import json
import sqlite3


def format_dataset_summary(dataset: dict) -> str:
    """Muotoile datasetin yhteenveto luettavaan muotoon."""
    title = dataset.get("title_fi") or dataset.get("title") or dataset.get("name", "")
    org = dataset.get("organization_title", "")
    notes = dataset.get("notes_fi") or dataset.get("notes", "")
    license_title = dataset.get("license_title", "")
    modified = dataset.get("metadata_modified", "")[:10]

    # Rajoita kuvaus
    if len(notes) > 300:
        notes = notes[:297] + "..."

    keywords_raw = dataset.get("keywords_fi", "[]")
    if isinstance(keywords_raw, str):
        try:
            keywords = json.loads(keywords_raw)
        except json.JSONDecodeError:
            keywords = []
    else:
        keywords = keywords_raw

    parts = [f"## {title}"]
    if org:
        parts.append(f"**Julkaisija:** {org}")
    if notes:
        parts.append(f"**Kuvaus:** {notes}")
    if keywords:
        parts.append(f"**Avainsanat:** {', '.join(keywords)}")
    if license_title:
        parts.append(f"**Lisenssi:** {license_title}")
    if modified:
        parts.append(f"**Päivitetty:** {modified}")
    parts.append(f"**ID:** {dataset.get('name', dataset.get('id', ''))}")

    return "\n".join(parts)


def format_dataset_detail(dataset: dict) -> str:
    """Muotoile datasetin täydet tiedot."""
    summary = format_dataset_summary(dataset)

    resources = dataset.get("resources", [])
    if resources:
        summary += "\n\n### Resurssit\n"
        for r in resources:
            name = r.get("name_fi") or r.get("name") or "Nimetön"
            fmt = r.get("format", "")
            url = r.get("url", "")
            summary += f"- **{name}** ({fmt}): {url}\n"

    geo_raw = dataset.get("geographical_coverage", "[]")
    if isinstance(geo_raw, str):
        try:
            geo = json.loads(geo_raw)
        except json.JSONDecodeError:
            geo = []
    else:
        geo = geo_raw

    if geo:
        summary += f"\n**Maantieteellinen kattavuus:** {', '.join(geo)}"

    freq = dataset.get("update_frequency", "")
    if freq:
        summary += f"\n**Päivitystiheys:** {freq}"

    return summary


def format_stats(stats: dict) -> str:
    """Muotoile tilastot luettavaan muotoon."""
    parts = [
        f"# Aura — Avoimen datan tilastot",
        f"**Datasettejä:** {stats['total_datasets']}",
        f"**Organisaatioita:** {stats['total_organizations']}",
        f"**Dataformaatteja:** {stats['total_formats']}",
    ]

    if stats.get("top_organizations"):
        parts.append("\n### Suurimmat julkaisijat")
        for org in stats["top_organizations"]:
            parts.append(f"- {org['organization_title']}: {org['count']} datasettiä")

    if stats.get("top_formats"):
        parts.append("\n### Yleisimmät formaatit")
        for fmt in stats["top_formats"]:
            parts.append(f"- {fmt['format']}: {fmt['count']} resurssia")

    return "\n".join(parts)
