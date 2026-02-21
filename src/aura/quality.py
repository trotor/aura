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
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

DIMENSION_WEIGHTS = {
    "completeness": 0.25,
    "timeliness": 0.30,
    "accessibility": 0.25,
    "documentation": 0.20,
}

MACHINE_READABLE_FORMATS = {
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "WCS", "OData",
    "XML", "API", "Parquet", "GeoParquet", "GPKG", "SQLite",
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

    count = 0
    for row in rows:
        dataset = dict(row)
        ds_id = dataset["id"]

        # Resurssit
        resources = [
            dict(r) for r in conn.execute(
                "SELECT * FROM resources WHERE dataset_id = ?", (ds_id,)
            ).fetchall()
        ]

        # Enrichment-lukumäärä
        enr_row = conn.execute(
            "SELECT COUNT(DISTINCT field) FROM enrichments WHERE dataset_id = ?",
            (ds_id,),
        ).fetchone()
        enrichment_count = enr_row[0] if enr_row else 0

        scores = calculate_quality(dataset, resources, enrichment_count)
        save_quality_scores(conn, ds_id, scores)
        count += 1

    conn.commit()
    logger.info("Laatupisteet laskettu %d datasetille", count)
    return count


def _keyword_count(dataset: dict[str, Any]) -> int:
    """Palauta avainsanojen lukumäärä (JSON-string tai lista)."""
    raw = dataset.get("keywords_fi", "[]")
    if isinstance(raw, list):
        return len(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return len(parsed) if isinstance(parsed, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0
    return 0
