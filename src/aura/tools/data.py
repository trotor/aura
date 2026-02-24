"""Yhtenäinen datakyselytyökalu: esikatsele ja kyselöi datasettejä."""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

import httpx
from fastmcp import Context

import aura.server as _server
from aura.constants import user_agent
from aura.database import get_dataset, get_latest_enrichments, get_source
from aura.server import mcp
from aura.tools.preview import (
    _format_md_table,
    _pick_resource,
    _preview_csv,
    _preview_json,
    _preview_odata,
    _preview_pxweb,
    _preview_wfs,
)
from aura.tools.query import (
    _find_pxweb_url,
    _parse_json_stat2,
    _resolve_values,
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 30.0
_MAX_DOWNLOAD_BYTES = 1_048_576  # 1 MB
_MAX_RESULT_ROWS = 500
_STREAM_CHUNK_LIMIT = 8192


@mcp.tool()
async def query_data(
    dataset_id: str,
    filters: dict[str, list[str]] | None = None,
    columns: list[str] | None = None,
    resource_index: int | None = None,
    format_hint: str = "",
    max_rows: int = 20,
    ctx: Context | None = None,
) -> str:
    """Hae tai esikatsele datasetin sisältöä.

    Ilman filttereitä: esikatselu (ensimmäiset rivit / dimensiot).
    Filttereiden kanssa: suodatettu kysely.

    Args:
        dataset_id: Datasetin ID tai nimi
        filters: Suodattimet dict-muodossa, esim. {"Alue": ["Tampere"]}
        columns: Näytettävät sarakkeet (valinnainen)
        resource_index: Resurssin indeksi (oletus: valitaan automaattisesti)
        format_hint: Haluttu formaatti (esim. "CSV", "JSON")
        max_rows: Tulosrivien enimmäismäärä (oletus 20, max 500)
    """
    max_rows = min(max_rows, _MAX_RESULT_ROWS)
    conn = _server._get_conn(ctx)
    dataset = get_dataset(conn, dataset_id)

    if dataset is None:
        return f"Datasettiä '{dataset_id}' ei löytynyt."

    resources = dataset.get("resources", [])
    source_name = dataset.get("source", "")
    fmt = ""

    # Yritä selvittää formaatti/protokolla sources-taulusta
    source_info = get_source(conn, source_name)
    query_protocol = (source_info or {}).get("query_protocol", "")

    # Valitse resurssi
    resource = _pick_resource(resources, resource_index, format_hint)
    if resource is not None:
        fmt = (resource.get("format") or "").upper()

    # Reititys formaatin ja protokollan mukaan
    try:
        # PxWeb-käsittely (tarkistetaan resurssi tai protokolla)
        if fmt == "PXWEB" or (query_protocol == "pxweb" and _find_pxweb_url(dataset)):
            return await _handle_pxweb(dataset, filters, columns, max_rows, conn)

        if resource is None:
            return "Datasetillä ei ole resursseja."

        url = resource.get("url", "")
        res_name = resource.get("name_fi") or resource.get("name", "")

        if not url:
            return f"Resurssilla '{res_name}' ei ole URL:ia."

        header = f"### {res_name}\n**Formaatti:** {fmt} | **URL:** {url}\n\n"

        # OData (tarkista ennen JSON/API koska query_protocol voi ohjata)
        if fmt == "ODATA" or query_protocol == "odata":
            if filters:
                body = await _query_odata(url, filters, columns, max_rows)
            else:
                body = await _preview_odata(url, max_rows)

        # CSV
        elif fmt == "CSV":
            if filters:
                body = await _query_csv(url, filters, columns, max_rows)
            else:
                body = await _preview_csv(url, max_rows)

        # JSON / GeoJSON / API
        elif fmt in ("JSON", "API", "GEOJSON"):
            if filters:
                body = await _query_json(url, filters, max_rows)
            else:
                body = await _preview_json(url, max_rows)

        # WFS
        elif fmt == "WFS":
            if filters:
                body = await _query_wfs(url, filters, max_rows)
            else:
                body = await _preview_wfs(url, max_rows)

        # WMS/WCS/HTML — vain linkki
        elif fmt in ("WMS", "WCS"):
            body = (
                f"{fmt}-palvelu ei tue suoraa esikatselua.\n\n"
                f"Avaa selaimessa: {url}"
            )
        elif fmt == "HTML":
            body = f"Verkkosivu: {url}"

        else:
            body = f"Formaatin '{fmt}' esikatselu ei ole tuettu.\n\nLataa: {url}"

    except httpx.HTTPStatusError as e:
        body = f"Palvelin palautti virheen {e.response.status_code}."
    except httpx.TimeoutException:
        body = "Aikakatkaisu: palvelin ei vastannut ajoissa."
    except httpx.ConnectError:
        body = "Yhteysvirhe: palvelimeen ei saatu yhteyttä."
    except Exception as e:
        logger.warning("query_data virhe: %s", e, exc_info=True)
        body = f"Kysely epäonnistui: {e}"

    return header + body


# --- PxWeb ---


async def _handle_pxweb(
    dataset: dict[str, Any],
    filters: dict[str, list[str]] | None,
    columns: list[str] | None,
    max_rows: int,
    conn: Any,
) -> str:
    """Käsittele PxWeb-datasetti: dimensiot tai datakysely."""
    api_url = _find_pxweb_url(dataset)
    if not api_url:
        return "Datasetille ei löytynyt PxWeb API -URL:ia."

    # Ilman filttereitä: näytä dimensiot
    if not filters:
        enrichments = get_latest_enrichments(conn, dataset["id"])
        res_name = ""
        for r in dataset.get("resources", []):
            if (r.get("format") or "").upper() == "PXWEB":
                res_name = r.get("name_fi") or r.get("name", "")
                break
        header = f"### {res_name}\n**Formaatti:** PXWEB | **URL:** {api_url}\n\n"
        body = await _preview_pxweb(api_url, dataset, enrichments)
        return header + body

    # Hae metadata
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": user_agent()},
        ) as client:
            resp = await client.get(api_url, follow_redirects=True)
            resp.raise_for_status()
            meta = resp.json()
    except Exception as e:
        return f"PxWeb-metatietojen haku epäonnistui: {e}"

    variables = meta.get("variables", [])
    if not variables:
        return "Taululla ei ole dimensioita."

    # Rakenna POST-kysely
    var_map: dict[str, dict[str, Any]] = {
        v.get("code", ""): v for v in variables
    }

    query_items: list[dict[str, Any]] = []
    unresolved: list[str] = []

    for code, user_vals in filters.items():
        if code not in var_map:
            matched = [
                v for v in variables
                if v.get("text", "").lower() == code.lower()
            ]
            if matched:
                code = matched[0].get("code", code)
            else:
                unresolved.append(code)
                continue

        resolved = _resolve_values(var_map[code], user_vals)
        query_items.append({
            "code": code,
            "selection": {"filter": "item", "values": resolved},
        })

    if unresolved:
        available = [f"`{v.get('code')}` ({v.get('text', '')})" for v in variables]
        return (
            f"Tuntemattomia dimensioita: {', '.join(unresolved)}\n\n"
            f"Käytettävissä: {', '.join(available)}"
        )

    # Lisää suodattamattomat dimensiot
    filtered_codes = {item["code"] for item in query_items}
    for var in variables:
        code = var.get("code", "")
        if code not in filtered_codes:
            all_values = var.get("values", [])
            if len(all_values) > 50:
                query_items.append({
                    "code": code,
                    "selection": {"filter": "item", "values": all_values[-5:]},
                })
            else:
                query_items.append({
                    "code": code,
                    "selection": {"filter": "item", "values": all_values},
                })

    post_body = {
        "query": query_items,
        "response": {"format": "json-stat2"},
    }

    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": user_agent()},
        ) as client:
            resp = await client.post(
                api_url,
                json=post_body,
                follow_redirects=True,
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        detail = ""
        try:
            detail = e.response.text[:500]
        except Exception:
            pass
        return f"PxWeb-kysely epäonnistui (HTTP {status}).\n{detail}"
    except Exception as e:
        return f"PxWeb-kysely epäonnistui: {e}"

    return _parse_json_stat2(result, max_rows)


# --- OData ---


async def _query_odata(
    url: str,
    filters: dict[str, list[str]],
    columns: list[str] | None,
    max_rows: int,
) -> str:
    """Kyselöi OData-palvelua $filter-parametrilla."""
    filter_parts = []
    for field, values in filters.items():
        if len(values) == 1:
            filter_parts.append(f"{field} eq '{values[0]}'")
        else:
            or_parts = [f"{field} eq '{v}'" for v in values]
            filter_parts.append(f"({' or '.join(or_parts)})")

    params: dict[str, str] = {
        "$top": str(max_rows),
        "$filter": " and ".join(filter_parts),
    }
    if columns:
        params["$select"] = ",".join(columns)

    sep = "&" if "?" in url else "?"
    query_url = url + sep + "&".join(f"{k}={v}" for k, v in params.items())

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": user_agent()},
    ) as client:
        resp = await client.get(query_url, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

    rows = data.get("value", [])
    if not rows:
        return "OData-kysely ei palauttanut tuloksia."

    headers = [k for k in rows[0].keys() if not k.startswith("@")]
    if columns:
        headers = [h for h in headers if h in columns]
    table_rows = [[str(r.get(h, "")) for h in headers] for r in rows[:max_rows]]
    return (
        f"**OData** — {len(rows)} riviä\n\n"
        + _format_md_table(headers, table_rows)
    )


# --- WFS ---


async def _query_wfs(
    url: str,
    filters: dict[str, list[str]],
    max_rows: int,
) -> str:
    """Kyselöi WFS-palvelua CQL_FILTER-parametrilla."""
    cql_parts = []
    for field, values in filters.items():
        if len(values) == 1:
            cql_parts.append(f"{field}='{values[0]}'")
        else:
            or_parts = [f"{field}='{v}'" for v in values]
            cql_parts.append(f"({' OR '.join(or_parts)})")

    base_url = url.split("?")[0]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "outputFormat": "application/json",
        "count": str(max_rows),
        "CQL_FILTER": " AND ".join(cql_parts),
    }

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": user_agent()},
    ) as client:
        resp = await client.get(base_url, params=params, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return "WFS-kysely ei palauttanut kohteita."

    rows = [f.get("properties", {}) for f in features[:max_rows]]
    headers = list(rows[0].keys()) if rows else []
    table_rows = [[str(r.get(h, "")) for h in headers] for r in rows]
    total = data.get("totalFeatures", data.get("numberMatched", "?"))
    return (
        f"**WFS** — {total} kohdetta yhteensä (suodatettu)\n\n"
        + _format_md_table(headers, table_rows)
    )


# --- CSV ---


async def _query_csv(
    url: str,
    filters: dict[str, list[str]],
    columns: list[str] | None,
    max_rows: int,
) -> str:
    """Lataa CSV ja suodata client-side."""
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": user_agent()},
    ) as client:
        async with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            content = b""
            async for chunk in resp.aiter_bytes():
                content += chunk
                if len(content) > _MAX_DOWNLOAD_BYTES:
                    break

    text = content.decode("utf-8", errors="replace")

    # Tunnista erotin
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if reader.fieldnames is None:
        return "CSV-tiedosto on tyhjä."

    headers = list(reader.fieldnames)
    if columns:
        headers = [h for h in headers if h in columns]

    # Suodata rivit
    matched_rows: list[list[str]] = []
    for row in reader:
        match = True
        for field, values in filters.items():
            cell = (row.get(field) or "").strip()
            if not any(v.lower() in cell.lower() for v in values):
                match = False
                break
        if match:
            matched_rows.append([str(row.get(h, "")) for h in headers])
            if len(matched_rows) >= max_rows:
                break

    if not matched_rows:
        return "CSV-suodatus ei tuottanut tuloksia."

    return (
        f"**CSV** — {len(matched_rows)} riviä (suodatettu)\n\n"
        + _format_md_table(headers, matched_rows)
    )


# --- JSON ---


async def _query_json(
    url: str,
    filters: dict[str, list[str]],
    max_rows: int,
) -> str:
    """Lataa JSON ja suodata client-side."""
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": user_agent()},
    ) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text[:_MAX_DOWNLOAD_BYTES]

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return "Vastaus ei ole kelvollista JSON:ia."

    # GeoJSON FeatureCollection
    items: list[dict[str, Any]] = []
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        items = [f.get("properties", {}) for f in data.get("features", [])]
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        items = data
    else:
        return "JSON-rakenne ei ole suodatettavissa (ei lista eikä FeatureCollection)."

    # Suodata
    matched: list[dict[str, Any]] = []
    for item in items:
        match = True
        for field, values in filters.items():
            cell = str(item.get(field, ""))
            if not any(v.lower() in cell.lower() for v in values):
                match = False
                break
        if match:
            matched.append(item)
            if len(matched) >= max_rows:
                break

    if not matched:
        return "JSON-suodatus ei tuottanut tuloksia."

    headers = list(matched[0].keys())
    table_rows = [[str(r.get(h, "")) for h in headers] for r in matched]
    return (
        f"**JSON** — {len(matched)} kohdetta (suodatettu)\n\n"
        + _format_md_table(headers, table_rows)
    )
