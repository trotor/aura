"""Testit PxWeb-kyselyille (query_data + query_pxweb backward compat)."""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db, upsert_dataset
from aura.models import Dataset, Resource
from aura.server import query_data, query_pxweb
from aura.tools.query import (
    _find_pxweb_url,
    _format_dimensions_help,
    _parse_json_stat2,
    _resolve_values,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _seed_pxweb_dataset(
    conn: sqlite3.Connection,
    ds_id: str = "statfin-test.px",
    source: str = "statfin",
) -> None:
    ds = Dataset(
        id=ds_id,
        name=ds_id,
        title="Testtaulu",
        source=source,
        resources=[
            Resource(
                id=f"{ds_id}-pxweb",
                name="Test (PxWeb API)",
                format="PXWEB",
                url="https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/test.px",
            ),
            Resource(
                id=f"{ds_id}-web",
                name="Test (web)",
                format="HTML",
                url="https://statfin.stat.fi/PxWeb/pxweb/fi/StatFin/test.px",
            ),
        ],
    )
    upsert_dataset(conn, ds)
    conn.commit()


# Esimerkkimetatiedot PxWeb-taulusta
SAMPLE_META = {
    "title": "Väestö alueen mukaan",
    "variables": [
        {
            "code": "Alue",
            "text": "Alue",
            "values": ["KU091", "KU837", "KU049"],
            "valueTexts": ["Helsinki", "Tampere", "Espoo"],
        },
        {
            "code": "Vuosi",
            "text": "Vuosi",
            "values": ["2022", "2023", "2024"],
            "valueTexts": ["2022", "2023", "2024"],
        },
        {
            "code": "Tiedot",
            "text": "Tiedot",
            "values": ["vaesto"],
            "valueTexts": ["Väestö 31.12."],
        },
    ],
}

# Esimerkki json-stat2 -vastaus
SAMPLE_JSON_STAT2 = {
    "id": ["Alue", "Vuosi", "Tiedot"],
    "size": [1, 1, 1],
    "dimension": {
        "Alue": {
            "category": {
                "index": {"KU837": 0},
                "label": {"KU837": "Tampere"},
            },
        },
        "Vuosi": {
            "category": {
                "index": {"2024": 0},
                "label": {"2024": "2024"},
            },
        },
        "Tiedot": {
            "category": {
                "index": {"vaesto": 0},
                "label": {"vaesto": "Väestö 31.12."},
            },
        },
    },
    "value": [249009],
}


class TestFindPxwebUrl:
    """Testit PxWeb URL:n etsinnälle."""

    def test_finds_pxweb_resource(self):
        dataset = {
            "resources": [
                {"format": "HTML", "url": "https://example.com/page"},
                {"format": "PXWEB", "url": "https://example.com/api"},
            ],
        }
        assert _find_pxweb_url(dataset) == "https://example.com/api"

    def test_returns_none_when_missing(self):
        dataset = {"resources": [{"format": "CSV", "url": "x.csv"}]}
        assert _find_pxweb_url(dataset) is None

    def test_empty_resources(self):
        assert _find_pxweb_url({"resources": []}) is None


class TestResolveValues:
    """Testit arvojen resolvointiin."""

    def test_resolves_text_to_code(self):
        var = {
            "values": ["KU091", "KU837"],
            "valueTexts": ["Helsinki", "Tampere"],
        }
        assert _resolve_values(var, ["Tampere"]) == ["KU837"]

    def test_keeps_existing_code(self):
        var = {
            "values": ["KU091", "KU837"],
            "valueTexts": ["Helsinki", "Tampere"],
        }
        assert _resolve_values(var, ["KU091"]) == ["KU091"]

    def test_case_insensitive(self):
        var = {
            "values": ["KU091"],
            "valueTexts": ["Helsinki"],
        }
        assert _resolve_values(var, ["helsinki"]) == ["KU091"]

    def test_partial_match(self):
        var = {
            "values": ["KU837"],
            "valueTexts": ["Tampere - Tammerfors"],
        }
        assert _resolve_values(var, ["Tampere"]) == ["KU837"]

    def test_unknown_passthrough(self):
        var = {
            "values": ["KU091"],
            "valueTexts": ["Helsinki"],
        }
        assert _resolve_values(var, ["Turku"]) == ["Turku"]


class TestFormatDimensionsHelp:
    """Testit dimensioiden ohjeen muodostukselle."""

    def test_shows_dimensions(self):
        result = _format_dimensions_help(SAMPLE_META["variables"], "test-1")
        assert "Alue" in result
        assert "Vuosi" in result
        assert "Helsinki" in result

    def test_shows_example_query(self):
        result = _format_dimensions_help(SAMPLE_META["variables"], "test-1")
        assert "Esimerkki" in result
        assert "filters" in result


class TestParseJsonStat2:
    """Testit json-stat2-parsinnalle."""

    def test_basic_parsing(self):
        result = _parse_json_stat2(SAMPLE_JSON_STAT2, 20)
        assert "Tampere" in result
        assert "2024" in result
        assert "249009" in result

    def test_empty_values(self):
        data = {"id": [], "size": [], "dimension": {}, "value": []}
        result = _parse_json_stat2(data, 20)
        assert "Tyhjä vastaus" in result

    def test_null_values(self):
        data = {
            "id": ["X"],
            "size": [2],
            "dimension": {
                "X": {
                    "category": {
                        "index": {"a": 0, "b": 1},
                        "label": {"a": "A", "b": "B"},
                    },
                },
            },
            "value": [42, None],
        }
        result = _parse_json_stat2(data, 20)
        assert "42" in result
        assert ".." in result  # None -> ".."

    def test_truncation_note(self):
        data = {
            "id": ["X"],
            "size": [100],
            "dimension": {
                "X": {
                    "category": {
                        "index": {str(i): i for i in range(100)},
                        "label": {str(i): f"Val {i}" for i in range(100)},
                    },
                },
            },
            "value": list(range(100)),
        }
        result = _parse_json_stat2(data, 5)
        assert "5/100" in result

    def test_multi_dimension(self):
        data = {
            "id": ["Alue", "Vuosi"],
            "size": [2, 2],
            "dimension": {
                "Alue": {
                    "category": {
                        "index": {"KU091": 0, "KU837": 1},
                        "label": {"KU091": "Helsinki", "KU837": "Tampere"},
                    },
                },
                "Vuosi": {
                    "category": {
                        "index": {"2023": 0, "2024": 1},
                        "label": {"2023": "2023", "2024": "2024"},
                    },
                },
            },
            "value": [100, 110, 200, 210],
        }
        result = _parse_json_stat2(data, 20)
        assert "Helsinki" in result
        assert "Tampere" in result
        assert "2023" in result
        assert "2024" in result


class TestQueryPxwebTool:
    """Testit query_data/query_pxweb MCP-työkalulle."""

    @pytest.mark.anyio
    async def test_dataset_not_found(self):
        conn = _memory_db()
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await query_data("nonexistent")
        assert "ei löytynyt" in result

    @pytest.mark.anyio
    async def test_non_pxweb_source_csv(self):
        """Non-PxWeb datasetti toimii jos sillä on CSV-resurssi."""
        conn = _memory_db()
        ds = Dataset(
            id="test-csv", name="test-csv", title="CSV Data",
            source="avoindata.fi",
            resources=[Resource(id="r1", name="test", format="CSV", url="https://example.com/x.csv")],
        )
        upsert_dataset(conn, ds)
        conn.commit()

        csv_content = b"nimi,arvo\nHelsinki,100\n"
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = MagicMock(return_value=_async_iter([csv_content]))
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
            result = await query_data("test-csv")
        assert "nimi" in result or "Helsinki" in result

    @pytest.mark.anyio
    async def test_no_filters_shows_dimensions(self):
        conn = _memory_db()
        _seed_pxweb_dataset(conn)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=SAMPLE_META)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("statfin-test.px")

        assert "Alue" in result
        assert "Helsinki" in result

    @pytest.mark.anyio
    async def test_with_filters_returns_data(self):
        conn = _memory_db()
        _seed_pxweb_dataset(conn)

        # Mock metadata GET
        mock_meta_resp = MagicMock()
        mock_meta_resp.raise_for_status = MagicMock()
        mock_meta_resp.json = MagicMock(return_value=SAMPLE_META)

        # Mock data POST
        mock_data_resp = MagicMock()
        mock_data_resp.raise_for_status = MagicMock()
        mock_data_resp.json = MagicMock(return_value=SAMPLE_JSON_STAT2)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_meta_resp)
        mock_client.post = AsyncMock(return_value=mock_data_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data(
                "statfin-test.px",
                filters={"Alue": ["Tampere"], "Vuosi": ["2024"]},
            )

        assert "Tampere" in result
        assert "249009" in result

    @pytest.mark.anyio
    async def test_resolves_text_to_codes_in_post(self):
        conn = _memory_db()
        _seed_pxweb_dataset(conn)

        mock_meta_resp = MagicMock()
        mock_meta_resp.raise_for_status = MagicMock()
        mock_meta_resp.json = MagicMock(return_value=SAMPLE_META)

        mock_data_resp = MagicMock()
        mock_data_resp.raise_for_status = MagicMock()
        mock_data_resp.json = MagicMock(return_value=SAMPLE_JSON_STAT2)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_meta_resp)
        mock_client.post = AsyncMock(return_value=mock_data_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            await query_data(
                "statfin-test.px",
                filters={"Alue": ["Tampere"]},
            )

        # Tarkista POST-kutsu sisältää koodin KU837
        post_call = mock_client.post.call_args
        post_body = post_call.kwargs["json"]
        alue_query = [q for q in post_body["query"] if q["code"] == "Alue"][0]
        assert "KU837" in alue_query["selection"]["values"]

    @pytest.mark.anyio
    async def test_unknown_dimension(self):
        conn = _memory_db()
        _seed_pxweb_dataset(conn)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=SAMPLE_META)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data(
                "statfin-test.px",
                filters={"TuntematonDimensio": ["arvo"]},
            )

        assert "Tuntemattomia" in result

    @pytest.mark.anyio
    async def test_luke_source_accepted(self):
        conn = _memory_db()
        _seed_pxweb_dataset(conn, ds_id="luke-test.px", source="luke")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=SAMPLE_META)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.preview.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data("luke-test.px")

        assert "Alue" in result  # Should show dimensions, not error

    @pytest.mark.anyio
    async def test_dimension_name_lookup(self):
        """Filtteri voi käyttää dimension text-nimeä koodin sijaan."""
        conn = _memory_db()
        _seed_pxweb_dataset(conn)

        mock_meta_resp = MagicMock()
        mock_meta_resp.raise_for_status = MagicMock()
        mock_meta_resp.json = MagicMock(return_value=SAMPLE_META)

        mock_data_resp = MagicMock()
        mock_data_resp.raise_for_status = MagicMock()
        mock_data_resp.json = MagicMock(return_value=SAMPLE_JSON_STAT2)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_meta_resp)
        mock_client.post = AsyncMock(return_value=mock_data_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("aura.tools.data._server._get_conn", return_value=conn),
            patch("aura.tools.data.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await query_data(
                "statfin-test.px",
                filters={"Alue": ["Helsinki"]},
            )

        assert "Tampere" in result or "Helsinki" in result  # Got some data back

    @pytest.mark.anyio
    async def test_backward_compat_query_pxweb(self):
        """query_pxweb() on backward-compat alias query_data:lle."""
        conn = _memory_db()
        with patch("aura.tools.data._server._get_conn", return_value=conn):
            result = await query_pxweb("nonexistent")
        assert "ei löytynyt" in result


async def _async_iter(chunks: list[bytes]):
    """Apugeneraattori async for -mockkausta varten."""
    for chunk in chunks:
        yield chunk
