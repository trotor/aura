"""Ulkoisten pyyntöjen suojaus: vain julkiset osoitteet, kokoraja.

Web-API haki minkä tahansa ``url``-parametrin palvelimen kautta, myös
sisäverkon osoitteet (SSRF, löydetty 8.10.2026). Nämä testit pitävät
huolen, ettei palvelin tee pyyntöä sisäverkkoon edes uudelleenohjauksen
kautta.
"""

from __future__ import annotations

import httpx
import pytest

from aura.net import (
    BlockedURLError,
    ResponseTooLargeError,
    ensure_public,
    public_client,
    read_capped,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/",
        "http://localhost/",
        "http://10.0.0.5/wfs",
        "http://172.17.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/metadata/instance",
        "http://[::1]/",
        "http://0.0.0.0/",
    ],
)
@pytest.mark.anyio
async def test_sisaverkko_estetaan(url: str) -> None:
    with pytest.raises(BlockedURLError):
        await ensure_public(httpx.Request("GET", url))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://x/"])
@pytest.mark.anyio
async def test_vain_http_ja_https(url: str) -> None:
    with pytest.raises(BlockedURLError):
        await ensure_public(httpx.Request("GET", url))


@pytest.mark.anyio
async def test_julkinen_osoite_sallitaan() -> None:
    await ensure_public(httpx.Request("GET", "https://93.184.215.14/wfs"))


@pytest.mark.anyio
async def test_uudelleenohjaus_sisaverkkoon_estetaan() -> None:
    """Julkinen palvelu voi ohjata sisäverkkoon; jokainen hyppy tarkistetaan."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.215.14":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:9/salaisuus"})
        return httpx.Response(200, text="sisäverkon data")

    async with public_client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BlockedURLError):
            await client.get("https://93.184.215.14/wfs", follow_redirects=True)


@pytest.mark.anyio
async def test_kokoraja() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    async with public_client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ResponseTooLargeError):
            await read_capped(client, "https://93.184.215.14/", limit=1000)
        resp, body = await read_capped(client, "https://93.184.215.14/", limit=10_000)
        assert resp.status_code == 200
        assert len(body) == 5000


@pytest.mark.anyio
async def test_query_source_ja_esikatselu_kayttavat_suojattua_asiakasta() -> None:
    """Katalogin osoite voi osoittaa sisäverkkoon (vanhentunut verkkotunnus)."""
    from aura import fetch, preview

    async with fetch._client() as client:
        with pytest.raises(BlockedURLError):
            await client.get("http://127.0.0.1:9/data.csv")
    async with preview._asiakas(None) as client:
        with pytest.raises(BlockedURLError):
            await client.get("http://169.254.169.254/latest/meta-data")


@pytest.mark.anyio
async def test_estetty_osoite_on_httpx_virhe() -> None:
    """Olemassa oleva ``except httpx.HTTPError`` käsittelee estetyn osoitteen."""
    with pytest.raises(httpx.HTTPError):
        await ensure_public(httpx.Request("GET", "http://10.0.0.1/"))


@pytest.mark.anyio
async def test_kokoraja_ilman_content_length_otsaketta() -> None:
    """Chunked-vastaus ilman Content-Lengthiä ei saa ohittaa rajaa (katselmointi)."""

    async def body():
        for _ in range(50):
            yield b"x" * 1000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())

    async with public_client(
        transport=httpx.MockTransport(handler), max_content_length=10_000
    ) as client:
        with pytest.raises(ResponseTooLargeError):
            await client.get("https://93.184.215.14/iso")


@pytest.mark.anyio
async def test_kokoraja_ei_esta_pientaa_vastausta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ok")

    async with public_client(
        transport=httpx.MockTransport(handler), max_content_length=10_000
    ) as client:
        assert (await client.get("https://93.184.215.14/")).text == "ok"
