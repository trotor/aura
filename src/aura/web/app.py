"""FastAPI-sovellus Auran web-käyttöliittymälle."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aura.database import get_connection, init_db

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Moduulitason tietokantayhteys (alustetaan lifespanissa)
_db_conn: sqlite3.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Hallitse tietokantayhteyttä sovelluksen elinkaaren ajan."""
    global _db_conn
    _db_conn = get_connection(check_same_thread=False)
    init_db(_db_conn)
    try:
        yield
    finally:
        if _db_conn:
            _db_conn.close()
            _db_conn = None


def get_db(request: Request) -> sqlite3.Connection:
    """Hae tietokantayhteys."""
    assert _db_conn is not None, "Tietokantaa ei ole alustettu"
    return _db_conn


def create_app() -> FastAPI:
    """Luo ja konfiguroi FastAPI-sovellus."""
    app = FastAPI(
        title="Aura",
        description="Suomalaisen avoimen datan selain",
        lifespan=lifespan,
    )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Jinja2 filtterit
    from aura.constants import format_date, parse_json_list

    templates.env.filters["format_date"] = lambda v: format_date(v)
    templates.env.filters["format_date_time"] = lambda v: format_date(v, include_time=True)
    templates.env.filters["parse_json_list"] = lambda v: parse_json_list(v)

    # Staattinen palvelu
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Rekisteröi reitit
    from aura.web.routes.api import router as api_router
    from aura.web.routes.dataset import router as dataset_router
    from aura.web.routes.index import router as index_router
    from aura.web.routes.map import router as map_router
    from aura.web.routes.search import router as search_router
    from aura.web.routes.view import router as view_router

    # Aseta templates kaikkiin routereihin
    for router in [index_router, search_router, dataset_router, map_router, view_router]:
        router.templates = templates  # type: ignore[attr-defined]

    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(dataset_router)
    app.include_router(map_router)
    app.include_router(view_router)
    app.include_router(api_router, prefix="/api")

    return app
