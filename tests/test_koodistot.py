"""Testit Koodistot.suomi.fi -harvesterille."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aura.database import init_db
from aura.harvesters.koodistot import KoodistotHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _mock_response(data: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# --- API-vastaukset ---

REGISTRIES_RESPONSE = {
    "results": [
        {
            "codeValue": "jhs",
            "prefLabel": {"fi": "Julkisen hallinnon organisaatiot"},
        },
        {
            "codeValue": "inspire",
            "prefLabel": {"fi": "INSPIRE", "en": "INSPIRE"},
        },
        {
            "codeValue": "test",
            "prefLabel": {"fi": "Testirekisteri"},
        },
    ],
}

JHS_SCHEMES_RESPONSE = {
    "results": [
        {
            "codeValue": "kunta",
            "prefLabel": {"fi": "Kuntakoodit", "en": "Municipality codes", "sv": "Kommunkoder"},
            "description": {"fi": "Suomen kuntien koodisto"},
            "status": "VALID",
            "modified": "2025-01-15T06:43:56.828Z",
            "codesUrl": "https://koodistot.suomi.fi/codelist-api/api/v1/coderegistries/jhs/codeschemes/kunta/codes/",
        },
        {
            "codeValue": "maakunta",
            "prefLabel": {"fi": "Maakuntakoodit"},
            "definition": {"fi": "Maakuntajako"},
            "status": "VALID",
            "modified": "2024-12-01T00:00:00Z",
            "codesUrl": "https://koodistot.suomi.fi/codelist-api/api/v1/coderegistries/jhs/codeschemes/maakunta/codes/",
        },
    ],
}

INSPIRE_SCHEMES_RESPONSE = {
    "results": [
        {
            "codeValue": "theme",
            "prefLabel": {"fi": "INSPIRE-teemat"},
            "description": {"fi": "INSPIRE-direktiivin teemat", "en": "INSPIRE directive themes"},
            "status": "VALID",
            "codesUrl": "https://koodistot.suomi.fi/codelist-api/api/v1/coderegistries/inspire/codeschemes/theme/codes/",
        },
    ],
}


class TestConfig:
    """Harvesterin konfiguraatio."""

    def test_name(self) -> None:
        h = KoodistotHarvester(conn=_memory_db())
        assert h.name == "koodistot"

    def test_description(self) -> None:
        h = KoodistotHarvester(conn=_memory_db())
        assert "koodisto" in h.description.lower()

    def test_url(self) -> None:
        h = KoodistotHarvester(conn=_memory_db())
        assert "koodistot.suomi.fi" in h.url


class TestHarvest:
    """harvest()-integraatiotestit mockilla."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)

        def route_get(url: str, **kwargs) -> MagicMock:  # noqa: ANN003, ARG001
            if "/codeschemes/" not in url:
                return _mock_response(REGISTRIES_RESPONSE)
            if "/jhs/" in url:
                return _mock_response(JHS_SCHEMES_RESPONSE)
            if "/inspire/" in url:
                return _mock_response(INSPIRE_SCHEMES_RESPONSE)
            return _mock_response({"results": []})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        h._make_client = MagicMock(return_value=mock_client)

        count = await h.harvest()
        # jhs: 2 (kunta, maakunta) + inspire: 1 (theme) = 3
        # test-rekisteri on skip-listalla
        assert count == 3

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)

        def route_get(url: str, **kwargs) -> MagicMock:  # noqa: ANN003, ARG001
            if "/codeschemes/" not in url:
                return _mock_response(REGISTRIES_RESPONSE)
            if "/jhs/" in url:
                return _mock_response(JHS_SCHEMES_RESPONSE)
            if "/inspire/" in url:
                return _mock_response(INSPIRE_SCHEMES_RESPONSE)
            return _mock_response({"results": []})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        h._make_client = MagicMock(return_value=mock_client)

        await h.harvest()

        rows = conn.execute("SELECT id, title_fi FROM datasets ORDER BY id").fetchall()
        ids = [r["id"] for r in rows]
        assert "koodistot-inspire-theme" in ids
        assert "koodistot-jhs-kunta" in ids
        assert "koodistot-jhs-maakunta" in ids

    @pytest.mark.asyncio
    async def test_test_registry_skipped(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)

        def route_get(url: str, **kwargs) -> MagicMock:  # noqa: ANN003, ARG001
            if "/codeschemes/" not in url:
                return _mock_response(REGISTRIES_RESPONSE)
            return _mock_response({"results": []})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        h._make_client = MagicMock(return_value=mock_client)

        await h.harvest()

        # test-rekisterin koodistoja ei haettu
        calls = [str(c) for c in mock_client.get.call_args_list]
        assert not any("/test/codeschemes" in c for c in calls)


