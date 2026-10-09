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

    def test_telemetria_kerrotaan_kun_paalla(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AURA_TELEMETRY_DB", raising=False)
        assert "tallentaa palvelun kehittämiseksi" not in client.get("/").text
        monkeypatch.setenv("AURA_TELEMETRY_DB", "/tmp/t.db")
        assert "tallentaa palvelun kehittämiseksi" in client.get("/").text

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


class TestWebApiKatalogirajaus:
    """Web-API:n välitysreitit hakevat vain katalogin osoitteita (SSRF 8.10.2026)."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/wms/capabilities?url=http://127.0.0.1:8000/sisainen",
            "/api/wfs/capabilities?url=http://172.17.0.1/",
            "/api/wfs/features?url=http://169.254.169.254/latest&typeName=x",
            "/api/wfs/features?url=https://ei-katalogissa.example/wfs&typeName=x",
        ],
    )
    def test_katalogin_ulkopuolista_ei_haeta(self, client: TestClient, path: str) -> None:
        with patch("aura.web.routes.api.read_capped") as fetch:
            data = client.get(path).json()
        fetch.assert_not_called()
        assert "katalog" in data["error"]

    def test_katalogin_osoite_sisaverkossa_estetaan(
        self, client: TestClient, test_db: sqlite3.Connection
    ) -> None:
        """Katalogin osoitekin voi osoittaa sisäverkkoon (vanhentunut verkkotunnus)."""
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-int", "test-ds-1", "Sisäinen", "WFS", "http://127.0.0.1:9/wfs"),
        )
        test_db.commit()
        data = client.get("/api/wfs/capabilities?url=http://127.0.0.1:9/wfs").json()
        assert data["error"] == "Palvelua ei voitu hakea"
        assert "127.0.0.1" not in json.dumps(data)

    def test_virheteksti_ei_vuoda(self, client: TestClient, test_db: sqlite3.Connection) -> None:
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-x", "test-ds-1", "X", "WMS", "https://x.example/wms"),
        )
        test_db.commit()
        virhe = OSError("All connection attempts failed")
        with patch("aura.web.routes.api.read_capped", side_effect=virhe):
            data = client.get("/api/wms/capabilities?url=https://x.example/wms").json()
        assert "connection" not in json.dumps(data).lower()


class TestKatalogiosoitteenTasmays:
    """Katalogiosoitteen on täsmättävä kokonaan, ei etuliitteenä (katselmointi 8.10.2026)."""

    @pytest.fixture()
    def conn(self, test_db: sqlite3.Connection) -> sqlite3.Connection:
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-hel", "test-ds-1", "Helsinki", "WMS",
             "https://kartta.hel.fi/ws/geoserver/avoindata/wms?service=wms"),
        )
        test_db.commit()
        return test_db

    def test_tasmalleen_sama_kelpaa(self, conn: sqlite3.Connection) -> None:
        from aura.web.routes.api import catalog_endpoint

        url = "https://kartta.hel.fi/ws/geoserver/avoindata/wms?request=GetCapabilities"
        assert catalog_endpoint(conn, url) == "https://kartta.hel.fi/ws/geoserver/avoindata/wms"

    @pytest.mark.parametrize(
        "url",
        [
            "https://kartta.hel/ws/geoserver/avoindata/wms",
            "https://kartta.hel.fi/ws",
            "https://kartta.hel.fi@127.0.0.1/ws/geoserver/avoindata/wms",
            "https://kartta.hel.fi\\@evil.example/ws/geoserver/avoindata/wms",
            "ftp://kartta.hel.fi/ws/geoserver/avoindata/wms",
        ],
    )
    def test_etuliite_tai_kikka_ei_kelpaa(self, conn: sqlite3.Connection, url: str) -> None:
        from aura.web.routes.api import catalog_endpoint

        assert catalog_endpoint(conn, url) is None


class TestUlkoisenSisallonEscapaus:
    """Katalogin ja esikatselun sisältö on kolmannen osapuolen dataa (XSS 8.10.2026)."""

    def test_javascript_osoite_ei_paase_linkiksi(
        self, client: TestClient, test_db: sqlite3.Connection
    ) -> None:
        test_db.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url) VALUES (?, ?, ?, ?, ?)",
            ("res-js", "test-ds-1", "Paha", "CSV", "javascript:alert(1)"),
        )
        test_db.commit()
        body = client.get("/dataset/test-ds-1").text
        assert 'href="javascript:' not in body
        assert "Paha" in body

    def test_esikatselu_ei_kayta_htmx_innerhtml_vaihtoa(self, client: TestClient) -> None:
        """htmx sijoitti JSON-vastauksen raakana innerHTML:ään ennen muotoilua."""
        body = client.get("/dataset/test-ds-1").text
        assert 'hx-get="/api/preview' not in body
        assert 'data-preview="res-1"' in body

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://a.fi/x", "https://a.fi/x"),
            ("http://a.fi/x", "http://a.fi/x"),
            ("javascript:alert(1)", "#"),
            ("  JavaScript:alert(1)", "#"),
            ("data:text/html,<b>", "#"),
            ("", "#"),
            (None, "#"),
        ],
    )
    def test_safe_href(self, url: str | None, expected: str) -> None:
        from aura.web.app import safe_href

        assert safe_href(url) == expected


class TestAvainsanaselain:
    """Avainsanat ovat linkkejä koko sivustolla ja vievät avainsanasivulle."""

    @pytest.fixture(autouse=True)
    def _tyhja_valimuisti(self) -> None:
        from aura import keywords

        keywords._cache.clear()

    def test_avainsanasivu_listaa_aineistot(self, client: TestClient) -> None:
        resp = client.get("/avainsana/testi")
        assert resp.status_code == 200
        assert "Testidatasetti 1" in resp.text
        assert 'href="/avainsana/data"' in resp.text  # liittyvä avainsana

    def test_kirjainkoko_ja_valilyonnit_eivat_haittaa(self, client: TestClient) -> None:
        assert client.get("/avainsana/TESTI").status_code == 200

    def test_tuntematon_avainsana(self, client: TestClient) -> None:
        resp = client.get("/avainsana/ei-olemassa")
        assert resp.status_code == 404
        assert 'href="/avainsanat"' in resp.text

    def test_hakemisto(self, client: TestClient) -> None:
        resp = client.get("/avainsanat")
        assert resp.status_code == 200
        assert 'href="/avainsana/testi"' in resp.text

    def test_aineistosivun_avainsanat_ovat_linkkeja(self, client: TestClient) -> None:
        body = client.get("/dataset/test-ds-1").text
        assert 'href="/avainsana/testi"' in body

    def test_hakutuloksen_avainsanat_ovat_linkkeja(self, client: TestClient) -> None:
        body = client.get("/search/results?q=testidatasetti").text
        assert 'href="/avainsana/testi"' in body

    def test_navigaatiossa_linkki(self, client: TestClient) -> None:
        assert 'href="/avainsanat"' in client.get("/search").text

    def test_lisaa_tuloksia_kysely_on_koodattu(self, client: TestClient) -> None:
        """Seuraavan sivun linkissä hakusana on URL-koodattu."""
        from aura.web.routes.search import results_query

        expected = "q=a%26b+c&source=&fmt=&organization=&page=2"
        assert results_query("a&b c", "", "", "", 2) == expected


class TestKohinaEiLinkiksi:
    """Kohina-avainsana näytetään tekstinä, ei linkkinä joka päätyisi 404:ään."""

    @pytest.fixture(autouse=True)
    def _kohinaa(self, test_db: sqlite3.Connection) -> None:
        from aura import keywords

        keywords._cache.clear()
        test_db.execute(
            "UPDATE datasets SET keywords_fi = ? WHERE id = 'test-ds-1'",
            ('["avoindata.fi", "1._Foo_bar", "testi"]',),
        )
        test_db.commit()

    def test_aineistosivu(self, client: TestClient) -> None:
        body = client.get("/dataset/test-ds-1").text
        assert 'href="/avainsana/avoindata.fi"' not in body
        assert "/avainsana/1._Foo_bar" not in body
        assert "avoindata.fi" in body and "1._Foo_bar" in body
        assert 'href="/avainsana/testi"' in body

    def test_kortti_nayttaa_oikeat_ensin(self, client: TestClient) -> None:
        body = client.get("/search/results?q=testidatasetti").text
        assert 'href="/avainsana/avoindata.fi"' not in body
        assert body.index('href="/avainsana/testi"') < body.index("avoindata.fi")
