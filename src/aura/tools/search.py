"""Hakutyökalut: search, search_structured, recommend, find_related, search_by_region."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.constants import MACHINE_READABLE_FORMATS, parse_json_list
from aura.database import (
    find_related_datasets,
    get_dataset,
    search_datasets,
)
from aura.limits import MAX_SEARCH_LIMIT, clamp
from aura.search import format_dataset_summary
from aura.server import mcp
from aura.telemetry import record_zero_result


@mcp.tool()
async def search(
    query: str,
    limit: int = 10,
    offset: int = 0,
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
    region: str = "",
    ctx: Context | None = None,
) -> str:
    """Hae suomalaisia avoimia datasettejä luonnollisella kielellä.

    Hakua laajennetaan automaattisesti YSO-ontologian avulla:
    esim. "liikenne" löytää myös tieliikenteen ja raideliikenteen datasetit.
    Lisäksi domain-sanastot laajentavat hakua ilman API-kutsuja.

    Args:
        query: Hakusanat (esim. "helsingin väestö", "ilmanlaatu", "joukkoliikenne")
        limit: Tulosten enimmäismäärä (oletus 10, katto 100)
        offset: Ohita ensimmäiset N tulosta (sivutus)
        source: Suodata lähteen mukaan (esim. "avoindata.fi", "hri.fi", "statfin")
        format: Suodata formaatin mukaan (esim. "CSV", "JSON", "GeoJSON")
        organization: Suodata organisaation mukaan (osa nimestä riittää)
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted")
        region: Suodata alueellisesti (kunnan nimi, maakunta tai postinumero)
    """
    limit = clamp(limit, MAX_SEARCH_LIMIT)
    conn = _server._get_conn(ctx)

    # YSO-hakulaajennus
    expanded_query = await _server._expand_query(query, ctx)

    # Aluerajaus
    region_names: list[str] | None = None
    if region.strip():
        region_names = _resolve_region(conn, region.strip()) or [region.strip()]

    results = search_datasets(
        conn, query, limit=limit, offset=offset,
        source=source, fmt=format, organization=organization,
        access_level=access_level,
        expanded_query=expanded_query,
        region_names=region_names,
    )

    if not results:
        # Nollatulos on ainoa signaali jossa käyttäjä kertoo suoraan mitä
        # katalogista puuttuu. Kirjaus on oletuksena pois päältä ja ohitetaan
        # hiljaisesti jos se ei onnistu — ks. aura.telemetry.
        record_zero_result(query)
        return f"Ei tuloksia haulle '{query}'. Kokeile eri hakusanoja tai suodattimia."

    parts = [f"Löytyi {len(results)} datasettiä haulle '{query}':\n"]
    for dataset in results:
        parts.append(format_dataset_summary(dataset))
        parts.append("---")

    return "\n".join(parts)


@mcp.tool()
async def search_structured(
    query: str,
    limit: int = 10,
    offset: int = 0,
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
    region: str = "",
    ctx: Context | None = None,
) -> str:
    """Hae datasettejä ja palauta rakenteellinen JSON tekoälyagenteille.

    Palauttaa hakutulokset JSON-muodossa koneluettavaa jatkokäsittelyä varten.
    Hakua laajennetaan YSO-ontologian avulla.

    Args:
        query: Hakusanat (esim. "väestö", "ilmanlaatu")
        limit: Tulosten enimmäismäärä (oletus 10, katto 100)
        offset: Ohita ensimmäiset N tulosta (sivutus)
        source: Suodata lähteen mukaan (esim. "avoindata.fi")
        format: Suodata formaatin mukaan (esim. "CSV")
        organization: Suodata organisaation mukaan
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted")
        region: Suodata alueellisesti (kunnan nimi, maakunta tai postinumero)
    """
    import json

    limit = clamp(limit, MAX_SEARCH_LIMIT)
    conn = _server._get_conn(ctx)
    expanded_query = await _server._expand_query(query, ctx)

    # Aluerajaus
    region_names: list[str] | None = None
    if region.strip():
        region_names = _resolve_region(conn, region.strip()) or [region.strip()]

    results = search_datasets(
        conn, query, limit=limit, offset=offset,
        source=source, fmt=format, organization=organization,
        access_level=access_level,
        expanded_query=expanded_query,
        region_names=region_names,
    )

    ds_ids = [d.get("id", "") for d in results]
    enrichment_counts = _batch_enrichment_counts(conn, ds_ids)
    health_map = _batch_health_status(conn, ds_ids)

    structured = []
    for d in results:
        keywords = parse_json_list(d.get("keywords_fi", "[]"))

        ds_id = d.get("id", "")
        structured.append({
            "id": ds_id,
            "name": d.get("name", ""),
            "title": d.get("title_fi") or d.get("title", ""),
            "description": d.get("notes_fi") or d.get("notes", ""),
            "organization": d.get("organization_title", ""),
            "source": d.get("source", ""),
            "license": d.get("license_title", ""),
            "keywords": keywords,
            "modified": d.get("metadata_modified", ""),
            "num_resources": d.get("num_resources", 0),
            "estimated_size_bytes": d.get("estimated_size_bytes", 0),
            "access_level": d.get("access_level", "open"),
            "harvested_at": d.get("harvested_at", ""),
            "enrichment_count": enrichment_counts.get(ds_id, 0),
            "health": health_map.get(ds_id),
        })

    return json.dumps(
        {"query": query, "count": len(structured), "offset": offset, "results": structured},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def recommend(topic: str, limit: int = 5, ctx: Context | None = None) -> str:
    """Suosittele parhaita datasettejä aiheesta.

    Etsii datasettejä ja järjestää ne relevanssin, tuoreuden ja resurssimäärän mukaan.

    Args:
        topic: Aihe tai teema (esim. "liikenne Helsinki", "ilmastonmuutos")
        limit: Suositusten enimmäismäärä (oletus 5)
    """
    limit = clamp(limit, MAX_SEARCH_LIMIT)
    conn = _server._get_conn(ctx)
    expanded_query = await _server._expand_query(topic, ctx)
    # Hae enemmän tuloksia kuin limit, jotta voidaan järjestää uudelleen
    results = search_datasets(conn, topic, limit=limit * 3, expanded_query=expanded_query)

    if not results:
        return f"Ei datasettejä aiheesta '{topic}'. Kokeile eri hakusanoja."

    # Hae lisätiedot batch-kyselyillä tehokkuuden vuoksi
    ds_ids = [d["id"] for d in results]
    enrichment_counts = _batch_enrichment_counts(conn, ds_ids)
    format_map = _batch_formats(conn, ds_ids)
    quality_scores = _batch_quality_scores(conn, ds_ids)

    now = datetime.now(tz=UTC)

    scored = []
    for d in results:
        rank = abs(d.get("rank", 0))
        num_res = d.get("num_resources", 0) or 0
        size = d.get("estimated_size_bytes", 0) or 0
        ds_id = d["id"]

        score = rank
        score -= num_res * 0.1
        score -= 1 if size > 0 else 0

        # Tuoreusbonus: metadata_modified viime vuodelta
        modified = d.get("metadata_modified", "")
        if modified:
            try:
                mod_dt = datetime.fromisoformat(modified).replace(
                    tzinfo=UTC
                )
                days_old = (now - mod_dt).days
                if days_old < 90:
                    score -= 0.8  # erittäin tuore
                elif days_old < 365:
                    score -= 0.4  # tuore
            except (ValueError, TypeError):
                pass

        # Enrichment-bonus: dokumentointi
        enr_count = enrichment_counts.get(ds_id, 0)
        score -= min(enr_count * 0.3, 1.5)  # max 1.5 bonus

        # Koneluettavuusbonus
        formats = format_map.get(ds_id, set())
        if formats & MACHINE_READABLE_FORMATS:
            score -= 0.3

        # Quality score -bonus (0–100 → 0–1.0 bonus)
        qs = quality_scores.get(ds_id, 0)
        score -= qs * 0.01

        scored.append((score, d))

    scored.sort(key=lambda x: x[0])
    top = scored[:limit]

    parts = [f"# Suositellut datasetit: {topic}\n"]
    for i, (_, d) in enumerate(top, 1):
        title = d.get("title_fi") or d.get("title") or d.get("name", "")
        org = d.get("organization_title", "")
        notes = d.get("notes_fi") or d.get("notes", "")
        if len(notes) > 200:
            notes = notes[:197] + "..."
        num_res = d.get("num_resources", 0) or 0
        name = d.get("name", d.get("id", ""))

        parts.append(f"## {i}. {title}")
        if org:
            parts.append(f"**Julkaisija:** {org}")
        if notes:
            parts.append(f"**Kuvaus:** {notes}")
        parts.append(f"**Resursseja:** {num_res}")
        parts.append(f"**ID:** {name}")
        parts.append("")

    return "\n".join(parts)


@mcp.tool()
def find_related(dataset_id: str, limit: int = 5, ctx: Context | None = None) -> str:
    """Etsi samankaltaiset datasetit avainsanojen ja organisaation perusteella.

    Args:
        dataset_id: Datasetin ID tai nimi
        limit: Tulosten enimmäismäärä (oletus 5)
    """
    limit = clamp(limit, MAX_SEARCH_LIMIT)
    conn = _server._get_conn(ctx)
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    related = find_related_datasets(conn, dataset_id, limit=limit)

    if not related:
        return f"Ei samankaltaisia datasettejä löytynyt datasetille '{dataset_id}'."

    title = dataset.get("title_fi") or dataset.get("title") or dataset.get("name", "")
    parts = [f"# Samankaltaiset datasetit: {title}\n"]

    for d in related:
        rel_title = d.get("title_fi") or d.get("title") or d.get("name", "")
        org = d.get("organization_title", "")
        source = d.get("source", "")
        name = d.get("name", d.get("id", ""))

        parts.append(f"- **{rel_title}** ({org}, {source}) — ID: {name}")

    return "\n".join(parts)


@mcp.tool()
async def search_by_region(
    region: str,
    query: str = "",
    limit: int = 10,
    ctx: Context | None = None,
) -> str:
    """Hae datasettejä alueellisesti kunnan, maakunnan tai postinumeron perusteella.

    Esim: region="Pirkanmaa", query="liikenne" → Pirkanmaan liikennedata.
    Yhdistää viitedatan geographical_coverage -kenttään.

    Args:
        region: Alue (kunnan nimi, maakunta tai postinumero)
        query: Valinnainen lisähakutermi
        limit: Tulosten enimmäismäärä
    """
    limit = clamp(limit, MAX_SEARCH_LIMIT)
    conn = _server._get_conn(ctx)
    region = region.strip()

    # Resolvoi aluenimi → lista kuntanimiä
    municipality_names = _resolve_region(conn, region)

    if not municipality_names:
        # Fallback: käytä region-nimeä sellaisenaan geographical_coverage-haussa
        municipality_names = [region]

    fts_query: str | None = None
    if query:
        expanded_query = await _server._expand_query(query, ctx)
        fts_query = expanded_query if expanded_query else query

    sql, params = _build_region_query(municipality_names, fts_query, limit)
    rows = conn.execute(sql, params).fetchall()

    if not rows:
        msg = f"Ei datasettejä alueelle '{region}'"
        if query:
            msg += f" haulle '{query}'"
        return msg + ". Kokeile laajempaa aluetta tai eri hakusanoja."

    parts = [f"Löytyi {len(rows)} datasettiä alueelle '{region}'"]
    if query:
        parts[0] += f" haulle '{query}'"
    parts[0] += ":\n"

    for row in rows:
        parts.append(format_dataset_summary(dict(row)))
        parts.append("---")

    return "\n".join(parts)


# --- Apufunktiot ---


def _build_region_query(
    municipality_names: list[str],
    fts_query: str | None,
    limit: int,
) -> tuple[str, list[Any]]:
    """Rakenna aluehaun SQL-kysely parametreineen."""
    coverage_conditions = " OR ".join(
        "d.geographical_coverage LIKE ?" for _ in municipality_names
    )
    coverage_params = [f"%{name}%" for name in municipality_names]

    if fts_query:
        sql = """
            SELECT d.*, COALESCE(fts.rank, 0) as rank
            FROM datasets d
            LEFT JOIN (
                SELECT rowid, rank FROM datasets_fts
                WHERE datasets_fts MATCH ?
            ) fts ON d.rowid = fts.rowid
            WHERE (""" + coverage_conditions + """)
            AND (fts.rowid IS NOT NULL OR d.id IN
                (SELECT DISTINCT dataset_id FROM enrichments_fts
                 WHERE enrichments_fts MATCH ?))
            ORDER BY rank
            LIMIT ?
        """
        params: list[Any] = [fts_query, *coverage_params, fts_query, limit]
    else:
        sql = """
            SELECT d.*
            FROM datasets d
            WHERE (""" + coverage_conditions + """)
            LIMIT ?
        """
        params = [*coverage_params, limit]

    return sql, params


def _batch_enrichment_counts(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> dict[str, int]:
    """Hae enrichment-lukumäärät yhdellä kyselyllä."""
    if not dataset_ids:
        return {}
    placeholders = ",".join("?" for _ in dataset_ids)
    rows = conn.execute(
        f"""
        SELECT dataset_id, COUNT(DISTINCT field) as cnt
        FROM enrichments
        WHERE dataset_id IN ({placeholders})
        GROUP BY dataset_id
        """,
        dataset_ids,
    ).fetchall()
    return {row["dataset_id"]: row["cnt"] for row in rows}


def _batch_formats(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> dict[str, set[str]]:
    """Hae resurssiformaatit dataseteille yhdellä kyselyllä."""
    if not dataset_ids:
        return {}
    placeholders = ",".join("?" for _ in dataset_ids)
    rows = conn.execute(
        f"""
        SELECT dataset_id, format
        FROM resources
        WHERE dataset_id IN ({placeholders}) AND format != ''
        """,
        dataset_ids,
    ).fetchall()
    result: dict[str, set[str]] = {}
    for row in rows:
        result.setdefault(row["dataset_id"], set()).add(row["format"])
    return result


def _batch_quality_scores(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> dict[str, float]:
    """Hae overall-laatupisteet dataseteille yhdellä kyselyllä."""
    if not dataset_ids:
        return {}
    placeholders = ",".join("?" for _ in dataset_ids)
    rows = conn.execute(
        f"""
        SELECT dataset_id, score
        FROM quality_scores
        WHERE dataset_id IN ({placeholders}) AND dimension = 'overall'
        """,
        dataset_ids,
    ).fetchall()
    return {row["dataset_id"]: row["score"] for row in rows}


def _batch_health_status(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Hae dataset-tason saatavuusyhteenveto yhdellä kyselyllä."""
    if not dataset_ids:
        return {}
    placeholders = ",".join("?" for _ in dataset_ids)
    rows = conn.execute(
        f"""
        SELECT
            dataset_id,
            MAX(is_available) AS is_available,
            MAX(checked_at) AS last_checked,
            CAST(ROUND(AVG(response_time_ms)) AS INTEGER) AS avg_response_time_ms
        FROM resource_health
        WHERE dataset_id IN ({placeholders})
        GROUP BY dataset_id
        """,
        dataset_ids,
    ).fetchall()
    return {
        row["dataset_id"]: {
            "is_available": bool(row["is_available"]),
            "last_checked": row["last_checked"],
            "avg_response_time_ms": row["avg_response_time_ms"],
        }
        for row in rows
    }


