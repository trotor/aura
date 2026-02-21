"""Testit Valtiokonttori-harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.valtiokonttori import ValtiokonttoriHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


# Esimerkkivastaukset APIM discovery -rajapinnasta

SAMPLE_APIS = {
    "value": [
        {
            "id": "ValtiontalousV1",
            "name": "Valtion talous",
            "description": "Valtion talousarviotalouden tietoja.",
            "path": "valtiontalous",
            "apiVersion": "v1",
        },
        {
            "id": "CentralGovernmentDebtV1",
            "name": "Central government debt",
            "description": "Valtionvelan tiedot.",
            "path": "central-government-debt",
            "apiVersion": "v1",
        },
    ],
}

SAMPLE_OPERATIONS_TALOUS = {
    "value": [
        {
            "name": "Budjettitalouden tapahtumat",
            "description": "Budjettitalouden tapahtumatiedot kuukausittain.",
            "urlTemplate": "/budjettitaloudentapahtumat",
            "templateParameters": [
                {"name": "yearFrom", "type": "integer"},
                {"name": "yearTo", "type": "integer"},
                {"name": "paaluokka", "type": "string"},
            ],
        },
        {
            "name": "Hallinnonalat",
            "description": "Hallinnonalojen luettelo.",
            "urlTemplate": "/hallinnonalat",
            "templateParameters": [],
        },
        {
            "name": "Tiedostot",
            "description": "CSV-tiedostojen latauslinkit.",
            "urlTemplate": "/budjettitalousvuosikuukausi",
            "templateParameters": [],
        },
    ],
}

SAMPLE_OPERATIONS_DEBT = {
    "value": [
        {
            "name": "Debt and GDP",
            "description": "Valtionvelka suhteessa BKT:hen vuodesta 1940 alkaen aikasarjana.",
            "urlTemplate": "/debt-and-gdp",
            "templateParameters": [
                {"name": "lang", "type": "string"},
            ],
        },
    ],
}


def _mock_client(
    apis: dict | None = None,
    operations_map: dict[str, dict] | None = None,
) -> AsyncMock:
    """Luo mock HTTP-client joka palauttaa oikeat vastaukset URL:n perusteella."""
    if apis is None:
        apis = SAMPLE_APIS
    if operations_map is None:
        operations_map = {
            "ValtiontalousV1": SAMPLE_OPERATIONS_TALOUS,
            "CentralGovernmentDebtV1": SAMPLE_OPERATIONS_DEBT,
        }

    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()

        if "developer/apis?" in url and "operations" not in url:
            resp.json.return_value = apis
        elif "/operations?" in url:
            # Parsitaan API ID URL:sta
            for api_id, ops in operations_map.items():
                if api_id in url:
                    resp.json.return_value = ops
                    break
            else:
                resp.json.return_value = {"value": []}
        else:
            resp.json.return_value = {"value": []}
        return resp

    client.get = AsyncMock(side_effect=mock_get)
    return client


class TestValtiokonttoriConfig:
    """Peruskonfiguraation testit."""

    def test_name(self):
        h = ValtiokonttoriHarvester(conn=_memory_db())
        assert h.name == "valtiokonttori"

    def test_source_in_dataset(self):
        h = ValtiokonttoriHarvester(conn=_memory_db())
        ds = h._make_dataset(
            id="test", name="test", title="Test",
        )
        assert ds.source == "valtiokonttori"

    def test_api_metadata_keys(self):
        """API_METADATA sisältää tunnetut API:t."""
        from aura.harvesters.valtiokonttori import API_METADATA
        assert "valtiontalousv1" in API_METADATA
        assert "centralgovernmentdebtv1" in API_METADATA
        assert "tilikartav1" in API_METADATA


class TestValtiokonttoriHarvest:
    """harvest()-metodin testit."""

    @pytest.mark.asyncio
    async def test_harvest_returns_count(self):
        """Harvest palauttaa operaatioiden lukumäärän."""
        h = ValtiokonttoriHarvester(conn=_memory_db())
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        # 3 operaatiota (talous) + 1 operaatio (debt) = 4
        assert count == 4

    @pytest.mark.asyncio
    async def test_harvest_writes_to_db(self):
        """Datasetit tallentuvat tietokantaan."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source = 'valtiokonttori'"
        ).fetchone()
        assert row[0] == 4

    @pytest.mark.asyncio
    async def test_dataset_ids_correct(self):
        """Dataset-tunnisteet muodostuvat oikein."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        ids = [
            r["id"] for r in
            conn.execute("SELECT id FROM datasets WHERE source = 'valtiokonttori'").fetchall()
        ]
        assert "valtiokonttori-valtiontalous-budjettitaloudentapahtumat" in ids
        assert "valtiokonttori-valtiontalous-hallinnonalat" in ids
        assert "valtiokonttori-central-government-debt-debt-and-gdp" in ids

    @pytest.mark.asyncio
    async def test_organization_is_valtiokonttori(self):
        """Organisaatio on Valtiokonttori."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT organization_title FROM datasets "
            "WHERE source = 'valtiokonttori' LIMIT 1"
        ).fetchone()
        assert row["organization_title"] == "Valtiokonttori"

    @pytest.mark.asyncio
    async def test_resources_created(self):
        """Jokaiselle datasetille luodaan resurssi."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            """SELECT COUNT(*) FROM resources r
               JOIN datasets d ON r.dataset_id = d.id
               WHERE d.source = 'valtiokonttori'"""
        ).fetchone()
        assert row[0] == 4

    @pytest.mark.asyncio
    async def test_resource_urls_point_to_gateway(self):
        """Resurssien URL:t osoittavat API-gatewayhyn."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        rows = conn.execute(
            """SELECT r.url FROM resources r
               JOIN datasets d ON r.dataset_id = d.id
               WHERE d.source = 'valtiokonttori'"""
        ).fetchall()
        for row in rows:
            assert row["url"].startswith("https://api.tutkihallintoa.fi")


