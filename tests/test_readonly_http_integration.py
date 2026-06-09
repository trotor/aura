"""Integraatiotesti: read-only-remote piilottaa kirjoittavat toolit (#135)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import pytest
from fastmcp import Client

from aura.server import WRITE_TOOL_NAMES


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def readonly_server() -> Iterator[str]:
    port = _free_port()
    env = {**os.environ, "AURA_READONLY": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "aura.cli", "serve", "--http",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
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


async def test_write_tools_absent_read_tools_present(readonly_server: str) -> None:
    async with Client(readonly_server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    # Kirjoittavat toolit eivät saa näkyä
    assert names.isdisjoint(WRITE_TOOL_NAMES), names & WRITE_TOOL_NAMES
    # Lukutoolit toimivat normaalisti
    assert "search" in names
    assert "stats" in names
