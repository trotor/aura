"""Data preview -apufunktiot.

Käytetään query_data-työkalusta. Ei rekisteröi omia MCP-työkaluja.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import urllib.parse
from typing import Any

import httpx

from aura.constants import PREVIEWABLE_FORMATS, user_agent

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_BYTES = 1_048_576  # 1 MB
_STREAM_CHUNK_LIMIT = 8192  # 8 KB for CSV streaming
_HTTP_TIMEOUT = 15.0


def _pick_resource(
    resources: list[dict[str, Any]],
    resource_index: int | None = None,
    format_hint: str = "",
) -> dict[str, Any] | None:
    """Valitse paras resurssi esikatseluun."""
    if not resources:
        return None
    if resource_index is not None:
        if 0 <= resource_index < len(resources):
            return resources[resource_index]
        return None
    if format_hint:
        hint = format_hint.upper()
        for r in resources:
            if (r.get("format") or "").upper() == hint:
                return r
    # Suosi formaatteja joille kysely osaa tehdä jotain. Koneluettavuus on
    # eri asia: XLSX on koneluettava mutta esikatselu ei osaa avata sitä.
    for r in resources:
        if (r.get("format") or "").upper() in PREVIEWABLE_FORMATS:
            return r
    return resources[0]


def _format_md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Muodosta markdown-taulukko."""
    if not headers:
        return ""
    parts = ["| " + " | ".join(headers) + " |"]
    parts.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        # Padaa/truncatoi rivit header-pituuteen
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        cells = [str(c).replace("|", "\\|").replace("\n", " ")[:80] for c in padded[:len(headers)]]
        parts.append("| " + " | ".join(cells) + " |")
    return "\n".join(parts)


async def _preview_csv(url: str, max_rows: int) -> str:
    """Esikatsele CSV-resurssi."""
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": user_agent()},
    ) as client:
        async with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            content = b""
            async for chunk in resp.aiter_bytes():
                content += chunk
                if len(content) > _STREAM_CHUNK_LIMIT:
                    break

    text = content.decode("utf-8", errors="replace")

    # Tunnista erotin: puolipiste vai pilkku
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows_list: list[list[str]] = []
    for csv_row in reader:
        rows_list.append(csv_row)
        if len(rows_list) > max_rows + 1:
            break

    if not rows_list:
        return "CSV-tiedosto on tyhjä."

    headers = rows_list[0]
    data_rows = rows_list[1 : max_rows + 1]
    total_note = f"\n\n*Näytetään {len(data_rows)} ensimmäistä riviä.*"
    return _format_md_table(headers, data_rows) + total_note


async def _preview_json(url: str, max_rows: int) -> str:
    """Esikatsele JSON/GeoJSON-resurssi."""
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": user_agent()},
    ) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        # Rajoita luetun vastauksen kokoa
        text = resp.text[:_MAX_DOWNLOAD_BYTES]

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        snippet = text[:2000]
        return f"Vastaus ei ole kelvollista JSON:ia. Alku:\n```\n{snippet}\n```"

    # GeoJSON FeatureCollection
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            return "GeoJSON FeatureCollection on tyhjä."
        rows = [f.get("properties", {}) for f in features[:max_rows]]
        headers = list(rows[0].keys()) if rows else []
        table_rows = [[str(r.get(h, "")) for h in headers] for r in rows]
        return (
            f"**GeoJSON** — {len(features)} kohdetta\n\n"
            + _format_md_table(headers, table_rows)
        )

    # Lista objekteja
    if isinstance(data, list) and data and isinstance(data[0], dict):
        headers = list(data[0].keys())
        table_rows = [[str(r.get(h, "")) for h in headers] for r in data[:max_rows]]
        return (
            f"**JSON** — {len(data)} kohdetta\n\n"
            + _format_md_table(headers, table_rows)
        )

    # Muu JSON
    snippet = json.dumps(data, ensure_ascii=False, indent=2)[:3000]
    return f"**JSON:**\n```json\n{snippet}\n```"


