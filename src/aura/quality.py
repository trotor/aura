"""Datasettien automaattinen laatupisteytys neljässä dimensiossa.

Dimensiot:
- completeness (25 %): metatiedon täydellisyys
- timeliness (30 %): aineiston tuoreus
- accessibility (25 %): saavutettavuus ja koneluettavuus
- documentation (20 %): dokumentointi ja rikastukset
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from aura.constants import MACHINE_READABLE_FORMATS, parse_json_list

logger = logging.getLogger(__name__)

DIMENSION_WEIGHTS = {
    "completeness": 0.25,
    "timeliness": 0.30,
    "accessibility": 0.25,
    "documentation": 0.20,
}


# --- Yksittäiset dimensiot ---


def calculate_completeness(dataset: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Metatiedon täydellisyys: kuinka moni kenttä on täytetty."""
    checks = {
        "title": bool(
            (dataset.get("title_fi") or "").strip()
            or (dataset.get("title") or "").strip()
        ),
        "description": len(
            (dataset.get("notes_fi") or dataset.get("notes") or "").strip()
        ) > 50,
        "keywords": _keyword_count(dataset) >= 3,
        "organization": bool(
            (dataset.get("organization_title") or "").strip()
        ),
        "license": bool((dataset.get("license_id") or "").strip()),
        "update_frequency": bool(
            (dataset.get("update_frequency") or "").strip()
        ),
    }
    passed = sum(checks.values())
    score = (passed / len(checks)) * 100
    return score, checks


