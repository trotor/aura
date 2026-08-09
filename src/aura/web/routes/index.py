"""Etusivu / dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from aura.database import get_stats
from aura.web.app import get_db

router = APIRouter()


def public_base_url(request: Request) -> str:
    """Palauta julkinen juuriosoite kauttaviivoineen.

    ``request.base_url`` kertoo skeeman jolla pyyntö saapui *sovellukseen*,
    ei sitä jolla käyttäjä saapui. Käänteisproxyn takana se on aina http,
    joten ländärin kopioitava MCP-konfiguraatio olisi väärä: asiakas
    yrittäisi http:tä ja päätyisi uudelleenohjaukseen.

    Luetaan siis ``X-Forwarded-Proto`` jos proxy sen asetti. Tämä ei nojaa
    uvicornin ``--forwarded-allow-ips``-asetukseen, joten se toimii myös
    silloin kun proxy näkyy kontista muuna kuin 127.0.0.1:nä.
    """
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    base = str(request.base_url)
    if forwarded in ("http", "https"):
        scheme, _, rest = base.partition("://")
        if scheme != forwarded:
            base = f"{forwarded}://{rest}"
    return base


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
        {
            "stats": stats,
            "sources": [dict(s) for s in sources],
            "base_url": public_base_url(request),
        },
    )
