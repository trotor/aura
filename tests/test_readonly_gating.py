"""Testit read-only-toolien gateykselle (#135)."""

from __future__ import annotations

import asyncio

from fastmcp import FastMCP

from aura.server import WRITE_TOOL_NAMES, apply_readonly_gating


def _tool_names(server: FastMCP) -> set[str]:
    tools = asyncio.run(server.list_tools())
    return {t.name for t in tools}


def _build_server() -> FastMCP:
    server = FastMCP("test")
    for name in [*WRITE_TOOL_NAMES, "search", "stats"]:
        @server.tool(name=name)
        def _fn() -> str:
            return "ok"
    return server


def test_gating_removes_write_tools_when_readonly() -> None:
    server = _build_server()
    removed = apply_readonly_gating(server, readonly=True)
    names = _tool_names(server)
    assert names == {"search", "stats"}
    assert set(removed) == set(WRITE_TOOL_NAMES)


def test_gating_keeps_all_tools_when_not_readonly() -> None:
    server = _build_server()
    removed = apply_readonly_gating(server, readonly=False)
    names = _tool_names(server)
    assert WRITE_TOOL_NAMES <= names
    assert removed == []


def test_write_tool_names_are_the_expected_set() -> None:
    assert WRITE_TOOL_NAMES == frozenset(
        {
            "harvest",
            "probe_sizes",
            "enrich",
            "batch_enrich",
            "save_session_findings",
            "populate_reference",
        }
    )
