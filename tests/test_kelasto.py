"""Kelasto: raportit Tietotarjottimen artikkelista kolmella kielellä."""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from aura.database import init_db
from aura.harvesters.kelasto import KelastoHarvester, parse_reports, report_key

WF = "http://raportit.kela.fi/ibi_apps/WFServlet?IBIF_ex="
COGNOS = (
    "https://tilastot.kela.fi/ibmcognos/bi/?pathRef=.public_folders%2FRaportit%2F91%2B"
    "Etuudet%2FEtuuksien%2Bratkaisujen%2Bkooste%2B%25289101RS007%2529"
)
FI = f"""
<h2><a id="kooste"></a>Koosteraportit</h2>
<ul><li><a href="{WF}NIT100AL">Kelan etuudet 2007–</a></li>
<li><a href="{COGNOS}">Etuuksien ratkaisujen kooste 2020–</a></li></ul>
<h2>Asumisen tuet</h2><h3>Yleinen asumistuki</h3>
<ul><li><a href="{WF}NIT149AL">Maksetut yleiset asumistuet 2007–</a></li>
<li><a href="{WF}NIT149AL">kaksoislinkki</a></li></ul>
<p><a href="/avoin-data">Avoin data</a></p>
"""
EN = f"""
<h2>Housing</h2>
<ul><li><a href="{WF}NIT149AL&amp;YKIELI=E">General housing allowance paid 2007–</a></li></ul>
"""
ARTICLE = [{"content_fi": [{"content": FI}], "content_en": [{"content": EN}], "content_sv": []}]


def test_avain_on_kielesta_riippumaton() -> None:
    assert (
        report_key("http://raportit.kela.fi/ibi_apps/WFServlet?IBIF_ex=NIT149AL&amp;YKIELI=E")
        == "NIT149AL"
    )
    assert report_key(COGNOS) == "9101RS007"


def test_raportit_ja_aiheet() -> None:
    reports = parse_reports(FI)
    assert [r["key"] for r in reports] == ["NIT100AL", "9101RS007", "NIT149AL"]
    assert reports[2]["themes"] == ["Asumisen tuet", "Yleinen asumistuki"]


@pytest.mark.asyncio
async def test_keruu() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    async def fake(self: Any, client: Any, url: str, **kw: Any) -> httpx.Response:
        return httpx.Response(200, json=ARTICLE, request=httpx.Request("GET", url))

    h = KelastoHarvester(conn=conn)
    with patch.object(KelastoHarvester, "_fetch", fake):
        assert await h.harvest() == 3
    row = conn.execute(
        "SELECT title_fi, title_en, organization_title, license_id, num_resources"
        " FROM datasets WHERE id = 'kelasto-nit149al'"
    ).fetchone()
    assert row["title_en"] == "General housing allowance paid 2007–"
    assert row["organization_title"] == "Kansaneläkelaitos (Kela)"
    assert row["license_id"].lower() == "cc-by-4.0"
    assert row["num_resources"] == 2
