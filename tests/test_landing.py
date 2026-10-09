"""Etusivun kieliversiot, laajennetun instanssin esittely ja llms.txt.

Etusivu on palvelun näyteikkuna kolmella kielellä. Testit varmistavat
kolme lupausta: jokainen kieli renderöityy ja kertoo oman kielensä,
avoin instanssi ei väitä tarjoavansa Pro-ominaisuuksia itse, ja
koneluettava kuvaus kertoo agentille oikean endpointin.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aura.asgi import create_asgi_app
from aura.database import init_db
from aura.web.i18n import LANGUAGES, TEXTS, format_number
from aura.web.routes.index import landing_html


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
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
    for name in ("AURA_INSTANCE_NAME", "AURA_INSTANCE_NOTE", "AURA_INSTANCE_OPERATOR"):
        monkeypatch.delenv(name, raising=False)
    with TestClient(create_asgi_app()) as c:
        yield c


@pytest.fixture
def pro_client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("AURA_DB", str(db_path))
    monkeypatch.setenv("AURA_INSTANCE_NAME", "Aura Pro")
    with TestClient(create_asgi_app()) as c:
        yield c


@pytest.mark.parametrize(("path", "lang"), [("/", "fi"), ("/en", "en"), ("/sv", "sv")])
def test_kieliversio_renderoityy_omalla_kielellaan(
    client: TestClient, path: str, lang: str
) -> None:
    resp = client.get(path)
    assert resp.status_code == 200
    assert f'<html lang="{lang}"' in resp.text
    assert TEXTS[lang]["hero_title"] in resp.text


def test_kieliversiot_viittaavat_toisiinsa(client: TestClient) -> None:
    """hreflang-linkit kertovat hakukoneelle ja agentille muut kielet."""
    body = client.get("/en").text
    for code in LANGUAGES:
        assert f'hreflang="{code}"' in body


def test_kaikilla_kielilla_samat_avaimet() -> None:
    """Puuttuva käännös kaataisi sivun vasta ajossa — tarkistetaan tässä."""
    keys = set(TEXTS["fi"])
    for lang in LANGUAGES:
        assert set(TEXTS[lang]) == keys, lang
        assert len(TEXTS[lang]["examples"]) == len(TEXTS["fi"]["examples"])
        assert len(TEXTS[lang]["how_steps"]) == 3


def test_avoin_instanssi_ohjaa_pro_versioon_eika_vaita_sita_omakseen(
    client: TestClient,
) -> None:
    body = client.get("/").text
    assert "aura.futuai.fi" in body
    assert TEXTS["fi"]["pro_intro_here"] not in body


def test_laajennettu_instanssi_kertoo_pro_ominaisuudet_omikseen(
    pro_client: TestClient,
) -> None:
    body = pro_client.get("/").text
    assert TEXTS["fi"]["pro_intro_here"] in body
    assert "get_facts" in body


def test_mcp_endpoint_ja_claude_code_komento(client: TestClient) -> None:
    body = client.get("/en").text
    assert "claude mcp add --transport http aura http://testserver/mcp" in body


def test_llms_txt_kertoo_endpointin(client: TestClient) -> None:
    resp = client.get("/llms.txt", headers={"x-forwarded-proto": "https"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text.startswith("# Aura\n")
    assert "https://testserver/mcp" in resp.text
    assert "find_data" in resp.text
    assert "get_facts" not in resp.text


def test_llms_txt_laajennetussa_mainitsee_tunnusluvut(pro_client: TestClient) -> None:
    assert "get_facts" in pro_client.get("/llms.txt").text


def test_lukujen_tuhaterotin_kielen_mukaan() -> None:
    assert format_number(13311, "en") == "13,311"
    assert format_number(13311, "fi") == "13 311"
    assert format_number(13311, "sv") == "13 311"


def test_hakusivu_pysyy_suomenkielisena(client: TestClient) -> None:
    """Haku- ja karttasivuja ei ole käännetty; ne eivät saa kaatua uuteen pohjaan."""
    resp = client.get("/search")
    assert resp.status_code == 200
    assert '<html lang="fi"' in resp.text


def test_kopioitava_osoite_escapataan() -> None:
    """Julkinen osoite tulee pyynnön Host-otsakkeesta, eli käyttäjältä.

    Starlette hylkää nykyään virheellisen Host-otsakkeen, mutta sivu ei saa
    nojata siihen: osoite upotetaan tekstiin ``<code>``-elementtinä, joten
    sen on mentävä escapattuna, muuten väärennetty otsake syöttäisi sivulle
    omaa HTML:ää.
    """
    html = landing_html(TEXTS["fi"], 'http://evil"><script>x()</script>/')
    assert "<script>" not in str(html["connect_quality"])
    assert "&lt;script&gt;" in str(html["connect_quality"])
    assert '<a href="/llms.txt">' in str(html["ai_points"][-1])


def test_mallipohjassa_ei_ole_safe_suodatinta() -> None:
    """HTML:n rakentaminen kuuluu landing_html:ään, ei mallipohjaan."""
    from aura.web.app import TEMPLATES_DIR

    assert "| safe" not in (TEMPLATES_DIR / "index.html").read_text()


@pytest.mark.parametrize("path,lang", [("/", "fi"), ("/en", "en"), ("/sv", "sv")])
def test_tekija_ja_mahdollistaja_nakyvat(client: TestClient, path: str, lang: str) -> None:
    """Tekijä, yhteystieto ja Futuai projektin mahdollistajana kaikilla kielillä.

    Tekijä kuuluu projektiin, ei instanssiin, joten se näkyy myös omalla
    koneella ajettavassa avoimessa versiossa.
    """
    body = client.get(path).text
    assert "Tero Rönkkö" in body
    assert 'href="mailto:tero@futuai.fi"' in body
    assert "Futuai Oy" in body
    assert TEXTS[lang]["author_title"] in body


@pytest.mark.parametrize("path,lang", [("/", "fi"), ("/en", "en"), ("/sv", "sv")])
def test_oma_data_ohjaa_githubiin(client: TestClient, path: str, lang: str) -> None:
    body = client.get(path).text
    assert TEXTS[lang]["own_title"] in body
    section = body.split('id="own-title"')[1].split("</section>")[0]
    assert 'href="https://github.com/trotor/aura"' in section
    assert "mailto:" not in section


def test_llms_txt_kertoo_tekijan(client: TestClient) -> None:
    text = client.get("/llms.txt").text
    assert "Tero Rönkkö" in text
    assert "tero@futuai.fi" in text


@pytest.mark.parametrize("path", ["/", "/en", "/sv"])
def test_etusivulla_avainsanaselain(client: TestClient, path: str) -> None:
    body = client.get(path).text
    assert 'href="/avainsanat"' in body
