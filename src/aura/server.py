"""Aura MCP-server FastMCP:llä."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastmcp import Context, FastMCP

from aura.database import (
    add_enrichment,
    find_related_datasets,
    get_conflicting_enrichments,
    get_connection,
    get_dataset,
    get_datasets_by_ids,
    get_enrichment_count,
    get_latest_enrichments,
    get_stale_enrichments,
    get_stats,
    init_db,
    search_datasets,
)
from aura.quality import get_quality_scores
from aura.tagger import format_suggestions
from aura.tagger import suggest_tags as _suggest_tags
from aura.yso import YsoClient, build_fts5_query
from aura.search import (
    format_dataset_detail,
    format_dataset_summary,
    format_enrichments,
    format_stats,
)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Hallitse tietokantayhteyttä serverin elinkaaren ajan."""
    conn = get_connection(check_same_thread=False)
    init_db(conn)
    try:
        yield {"db": conn, "findings": [], "yso": YsoClient()}
    finally:
        conn.close()


mcp = FastMCP(
    "Aura",
    instructions=(
        "Suomalaisen avoimen datan discovery-palvelu. "
        "Hae ja ymmärrä Suomen avoimia datasettejä. "
        "Kun tutkit datasettejä ja löydät uutta tietoa niistä "
        "(kenttiä, käyttöohjeita, laatuhuomioita), "
        "kirjaa löydökset log_finding()-työkalulla tutkimuksen aikana. "
        "Lopuksi tallenna ne enrichmenteiksi save_session_findings()-kutsulla.\n\n"
        "RAJAUSAINEISTOT (data/boundaries/, EPSG:3067):\n"
        "1) karttalehtijako.gpkg — MML:n TM35-ruutujako. "
        "Tasot: utm200..utm5, utm1. Kenttä: lehtitunnus (esim. 'L4133A'). "
        "Hierarkia: L4→L41→L413→L4133→L4133A→L4133A3. "
        "Käytä bbox-rajauksia WFS/WCS-kyselyihin. "
        "Mittakaava: utm50 maakunnille, utm25 kaupungeille, utm10 yksityiskohdille.\n"
        "2) kuntajako_1000k.gpkg / kuntajako_10k.gpkg — MML:n hallinnolliset rajat. "
        "Tasot: Kunta (308), Maakunta (19), Hyvinvointialue (23), Valtakunta (1). "
        "Kentät: natcode (koodi), namefin (nimi fi), nameswe (nimi sv), landarea, totalarea. "
        "Käytä kunnan/maakunnan bbox:ia aluerajauksiin: "
        "SELECT MbrMinX(multipolygon),MbrMinY(multipolygon),"
        "MbrMaxX(multipolygon),MbrMaxY(multipolygon) "
        "FROM Kunta WHERE namefin='Helsinki'."
    ),
    lifespan=_lifespan,
)


def _get_conn(ctx: Context | None = None) -> sqlite3.Connection:
    """Hae tietokantayhteys lifespan-kontekstista tai luo uusi.

    Lifespan-yhteys on suositeltava (thread-safe, jaettu).
    Fallback luo uuden yhteyden (CLI-käyttö, testit).
    """
    if ctx is not None:
        try:
            conn: sqlite3.Connection = ctx.lifespan_context["db"]
            return conn
        except (AttributeError, KeyError):
            pass
    # Fallback: luo uusi yhteys (esim. CLI, testit, vanha kutsupolku)
    conn = get_connection(check_same_thread=False)
    init_db(conn)
    return conn


def _get_yso(ctx: Context | None) -> YsoClient | None:
    """Hae YsoClient lifespan-kontekstista."""
    if ctx:
        try:
            return ctx.lifespan_context.get("yso")
        except (AttributeError, KeyError):
            pass
    return None


async def _expand_with_yso(query: str, ctx: Context | None) -> str:
    """Laajenna hakutermi YSO-ontologialla.

    Palauttaa FTS5-hakulausekkeen tai tyhjän merkkijonon jos
    laajennusta ei tehdä.
    """
    yso = _get_yso(ctx)
    if not yso:
        return ""
    try:
        terms = await yso.expand_query(query)
        if len(terms) > 1:
            return build_fts5_query(terms)
    except Exception:
        pass
    return ""


