"""Ulkoiset pyynnöt käyttäjän antamiin tai katalogin osoitteisiin.

**Miksi.** Web-API:n karttanäkymä haki minkä tahansa ``url``-parametrin
palvelimen kautta (löydetty 8.10.2026). Julkisella palvelimella se on avoin
välityspalvelin: kuka tahansa saattoi hakea palvelimen sisäverkosta
(docker-silta, saman koneen muut palvelut) ja käyttää palvelinta
anonymisoivana välikätenä. Rajaton vastaus olisi myös kaatanut kontin muistin.

Kolme suojaa, jotka pätevät jokaiseen tämän moduulin kautta tehtyyn pyyntöön:

- vain ``http`` ja ``https``
- kohteen kaikkien osoitteiden on oltava julkisia (``ipaddress.is_global``)
  — tarkistus tehdään **jokaiselle uudelleenohjauksen hypylle**, koska
  julkinen palvelu voi ohjata sisäverkkoon
- vastaus luetaan virtana ja keskeytetään kokorajalla

Jäännösriski: nimipalvelun vastaus voi muuttua tarkistuksen ja yhteyden
välillä (DNS rebinding). Se vaatisi hyökkääjän hallitseman nimipalvelun ja
katalogissa olevan osoitteen; web-API hyväksyy vain katalogin osoitteita.
"""

from __future__ import annotations

import asyncio
import ipaddress
import zlib
from typing import Any

import httpx

#: Oletuskokoraja vastaukselle. GetCapabilities-dokumentit ovat isoimmillaan
#: noin 1 MB (Luken MVMI 0,9 MB), WFS-featuret 500 kohteella muutamia megoja.
DEFAULT_LIMIT = 20 * 1024 * 1024


class BlockedURLError(httpx.RequestError):
    """Osoitetta ei saa hakea: väärä skeema tai ei-julkinen kohde.

    ``httpx.RequestError``in aliluokka, jotta olemassa oleva verkkovirheiden
    käsittely (``except httpx.HTTPError``) kohtelee sitä kuten mitä tahansa
    tavoittamatonta palvelua eikä työkalu kaadu.
    """


class ResponseTooLargeError(httpx.RequestError):
    """Vastaus ylitti kokorajan."""


async def ensure_public(request: httpx.Request) -> None:
    """Hylkää pyyntö jos skeema ei ole http(s) tai kohde ei ole julkinen.

    Toimii httpx:n ``request``-tapahtumakoukkuna, joten se ajetaan myös
    jokaiselle uudelleenohjauksen pyynnölle.
    """
    url = request.url
    if url.scheme not in ("http", "https"):
        raise BlockedURLError(f"skeema {url.scheme!r} ei ole sallittu", request=request)
    host = url.host
    if not host:
        raise BlockedURLError("osoitteessa ei ole isäntää", request=request)
    port = url.port or (443 if url.scheme == "https" else 80)
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port)
    except OSError as exc:
        raise BlockedURLError(f"isäntää {host} ei voitu selvittää", request=request) from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise BlockedURLError(f"isäntä {host} ei ole julkisessa verkossa", request=request)


#: Pakkaukset jotka puretaan itse rajatusti. Muita ei pyydetä.
_DECODED_ENCODINGS = {"gzip", "x-gzip", "deflate"}
#: zlib tunnistaa gzip- ja zlib-otsakkeen itse (32 + MAX_WBITS).
_AUTO_WBITS = 32 + 15


