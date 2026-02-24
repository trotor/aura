"""Alueprofiilityökalut: area_profile, compare_municipalities."""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.constants import MACHINE_READABLE_FORMATS, format_date, parse_json_list
from aura.server import mcp
from aura.tools.search import (
    _batch_formats,
    _batch_quality_scores,
    _build_region_query,
    _resolve_region,
)

_QUALITY_DIMENSIONS = ("completeness", "timeliness", "accessibility", "documentation")
_DIM_LABELS = {
    "completeness": "Täydellisyys",
    "timeliness": "Ajantasaisuus",
    "accessibility": "Saavutettavuus",
    "documentation": "Dokumentointi",
}


def _batch_dimension_scores(
    conn: sqlite3.Connection, dataset_ids: list[str],
) -> dict[str, dict[str, float]]:
    """Hae laatudimensioiden pisteet dataseteille yhdellä kyselyllä.

    Returns:
        {dataset_id: {dimension: score, ...}, ...}
    """
    if not dataset_ids:
        return {}
    placeholders = ",".join("?" for _ in dataset_ids)
    rows = conn.execute(
        f"""
        SELECT dataset_id, dimension, score
        FROM quality_scores
        WHERE dataset_id IN ({placeholders})
          AND dimension IN ('completeness', 'timeliness', 'accessibility', 'documentation')
        """,
        dataset_ids,
    ).fetchall()
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        result.setdefault(row["dataset_id"], {})[row["dimension"]] = row["score"]
    return result

# Regex: vuosiluvut (2000–2099), kvartaalit, vuodenajat
_TEMPORAL_RE = re.compile(
    r"\b(20\d{2}|q[1-4]|kevät|kesä|syksy|talvi|vuosi|kuukausi)\b", re.IGNORECASE,
)
# Regex: välimerkit ja ylimääräinen whitespace
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

# Aihekategoriat: (label, source-prefixes, keyword-patterns)
_TOPIC_CATEGORIES: list[tuple[str, set[str], set[str]]] = [
    ("Tilastot", {"statfin", "luke"}, {"väestö", "tilasto", "talous", "työ"}),
    ("Paikkatieto", {"kunnat", "gtk", "metsakeskus", "taustakartat"}, {
        "kartta", "WFS", "WMS", "paikkatieto", "kiinteistö", "kaava",
    }),
    ("Liikenne", {"digitraffic", "traficom"}, {
        "liikenne", "tie", "rata", "joukkoliikenne", "pysäköinti",
    }),
    ("Ympäristö", {"syke", "fmi"}, {
        "ympäristö", "ilma", "sää", "vesi", "luonto", "metsä",
    }),
    ("Hallinto", {"avoindata.fi", "hri.fi"}, {
        "hallinto", "päätös", "budjetti", "talousarvio", "organisaatio",
    }),
]

# Aihepiirit joita kunnalta odotetaan
_EXPECTED_TOPICS: list[tuple[str, list[str]]] = [
    ("Väestö", ["väestö", "asukas", "muutto"]),
    ("Talous", ["talous", "budjetti", "talousarvio", "vero"]),
    ("Kaavoitus", ["kaava", "asemakaava", "yleiskaava", "rakennuslupa"]),
    ("Liikenne", ["liikenne", "pysäköinti", "joukkoliikenne", "pyörä"]),
    ("Ympäristö", ["ympäristö", "ilmanlaatu", "melu", "energia"]),
    ("Koulutus", ["koulu", "oppilas", "päiväkoti", "varhaiskasvatus"]),
    ("Sosiaali- ja terveyspalvelut", ["sote", "terveys", "sosiaali", "hyvinvointi"]),
]


