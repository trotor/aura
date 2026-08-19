"""Testit CSV/JSON-proberille.

Tämä on nykyinen infer-schemas-polku siirrettynä. Käytös ei muutu, joten
testit kiinnittävät sen: samat kentät, sama tyyppipäättely. Uutta on vain
se että tulos palautuu eikä kirjoittaudu suoraan kantaan — ilman sitä
epäonnistumista ei voi kirjata eikä TTL:ää laskea.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aura.probe.tabular import probe
from aura.probe.types import ProbeStatus


@pytest.mark.anyio
async def test_csv_otsikkorivi_tuottaa_kentat() -> None:
    markdown = (
        "| kuntakoodi | nimi | vaesto |\n"
        "| --- | --- | --- |\n"
        "| 091 | Helsinki | 664000 |\n"
    )
    with patch("aura.probe.tabular._preview_csv", AsyncMock(return_value=markdown)):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.OK
    assert tulos.http_status == 200
    kentat = dict(tulos.fields)
    assert kentat["kuntakoodi"] == "integer"
    assert kentat["nimi"] == "string"
    assert kentat["vaesto"] == "integer"
    assert tulos.enrichments == []


@pytest.mark.anyio
async def test_json_muoto_kutsuu_preview_jsonia() -> None:
    """Format-kentän ollessa muu kuin CSV (esim. JSON/GEOJSON) esikatsellaan JSONina.

    Jos esikatselufunktion valinta menisi väärin, testi kutsuisi
    _preview_csv:tä eikä _preview_json:ia — mockit paljastaisivat tämän.
    """
    markdown = (
        "| kuntakoodi | nimi |\n"
        "| --- | --- |\n"
        "| 091 | Helsinki |\n"
    )
    with (
        patch("aura.probe.tabular._preview_json", AsyncMock(return_value=markdown)) as m_json,
        patch("aura.probe.tabular._preview_csv", AsyncMock()) as m_csv,
    ):
        tulos = await probe(
            {"url": "https://example.test/a.json", "format": "JSON"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.OK
    m_json.assert_awaited_once()
    m_csv.assert_not_called()


@pytest.mark.anyio
async def test_tyhja_esikatselu_on_empty() -> None:
    with patch(
        "aura.probe.tabular._preview_csv", AsyncMock(return_value="CSV-tiedosto on tyhjä.")
    ):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.EMPTY
    assert tulos.detail == "CSV-tiedosto on tyhjä."
    assert tulos.fields == []


@pytest.mark.anyio
async def test_verkkovirhe_kirjautuu_timeoutina() -> None:
    with patch(
        "aura.probe.tabular._preview_csv",
        AsyncMock(side_effect=httpx.TimeoutException("hidas")),
    ):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.TIMEOUT
    assert tulos.detail == "esikatselu"
    assert tulos.fields == []


@pytest.mark.anyio
async def test_http_statuskoodivirhe_kirjautuu_koodina() -> None:
    """_preview_csv nostaa HTTPStatusErrorin resp.raise_for_status()-kutsusta."""
    error_response = MagicMock(spec=httpx.Response)
    error_response.status_code = 404
    with patch(
        "aura.probe.tabular._preview_csv",
        AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=error_response
            )
        ),
    ):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.HTTP_ERROR
    assert tulos.detail == "HTTP 404"
    assert tulos.http_status == 404
    assert tulos.fields == []


@pytest.mark.anyio
async def test_muu_verkkovirhe_kirjautuu_http_errorina() -> None:
    """Yhteysvirhe (esim. DNS-epäonnistuminen) ei ole timeout eikä statuskoodi."""
    with patch(
        "aura.probe.tabular._preview_csv",
        AsyncMock(side_effect=httpx.ConnectError("nimenselvitys epäonnistui")),
    ):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.HTTP_ERROR
    assert "nimenselvitys" in tulos.detail
    assert tulos.http_status is None
    assert tulos.fields == []
