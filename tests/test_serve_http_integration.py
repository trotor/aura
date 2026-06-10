"""Integraatiotesti: serve --http käynnistyy ja vastaa MCP-kutsuun HTTP:n yli (#134).

Käynnistää oikean serverin aliprosessina ja yhdistää FastMCP-clientilla.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest
from fastmcp import Client


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def http_server() -> Iterator[str]:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "aura.cli", "serve", "--http",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        # Odota että portti kuuntelee
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read().decode() if proc.stdout else ""
                raise RuntimeError(f"server kuoli ennen valmistumista:\n{out}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.2)
        else:
            raise RuntimeError("server ei käynnistynyt ajoissa")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


async def test_initialize_and_list_tools_over_http(http_server: str) -> None:
    async with Client(http_server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert "search" in names


def test_health_endpoint_returns_200(http_server: str) -> None:
    health_url = http_server.replace("/mcp", "/health")
    resp = httpx.get(health_url, timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["datasets"] >= 0
