"""Laatutyökalut: quality_report, quality_overview, quality_ranking, quality_gaps."""

from __future__ import annotations

import logging

from fastmcp import Context

import aura.server as _server
from aura.database import get_dataset
from aura.limits import MAX_LIST_LIMIT, clamp
from aura.quality import get_quality_scores
from aura.server import mcp

logger = logging.getLogger(__name__)

# Yhteinen vakio laatudimensioiden nimille (käytetään useassa paikassa)
DIMENSION_LABELS: dict[str, str] = {
    "completeness": "Täydellisyys",
    "timeliness": "Ajantasaisuus",
    "accessibility": "Saavutettavuus",
    "documentation": "Dokumentointi",
}


@mcp.tool()
def quality_report(
    dataset_id: str, ctx: Context | None = None
) -> str:
    """Näytä datasetin laatupisteet dimensioittain.

    Args:
        dataset_id: Datasetin ID tai nimi
    """
    conn = _server._get_conn(ctx)
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    ds_id = dataset["id"]
    quality = get_quality_scores(conn, ds_id)
    if not quality:
        # Laske lennossa
        from aura.quality import calculate_quality, save_quality_scores

        resources = [
            dict(r) for r in conn.execute(
                "SELECT * FROM resources WHERE dataset_id = ?", (ds_id,)
            ).fetchall()
        ]
        enr_row = conn.execute(
            "SELECT COUNT(DISTINCT field) FROM enrichments WHERE dataset_id = ?",
            (ds_id,),
        ).fetchone()
        enr_count = enr_row[0] if enr_row else 0
        scores = calculate_quality(dataset, resources, enr_count)

        # Tallennus on parhaan yrityksen sivuvaikutus, ei lukupolun
        # edellytys. Toimitettavassa kannassa jokainen datasetti on jo
        # pisteytetty (DISTINCT dataset_id FROM quality_scores == COUNT
        # datasets), joten tämä haara on julkisella read-only-instanssilla
        # käytännössä kuollut — mutta jos se joskus osuu (esim. juuri
        # harvestoitu datasetti), lukupolun on toimittava silti. Sama
        # perustelu kuin query_data():lla (tools/data.py): kirjoitus ei saa
        # estää lukua.
        try:
            save_quality_scores(conn, ds_id, scores)
            conn.commit()
        except Exception:
            logger.debug("Laatupisteiden tallennus epäonnistui", exc_info=True)

        # Muodosta vastaus juuri lasketuista pisteistä sen sijaan että
        # luettaisiin kanta uudelleen — read-only-kannassa yllä oleva
        # tallennus ei koskaan onnistu, joten uudelleenluku palauttaisi
        # aina None:n.
        quality = {
            dim: {"score": score, "details": details}
            for dim, (score, details) in scores.items()
        }

    if not quality:
        return "Laatupisteitä ei voitu laskea."

    title = dataset.get("title_fi") or dataset.get("title") or ds_id
    overall = quality.get("overall", {}).get("score", 0)

    parts = [f"# Laatuarvio: {title}\n"]
    parts.append(f"**Kokonaispistemäärä: {overall:.0f}/100**\n")

    for dim, label in DIMENSION_LABELS.items():
        if dim in quality:
            s = quality[dim]["score"]
            bar_len = int(s / 10)
            bar = "\u2588" * bar_len + "\u2591" * (10 - bar_len)
            parts.append(f"  {label:16s} {s:5.0f}/100 {bar}")
            details = quality[dim].get("details", {})
            if isinstance(details, dict):
                for k, v in details.items():
                    if not k.endswith("_score"):
                        parts.append(f"    {k}: {v}")

    return "\n".join(parts)


