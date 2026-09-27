"""find_data: tekstiyhteenvedon määrärivi ei väitä sivun kokoa kokonaismääräksi.

Ulkoinen arvio 27.9.2026: rivi "10 aineistoa haulle ..." luettiin
kokonaismääräksi, vaikka ``count`` on sivun koko, ja tekstissä listattiin
vain kolme ensimmäistä.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastmcp import Client

from aura.database import init_db, upsert_dataset
from aura.models import Dataset
from aura.server import apply_tool_profile, mcp, reset_tool_profile
from aura.tools.find import _count_line


def test_maararivi() -> None:
    assert _count_line(2, "x", 0, False) == "2 aineistoa haulle 'x'."
    assert _count_line(7, "x", 0, False) == (
        "7 aineistoa haulle 'x' (näytetään 3, kaikki 7 rakenteisessa vastauksessa)."
    )
    assert _count_line(10, "x", 20, True) == (
        "Ainakin 10 aineistoa haulle 'x' (näytetään 3, kaikki 10 rakenteisessa "
        "vastauksessa; lisää: offset=30)."
    )


@pytest.fixture()
def public() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_db(c)
    for i in range(6):
        upsert_dataset(
            c,
            Dataset(
                id=f"kirjasto-{i}",
                name=f"kirjasto-{i}",
                title=f"Kirjastojen lainaukset {i}",
                title_fi=f"Kirjastojen lainaukset {i}",
                keywords_fi=["kirjasto", "lainaukset"],
                source="avoindata.fi",
            ),
        )
    c.commit()
    apply_tool_profile(mcp, profile="public")
    try:
        with patch("aura.server._get_conn", return_value=c):
            yield c
    finally:
        reset_tool_profile(mcp)


async def _find(args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    async with Client(mcp) as client:
        result = await client.call_tool("find_data", args, raise_on_error=False)
    assert isinstance(result.structured_content, dict)
    return result.structured_content, result.content[0].text.splitlines()  # type: ignore[union-attr]


async def test_taysi_sivu_kertoo_etta_lisaa_voi_olla(public: sqlite3.Connection) -> None:
    data, lines = await _find({"query": "kirjasto", "limit": 5})
    assert data["count"] == 5 and data["may_have_more"] is True
    assert lines[0].startswith("Ainakin 5 aineistoa haulle 'kirjasto' (näytetään 3")
    assert "lisää: offset=5" in lines[0]
    assert len(lines) == 4


async def test_vajaa_sivu_ei_lupaa_lisaa(public: sqlite3.Connection) -> None:
    data, lines = await _find({"query": "kirjasto", "limit": 50})
    assert data["count"] == 6 and data["may_have_more"] is False
    assert lines[0] == (
        "6 aineistoa haulle 'kirjasto' (näytetään 3, kaikki 6 rakenteisessa vastauksessa)."
    )
