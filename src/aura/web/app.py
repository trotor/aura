"""FastAPI-sovellus Auran web-käyttöliittymälle."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aura.config import is_readonly
from aura.database import check_schema_freshness, get_connection, init_db

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Moduulitason tietokantayhteys (alustetaan lifespanissa)
_db_conn: sqlite3.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Hallitse tietokantayhteyttä sovelluksen elinkaaren ajan.

    Read-only-moodissa yhteys avataan ``mode=ro`` eikä migraatioita ajeta.
    Ilman tätä sovellus ei nouse etäpalvelimella lainkaan: ``init_db()``
    kirjoittaa skeemaa, ja kanta on siellä kirjoitussuojattu.
    """
    global _db_conn
    readonly = is_readonly()
    _db_conn = get_connection(check_same_thread=False, readonly=readonly)
    if not readonly:
        init_db(_db_conn)
    check_schema_freshness(_db_conn)
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


def safe_href(url: object) -> str:
    """Linkin osoite vain jos se on http(s); muuten ``#``.

    Katalogin osoitteet tulevat kolmansilta osapuolilta. Jinja escapaa
    merkit mutta ei skeemaa, joten ``javascript:``-osoite päätyisi
    sellaisenaan klikattavaksi linkiksi.
    """
    text = str(url or "").strip()
    if text.lower().startswith(("http://", "https://")):
        return text
    return "#"


def create_app(lifespan: object = lifespan) -> FastAPI:
    """Luo ja konfiguroi FastAPI-sovellus.

    Args:
        lifespan: Ohitettavissa, jotta yhdistetty ASGI-sovellus voi ketjuttaa
            tämän ja FastMCP:n lifespanin (ks. ``aura.asgi``).
    """
    # Julkisella (read-only) palvelimella ei automaattista rajapintakuvausta:
    # /docs ja /openapi.json luettelivat kaikki sisäiset reitit, eikä niitä
    # tarvita palvelun käyttöön. Omalla koneella ne ovat kehittäjän apu.
    from aura.config import is_readonly

    public = is_readonly()
    app = FastAPI(
        title="Aura",
        description="Suomalaisen avoimen datan selain",
        lifespan=lifespan,  # type: ignore[arg-type]
        docs_url=None if public else "/docs",
        redoc_url=None if public else "/redoc",
        openapi_url=None if public else "/openapi.json",
    )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Jinja2 filtterit
    from aura.constants import format_date, parse_json_list

    templates.env.filters["format_date"] = lambda v: format_date(v)
    templates.env.filters["format_date_time"] = lambda v: format_date(v, include_time=True)
    templates.env.filters["parse_json_list"] = lambda v: parse_json_list(v)
    templates.env.filters["safe_href"] = safe_href

    # Avainsana on linkki vain jos avainsanasivu tuntee sen; kohina
    # (lähteen nimi, PxWeb-kansiotunniste) näytetään tekstinä. Korteissa
    # oikeat avainsanat ensin, jotta näytettävät viisi ovat sisältöä.
    from aura.keywords import is_noise

    def browsable(keyword: object) -> bool:
        return isinstance(keyword, str) and not is_noise(keyword)

    templates.env.tests["browsable"] = browsable
    templates.env.filters["browsable_first"] = lambda kws: sorted(
        kws, key=lambda k: not browsable(k)
    )

    # Staattinen palvelu
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Rekisteröi reitit
    from aura.web.routes.api import router as api_router
    from aura.web.routes.dataset import router as dataset_router
    from aura.web.routes.index import router as index_router
    from aura.web.routes.keywords import router as keywords_router
    from aura.web.routes.map import router as map_router
    from aura.web.routes.search import router as search_router
    from aura.web.routes.view import router as view_router

    # Aseta templates kaikkiin routereihin
    for router in [
        index_router, search_router, dataset_router, map_router, view_router, keywords_router
    ]:
        router.templates = templates  # type: ignore[attr-defined]

    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(dataset_router)
    app.include_router(map_router)
    app.include_router(view_router)
    app.include_router(keywords_router)
    app.include_router(api_router, prefix="/api")

    return app
