"""Hakutoiminnot dataseteille."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from aura.constants import format_date, parse_json_list


def format_dataset_summary(dataset: dict[str, Any]) -> str:
    """Muotoile datasetin yhteenveto luettavaan muotoon."""
    title = dataset.get("title_fi") or dataset.get("title") or dataset.get("name", "")
    org = dataset.get("organization_title", "")
    notes = dataset.get("notes_fi") or dataset.get("notes", "")
    license_title = dataset.get("license_title", "")
    modified = format_date(dataset.get("metadata_modified"))

    # Rajoita kuvaus
    if len(notes) > 300:
        notes = notes[:297] + "..."

    keywords = parse_json_list(dataset.get("keywords_fi", "[]"))

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

    # Duplikaatteja ei piiloteta vaan kerrotaan: sama taulu esiintyy usein
    # monella tunnisteella (Tilastokeskuksen taulukoodit, katalogien
    # peilaukset). Käyttäjän on voitava tietää että vaihtoehtoja on.
    duplicates = int(dataset.get("duplicate_count", 0) or 0)
    if duplicates:
        muoto = "versio" if duplicates == 1 else "versiota"
        parts.append(f"**Muita versioita:** {duplicates} {muoto} samasta aineistosta")

    parts.append(f"**ID:** {dataset.get('name', dataset.get('id', ''))}")

    return "\n".join(parts)


ENRICHMENT_FIELD_LABELS: dict[str, str] = {
    "description_extended": "Laajennettu kuvaus",
    "api_endpoint": "Rajapinta-URL",
    "api_format": "Rajapinnan formaatti",
    "data_fields": "Datakentät",
    "related_datasets": "Liittyvät datasetit",
    "related_services": "Liittyvät palvelut",
    "quality_notes": "Laatuhuomiot",
    "use_case": "Käyttötapaus",
    "access_instructions": "Käyttöohjeet",
    "auth_method": "Autentikointi",
    "auth_registration_url": "Rekisteröitymis-URL",
    "auth_notes": "Pääsyhuomiot",
    "organization_context": "Organisaation tausta",
    "temporal_coverage": "Ajallinen kattavuus",
    "update_frequency_actual": "Havaittu päivitystiheys",
    "keywords": "Lisäavainsanat",
    "tags": "Tagit",
    "crs": "Koordinaattijärjestelmä",
    "joinable_keys": "Yhdistettävät avaimet",
}

# Kentät joiden arvo on JSON-taulukko
_LIST_FIELDS = {"data_fields", "keywords", "tags", "related_services", "joinable_keys"}


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


def _enrichment_age_warning(created_at: str, max_age_days: int = 180) -> str:
    """Palauta ikävaroitus jos rikastus on vanha."""
    if not created_at:
        return ""
    try:
        created = datetime.fromisoformat(created_at)
        age = (datetime.now(tz=UTC) - created.replace(tzinfo=UTC)).days
        if age > max_age_days:
            months = age // 30
            return f" [{months} kk vanha]"
    except (ValueError, TypeError):
        pass
    return ""


def format_enrichments(
    enrichments: list[dict[str, Any]],
    stale_ids: set[str] | None = None,
) -> str:
    """Muotoile rikastukset luettavaan muotoon.

    Args:
        enrichments: Lista rikastuksia.
        stale_ids: Vanhentuneiden rikastusten id:t (näytetään varoitus).
    """
    if not enrichments:
        return ""
    if stale_ids is None:
        stale_ids = set()

    parts = ["\n### Rikastukset\n"]
    for e in enrichments:
        field = e.get("field", "")
        label = ENRICHMENT_FIELD_LABELS.get(field, field)
        value = _format_enrichment_value(field, e.get("value", ""))
        confidence = e.get("confidence", "")
        source_type = e.get("source_type", "")
        enrichment_id = e.get("id", "")

        conf_marker = ""
        if confidence == "high":
            conf_marker = " [varma]"
        elif confidence == "low":
            conf_marker = " [epävarma]"
        elif confidence == "verified":
            conf_marker = " [vahvistettu]"

        age_warning = _enrichment_age_warning(e.get("created_at", ""))

        stale_marker = ""
        if enrichment_id in stale_ids:
            stale_marker = " [vanhentunut]"

        parts.append(f"- **{label}:** {value}{conf_marker}{age_warning}{stale_marker}")
        if source_type and source_type != "mcp_session":
            parts.append(f"  (lähde: {source_type})")

    return "\n".join(parts)


def format_conflicts(conflicts: list[dict[str, Any]]) -> str:
    """Muotoile ristiriitaiset rikastukset."""
    if not conflicts:
        return ""

    # Ryhmitä kentän mukaan
    by_field: dict[str, list[dict[str, Any]]] = {}
    for c in conflicts:
        field = c.get("field", "")
        by_field.setdefault(field, []).append(c)

    parts = ["\n### Ristiriitaiset rikastukset\n"]
    for field, entries in by_field.items():
        label = ENRICHMENT_FIELD_LABELS.get(field, field)
        parts.append(f"**{label}:**")
        for e in entries:
            value = _format_enrichment_value(field, e.get("value", ""))
            confidence = e.get("confidence", "medium")
            created = format_date(e.get("created_at"))
            parts.append(f"  - {value} ({confidence}, {created})")

    return "\n".join(parts)


def format_dataset_detail(
    dataset: dict[str, Any],
    enrichments: list[dict[str, Any]] | None = None,
    stale_ids: set[str] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
) -> str:
    """Muotoile datasetin täydet tiedot.

    Args:
        dataset: Datasetin tiedot.
        enrichments: Uusimmat rikastukset (yksi per kenttä).
        stale_ids: Vanhentuneiden rikastusten id:t.
        conflicts: Ristiriitaiset rikastukset.
    """
    summary = format_dataset_summary(dataset)

    resources = dataset.get("resources", [])
    if resources:
        summary += "\n\n### Resurssit\n"
        for r in resources:
            name = r.get("name_fi") or r.get("name") or "Nimetön"
            fmt = r.get("format", "")
            url = r.get("url", "")
            summary += f"- **{name}** ({fmt}): {url}\n"

    geo = parse_json_list(dataset.get("geographical_coverage", "[]"))

    if geo:
        summary += f"\n**Maantieteellinen kattavuus:** {', '.join(geo)}"

    freq = dataset.get("update_frequency", "")
    if freq:
        summary += f"\n**Päivitystiheys:** {freq}"

    access_level = dataset.get("access_level", "open")
    if access_level != "open":
        label = {"registration": "Vaatii rekisteröinnin", "restricted": "Rajoitettu pääsy"}
        summary += f"\n**Saatavuus:** {label.get(access_level, access_level)}"

    harvested = format_date(dataset.get("harvested_at"))
    if harvested:
        summary += f"\n**Harvestoitu:** {harvested}"

    if enrichments:
        summary += format_enrichments(enrichments, stale_ids=stale_ids)

    if conflicts:
        summary += format_conflicts(conflicts)

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

    if stats.get("probe_total"):
        parts.append(
            f"\n**Skeema johdettu:** {stats['probe_ok']}/{stats['probe_total']} "
            "resurssista onnistuneesti"
        )

    return "\n".join(parts)
