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
from typing import Any

import httpx

#: Oletuskokoraja vastaukselle. GetCapabilities-dokumentit ovat isoimmillaan
#: noin 1 MB (Luken MVMI 0,9 MB), WFS-featuret 500 kohteella muutamia megoja.
DEFAULT_LIMIT = 20 * 1024 * 1024


class BlockedURLError(ValueError):
    """Osoitetta ei saa hakea: väärä skeema tai ei-julkinen kohde."""


class ResponseTooLargeError(ValueError):
    """Vastaus ylitti kokorajan."""


async def ensure_public(request: httpx.Request) -> None:
    """Hylkää pyyntö jos skeema ei ole http(s) tai kohde ei ole julkinen.

    Toimii httpx:n ``request``-tapahtumakoukkuna, joten se ajetaan myös
    jokaiselle uudelleenohjauksen pyynnölle.
    """
    url = request.url
    if url.scheme not in ("http", "https"):
        raise BlockedURLError(f"skeema {url.scheme!r} ei ole sallittu")
    host = url.host
    if not host:
        raise BlockedURLError("osoitteessa ei ole isäntää")
    port = url.port or (443 if url.scheme == "https" else 80)
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port)
    except OSError as exc:
        raise BlockedURLError(f"isäntää {host} ei voitu selvittää") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise BlockedURLError(f"isäntä {host} ei ole julkisessa verkossa")


def public_client(**kwargs: Any) -> httpx.AsyncClient:
    """httpx-asiakas joka tarkistaa jokaisen pyynnön ``ensure_public``illa."""
    hooks = kwargs.pop("event_hooks", {}) or {}
    hooks = {**hooks, "request": [ensure_public, *hooks.get("request", [])]}
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
                raise ResponseTooLargeError(f"vastaus ylitti {limit} tavua")
            chunks.append(chunk)
    return response, b"".join(chunks)
