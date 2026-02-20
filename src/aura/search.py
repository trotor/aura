"""Hakutoiminnot dataseteille."""

from __future__ import annotations

import json
from typing import Any


def format_dataset_summary(dataset: dict[str, Any]) -> str:
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

    access_level = dataset.get("access_level", "open")
    lock = "\U0001f512 " if access_level == "restricted" else ""

    parts = [f"## {lock}{title}"]
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


ENRICHMENT_FIELD_LABELS: dict[str, str] = {
    "description_extended": "Laajennettu kuvaus",
    "api_endpoint": "Rajapinta-URL",
    "api_format": "Rajapinnan formaatti",
    "data_fields": "Datakentät",
    "related_datasets": "Liittyvät datasetit",
    "quality_notes": "Laatuhuomiot",
    "use_case": "Käyttötapaus",
    "access_instructions": "Käyttöohjeet",
    "organization_context": "Organisaation tausta",
    "temporal_coverage": "Ajallinen kattavuus",
    "update_frequency_actual": "Havaittu päivitystiheys",
    "keywords": "Lisäavainsanat",
    "tags": "Tagit",
}

# Kentät joiden arvo on JSON-taulukko
_LIST_FIELDS = {"data_fields", "keywords", "tags"}


def _format_enrichment_value(field: str, value: str) -> str:
    """Muotoile rikastuksen arvo kenttätyypin mukaan."""
    if field in _LIST_FIELDS:
        try:
            items = json.loads(value)
            if isinstance(items, list):
                return ", ".join(str(v) for v in items)
        except (json.JSONDecodeError, TypeError):
            pass
    return value


def format_enrichments(enrichments: list[dict[str, Any]]) -> str:
    """Muotoile rikastukset luettavaan muotoon."""
    if not enrichments:
        return ""

    parts = ["\n### Rikastukset\n"]
    for e in enrichments:
        field = e.get("field", "")
        label = ENRICHMENT_FIELD_LABELS.get(field, field)
        value = _format_enrichment_value(field, e.get("value", ""))
        confidence = e.get("confidence", "")
        source_type = e.get("source_type", "")

        conf_marker = ""
        if confidence == "high":
            conf_marker = " [varma]"
        elif confidence == "low":
            conf_marker = " [epävarma]"
        elif confidence == "verified":
            conf_marker = " [vahvistettu]"

        parts.append(f"- **{label}:** {value}{conf_marker}")
        if source_type and source_type != "mcp_session":
            parts.append(f"  (lähde: {source_type})")

    return "\n".join(parts)


def format_dataset_detail(
    dataset: dict[str, Any],
    enrichments: list[dict[str, Any]] | None = None,
) -> str:
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

    access_level = dataset.get("access_level", "open")
    if access_level != "open":
        label = {"registration": "Vaatii rekisteröinnin", "restricted": "Rajoitettu pääsy"}
        summary += f"\n**Saatavuus:** {label.get(access_level, access_level)}"

    if enrichments:
        summary += format_enrichments(enrichments)

    return summary


def format_stats(stats: dict[str, Any]) -> str:
    """Muotoile tilastot luettavaan muotoon."""
    parts = [
        "# Aura — Avoimen datan tilastot",
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
