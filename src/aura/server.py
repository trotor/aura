"""Aura MCP-server FastMCP:llä."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP

from aura.database import (
    get_connection,
    init_db,
)
from aura.yso import YsoClient, build_fts5_query


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


# Rekisteröi kaikki @mcp.tool()-funktiot alimoduuleista
import aura.tools  # noqa: E402, F401

# Re-export kaikki toolit ja apufunktiot taaksepäinyhteensopivuutta varten
# (testit importoivat suoraan: from aura.server import search, describe, ...)
from aura.tools.admin import (  # noqa: E402, F401
    harvest,
    list_formats,
    list_organizations,
    list_sources,
    probe_sizes,
    stats,
)
from aura.tools.describe import compare, describe  # noqa: E402, F401
from aura.tools.enrichment import (  # noqa: E402, F401
    batch_enrich,
    enrich,
    get_enrichments_tool,
    suggest_yso_tags,
)
from aura.tools.health import health_check, health_report  # noqa: E402, F401
from aura.tools.quality import (  # noqa: E402, F401
    quality_gaps,
    quality_overview,
    quality_ranking,
    quality_report,
)
from aura.tools.reference import (  # noqa: E402, F401
    lookup_municipality,
    populate_reference,
    reference_status,
)
from aura.tools.research import (  # noqa: E402, F401
    _fallback_findings,
    list_findings,
    log_finding,
    save_session_findings,
)
from aura.tools.search import (  # noqa: E402, F401
    _resolve_region,
    find_related,
    recommend,
    search,
    search_by_region,
    search_structured,
)
