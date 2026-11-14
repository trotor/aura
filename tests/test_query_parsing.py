"""Rivien jäsennys lähteistä, jotka query_source ja web-esikatselu tarjosivat
kyseltävinä mutta joista ei saatu rivejä (arvio 13.11.2026).

- Eduskunnan rajapinta palauttaa ``columnNames`` + ``rowData`` (rivit listoina).
- VTV:n vaalirahoitus-CSV:t käyttävät lainausmerkkinä heittomerkkiä.
- Katalogin yhdistelmäformaatti ``"JSON, JSONP"`` ei ollut kyseltävä.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from aura import fetch

EDUSKUNTA = {
    "page": 0,
    "perPage": 2,
    "hasMore": True,
    "tableName": "MemberOfParliament",
    "columnNames": ["personId", "lastname", "firstname", "party"],
    "rowData": [["102", " Aaltonen", "Markus", "kesk"], ["103", "Aho", "Esko", "kesk"]],
}

VAALIRAHOITUS = (
    "'Ehdokasnumero';'Etunimet';'Puolue';'Vaalikampanjan kulut yhteensa'\n"
    "'0067';'Mia';'VAS';'10299'\n"
    "'0070';'Veronika';'VAS';'25000'\n"
)


def _fake_download(payload: bytes) -> Any:
    async def fake(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        return payload, False

    return fake


# --- Eduskunta: columnNames + rowData ---


@pytest.mark.asyncio
async def test_eduskunnan_rivit_sarakenimilla() -> None:
    payload = json.dumps(EDUSKUNTA).encode()
    with patch.object(fetch, "_download", _fake_download(payload)):
        table = await fetch.fetch_json("https://avoindata.eduskunta.fi/x", None, 50)
    assert table.error is None
    assert table.columns == ["personId", "lastname", "firstname", "party"]
    assert table.rows[1]["firstname"] == "Esko"


@pytest.mark.asyncio
async def test_eduskunnan_rivit_suodatettavissa() -> None:
    payload = json.dumps(EDUSKUNTA).encode()
    with patch.object(fetch, "_download", _fake_download(payload)):
        table = await fetch.fetch_json(
            "https://avoindata.eduskunta.fi/x", {"lastname": ["Aho"]}, 50
        )
    assert [r["personId"] for r in table.rows] == ["103"]


@pytest.mark.asyncio
async def test_eduskunnan_sivu_ei_vaita_kokonaismaaraa() -> None:
    # hasMore=True: vastaus on yksi sivu, joten sivun rivimäärä ei ole lähteen koko.
    payload = json.dumps(EDUSKUNTA).encode()
    with patch.object(fetch, "_download", _fake_download(payload)):
        table = await fetch.fetch_json("https://avoindata.eduskunta.fi/x", None, 50)
    assert table.total is None
    assert table.truncated is True


def test_eduskunnan_suodatin_palvelimelle() -> None:
    url = fetch.eduskunta_filter_url(
        "https://avoindata.eduskunta.fi/api/v1/tables/MemberOfParliament/rows",
        {"lastname": ["Marin"]},
    )
    assert "columnName=lastname" in url
    assert "columnValue=Marin" in url


def test_eduskunnan_suodatin_vain_yksiselitteisesta() -> None:
    # Rajapinta tuntee yhden sarakkeen ja yhden arvon; muut suodatetaan sivulta.
    base = "https://avoindata.eduskunta.fi/api/v1/tables/MemberOfParliament/rows"
    assert fetch.eduskunta_filter_url(base, {"lastname": ["Marin", "Orpo"]}) == base


@pytest.mark.asyncio
async def test_eduskunnan_kysely_suodattaa_palvelimella() -> None:
    seen: list[str] = []
    one = {**EDUSKUNTA, "hasMore": False, "rowData": [["1297", "Marin", "Sanna", "sd"]]}

    async def fake(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        seen.append(url)
        return json.dumps(one).encode(), False

    with patch.object(fetch, "_download", fake):
        table = await fetch.fetch_json(
            "https://avoindata.eduskunta.fi/api/v1/tables/MemberOfParliament/rows",
            {"lastname": ["Marin"]},
            50,
        )
    assert "columnValue=Marin" in seen[0]
    assert [r["firstname"] for r in table.rows] == ["Sanna"]
    assert any("palvelimella" in n for n in table.notes)


MEMBERS_URL = "https://avoindata.eduskunta.fi/api/v1/tables/MemberOfParliament/rows"


def _eduskunta_fake(filtered: Any, seen: list[str]) -> Any:
    """Suodatettu URL palauttaa ``filtered`` (bytes tai poikkeus), muut koko sivun."""

    async def fake(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        seen.append(url)
        if "columnValue" in url:
            if isinstance(filtered, Exception):
                raise filtered
            return filtered, False
        return json.dumps(EDUSKUNTA).encode(), False

    return fake


@pytest.mark.asyncio
async def test_eduskunta_palaa_sivusuodatukseen_kun_tasmallinen_ei_osu() -> None:
    # Palvelin vertaa täsmällisesti ja kirjainkoko huomioiden: "aho" ei osu
    # riviin "Aho". Tyhjä vastaus ei ole "ei osumia", vaan sivu suodatetaan.
    seen: list[str] = []
    empty = json.dumps({**EDUSKUNTA, "hasMore": False, "rowData": []}).encode()
    with patch.object(fetch, "_download", _eduskunta_fake(empty, seen)):
        table = await fetch.fetch_json(MEMBERS_URL, {"lastname": ["aho"]}, 50)
    assert len(seen) == 2
    assert [r["personId"] for r in table.rows] == ["103"]
    assert table.error is None


@pytest.mark.asyncio
async def test_eduskunta_tuntematon_sarake_ei_kaada() -> None:
    # Tuntematon sarake: palvelin vastaa 400. Sivulta tulee unknown_filter-virhe
    # sarakelistan kanssa, ei HTTP-virhettä.
    seen: list[str] = []
    request = httpx.Request("GET", MEMBERS_URL)
    error = httpx.HTTPStatusError(
        "400", request=request, response=httpx.Response(400, request=request)
    )
    with patch.object(fetch, "_download", _eduskunta_fake(error, seen)):
        table = await fetch.fetch_json(MEMBERS_URL, {"eiole": ["x"]}, 50)
    assert table.error_code == "unknown_filter"
    assert "lastname" in (table.error or "")


@pytest.mark.asyncio
async def test_eduskunta_palvelinsuodatus_monisivuinen() -> None:
    # Suodatettu tulos on itsekin monisivuinen: ei väitetä koko taulun kattamista.
    seen: list[str] = []
    many = json.dumps({**EDUSKUNTA, "hasMore": True}).encode()
    with patch.object(fetch, "_download", _eduskunta_fake(many, seen)):
        table = await fetch.fetch_json(MEMBERS_URL, {"party": ["kesk"]}, 50)
    assert table.truncated is True
    assert not any("koko taulun" in n for n in table.notes)


@pytest.mark.asyncio
async def test_hasmore_ei_hylkaa_lahteen_omaa_kokonaismaaraa() -> None:
    data = {"total": 500, "hasMore": True, "items": [{"a": 1}, {"a": 2}]}
    with patch.object(fetch, "_download", _fake_download(json.dumps(data).encode())):
        table = await fetch.fetch_json("https://x.fi/api", None, 50)
    assert table.total == 500


@pytest.mark.asyncio
async def test_eduskunta_iso_sivu_haetaan_pienempana() -> None:
    # VaskiDatan 100 asiakirjan sivu ylittää latausrajan: katkaistu JSON ei
    # jäsenny. Pienempi sivu (perPage) mahtuu.
    seen: list[str] = []

    async def fake(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        seen.append(url)
        if "perPage=" in url:
            return json.dumps(EDUSKUNTA).encode(), False
        return json.dumps(EDUSKUNTA).encode()[:40], True

    with patch.object(fetch, "_download", fake):
        table = await fetch.fetch_json(
            "https://avoindata.eduskunta.fi/api/v1/tables/VaskiData/rows", None, 50
        )
    assert table.error is None
    assert len(table.rows) == 2
    assert "perPage=" in seen[-1]


@pytest.mark.asyncio
async def test_eduskunta_suodatettu_iso_sivu_haetaan_pienempana() -> None:
    # Suodatettukin VaskiData-sivu ylittää latausrajan. Katkaisu ei ole
    # "ei osumia": suodatettu kysely toistetaan pienellä sivulla.
    seen: list[str] = []
    one = {**EDUSKUNTA, "hasMore": False, "rowData": [["5", "x", "y", "z"]]}

    async def fake(url: str, *a: Any, **kw: Any) -> tuple[bytes, bool]:
        seen.append(url)
        if "perPage=" in url:
            return json.dumps(one).encode(), False
        return json.dumps(EDUSKUNTA).encode()[:40], True

    with patch.object(fetch, "_download", fake):
        table = await fetch.fetch_json(
            "https://avoindata.eduskunta.fi/api/v1/tables/VaskiData/rows",
            {"personId": ["5"]},
            50,
        )
    assert "columnValue=5" in seen[-1] and "perPage=" in seen[-1]
    assert [r["personId"] for r in table.rows] == ["5"]
    assert any("palvelimella" in n for n in table.notes)


# --- CSV: lainausmerkki päätellään ---


@pytest.mark.asyncio
async def test_heittomerkkilainattu_csv() -> None:
    with patch.object(fetch, "_download", _fake_download(VAALIRAHOITUS.encode())):
        table = await fetch.fetch_csv("https://x.fi/a.csv", None, None, 50)
    assert table.columns == ["Ehdokasnumero", "Etunimet", "Puolue", "Vaalikampanjan kulut yhteensa"]
    assert table.rows[0]["Etunimet"] == "Mia"
    assert table.rows[1]["Vaalikampanjan kulut yhteensa"] == 25000
    # Etunollallinen koodi pysyy koodina
    assert table.rows[0]["Ehdokasnumero"] == "0067"


@pytest.mark.asyncio
async def test_lainausmerkillinen_csv_ennallaan() -> None:
    text = '"nimi";"kuvaus"\n"A";"pitkä; puolipisteellinen"\n'
    with patch.object(fetch, "_download", _fake_download(text.encode())):
        table = await fetch.fetch_csv("https://x.fi/a.csv", None, None, 50)
    assert table.columns == ["nimi", "kuvaus"]
    assert table.rows[0]["kuvaus"] == "pitkä; puolipisteellinen"


def test_heittomerkki_sanan_sisalla_ei_ole_lainausmerkki() -> None:
    assert fetch.csv_dialect("nimi;Lapin l'aani;arvo") == (";", '"')


@pytest.mark.asyncio
async def test_tyhja_otsikkosarake_ei_rivien_avaimena() -> None:
    # VTV:n rahoitusriveissä otsikko päättyy erottimeen: tyhjä sarake.
    text = "'a';'b';\n'1';'2';\n"
    with patch.object(fetch, "_download", _fake_download(text.encode())):
        table = await fetch.fetch_csv("https://x.fi/a.csv", None, None, 50)
    assert table.columns == ["a", "b"]
    assert set(table.rows[0]) == {"a", "b"}


# --- Yhdistelmäformaatit ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("JSON, JSONP", "JSON"),
        ("JSON/REST", "JSON/REST"),
        ("json", "JSON"),
        ("XLSX, CSV", "XLSX, CSV"),
        ("WEBSOCKET/JSON", "WEBSOCKET/JSON"),
        ("JSON, XML", "JSON, XML"),
    ],
)
def test_saman_protokollan_yhdistelma_normalisoidaan(raw: str, expected: str) -> None:
    from aura.formats import normalize_format

    assert normalize_format(raw) == expected


def test_resurssin_formaatti_yhdistelmasta() -> None:
    from aura.formats import resource_format

    assert resource_format({"format": "JSON, JSONP", "url": "https://x.fi/api"}) == "JSON"


def test_find_data_nayttaa_yhdistelman_kyseltavana() -> None:
    from aura.tools.find import _hit

    hit = _hit({"id": "x", "title": "Aloitteet"}, {"JSON, JSONP"}, None, None, None)
    assert hit.queryable is True


# --- Web-esikatselu käyttää samoja jäsentimiä ---


def test_web_esikatselu_eduskunta_taulukkona() -> None:
    from aura.web.routes.api import _json_preview

    out = _json_preview(EDUSKUNTA, 10)
    assert out["type"] == "table"
    assert out["rows"][0]["lastname"] == " Aaltonen"


def test_web_esikatselu_heittomerkki_csv() -> None:
    from aura.web.routes.api import _csv_preview

    out = _csv_preview(VAALIRAHOITUS, 10)
    assert out["headers"] == [
        "Ehdokasnumero",
        "Etunimet",
        "Puolue",
        "Vaalikampanjan kulut yhteensa",
    ]
    assert out["rows"][0] == ["0067", "Mia", "VAS", "10299"]
