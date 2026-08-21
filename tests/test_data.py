"""Testit query_data unified MCP-työkalulle."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db, upsert_dataset, upsert_source
from aura.models import Dataset, Resource
from aura.server import query_data


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed(
    conn: sqlite3.Connection,
    ds_id: str = "test-1",
    source: str = "test",
    resources: list[Resource] | None = None,
) -> None:
    if resources is None:
        resources = [
            Resource(id=f"{ds_id}-csv", name="test.csv", format="CSV",
                     url="https://example.com/test.csv"),
        ]
    ds = Dataset(id=ds_id, name=ds_id, title="Test", source=source, resources=resources)
    upsert_dataset(conn, ds)
    conn.commit()


async def _async_iter(chunks: list[bytes]):
    for chunk in chunks:
        yield chunk


class TestQueryDataRouting:
    """Testit formaatin mukaiselle reititykselle."""

    @pytest.mark.anyio
    async def test_csv_preview(self):
        conn = _memory_db()
        _seed(conn)

        csv_data = b"nimi,arvo\nHelsinki,100\nTampere,200\n"
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = MagicMock(return_value=_async_iter([csv_data]))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("test-1")

        assert "Helsinki" in result
        assert "Tampere" in result

    @pytest.mark.anyio
    async def test_csv_with_filters(self):
        conn = _memory_db()
        _seed(conn)

        csv_data = b"nimi,arvo\nHelsinki,100\nTampere,200\nEspoo,300\n"
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = MagicMock(return_value=_async_iter([csv_data]))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("test-1", filters={"nimi": ["Tampere"]})

        assert "Tampere" in result
        assert "suodatettu" in result

    @pytest.mark.anyio
    async def test_json_preview(self):
        conn = _memory_db()
        _seed(conn, resources=[
            Resource(id="r1", name="data", format="JSON", url="https://example.com/data.json"),
        ])

        data = [{"nimi": "Helsinki"}, {"nimi": "Tampere"}]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = json.dumps(data)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("test-1")

        assert "Helsinki" in result

    @pytest.mark.anyio
    async def test_json_with_filters(self):
        conn = _memory_db()
        _seed(conn, resources=[
            Resource(id="r1", name="data", format="JSON", url="https://example.com/data.json"),
        ])

        data = [{"nimi": "Helsinki", "arvo": 1}, {"nimi": "Tampere", "arvo": 2}]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = json.dumps(data)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("test-1", filters={"nimi": ["Tampere"]})

        assert "Tampere" in result
        assert "suodatettu" in result

    @pytest.mark.anyio
    async def test_odata_with_filters(self):
        conn = _memory_db()
        _seed(conn, resources=[
            Resource(id="r1", name="data", format="ODATA", url="https://example.com/odata/Entities"),
        ])

        odata_resp = {"value": [{"Nimi": "Tampere", "Arvo": 42}]}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=odata_resp)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data(
                "test-1",
                filters={"Nimi": ["Tampere"]},
            )

        assert "Tampere" in result
        assert "42" in result

    @pytest.mark.anyio
    async def test_wfs_with_filters(self):
        conn = _memory_db()
        _seed(conn, resources=[
            Resource(id="r1", name="WFS", format="WFS", url="https://example.com/wfs"),
        ])

        wfs_resp = {
            "features": [
                {"properties": {"nimi": "Helsinki", "tyyppi": "kunta"}},
            ],
            "totalFeatures": 1,
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = json.dumps(wfs_resp)
        mock_resp.json = MagicMock(return_value=wfs_resp)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.wfs.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data(
                "test-1",
                filters={"nimi": ["Helsinki"]},
            )

        assert "Helsinki" in result
        assert "suodatettu" in result


class TestQueryDataSourceProtocol:
    """Testit sources-taulun query_protocol -reititystä varten."""

    @pytest.mark.anyio
    async def test_odata_routed_by_protocol(self):
        """Datasetti reititetään OData:ksi sources.query_protocol perusteella."""
        conn = _memory_db()
        _seed(conn, source="traficom", resources=[
            Resource(id="r1", name="API", format="API",
                     url="https://opendata.traficom.fi/api/v12/Entities"),
        ])
        upsert_source(conn, {
            "name": "traficom",
            "query_protocol": "odata",
        })
        conn.commit()

        odata_resp = {"value": [{"Nimi": "Test", "Arvo": 1}]}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=odata_resp)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data(
                "test-1",
                filters={"Nimi": ["Test"]},
            )

        assert "Test" in result


def _seed_kunta(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO ref_municipalities"
        " (code, name_fi, name_sv, min_x, min_y, max_x, max_y)"
        " VALUES ('297','Kuopio','Kuopio', 494427.8, 6940948.7, 588843.3, 7030987.9)"
    )
    conn.commit()


def _wfs_client(responses: list[dict]) -> tuple[AsyncMock, list[dict]]:
    """WFS-mock joka kirjaa jokaisen kutsun parametrit."""
    calls: list[dict] = []

    def _make(payload: dict) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.text = json.dumps(payload)
        resp.json = MagicMock(return_value=payload)
        return resp

    async def _get(url, params=None, **kwargs):
        calls.append({"url": url, "params": params or {}})
        return _make(responses[min(len(calls) - 1, len(responses) - 1)])

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client, calls


class TestQueryDataArea:
    """Aluerajaus (#146): area kääntyy bbox:iksi ja päätyy WFS-kyselyyn."""

    @pytest.mark.anyio
    async def test_wfs_area_lisaa_bbox_parametrin(self):
        conn = _memory_db()
        _seed_kunta(conn)
        _seed(conn, resources=[
            Resource(id="r1", name="WFS", format="WFS", url="https://example.com/wfs"),
        ])

        client, calls = _wfs_client([
            {"features": [{"properties": {"nimi": "Kohde"}}], "totalFeatures": 1},
        ])

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.wfs.httpx.AsyncClient", return_value=client),
        ):
            result = await query_data("test-1", area="Kuopio")

        assert calls, "WFS-kutsua ei tehty"
        bbox = calls[-1]["params"].get("bbox", "")
        assert bbox.startswith("494427.8,6940948.7,588843.3,7030987.9")
        assert bbox.endswith("EPSG:3067")
        assert "Aluerajaus" in result and "Kuopio" in result

    @pytest.mark.anyio
    async def test_area_ja_filtterit_taittuvat_cqlaan(self):
        """Palvelin hylkää bbox+cql_filter-yhdistelmän, joten rajaus menee CQL:ään."""
        conn = _memory_db()
        _seed_kunta(conn)
        _seed(conn, resources=[
            Resource(id="r1", name="WFS", format="WFS", url="https://example.com/wfs"),
        ])

        client, calls = _wfs_client([
            # 1. luotain: geometriakentän nimi
            {"features": [{"geometry_name": "geom", "properties": {"nimi": "Kohde"}}]},
            # 2. varsinainen kysely
            {"features": [{"properties": {"nimi": "Kohde"}}], "totalFeatures": 1},
        ])

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.wfs.httpx.AsyncClient", return_value=client),
        ):
            result = await query_data("test-1", filters={"nimi": ["Kohde"]}, area="Kuopio")

        params = calls[-1]["params"]
        assert "bbox" not in params, "bbox ja cql_filter ovat toisensa poissulkevia"
        cql = params.get("CQL_FILTER", "")
        assert "BBOX(geom," in cql
        assert "'EPSG:3067'" in cql
        assert "nimi='Kohde'" in cql
        assert "Kohde" in result

    @pytest.mark.anyio
    async def test_tuntematon_geometriakentta_kerrotaan(self):
        """Hiljainen pudotus antaisi tuloksen väärältä alueelta."""
        conn = _memory_db()
        _seed_kunta(conn)
        _seed(conn, resources=[
            Resource(id="r1", name="WFS", format="WFS", url="https://example.com/wfs"),
        ])

        client, _calls = _wfs_client([{"features": [{"properties": {"nimi": "X"}}]}])

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.wfs.httpx.AsyncClient", return_value=client),
        ):
            result = await query_data("test-1", filters={"nimi": ["X"]}, area="Kuopio")

        assert "geometria" in result.lower()
        assert "| X |" not in result, "rajaamaton tulos esitettiin rajattuna"

    @pytest.mark.anyio
    async def test_ei_paikkatietoformaatti_hylataan_ilman_verkkokutsua(self):
        conn = _memory_db()
        _seed_kunta(conn)
        _seed(conn)  # CSV

        client, calls = _wfs_client([{}])

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=client),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=client),
        ):
            result = await query_data("test-1", area="Kuopio")

        assert "CSV" in result
        assert not calls, "hylätty aluerajaus ei saa aiheuttaa verkkokutsua"

    @pytest.mark.anyio
    async def test_pxweb_ohjaa_dimensiosuodattimeen(self):
        conn = _memory_db()
        _seed_kunta(conn)
        _seed(conn, resources=[
            Resource(id="r1", name="Taulu", format="PXWEB",
                     url="https://example.com/px/table"),
        ])

        client, calls = _wfs_client([{}])

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=client),
        ):
            result = await query_data("test-1", area="Kuopio")

        assert "filters" in result and "Alue" in result
        assert not calls

    @pytest.mark.anyio
    async def test_tuntematon_alue_ei_kysele_verkosta(self):
        conn = _memory_db()
        _seed(conn, resources=[
            Resource(id="r1", name="WFS", format="WFS", url="https://example.com/wfs"),
        ])

        client, calls = _wfs_client([{}])

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=client),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=client),
        ):
            result = await query_data("test-1", area="Atlantis")

        assert "Atlantis" in result
        assert not calls