@mcp.tool()
async def search(
    query: str,
    limit: int = 10,
    offset: int = 0,
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
    ctx: Context | None = None,
) -> str:
    """Hae suomalaisia avoimia datasettejä luonnollisella kielellä.

    Hakua laajennetaan automaattisesti YSO-ontologian avulla:
    esim. "liikenne" löytää myös tieliikenteen ja raideliikenteen datasetit.

    Args:
        query: Hakusanat (esim. "helsingin väestö", "ilmanlaatu", "joukkoliikenne")
        limit: Tulosten enimmäismäärä (oletus 10)
        offset: Ohita ensimmäiset N tulosta (sivutus)
        source: Suodata lähteen mukaan (esim. "avoindata.fi", "hri.fi", "statfin")
        format: Suodata formaatin mukaan (esim. "CSV", "JSON", "GeoJSON")
        organization: Suodata organisaation mukaan (osa nimestä riittää)
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted")
    """
    conn = _get_conn(ctx)

    # YSO-hakulaajennus
    expanded_query = await _expand_with_yso(query, ctx)

    results = search_datasets(
        conn, query, limit=limit, offset=offset,
        source=source, fmt=format, organization=organization,
        access_level=access_level,
        expanded_query=expanded_query,
    )

    if not results:
        return f"Ei tuloksia haulle '{query}'. Kokeile eri hakusanoja tai suodattimia."

    parts = [f"Löytyi {len(results)} datasettiä haulle '{query}':\n"]
    for dataset in results:
        parts.append(format_dataset_summary(dataset))
        parts.append("---")

    return "\n".join(parts)


@mcp.tool()
def describe(dataset_id: str, ctx: Context | None = None) -> str:
    """Kuvaa yksittäinen datasetti yksityiskohtaisesti.

    Args:
        dataset_id: Datasetin ID tai nimi (esim. "helsinkikanava-open-data")
    """
    conn = _get_conn(ctx)
    dataset = get_dataset(conn, dataset_id)

    if dataset is None:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    ds_id = dataset["id"]
    enrichments = get_latest_enrichments(conn, ds_id)
    stale = get_stale_enrichments(conn, ds_id)
    stale_ids = {e["id"] for e in stale}
    conflicts = get_conflicting_enrichments(conn, ds_id)
    result = format_dataset_detail(
        dataset,
        enrichments=enrichments,
        stale_ids=stale_ids,
        conflicts=conflicts,
    )

    # Laatupisteet
    quality = get_quality_scores(conn, ds_id)
    if quality and "overall" in quality:
        result += _format_quality_section(quality)

    # Resurssien saatavuus
    result += _format_health_section(conn, ds_id)

    # Enrichment-kehotus: puuttuvat kentät
    result += _format_enrichment_gaps(ds_id, enrichments)

    return result


@mcp.tool()
def stats(ctx: Context | None = None) -> str:
    """Näytä tilastot Auran tietokannasta: datasettien, organisaatioiden ja formaattien määrät."""
    conn = _get_conn(ctx)
    return format_stats(get_stats(conn))