class TestProcessScheme:
    """_process_scheme()-yksikkötestit."""

    def test_dataset_fields(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = JHS_SCHEMES_RESPONSE["results"][0]
        h._process_scheme("jhs", "Julkisen hallinnon organisaatiot", scheme)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM datasets WHERE id = 'koodistot-jhs-kunta'"
        ).fetchone()
        assert row is not None
        assert row["title_fi"] == "Kuntakoodit"
        assert row["title_en"] == "Municipality codes"
        assert row["title_sv"] == "Kommunkoder"
        assert row["notes_fi"] == "Suomen kuntien koodisto"
        assert row["organization_title"] == "Julkisen hallinnon organisaatiot"
        assert row["source"] == "koodistot"

    def test_resources_created(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = JHS_SCHEMES_RESPONSE["results"][0]
        h._process_scheme("jhs", "JHS", scheme)
        conn.commit()

        resources = conn.execute(
            "SELECT format, url FROM resources WHERE dataset_id = 'koodistot-jhs-kunta' ORDER BY format"
        ).fetchall()
        assert len(resources) == 2
        formats = {r["format"] for r in resources}
        assert formats == {"JSON", "CSV"}
        assert "format=json" in resources[0]["url"] or "format=json" in resources[1]["url"]

    def test_description_fallback_to_definition(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = JHS_SCHEMES_RESPONSE["results"][1]  # maakunta — has definition, no description
        h._process_scheme("jhs", "JHS", scheme)
        conn.commit()

        row = conn.execute(
            "SELECT notes_fi FROM datasets WHERE id = 'koodistot-jhs-maakunta'"
        ).fetchone()
        assert row["notes_fi"] == "Maakuntajako"

    def test_english_description_enriched(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = INSPIRE_SCHEMES_RESPONSE["results"][0]  # has en description
        h._process_scheme("inspire", "INSPIRE", scheme)
        conn.commit()

        enrichment = conn.execute(
            "SELECT value FROM enrichments WHERE dataset_id = 'koodistot-inspire-theme'"
        ).fetchone()
        assert enrichment is not None
        assert "INSPIRE directive themes" in enrichment["value"]

    def test_no_codes_url(self) -> None:
        """Koodisto ilman codesUrl:ia ei luo resursseja."""
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = {
            "codeValue": "nourl",
            "prefLabel": {"fi": "Testi"},
            "status": "VALID",
        }
        h._process_scheme("jhs", "JHS", scheme)
        conn.commit()

        resources = conn.execute(
            "SELECT * FROM resources WHERE dataset_id = 'koodistot-jhs-nourl'"
        ).fetchall()
        assert len(resources) == 0

    def test_label_fallback_to_en(self) -> None:
        """Jos fi-otsikkoa ei ole, käytetään en-otsikkoa."""
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = {
            "codeValue": "english_only",
            "prefLabel": {"en": "English Only"},
            "status": "VALID",
        }
        h._process_scheme("reg", "Reg", scheme)
        conn.commit()

        row = conn.execute(
            "SELECT title_fi FROM datasets WHERE id = 'koodistot-reg-english_only'"
        ).fetchone()
        assert row["title_fi"] == "English Only"

    def test_keywords_contain_koodisto(self) -> None:
        conn = _memory_db()
        h = KoodistotHarvester(conn=conn)
        scheme = JHS_SCHEMES_RESPONSE["results"][0]
        h._process_scheme("jhs", "JHS", scheme)
        conn.commit()

        row = conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'koodistot-jhs-kunta'"
        ).fetchone()
        keywords = json.loads(row["keywords_fi"])
        assert "koodisto" in keywords
