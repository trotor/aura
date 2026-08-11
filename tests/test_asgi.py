"""Testit yhdistetylle ASGI-sovellukselle (web + MCP samassa prosessissa).

Ennen tätä ``aura serve --http`` ajoi pelkkää FastMCP:tä, joten julkisen
palvelimen juuri palautti 404 vaikka web-templatet olivat olemassa.
Web-UI oli ajettavissa vain erillisellä ``aura web`` -komennolla.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aura.asgi import create_asgi_app
from aura.database import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Pieni oikea kanta levyllä — sovellus avaa sen polun perusteella."""
    path = tmp_path / "aura.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("AURA_DB", str(db_path))
    with TestClient(create_asgi_app()) as c:
        yield c


@pytest.fixture
def readonly_client(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("AURA_DB", str(db_path))
    monkeypatch.setenv("AURA_READONLY", "1")
    with TestClient(create_asgi_app()) as c:
        yield c


class TestLandingPage:
    def test_root_is_not_404(self, client: TestClient) -> None:
        """Juuren 404 oli koko syy tähän työhön."""
        assert client.get("/").status_code == 200

    def test_landing_mentions_open_source(self, client: TestClient) -> None:
        body = client.get("/").text
        assert "github.com/trotor/aura" in body

    def test_landing_shows_mcp_endpoint(self, client: TestClient) -> None:
        assert "/mcp" in client.get("/").text

    def test_landing_honours_forwarded_proto(self, client: TestClient) -> None:
        """Käänteisproxyn takana kopioitavan osoitteen on oltava https.

        ``request.base_url`` kertoo skeeman jolla pyyntö saapui sovellukseen,
        eli nginxin takana aina http. Väärä skeema ohjaisi asiakkaan
        uudelleenohjauksen taakse.
        """
        body = client.get("/", headers={"X-Forwarded-Proto": "https"}).text
        assert "https://testserver/mcp" in body
        assert "http://testserver/mcp" not in body


class TestMcpMount:
    def test_mcp_initialize_works(self, client: TestClient) -> None:
        """Mountattu MCP ei riitä — lifespanin on myös käynnistyttävä.

        Ilman lifespanin ketjutusta reitti vastaa mutta session manager
        ei ole käynnissä, ja virhe näkyy vasta asiakkaalla.
        """
        response = client.post(
            "/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        assert response.status_code == 200
        assert "Aura" in response.text

    def test_mcp_does_not_redirect(self, client: TestClient) -> None:
        """``POST /mcp`` on vastattava suoraan, ei 307:llä ``/mcp/``:hen.

        Nykyinen tuotanto tarjoilee /mcp:n ilman ohjausta. Jos mountti
        lisää sen, asiakkaat jotka eivät seuraa ohjausta hajoavat — eikä
        palvelin näytä mitään vikaa.
        """
        response = client.post(
            "/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            follow_redirects=False,
        )
        assert response.status_code == 200, (
            f"sai {response.status_code} → {response.headers.get('location')}"
        )

    def test_mcp_is_stateless(self, client: TestClient) -> None:
        """Työkalukutsu ilman istuntoa on toimiva sopimus.

        ``mcp.run()`` asetti ``stateless_http=True`` itse, mutta mountattu
        ``http_app()`` ei peri sitä. Jos se unohtuu, endpoint alkaa vaatia
        istuntoa ja jo liitetyt asiakkaat hajoavat — palvelin ei valita
        mitään.
        """
        response = client.post(
            "/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "stats", "arguments": {}},
            },
        )
        assert response.status_code == 200
        assert "error" not in response.text.lower() or "result" in response.text


class TestHealth:
    def test_health_at_root(self, client: TestClient) -> None:
        """Savutestit ja infran nginx-template odottavat /health juuresta."""
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "datasets" in payload


class TestReadonly:
    def test_readonly_app_starts(self, readonly_client: TestClient) -> None:
        """Web-app avasi kirjoittavan yhteyden ja ajoi init_db():n.

        Read-only-kontissa se kaatui käynnistyksessä, eli koko sovellus
        ei noussut lainkaan.
        """
        assert readonly_client.get("/health").status_code == 200

    def test_readonly_serves_landing(self, readonly_client: TestClient) -> None:
        assert readonly_client.get("/").status_code == 200


class TestInstanssikuvaus:
    """Ländärin on kerrottava totuus siitä mitä palvelin ajaa.

    Sivu väitti aiemmin ehdoitta että "tämä sivu ja MCP-endpoint tulevat
    samasta repositoriosta". Väite lakkaa olemasta totta heti kun instanssi
    ajaa laajennettua kerrosta, ja väärä väite julkisella sivulla on pahempi
    kuin puuttuva.
    """

    def test_oletuksena_kertoo_olevansa_sama_kuin_repositorio(
        self, client: TestClient
    ) -> None:
        assert "tulevat samasta repositoriosta" in client.get("/").text

    def test_laajennettu_instanssi_kertoo_siita(
        self, db_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AURA_DB", str(db_path))
        monkeypatch.setenv("AURA_INSTANCE_NAME", "Aura Pro")
        monkeypatch.setenv("AURA_INSTANCE_NOTE", "Kenttätason indeksi mukana.")
        with TestClient(create_asgi_app()) as c:
            body = c.get("/").text
        assert "laajennettua versiota" in body
        assert "Aura Pro" in body
        assert "Kenttätason indeksi mukana." in body
        assert "tulevat samasta repositoriosta" not in body
