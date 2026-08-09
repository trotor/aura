"""Yhdistetty ASGI-sovellus: web-käyttöliittymä ja MCP samassa prosessissa.

Aiemmin nämä olivat kaksi erillistä ajotapaa — ``aura serve --http`` ajoi
pelkkää FastMCP:tä ja ``aura web`` pelkkää FastAPIa. Etäpalvelimella ajettiin
edellistä, joten juuri palautti 404 vaikka web-templatet olivat olemassa.

Nyt FastAPI on juuressa ja FastMCP:n ASGI-app on mountattuna polkuun
``/mcp``. Yksi kontti, yksi portti, ei nginx-muutosta.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.responses import JSONResponse

from aura.config import is_readonly
from aura.database import get_connection
from aura.server import apply_readonly_gating, health_payload, mcp
from aura.web.app import create_app
from aura.web.app import lifespan as web_lifespan

MCP_PATH = "/mcp"


def create_asgi_app(stateless_http: bool = True) -> FastAPI:
    """Rakenna yhdistetty sovellus.

    Read-only-gatettu MCP mountataan ``/mcp``:hen ja web-UI jää juureen.

    Args:
        stateless_http: Sama oletus kuin ``resolve_serve_config``:lla
            HTTP-moodissa. Tätä **täytyy** välittää eksplisiittisesti:
            ``mcp.run()`` asetti sen itse, mutta mountattu ``http_app()``
            ei peri sitä, ja ero näkyy vasta asiakkaalla istuntopakkona.
    """
    apply_readonly_gating(mcp)

    # MCP-app saa oman reittinsä polkuun /mcp, ja se mountataan TYHJÄLLÄ
    # prefiksillä. Luonteva ``app.mount("/mcp", http_app(path="/"))`` ei
    # kelpaa: Starletten Mount vastaa tarkkaan osumaan ``/mcp`` 307-ohjauksella
    # osoitteeseen ``/mcp/``, ja asiakkaat jotka eivät seuraa ohjausta
    # hajoavat. Nykyinen tuotanto tarjoilee ``/mcp``:n ilman ohjausta, joten
    # ohjauksen lisääminen olisi rikkova muutos.
    #
    # Tyhjä prefiksi nappaa vain ne polut joita FastAPIn omat reitit eivät
    # ota, koska ne on rekisteröity ensin.
    mcp_app = mcp.http_app(path=MCP_PATH, stateless_http=stateless_http)

    @asynccontextmanager
    async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Aja molempien sovellusten lifespanit.

        FastMCP:n lifespan käynnistää istuntomanagerin. Jos sitä ei aja,
        ``/mcp`` vastaa mutta istunnot eivät toimi — ja vika näkyy vasta
        asiakkaalla, ei palvelimen käynnistyksessä.
        """
        async with web_lifespan(app):
            async with mcp_app.router.lifespan_context(app):
                yield

    app = create_app(lifespan=combined_lifespan)

    # /health juureen. Mountattu MCP tarjoaa oman /health:in polussa
    # /mcp/health, mutta savutestit ja infran nginx-template odottavat
    # sitä juuresta.
    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        conn = get_connection(readonly=is_readonly())
        try:
            return JSONResponse(health_payload(conn))
        finally:
            conn.close()

    app.mount("", mcp_app)
    return app
