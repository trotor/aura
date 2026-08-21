"""Hallinta- ja ylläpitotyökalut."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.constants import format_date
from aura.database import get_all_sources, get_stats, upsert_source
from aura.limits import MAX_LIST_LIMIT, clamp
from aura.search import format_stats
from aura.server import mcp


@mcp.tool()
def stats(ctx: Context | None = None) -> str:
    """Näytä tilastot Auran tietokannasta: datasettien, organisaatioiden ja formaattien määrät."""
    conn = _server._get_conn(ctx)
    return format_stats(get_stats(conn))


@mcp.tool()
def list_organizations(limit: int = 20, ctx: Context | None = None) -> str:
    """Listaa avoimen datan julkaisijat datasettien lukumäärän mukaan.

    Args:
        limit: Näytettävien organisaatioiden enimmäismäärä
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    conn = _server._get_conn(ctx)
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
    limit = clamp(limit, MAX_LIST_LIMIT)
    conn = _server._get_conn(ctx)
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
async def harvest(source: str = "all", ctx: Context | None = None) -> str:
    """Hae datasettien metatiedot lähteistä ja tallenna tietokantaan.

    Args:
        source: Lähteen nimi (esim. "avoindata.fi", "statfin") tai "all" kaikille
    """
    from aura.harvesters import get_all_harvesters, get_harvester

    conn = _server._get_conn(ctx)
    now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")

    if source == "all":
        total = 0
        parts = []
        for name, cls in get_all_harvesters().items():
            harvester = cls(conn=conn)
            count = await harvester.harvest()
            parts.append(f"- {name}: {count} datasettiä")
            total += count
            # Päivitä sources-taulu
            src_cfg = cls.source_config()
            src_cfg["dataset_count"] = count
            src_cfg["last_harvested_at"] = now
            upsert_source(conn, src_cfg)
        conn.commit()
        # Laske laatupisteet harvestoinnin jälkeen (#127)
        from aura.quality import score_all_datasets

        qcount = score_all_datasets(conn)
        parts.insert(0, f"# Harvest valmis\n\nYhteensä {total} datasettiä (laatu: {qcount}):\n")
        return "\n".join(parts)

    try:
        cls = get_harvester(source)
    except ValueError as e:
        return str(e)

    harvester = cls(conn=conn)
    count = await harvester.harvest()
    # Päivitä sources-taulu
    src_cfg = cls.source_config()
    src_cfg["dataset_count"] = count
    src_cfg["last_harvested_at"] = now
    upsert_source(conn, src_cfg)
    conn.commit()
    # Laske laatupisteet harvestoinnin jälkeen (#127)
    from aura.quality import score_all_datasets

    qcount = score_all_datasets(conn, source=source)
    return f"Haettu {count} datasettiä lähteestä {source}. Laatupisteet: {qcount}."


@mcp.tool()
def list_sources(ctx: Context | None = None) -> str:
    """Listaa kaikki datalähteet, niiden datasettien lukumäärät ja harvestoinnin tila."""
    conn = _server._get_conn(ctx)

    # Yritä lukea sources-taulusta ensin
    db_sources = get_all_sources(conn)
    if db_sources:
        return _format_sources_from_db(db_sources)

    # Fallback: lue harvestereista
    return _format_sources_from_harvesters(conn)


def _format_sources_from_db(sources: list[dict[str, Any]]) -> str:
    """Muotoile lähteet sources-taulusta."""
    parts = ["# Datalähteet\n"]
    now = datetime.now(tz=UTC)

    for src in sources:
        name = src["name"]
        desc = src.get("description", "")
        count = src.get("dataset_count", 0)
        last_harvest = src.get("last_harvested_at", "")
        protocol = src.get("query_protocol", "")

        status = f"{count} datasettiä"
        warning = ""
        if last_harvest:
            harvest_dt = datetime.fromisoformat(last_harvest)
            days_old = (now - harvest_dt.replace(tzinfo=UTC)).days
            status += f" (viimeksi: {format_date(last_harvest, include_time=True)})"
            if days_old > 7:
                warning = f" ⚠ {days_old} pv vanha"
        elif count == 0:
            status = "ei harvestoitu"

        proto_tag = f" [{protocol}]" if protocol and protocol != "none" else ""
        parts.append(f"- **{name}**: {desc} [{status}]{proto_tag}{warning}")

    return "\n".join(parts)


def _format_sources_from_harvesters(conn: sqlite3.Connection) -> str:
    """Fallback: lue lähteet harvestereista."""
    from aura.harvesters import get_all_harvesters

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
            status += f" (viimeksi: {format_date(last_harvest, include_time=True)})"
            if days_old > 7:
                warning = f" ⚠ {days_old} pv vanha"
        elif count == 0:
            status = "ei harvestoitu"

        parts.append(f"- **{name}**: {cls.description} [{status}]{warning}")

    return "\n".join(parts)


@mcp.tool()
async def probe_sizes(source: str = "all", ctx: Context | None = None) -> str:
    """Mittaa paikkatietoaineistojen koot otoskyselyillä (WFS/WCS).

    Args:
        source: "metsakeskus", "gtk" tai "all"
    """
    from aura.spatial_probe import format_probe_report, probe_all

    probe_results = await probe_all(source=source, timeout=180.0)
    return format_probe_report(probe_results)