def calculate_timeliness(dataset: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Aineiston tuoreus metadata_modified-kentän perusteella."""
    modified = (dataset.get("metadata_modified") or "").strip()
    if not modified:
        return 10.0, {"metadata_modified": None, "days_old": None}

    try:
        mod_dt = datetime.fromisoformat(modified).replace(tzinfo=UTC)
        days_old = (datetime.now(tz=UTC) - mod_dt).days
    except (ValueError, TypeError):
        logger.warning("[quality] Virheellinen metadata_modified: '%s'", modified)
        return 10.0, {"metadata_modified": modified, "parse_error": True}

    if days_old <= 30:
        score = 100.0
    elif days_old <= 90:
        score = 85.0
    elif days_old <= 365:
        score = 60.0
    elif days_old <= 730:
        score = 30.0
    else:
        score = 10.0

    return score, {"metadata_modified": modified, "days_old": days_old}


def calculate_accessibility(
    dataset: dict[str, Any],
    resources: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Saavutettavuus: access_level, resurssimäärä, formaatit."""
    details: dict[str, Any] = {}

    # Access level
    access = (dataset.get("access_level") or "open").lower()
    access_scores = {"open": 100, "registration": 50, "restricted": 20}
    access_score = access_scores.get(access, 30)
    details["access_level"] = access
    details["access_score"] = access_score

    # Resurssien lukumäärä
    num_res = len(resources) if resources else (dataset.get("num_resources") or 0)
    if num_res == 0:
        res_score = 0.0
    elif num_res == 1:
        res_score = 50.0
    elif num_res < 5:
        res_score = 80.0
    else:
        res_score = 100.0
    details["num_resources"] = num_res
    details["resource_score"] = res_score

    # Koneluettavuus
    formats = {(r.get("format") or "").upper() for r in resources}
    machine_readable = formats & {f.upper() for f in MACHINE_READABLE_FORMATS}
    if machine_readable:
        format_score = 100.0
    elif formats:
        format_score = 40.0
    else:
        format_score = 0.0
    details["formats"] = sorted(formats - {""})
    details["machine_readable"] = sorted(machine_readable)
    details["format_score"] = format_score

    # Painotettu keskiarvo
    score = access_score * 0.4 + res_score * 0.3 + format_score * 0.3
    return score, details


def calculate_documentation(
    dataset: dict[str, Any],
    enrichment_count: int,
) -> tuple[float, dict[str, Any]]:
    """Dokumentoinnin taso: monikielisyys ja rikastukset."""
    details: dict[str, Any] = {}

    # Monikielisyys
    langs = set()
    if (dataset.get("title_fi") or "").strip() or (dataset.get("notes_fi") or "").strip():
        langs.add("fi")
    if (dataset.get("title_en") or "").strip() or (dataset.get("notes_en") or "").strip():
        langs.add("en")
    if (dataset.get("title_sv") or "").strip() or (dataset.get("notes_sv") or "").strip():
        langs.add("sv")

    lang_scores = {3: 100, 2: 70, 1: 40, 0: 0}
    lang_score = lang_scores.get(len(langs), 0)
    details["languages"] = sorted(langs)
    details["language_score"] = lang_score

    # Enrichment-rikastukset
    if enrichment_count >= 5:
        enrich_score = 100.0
    elif enrichment_count >= 3:
        enrich_score = 70.0
    elif enrichment_count >= 1:
        enrich_score = 40.0
    else:
        enrich_score = 0.0
    details["enrichment_count"] = enrichment_count
    details["enrichment_score"] = enrich_score

    score = lang_score * 0.5 + enrich_score * 0.5
    return score, details


# --- Kokonaispisteytys ---


def calculate_quality(
    dataset: dict[str, Any],
    resources: list[dict[str, Any]],
    enrichment_count: int,
) -> dict[str, tuple[float, dict[str, Any]]]:
    """Laske kaikki laatudimensiot datasettille.

    Returns:
        Dict dimensio -> (pisteet, yksityiskohdat).
    """
    scores = {
        "completeness": calculate_completeness(dataset),
        "timeliness": calculate_timeliness(dataset),
        "accessibility": calculate_accessibility(dataset, resources),
        "documentation": calculate_documentation(dataset, enrichment_count),
    }

    # Kokonaispisteet
    overall = sum(
        scores[dim][0] * weight
        for dim, weight in DIMENSION_WEIGHTS.items()
    )
    overall_details = {
        dim: {"score": scores[dim][0], "weight": weight}
        for dim, weight in DIMENSION_WEIGHTS.items()
    }
    scores["overall"] = (overall, overall_details)

    return scores


# --- Tietokantaoperaatiot ---


def save_quality_scores(
    conn: sqlite3.Connection,
    dataset_id: str,
    scores: dict[str, tuple[float, dict[str, Any]]],
) -> None:
    """Tallenna laatupisteet tietokantaan."""
    now = datetime.now(tz=UTC).isoformat()
    for dimension, (score, details) in scores.items():
        conn.execute(
            """
            INSERT INTO quality_scores (dataset_id, dimension, score, details, calculated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id, dimension) DO UPDATE SET
                score=excluded.score,
                details=excluded.details,
                calculated_at=excluded.calculated_at
            """,
            (dataset_id, dimension, score, json.dumps(details, ensure_ascii=False), now),
        )


def get_quality_scores(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> dict[str, Any] | None:
    """Hae datasetin laatupisteet."""
    rows = conn.execute(
        "SELECT dimension, score, details FROM quality_scores WHERE dataset_id = ?",
        (dataset_id,),
    ).fetchall()
    if not rows:
        return None
    result: dict[str, Any] = {}
    for row in rows:
        result[row["dimension"]] = {
            "score": row["score"],
            "details": json.loads(row["details"]) if row["details"] else {},
        }
    return result


def score_all_datasets(conn: sqlite3.Connection, source: str = "") -> int:
    """Laske laatupisteet kaikille dataseteille.

    Args:
        source: Rajaa lähteeseen (tyhjä = kaikki).

    Returns:
        Pisteytettyjen datasettien lukumäärä.
    """
    if source:
        rows = conn.execute(
            "SELECT * FROM datasets WHERE source = ?", (source,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM datasets").fetchall()

    # Hae kaikki resurssit ja enrichment-luvut kerralla (vältetään N+1)
    resources_by_ds: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in conn.execute("SELECT * FROM resources").fetchall():
        resources_by_ds[r["dataset_id"]].append(dict(r))

    enr_counts: dict[str, int] = dict(conn.execute(
        "SELECT dataset_id, COUNT(DISTINCT field) FROM enrichments GROUP BY dataset_id"
    ).fetchall())

    count = 0
    for row in rows:
        dataset = dict(row)
        ds_id = dataset["id"]
        resources = resources_by_ds.get(ds_id, [])
        enrichment_count = enr_counts.get(ds_id, 0)

        scores = calculate_quality(dataset, resources, enrichment_count)
        save_quality_scores(conn, ds_id, scores)
        count += 1

    conn.commit()
    logger.info("Laatupisteet laskettu %d datasetille", count)
    return count


def analyze_metadata_gaps(
    conn: sqlite3.Connection,
    source: str = "",
) -> dict[str, Any]:
    """Analysoi metatiedon puutteet lähteittäin.

    Returns:
        Dict jossa lähdekohtaiset tilastot ja parannusehdotukset.
    """
    where = "WHERE d.source = ?" if source else ""
    params: list[str] = [source] if source else []

    # Perustilastot
    rows = conn.execute(
        f"""
        SELECT
            d.source,
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(d.notes_fi, '') = '' THEN 1 ELSE 0 END) as missing_desc,
            SUM(CASE WHEN COALESCE(d.keywords_fi, '[]') IN ('[]', '', '[""]')
                THEN 1 ELSE 0 END) as missing_keywords,
            SUM(CASE WHEN COALESCE(d.update_frequency, '') = '' THEN 1 ELSE 0 END)
                as missing_freq,
            SUM(CASE WHEN COALESCE(d.license_id, '') = '' THEN 1 ELSE 0 END)
                as missing_license,
            SUM(CASE WHEN COALESCE(d.title_en, '') = '' THEN 1 ELSE 0 END)
                as missing_title_en,
            SUM(CASE WHEN COALESCE(d.notes_en, '') = '' THEN 1 ELSE 0 END)
                as missing_notes_en
        FROM datasets d
        {where}
        GROUP BY d.source
        ORDER BY total DESC
        """,
        params,
    ).fetchall()

    sources: list[dict[str, Any]] = []
    # float eikä int: kentät ovat lukumääriä, mutta samaan dictiin kirjoitetaan
    # myös completeness_pct, joka on desimaaliluku. Lukumäärät pysyvät
    # ajonaikaisesti int-tyyppisinä.
    totals: dict[str, float] = {
        "total": 0,
        "missing_desc": 0,
        "missing_keywords": 0,
        "missing_freq": 0,
        "missing_license": 0,
        "missing_title_en": 0,
        "missing_notes_en": 0,
    }

    for row in rows:
        src: dict[str, Any] = dict(row)
        # Lasketaan täydellisyysprosentti
        total = src["total"]
        if total > 0:
            filled = sum(
                total - src.get(f, 0)
                for f in [
                    "missing_desc", "missing_keywords", "missing_freq",
                    "missing_license",
                ]
            )
            src["completeness_pct"] = round(100.0 * filled / (total * 4), 1)
        else:
            src["completeness_pct"] = 0.0

        sources.append(src)
        for key in totals:
            totals[key] += src.get(key, 0)

    total_all = totals["total"]
    if total_all > 0:
        filled_all = sum(
            total_all - totals[f]
            for f in [
                "missing_desc", "missing_keywords", "missing_freq",
                "missing_license",
            ]
        )
        totals["completeness_pct"] = round(
            100.0 * filled_all / (total_all * 4), 1,
        )
    else:
        totals["completeness_pct"] = 0.0

    return {
        "sources": sources,
        "totals": totals,
    }


def suggest_improvements(
    conn: sqlite3.Connection,
    source: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Ehdota helposti parannettavia datasettejä.

    Palauttaa datasetit joilla on eniten puutteita mutta jotka ovat
    helposti rikastettavissa.
    """
    where = "AND d.source = ?" if source else ""
    params: list[Any] = [source] if source else []

    rows = conn.execute(
        f"""
        SELECT * FROM (
            SELECT d.id, d.name,
                   COALESCE(d.title_fi, d.title) as title,
                   d.source,
                   d.organization_title as org,
                   (CASE WHEN COALESCE(d.notes_fi, '') = '' THEN 1 ELSE 0 END
                    + CASE WHEN COALESCE(d.keywords_fi, '[]') IN ('[]', '', '[""]')
                        THEN 1 ELSE 0 END
                    + CASE WHEN COALESCE(d.update_frequency, '') = '' THEN 1 ELSE 0 END
                    + CASE WHEN COALESCE(d.license_id, '') = '' THEN 1 ELSE 0 END
                   ) as gap_count,
                   CASE WHEN COALESCE(d.notes_fi, '') = ''
                       THEN 'kuvaus' ELSE '' END as m1,
                   CASE WHEN COALESCE(d.keywords_fi, '[]') IN ('[]', '', '[""]')
                       THEN 'avainsanat' ELSE '' END as m2,
                   CASE WHEN COALESCE(d.update_frequency, '') = ''
                       THEN 'päivitystiheys' ELSE '' END as m3,
                   CASE WHEN COALESCE(d.license_id, '') = ''
                       THEN 'lisenssi' ELSE '' END as m4
            FROM datasets d
            WHERE 1=1 {where}
        ) sub
        WHERE gap_count > 0
        ORDER BY gap_count DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        missing = [
            v for v in [row["m1"], row["m2"], row["m3"], row["m4"]] if v
        ]
        results.append({
            "id": row["id"],
            "name": row["name"],
            "title": row["title"],
            "source": row["source"],
            "org": row["org"],
            "gap_count": row["gap_count"],
            "missing_fields": missing,
        })

    return results


def _keyword_count(dataset: dict[str, Any]) -> int:
    """Palauta avainsanojen lukumäärä (JSON-string tai lista)."""
    return len(parse_json_list(dataset.get("keywords_fi", "[]")))