class TestValtiokonttoriEnrichment:
    """Enrichment-testit."""

    @pytest.mark.asyncio
    async def test_parameters_enriched(self):
        """Operaation parametrit rikastetaan access_instructions-kenttään."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT value FROM enrichments "
            "WHERE dataset_id = 'valtiokonttori-valtiontalous-budjettitaloudentapahtumat' "
            "AND field = 'access_instructions'"
        ).fetchone()
        assert row is not None
        assert "yearFrom" in row["value"]

    @pytest.mark.asyncio
    async def test_description_enriched(self):
        """Pitkä kuvaus tallennetaan description_extended-kenttään."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT value FROM enrichments "
            "WHERE dataset_id = 'valtiokonttori-central-government-debt-debt-and-gdp' "
            "AND field = 'description_extended'"
        ).fetchone()
        assert row is not None
        assert "BKT" in row["value"]

    @pytest.mark.asyncio
    async def test_enrichments_source_type(self):
        """Enrichmentien source_type on 'harvest'."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client()

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        rows = conn.execute(
            "SELECT source_type FROM enrichments "
            "WHERE dataset_id LIKE 'valtiokonttori-%'"
        ).fetchall()
        assert all(r["source_type"] == "harvest" for r in rows)


class TestValtiokonttoriEdgeCases:
    """Reunatapaukset."""

    @pytest.mark.asyncio
    async def test_no_operations_creates_api_dataset(self):
        """Jos operaatioita ei saada, luodaan yksi datasetti per API."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client(operations_map={})

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        # 2 API:a, kummallekin yksi fallback-datasetti
        assert count == 2

    @pytest.mark.asyncio
    async def test_empty_api_list(self):
        """Tyhjä API-lista palauttaa 0."""
        conn = _memory_db()
        h = ValtiokonttoriHarvester(conn=conn)
        mock = _mock_client(apis={"value": []})

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 0

    def test_guess_format_csv(self):
        """Tiedosto-operaatio tunnistetaan CSV:ksi."""
        assert ValtiokonttoriHarvester._guess_format(
            "/budjettitalousvuosikuukausi", "Tiedostot"
        ) == "CSV"

    def test_guess_format_api(self):
        """Normaali operaatio on API."""
        assert ValtiokonttoriHarvester._guess_format(
            "/hallinnonalat", "Hallinnonalat"
        ) == "API"
