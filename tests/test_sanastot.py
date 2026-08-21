"""Testit Sanastot.suomi.fi -harvesterille."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aura.database import init_db
from aura.harvesters.sanastot import SanastotHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _mock_response(data: dict | list) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# --- API-vastaukset ---

ORGANIZATIONS = [
    {
        "id": "org-dvv",
        "label": {
            "fi": "Digi- ja väestötietovirasto",
            "en": "Digital and Population Data Services Agency",
        },
    },
    {
        "id": "org-ym",
        "label": {"fi": "Ympäristöministeriö", "en": "Ministry of the Environment"},
    },
]

TERMINOLOGIES_PAGE_1 = {
    "totalHitCount": 3,
    "terminologies": [
        {
            "prefix": "jupo",
            "label": {"fi": "Julkisen hallinnon sanasto (JUPO)", "en": "JUPO Vocabulary"},
            "description": {
                "fi": "Julkishallinnon yhteinen sanasto",
                "en": "Finnish public administration vocabulary",
            },
            "status": "VALID",
            "modified": "2024-06-15T10:00:00Z",
            "uri": "https://iri.suomi.fi/terminology/jupo/",
            "organizations": ["org-dvv"],
            "languages": ["fi", "sv", "en"],
            "type": "TERMINOLOGICAL_VOCABULARY",
        },
        {
            "prefix": "meluntorjunta",
            "label": {"fi": "Akustiikka- ja meluntorjuntasanasto"},
            "description": {"fi": "Akustiikan ja meluntorjunnan termit"},
            "status": "VALID",
            "modified": "2024-04-03T11:08:19Z",
            "organizations": ["org-ym"],
            "languages": ["fi"],
            "type": "TERMINOLOGICAL_VOCABULARY",
        },
        {
            "prefix": "draft-sanasto",
            "label": {"fi": "Luonnossanasto"},
            "description": {"fi": "Kesken"},
            "status": "DRAFT",
            "modified": "2024-01-01T00:00:00Z",
            "organizations": [],
            "languages": ["fi"],
            "type": "TERMINOLOGICAL_VOCABULARY",
        },
    ],
}


class TestConfig:
    """Harvesterin konfiguraatio."""

    def test_name(self) -> None:
        h = SanastotHarvester(conn=_memory_db())
        assert h.name == "sanastot"

    def test_description(self) -> None:
        h = SanastotHarvester(conn=_memory_db())
        assert "sanasto" in h.description.lower()

    def test_url(self) -> None:
        h = SanastotHarvester(conn=_memory_db())
        assert "sanastot.suomi.fi" in h.url


class TestHarvest:
    """harvest()-integraatiotestit mockilla."""

    @pytest.mark.asyncio
    async def test_harvest_returns_correct_count(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)

        def route_get(url: str, **kwargs) -> MagicMock:  # noqa: ANN003, ARG001
            if "/organizations" in url:
                return _mock_response(ORGANIZATIONS)
            if "/search-terminologies" in url:
                return _mock_response(TERMINOLOGIES_PAGE_1)
            return _mock_response({"terminologies": [], "totalHitCount": 0})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        h._make_client = MagicMock(return_value=mock_client)

        count = await h.harvest()
        # 2 VALID, 1 DRAFT (skipped)
        assert count == 2

    @pytest.mark.asyncio
    async def test_datasets_saved_to_db(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)

        def route_get(url: str, **kwargs) -> MagicMock:  # noqa: ANN003, ARG001
            if "/organizations" in url:
                return _mock_response(ORGANIZATIONS)
            if "/search-terminologies" in url:
                return _mock_response(TERMINOLOGIES_PAGE_1)
            return _mock_response({"terminologies": [], "totalHitCount": 0})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        h._make_client = MagicMock(return_value=mock_client)

        await h.harvest()

        rows = conn.execute("SELECT id FROM datasets ORDER BY id").fetchall()
        ids = [r["id"] for r in rows]
        assert "sanastot-jupo" in ids
        assert "sanastot-meluntorjunta" in ids
        assert "sanastot-draft-sanasto" not in ids

    @pytest.mark.asyncio
    async def test_draft_skipped(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)

        def route_get(url: str, **kwargs) -> MagicMock:  # noqa: ANN003, ARG001
            if "/organizations" in url:
                return _mock_response(ORGANIZATIONS)
            if "/search-terminologies" in url:
                return _mock_response(TERMINOLOGIES_PAGE_1)
            return _mock_response({"terminologies": [], "totalHitCount": 0})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=route_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        h._make_client = MagicMock(return_value=mock_client)

        await h.harvest()

        row = conn.execute(
            "SELECT * FROM datasets WHERE id = 'sanastot-draft-sanasto'"
        ).fetchone()
        assert row is None


class TestProcessTerminology:
    """_process_terminology()-yksikkötestit."""

    def test_dataset_fields(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        orgs = {o["id"]: o["label"] for o in ORGANIZATIONS}
        term = TERMINOLOGIES_PAGE_1["terminologies"][0]
        h._process_terminology(term, orgs)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM datasets WHERE id = 'sanastot-jupo'"
        ).fetchone()
        assert row is not None
        assert row["title_fi"] == "Julkisen hallinnon sanasto (JUPO)"
        assert row["title_en"] == "JUPO Vocabulary"
        assert row["notes_fi"] == "Julkishallinnon yhteinen sanasto"
        assert row["organization_title"] == "Digi- ja väestötietovirasto"
        assert row["source"] == "sanastot"

    def test_resources_created(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        orgs = {o["id"]: o["label"] for o in ORGANIZATIONS}
        term = TERMINOLOGIES_PAGE_1["terminologies"][0]
        h._process_terminology(term, orgs)
        conn.commit()

        resources = conn.execute(
            "SELECT format, url FROM resources WHERE dataset_id = 'sanastot-jupo' ORDER BY format"
        ).fetchall()
        assert len(resources) == 2
        formats = {r["format"] for r in resources}
        assert formats == {"HTML", "JSON-LD"}

    def test_html_resource_url(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        term = TERMINOLOGIES_PAGE_1["terminologies"][0]
        h._process_terminology(term, {})
        conn.commit()

        res = conn.execute(
            "SELECT url FROM resources WHERE dataset_id = 'sanastot-jupo' AND format = 'HTML'"
        ).fetchone()
        assert "sanastot.suomi.fi/terminology/jupo" in res["url"]

    def test_json_ld_export_url(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        term = TERMINOLOGIES_PAGE_1["terminologies"][0]
        h._process_terminology(term, {})
        conn.commit()

        res = conn.execute(
            "SELECT url FROM resources WHERE dataset_id = 'sanastot-jupo' AND format = 'JSON-LD'"
        ).fetchone()
        assert "/export/jupo" in res["url"]
        assert "format=json-ld" in res["url"]

    def test_org_resolved(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        orgs = {o["id"]: o["label"] for o in ORGANIZATIONS}
        term = TERMINOLOGIES_PAGE_1["terminologies"][1]  # meluntorjunta → org-ym
        h._process_terminology(term, orgs)
        conn.commit()

        row = conn.execute(
            "SELECT organization_title FROM datasets WHERE id = 'sanastot-meluntorjunta'"
        ).fetchone()
        assert row["organization_title"] == "Ympäristöministeriö"

    def test_missing_org_graceful(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        term = TERMINOLOGIES_PAGE_1["terminologies"][0]
        # Tyhjä org-map
        h._process_terminology(term, {})
        conn.commit()

        row = conn.execute(
            "SELECT organization_title FROM datasets WHERE id = 'sanastot-jupo'"
        ).fetchone()
        assert row["organization_title"] == ""

    def test_label_fallback_to_en(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        term = {
            "prefix": "english_only",
            "label": {"en": "English Only"},
            "status": "VALID",
            "organizations": [],
        }
        h._process_terminology(term, {})
        conn.commit()

        row = conn.execute(
            "SELECT title_fi FROM datasets WHERE id = 'sanastot-english_only'"
        ).fetchone()
        assert row["title_fi"] == "English Only"

    def test_keywords_contain_sanasto(self) -> None:
        conn = _memory_db()
        h = SanastotHarvester(conn=conn)
        term = TERMINOLOGIES_PAGE_1["terminologies"][0]
        h._process_terminology(term, {})
        conn.commit()

        row = conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'sanastot-jupo'"
        ).fetchone()
        keywords = json.loads(row["keywords_fi"])
        assert "sanasto" in keywords
        assert "terminologia" in keywords
