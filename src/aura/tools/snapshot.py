"""area_snapshot — alue: mikä se on, mihin se kuuluu, ja mitä siitä on dataa.

Korvaa ``area_profile``n ja ``lookup_municipality``n. Vanha profiili laski
aineistoja, ei tunnuslukuja: "mikä on Kuopion väkiluku" ei saanut siitä
vastausta. Avoin Aura on metatietokatalogi, joten sen oma vastaus on alueen
tunnistus, hierarkia ja datatarjonta; instanssi joka tuntee tunnusluvut
(koukku ``area_snapshot.key_figures``) lisää ne ``key_figures``-kenttään.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.tools.tool import ToolResult
from pydantic import Field

import aura.server as _server
from aura import extensions
from aura.areas import members, parents, resolve_area
from aura.responses import AreaRef, Envelope, Model, NextAction, fail, respond, schema_of
from aura.server import mcp
from aura.tools.area import _compute_area_stats
from aura.tools.search import _build_region_query, _resolve_region

_MAX_EXAMPLES = 5
_MAX_MEMBERS = 50


class ThemeCount(Model):
    theme: str
    count: int
    examples: list[dict[str, str]] = Field(default_factory=list)


class KeyFigure(Model):
    indicator: str
    name: str
    value: float | int | None = None
    unit: str | None = None
    period: str | None = None
    source: str | None = None
    source_url: str | None = None
    license: str | None = None


class AreaSnapshotResult(Envelope):
    area: AreaRef | None = None
    parents: dict[str, AreaRef] = Field(default_factory=dict)
    municipalities: list[AreaRef] = Field(
        default_factory=list, description="Alueen kunnat (ei kunnalle itselleen)"
    )
    codes: dict[str, Any] = Field(
        default_factory=dict, description="Tunnisteet muissa järjestelmissä (Sotkanet, bbox)"
    )
    key_figures: list[KeyFigure] = Field(
        default_factory=list, description="Tunnusluvut (vain jos instanssi tarjoaa)"
    )
    datasets_local: int = Field(default=0, description="Aineistot jotka koskevat aluetta")
    datasets_nationwide: int = Field(
        default=0, description="Koko maan aineistot joissa alue on dimensioarvo"
    )
    themes: list[ThemeCount] = Field(default_factory=list)
    quality_avg: float | None = None
    gaps: list[str] = Field(default_factory=list)


def _number(value: float | int | None) -> str:
    """Luku ilman turhaa desimaalia: 121832.0 → "121 832", 42.1 → "42,1"."""
    if value is None:
        return ".."
    if float(value).is_integer():
        return f"{value:,.0f}".replace(",", " ")
    return f"{value}".replace(".", ",")


def _ref(area: Any) -> AreaRef:
    return AreaRef(**area.to_dict())


def _codes(conn: Any, code: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT sotkanet_id, min_x, min_y, max_x, max_y FROM ref_municipalities WHERE code = ?",
        (code,),
    ).fetchone()
    out: dict[str, Any] = {"kuntakoodi": code, "statfin": f"KU{code}"}
    if row:
        if row[0] is not None:
            out["sotkanet_region"] = row[0]
        if row[1] is not None:
            out["bbox_epsg3067"] = f"{row[1]:.0f},{row[2]:.0f},{row[3]:.0f},{row[4]:.0f}"
    return out


@mcp.tool(tags={"public"}, output_schema=schema_of(AreaSnapshotResult))
async def area_snapshot(region: str, ctx: Context | None = None) -> ToolResult:
    """Alueen tunnistus, hierarkia, tunnukset ja datatarjonta aiheittain.

    Hyväksyy kunnan, maakunnan, hyvinvointialueen, seutukunnan tai
    postinumeron nimellä tai koodilla ("Kuopio", "297", "KU297",
    "Pohjois-Savo", "70100"). Lakkautettu kunta tulkitaan seuraajakseen.

    Args:
        region: Alueen nimi tai koodi.
    """
    conn = _server._get_conn(ctx)
    match = resolve_area(conn, region)
    if match is None:
        return fail(
            AreaSnapshotResult,
            "unknown_area",
            f"Aluetta '{region}' ei tunnistettu.",
            hint="Kokeile kunnan, maakunnan tai hyvinvointialueen nimeä tai kuntakoodia.",
            suggested_call=NextAction(tool="find_data", args={"query": region}),
        )
    area = match.area
    notes = [match.note] if match.note else []
    payload = AreaSnapshotResult(area=AreaRef(**match.to_dict()), notes=notes)

    if area.level == "kunta":
        payload.parents = {lvl: _ref(a) for lvl, a in parents(conn, area.code).items()}
        payload.codes = _codes(conn, area.code)
    elif area.level == "postinumero":
        kunta_row = conn.execute(
            "SELECT municipality_code FROM ref_postal_codes WHERE code = ?", (area.code,)
        ).fetchone()
        if kunta_row and kunta_row[0]:
            kunta = resolve_area(conn, kunta_row[0])
            if kunta:
                payload.parents = {"kunta": _ref(kunta.area)}
    else:
        munis = members(conn, area)
        payload.municipalities = [_ref(m) for m in munis[:_MAX_MEMBERS]]
        if len(munis) > _MAX_MEMBERS:
            payload.notes.append(f"Näytetään {_MAX_MEMBERS}/{len(munis)} kuntaa.")

    for contribution in await extensions.call_all(
        "area_snapshot.key_figures", conn=conn, area=area
    ):
        payload.key_figures.extend(KeyFigure(**k) for k in contribution)

    names = _resolve_region(conn, area.name_fi) or [area.name_fi]
    if area.level == "postinumero" and payload.parents.get("kunta"):
        names = [payload.parents["kunta"].name_fi]
    sql, params = _build_region_query(names, None, 500)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    local = [r for r in rows if not r.get("on_aluetaso")]
    payload.datasets_local = len(local)
    payload.datasets_nationwide = len(rows) - len(local)
    if local:
        stats = _compute_area_stats(conn, local)
        payload.quality_avg = round(stats["avg_quality"], 1)
        payload.gaps = list(stats["gaps"])
        for theme, items in stats["categorized"].items():
            payload.themes.append(
                ThemeCount(
                    theme=theme,
                    count=len(items),
                    examples=[
                        {"id": d["id"], "title": d.get("title_fi") or d.get("title") or ""}
                        for d in items[:_MAX_EXAMPLES]
                    ],
                )
            )
        payload.themes.sort(key=lambda t: -t.count)
    if payload.gaps and payload.datasets_nationwide:
        payload.notes.append(
            "Puutteet koskevat vain alueelle rajattuja aineistoja; koko maan aineistoissa "
            "alue voi olla dimensiona."
        )
    payload.next_actions = [
        NextAction(
            tool="find_data",
            args={"region": area.name_fi, "query": "<aihe>"},
            why="Alueen aineistot aiheesta",
        ),
    ]
    if not payload.key_figures:
        payload.next_actions.insert(
            0,
            NextAction(
                tool="find_data",
                args={"query": "väkiluku", "region": area.name_fi},
                why="Tunnusluku kysytään lähdetaulusta (query_source)",
            ),
        )

    level_fi = {
        "kunta": "kunta",
        "maakunta": "maakunta",
        "hyvinvointialue": "hyvinvointialue",
        "postinumero": "postinumeroalue",
    }.get(area.level, area.level)
    summary = [f"{area.name_fi} ({level_fi} {area.code})"]
    if match.note:
        summary[0] += f" — {match.note.split('. ')[0]}."
    if payload.parents:
        shown = ("maakunta", "hyvinvointialue", "seutukunta", "kunta")
        summary.append(
            ", ".join(f"{k}: {v.name_fi}" for k, v in payload.parents.items() if k in shown)
        )
    for k in payload.key_figures[:2]:
        summary.append(f"{k.name}: {_number(k.value)} {k.unit or ''} ({k.period})".strip())
    summary.append(
        f"{payload.datasets_local} alueen omaa aineistoa, {payload.datasets_nationwide} koko maan."
    )
    return respond(payload, summary)
