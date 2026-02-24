"""Testit THL Sotkanet -harvesterille."""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from aura.database import init_db
from aura.harvesters.sotkanet import SotkanetHarvester, _strip_html


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


# Esimerkkidata API-vastauksista
INDICATOR_LIST_ITEM: dict[str, Any] = {
    "id": 4,
    "title": {
        "fi": "Mielenterveyden häiriöihin sairaalahoitoa saaneet 0-17-vuotiaat",
        "en": "Hospital care for mental disorders, aged 0-17",
        "sv": "Sjukhusvård för psykiska störningar, 0-17 år",
    },
    "organization": {
        "id": 2,
        "title": {
            "fi": "Terveyden ja hyvinvoinnin laitos (THL)",
            "en": "Finnish Institute for Health and Welfare (THL)",
            "sv": "Institutet för hälsa och välfärd (THL)",
        },
    },
    "classifications": {
        "sex": {"values": ["male", "female", "total"]},
        "region": {"values": ["Kunta", "Maakunta", "Maa"]},
    },
}

INDICATOR_DETAIL: dict[str, Any] = {
    "id": 4,
    "title": INDICATOR_LIST_ITEM["title"],
    "description": {
        "fi": "<p>Vuoden aikana sairaaloiden vuodeosastoilla hoitoa saaneet.</p>",
        "en": "Patients treated in hospital wards during the year.",
        "sv": "",
    },
    "interpretation": {
        "fi": "<p>Indikaattori kuvaa mielenterveyspalvelujen käyttöä.</p>",
        "en": "",
        "sv": "",
    },
    "data-updated": "2025-05-28",
    "range": {"start": 1996, "end": 2024},
    "primaryValueType": {
        "code": "PER1000",
        "title": {"fi": "Tuhatta asukasta kohden", "en": "Per 1 000 inhabitants"},
    },
    "subjects": [
        {"fi": "sairaalahoito", "en": "hospital care", "sv": "", "uri": ""},
        {"fi": "mielenterveys", "en": "mental health", "sv": "", "uri": "http://www.yso.fi/onto/yso/p1949"},
    ],
    "organization": INDICATOR_LIST_ITEM["organization"],
    "classifications": INDICATOR_LIST_ITEM["classifications"],
    "groups": [730, 103],
    "sources": [],
    "limits": {"fi": "", "en": "", "sv": ""},
    "legislation": {"fi": "", "en": "", "sv": ""},
    "notices": {"fi": "", "en": "", "sv": ""},
    "decimals": 1,
}


class TestStripHtml:
    """Testit HTML-stripperin toiminnalle."""

    def test_strips_tags(self) -> None:
        assert _strip_html("<p>Teksti</p>") == "Teksti"

    def test_decodes_entities(self) -> None:
        assert _strip_html("&amp; &lt;") == "& <"

    def test_empty_input(self) -> None:
        assert _strip_html("") == ""

    def test_nested_tags(self) -> None:
        assert _strip_html("<div><p>Hello <b>world</b></p></div>") == "Hello world"


