"""Testit Paikkatietoikkuna-harvesterille."""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from aura.database import init_db
from aura.harvesters.paikkatietoikkuna import PaikkatietoikkunaHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


# Esimerkkidata Oskari API -vastauksista

PROVIDERS: dict[str, Any] = {
    "1": {"id": 1, "name": "Maanmittauslaitos"},
    "2": {"id": 2, "name": "Suomen ympäristökeskus"},
}

GROUPS: list[dict[str, Any]] = [
    {"id": 10, "name": "Maastotietokanta"},
    {"id": 20, "name": "Liikenneverkot"},
]

LAYER_WITH_UUID: dict[str, Any] = {
    "id": 101,
    "name": "Maastotietokannan rakennukset",
    "type": "wfslayer",
    "url": "https://avoin-paikkatieto.maanmittauslaitos.fi/maastotiedot/wfs3",
    "layerName": "mtk:rakennus",
    "orgName": "Maanmittauslaitos",
    "dataproviderId": 1,
    "metadataUuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
    "groups": [10],
    "srs_name": "EPSG:3067",
    "created": "2024-01-15",
    "updated": "2025-06-01",
}

LAYER_WITHOUT_UUID: dict[str, Any] = {
    "id": 202,
    "name": "Testikarttataso",
    "type": "wmslayer",
    "url": "https://example.com/wms",
    "layerName": "test:taso",
    "orgName": "Testiorganisaatio",
    "dataproviderId": 99,
    "metadataUuid": "",
    "groups": [20],
}

CSW_METADATA: dict[str, Any] = {
    "fileIdentifier": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
    "identifications": [
        {
            "citation": {"title": "Maastotietokannan rakennukset"},
            "abstractText": "Koko Suomen kattava rakennusaineisto.",
            "descriptiveKeywords": [
                {"keywords": ["rakennukset", "maastotietokanta"]},
                {"keywords": ["INSPIRE"]},
            ],
            "otherConstraints": ["CC BY 4.0"],
            "topicCategories": ["structure"],
            "responsibleParties": [
                {"organisationName": "Maanmittauslaitos", "role": "owner"},
            ],
        },
    ],
    "metadataDateStamp": "2025-06-01",
}

LAYERS_RESPONSE: dict[str, Any] = {
    "layers": [LAYER_WITH_UUID, LAYER_WITHOUT_UUID],
    "groups": GROUPS,
    "providers": PROVIDERS,
}


