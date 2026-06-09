"""Serve-komennon transport-konfiguraation resoluutio (#134).

Eristää päätöslogiikan (stdio vs. streamable HTTP, host/portti) blokkaavasta
``mcp.run()``-kutsusta, jotta se on yksikkötestattavissa.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_PATH = "/mcp"


@dataclass(frozen=True)
class ServeConfig:
    """Resoluoitu serve-konfiguraatio.

    ``run_args()`` palauttaa suoraan ``mcp.run(**kwargs)``-yhteensopivan dictin.
    """

    transport: str
    host: str | None = None
    port: int | None = None
    path: str | None = None
    stateless_http: bool = False

    def run_args(self) -> dict[str, Any]:
        if self.transport == "stdio":
            return {"transport": "stdio"}
        return {
            "transport": self.transport,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "stateless_http": self.stateless_http,
        }


def resolve_serve_config(
    *,
    http: bool,
    host: str | None = None,
    port: int | None = None,
    env: Mapping[str, str] | None = None,
) -> ServeConfig:
    """Resoluoi serve-konfiguraatio argumenteista ja ympäristömuuttujista.

    Eksplisiittiset argumentit voittavat env-muuttujat, jotka voittavat oletukset.
    """
    if env is None:
        env = os.environ

    if not http:
        return ServeConfig(transport="stdio")

    resolved_host = host or env.get("AURA_HTTP_HOST") or DEFAULT_HOST

    if port is not None:
        resolved_port = port
    elif env.get("AURA_HTTP_PORT"):
        resolved_port = int(env["AURA_HTTP_PORT"])
    else:
        resolved_port = DEFAULT_PORT

    return ServeConfig(
        transport="http",
        host=resolved_host,
        port=resolved_port,
        path=DEFAULT_PATH,
        stateless_http=True,
    )
