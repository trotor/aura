"""Testit serve-komennon CLI-johdotukselle (#134).

``mcp.run()`` blokkaa, joten se mockataan kwargsien talteenottoon — testi
varmistaa että argumentit kulkevat resoluution läpi oikein run-kutsuun.
"""

from __future__ import annotations

from typing import Any

import pytest

import aura.server
from aura import cli


@pytest.fixture
def captured_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(aura.server.mcp, "run", fake_run)
    return captured


def test_serve_stdio_default(
    monkeypatch: pytest.MonkeyPatch, captured_run: dict[str, Any]
) -> None:
    monkeypatch.setattr("sys.argv", ["aura", "serve"])
    cli.main()
    assert captured_run == {"transport": "stdio"}


def test_serve_http_flag(
    monkeypatch: pytest.MonkeyPatch, captured_run: dict[str, Any]
) -> None:
    monkeypatch.setattr("sys.argv", ["aura", "serve", "--http", "--port", "8123"])
    cli.main()
    assert captured_run["transport"] == "http"
    assert captured_run["port"] == 8123
    assert captured_run["host"] == "127.0.0.1"
    assert captured_run["path"] == "/mcp"
    assert captured_run["stateless_http"] is True