class TestPaikkatietoikkunaHarvester:
    """Testit Paikkatietoikkuna-harvesterille."""

    def test_source_config(self) -> None:
        config = PaikkatietoikkunaHarvester.source_config()
        assert config["name"] == "paikkatietoikkuna"
        assert config["harvester_type"] == "oskari"
        assert config["query_protocol"] == "oskari_action"

    def test_build_group_map(self) -> None:
        result = PaikkatietoikkunaHarvester._build_group_map(GROUPS)
        assert result == {10: "Maastotietokanta", 20: "Liikenneverkot"}

    def test_resolve_org_with_provider(self) -> None:
        name, title = PaikkatietoikkunaHarvester._resolve_org(
            LAYER_WITH_UUID, PROVIDERS,
        )
        assert title == "Maanmittauslaitos"
        assert name == "maanmittauslaitos"

    def test_resolve_org_without_provider(self) -> None:
        name, title = PaikkatietoikkunaHarvester._resolve_org(
            LAYER_WITHOUT_UUID, PROVIDERS,
        )
        assert title == "Testiorganisaatio"
        assert name == "testiorganisaatio"

    def test_layer_keywords(self) -> None:
        group_map = {10: "Maastotietokanta", 20: "Liikenneverkot"}
        keywords = PaikkatietoikkunaHarvester._layer_keywords(
            LAYER_WITH_UUID, group_map,
        )
        assert "paikkatietoikkuna" in keywords
        assert "Maastotietokanta" in keywords

    def test_build_dataset_with_csw(self) -> None:
        """Testaa datasetin muodostus CSW-metatiedoilla."""
        conn = _memory_db()
        harvester = PaikkatietoikkunaHarvester(conn)
        group_map = {10: "Maastotietokanta", 20: "Liikenneverkot"}

        dataset = harvester._build_dataset(
            uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
            layers=[LAYER_WITH_UUID],
            csw=CSW_METADATA,
            providers=PROVIDERS,
            group_map=group_map,
        )

        assert dataset.id == "paikkatietoikkuna-aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001"
        assert dataset.source == "paikkatietoikkuna"
        assert "rakennukset" in dataset.title_fi.lower()
        assert "rakennusaineisto" in dataset.notes_fi.lower()
        assert "rakennukset" in dataset.keywords_fi
        assert "Maastotietokanta" in dataset.keywords_fi
        assert dataset.organization_title == "Maanmittauslaitos"
        assert dataset.license_title == "CC BY 4.0"
        assert dataset.metadata_modified == "2025-06-01T00:00:00"

        # Resurssit: yksi WFS + yksi HTML (metadatalinkki)
        assert len(dataset.resources) == 2
        formats = {r.format for r in dataset.resources}
        assert "WFS" in formats
        assert "HTML" in formats

    def test_build_dataset_without_csw(self) -> None:
        """Testaa datasetin muodostus ilman CSW-metatietoja."""
        conn = _memory_db()
        harvester = PaikkatietoikkunaHarvester(conn)

        dataset = harvester._build_dataset(
            uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
            layers=[LAYER_WITH_UUID],
            csw={},
            providers=PROVIDERS,
            group_map={10: "Maastotietokanta"},
        )

        # Otsikko tulee tasolta kun CSW on tyhjä
        assert "rakennukset" in dataset.title_fi.lower()
        assert dataset.notes_fi == ""

    @pytest.mark.asyncio
    async def test_harvest_with_mock(self) -> None:
        """Testaa harvest-flow mockattuna."""
        conn = _memory_db()
        harvester = PaikkatietoikkunaHarvester(conn)

        layers_response = AsyncMock(spec=httpx.Response)
        layers_response.json.return_value = LAYERS_RESPONSE
        layers_response.status_code = 200

        csw_response = AsyncMock(spec=httpx.Response)
        csw_response.json.return_value = CSW_METADATA
        csw_response.status_code = 200

        call_count = 0

        async def mock_fetch(client, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "GetHierarchicalMapLayerGroups" in url:
                return layers_response
            if "GetCSWData" in url:
                return csw_response
            raise httpx.HTTPError("unexpected url")

        with patch.object(harvester, "_fetch", side_effect=mock_fetch):
            count = await harvester.harvest()

        # 1 UUID-datasetti + 1 ilman UUID:tä
        assert count == 2

        # Tarkista UUID-datasetti
        row = conn.execute(
            "SELECT * FROM datasets WHERE id LIKE 'paikkatietoikkuna-aaaa%'"
        ).fetchone()
        assert row is not None

        # Tarkista UUID-tön datasetti
        row2 = conn.execute(
            "SELECT * FROM datasets WHERE id = 'paikkatietoikkuna-layer-202'"
        ).fetchone()
        assert row2 is not None

    @pytest.mark.asyncio
    async def test_harvest_empty_layers(self) -> None:
        """Testaa tyhjä API-vastaus."""
        conn = _memory_db()
        harvester = PaikkatietoikkunaHarvester(conn)

        response = AsyncMock(spec=httpx.Response)
        response.json.return_value = {"layers": [], "groups": [], "providers": {}}
        response.status_code = 200

        with patch.object(harvester, "_fetch", return_value=response):
            count = await harvester.harvest()

        assert count == 0

    @pytest.mark.asyncio
    async def test_harvest_csw_error_continues(self) -> None:
        """Testaa että CSW-virhe ei kaada harvestia."""
        conn = _memory_db()
        harvester = PaikkatietoikkunaHarvester(conn)

        layers_response = AsyncMock(spec=httpx.Response)
        layers_response.json.return_value = {
            "layers": [LAYER_WITH_UUID],
            "groups": GROUPS,
            "providers": PROVIDERS,
        }
        layers_response.status_code = 200

        call_count = 0

        async def mock_fetch(client, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "GetHierarchicalMapLayerGroups" in url:
                return layers_response
            # CSW epäonnistuu
            raise httpx.HTTPError("csw error")

        with patch.object(harvester, "_fetch", side_effect=mock_fetch):
            count = await harvester.harvest()

        # Datasetti tallennetaan silti (ilman CSW-metatietoja)
        assert count == 1