def _resolve_region(conn: sqlite3.Connection, region: str) -> list[str]:
    """Resolvoi aluenimi kuntanimien listaksi viitedatan avulla."""
    # Tarkista onko viitedata populoitu
    meta = conn.execute(
        "SELECT record_count FROM ref_metadata WHERE name = 'municipalities'"
    ).fetchone()
    if not meta or meta["record_count"] == 0:
        return []

    # Postinumero → kunnan nimi
    if region.isdigit() and len(region) == 5:
        postal = conn.execute(
            "SELECT municipality_code FROM ref_postal_codes WHERE code = ?",
            (region,),
        ).fetchone()
        if postal:
            muni = conn.execute(
                "SELECT name_fi FROM ref_municipalities WHERE code = ?",
                (postal["municipality_code"],),
            ).fetchone()
            if muni:
                return [muni["name_fi"]]
        return []

    # Kuntakoodi → kunnan nimi
    if region.isdigit() and len(region) <= 3:
        code = region.zfill(3)
        muni = conn.execute(
            "SELECT name_fi FROM ref_municipalities WHERE code = ?", (code,)
        ).fetchone()
        if muni:
            return [muni["name_fi"]]
        return []

    # Maakunta → kaikki maakunnan kunnat
    munis = conn.execute(
        "SELECT name_fi FROM ref_municipalities WHERE region_name_fi LIKE ?",
        (region,),
    ).fetchall()
    if munis:
        return [m["name_fi"] for m in munis]

    # ELY-alue → kaikki ELY:n kunnat
    munis = conn.execute(
        "SELECT name_fi FROM ref_municipalities WHERE ely_name_fi LIKE ?",
        (region,),
    ).fetchall()
    if munis:
        return [m["name_fi"] for m in munis]

    # Hyvinvointialue → kunnat
    munis = conn.execute(
        "SELECT name_fi FROM ref_municipalities WHERE wellbeing_area_name_fi LIKE ?",
        (region,),
    ).fetchall()
    if munis:
        return [m["name_fi"] for m in munis]

    # Yksittäinen kunta nimellä
    muni = conn.execute(
        "SELECT name_fi FROM ref_municipalities WHERE name_fi LIKE ? OR name_sv LIKE ?",
        (region, region),
    ).fetchone()
    if muni:
        return [muni["name_fi"]]

    return []
