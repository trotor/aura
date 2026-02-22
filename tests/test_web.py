"""Testit web-käyttöliittymälle."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def test_db(tmp_path: Path) -> sqlite3.Connection:
    """Luo testitietokanta."""
    from aura.database import get_connection, init_db, upsert_dataset
    from aura.models import Dataset, Resource

    db_path = tmp_path / "test.db"
    conn = get_connection(db_path, check_same_thread=False)
    init_db(conn)

    # Lisää testidatasetit
    ds = Dataset(
        id="test-ds-1",
        name="test-dataset-1",
        title="Testidatasetti 1",
        title_fi="Testidatasetti 1",
        notes_fi="Tämä on testidatasetti.",
        source="avoindata.fi",
        organization_id="org-1",
        organization_name="test-org",
        organization_title="Testiorganisaatio",
        keywords_fi=["testi", "data"],
        geographical_coverage=["Helsinki"],
        num_resources=1,
        resources=[
            Resource(
                id="res-1",
                name="Test CSV",
                format="CSV",
                url="https://example.com/test.csv",
            )
        ],
    )
    upsert_dataset(conn, ds)

    ds2 = Dataset(
        id="test-ds-2",
        name="test-dataset-2",
        title="Toinen datasetti",
        title_fi="Toinen datasetti",
        notes_fi="Toinen testidatasetti.",
        source="hri.fi",
        organization_id="org-2",
        organization_name="toinen-org",
        organization_title="Toinen organisaatio",
        keywords_fi=["avoin", "data"],
        geographical_coverage=["Suomi"],
        num_resources=1,
        resources=[
            Resource(
                id="res-2",
                name="Test JSON",
                format="JSON",
                url="https://example.com/test.json",
            )
        ],
    )
    upsert_dataset(conn, ds2)
    conn.commit()
    return conn


@pytest.fixture()
def client(test_db: sqlite3.Connection) -> TestClient:
    """Luo TestClient testitietokannalla."""
    import aura.web.app as app_module
    import aura.web.routes.api as api_module
    from aura.web.app import create_app

    # Tyhjennä kuntarajojen cache
    api_module._municipality_geojson_cache = None

    # Korvaa lifespan noop-versiolla
    @asynccontextmanager
    async def noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    original_conn = app_module._db_conn
    app_module._db_conn = test_db

    try:
        app = create_app()
        app.router.lifespan_context = noop_lifespan  # type: ignore[assignment]
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app_module._db_conn = original_conn
        api_module._municipality_geojson_cache = None


class TestIndexPage:
    """Etusivun testit."""

    def test_index_returns_200(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_stats(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "Aura" in resp.text

    def test_index_contains_source_table(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "avoindata.fi" in resp.text


class TestSearchPage:
    """Hakusivun testit."""

    def test_search_page_returns_200(self, client: TestClient) -> None:
        resp = client.get("/search")
        assert resp.status_code == 200

    def test_search_results_default(self, client: TestClient) -> None:
        resp = client.get("/search/results")
        assert resp.status_code == 200
        # Pitäisi näyttää testidatasetit
        assert "Testidatasetti" in resp.text or "Toinen datasetti" in resp.text

    def test_search_results_with_query(self, client: TestClient) -> None:
        resp = client.get("/search/results?q=testi")
        assert resp.status_code == 200
        assert "Testidatasetti" in resp.text

    def test_search_results_with_source_filter(self, client: TestClient) -> None:
        resp = client.get("/search/results?source=hri.fi")
        assert resp.status_code == 200
        assert "Toinen" in resp.text

    def test_search_results_with_format_filter(self, client: TestClient) -> None:
        resp = client.get("/search/results?fmt=CSV")
        assert resp.status_code == 200

    def test_search_results_show_view_links(self, client: TestClient) -> None:
        """Hakutuloksissa näkyy Avaa-linkit resursseihin."""
        resp = client.get("/search/results")
        assert resp.status_code == 200
        assert "/view/" in resp.text

    def test_search_page_with_query_params(self, client: TestClient) -> None:
        """Hakusivu esitäyttää lomakkeen URL-parametreilla (jaettava URL)."""
        resp = client.get("/search?q=testi&source=avoindata.fi")
        assert resp.status_code == 200
        assert 'value="testi"' in resp.text
        assert "selected" in resp.text  # source option is selected


class TestDatasetPage:
    """Datasettisivun testit."""

    def test_dataset_returns_200(self, client: TestClient) -> None:
        resp = client.get("/dataset/test-ds-1")
        assert resp.status_code == 200
        assert "Testidatasetti 1" in resp.text

    def test_dataset_shows_resources(self, client: TestClient) -> None:
        resp = client.get("/dataset/test-ds-1")
        assert "CSV" in resp.text

    def test_dataset_not_found(self, client: TestClient) -> None:
        resp = client.get("/dataset/nonexistent")
        assert resp.status_code == 404

    def test_dataset_by_name(self, client: TestClient) -> None:
        resp = client.get("/dataset/test-dataset-1")
        assert resp.status_code == 200
        assert "Testidatasetti 1" in resp.text


class TestMapPage:
    """Karttasivun testit."""

    def test_map_returns_200(self, client: TestClient) -> None:
        resp = client.get("/map")
        assert resp.status_code == 200
        assert "leaflet" in resp.text.lower()


class TestApiEndpoints:
    """API-endpointtien testit."""

    def test_dataset_counts(self, client: TestClient) -> None:
        resp = client.get("/api/geo/dataset-counts")
        assert resp.status_code == 200
        data = resp.json()
        assert "counts" in data
        assert "Helsinki" in data["counts"]

    def test_municipalities_geojson_returns_featurecollection(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/geo/municipalities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        # Tiedosto ei välttämättä löydy testissä → tyhjä features ok
        assert isinstance(data["features"], list)

    def test_preview_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/preview/nonexistent")
        assert resp.status_code == 404


class TestViewPage:
    """Katselusivun testit."""

    def test_view_csv_returns_200(self, client: TestClient) -> None:
        resp = client.get("/view/res-1")
        assert resp.status_code == 200
        assert "Taulukko" in resp.text or "view_table" in resp.text or "data-table" in resp.text

    def test_view_json_returns_200(self, client: TestClient) -> None:
        resp = client.get("/view/res-2")
        assert resp.status_code == 200

    def test_view_not_found(self, client: TestClient) -> None:
        resp = client.get("/view/nonexistent")
        assert resp.status_code == 404
        assert "ei löytynyt" in resp.text.lower()

    def test_view_wms_resource(self, client: TestClient, test_db: sqlite3.Connection) -> None:
        # Lisää WMS-resurssi
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-wms-1", "test-ds-1", "WMS-palvelu", "WMS", "https://example.com/wms"),
        )
        test_db.commit()
        resp = client.get("/view/res-wms-1")
        assert resp.status_code == 200
        assert "leaflet" in resp.text.lower()
        assert "viewer.js" in resp.text

    def test_view_wfs_resource(self, client: TestClient, test_db: sqlite3.Connection) -> None:
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-wfs-1", "test-ds-1", "WFS-palvelu", "WFS", "https://example.com/wfs"),
        )
        test_db.commit()
        resp = client.get("/view/res-wfs-1")
        assert resp.status_code == 200
        assert "leaflet" in resp.text.lower()

    def test_view_unknown_format_redirects(
        self, client: TestClient, test_db: sqlite3.Connection
    ) -> None:
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-pdf-1", "test-ds-1", "PDF-tiedosto", "PDF", "https://example.com/file.pdf"),
        )
        test_db.commit()
        resp = client.get("/view/res-pdf-1", follow_redirects=False)
        assert resp.status_code == 302
        assert "/dataset/" in resp.headers["location"]


class TestWmsWfsApi:
    """WMS/WFS API -endpointtien testit."""

    def test_wms_capabilities_returns_json(self, client: TestClient) -> None:
        # Without actual WMS server, expect error but valid JSON
        resp = client.get("/api/wms/capabilities?url=https://example.com/wms")
        assert resp.status_code == 200
        data = resp.json()
        assert "layers" in data or "error" in data

    def test_wfs_capabilities_returns_json(self, client: TestClient) -> None:
        resp = client.get("/api/wfs/capabilities?url=https://example.com/wfs")
        assert resp.status_code == 200
        data = resp.json()
        assert "feature_types" in data or "error" in data

    def test_wfs_features_returns_json(self, client: TestClient) -> None:
        resp = client.get(
            "/api/wfs/features?url=https://example.com/wfs&typeName=test:layer"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "geojson" in data or "error" in data

    def test_preview_max_rows_100(self, client: TestClient) -> None:
        # Verify max_rows=100 is accepted (was 50 before)
        resp = client.get("/api/preview/res-1?max_rows=100")
        # res-1 has external URL that won't resolve in tests, but should not 422
        assert resp.status_code == 200


class TestWmsCapabilitiesParsing:
    """WMS GetCapabilities XML-parsintayksikkötestit."""

    def test_parse_wms_capabilities(self) -> None:
        from aura.web.routes.api import _parse_wms_capabilities

        xml = """<?xml version="1.0"?>
        <WMS_Capabilities version="1.3.0">
          <Capability>
            <Layer>
              <Title>Root</Title>
              <Layer>
                <Name>layer1</Name>
                <Title>First Layer</Title>
              </Layer>
              <Layer>
                <Name>layer2</Name>
                <Title>Second Layer</Title>
              </Layer>
            </Layer>
          </Capability>
        </WMS_Capabilities>"""

        result = _parse_wms_capabilities(xml)
        assert len(result["layers"]) == 2
        assert result["layers"][0]["name"] == "layer1"
        assert result["layers"][1]["title"] == "Second Layer"

    def test_parse_wms_invalid_xml(self) -> None:
        from aura.web.routes.api import _parse_wms_capabilities

        result = _parse_wms_capabilities("not xml at all")
        assert "error" in result

    def test_parse_wfs_capabilities(self) -> None:
        from aura.web.routes.api import _parse_wfs_capabilities

        xml = """<?xml version="1.0"?>
        <wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0">
          <FeatureTypeList>
            <wfs:FeatureType>
              <wfs:Name>ns:buildings</wfs:Name>
              <wfs:Title>Buildings</wfs:Title>
            </wfs:FeatureType>
          </FeatureTypeList>
        </wfs:WFS_Capabilities>"""

        result = _parse_wfs_capabilities(xml)
        assert len(result["feature_types"]) == 1
        assert result["feature_types"][0]["name"] == "ns:buildings"


class TestDatasetPageViewButtons:
    """Datasettisivun Avaa-nappien testit."""

    def test_csv_has_view_button(self, client: TestClient) -> None:
        resp = client.get("/dataset/test-ds-1")
        assert resp.status_code == 200
        assert "/view/res-1" in resp.text
        assert "Avaa" in resp.text

    def test_json_has_view_button(self, client: TestClient) -> None:
        resp = client.get("/dataset/test-ds-2")
        assert resp.status_code == 200
        assert "/view/res-2" in resp.text


class TestStaticSiteBuild:
    """Staattisen sivun generointitesti."""

    def test_build_creates_files(self, test_db: sqlite3.Connection) -> None:
        from aura.web.build import build_static_site

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("aura.web.build.get_connection", return_value=test_db):
                with patch("aura.web.build.init_db"):
                    build_static_site(output_dir=tmpdir)

            index_path = Path(tmpdir) / "index.html"
            data_path = Path(tmpdir) / "data.json"

            assert index_path.exists()
            assert data_path.exists()

            html = index_path.read_text()
            assert "Aura" in html

            data = json.loads(data_path.read_text())
            assert len(data) == 2
            assert data[0]["s"] in ("avoindata.fi", "hri.fi")
