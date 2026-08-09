"""Testit serve-komennon CLI-johdotukselle (#134).

Molemmat ajotavat blokkaavat, joten ne mockataan argumenttien talteenottoon.

Stdio menee yhä ``mcp.run()``:n läpi. HTTP-moodi ei enää: se tarjoilee
web-UI:n ja MCP:n samasta prosessista, joten se ajaa uvicornilla
``aura.asgi.create_asgi_app()``-sovellusta (ks. ``aura.asgi``).
"""

from __future__ import annotations

from typing import Any

import pytest

import aura.cli
import aura.server
from aura import cli


@pytest.fixture
def captured_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Nappaa ``mcp.run()``-kutsun (stdio-polku)."""
    captured: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(aura.server.mcp, "run", fake_run)
    return captured


@pytest.fixture
def captured_uvicorn(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Nappaa ``uvicorn.run()``-kutsun (HTTP-polku).

    Ilman tätä testi käynnistäisi oikean palvelimen ja jäisi roikkumaan
    ikuisesti — juuri niin kävi kun HTTP-polku vaihdettiin mcp.run():sta
    uvicorniin eikä tätä mockia ollut.
    """
    import uvicorn

    captured: dict[str, Any] = {}

    def fake_run(app: Any, **kwargs: Any) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    return captured


def test_serve_stdio_default(
    monkeypatch: pytest.MonkeyPatch, captured_run: dict[str, Any]
) -> None:
    monkeypatch.setattr("sys.argv", ["aura", "serve"])
    cli.main()
    assert captured_run == {"transport": "stdio"}


def test_serve_http_uses_uvicorn(
    monkeypatch: pytest.MonkeyPatch, captured_uvicorn: dict[str, Any]
) -> None:
    monkeypatch.setattr("sys.argv", ["aura", "serve", "--http", "--port", "8123"])
    cli.main()
    assert captured_uvicorn["port"] == 8123
    assert captured_uvicorn["host"] == "127.0.0.1"


def test_serve_http_serves_both_web_and_mcp(
    monkeypatch: pytest.MonkeyPatch, captured_uvicorn: dict[str, Any]
) -> None:
    """HTTP-moodin koko pointti: juuri on ländäri, /mcp on endpoint."""
    monkeypatch.setattr("sys.argv", ["aura", "serve", "--http"])
    cli.main()

    paths = {getattr(r, "path", None) for r in captured_uvicorn["app"].routes}
    assert "/" in paths
    assert "/health" in paths


def test_serve_http_does_not_call_mcp_run(
    monkeypatch: pytest.MonkeyPatch,
    captured_run: dict[str, Any],
    captured_uvicorn: dict[str, Any],
) -> None:
    """Vartija: jos HTTP-polku palaa mcp.run():iin, web-UI katoaa juuresta."""
    monkeypatch.setattr("sys.argv", ["aura", "serve", "--http"])
    cli.main()
    assert captured_run == {}
    assert captured_uvicorn
