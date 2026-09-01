"""CSV- ja JSON-prober: nykyinen esikatselupolku siirrettynä.

Käytös on sama kuin ``infer-schemas``-komennolla ennen: esikatselu, sitten
tyyppipäättely otsikkorivistä. Ero on että tulos palautuu eikä kirjoittaudu
suoraan kantaan — ilman sitä epäonnistumista ei voi kirjata eikä TTL:ää
laskea.
"""

from __future__ import annotations

from typing import Any

import httpx

from aura.preview import _preview_csv, _preview_json
from aura.probe.types import ProbeResult, ProbeStatus
from aura.schema_infer import infer_type, parse_md_table

_PREVIEW_ROWS = 10


async def probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Päättele sarakkeet ja tyypit esikatselusta.

    ``client`` on mukana rajapinnan yhtenäisyyden vuoksi; esikatselufunktiot
    avaavat oman yhteytensä.
    """
    url = resource.get("url", "")
    fmt = (resource.get("format") or "").upper()

    try:
        if fmt == "CSV":
            body = await _preview_csv(url, _PREVIEW_ROWS)
        else:
            body = await _preview_json(url, _PREVIEW_ROWS)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="esikatselu")
    except httpx.HTTPStatusError as e:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {e.response.status_code}",
            http_status=e.response.status_code,
        )
    except httpx.HTTPError as e:
        return ProbeResult(status=ProbeStatus.HTTP_ERROR, detail=str(e)[:100])

    headers, rows = parse_md_table(body)
    if not headers:
        return ProbeResult(status=ProbeStatus.EMPTY, detail=body[:100])

    fields: list[tuple[str, str]] = []
    for i, header in enumerate(headers):
        col_values = [r[i] for r in rows if i < len(r)]
        fields.append((header, infer_type(col_values)))

    return ProbeResult(status=ProbeStatus.OK, fields=fields, http_status=200)
