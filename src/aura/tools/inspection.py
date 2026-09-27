"""inspect_dataset — kaikki mitä aineistosta tiedetään, yhdellä kutsulla.

Korvaa kolme työkalua: ``describe``, ``quality_report`` ja
``get_enrichments_tool``. Perustasoajossa (27.9.2026) ``describe`` kutsuttiin
lähes joka kysymyksessä — usein kahdesti samalle aineistolle, koska ensimmäinen
vastaus ei kertonut miten aineistoa kysytään. Tämä vastaus päättyy siksi aina
valmiiseen ``query_source``-kutsuun.
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from typing import Any

from fastmcp import Context
from fastmcp.tools import ToolResult
from pydantic import Field

import aura.server as _server
from aura import extensions
from aura.constants import parse_json_list
from aura.database import get_dataset, get_latest_enrichments, get_resource_schema, get_source
from aura.formats import resource_format
from aura.health import get_dataset_health
from aura.quality import get_quality_scores
from aura.responses import Envelope, Model, NextAction, fail, respond, schema_of
from aura.server import mcp
from aura.tools.find import QUERYABLE_FORMATS
from aura.wfs import type_name_from_url

_MAX_RESOURCES = 30
_MAX_FIELDS = 100
_MAX_ENRICHMENT_CHARS = 500
_MAX_DESCRIPTION_CHARS = 2000
#: Kuvauksen ensimmäisen virkkeen enimmäispituus tekstiyhteenvedossa.
_SUMMARY_SENTENCE_CHARS = 160


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
    layer: str | None = Field(default=None, description="WFS: kerros josta kentät luettiin")


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


def _first_sentence(text: str, limit: int = _SUMMARY_SENTENCE_CHARS) -> str:
    """Kuvauksen ensimmäinen virke yhdelle riville, enintään ``limit`` merkkiä."""
    flat = re.sub(r"\s+", " ", re.sub(r"[#*_`>]+", " ", text)).strip()
    if not flat:
        return ""
    sentence = re.split(r"(?<=[.!?])\s", flat, maxsplit=1)[0]
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rsplit(" ", 1)[0] + "…"
    return sentence


def _availability_text(availability: dict[str, Any] | None) -> str:
    if not availability:
        return ""
    when = str(availability.get("last_checked") or "")[:10]
    checked, ok = availability["checked"], availability["available"]
    if ok == checked:
        return f"saatavilla ({when})" if when else "saatavilla"
    if ok == 0:
        return f"ei vastannut {when}".strip()
    return f"osin saatavilla ({ok}/{checked} resurssia, {when})"


def _probed_layers(conn: sqlite3.Connection, dataset_id: str) -> dict[str, str]:
    """WFS-palvelun osoite → kerros, jolla probe luki kentät (example_request).

    Probe tallentaa toimivan esimerkkikutsun, ja siinä on käytetty kerros.
    Kun resurssin URL ei nimeä kerrosta, se on palvelun ensimmäinen.
    """
    out: dict[str, str] = {}
    rows = conn.execute(
        "SELECT value FROM enrichments WHERE dataset_id = ? AND field = 'example_request'",
        (dataset_id,),
    ).fetchall()
    for (value,) in rows:
        base = str(value).split("?", 1)[0]
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(str(value)).query)
        layer = (query.get("typeNames") or query.get("typeName") or [""])[0]
        if layer:
            out.setdefault(base, layer)
    return out


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
    # Formaatiton resurssi arvioidaan URL:sta (aura.formats), kuten
    # query_source tekee — muuten kyselyohje ja kysely olisivat eri mieltä.
    resources = [
        ResourceInfo(
            index=i,
            name=r.get("name_fi") or r.get("name", "") or "",
            format=resource_format(r),
            url=r.get("url", "") or "",
            queryable=resource_format(r) in QUERYABLE_FORMATS,
        )
        for i, r in enumerate(all_resources[:_MAX_RESOURCES])
    ]
    notes: list[str] = []
    if len(all_resources) > _MAX_RESOURCES:
        notes.append(f"Näytetään {_MAX_RESOURCES}/{len(all_resources)} resurssia.")

    src = get_source(conn, d.get("source", "")) or {}
    api = {k: v for k in ("query_protocol", "api_base_url") if (v := src.get(k))} or None

    # Ulkoinen arvio 27.9.2026: kerroksettoman WFS-resurssin kentät luettiin
    # palvelun ensimmäisestä kerroksesta (HSY:n ilmanlaatuaineisto näytti
    # asuntotuotannon kenttiä). Kentät merkitään kerroksella ja huomautuksella.
    by_resource = {r.get("id"): r for r in all_resources}
    probed = _probed_layers(conn, ds_id)
    first_layer_resources: dict[str, str] = {}
    fields: list[FieldInfo] = []
    for f in get_resource_schema(conn, ds_id)[:_MAX_FIELDS]:
        res = by_resource.get(f["resource_id"]) or {}
        res_url = str(res.get("url") or "")
        layer = None
        if resource_format(res) == "WFS":
            layer = type_name_from_url(res_url)
            if layer is None:
                layer = probed.get(res_url.split("?", 1)[0])
                first_layer_resources[f["resource_id"]] = layer or ""
        fields.append(
            FieldInfo(
                name=f["field_name"],
                type=f.get("field_type") or "",
                resource_id=f["resource_id"],
                layer=layer,
            )
        )
    for rid, layer in first_layer_resources.items():
        idx = next((i for i, r in enumerate(all_resources) if r.get("id") == rid), None)
        notes.append(
            f"Resurssin {idx} kentät ovat WFS-palvelun ensimmäisestä kerroksesta"
            + (f" ({layer})" if layer else "")
            + ", "
            "koska resurssin URL ei nimeä kerrosta; aineiston oma kerros voi olla toinen. "
            "query_source kertoo kerrokset (layers) ja ottaa layer-parametrin."
        )
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
    elif first := next((r for r in resources if r.queryable), None):
        args: dict[str, Any] = {"dataset_id": ds_id, "resource_index": first.index}
        if first.format == "WFS" and (layer := type_name_from_url(first.url)):
            args["layer"] = layer
        next_actions.append(
            NextAction(
                tool="query_source",
                args=args,
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
    # Tekstiyhteenveto on enintään viisi riviä (responses.MAX_SUMMARY_LINES).
    # Ulkoinen arvio 27.9.2026: kuvaus, päivitys, kentät ja saatavuus olivat
    # vain rakenteisessa sisällössä, eikä tekstiä lukeva asiakas nähnyt niitä.
    formats = sorted({r.format for r in resources if r.format})
    summary = [f"{info.title} [{ds_id}] — {info.organization}"]
    if sentence := _first_sentence(desc):
        summary.append(sentence)
    summary.append(
        f"Lisenssi: {info.license or 'ei tiedossa'}. Formaatit: {', '.join(formats) or '—'}."
        + (f" Päivitetty {info.modified}." if info.modified else "")
    )
    facts = [f"Kenttiä {len(fields)}" if fields else "Kenttiä ei tunnettu"]
    if quality and "overall" in quality:
        facts.append(f"laatu {quality['overall']:.0f}/100")
    if avail := _availability_text(availability):
        facts.append(avail)
    summary.append(", ".join(facts) + ".")
    return respond(payload, summary)
