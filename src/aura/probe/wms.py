"""WMS-prober: layerien nimet ja otsikot.

WMS ei tarjoa sarakkeita. Sen tulos ei siksi mene resource_schemaan vaan
omaan service_layers-kenttäänsä — layer-listan esittäminen kenttätietona
antaisi lukijalle väärän kuvan siitä mitä aineistosta saa irti.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus
from aura.wfs import _local, _root, exception_text


def parse_layers(body: str) -> list[dict[str, str]]:
    """Poimi kysyttävät layerit GetCapabilities-vastauksesta.

    Nimetön layer on kokoava kääre, ei kerros jota voi kysyä; se ohitetaan.
    """
    root = _root(body)
    if root is None:
        return []
    layers: list[dict[str, str]] = []
    for el in root.iter():
        if _local(el.tag) != "Layer":
            continue
        nimi = next((c.text or "" for c in el if _local(c.tag) == "Name"), "").strip()
        if not nimi:
            continue
        otsikko = next((c.text or "" for c in el if _local(c.tag) == "Title"), "").strip()
        layers.append({"name": nimi, "title": otsikko})
    return layers


async def probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Hae WMS-palvelun layerit."""
    base_url = resource.get("url", "").split("?")[0]
    params = {"service": "WMS", "version": "1.3.0", "request": "GetCapabilities"}
    try:
        resp = await client.get(base_url, params=params, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="GetCapabilities")
    if resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {resp.status_code}",
            http_status=resp.status_code,
        )

    layers = parse_layers(resp.text)
    if not layers:
        virhe = exception_text(resp.text) or "GetCapabilities ei sisältänyt layereita"
        return ProbeResult(
            status=ProbeStatus.EMPTY, detail=virhe, http_status=resp.status_code
        )

    arvo = json.dumps(layers, ensure_ascii=False)
    return ProbeResult(
        status=ProbeStatus.OK,
        enrichments=[("service_layers", arvo)],
        http_status=resp.status_code,
    )