@mcp.tool()
def quality_overview(
    source: str = "",
    min_score: float = 0,
    max_results: int = 10,
    ctx: Context | None = None,
) -> str:
    """Yhteenveto laatupisteistä lähteen tai koko kannan tasolla.

    Args:
        source: Rajaa lähteeseen (tyhjä = kaikki)
        min_score: Näytä vain yli tämän pistemäärän (0-100)
        max_results: Tulosten enimmäismäärä
    """
    conn = _server._get_conn(ctx)

    if source:
        rows = conn.execute(
            """
            SELECT q.score, d.source
            FROM quality_scores q
            JOIN datasets d ON q.dataset_id = d.id
            WHERE q.dimension = 'overall' AND d.source = ?
            ORDER BY q.score DESC
            """,
            (source,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT q.score
            FROM quality_scores q
            WHERE q.dimension = 'overall'
            ORDER BY q.score DESC
            """,
        ).fetchall()

    if not rows:
        label = f"lähteestä '{source}'" if source else "tietokannasta"
        return f"Laatupisteitä ei löytynyt {label}. Aja ensin 'aura quality'."

    scores = [r["score"] for r in rows]
    total = len(scores)
    avg = sum(scores) / total
    mid = sorted(scores)[total // 2]
    over_80 = sum(1 for s in scores if s >= 80)
    under_30 = sum(1 for s in scores if s < 30)

    # Dimensiokohtaiset keskiarvot
    dims = ["completeness", "timeliness", "accessibility", "documentation"]

    label = source if source else "koko tietokanta"
    parts = [f"# Laadun yhteenveto: {label} ({total} datasettiä)\n"]
    parts.append(f"**Keskiarvo:** {avg:.0f}/100")
    parts.append(f"**Mediaani:** {mid:.0f}/100")
    parts.append(f"**Yli 80:** {over_80} ({over_80 * 100 // total}%)")
    parts.append(f"**Alle 30:** {under_30} ({under_30 * 100 // total}%)")

    parts.append("\n### Dimensiot\n")
    for dim in dims:
        if source:
            dim_rows = conn.execute(
                """
                SELECT AVG(q.score) as avg_s
                FROM quality_scores q
                JOIN datasets d ON q.dataset_id = d.id
                WHERE q.dimension = ? AND d.source = ?
                """,
                (dim, source),
            ).fetchone()
        else:
            dim_rows = conn.execute(
                "SELECT AVG(score) as avg_s FROM quality_scores WHERE dimension = ?",
                (dim,),
            ).fetchone()
        if dim_rows and dim_rows["avg_s"] is not None:
            s = dim_rows["avg_s"]
            parts.append(f"  {DIMENSION_LABELS[dim]:16s} ka. {s:.0f}/100")

    return "\n".join(parts)


@mcp.tool()
def quality_ranking(
    dimension: str = "overall",
    source: str = "",
    limit: int = 10,
    ctx: Context | None = None,
) -> str:
    """Parhaiten pisteytetyt datasetit laadun mukaan.

    Args:
        dimension: Laatudimensio: "overall", "completeness", "timeliness",
            "accessibility", "documentation"
        source: Rajaa lähteeseen (tyhjä = kaikki)
        limit: Tulosten enimmäismäärä (oletus 10)
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    conn = _server._get_conn(ctx)

    valid_dims = {
        "overall", "completeness", "timeliness",
        "accessibility", "documentation",
    }
    if dimension not in valid_dims:
        return f"Tuntematon dimensio '{dimension}'. Valitse: {', '.join(sorted(valid_dims))}"

    if source:
        rows = conn.execute(
            """
            SELECT q.dataset_id, q.score,
                   COALESCE(d.title_fi, d.title) as title,
                   d.organization_title as org
            FROM quality_scores q
            JOIN datasets d ON q.dataset_id = d.id
            WHERE q.dimension = ? AND d.source = ?
            ORDER BY q.score DESC
            LIMIT ?
            """,
            (dimension, source, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT q.dataset_id, q.score,
                   COALESCE(d.title_fi, d.title) as title,
                   d.organization_title as org
            FROM quality_scores q
            JOIN datasets d ON q.dataset_id = d.id
            WHERE q.dimension = ?
            ORDER BY q.score DESC
            LIMIT ?
            """,
            (dimension, limit),
        ).fetchall()

    if not rows:
        return "Ei laatupisteitä. Aja ensin 'aura quality'."

    dim_labels_full = {
        "overall": "Kokonaislaatu",
        **DIMENSION_LABELS,
    }
    label = dim_labels_full.get(dimension, dimension)
    parts = [f"# Parhaat datasetit: {label}\n"]

    for i, row in enumerate(rows, 1):
        title = row["title"] or row["dataset_id"]
        if len(title) > 60:
            title = title[:57] + "..."
        org = row["org"] or ""
        parts.append(f"{i:2d}. **{title}** ({row['score']:.0f}/100)")
        if org:
            parts.append(f"    {org}")

    return "\n".join(parts)


@mcp.tool()
def quality_gaps(
    source: str = "",
    limit: int = 10,
    ctx: Context | None = None,
) -> str:
    """Analysoi metatiedon puutteet ja ehdota parannuksia.

    Args:
        source: Rajaa lähteeseen (esim. "avoindata.fi")
        limit: Parannusehdotusten enimmäismäärä (oletus 10)
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    from aura.quality import analyze_metadata_gaps, suggest_improvements

    conn = _server._get_conn(ctx)
    report = analyze_metadata_gaps(conn, source=source)
    suggestions = suggest_improvements(conn, source=source, limit=limit)

    parts: list[str] = ["# Metatiedon puutteet\n"]

    # Lähdekohtainen yhteenveto
    sources = report.get("sources", [])
    if sources:
        parts.append("| Lähde | Datasettejä | Kuvaus | Avainsanat "
                      "| Päivitystiheys | Lisenssi | Täydellisyys |")
        parts.append("|-------|-------------|--------|----------"
                      "|----------------|----------|--------------|")
        for s in sources:
            total = s["total"]
            parts.append(
                f"| {s['source']} | {total} "
                f"| {s['missing_desc']} ({_pct(s['missing_desc'], total)}) "
                f"| {s['missing_keywords']} ({_pct(s['missing_keywords'], total)}) "
                f"| {s['missing_freq']} ({_pct(s['missing_freq'], total)}) "
                f"| {s['missing_license']} ({_pct(s['missing_license'], total)}) "
                f"| {s.get('completeness_pct', 0):.0f}% |"
            )

    # Kokonaistilanne
    totals = report.get("totals", {})
    total_all = totals.get("total", 0)
    if total_all > 0:
        parts.append(
            f"\n**Kokonaismetatiedon täydellisyys: "
            f"{totals.get('completeness_pct', 0):.0f}%** "
            f"({total_all} datasettiä)"
        )

        # Monikielisyys
        en_title = totals.get("missing_title_en", 0)
        en_notes = totals.get("missing_notes_en", 0)
        parts.append(
            f"\nMonikielisyys: {en_title} datasetiltä puuttuu "
            f"englanninkielinen otsikko ({_pct(en_title, total_all)}), "
            f"{en_notes} englanninkielinen kuvaus ({_pct(en_notes, total_all)})"
        )

    # Parannusehdotukset
    if suggestions:
        parts.append(f"\n## Helpoimmin parannettavat ({len(suggestions)} kpl)\n")
        for i, s in enumerate(suggestions, 1):
            title = s["title"] or s["name"]
            if len(title) > 50:
                title = title[:47] + "..."
            missing = ", ".join(s["missing_fields"])
            parts.append(f"{i}. **{title}** ({s['source']})")
            parts.append(f"   Puuttuu: {missing}")

    return "\n".join(parts)


def _pct(n: int, total: int) -> str:
    """Formatoi prosenttiluku."""
    if total == 0:
        return "0%"
    return f"{100.0 * n / total:.0f}%"
