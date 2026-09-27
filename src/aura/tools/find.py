"""find_data — yksi hakutyökalu kaikille hakuaikomuksille.

Korvaa neljä päällekkäistä työkalua: ``search``, ``search_structured``,
``search_by_region`` ja ``recommend``. Mitattuna 27.9.2026 (tehtäväsarja,
31 kysymystä) agentti kutsui niitä ristiin saman kysymyksen aikana —
yksittäinen faktakysymys vaati mediaanina seitsemän kutsua, joista useimmat
olivat hakuja eri työkaluilla samalla aikomuksella.

Järjestys on sama kuin ``search``issä (mitattu hakupino), ei ``recommend``in
uudelleenpisteytys: sille ei ole mittausta joka osoittaisi sen paremmaksi.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.tools.tool import ToolResult
from pydantic import Field

import aura.server as _server
from aura import extensions
from aura.areas import resolve_area
from aura.constants import parse_json_list
from aura.database import search_datasets
from aura.limits import MAX_SEARCH_LIMIT, clamp
from aura.responses import AreaRef, Envelope, Model, NextAction, respond, schema_of
from aura.server import mcp
from aura.telemetry import record_zero_result
from aura.tools.search import (
    _batch_formats,
    _batch_health_status,
    _batch_quality_scores,
    _build_region_query,
    _resolve_region,
)

#: Formaatit joille query_source osaa tehdä kyselyn.
QUERYABLE_FORMATS = frozenset({"PXWEB", "WFS", "CSV", "JSON", "GEOJSON", "API", "ODATA"})

_DESCRIPTION_CHARS = 300


class DatasetHit(Model):
    id: str
    title: str
    description: str = ""
    organization: str = ""
    source: str = ""
    license: str = ""
    formats: list[str] = Field(default_factory=list)
    queryable: bool = False
    modified: str = ""
    access_level: str = "open"
    quality: float | None = Field(None, description="Metatiedon laatupisteet 0–100")
    available: bool | None = Field(None, description="Viimeisin saatavuustarkistus")
    coverage: str | None = Field(
        None,
        description="own = aineisto koskee aluetta; nationwide = koko maan aineisto "
        "jossa alue on dimensioarvo",
    )


class IndicatorHit(Model):
    id: str
    name: str
    unit: str | None = None
    source: str | None = None
    tool: str | None = None


class FindDataResult(Envelope):
    query: str = ""
    count: int = 0
    offset: int = 0
    region: AreaRef | None = None
    indicators: list[IndicatorHit] = Field(
        default_factory=list,
        description="Valmiit tunnusluvut jotka vastaavat hakua (vain jos instanssi tarjoaa)",
    )
    results: list[DatasetHit] = Field(default_factory=list)


def _hit(
    d: dict[str, Any],
    formats: set[str],
    quality: float | None,
    health: dict[str, Any] | None,
    region_names: list[str] | None,
) -> DatasetHit:
    desc = d.get("notes_fi") or d.get("notes") or ""
    if len(desc) > _DESCRIPTION_CHARS:
        desc = desc[: _DESCRIPTION_CHARS - 1].rstrip() + "…"
    coverage = None
    if region_names:
        cov = " ".join(parse_json_list(d.get("geographical_coverage", "[]"))).lower()
        coverage = "own" if any(n.lower() in cov for n in region_names) else "nationwide"
    upper = {f.upper() for f in formats}
    return DatasetHit(
        id=d.get("id", ""),
        title=d.get("title_fi") or d.get("title") or d.get("name", ""),
        description=desc,
        organization=d.get("organization_title", "") or "",
        source=d.get("source", "") or "",
        license=d.get("license_title", "") or "",
        formats=sorted(formats),
        queryable=bool(upper & QUERYABLE_FORMATS),
        modified=(d.get("metadata_modified") or "")[:10],
        access_level=d.get("access_level", "open") or "open",
        quality=round(quality, 1) if quality is not None else None,
        available=health.get("is_available") if health else None,
        coverage=coverage,
    )


@mcp.tool(tags={"public"}, output_schema=schema_of(FindDataResult))
async def find_data(
    query: str = "",
    region: str = "",
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
    limit: int = 10,
    offset: int = 0,
    ctx: Context | None = None,
) -> ToolResult:
    """Etsi aineistoja tai valmiita tunnuslukuja. Aloita tästä.

    Palauttaa aineistot strukturoituna (tunniste, julkaisija, lisenssi,
    formaatit, kyseltävyys, laatu) ja valmiit seuraavat kutsut. Jos
    instanssi tuntee hakua vastaavan tunnusluvun, se tulee ``indicators``-
    kenttään — silloin arvo saadaan suoraan ilman aineiston tutkimista.

    Args:
        query: Hakusanat suomeksi tai englanniksi ("väkiluku", "air quality").
            Tyhjä + region = kaikki alueen aineistot.
        region: Kunta, maakunta, hyvinvointialue tai postinumero. Tuo mukaan
            myös koko maan aineistot joissa alue on dimensioarvo
            (``coverage="nationwide"``).
        source: Lähde, esim. "statfin", "sotkanet", "hri.fi".
        format: Formaatti, esim. "CSV", "WFS", "PXWEB".
        organization: Julkaisijan nimi tai sen osa.
        access_level: "open", "registration" tai "restricted".
        limit: Tulosten määrä (oletus 10, katto 100).
        offset: Sivutus.
    """
    limit = clamp(limit, MAX_SEARCH_LIMIT)
    conn = _server._get_conn(ctx)
    query = query.strip()
    region = region.strip()
    notes: list[str] = []

    area_ref: AreaRef | None = None
    region_names: list[str] | None = None
    if region:
        match = resolve_area(conn, region)
        if match:
            area_ref = AreaRef(**match.to_dict())
            if match.note:
                notes.append(match.note)
        region_names = _resolve_region(conn, region) or (
            [match.area.name_fi] if match else [region]
        )

    indicators: list[IndicatorHit] = []
    if query:
        for contribution in await extensions.call_all(
            "find_data.indicators", conn=conn, query=query, region=area_ref
        ):
            indicators.extend(IndicatorHit(**i) for i in contribution)

    if query:
        expanded = await _server._expand_query(query, ctx)
        rows = search_datasets(
            conn,
            query,
            limit=limit,
            offset=offset,
            source=source,
            fmt=format,
            organization=organization,
            access_level=access_level,
            expanded_query=expanded,
            region_names=region_names,
        )
    elif region_names:
        sql, params = _build_region_query(region_names, None, limit + offset)
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()][offset:]
    else:
        return respond(
            FindDataResult(
                notes=["Anna query tai region."],
                next_actions=[NextAction(tool="find_data", args={"query": "väkiluku"})],
            ),
            "Anna hakusana (query) tai alue (region).",
        )

    ids = [r["id"] for r in rows]
    formats = _batch_formats(conn, ids)
    quality = _batch_quality_scores(conn, ids)
    health = _batch_health_status(conn, ids)
    hits = [
        _hit(
            r, formats.get(r["id"], set()), quality.get(r["id"]), health.get(r["id"]), region_names
        )
        for r in rows
    ]

    if not hits and not indicators:
        record_zero_result(query or region)

    next_actions: list[NextAction] = []
    for ind in indicators[:1]:
        if ind.tool:
            args: dict[str, Any] = {"indicator": ind.id}
            if area_ref:
                args["areas"] = [area_ref.code if area_ref.level == "kunta" else area_ref.name_fi]
            next_actions.append(
                NextAction(tool=ind.tool, args=args, why="Valmis tunnusluku: arvo suoraan")
            )
    if hits:
        top = hits[0]
        next_actions.append(
            NextAction(
                tool="inspect_dataset",
                args={"dataset_id": top.id},
                why="Rakenne, lisenssi ja kyselyohje",
            )
        )
        if top.queryable:
            next_actions.append(
                NextAction(
                    tool="query_source",
                    args={"dataset_id": top.id},
                    why="Esikatsele sisältö; ilman suodattimia palauttaa dimensiot",
                )
            )
    if region_names and hits:
        own = sum(1 for h in hits if h.coverage == "own")
        notes.append(
            f"Alue '{region}': {own} aineistoa koskee aluetta, {len(hits) - own} on koko "
            "maan aineistoja joissa alue on dimensioarvo."
        )

    payload = FindDataResult(
        query=query,
        count=len(hits),
        offset=offset,
        region=area_ref,
        indicators=indicators,
        results=hits,
        notes=notes,
        next_actions=next_actions,
    )
    summary = [f"{len(hits)} aineistoa haulle '{query or region}'."]
    if indicators:
        summary.insert(0, f"Tunnusluku: {indicators[0].name} ({indicators[0].id}).")
    for h in hits[:3]:
        summary.append(f"- {h.title} [{h.id}] — {h.organization}")
    return respond(payload, summary)