class TestSotkanetHarvester:
    """Testit Sotkanet-harvesterille."""

    def test_source_config(self) -> None:
        config = SotkanetHarvester.source_config()
        assert config["name"] == "sotkanet"
        assert config["harvester_type"] == "rest_api"
        assert config["query_protocol"] == "rest_json"

    def test_build_dataset(self) -> None:
        """Testaa datasetin muodostus indikaattoritiedoista."""
        conn = _memory_db()
        harvester = SotkanetHarvester(conn)
        dataset = harvester._build_dataset(INDICATOR_LIST_ITEM, INDICATOR_DETAIL)

        assert dataset.id == "sotkanet-4"
        assert dataset.source == "sotkanet"
        assert "Mielenterveyden" in dataset.title_fi
        assert dataset.title_en == "Hospital care for mental disorders, aged 0-17"
        assert dataset.organization_title == "Terveyden ja hyvinvoinnin laitos (THL)"
        assert "sairaalahoito" in dataset.keywords_fi
        assert "mielenterveys" in dataset.keywords_fi
        assert dataset.license_id == "cc-by-4.0"
        assert dataset.update_frequency == "vuosittain"
        assert len(dataset.resources) == 3

        # Resurssien formaatit
        formats = {r.format for r in dataset.resources}
        assert formats == {"JSON", "CSV", "HTML"}

        # Kuvaus sisältää detailitiedot
        assert "sairaaloiden vuodeosastoilla" in dataset.notes_fi
        assert "Tulkinta:" in dataset.notes_fi
        assert "Mittayksikkö: Tuhatta asukasta kohden" in dataset.notes_fi
        assert "1996–2024" in dataset.notes_fi
        assert "kuntatasolla" in dataset.notes_fi

    def test_build_dataset_minimal(self) -> None:
        """Testaa datasetin muodostus minimaalisilla tiedoilla."""
        conn = _memory_db()
        harvester = SotkanetHarvester(conn)

        minimal_indicator = {
            "id": 999,
            "title": {"fi": "Testindikaattori"},
            "organization": {"id": 1, "title": {"fi": "Testi"}},
            "classifications": {},
        }
        minimal_detail: dict[str, Any] = {
            "description": {},
            "interpretation": {},
            "subjects": [],
            "range": {},
            "primaryValueType": None,
        }

        dataset = harvester._build_dataset(minimal_indicator, minimal_detail)
        assert dataset.id == "sotkanet-999"
        assert dataset.title_fi == "Testindikaattori"
        # Oletusavainsanat kun subjects tyhjä
        assert "hyvinvointi" in dataset.keywords_fi

    @pytest.mark.asyncio
    async def test_harvest_with_mock(self) -> None:
        """Testaa harvest-flow mockattuna."""
        conn = _memory_db()
        harvester = SotkanetHarvester(conn)

        list_response = AsyncMock(spec=httpx.Response)
        list_response.json.return_value = [INDICATOR_LIST_ITEM]
        list_response.status_code = 200

        detail_response = AsyncMock(spec=httpx.Response)
        detail_response.json.return_value = INDICATOR_DETAIL
        detail_response.status_code = 200

        with patch.object(harvester, "_fetch", side_effect=[list_response, detail_response]):
            count = await harvester.harvest()

        assert count == 1

        # Varmista että datasetti tallennettiin
        row = conn.execute(
            "SELECT * FROM datasets WHERE id = 'sotkanet-4'"
        ).fetchone()
        assert row is not None
        assert "Mielenterveyden" in row["title_fi"]

        # Resurssit tallennettiin
        resources = conn.execute(
            "SELECT * FROM resources WHERE dataset_id = 'sotkanet-4'"
        ).fetchall()
        assert len(resources) == 3

    @pytest.mark.asyncio
    async def test_harvest_handles_detail_error(self) -> None:
        """Testaa että yksittäisen indikaattorin virhe ei kaada koko harvestia."""
        conn = _memory_db()
        harvester = SotkanetHarvester(conn)

        list_response = AsyncMock(spec=httpx.Response)
        list_response.json.return_value = [
            INDICATOR_LIST_ITEM,
            {**INDICATOR_LIST_ITEM, "id": 999},
        ]
        list_response.status_code = 200

        detail_response = AsyncMock(spec=httpx.Response)
        detail_response.json.return_value = INDICATOR_DETAIL
        detail_response.status_code = 200

        call_count = 0

        async def mock_fetch(client, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return list_response
            if "indicators/4" in url:
                return detail_response
            # 999 epäonnistuu
            raise httpx.HTTPError("mock error")

        with patch.object(harvester, "_fetch", side_effect=mock_fetch):
            count = await harvester.harvest()

        # Vain yksi onnistui
        assert count == 1

    @pytest.mark.asyncio
    async def test_harvest_empty_list(self) -> None:
        """Testaa tyhjä indikaattorilista."""
        conn = _memory_db()
        harvester = SotkanetHarvester(conn)

        list_response = AsyncMock(spec=httpx.Response)
        list_response.json.return_value = []
        list_response.status_code = 200

        with patch.object(harvester, "_fetch", return_value=list_response):
            count = await harvester.harvest()

        assert count == 0