class _CappedStream(httpx.AsyncByteStream):
    """Vastausvirta joka keskeytyy, kun tavuja on yli rajan.

    Pakattu vastaus puretaan tässä eikä httpx:ssä, ja raja lasketaan
    **puretuista** tavuista: 20 kt:n gzip voi purkautua gigatavuiksi
    (katselmointi 8.10.2026). Purku tehdään rajatuissa paloissa
    (``max_length``), joten yksikään välivaihe ei ylitä rajaa paljon.
    """

    def __init__(
        self,
        inner: httpx.AsyncByteStream,
        limit: int,
        request: httpx.Request,
        decode: bool,
    ) -> None:
        self._inner = inner
        self._limit = limit
        self._request = request
        self._decode = decode

    def _too_large(self) -> ResponseTooLargeError:
        return ResponseTooLargeError(
            f"vastaus ylitti {self._limit} tavua", request=self._request
        )

    async def __aiter__(self) -> Any:
        size = 0
        decompressor = zlib.decompressobj(_AUTO_WBITS) if self._decode else None
        async for chunk in self._inner:
            if decompressor is None:
                size += len(chunk)
                if size > self._limit:
                    raise self._too_large()
                yield chunk
                continue
            data = chunk
            while data:
                try:
                    out = decompressor.decompress(data, self._limit - size + 1)
                except zlib.error as exc:
                    raise httpx.DecodingError(str(exc), request=self._request) from exc
                size += len(out)
                if size > self._limit:
                    raise self._too_large()
                if out:
                    yield out
                data = decompressor.unconsumed_tail
        if decompressor is not None:
            tail = decompressor.flush()
            size += len(tail)
            if size > self._limit:
                raise self._too_large()
            if tail:
                yield tail

    async def aclose(self) -> None:
        await self._inner.aclose()


class _CappedTransport(httpx.AsyncBaseTransport):
    """Kuljetus joka rajaa jokaisen vastauksen tavut.

    ``Content-Length``-otsakkeeseen ei voi luottaa: chunked-vastauksella sitä
    ei ole, ja pakatulla vastauksella se kertoo pakatun koon. Raja koskee
    siksi purettua virtaa; ilmoitettu liian iso koko hylätään jo ennen
    lukemista.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, limit: int) -> None:
        self._inner = inner
        self._limit = limit

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers["accept-encoding"] = "gzip, deflate"
        response = await self._inner.handle_async_request(request)
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self._limit:
            await response.aclose()
            raise ResponseTooLargeError(
                f"vastaus {declared} tavua ylittää rajan {self._limit}", request=request
            )
        encoding = response.headers.get("content-encoding", "").strip().lower()
        decode = encoding in _DECODED_ENCODINGS
        if decode:
            # Purettu virta: httpx ei saa purkaa toista kertaa, eikä pakatun
            # koon Content-Length pidä enää paikkaansa.
            del response.headers["content-encoding"]
            if "content-length" in response.headers:
                del response.headers["content-length"]
        stream = response.stream
        assert isinstance(stream, httpx.AsyncByteStream)
        response.stream = _CappedStream(stream, self._limit, request, decode)
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


def public_client(
    *, max_content_length: int | None = None, **kwargs: Any
) -> httpx.AsyncClient:
    """httpx-asiakas joka tarkistaa jokaisen pyynnön ``ensure_public``illa.

    ``max_content_length`` rajaa jokaisen vastauksen luetut tavut (myös
    chunked-vastauksilla). Virtana luettavat koodipolut (``read_capped``,
    ``fetch._download``, CSV-esikatselu) rajaavat itse eivätkä käytä sitä;
    ne lukevat isosta tiedostosta vain alun.
    """
    hooks = dict(kwargs.pop("event_hooks", {}) or {})
    hooks["request"] = [ensure_public, *hooks.get("request", [])]
    if max_content_length is not None:
        inner = kwargs.pop("transport", None) or httpx.AsyncHTTPTransport()
        kwargs["transport"] = _CappedTransport(inner, max_content_length)
    return httpx.AsyncClient(event_hooks=hooks, **kwargs)


async def read_capped(
    client: httpx.AsyncClient,
    url: str,
    *,
    limit: int = DEFAULT_LIMIT,
    **kwargs: Any,
) -> tuple[httpx.Response, bytes]:
    """GET virtana; keskeytä jos vastaus kasvaa yli ``limit`` tavun."""
    async with client.stream("GET", url, **kwargs) as response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > limit:
                raise ResponseTooLargeError(
                    f"vastaus ylitti {limit} tavua", request=response.request
                )
            chunks.append(chunk)
    return response, b"".join(chunks)
