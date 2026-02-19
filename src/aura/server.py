"""Aura MCP-server FastMCP:llä."""

from __future__ import annotations

from fastmcp import FastMCP

from aura.database import get_connection, get_dataset, get_stats, init_db, search_datasets
from aura.search import format_dataset_detail, format_dataset_summary, format_stats

mcp = FastMCP(
    "Aura",
    description="Suomalaisen avoimen datan discovery-palvelu. "
    "Hae ja ymmärrä Suomen avoimia datasettejä.",
)

_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        _conn = get_connection()
        init_db(_conn)
    return _conn


@mcp.tool()
def search(query: str, limit: int = 10) -> str:
    """Hae suomalaisia avoimia datasettejä luonnollisella kielellä.

    Args:
        query: Hakusanat (esim. "helsingin väestö", "ilmanlaatu", "joukkoliikenne")
        limit: Tulosten enimmäismäärä (oletus 10)
    """
    conn = _get_conn()
    results = search_datasets(conn, query, limit=limit)

    if not results:
        return f"Ei tuloksia haulle '{query}'. Kokeile eri hakusanoja."

    parts = [f"Löytyi {len(results)} datasettiä haulle '{query}':\n"]
    for dataset in results:
        parts.append(format_dataset_summary(dataset))
        parts.append("---")

    return "\n".join(parts)


@mcp.tool()
def describe(dataset_id: str) -> str:
    """Kuvaa yksittäinen datasetti yksityiskohtaisesti.

    Args:
        dataset_id: Datasetin ID tai nimi (esim. "helsinkikanava-open-data")
    """
    conn = _get_conn()
    dataset = get_dataset(conn, dataset_id)

    if dataset is None:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    return format_dataset_detail(dataset)


@mcp.tool()
def stats() -> str:
    """Näytä tilastot Auran tietokannasta: datasettien, organisaatioiden ja formaattien määrät."""
    conn = _get_conn()
    return format_stats(get_stats(conn))


@mcp.tool()
def list_organizations(limit: int = 20) -> str:
    """Listaa avoimen datan julkaisijat datasettien lukumäärän mukaan.

    Args:
        limit: Näytettävien organisaatioiden enimmäismäärä
    """
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT organization_title, COUNT(*) as count
        FROM datasets
        WHERE organization_title != ''
        GROUP BY organization_title
        ORDER BY count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    if not rows:
        return "Tietokanta on tyhjä. Aja ensin 'aura harvest'."

    parts = ["# Avoimen datan julkaisijat\n"]
    for row in rows:
        parts.append(f"- **{row['organization_title']}**: {row['count']} datasettiä")
    return "\n".join(parts)


@mcp.tool()
def list_formats(limit: int = 20) -> str:
    """Listaa saatavilla olevat dataformaatit resurssien lukumäärän mukaan.

    Args:
        limit: Näytettävien formaattien enimmäismäärä
    """
    conn = _get_conn()
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