def _categorize_datasets(
    datasets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Ryhmittele datasetit aihekategorioihin."""
    categorized: dict[str, list[dict[str, Any]]] = {}
    uncategorized: list[dict[str, Any]] = []

    for ds in datasets:
        source = ds.get("source", "")
        title = (ds.get("title_fi") or ds.get("title") or "").lower()
        keywords_raw = parse_json_list(ds.get("keywords_fi", "[]"))
        keywords_lower = {k.lower() for k in keywords_raw}

        matched = False
        for label, sources, kw_patterns in _TOPIC_CATEGORIES:
            if source in sources:
                categorized.setdefault(label, []).append(ds)
                matched = True
                break
            for pattern in kw_patterns:
                if pattern.lower() in title or pattern.lower() in keywords_lower:
                    categorized.setdefault(label, []).append(ds)
                    matched = True
                    break
            if matched:
                break

        if not matched:
            uncategorized.append(ds)

    if uncategorized:
        categorized["Muu"] = uncategorized

    return categorized


def _detect_gaps(datasets: list[dict[str, Any]]) -> list[str]:
    """Tunnista puuttuvat aihepiirit vertaamalla odotettuihin."""
    all_titles = " ".join(
        (ds.get("title_fi") or ds.get("title") or "").lower()
        for ds in datasets
    )
    all_keywords: set[str] = set()
    for ds in datasets:
        kw = parse_json_list(ds.get("keywords_fi", "[]"))
        all_keywords.update(k.lower() for k in kw)

    corpus = all_titles + " " + " ".join(all_keywords)

    gaps: list[str] = []
    for topic_label, patterns in _EXPECTED_TOPICS:
        if not any(p in corpus for p in patterns):
            gaps.append(topic_label)

    return gaps


def _compute_freshness(datasets: list[dict[str, Any]]) -> tuple[int, int]:
    """Laske tuoreiden datasettien osuus.

    Returns:
        (fresh_count, total_with_date) — tuoreet (< 1v) ja ne joilla on päivämäärä.
    """
    now = datetime.now(tz=UTC)
    fresh = 0
    with_date = 0

    for ds in datasets:
        modified = ds.get("metadata_modified", "")
        if not modified:
            continue
        with_date += 1
        try:
            mod_dt = datetime.fromisoformat(modified).replace(tzinfo=UTC)
            if (now - mod_dt).days < 365:
                fresh += 1
        except (ValueError, TypeError):
            pass

    return fresh, with_date


def _compute_area_stats(
    conn: sqlite3.Connection,
    datasets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Laske alueen tilastot dataseteistä.

    Returns:
        dict with keys: total, avg_quality, mr_pct, fresh_pct, gaps,
        categorized, quality_scores, format_map, dimension_avgs, org_count
    """
    ds_ids = [d["id"] for d in datasets]

    # Batch-kyselyt
    quality_scores = _batch_quality_scores(conn, ds_ids)
    format_map = _batch_formats(conn, ds_ids)
    dim_scores = _batch_dimension_scores(conn, ds_ids)

    # Kategorisoi
    categorized = _categorize_datasets(datasets)

    # Tilastot
    total = len(datasets)
    avg_quality = (
        sum(quality_scores.values()) / len(quality_scores)
        if quality_scores
        else 0.0
    )

    # Dimensioiden keskiarvot
    dimension_avgs: dict[str, float] = {}
    for dim in _QUALITY_DIMENSIONS:
        values = [
            ds_dims[dim]
            for ds_dims in dim_scores.values()
            if dim in ds_dims
        ]
        dimension_avgs[dim] = sum(values) / len(values) if values else 0.0

    # Organisaatioiden lukumäärä
    org_count = len({
        d.get("organization_title") or d.get("organization_name", "")
        for d in datasets
        if d.get("organization_title") or d.get("organization_name")
    })

    # Koneluettavuus
    machine_readable_count = 0
    for ds_id in ds_ids:
        formats = format_map.get(ds_id, set())
        if formats & MACHINE_READABLE_FORMATS:
            machine_readable_count += 1
    mr_pct = round(100 * machine_readable_count / total) if total else 0

    # Tuoreus
    fresh_count, with_date = _compute_freshness(datasets)
    fresh_pct = round(100 * fresh_count / with_date) if with_date else 0

    # Puutteet
    gaps = _detect_gaps(datasets)

    return {
        "total": total,
        "avg_quality": avg_quality,
        "mr_pct": mr_pct,
        "fresh_pct": fresh_pct,
        "gaps": gaps,
        "categorized": categorized,
        "quality_scores": quality_scores,
        "format_map": format_map,
        "dimension_avgs": dimension_avgs,
        "org_count": org_count,
    }


@mcp.tool()
def area_profile(region: str, ctx: Context | None = None) -> str:
    """Koosta alueprofiili: löytyneet datasetit ryhmitelty aiheittain,
    datan laatu, formaatit ja puutteet.

    Args:
        region: Alue (kunnan nimi, maakunta tai postinumero)
    """
    conn = _server._get_conn(ctx)

    # 1. Resolvoi alue
    region_clean = region.strip()
    municipality_names = _resolve_region(conn, region_clean)
    if not municipality_names:
        municipality_names = [region_clean]

    # Näyttönimi: yksittäinen kunta tai alkuperäinen aluenimi
    display_name = (
        municipality_names[0]
        if len(municipality_names) == 1
        else region_clean
    )

    # 2. Hae datasetit (ilman FTS, limit=500)
    sql, params = _build_region_query(municipality_names, fts_query=None, limit=500)
    rows = conn.execute(sql, params).fetchall()
    datasets = [dict(row) for row in rows]

    if not datasets:
        return (
            f"Alueelle '{display_name}' ei löytynyt datasettejä. "
            "Kokeile laajempaa aluetta tai tarkista alueen nimi."
        )

    # 3. Laske tilastot
    stats = _compute_area_stats(conn, datasets)
    total = stats["total"]
    avg_quality = stats["avg_quality"]
    mr_pct = stats["mr_pct"]
    fresh_pct = stats["fresh_pct"]
    gaps = stats["gaps"]
    categorized = stats["categorized"]
    quality_scores = stats["quality_scores"]
    format_map = stats["format_map"]

    # 7. Muotoile raportti
    parts: list[str] = []
    parts.append(f"# {display_name} — avoin data\n")
    parts.append(
        f"**{total} datasettiä** | "
        f"Laatu: {avg_quality:.0f}/100 | "
        f"Koneluettavia: {mr_pct}%\n"
    )

    # Aiheittain
    parts.append("## Aiheittain\n")
    for category, ds_list in categorized.items():
        parts.append(f"### {category} ({len(ds_list)})\n")
        # Näytä max 10 per kategoria
        for ds in ds_list[:10]:
            title = ds.get("title_fi") or ds.get("title") or ds.get("name", "")
            source = ds.get("source", "")
            modified = format_date(ds.get("metadata_modified"))
            ds_id = ds["id"]
            qs = quality_scores.get(ds_id, 0)
            fmts = format_map.get(ds_id, set())
            fmt_str = "/".join(sorted(fmts)[:3]) if fmts else "—"

            line = f"- {title} ({source})"
            if modified:
                line += f" — {modified}"
            if qs > 0:
                line += f" [{qs:.0f}p]"
            line += f" [{fmt_str}]"
            parts.append(line)

        if len(ds_list) > 10:
            parts.append(f"  ... ja {len(ds_list) - 10} muuta")
        parts.append("")

    # Yhteenveto
    parts.append("## Yhteenveto\n")
    parts.append("| Mittari | Arvo |")
    parts.append("|---------|------|")
    parts.append(f"| Datasettejä | {total} |")
    parts.append(f"| Koneluettavia | {mr_pct}% |")
    parts.append(f"| Tuoreita (< 1v) | {fresh_pct}% |")
    parts.append(f"| Laatu (ka.) | {avg_quality:.0f}/100 |")
    parts.append("")

    # Puutteet
    if gaps:
        parts.append("## Puutteet\n")
        for gap in gaps:
            parts.append(f"- Ei avointa {gap.lower()}-dataa")
        parts.append("")

    return "\n".join(parts)


def _normalize_title(ds: dict[str, Any], municipality_names: list[str] | None = None) -> str:
    """Normalisoi datasetin otsikko kuntien välistä vertailua varten.

    Poistaa kuntanimet, vuosiluvut ja välimerkit jotta
    "Tampere väestödata 2024" ja "Turku väestödata 2025"
    tunnistetaan samaksi datasetiksi.
    """
    title = (ds.get("title_fi") or ds.get("title") or ds.get("name", "")).lower()
    # Poista kuntanimet
    if municipality_names:
        for name in municipality_names:
            title = title.replace(name.lower(), "")
    # Poista vuosiluvut ja vuodenajat
    title = _TEMPORAL_RE.sub("", title)
    # Poista välimerkit
    title = _PUNCT_RE.sub(" ", title)
    # Normalisoi whitespace
    return " ".join(title.split())


def _filter_by_theme(
    datasets: list[dict[str, Any]], theme: str
) -> list[dict[str, Any]]:
    """Suodata datasetit teeman mukaan.

    Käyttää domain-sanastoja laajentamaan teemaa, jotta esim.
    "liikenne" löytää myös "joukkoliikenne", "tieliikenne" jne.
    """
    from aura.vocabularies import expand_with_vocabularies

    theme_lower = theme.lower()
    # Laajenna teema domain-sanastoilla
    expanded = expand_with_vocabularies(theme)
    search_terms = {theme_lower} | {t.lower() for t in expanded}

    result: list[dict[str, Any]] = []
    for ds in datasets:
        title = (ds.get("title_fi") or ds.get("title") or "").lower()
        kw_raw = parse_json_list(ds.get("keywords_fi", "[]"))
        keywords_lower = {k.lower() for k in kw_raw}
        # Tarkista löytyykö mikään hakutermi otsikosta tai avainsanoista
        if any(t in title for t in search_terms) or (search_terms & keywords_lower):
            result.append(ds)
    return result


@mcp.tool()
def compare_municipalities(
    municipalities: list[str],
    theme: str = "",
    ctx: Context | None = None,
) -> str:
    """Vertaile kuntien datatarjontaa ja avoimuutta.

    Args:
        municipalities: Kunnat (esim. ["Tampere", "Turku", "Oulu"]), 2–5 kpl
        theme: Valinnainen teemarajaus (esim. "liikenne", "väestö")
    """
    if len(municipalities) < 2:
        return "Anna vähintään 2 kuntaa vertailtavaksi."
    if len(municipalities) > 5:
        return "Vertaile korkeintaan 5 kuntaa kerrallaan."

    conn = _server._get_conn(ctx)

    # Kerää data kunnittain
    muni_data: dict[str, dict[str, Any]] = {}
    muni_datasets: dict[str, list[dict[str, Any]]] = {}

    for muni in municipalities:
        muni_clean = muni.strip()
        names = _resolve_region(conn, muni_clean)
        if not names:
            names = [muni_clean]
        display = names[0] if len(names) == 1 else muni_clean

        sql, params = _build_region_query(names, fts_query=None, limit=500)
        rows = conn.execute(sql, params).fetchall()
        datasets = [dict(row) for row in rows]

        if theme:
            datasets = _filter_by_theme(datasets, theme)

        if datasets:
            stats = _compute_area_stats(conn, datasets)
        else:
            stats = {
                "total": 0,
                "avg_quality": 0.0,
                "mr_pct": 0,
                "fresh_pct": 0,
                "gaps": [],
                "categorized": {},
                "quality_scores": {},
                "format_map": {},
                "dimension_avgs": {d: 0.0 for d in _QUALITY_DIMENSIONS},
                "org_count": 0,
            }

        muni_data[display] = stats
        muni_datasets[display] = datasets

    names_list = list(muni_data.keys())

    # Muotoile vertailutaulukko
    parts: list[str] = []
    theme_suffix = f" ({theme})" if theme else ""
    parts.append(f"# Kuntavertailu: {', '.join(names_list)}{theme_suffix}\n")

    # Taulukko
    header = "| | " + " | ".join(names_list) + " |"
    sep = "|---|" + "|".join("------" for _ in names_list) + "|"
    parts.append(header)
    parts.append(sep)

    def _row(label: str, values: list[str]) -> str:
        return f"| {label} | " + " | ".join(values) + " |"

    parts.append(_row("Datasettejä", [str(muni_data[n]["total"]) for n in names_list]))
    parts.append(_row("Organisaatioita", [str(muni_data[n]["org_count"]) for n in names_list]))
    parts.append(_row("Koneluettavia", [f"{muni_data[n]['mr_pct']}%" for n in names_list]))
    parts.append(_row("Tuoreita (< 1v)", [f"{muni_data[n]['fresh_pct']}%" for n in names_list]))
    parts.append(_row("Laatu (ka.)", [
        f"{muni_data[n]['avg_quality']:.0f}/100" for n in names_list
    ]))

    # Dimensiokohtaiset pisteet
    for dim in _QUALITY_DIMENSIONS:
        label = _DIM_LABELS[dim]
        parts.append(_row(f"  {label}", [
            f"{muni_data[n]['dimension_avgs'].get(dim, 0):.0f}" for n in names_list
        ]))
    parts.append("")

    # Erojen tunnistus: mitä toisella on mutta toisella ei
    all_muni_names = list(names_list)  # kuntanimet normalisointia varten
    title_sets: dict[str, set[str]] = {}
    title_to_display: dict[str, dict[str, str]] = {}  # norm_title -> {muni: display_title}
    for name in names_list:
        titles: set[str] = set()
        for ds in muni_datasets[name]:
            norm = _normalize_title(ds, municipality_names=all_muni_names)
            if norm:
                titles.add(norm)
                title_to_display.setdefault(norm, {})[name] = (
                    ds.get("title_fi") or ds.get("title") or ds.get("name", "")
                )
        title_sets[name] = titles

    has_diffs = False
    for i, name_a in enumerate(names_list):
        for name_b in names_list[i + 1 :]:
            only_a = title_sets[name_a] - title_sets[name_b]
            only_b = title_sets[name_b] - title_sets[name_a]

            if only_b:
                if not has_diffs:
                    parts.append("## Erot\n")
                    has_diffs = True
                parts.append(f"### {name_b}lla on mutta {name_a}lla ei:\n")
                for t in sorted(only_b)[:5]:
                    display_t = title_to_display.get(t, {}).get(name_b, t)
                    parts.append(f"- {display_t}")
                if len(only_b) > 5:
                    parts.append(f"  ... ja {len(only_b) - 5} muuta")
                parts.append("")

            if only_a:
                if not has_diffs:
                    parts.append("## Erot\n")
                    has_diffs = True
                parts.append(f"### {name_a}lla on mutta {name_b}lla ei:\n")
                for t in sorted(only_a)[:5]:
                    display_t = title_to_display.get(t, {}).get(name_a, t)
                    parts.append(f"- {display_t}")
                if len(only_a) > 5:
                    parts.append(f"  ... ja {len(only_a) - 5} muuta")
                parts.append("")

    if not has_diffs:
        parts.append("Kunnilla on samat datasetit.\n")

    return "\n".join(parts)
