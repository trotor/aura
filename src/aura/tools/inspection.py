"""inspect_dataset — kaikki mitä aineistosta tiedetään, yhdellä kutsulla.

Korvaa kolme työkalua: ``describe``, ``quality_report`` ja
``get_enrichments_tool``. Perustasoajossa (27.9.2026) ``describe`` kutsuttiin
lähes joka kysymyksessä — usein kahdesti samalle aineistolle, koska ensimmäinen
vastaus ei kertonut miten aineistoa kysytään. Tämä vastaus päättyy siksi aina
valmiiseen ``query_source``-kutsuun.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Context
from fastmcp.tools import ToolResult
from pydantic import Field

import aura.server as _server
from aura import extensions
from aura.constants import parse_json_list
from aura.database import get_dataset, get_latest_enrichments, get_resource_schema, get_source
from aura.health import get_dataset_health
from aura.quality import get_quality_scores
from aura.responses import Envelope, Model, NextAction, fail, respond, schema_of
from aura.server import mcp
from aura.tools.find import QUERYABLE_FORMATS

_MAX_RESOURCES = 30
_MAX_FIELDS = 100
_MAX_ENRICHMENT_CHARS = 500
_MAX_DESCRIPTION_CHARS = 2000


class DatasetInfo(Model):
    id: str
    name: str = ""
    title: str = ""
    description: str = ""
    organization: str = ""
    source: str = ""
    license: str = ""
    keywords: list[str] = Field(default_factory=list)
    modified: str = ""
    geographical_coverage: list[str] = Field(default_factory=list)
    update_frequency: str = ""
    access_level: str = "open"


class ResourceInfo(Model):
    index: int
    name: str = ""
    format: str = ""
    url: str = ""
    queryable: bool = False


class FieldInfo(Model):
    name: str
    type: str = ""
    resource_id: str | None = None


class InspectResult(Envelope):
    dataset: DatasetInfo | None = None
    resources: list[ResourceInfo] = Field(default_factory=list)
    resource_count: int = 0
    api: dict[str, str] | None = None
    fields: list[FieldInfo] = Field(default_factory=list)
    quality: dict[str, float] | None = Field(
        default=None, description="Laatupisteet 0–100 dimensioittain"
    )
    availability: dict[str, Any] | None = None
    enrichments: dict[str, str] = Field(
        default_factory=dict, description="Tutkimuksessa kirjatut lisätiedot kentittäin"
    )
    recipe: dict[str, Any] | None = Field(
        default=None, description="Todennettu kyselypohja (vain jos instanssi tarjoaa)"
    )


def _frequency(raw: Any) -> str:
    if not raw:
        return ""
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return str(raw)
    if isinstance(value, dict):
        fi = value.get("fi") or next(iter(value.values()), "")
        return ", ".join(fi) if isinstance(fi, list) else str(fi)
    return str(value)


@mcp.tool(tags={"public", "quality"}, output_schema=schema_of(InspectResult))
async def inspect_dataset(dataset_id: str, ctx: Context | None = None) -> ToolResult:
    """Aineiston kuvaus, resurssit, kentät, laatu, saatavuus ja kyselyohje.

    Päättyy valmiiseen ``query_source``-kutsuun, jos aineistoa voi kysellä.

    Args:
        dataset_id: Aineiston tunniste (id tai name), esim. find_datan tuloksesta.
    """
    conn = _server._get_conn(ctx)
    d = get_dataset(conn, dataset_id)
    if d is None:
        return fail(
            InspectResult,
            "dataset_not_found",
            f"Aineistoa '{dataset_id}' ei löytynyt.",
            hint="Hae tunniste find_data-työkalulla.",
            suggested_call=NextAction(tool="find_data", args={"query": dataset_id}),
        )
    ds_id = d["id"]
    desc = d.get("notes_fi") or d.get("notes") or ""
    info = DatasetInfo(
        id=ds_id,
        name=d.get("name", "") or "",
        title=d.get("title_fi") or d.get("title") or "",
        description=desc[:_MAX_DESCRIPTION_CHARS],
        organization=d.get("organization_title", "") or "",
        source=d.get("source", "") or "",
        license=d.get("license_title", "") or "",
        keywords=parse_json_list(d.get("keywords_fi", "[]"))[:20],
        modified=(d.get("metadata_modified") or "")[:10],
        geographical_coverage=parse_json_list(d.get("geographical_coverage", "[]")),
        update_frequency=_frequency(d.get("update_frequency")),
        access_level=d.get("access_level", "open") or "open",
    )
    all_resources = d.get("resources", [])
    resources = [
        ResourceInfo(
            index=i,
            name=r.get("name_fi") or r.get("name", "") or "",
            format=(r.get("format") or "").upper(),
            url=r.get("url", "") or "",
            queryable=(r.get("format") or "").upper() in QUERYABLE_FORMATS,
        )
        for i, r in enumerate(all_resources[:_MAX_RESOURCES])
    ]
    notes: list[str] = []
    if len(all_resources) > _MAX_RESOURCES:
        notes.append(f"Näytetään {_MAX_RESOURCES}/{len(all_resources)} resurssia.")

    src = get_source(conn, d.get("source", "")) or {}
    api = {k: v for k in ("query_protocol", "api_base_url") if (v := src.get(k))} or None

    fields = [
        FieldInfo(
            name=f["field_name"], type=f.get("field_type") or "", resource_id=f["resource_id"]
        )
        for f in get_resource_schema(conn, ds_id)[:_MAX_FIELDS]
    ]
    scores = get_quality_scores(conn, ds_id)
    quality = {k: round(float(v["score"]), 1) for k, v in scores.items()} if scores else None

    health = get_dataset_health(conn, ds_id)
    availability = None
    if health:
        availability = {
            "checked": len(health),
            "available": sum(1 for h in health if h["is_available"]),
            "last_checked": max((h.get("checked_at") or "" for h in health), default=""),
        }

    enrichments: dict[str, str] = {}
    for e in get_latest_enrichments(conn, ds_id):
        value = str(e.get("value", ""))
        enrichments.setdefault(e["field"], value[:_MAX_ENRICHMENT_CHARS])

    recipe = None
    for contribution in await extensions.call_all("inspect_dataset.recipe", conn=conn, dataset=d):
        recipe = contribution
        break

    next_actions: list[NextAction] = []
    if recipe and recipe.get("example"):
        next_actions.append(NextAction(**recipe["example"]))
    elif any(r.queryable for r in resources):
        next_actions.append(
            NextAction(
                tool="query_source",
                args={"dataset_id": ds_id},
                why="Esikatselu; PxWebissä palauttaa dimensiot suodattimia varten",
            )
        )
    next_actions.append(NextAction(tool="find_related", args={"dataset_id": ds_id}))

    payload = InspectResult(
        dataset=info,
        resources=resources,
        resource_count=len(all_resources),
        api=api,
        fields=fields,
        quality=quality,
        availability=availability,
        enrichments=enrichments,
        recipe=recipe,
        notes=notes,
        next_actions=next_actions,
    )
    formats = sorted({r.format for r in resources if r.format})
    summary = [
        f"{info.title} [{ds_id}] — {info.organization}",
        f"Lisenssi: {info.license or 'ei tiedossa'}. Formaatit: {', '.join(formats) or '—'}.",
    ]
    if quality and "overall" in quality:
        summary.append(f"Laatu {quality['overall']:.0f}/100.")
    return respond(payload, summary)