async def _preview_pxweb(
    url: str,
    dataset: dict[str, Any],
    enrichments: list[dict[str, Any]],
) -> str:
    """Esikatsele PxWeb-taulu: näytä dimensiot ja esimerkkiarvot."""
    # Tarkista löytyykö data_fields enrichment jo valmiina
    for e in enrichments:
        if e.get("field") == "data_fields":
            try:
                fields = json.loads(e["value"])
                parts = ["**PxWeb-taulun dimensiot** (enrichmentistä):\n"]
                for f in fields:
                    name = f.get("name", f.get("code", "?"))
                    code = f.get("code", "")
                    count = f.get("value_count", 0)
                    examples = f.get("examples", [])
                    ex_str = ", ".join(str(x) for x in examples[:5])
                    parts.append(f"- **{name}** (`{code}`): {count} arvoa")
                    if ex_str:
                        parts.append(f"  Esim: {ex_str}")
                ds_ref = dataset.get("name", dataset.get("id", ""))
                parts.append(
                    f'\nKysele dataa: `query_data(dataset_id="{ds_ref}", '
                    "filters={...})`"
                )
                return "\n".join(parts)
            except (json.JSONDecodeError, KeyError):
                pass

    # Hae metadata API:sta
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": user_agent()},
        ) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            meta = resp.json()
    except Exception as e:
        return f"PxWeb-metatietojen haku epäonnistui: {e}"

    title = meta.get("title", "")
    variables = meta.get("variables", [])
    if not variables:
        return "PxWeb-taululla ei ole muuttujia."

    parts = []
    if title:
        parts.append(f"**{title}**\n")
    parts.append("**Dimensiot:**\n")

    for var in variables:
        code = var.get("code", "")
        text = var.get("text", code)
        values = var.get("values", [])
        value_texts = var.get("valueTexts", [])
        examples = value_texts[:5] if value_texts else values[:5]
        ex_str = ", ".join(str(x) for x in examples)
        parts.append(f"- **{text}** (`{code}`): {len(values)} arvoa")
        if ex_str:
            parts.append(f"  Esim: {ex_str}")

    ds_name = dataset.get("name", dataset.get("id", ""))
    parts.append(
        f"\nKysele dataa: `query_pxweb(dataset_id=\"{ds_name}\", "
        "filters={...})`"
    )
    return "\n".join(parts)


def _wfs_params(
    url: str, max_rows: int, bbox: str | None = None
) -> tuple[str, dict[str, str]]:
    """Rakenna WFS GetFeature -pyyntö säilyttäen kerroksen nimi URL:sta.

    Resurssin URL on useimmiten GetCapabilities-osoite, jonka query-osa on
    turha — mutta osassa lähteitä se kantaa myös ``typeName``-parametrin.
    Jos se pudotetaan, palvelin vastaa "The query should specify either
    typeName..." eikä virheestä näe että kerros katosi kyselyä
    rakennettaessa. Siksi kerroksen nimi poimitaan talteen.
    """
    base_url = url.split("?")[0]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "outputFormat": "application/json",
        "count": str(max_rows),
    }
    query = urllib.parse.urlparse(url).query
    for key, values in urllib.parse.parse_qs(query).items():
        if key.lower() in ("typename", "typenames") and values:
            params[key] = values[0]
    if bbox:
        params["bbox"] = bbox
    return base_url, params


async def _preview_wfs(url: str, max_rows: int, bbox: str | None = None) -> str:
    """Esikatsele WFS-palvelu: hae muutama feature (valinnaisella bbox-rajauksella)."""
    base_url, params = _wfs_params(url, max_rows, bbox)
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": user_agent()},
        ) as client:
            resp = await client.get(base_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return f"WFS-esikatselu epäonnistui: {e}\n\nPalvelun URL: {url}"

    features = data.get("features", [])
    if not features:
        return f"WFS-palvelu ei palauttanut kohteita.\n\nURL: {url}"

    rows = [f.get("properties", {}) for f in features[:max_rows]]
    headers = list(rows[0].keys()) if rows else []
    table_rows = [[str(r.get(h, "")) for h in headers] for r in rows]
    total = data.get("totalFeatures", data.get("numberMatched", "?"))
    return (
        f"**WFS** — {total} kohdetta yhteensä\n\n"
        + _format_md_table(headers, table_rows)
    )


async def _preview_odata(url: str, max_rows: int) -> str:
    """Esikatsele OData-palvelu: hae muutama rivi."""
    sep = "&" if "?" in url else "?"
    query_url = f"{url}{sep}$top={max_rows}"
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": user_agent()},
        ) as client:
            resp = await client.get(query_url, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return f"OData-esikatselu epäonnistui: {e}\n\nURL: {url}"

    rows = data.get("value", [])
    if not rows:
        return f"OData-palvelu ei palauttanut rivejä.\n\nURL: {url}"

    headers = [k for k in rows[0].keys() if not k.startswith("@")]
    table_rows = [[str(r.get(h, "")) for h in headers] for r in rows[:max_rows]]
    return (
        f"**OData** — {len(rows)} riviä\n\n"
        + _format_md_table(headers, table_rows)
    )


async def preview_data(
    dataset_id: str,
    resource_index: int | None = None,
    format_hint: str = "",
    max_rows: int = 10,
    ctx: Any = None,
) -> str:
    """Backward-compat alias: delegoi query_data-työkaluun."""
    from aura.tools.data import query_data

    return await query_data(
        dataset_id=dataset_id,
        resource_index=resource_index,
        format_hint=format_hint,
        max_rows=max_rows,
        ctx=ctx,
    )
