"""Kiinteistötunnus aluerajauksena: jäsennys, rajojen haku ja query_source.

Tavoite: paikallinen käyttäjä kysyy kiinteistötunnuksella paikkatietoa
("mitä puustoa tilalla 174-401-3-6 on?"). Tunnus muutetaan kiinteistön
palstojen rajoiksi, ja niillä rajataan WFS-kysely.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from aura import fetch, kiinteisto
from aura.kiinteisto import Parcel, format_tunnus, parse_tunnus


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("09104399030004", "09104399030004"),
        ("91-43-9903-4", "09104399030004"),
        ("092-072-0032-0006", "09207200320006"),
        ("174-401-3-6", "17440100030006"),
        (" 174-401-3-6 ", "17440100030006"),
        ("174 401 3 6", "17440100030006"),
    ],
)
def test_tunnus_normalisoidaan(text: str, expected: str) -> None:
    assert parse_tunnus(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "00100",
        "091",
        "Helsinki",
        "L4133A",
        "1,2,3,4",
        "1234-401-3-6",
        "174-401-3",
        "123456789012345",
        "\uff11\uff17\uff14-401-3-6",  # täysleveät numerot
    ],
)
def test_muut_aluemuodot_eivat_ole_tunnuksia(text: str) -> None:
    assert parse_tunnus(text) is None


def test_maaraala_hylataan_selkeasti() -> None:
    with pytest.raises(ValueError, match="määräala"):
        parse_tunnus("091-043-9903-0004-M601")


def test_lyhyt_muoto_nayttoon() -> None:
    assert format_tunnus("17440100030006") == "174-401-3-6"
    assert format_tunnus("09104399030004") == "91-43-9903-4"


def _geojson(*features: list[list[float]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
                "properties": {"kiinteistotunnus": "09104399030004"},
            }
            for ring in features
        ],
    }


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, body: dict[str, Any]) -> None:
        self.body = body
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.body, request=request)


@pytest.fixture(autouse=True)
def _ei_paikallista_indeksia(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AURA_KIINTEISTOT_DB", str(tmp_path / "ei-ole.sqlite"))


@pytest.mark.asyncio
async def test_helsingin_palstat_ja_bboxit() -> None:
    body = _geojson(
        [[100.0, 200.0], [110.0, 200.0], [110.0, 230.0], [100.0, 200.0]],
        [[5000.0, 6000.0], [5004.0, 6000.0], [5004.0, 6002.0], [5000.0, 6000.0]],
    )
    transport = _Transport(body)
    result = await kiinteisto.find_parcels("09104399030004", transport=transport)
    assert result.provider == "Helsingin kaupunki (kartta.hel.fi)"
    assert result.parcels == [
        Parcel(bbox=(100.0, 200.0, 110.0, 230.0)),
        Parcel(bbox=(5000.0, 6000.0, 5004.0, 6002.0)),
    ]
    params = transport.requests[0].url.params
    assert params["typeNames"] == "avoindata:Kiinteisto_alue"
    assert params["CQL_FILTER"] == "kiinteistotunnus='09104399030004'"
    assert params["srsName"] == "EPSG:3067"


@pytest.mark.asyncio
async def test_kunnalla_ilman_palvelua_neuvotaan_lataamaan() -> None:
    result = await kiinteisto.find_parcels("17440100030006")
    assert result.parcels == []
    assert result.provider is None
    assert "aura parcels 174" in result.hint


# --- query_source ---------------------------------------------------------


@pytest.fixture()
def conn() -> Iterator[sqlite3.Connection]:
    from aura.database import init_db, upsert_dataset
    from aura.models import Dataset, Resource
    from aura.server import apply_tool_profile, mcp, reset_tool_profile

    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_db(c)
    upsert_dataset(
        c,
        Dataset(
            id="metsakeskus-stand",
            name="metsakeskus-stand",
            title="Metsävarakuviot",
            source="metsakeskus",
            resources=[
                Resource(
                    id="s-wfs",
                    name="WFS",
                    format="WFS",
                    url="https://avoin.metsakeskus.fi/rajapinnat/v1/stand/ows",
                )
            ],
        ),
    )
    c.commit()
    apply_tool_profile(mcp, profile="public")
    try:
        with patch("aura.server._get_conn", return_value=c):
            yield c
    finally:
        reset_tool_profile(mcp)


async def _call(args: dict[str, Any]) -> dict[str, Any]:
    from fastmcp import Client

    from aura.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool("query_source", args, raise_on_error=False)
    data = result.structured_content
    assert isinstance(data, dict)
    return data


async def test_query_source_rajaa_jokaisen_palstan_erikseen(conn: sqlite3.Connection) -> None:
    async def fake_parcels(tunnus: str, **_: Any) -> kiinteisto.Lookup:
        return kiinteisto.Lookup(
            tunnus=tunnus,
            provider="Testi",
            parcels=[
                Parcel(bbox=(0.0, 0.0, 10.0, 10.0)),
                Parcel(bbox=(500.0, 500.0, 510.0, 510.0)),
            ],
        )

    seen: list[Any] = []

    async def fake_wfs(url: str, filters: Any, max_rows: int, bbox: Any, **kw: Any) -> fetch.Table:
        seen.append(bbox)
        table = fetch.Table(protocol="wfs", request_url=url, layer="v1:stand")
        rows = [{"STANDNUMBER": int(bbox[0])}, {"STANDNUMBER": 7}]
        return fetch._finish(table, ["STANDNUMBER"], rows, None, 2)

    with (
        patch.object(kiinteisto, "find_parcels", fake_parcels),
        patch.object(fetch, "fetch_wfs", fake_wfs),
    ):
        data = await _call({"dataset_id": "metsakeskus-stand", "area": "174-401-3-6"})
    assert seen == [(0.0, 0.0, 10.0, 10.0), (500.0, 500.0, 510.0, 510.0)]
    # Kahdessa rajauksessa sama kuvio (7) näkyy vain kerran.
    assert [r["STANDNUMBER"] for r in data["rows"]] == [0, 7, 500]
    assert data["notes"][0] == "Aluerajaus: kiinteistö 174-401-3-6, 2 palstaa (Testi)"
    assert any("naapuri" in n for n in data["notes"])


async def test_query_source_ilman_rajoja_kertoo_miten_edetaan(conn: sqlite3.Connection) -> None:
    async def fake_parcels(tunnus: str, **_: Any) -> kiinteisto.Lookup:
        return kiinteisto.Lookup(tunnus=tunnus, provider=None, parcels=[], hint="aura parcels 174")

    with patch.object(kiinteisto, "find_parcels", fake_parcels):
        data = await _call({"dataset_id": "metsakeskus-stand", "area": "174-401-3-6"})
    assert data["error"]["code"] == "property_geometry_unavailable"
    assert "aura parcels 174" in data["error"]["hint"]


async def test_query_source_maaraala_on_selkea_virhe(conn: sqlite3.Connection) -> None:
    data = await _call({"dataset_id": "metsakeskus-stand", "area": "091-043-9903-0004-M601"})
    assert data["error"]["code"] == "unknown_area"
    assert "määräala" in data["error"]["message"]
