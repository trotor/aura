"""query_source WFS:llä: kerroksen valinta, postinumerorajaus ja kerroslistaus.

Ulkoinen arvio 27.9.2026: Paavo-aineiston WFS-resurssilla ei ole kerrosta
URL:ssa, joten kysely palautti palvelun ensimmäisen kerroksen
(postinumerorajat) eikä tunnuslukuja — eikä vastaus kertonut, että muita
kerroksia on. Postinumeroa ei voinut antaa aluerajaukseksi lainkaan.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httpx
import jsonschema
import pytest
from fastmcp import Client

from aura import fetch
from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import apply_tool_profile, mcp, reset_tool_profile
from aura.wfs import Features, fetch_features, type_name_from_url, with_layer

PAAVO = "https://geo.stat.fi/geoserver/postialue/wfs"
LAYERS = ["postialue:pno", "postialue:pno_tilasto_2026", "postialue:pno_tilasto_2025"]


def test_with_layer_korvaa_urlin_kerroksen() -> None:
    url = with_layer(f"{PAAVO}?service=WFS&typeName=postialue:pno", "postialue:pno_tilasto")
    q = parse_qs(urlsplit(url).query)
    assert q["typeNames"] == ["postialue:pno_tilasto"]
    assert "typeName" not in q and q["service"] == ["WFS"]
    assert type_name_from_url(url) == "postialue:pno_tilasto"
    assert type_name_from_url(PAAVO) is None


def test_etunollallinen_koodi_pysyy_merkkijonona() -> None:
    assert fetch._num("00100") == "00100"
    assert fetch._num("091") == "091"
    assert fetch._num("0") == 0
    assert fetch._num("18492") == 18492
    assert fetch._num("-5") == -5


def _caps(layers: list[str]) -> str:
    types = "".join(f"<FeatureType><Name>{n}</Name></FeatureType>" for n in layers)
    return (
        '<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0">'
        f"<FeatureTypeList>{types}</FeatureTypeList></wfs:WFS_Capabilities>"
    )


@pytest.mark.asyncio
async def test_http_400_ilman_kerrosta_neuvotellaan_ja_kerrokset_kerrotaan() -> None:
    """geo.stat.fi vastaa kerroksettomaan GetFeatureen HTTP 400:lla."""
    seen: list[dict[str, str]] = []

    async def _get(url: str, params: dict[str, str] | None = None, **_: Any) -> Any:
        params = params or {}
        seen.append(params)
        resp = MagicMock()
        if params.get("request") == "GetCapabilities":
            resp.raise_for_status = MagicMock()
            resp.text = _caps(LAYERS)
            return resp
        if "typeNames" not in params:
            request = httpx.Request("GET", url)
            response = httpx.Response(400, request=request)
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("400", request=request, response=response)
            )
            return resp
        resp.raise_for_status = MagicMock()
        resp.text = (
            '{"type":"FeatureCollection","totalFeatures":1,'
            '"features":[{"geometry_name":"geom","properties":{"posti_alue":"00100"}}]}'
        )
        return resp

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("aura.wfs.httpx.AsyncClient", return_value=client):
        result = await fetch_features(PAAVO, 1)
    assert result.error is None
    assert result.type_name == "postialue:pno"
    assert result.feature_types == LAYERS
    assert seen[-1]["typeNames"] == "postialue:pno"


def _feature(headers: list[str], values: list[str], **kw: Any) -> Features:
    return Features(headers=headers, rows=[values], total="1", geometry_name="geom", **kw)


@pytest.mark.asyncio
async def test_postinumero_suodatetaan_kerroksen_postinumerokentalla() -> None:
    calls: list[tuple[str, int, str | None]] = []

    async def fake(url: str, max_rows: int, **kw: Any) -> Features:
        calls.append((url, max_rows, kw.get("cql_filter")))
        return _feature(
            ["postinumeroalue", "nimi", "he_vakiy"], ["00100", "Helsinki keskusta", "18492"]
        )

    with patch("aura.wfs.fetch_features", fake):
        table = await fetch.fetch_wfs(
            PAAVO, None, 5, None, layer="postialue:pno_tilasto_2026", postal_code="00100"
        )
    assert table.error is None
    assert table.rows == [
        {"postinumeroalue": "00100", "nimi": "Helsinki keskusta", "he_vakiy": 18492}
    ]
    assert calls[-1][2] == "postinumeroalue='00100'"
    assert type_name_from_url(calls[-1][0]) == "postialue:pno_tilasto_2026"
    assert table.layer == "postialue:pno_tilasto_2026"
    # Kerros annettiin: ei kerroslistausta.
    assert not any("kerrosta" in n for n in table.notes)


@pytest.mark.asyncio
async def test_postinumero_ilman_postinumerokenttaa_on_selkea_virhe() -> None:
    async def fake(url: str, max_rows: int, **kw: Any) -> Features:
        return _feature(
            ["id", "avi", "nimi"],
            ["1", "1", "Etelä-Suomi"],
            feature_types=["t:avi1000k", "t:kunta1000k"],
            type_name="t:avi1000k",
        )

    with patch("aura.wfs.fetch_features", fake):
        table = await fetch.fetch_wfs(PAAVO, None, 5, None, postal_code="00100")
    assert table.error_code == "area_not_supported"
    assert "00100 tunnistettiin" in (table.error or "")
    assert "t:avi1000k" in (table.error or "")
    assert table.layers == ["t:avi1000k", "t:kunta1000k"]


@pytest.mark.asyncio
async def test_monikerroksinen_palvelu_kertoo_kerrokset() -> None:
    async def fake(url: str, max_rows: int, **kw: Any) -> Features:
        return _feature(["posti_alue"], ["00100"], feature_types=LAYERS, type_name="postialue:pno")

    with patch("aura.wfs.fetch_features", fake):
        table = await fetch.fetch_wfs(PAAVO, None, 5, None)
    assert table.layers == LAYERS
    assert table.layer == "postialue:pno"
    note = next(n for n in table.notes if "kerrosta" in n)
    assert "käytettiin ensimmäistä (postialue:pno)" in note
    assert "postialue:pno_tilasto_2026" in note


@pytest.mark.asyncio
async def test_suodatinarvon_lainausmerkki_escapetaan() -> None:
    seen: list[str | None] = []

    async def fake(url: str, max_rows: int, **kw: Any) -> Features:
        seen.append(kw.get("cql_filter"))
        return _feature(["nimi"], ["x"])

    with patch("aura.wfs.fetch_features", fake):
        await fetch.fetch_wfs(PAAVO, {"nimi": ["Pyhä'joki"]}, 5, None)
    assert seen[-1] == "nimi='Pyhä''joki'"


# --- Työkalupinta -------------------------------------------------------


@pytest.fixture()
def public() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_db(c)
    upsert_dataset(
        c,
        Dataset(
            id="statfin-geo-paavo",
            name="statfin-geo-paavo",
            title="Paavo",
            organization_title="Tilastokeskus",
            license_title="CC BY 4.0",
            source="statfin-geo",
            resources=[
                Resource(id="p-wfs", name="Paavo WFS", format="WFS", url=PAAVO),
                Resource(id="p-csv", name="CSV", format="CSV", url="https://x/p.csv"),
            ],
        ),
    )
    c.execute(
        "INSERT INTO ref_postal_codes (code, name_fi, name_sv, municipality_code)"
        " VALUES ('00100', 'Helsinki keskusta - Etu-Töölö', 'Helsingfors centrum', '091')"
    )
    c.commit()
    apply_tool_profile(mcp, profile="public")
    try:
        with patch("aura.server._get_conn", return_value=c):
            yield c
    finally:
        reset_tool_profile(mcp)


async def _call(args: dict[str, Any]) -> dict[str, Any]:
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        result = await client.call_tool("query_source", args, raise_on_error=False)
    data = result.structured_content
    assert isinstance(data, dict)
    jsonschema.validate(data, tools["query_source"].output_schema)
    assert len(result.content[0].text.splitlines()) <= 5  # type: ignore[union-attr]
    return data


async def test_query_source_valittaa_layerin_ja_postinumeron(
    public: sqlite3.Connection,
) -> None:
    seen: dict[str, Any] = {}

    async def fake_wfs(url: str, filters: Any, max_rows: int, bbox: Any, **kw: Any) -> fetch.Table:
        seen.update(kw, bbox=bbox)
        table = fetch.Table(protocol="wfs", request_url=url, layer=kw["layer"])
        return fetch._finish(table, ["postinumeroalue"], [{"postinumeroalue": "00100"}], None, 1)

    with patch.object(fetch, "fetch_wfs", fake_wfs):
        data = await _call(
            {
                "dataset_id": "statfin-geo-paavo",
                "area": "00100",
                "layer": "postialue:pno_tilasto_2026",
            }
        )
    assert seen == {
        "layer": "postialue:pno_tilasto_2026",
        "postal_code": "00100",
        "bbox": None,
        "layer_hints": ["Paavo"],
    }
    assert data["resource"]["layer"] == "postialue:pno_tilasto_2026"
    assert data["notes"][0].startswith("Aluerajaus: postinumeroalue 00100 Helsinki")
    assert "layers" not in data


async def test_query_source_ehdottaa_kerrosta_kun_palvelu_valitsi(
    public: sqlite3.Connection,
) -> None:
    async def fake_wfs(url: str, filters: Any, max_rows: int, bbox: Any, **kw: Any) -> fetch.Table:
        table = fetch.Table(protocol="wfs", request_url=url, layers=LAYERS, layer=LAYERS[0])
        return fetch._finish(table, ["posti_alue"], [{"posti_alue": "00100"}], None, 3018)

    with patch.object(fetch, "fetch_wfs", fake_wfs):
        data = await _call({"dataset_id": "statfin-geo-paavo"})
    assert data["layers"] == LAYERS
    assert data["next_actions"][0] == {
        "tool": "query_source",
        "args": {"dataset_id": "statfin-geo-paavo", "resource_index": 0, "layer": LAYERS[0]},
        "why": "Kerros valittiin automaattisesti (ensimmäinen); vaihda layer, vaihtoehdot: layers",
    }


async def test_query_source_postinumerovirhe_listaa_kerrokset(
    public: sqlite3.Connection,
) -> None:
    async def fake_wfs(url: str, filters: Any, max_rows: int, bbox: Any, **kw: Any) -> fetch.Table:
        return fetch.Table(
            protocol="wfs",
            request_url=url,
            error_code="area_not_supported",
            error="Postinumero 00100 tunnistettiin, mutta kerroksessa x ei ole postinumerokenttää",
            layers=LAYERS,
            layer=LAYERS[0],
        )

    with patch.object(fetch, "fetch_wfs", fake_wfs):
        data = await _call({"dataset_id": "statfin-geo-paavo", "area": "00100"})
    assert data["error"]["code"] == "area_not_supported"
    assert "postialue:pno_tilasto_2026" in data["error"]["hint"]
    assert data["layers"] == LAYERS


async def test_layer_muulla_protokollalla_ohitetaan_huomautuksella(
    public: sqlite3.Connection,
) -> None:
    async def fake_csv(url: str, filters: Any, columns: Any, max_rows: int) -> fetch.Table:
        return fetch._finish(fetch.Table(protocol="csv"), ["a"], [{"a": 1}], None, 1)

    with patch.object(fetch, "fetch_csv", fake_csv):
        data = await _call({"dataset_id": "statfin-geo-paavo", "resource_index": 1, "layer": "x"})
    assert any("layer koskee vain WFS" in n for n in data["notes"])
    assert "layer" not in data["resource"]


def test_nimetty_taso_ennen_oletustasoa() -> None:
    """Paavo: tilastotaso (typeName) valitaan ennen rajatasoa (ei tasoa URL:ssa)."""
    from aura.preview import _pick_resource

    resources = [
        {"format": "WFS", "url": "https://geo.stat.fi/geoserver/postialue/wfs"},
        {"format": "WMS", "url": "https://geo.stat.fi/geoserver/postialue/wms"},
        {
            "format": "WFS",
            "url": "https://geo.stat.fi/geoserver/postialue/wfs?typeName=postialue:pno_tilasto_2026",
        },
    ]
    assert "pno_tilasto" in _pick_resource(resources)["url"]


async def test_sotkanet_aluerajaus_tunnuksilla() -> None:
    """Telemetria 28.9.2026: query_source(sotkanet-N, area="Oulu") → area_not_supported.

    Sotkanet palauttaa kaikki alueet; alue rajataan Tilastokeskuksen
    tunnuksilla, joilla rivit on nimetty (region_code, region_level).
    """
    conn = sqlite3.connect("file:data/aura.db?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    seen: dict[str, Any] = {}

    async def fake_json(url: str, filters: Any, max_rows: int, c: Any = None) -> Any:
        seen["filters"] = filters
        table = fetch.Table(protocol="json", request_url=url)
        return fetch._finish(table, ["region"], [], None, 0)

    apply_tool_profile(mcp, profile="public")
    try:
        with (
            patch("aura.server._get_conn", return_value=conn),
            patch.object(fetch, "fetch_json", fake_json),
        ):
            async with Client(mcp) as client:
                r = await client.call_tool(
                    "query_source", {"dataset_id": "sotkanet-3114", "area": "Oulu"}
                )
    finally:
        reset_tool_profile(mcp)
    assert seen["filters"] == {"region_code": ["564"], "region_level": ["kunta"]}
    assert "Aluerajaus" in " ".join(r.structured_content["notes"])


# --- Kerroksen valinta aineiston nimestä (10.10.2026) -------------------
#
# "Helsingin kiinteistöt alueina" kysyi palvelun ensimmäisen kerroksen
# (liikennemäärät), vaikka kiinteistökerros on samassa palvelussa nimellä
# avoindata:Kiinteisto_alue. Valinta tehdään vain kun URL ei nimeä kerrosta.

HEL = [
    "avoindata:Ajoneuvoliikenne_liikennemaarat_viiva",
    "avoindata:Aluesarjat_avainluvut_2024",
    "avoindata:Helsinki_osoiteluettelo",
    "avoindata:Kiinteisto_alue",
    "avoindata:Maaraala_alue_varma_sijainti",
]


def test_kerros_valitaan_aineiston_nimen_perusteella() -> None:
    from aura.wfs import choose_layer

    assert choose_layer(HEL, ["Helsingin kiinteistöt alueina"]) == "avoindata:Kiinteisto_alue"


def test_muun_resurssin_kerrosnimi_ratkaisee() -> None:
    from aura.wfs import choose_layer

    hints = ["Helsingin osoitteet", "avoindata:Helsinki_osoiteluettelo"]
    assert choose_layer(HEL, hints) == "avoindata:Helsinki_osoiteluettelo"


def test_ilman_osumaa_ei_valita() -> None:
    from aura.wfs import choose_layer

    assert choose_layer(HEL, ["Paavo"]) is None
    assert choose_layer(["a:yksi"], ["yksi"]) is None  # yksi kerros: ei valittavaa


def test_camelcase_ja_aakkoset() -> None:
    from aura.wfs import choose_layer

    layers = ["ms:Rakennukset", "ms:KiinteistoRajat", "ms:Tiet"]
    assert choose_layer(layers, ["Kiinteistörajat"]) == "ms:KiinteistoRajat"


@pytest.mark.asyncio
async def test_neuvottelu_kayttaa_vihjeiden_kerrosta() -> None:
    seen: list[dict[str, str]] = []

    async def _get(url: str, params: dict[str, str] | None = None, **_: Any) -> Any:
        params = params or {}
        seen.append(params)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if params.get("request") == "GetCapabilities":
            resp.text = _caps(HEL)
        elif "typeNames" not in params:
            resp.text = '<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1">' \
                '<ows:Exception><ows:ExceptionText>typeName puuttuu</ows:ExceptionText>' \
                "</ows:Exception></ows:ExceptionReport>"
        else:
            resp.text = (
                '{"type":"FeatureCollection","totalFeatures":1,"features":'
                '[{"geometry_name":"geom","properties":{"kiinteistotunnus":"09104399030004"}}]}'
            )
        return resp

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("aura.wfs.httpx.AsyncClient", return_value=client):
        result = await fetch_features(
            "https://kartta.hel.fi/ws/geoserver/avoindata/wfs", 1,
            layer_hints=["Helsingin kiinteistöt alueina"],
        )
    assert result.type_name == "avoindata:Kiinteisto_alue"
    assert result.layer_matched
    assert seen[-1]["typeNames"] == "avoindata:Kiinteisto_alue"


@pytest.mark.asyncio
async def test_valittu_kerros_kerrotaan_huomautuksessa() -> None:
    async def fake(url: str, max_rows: int, **kw: Any) -> Features:
        assert kw["layer_hints"] == ["Helsingin kiinteistöt alueina"]
        return _feature(
            ["kiinteistotunnus"], ["09104399030004"],
            feature_types=HEL, type_name="avoindata:Kiinteisto_alue", layer_matched=True,
        )

    with patch("aura.wfs.fetch_features", fake):
        table = await fetch.fetch_wfs(
            PAAVO, None, 5, None, layer_hints=["Helsingin kiinteistöt alueina"]
        )
    assert table.layer_matched
    note = next(n for n in table.notes if "kerrosta" in n)
    assert "aineiston nimeen sopivinta (avoindata:Kiinteisto_alue)" in note


async def test_query_source_antaa_vihjeiksi_nimen_ja_muiden_resurssien_kerrokset(
    public: sqlite3.Connection,
) -> None:
    upsert_dataset(
        public,
        Dataset(
            id="hel-kiinteistot",
            name="hel-kiinteistot",
            title="Helsingin kiinteistöt alueina",
            source="hri.fi",
            resources=[
                Resource(
                    id="h-png", name="Esikatselukuva", format="PNG",
                    url="https://kartta.hel.fi/ws/geoserver/avoindata/wms?LAYERS=avoindata:Kiinteistot",
                ),
                Resource(
                    id="h-wfs", name="WFS-rajapinta", format="WFS",
                    url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs?request=getCapabilities",
                ),
            ],
        ),
    )
    public.commit()
    seen: dict[str, Any] = {}

    async def fake_wfs(url: str, filters: Any, max_rows: int, bbox: Any, **kw: Any) -> fetch.Table:
        seen.update(kw)
        table = fetch.Table(
            protocol="wfs", request_url=url, layers=HEL,
            layer="avoindata:Kiinteisto_alue", layer_matched=True,
        )
        return fetch._finish(table, ["kiinteistotunnus"], [{"kiinteistotunnus": "1"}], None, 1)

    with patch.object(fetch, "fetch_wfs", fake_wfs):
        data = await _call({"dataset_id": "hel-kiinteistot"})
    assert seen["layer_hints"][0] == "Helsingin kiinteistöt alueina"
    assert "avoindata:Kiinteistot" in seen["layer_hints"]
    assert data["resource"]["layer"] == "avoindata:Kiinteisto_alue"
    assert data["next_actions"][0]["why"].startswith(
        "Kerros valittiin aineiston nimen perusteella"
    )
