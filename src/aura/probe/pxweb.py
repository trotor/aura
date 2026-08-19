"""PxWeb-prober: taulun dimensiot ja luokitusarvot.

Muoto on harvesterin määräämä: {code, name, value_count, examples}.
region_levels.py lukee sitä tunnistaakseen kuntadimension, ja se ohjaa
hakutuloksen aluelaajennusta — eri muoto rikkoisi sen hiljaa.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus

#: Esimerkkiarvoja per dimensio. Koko luokitus veisi tilan kertomatta enempää.
_MAX_EXAMPLES = 5


def parse_dimensions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Muunna PxWeb-metadata harvesterin data_fields-muotoon.

    ``value_count`` lasketaan ``values``-listasta — se on dimension
    todellinen koko, kun taas ``examples`` on korkeintaan viisi
    ensimmäistä ihmisluettavaa arvoa (``valueTexts``, tai ``values``
    jos tekstejä ei ole).
    """
    dims: list[dict[str, Any]] = []
    for var in payload.get("variables", []):
        values = var.get("values", [])
        texts = var.get("valueTexts") or values
        dims.append(
            {
                "code": var.get("code", ""),
                "name": var.get("text", var.get("code", "")),
                "value_count": len(values),
                "examples": [str(t) for t in texts[:_MAX_EXAMPLES]],
            }
        )
    return dims


async def probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Hae PxWeb-taulun dimensiot ja luokitusarvot."""
    url = resource.get("url", "")
    try:
        resp = await client.get(url, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="metadata")
    if resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {resp.status_code}",
            http_status=resp.status_code,
        )

    try:
        payload = resp.json()
    except ValueError:
        return ProbeResult(
            status=ProbeStatus.PARSE_ERROR,
            detail="Vastaus ei ole JSONia",
            http_status=resp.status_code,
        )

    dims = parse_dimensions(payload)
    if not dims:
        return ProbeResult(
            status=ProbeStatus.EMPTY,
            detail="Taululla ei ole dimensioita",
            http_status=resp.status_code,
        )

    return ProbeResult(
        status=ProbeStatus.OK,
        enrichments=[("data_fields", json.dumps(dims, ensure_ascii=False))],
        http_status=resp.status_code,
    )
