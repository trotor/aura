"""Aura MCP-server FastMCP:llä."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC

from fastmcp import FastMCP

from aura.database import (
    find_related_datasets,
    get_connection,
    get_dataset,
    get_datasets_by_ids,
    get_stats,
    init_db,
    search_datasets,
)
from aura.search import format_dataset_detail, format_dataset_summary, format_stats

mcp = FastMCP(
    "Aura",
    instructions="Suomalaisen avoimen datan discovery-palvelu. "
    "Hae ja ymmärrä Suomen avoimia datasettejä.",
)

_conn = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = get_connection()
        init_db(_conn)
    return _conn


@mcp.tool()
def search(
    query: str,
    limit: int = 10,
    offset: int = 0,
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
) -> str:
    """Hae suomalaisia avoimia datasettejä luonnollisella kielellä.

    Args:
        query: Hakusanat (esim. "helsingin väestö", "ilmanlaatu", "joukkoliikenne")
        limit: Tulosten enimmäismäärä (oletus 10)
        offset: Ohita ensimmäiset N tulosta (sivutus)
        source: Suodata lähteen mukaan (esim. "avoindata.fi", "hri.fi", "statfin")
        format: Suodata formaatin mukaan (esim. "CSV", "JSON", "GeoJSON")
        organization: Suodata organisaation mukaan (osa nimestä riittää)
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted")
    """
    conn = _get_conn()
    results = search_datasets(
        conn, query, limit=limit, offset=offset,
        source=source, fmt=format, organization=organization,
        access_level=access_level,
    )

    if not results:
        return f"Ei tuloksia haulle '{query}'. Kokeile eri hakusanoja tai suodattimia."

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


@mcp.tool()
def harvest(source: str = "all") -> str:
    """Hae datasettien metatiedot lähteistä ja tallenna tietokantaan.

    Args:
        source: Lähteen nimi (esim. "avoindata.fi", "statfin") tai "all" kaikille
    """
    from aura.harvesters import get_all_harvesters, get_harvester

    if source == "all":
        total = 0
        parts = []
        for name, cls in get_all_harvesters().items():
            harvester = cls(conn=_get_conn())
            count = asyncio.run(harvester.harvest())
            parts.append(f"- {name}: {count} datasettiä")
            total += count
        parts.insert(0, f"# Harvest valmis\n\nYhteensä {total} datasettiä:\n")
        return "\n".join(parts)

    try:
        cls = get_harvester(source)
    except ValueError as e:
        return str(e)

    harvester = cls(conn=_get_conn())
    count = asyncio.run(harvester.harvest())
    return f"Haettu {count} datasettiä lähteestä {source}."


@mcp.tool()
def list_sources() -> str:
    """Listaa kaikki datalähteet, niiden datasettien lukumäärät ja harvestoinnin tila."""
    from datetime import datetime

    from aura.harvesters import get_all_harvesters

    conn = _get_conn()
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
def probe_sizes(source: str = "all") -> str:
    """Mittaa paikkatietoaineistojen koot otoskyselyillä (WFS/WCS).

    Args:
        source: "metsakeskus", "gtk" tai "all"
    """
    from aura.spatial_probe import format_probe_report, probe_all

    probe_results = asyncio.run(probe_all(source=source, timeout=180.0))
    return format_probe_report(probe_results)


@mcp.tool()
def search_structured(
    query: str,
    limit: int = 10,
    offset: int = 0,
    source: str = "",
    format: str = "",
    organization: str = "",
    access_level: str = "",
) -> str:
    """Hae datasettejä ja palauta rakenteellinen JSON tekoälyagenteille.

    Palauttaa hakutulokset JSON-muodossa koneluettavaa jatkokäsittelyä varten.

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

    conn = _get_conn()
    results = search_datasets(
        conn, query, limit=limit, offset=offset,
        source=source, fmt=format, organization=organization,
        access_level=access_level,
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

        structured.append({
            "id": d.get("id", ""),
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
        })

    return json.dumps(
        {"query": query, "count": len(structured), "offset": offset, "results": structured},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def recommend(topic: str, limit: int = 5) -> str:
    """Suosittele parhaita datasettejä aiheesta.

    Etsii datasettejä ja järjestää ne relevanssin, tuoreuden ja resurssimäärän mukaan.

    Args:
        topic: Aihe tai teema (esim. "liikenne Helsinki", "ilmastonmuutos")
        limit: Suositusten enimmäismäärä (oletus 5)
    """
    conn = _get_conn()
    # Hae enemmän tuloksia kuin limit, jotta voidaan järjestää uudelleen
    results = search_datasets(conn, topic, limit=limit * 3)

    if not results:
        return f"Ei datasettejä aiheesta '{topic}'. Kokeile eri hakusanoja."

    # Pisteytä: relevanssi (rank, pienempi = parempi), resurssimäärä, tuoreus
    scored = []
    for d in results:
        rank = abs(d.get("rank", 0))
        num_res = d.get("num_resources", 0) or 0
        size = d.get("estimated_size_bytes", 0) or 0
        # Normalisoi pisteeksi: pienempi rank = parempi
        score = rank - (num_res * 0.1) - (1 if size > 0 else 0)
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
def compare(dataset_ids: list[str]) -> str:
    """Vertaile datasettejä rinnakkain.

    Args:
        dataset_ids: Lista datasetin ID:istä tai nimistä (2–5 kpl)
    """
    if len(dataset_ids) < 2:
        return "Anna vähintään 2 datasetin ID:tä vertailua varten."
    if len(dataset_ids) > 5:
        return "Vertaile korkeintaan 5 datasettiä kerrallaan."

    import json

    conn = _get_conn()
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
def find_related(dataset_id: str, limit: int = 5) -> str:
    """Etsi samankaltaiset datasetit avainsanojen ja organisaation perusteella.

    Args:
        dataset_id: Datasetin ID tai nimi
        limit: Tulosten enimmäismäärä (oletus 5)
    """
    conn = _get_conn()
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
