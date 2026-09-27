"""Laadunvalvonnan työkalut: laatuprofiili julkaisijoille ja ylläpitäjille.

Datan käyttäjä kysyy "mikä on X". Julkaisija kysyy "missä kuvailuni on
puutteellinen ja toimivatko rajapintani". Nämä ovat eri käyttäjiä, joten ne
saavat eri pinnan: laatutyökalut julkisessa profiilissa maksaisivat kontekstia
jokaiselta datan käyttäjältä, ja julkisessa profiilissa ne eivät näkyisi
etäkäyttäjälle lainkaan (profiilia ei voi valita etäpalvelun asetuksista).

Laatuprofiili tarjoillaan omasta polustaan (``/mcp/laatu``) ja paikallisesti
``AURA_TOOL_PROFILE=laatu``. Kaikki sen työkalut ovat lukuoperaatioita, joten
profiili toimii myös read-only-instanssissa. Metatiedon laatupisteet lasketaan
katalogin omista kentistä; saatavuus luetaan tallennetuista tarkistuksista,
ja vastaus kertoo niiden iän — tarkistuksen ajaminen (``health_check``) on
ylläpitotyö eikä kuulu tähän profiiliin.

Kaikki kolme rajautuvat lähteeseen tai julkaisijaan (osa nimestä riittää),
jotta julkaisija näkee omat aineistonsa ilman koko katalogin läpikäyntiä.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastmcp import Context
from fastmcp.tools import ToolResult
from pydantic import Field

import aura.server as _server
from aura.limits import MAX_LIST_LIMIT, clamp
from aura.responses import Envelope, Model, NextAction, fail, respond, schema_of
from aura.server import QUALITY_TAG, mcp
from aura.tools.quality import DIMENSION_LABELS

#: Saatavuustarkistus jota vanhempi on vanhentunut raportoinnin kannalta.
STALE_HEALTH_DAYS = 30

_DIMENSIONS = ("overall", *DIMENSION_LABELS)


def _filters(source: str, organization: str, alias: str = "d") -> tuple[str, list[str]]:
    parts: list[str] = []
    params: list[str] = []
    if source:
        parts.append(f"{alias}.source = ?")
        params.append(source)
    if organization:
        parts.append(f"{alias}.organization_title LIKE ?")
        params.append(f"%{organization}%")
    return (" AND " + " AND ".join(parts)) if parts else "", params


def _scope(source: str, organization: str) -> dict[str, str]:
    return {k: v for k, v in (("source", source), ("organization", organization)) if v}


class ScoredDataset(Model):
    id: str
    title: str = ""
    organization: str = ""
    source: str = ""
    score: float


class QualitySummary(Envelope):
    scope: dict[str, str] = Field(default_factory=dict)
    datasets: int = 0
    average: dict[str, float] = Field(
        default_factory=dict, description="Keskiarvo 0–100 dimensioittain (overall = kokonais)"
    )
    median: float | None = None
    distribution: dict[str, int] = Field(
        default_factory=dict, description="Kokonaispisteiden jakauma: 0-29, 30-59, 60-79, 80-100"
    )
    weakest: list[ScoredDataset] = Field(default_factory=list)
    strongest: list[ScoredDataset] = Field(default_factory=list)


@mcp.tool(tags={QUALITY_TAG}, output_schema=schema_of(QualitySummary))
def quality_summary(
    source: str = "",
    organization: str = "",
    limit: int = 5,
    ctx: Context | None = None,
) -> ToolResult:
    """Metatiedon laatu yhteenvetona: keskiarvot, jakauma, heikoimmat ja parhaat.

    Args:
        source: Rajaa lähteeseen, esim. "avoindata.fi", "hri.fi".
        organization: Rajaa julkaisijaan (osa nimestä riittää), esim. "Espoo".
        limit: Heikoimpien ja parhaiden määrä (oletus 5).
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    conn = _server._get_conn(ctx)
    cond, params = _filters(source, organization)
    rows = conn.execute(
        f"SELECT q.dataset_id, q.dimension, q.score, COALESCE(d.title_fi, d.title) AS title,"
        f" d.organization_title AS org, d.source FROM quality_scores q"
        f" JOIN datasets d ON d.id = q.dataset_id WHERE 1=1{cond}",
        params,
    ).fetchall()
    scope = _scope(source, organization)
    if not rows:
        return fail(
            QualitySummary,
            "no_scores",
            "Rajaukselle ei löytynyt laatupisteitä.",
            hint="Tarkista lähteen tai julkaisijan nimi find_data-työkalulla.",
            suggested_call=NextAction(
                tool="find_data",
                args={"organization": organization} if organization else {"query": source},
            ),
            scope=scope,
        )
    by_dim: dict[str, list[float]] = {}
    overall: list[tuple[float, Any]] = []
    for r in rows:
        by_dim.setdefault(r["dimension"], []).append(float(r["score"]))
        if r["dimension"] == "overall":
            overall.append((float(r["score"]), r))
    overall.sort(key=lambda x: x[0])
    scores = [s for s, _ in overall]
    buckets = {"0-29": 0, "30-59": 0, "60-79": 0, "80-100": 0}
    for s in scores:
        key = "0-29" if s < 30 else "30-59" if s < 60 else "60-79" if s < 80 else "80-100"
        buckets[key] += 1

    def _ds(item: tuple[float, Any]) -> ScoredDataset:
        s, r = item
        return ScoredDataset(
            id=r["dataset_id"],
            title=r["title"] or "",
            organization=r["org"] or "",
            source=r["source"] or "",
            score=round(s, 1),
        )

    payload = QualitySummary(
        scope=scope,
        datasets=len(scores),
        average={d: round(sum(v) / len(v), 1) for d, v in by_dim.items() if d in _DIMENSIONS},
        median=round(scores[len(scores) // 2], 1) if scores else None,
        distribution=buckets,
        weakest=[_ds(x) for x in overall[:limit]],
        strongest=[_ds(x) for x in reversed(overall[-limit:])],
        next_actions=[
            NextAction(tool="metadata_gaps", args=scope, why="Mitkä kentät puuttuvat"),
            *[
                NextAction(tool="inspect_dataset", args={"dataset_id": x[1]["dataset_id"]})
                for x in overall[:1]
            ],
        ],
    )
    label = ", ".join(scope.values()) or "koko katalogi"
    avg = payload.average.get("overall")
    summary = [f"Laatu: {label} — {payload.datasets} aineistoa, keskiarvo {avg}/100."]
    summary.append("Jakauma: " + ", ".join(f"{k}: {v}" for k, v in buckets.items()))
    if payload.weakest:
        w = payload.weakest[0]
        summary.append(f"Heikoin: {w.title} [{w.id}] {w.score}/100")
    return respond(payload, summary)


class GapDataset(Model):
    id: str
    title: str = ""
    organization: str = ""
    source: str = ""
    missing: list[str] = Field(default_factory=list)


class MetadataGaps(Envelope):
    scope: dict[str, str] = Field(default_factory=dict)
    datasets: int = 0
    completeness_pct: float | None = Field(
        default=None, description="Kuvaus, avainsanat, päivitystiheys ja lisenssi täytetty (%)"
    )
    missing: dict[str, int] = Field(
        default_factory=dict, description="Puuttuvien kenttien määrä kentittäin"
    )
    by_source: list[dict[str, Any]] = Field(default_factory=list)
    easiest: list[GapDataset] = Field(
        default_factory=list, description="Eniten puutteita — helpoimmin parannettavat ensin"
    )


@mcp.tool(tags={QUALITY_TAG}, output_schema=schema_of(MetadataGaps))
def metadata_gaps(
    source: str = "",
    organization: str = "",
    limit: int = 10,
    ctx: Context | None = None,
) -> ToolResult:
    """Puuttuvat metatietokentät ja helpoimmin parannettavat aineistot.

    Args:
        source: Rajaa lähteeseen.
        organization: Rajaa julkaisijaan (osa nimestä riittää).
        limit: Parannusehdotusten määrä (oletus 10).
    """
    from aura.quality import analyze_metadata_gaps, suggest_improvements

    limit = clamp(limit, MAX_LIST_LIMIT)
    conn = _server._get_conn(ctx)
    report = analyze_metadata_gaps(conn, source=source, organization=organization)
    totals = report.get("totals", {})
    scope = _scope(source, organization)
    if not totals.get("total"):
        return fail(
            MetadataGaps,
            "no_datasets",
            "Rajaukselle ei löytynyt aineistoja.",
            hint="Tarkista lähteen tai julkaisijan nimi.",
            scope=scope,
        )
    suggestions = suggest_improvements(conn, source=source, limit=limit, organization=organization)
    fields = {
        "kuvaus": "missing_desc",
        "avainsanat": "missing_keywords",
        "päivitystiheys": "missing_freq",
        "lisenssi": "missing_license",
        "englanninkielinen otsikko": "missing_title_en",
        "englanninkielinen kuvaus": "missing_notes_en",
    }
    payload = MetadataGaps(
        scope=scope,
        datasets=int(totals["total"]),
        completeness_pct=totals.get("completeness_pct"),
        missing={label: int(totals.get(key, 0)) for label, key in fields.items()},
        by_source=[
            {
                "source": s["source"],
                "datasets": s["total"],
                "completeness_pct": s.get("completeness_pct"),
            }
            for s in report.get("sources", [])
        ],
        easiest=[
            GapDataset(
                id=s["id"],
                title=s["title"] or s["name"] or "",
                organization=s["org"] or "",
                source=s["source"] or "",
                missing=s["missing_fields"],
            )
            for s in suggestions
        ],
        next_actions=[
            NextAction(tool="inspect_dataset", args={"dataset_id": s["id"]})
            for s in suggestions[:1]
        ],
    )
    label = ", ".join(scope.values()) or "koko katalogi"
    top = sorted(payload.missing.items(), key=lambda kv: -kv[1])[:3]
    summary = [
        f"Metatiedon täydellisyys: {label} — {payload.completeness_pct} % "
        f"({payload.datasets} aineistoa).",
        "Eniten puuttuu: " + ", ".join(f"{k} {v}" for k, v in top),
    ]
    return respond(payload, summary)


class FailingResource(Model):
    dataset_id: str
    url: str
    status_code: int | None = None
    error: str | None = None
    checked_at: str | None = None


class AvailabilityReport(Envelope):
    scope: dict[str, str] = Field(default_factory=dict)
    resources_checked: int = 0
    available: int = 0
    available_pct: float | None = None
    last_checked: str | None = None
    stale: bool = Field(
        default=False, description=f"Viimeisin tarkistus yli {STALE_HEALTH_DAYS} vrk vanha"
    )
    median_response_ms: int | None = None
    failing: list[FailingResource] = Field(default_factory=list)


@mcp.tool(tags={QUALITY_TAG}, output_schema=schema_of(AvailabilityReport))
def availability_report(
    source: str = "",
    organization: str = "",
    limit: int = 20,
    ctx: Context | None = None,
) -> ToolResult:
    """Resurssien saatavuus tallennetuista tarkistuksista: osuus, iät, rikkinäiset linkit.

    Raportti ei aja uutta tarkistusta; se kertoo milloin viimeisin ajettiin.

    Args:
        source: Rajaa lähteeseen.
        organization: Rajaa julkaisijaan (osa nimestä riittää).
        limit: Rikkinäisten resurssien enimmäismäärä (oletus 20).
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    conn = _server._get_conn(ctx)
    cond, params = _filters(source, organization)
    scope = _scope(source, organization)
    rows = conn.execute(
        f"SELECT h.dataset_id, h.url, h.status_code, h.is_available, h.error_message,"
        f" h.checked_at, h.response_time_ms FROM resource_health h"
        f" JOIN datasets d ON d.id = h.dataset_id WHERE 1=1{cond}",
        params,
    ).fetchall()
    if not rows:
        return fail(
            AvailabilityReport,
            "no_health_data",
            "Rajaukselle ei ole tallennettuja saatavuustarkistuksia.",
            hint="Tarkistukset ajetaan ylläpidossa (aura health).",
            scope=scope,
        )
    ok = sum(1 for r in rows if r["is_available"])
    last = max((r["checked_at"] or "" for r in rows), default="")
    stale = False
    if last:
        try:
            age = datetime.now(tz=UTC) - datetime.fromisoformat(last).replace(tzinfo=UTC)
            stale = age.days > STALE_HEALTH_DAYS
        except ValueError:
            stale = False
    times = sorted(int(r["response_time_ms"]) for r in rows if r["response_time_ms"])
    failing = [
        FailingResource(
            dataset_id=r["dataset_id"],
            url=r["url"],
            status_code=r["status_code"],
            error=(r["error_message"] or None),
            checked_at=r["checked_at"],
        )
        for r in rows
        if not r["is_available"]
    ][:limit]
    notes = []
    if stale:
        notes.append(
            f"Viimeisin tarkistus {last[:10]} on yli {STALE_HEALTH_DAYS} vrk vanha; "
            "tilanne voi olla muuttunut."
        )
    payload = AvailabilityReport(
        scope=scope,
        resources_checked=len(rows),
        available=ok,
        available_pct=round(100.0 * ok / len(rows), 1),
        last_checked=last or None,
        stale=stale,
        median_response_ms=times[len(times) // 2] if times else None,
        failing=failing,
        notes=notes,
        next_actions=[
            NextAction(tool="inspect_dataset", args={"dataset_id": f.dataset_id})
            for f in failing[:1]
        ],
    )
    label = ", ".join(scope.values()) or "koko katalogi"
    summary = [
        f"Saatavuus: {label} — {ok}/{len(rows)} resurssia vastasi ({payload.available_pct} %).",
        f"Tarkistettu viimeksi {last[:10] or '—'}" + (" (vanhentunut)" if stale else "") + ".",
    ]
    if failing:
        summary.append(f"Esim. rikki: {failing[0].url[:80]}")
    return respond(payload, summary)
