"""Etusivu / dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from aura.database import get_stats
from aura.web.app import get_db

router = APIRouter()


@router.get("/")
async def index(request: Request) -> object:
    """Dashboard-etusivu tilastoineen."""
    conn = get_db(request)
    stats = get_stats(conn)

    # Lähdekohtaiset tiedot
    sources = conn.execute(
        """
        SELECT source, COUNT(*) as count, MAX(harvested_at) as last_harvest
        FROM datasets
        GROUP BY source
        ORDER BY count DESC
        """
    ).fetchall()

    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"stats": stats, "sources": [dict(s) for s in sources]},
    )