@mcp.tool()
def list_organizations(limit: int = 20, ctx: Context | None = None) -> str:
    """Listaa avoimen datan julkaisijat datasettien lukumäärän mukaan.

    Args:
        limit: Näytettävien organisaatioiden enimmäismäärä
    """
    conn = _get_conn(ctx)
    rows = conn.execute(
        """
        SELECT o.id, o.title, o.name, COUNT(d.id) as count
        FROM organizations o
        JOIN datasets d ON d.organization_id = o.id
        GROUP BY o.id
        ORDER BY count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    if not rows:
        # Fallback to old denormalized query if organizations table empty
        rows = conn.execute(
            """
            SELECT organization_title as title, COUNT(*) as count
            FROM datasets WHERE organization_title != ''
            GROUP BY organization_title ORDER BY count DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return "Tietokanta on tyhjä. Aja ensin 'aura harvest'."

    parts = ["# Avoimen datan julkaisijat\n"]
    for row in rows:
        parts.append(f"- **{row['title']}**: {row['count']} datasettiä")
    return "\n".join(parts)


@mcp.tool()
def list_formats(limit: int = 20, ctx: Context | None = None) -> str:
    """Listaa saatavilla olevat dataformaatit resurssien lukumäärän mukaan.

    Args:
        limit: Näytettävien formaattien enimmäismäärä
    """
    conn = _get_conn(ctx)
    rows = conn.execute(
        """
        SELECT format, COUNT(*) as count
        FROM resources
        WHERE format != ''
        GROUP BY format
        ORDER BY count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    if not rows:
        return "Tietokanta on tyhjä. Aja ensin 'aura harvest'."

    parts = ["# Dataformaatit\n"]
    for row in rows:
        parts.append(f"- **{row['format']}**: {row['count']} resurssia")
    return "\n".join(parts)


@mcp.tool()
def harvest(source: str = "all", ctx: Context | None = None) -> str:
    """Hae datasettien metatiedot lähteistä ja tallenna tietokantaan.

    Args:
        source: Lähteen nimi (esim. "avoindata.fi", "statfin") tai "all" kaikille
    """
    from aura.harvesters import get_all_harvesters, get_harvester

    conn = _get_conn(ctx)
    if source == "all":
        total = 0
        parts = []
        for name, cls in get_all_harvesters().items():
            harvester = cls(conn=conn)
            count = asyncio.run(harvester.harvest())
            parts.append(f"- {name}: {count} datasettiä")
            total += count
        parts.insert(0, f"# Harvest valmis\n\nYhteensä {total} datasettiä:\n")
        return "\n".join(parts)

    try:
        cls = get_harvester(source)
    except ValueError as e:
        return str(e)

    harvester = cls(conn=conn)
    count = asyncio.run(harvester.harvest())
    return f"Haettu {count} datasettiä lähteestä {source}."


@mcp.tool()
def list_sources(ctx: Context | None = None) -> str:
    """Listaa kaikki datalähteet, niiden datasettien lukumäärät ja harvestoinnin tila."""
    from datetime import datetime

    from aura.harvesters import get_all_harvesters

    conn = _get_conn(ctx)
    parts = ["# Datalähteet\n"]
    now = datetime.now(tz=UTC)

    for name, cls in get_all_harvesters().items():
        row = conn.execute(
            """
            SELECT COUNT(*) as count, MAX(harvested_at) as last_harvest
            FROM datasets WHERE source = ?
            """,
            (name,),
        ).fetchone()
        count = row["count"] if row else 0
        last_harvest = row["last_harvest"] if row else None

        status = f"{count} datasettiä"
        warning = ""
        if last_harvest:
            harvest_dt = datetime.fromisoformat(last_harvest)
            days_old = (now - harvest_dt.replace(tzinfo=UTC)).days
            status += f" (viimeksi: {last_harvest[:16]})"
            if days_old > 7:
                warning = f" ⚠ {days_old} pv vanha"
        elif count == 0:
            status = "ei harvestoitu"

        parts.append(f"- **{name}**: {cls.description} [{status}]{warning}")

    return "\n".join(parts)


@mcp.tool()
def probe_sizes(source: str = "all", ctx: Context | None = None) -> str:
    """Mittaa paikkatietoaineistojen koot otoskyselyillä (WFS/WCS).

    Args:
        source: "metsakeskus", "gtk" tai "all"
    """
    from aura.spatial_probe import format_probe_report, probe_all

    probe_results = asyncio.run(probe_all(source=source, timeout=180.0))
    return format_probe_report(probe_results)


@mcp.tool()
async def search_structured(
    query: str,
    limit: int = 10,
    offset: int = 0,
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
    ctx: Context | None = None,
) -> str:
    """Hae datasettejä ja palauta rakenteellinen JSON tekoälyagenteille.

    Palauttaa hakutulokset JSON-muodossa koneluettavaa jatkokäsittelyä varten.
    Hakua laajennetaan YSO-ontologian avulla.

    Args:
        query: Hakusanat (esim. "väestö", "ilmanlaatu")
        limit: Tulosten enimmäismäärä (oletus 10)
        offset: Ohita ensimmäiset N tulosta (sivutus)
        source: Suodata lähteen mukaan (esim. "avoindata.fi")
        format: Suodata formaatin mukaan (esim. "CSV")
        organization: Suodata organisaation mukaan
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted")
    """
    import json

    conn = _get_conn(ctx)
    expanded_query = await _expand_with_yso(query, ctx)
    results = search_datasets(
        conn, query, limit=limit, offset=offset,
        source=source, fmt=format, organization=organization,
        access_level=access_level,
        expanded_query=expanded_query,
    )

    structured = []
    for d in results:
        keywords_raw = d.get("keywords_fi", "[]")
        if isinstance(keywords_raw, str):
            try:
                keywords = json.loads(keywords_raw)
            except json.JSONDecodeError:
                keywords = []
        else:
            keywords = keywords_raw

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
            "enrichment_count": get_enrichment_count(conn, ds_id),
        })

    return json.dumps(
        {"query": query, "count": len(structured), "offset": offset, "results": structured},
        ensure_ascii=False,
        indent=2,
    )


MACHINE_READABLE_FORMATS = {
    "CSV", "JSON", "GeoJSON", "WFS", "WMS", "OData", "XML", "API",
    "Parquet", "GeoParquet", "GPKG", "SQLite", "WCS",
}


@mcp.tool()
def recommend(topic: str, limit: int = 5, ctx: Context | None = None) -> str:
    """Suosittele parhaita datasettejä aiheesta.

    Etsii datasettejä ja järjestää ne relevanssin, tuoreuden ja resurssimäärän mukaan.

    Args:
        topic: Aihe tai teema (esim. "liikenne Helsinki", "ilmastonmuutos")
        limit: Suositusten enimmäismäärä (oletus 5)
    """
    conn = _get_conn(ctx)
    # Hae enemmän tuloksia kuin limit, jotta voidaan järjestää uudelleen
    results = search_datasets(conn, topic, limit=limit * 3)

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


def _format_quality_section(quality: dict[str, Any]) -> str:
    """Muotoile laatupisteet describe()-tulokseen."""
    overall = quality.get("overall", {}).get("score", 0)

    dim_labels = {
        "completeness": "Täydellisyys",
        "timeliness": "Ajantasaisuus",
        "accessibility": "Saavutettavuus",
        "documentation": "Dokumentointi",
    }

    parts = [f"\n\n### Laatuarvio: {overall:.0f}/100\n"]
    for dim, label in dim_labels.items():
        if dim in quality:
            s = quality[dim]["score"]
            bar_len = int(s / 10)
            bar = "\u2588" * bar_len + "\u2591" * (10 - bar_len)
            parts.append(f"  {label:16s} {s:5.0f}/100 {bar}")

    return "\n".join(parts)


def _format_health_section(conn: sqlite3.Connection, dataset_id: str) -> str:
    """Muotoile datasetin resurssien saatavuustiedot."""
    from aura.health import get_dataset_health

    health = get_dataset_health(conn, dataset_id)
    if not health:
        return ""

    total = len(health)
    avail = sum(1 for h in health if h["is_available"])
    parts = [f"\n\n### Resurssien saatavuus ({avail}/{total})\n"]

    for h in health:
        icon = "+" if h["is_available"] else "-"
        ms = f" ({h['response_time_ms']}ms)" if h.get("response_time_ms") else ""
        err = f" — {h['error_message']}" if h.get("error_message") else ""
        url = h.get("url", "")
        if len(url) > 70:
            url = url[:67] + "..."
        parts.append(f"- [{icon}] {url}{ms}{err}")

    return "\n".join(parts)


# Enrichment-kentät prioriteettijärjestyksessä
_ENRICHMENT_PRIORITIES = [
    ("access_instructions", "Miten dataa haetaan käytännössä?"),
    ("data_fields", "Mitä kenttiä/sarakkeita data sisältää?"),
    ("use_case", "Mihin dataa voi käyttää?"),
    ("temporal_coverage", "Miltä ajanjaksolta data on?"),
    ("description_extended", "Laajempi kuvaus aineistosta"),
    ("keywords", "Lisäavainsanat haun parantamiseksi"),
    ("api_endpoint", "Rajapinnan URL"),
    ("api_format", "Rajapinnan formaatti (REST, WFS, OData)"),
    ("quality_notes", "Huomioita datan laadusta"),
    ("organization_context", "Taustatietoa julkaisijasta"),
    ("update_frequency_actual", "Havaittu päivitystiheys"),
]


def _format_enrichment_gaps(
    dataset_id: str,
    enrichments: list[dict[str, Any]],
    max_gaps: int = 5,
) -> str:
    """Muotoile puuttuvien enrichment-kenttien kehotus."""
    existing_fields = {e.get("field", "") for e in enrichments}

    missing = [
        (field, desc)
        for field, desc in _ENRICHMENT_PRIORITIES
        if field not in existing_fields
    ]

    if not missing:
        return ""

    show = missing[:max_gaps]
    parts = ["\n\n### Puuttuvat tiedot\n"]
    for field, desc in show:
        parts.append(f"- **{field}**: {desc}")

    parts.append(
        f'\nTallenna: enrich(dataset_id="{dataset_id}", '
        'field="...", value="...")'
    )

    return "\n".join(parts)


@mcp.tool()
def quality_report(
    dataset_id: str, ctx: Context | None = None
) -> str:
    """Näytä datasetin laatupisteet dimensioittain.

    Args:
        dataset_id: Datasetin ID tai nimi
    """
    conn = _get_conn(ctx)
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
        save_quality_scores(conn, ds_id, scores)
        conn.commit()
        quality = get_quality_scores(conn, ds_id)

    if not quality:
        return "Laatupisteitä ei voitu laskea."

    title = dataset.get("title_fi") or dataset.get("title") or ds_id
    overall = quality.get("overall", {}).get("score", 0)

    dim_info = {
        "completeness": "Täydellisyys",
        "timeliness": "Ajantasaisuus",
        "accessibility": "Saavutettavuus",
        "documentation": "Dokumentointi",
    }

    parts = [f"# Laatuarvio: {title}\n"]
    parts.append(f"**Kokonaispistemäärä: {overall:.0f}/100**\n")

    for dim, label in dim_info.items():
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
    conn = _get_conn(ctx)

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
    dim_labels = {
        "completeness": "Täydellisyys",
        "timeliness": "Ajantasaisuus",
        "accessibility": "Saavutettavuus",
        "documentation": "Dokumentointi",
    }

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
            parts.append(f"  {dim_labels[dim]:16s} ka. {s:.0f}/100")

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
    conn = _get_conn(ctx)

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

    dim_labels = {
        "overall": "Kokonaislaatu",
        "completeness": "Täydellisyys",
        "timeliness": "Ajantasaisuus",
        "accessibility": "Saavutettavuus",
        "documentation": "Dokumentointi",
    }
    label = dim_labels.get(dimension, dimension)
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
def compare(dataset_ids: list[str], ctx: Context | None = None) -> str:
    """Vertaile datasettejä rinnakkain.

    Args:
        dataset_ids: Lista datasetin ID:istä tai nimistä (2–5 kpl)
    """
    if len(dataset_ids) < 2:
        return "Anna vähintään 2 datasetin ID:tä vertailua varten."
    if len(dataset_ids) > 5:
        return "Vertaile korkeintaan 5 datasettiä kerrallaan."

    import json

    conn = _get_conn(ctx)
    datasets = get_datasets_by_ids(conn, dataset_ids)

    if not datasets:
        return "Yhtäkään datasettiä ei löytynyt annetuilla ID:illä."

    parts = [f"# Datasettien vertailu ({len(datasets)} kpl)\n"]

    for d in datasets:
        title = d.get("title_fi") or d.get("title") or d.get("name", "")
        org = d.get("organization_title", "")
        source = d.get("source", "")
        license_t = d.get("license_title", "")
        num_res = d.get("num_resources", 0) or 0
        modified = (d.get("metadata_modified") or "")[:10]
        size = d.get("estimated_size_bytes", 0) or 0

        keywords_raw = d.get("keywords_fi", "[]")
        if isinstance(keywords_raw, str):
            try:
                keywords = json.loads(keywords_raw)
            except json.JSONDecodeError:
                keywords = []
        else:
            keywords = keywords_raw

        # Resurssiformaatit
        formats = sorted({r.get("format", "") for r in d.get("resources", []) if r.get("format")})

        parts.append(f"## {title}")
        parts.append(f"- **Lähde:** {source}")
        parts.append(f"- **Julkaisija:** {org}")
        parts.append(f"- **Lisenssi:** {license_t}")
        parts.append(f"- **Resursseja:** {num_res}")
        parts.append(f"- **Formaatit:** {', '.join(formats) if formats else '—'}")
        parts.append(f"- **Päivitetty:** {modified or '—'}")
        if size > 0:
            size_mb = size / (1024 * 1024)
            parts.append(f"- **Arvioitu koko:** {size_mb:.1f} MB")
        if keywords:
            parts.append(f"- **Avainsanat:** {', '.join(keywords[:10])}")
        parts.append(f"- **ID:** {d.get('name', d.get('id', ''))}")
        parts.append("")

    return "\n".join(parts)


@mcp.tool()
def enrich(
    dataset_id: str,
    field: str,
    value: str,
    confidence: str = "medium",
    source_type: str = "mcp_session",
    source_detail: str = "",
    ctx: Context | None = None,
) -> str:
    """Rikasta datasetin tietoja. Tallentaa löydetyn tiedon kantaan.

    Käytä tätä kun löydät uutta tietoa datasetistä tutkimuksen aikana.

    Args:
        dataset_id: Datasetin ID tai nimi
        field: Rikastettava kenttä. Tuetut kentät:
            - description_extended: laajennettu kuvaus
            - api_endpoint: löydetty rajapinta-URL
            - api_format: rajapinnan formaatti (REST, WFS, OData, jne.)
            - data_fields: JSON-lista datasetin kentistä/sarakkeista
            - keywords: lisäavainsanat JSON-listana (esim. '["maatalous", "peltolohko"]')
            - tags: vapaamuotoiset tagit JSON-listana (esim. '["paikkatietoaineisto", "INSPIRE"]')
            - related_datasets: liittyvät datasetit
            - quality_notes: huomioita datan laadusta
            - use_case: käyttötapausesimerkki
            - access_instructions: ohjeet datan hakemiseen
            - organization_context: taustatietoa julkaisijasta
            - temporal_coverage: ajallinen kattavuus
            - update_frequency_actual: havaittu päivitystiheys
        value: Rikastuksen arvo (teksti tai JSON-merkkijono)
        confidence: Luottamustaso: "low", "medium", "high", "verified"
        source_type: Lähdetyyppi: "mcp_session", "web_research",
            "manual", "ai_analysis"
        source_detail: Lähteen kuvaus tai URL
    """
    conn = _get_conn(ctx)

    valid_fields = {
        "description_extended", "api_endpoint", "api_format",
        "data_fields", "keywords", "tags",
        "related_datasets", "quality_notes",
        "use_case", "access_instructions", "organization_context",
        "temporal_coverage", "update_frequency_actual",
        "yso_concepts",
    }
    if field not in valid_fields:
        fields_list = ", ".join(sorted(valid_fields))
        return f"Tuntematon kenttä '{field}'. Tuetut: {fields_list}"

    valid_confidence = {"low", "medium", "high", "verified"}
    if confidence not in valid_confidence:
        return f"Virheellinen luottamustaso '{confidence}'."

    enrichment_id = add_enrichment(
        conn, dataset_id, field, value,
        confidence=confidence,
        source_type=source_type,
        source_detail=source_detail,
    )
    return (
        f"Rikastus tallennettu (id: {enrichment_id}). "
        f"Datasetti: {dataset_id}, kenttä: {field}."
    )


@mcp.tool()
def batch_enrich(
    enrichments: list[dict[str, str]],
    ctx: Context | None = None,
) -> str:
    """Tallenna useita rikastuksia kerralla.

    Tehokkaampi kuin yksittäiset enrich()-kutsut kun haluat
    tallentaa monta löydöstä samalla kertaa.

    Args:
        enrichments: Lista rikastuksista. Jokainen sisältää:
            - dataset_id: Datasetin ID tai nimi
            - field: Rikastettava kenttä (samat kuin enrich()-työkalussa)
            - value: Rikastuksen arvo
            - confidence: (valinnainen) "low"/"medium"/"high"/"verified"
            - source_type: (valinnainen) lähdetyyppi
            - source_detail: (valinnainen) lähteen kuvaus
    """
    conn = _get_conn(ctx)

    valid_fields = {
        "description_extended", "api_endpoint", "api_format",
        "data_fields", "keywords", "tags",
        "related_datasets", "quality_notes",
        "use_case", "access_instructions", "organization_context",
        "temporal_coverage", "update_frequency_actual",
        "yso_concepts",
    }

    results: list[str] = []
    errors: list[str] = []

    for i, e in enumerate(enrichments):
        ds_id = e.get("dataset_id", "")
        field = e.get("field", "")
        value = e.get("value", "")

        if not ds_id or not field or not value:
            errors.append(f"#{i + 1}: puuttuva dataset_id/field/value")
            continue
        if field not in valid_fields:
            errors.append(f"#{i + 1}: tuntematon kenttä '{field}'")
            continue

        add_enrichment(
            conn, ds_id, field, value,
            confidence=e.get("confidence", "medium"),
            source_type=e.get("source_type", "mcp_session"),
            source_detail=e.get("source_detail", ""),
        )
        results.append(f"- {ds_id}/{field}")

    parts: list[str] = []
    if results:
        parts.append(f"Tallennettu {len(results)} rikastusta:")
        parts.extend(results)
    if errors:
        parts.append(f"\nVirheet ({len(errors)}):")
        parts.extend(errors)
    if not results and not errors:
        parts.append("Ei rikastuksia tallennettavaksi.")

    return "\n".join(parts)


@mcp.tool()
async def suggest_yso_tags(
    dataset_id: str,
    save: bool = False,
    ctx: Context | None = None,
) -> str:
    """Ehdota YSO-ontologian mukaisia avainsanoja datasetille.

    Analysoi datasetin otsikon, kuvauksen ja olemassaolevat avainsanat
    ja etsii vastaavat YSO-käsitteet Finto API:sta.

    Args:
        dataset_id: Datasetin ID tai nimi
        save: Jos True, tallenna ehdotukset yso_concepts-enrichmentiksi
    """
    conn = _get_conn(ctx)
    yso = _get_yso(ctx)
    if not yso:
        yso = YsoClient()

    dataset = get_dataset(conn, dataset_id)
    if not dataset:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    suggestions = await _suggest_tags(dataset, yso)

    if save and suggestions:
        import json as _json

        concepts_json = _json.dumps(
            [s.to_dict() for s in suggestions], ensure_ascii=False,
        )
        add_enrichment(
            conn,
            dataset_id=dataset["id"],
            field="yso_concepts",
            value=concepts_json,
            confidence="high",
            source_type="ai_analysis",
            source_detail="YSO auto-tagger",
        )
        conn.commit()
        return (
            format_suggestions(suggestions)
            + f"\n\nTallennettu {len(suggestions)} YSO-käsitettä enrichmentiksi."
        )

    return format_suggestions(suggestions)


@mcp.tool()
def get_enrichments_tool(dataset_id: str, ctx: Context | None = None) -> str:
    """Näytä datasetin rikastukset (crowdsourced enrichments).

    Args:
        dataset_id: Datasetin ID tai nimi
    """
    conn = _get_conn(ctx)
    enrichments = get_latest_enrichments(conn, dataset_id)

    if not enrichments:
        return f"Ei rikastuksia datasetille '{dataset_id}'."

    return format_enrichments(enrichments)


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
    from aura.quality import analyze_metadata_gaps, suggest_improvements

    conn = _get_conn(ctx)
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


@mcp.tool()
def health_check(
    source: str = "",
    limit: int = 50,
    stale_days: int = 7,
    ctx: Context | None = None,
) -> str:
    """Tarkista resurssien saatavuus (HTTP HEAD/GET).

    Args:
        source: Rajaa lähteeseen (esim. "avoindata.fi")
        limit: Tarkistettavien resurssien enimmäismäärä (oletus 50)
        stale_days: Tarkista uudelleen vain N päivää vanhat (oletus 7)
    """
    from aura.health import check_all_resources as _check_all

    conn = _get_conn(ctx)
    summary = asyncio.run(_check_all(
        conn, source=source, stale_days=stale_days, limit=limit,
    ))

    if summary.total == 0:
        return "Ei tarkistettavia resursseja."

    parts = [
        "# Resurssien saatavuustarkistus\n",
        "| Mittari | Arvo |",
        "|---------|------|",
        f"| Tarkistettu | {summary.total} |",
        f"| Saatavilla | {summary.available} |",
        f"| Ei saatavilla | {summary.unavailable} |",
        f"| Saatavuus | {summary.availability_pct:.1f}% |",
    ]
    if summary.avg_response_ms > 0:
        parts.append(f"| Vasteaika ka. | {summary.avg_response_ms:.0f} ms |")

    broken = [r for r in summary.results if not r.is_available]
    if broken:
        parts.append(f"\n## Ei saatavilla ({len(broken)})\n")
        for r in broken[:20]:
            err = r.error_message or f"HTTP {r.status_code}"
            parts.append(f"- {err}: {r.url}")

    return "\n".join(parts)


@mcp.tool()
def health_report(source: str = "", ctx: Context | None = None) -> str:
    """Näytä resurssien saatavuusraportti aiempien tarkistusten perusteella.

    Args:
        source: Rajaa lähteeseen (esim. "avoindata.fi")
    """
    from aura.health import get_health_summary, get_unavailable_resources

    conn = _get_conn(ctx)
    summary = get_health_summary(conn, source=source)

    if summary.get("total", 0) == 0:
        return (
            "Ei saatavuustarkistuksia. "
            "Aja ensin: health_check(source=..., limit=100)"
        )

    total = summary["total"]
    avail = summary.get("available", 0) or 0
    unavail = summary.get("unavailable", 0) or 0
    avg_ms = summary.get("avg_response_ms", 0) or 0
    pct = 100.0 * avail / total if total > 0 else 0

    parts = [
        "# Saatavuusraportti\n",
        "| Mittari | Arvo |",
        "|---------|------|",
        f"| Tarkistettu resursseja | {total} |",
        f"| Saatavilla | {avail} ({pct:.1f}%) |",
        f"| Ei saatavilla | {unavail} |",
        f"| Vasteaika ka. | {avg_ms:.0f} ms |",
        f"| Vanhin tarkistus | {(summary.get('oldest_check') or '')[:16]} |",
        f"| Uusin tarkistus | {(summary.get('newest_check') or '')[:16]} |",
    ]

    broken = get_unavailable_resources(conn, source=source, limit=15)
    if broken:
        parts.append(f"\n## Ei saatavilla ({len(broken)} näytetään)\n")
        for r in broken:
            err = r.get("error_message") or f"HTTP {r.get('status_code', '?')}"
            title = r.get("dataset_title", "")[:50]
            parts.append(f"- **{title}**: {err}")
            parts.append(f"  {r.get('url', '')}")

    return "\n".join(parts)


@mcp.tool()
def find_related(dataset_id: str, limit: int = 5, ctx: Context | None = None) -> str:
    """Etsi samankaltaiset datasetit avainsanojen ja organisaation perusteella.

    Args:
        dataset_id: Datasetin ID tai nimi
        limit: Tulosten enimmäismäärä (oletus 5)
    """
    conn = _get_conn(ctx)
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


# --- Research Log ---

# Category-to-enrichment-field mapping for save_session_findings
_CATEGORY_FIELD_MAP: dict[str, str] = {
    "quality": "quality_notes",
    "access": "access_instructions",
    "content": "data_fields",
    "description": "description_extended",
    "use_case": "use_case",
    "temporal": "temporal_coverage",
    "api": "api_endpoint",
    "general": "description_extended",
}

VALID_FINDING_CATEGORIES = set(_CATEGORY_FIELD_MAP.keys())


def _get_findings(ctx: Context | None) -> list[dict[str, str]]:
    """Hae session-tason findings-lista lifespan-kontekstista."""
    if ctx is not None:
        try:
            findings: list[dict[str, str]] = ctx.lifespan_context["findings"]
            return findings
        except (AttributeError, KeyError):
            pass
    # Fallback: module-level list (CLI, testit)
    return _fallback_findings


_fallback_findings: list[dict[str, str]] = []


@mcp.tool()
def log_finding(
    dataset_id: str,
    finding: str,
    category: str = "general",
    ctx: Context | None = None,
) -> str:
    """Kirjaa löydös tutkimuksen aikana. Tallentuu session lokiin.

    Kevyempi kuin enrich() — ei vaadi tarkkaa kenttä/arvo-mappingia.
    Session lopussa löydökset voi tallentaa enrichmenteiksi
    kutsumalla save_session_findings().

    Args:
        dataset_id: Datasetin ID tai nimi
        finding: Löydös vapaana tekstinä
        category: Kategoria: "quality", "access", "content", "description",
            "use_case", "temporal", "api", "general"
    """
    if category not in VALID_FINDING_CATEGORIES:
        return (
            f"Tuntematon kategoria '{category}'. "
            f"Valitse: {', '.join(sorted(VALID_FINDING_CATEGORIES))}"
        )

    findings = _get_findings(ctx)
    findings.append({
        "dataset_id": dataset_id,
        "finding": finding,
        "category": category,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })

    return (
        f"Löydös kirjattu ({len(findings)} session aikana). "
        f"Datasetti: {dataset_id}, kategoria: {category}."
    )


@mcp.tool()
def list_findings(ctx: Context | None = None) -> str:
    """Näytä session aikana kirjatut löydökset.

    Palauttaa kaikki log_finding()-kutsulla tallennetut löydökset.
    """
    findings = _get_findings(ctx)

    if not findings:
        return "Ei löydöksiä tässä sessiossa."

    # Ryhmittele datasetin mukaan
    by_dataset: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        by_dataset.setdefault(f["dataset_id"], []).append(f)

    parts = [f"# Session löydökset ({len(findings)} kpl)\n"]
    for ds_id, ds_findings in by_dataset.items():
        parts.append(f"## {ds_id}")
        for f in ds_findings:
            parts.append(f"- [{f['category']}] {f['finding']}")
        parts.append("")

    return "\n".join(parts)


@mcp.tool()
def save_session_findings(ctx: Context | None = None) -> str:
    """Tallenna session aikana kerätyt löydökset enrichmenteiksi.

    Analysoi log_finding()-kutsut, mappaa sopiviin enrichment-kenttiin,
    deduplikoi olemassaolevien kanssa ja tallentaa uudet.
    """
    conn = _get_conn(ctx)
    findings = _get_findings(ctx)

    if not findings:
        return "Ei löydöksiä tallennettavaksi."

    saved: list[str] = []
    skipped: list[str] = []

    # Ryhmittele datasetin ja kategorian mukaan
    grouped: dict[tuple[str, str], list[str]] = {}
    for f in findings:
        key = (f["dataset_id"], f["category"])
        grouped.setdefault(key, []).append(f["finding"])

    for (ds_id, category), finding_texts in grouped.items():
        field = _CATEGORY_FIELD_MAP.get(category, "description_extended")

        # Yhdistä saman kategorian löydökset
        combined = "; ".join(finding_texts) if len(finding_texts) > 1 else finding_texts[0]

        # Tarkista duplikaatit
        existing = get_latest_enrichments(conn, ds_id)
        already_exists = any(
            e.get("field") == field and e.get("value") == combined
            for e in existing
        )

        if already_exists:
            skipped.append(f"- {ds_id}/{field} (duplikaatti)")
            continue

        add_enrichment(
            conn, ds_id, field, combined,
            confidence="medium",
            source_type="mcp_session",
            source_detail="research_log",
        )
        saved.append(f"- {ds_id}/{field}")

    # Tyhjennä löydökset
    findings.clear()

    parts: list[str] = []
    if saved:
        parts.append(f"Tallennettu {len(saved)} rikastusta:")
        parts.extend(saved)
    if skipped:
        parts.append(f"\nOhitettu {len(skipped)} (duplikaatit):")
        parts.extend(skipped)
    if not saved and not skipped:
        parts.append("Ei uusia rikastuksia tallennettavaksi.")

    return "\n".join(parts)
