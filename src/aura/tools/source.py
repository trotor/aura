"""query_source — hae aineiston sisältö strukturoituna.

Korvaa ``query_data``n. Sama reititys protokollan mukaan, mutta vastaus on
rivejä eikä markdownia, ja jokaisella vastauksella on lähdetieto: kyselyn
täsmällinen URL (PxWebissä myös POST-runko), lisenssi ja hakuaika.

Kyselyn logiikka on ``aura.fetch``issä; tämä moduuli valitsee resurssin,
tulkitsee aluerajauksen ja muotoilee vastauksen.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from fastmcp import Context
from fastmcp.tools import ToolResult
from pydantic import Field

import aura.server as _server
from aura import fetch
from aura.areas import resolve_area
from aura.database import get_dataset, get_source
from aura.formats import resource_format
from aura.preview import _pick_resource
from aura.responses import (
    Envelope,
    Model,
    NextAction,
    Provenance,
    fail,
    now_iso,
    respond,
    schema_of,
)
from aura.server import mcp
from aura.tools.query import _find_pxweb_url
from aura.tools.spatial import _resolve_area
from aura.wfs import type_name_from_url

_POSTAL_CODE = re.compile(r"^\d{5}$")


class ResourceRef(Model):
    index: int | None = None
    name: str = ""
    format: str = ""
    url: str = ""
    layer: str | None = Field(default=None, description="WFS: kysytty kerros (typeName)")


class Dimension(Model):
    code: str
    text: str = ""
    values: int = 0
    time: bool = False
    area: bool = False
    optional: bool = False
    examples: list[dict[str, str]] = Field(default_factory=list)


class QuerySourceResult(Envelope):
    dataset_id: str = ""
    protocol: str = ""
    resource: ResourceRef | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    total: int | None = Field(default=None, description="Osumien kokonaismäärä jos lähde kertoi")
    truncated: bool = False
    dimensions: list[Dimension] | None = Field(
        default=None, description="PxWeb: taulun dimensiot koodeineen (suodattimien rakentamiseen)"
    )
    codes: dict[str, dict[str, str]] | None = Field(
        default=None, description="PxWeb: rivien nimet → koodit dimensioittain"
    )
    layers: list[str] | None = Field(
        default=None, description="WFS: palvelun kerrokset, jos kerrosta ei annettu"
    )
    provenance: Provenance | None = None


def _protocol(fmt: str, url: str, dataset: dict[str, Any], query_protocol: str) -> str:
    if fmt == "PXWEB" or (query_protocol == "pxweb" and _find_pxweb_url(dataset)):
        return "pxweb"
    if fmt == "WFS" and fetch.is_stored_query(url):
        return "fmi_stored_query"
    if fmt == "ODATA" or query_protocol == "odata":
        return "odata"
    if fmt == "WFS":
        return "wfs"
    if fmt == "CSV":
        return "csv"
    if fmt in ("JSON", "GEOJSON", "API"):
        return "json"
    return ""


def _example_call(dataset_id: str, table: fetch.Table) -> NextAction | None:
    if not table.dimensions:
        return None
    filters: dict[str, list[str]] = {}
    for d in table.dimensions:
        if d["time"]:
            filters[d["code"]] = ["uusin"]
        elif d["examples"] and not d["optional"]:
            filters[d["code"]] = [d["examples"][0]["text"]]
    return NextAction(
        tool="query_source",
        args={"dataset_id": dataset_id, "filters": filters},
        why="Esimerkkikysely: vaihda arvot. Aluedimensioon kelpaa kunnan nimi tai koodi.",
    )


def _layer_call(
    dataset_id: str, res_ref: ResourceRef, table: fetch.Table, layer: str
) -> NextAction | None:
    """Ehdota kerroksen valintaa, kun palvelu valitsi sen käyttäjän puolesta.

    Ulkoinen arvio 27.9.2026: kerroksettoman WFS-resurssin kysely palautti
    palvelun ensimmäisen kerroksen (Paavossa postinumerorajat, ei
    tunnuslukuja) eikä vastaus kertonut, että muita kerroksia on.
    """
    if layer or not table.layers or len(table.layers) < 2 or not table.layer:
        return None
    if type_name_from_url(res_ref.url):
        return None
    return NextAction(
        tool="query_source",
        args={"dataset_id": dataset_id, "resource_index": res_ref.index, "layer": table.layer},
        why="Kerros valittiin automaattisesti (ensimmäinen); vaihda layer, vaihtoehdot: layers",
    )


@mcp.tool(tags={"public"}, output_schema=schema_of(QuerySourceResult))
async def query_source(
    dataset_id: str,
    filters: dict[str, list[str]] | None = None,
    area: str = "",
    columns: list[str] | None = None,
    resource_index: int | None = None,
    format_hint: str = "",
    max_rows: int = fetch.DEFAULT_ROWS,
    layer: str = "",
    ctx: Context | None = None,
) -> ToolResult:
    """Hae aineiston sisältö riveinä: PxWeb, WFS, FMI, OData, CSV, JSON.

    Ilman suodattimia palauttaa esikatselun — PxWeb-taulusta dimensiot ja
    niiden koodit, joista suodattimet rakennetaan. Suodattimien kanssa
    palauttaa rivit, kokonaismäärän ja kyselyn täsmällisen URL:n.

    Args:
        dataset_id: Aineiston tunniste (id tai name).
        filters: ``{"kenttä": ["arvo", ...]}``. PxWebissä avain on dimension
            koodi tai nimi ja arvo koodi tai nimi ("Tampere", "837",
            "KU837"); aikadimensio ymmärtää "uusin" ja "2020-2024". FMI:n
            tallennetuissa kyselyissä avaimet ovat kyselyn parametreja
            (place, fmisid, parameters, starttime).
        area: Aluerajaus. PxWebissä rajaa aluedimension, WFS:ssä bbox:iin
            (kunta, karttalehti tai "minx,miny,maxx,maxy") tai postinumeroon
            ("00100"), jos kerroksessa on postinumerokenttä.
        columns: Palautettavat sarakkeet (CSV, OData).
        resource_index: Resurssin indeksi; oletus valitaan automaattisesti.
        format_hint: Suosi tätä formaattia, esim. "WFS" tai "CSV".
        max_rows: Rivien enimmäismäärä (oletus 50, katto 500).
        layer: WFS-kerros (typeName), jos palvelussa on useita.
    """
    max_rows = max(1, min(max_rows, fetch.MAX_ROWS))
    conn = _server._get_conn(ctx)
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        return fail(
            QuerySourceResult,
            "dataset_not_found",
            f"Aineistoa '{dataset_id}' ei löytynyt.",
            hint="Hae tunniste find_data-työkalulla.",
            suggested_call=NextAction(tool="find_data", args={"query": dataset_id}),
            dataset_id=dataset_id,
        )
    ds_id = dataset["id"]
    source_info = get_source(conn, dataset.get("source", "")) or {}
    resource = _pick_resource(dataset.get("resources", []), resource_index, format_hint)
    # Tyhjä formaatti päätellään URL:sta: jo kerätyssä kannassa SYKE:n
    # WFS-resurssit ovat formaatittomia kunnes lähde kerätään uudelleen.
    fmt = resource_format(resource) if resource else ""
    url = (resource or {}).get("url", "") or ""
    protocol = _protocol(fmt, url, dataset, source_info.get("query_protocol", ""))
    res_ref = ResourceRef(
        index=dataset.get("resources", []).index(resource) if resource else None,
        name=(resource or {}).get("name_fi") or (resource or {}).get("name", "") or "",
        format=fmt,
        url=url,
        layer=(layer or type_name_from_url(url)) if protocol == "wfs" else None,
    )
    if protocol == "pxweb":
        url = _find_pxweb_url(dataset) or url
        res_ref.url = url
        res_ref.format = "PXWEB"

    if not protocol:
        formats = sorted({(r.get("format") or "?").upper() for r in dataset.get("resources", [])})
        return fail(
            QuerySourceResult,
            "unsupported_format",
            f"Resurssin formaattia '{fmt or '?'}' ei voi kysellä.",
            hint=f"Aineiston formaatit: {', '.join(formats)}. Lataa URL:sta: {url}"
            if url
            else f"Aineiston formaatit: {', '.join(formats)}.",
            dataset_id=ds_id,
            resource=res_ref,
        )

    bbox = None
    area_note = ""
    postal_code = ""
    notes_pre: list[str] = []
    if layer and protocol != "wfs":
        notes_pre.append(f"layer koskee vain WFS-resursseja; ohitettiin ({protocol}).")
    if area and protocol == "wfs" and _POSTAL_CODE.match(area.strip()):
        # Postinumero rajataan attribuutilla, ei bbox:lla (ks. fetch_wfs).
        postal_code = area.strip()
        match = resolve_area(conn, postal_code, levels=("postinumero",))
        area_note = (
            f"postinumeroalue {postal_code} {match.area.name_fi}".rstrip()
            if match
            else f"postinumero {postal_code} (ei postinumerotaulussa; suodatettiin silti)"
        )
    elif area and protocol in ("wfs", "fmi_stored_query"):
        bbox, area_note = _resolve_area(conn, area)
        if bbox is None:
            return fail(QuerySourceResult, "unknown_area", area_note, dataset_id=ds_id)
    elif area and protocol == "json" and "sotkanet.fi" in url:
        # Sotkanet palauttaa kaikki alueet; rivit on jo nimetty Tilastokeskuksen
        # tunnuksilla (region_code/region_level, ks. fetch._annotate_sotkanet),
        # joten alue rajataan niillä. Ilman tätä "Oulu" → area_not_supported
        # (telemetria 28.9.2026).
        match = resolve_area(conn, area)
        if match is None:
            return fail(
                QuerySourceResult,
                "unknown_area",
                f"Aluetta '{area}' ei tunnistettu.",
                hint="Anna kunnan, maakunnan tai hyvinvointialueen nimi tai koodi.",
                dataset_id=ds_id,
                resource=res_ref,
            )
        filters = {
            **(filters or {}),
            "region_code": [match.area.code],
            "region_level": [match.area.level],
        }
        area_note = f"{match.area.level} {match.area.name_fi} ({match.area.code})"
        if match.note:
            notes_pre.append(match.note)
    elif area and protocol not in ("pxweb",):
        return fail(
            QuerySourceResult,
            "area_not_supported",
            f"Aluerajaus ei toimi {protocol.upper()}-resurssilla.",
            hint="Suodata filters-parametrilla alueen sarakkeella.",
            dataset_id=ds_id,
            resource=res_ref,
        )

    try:
        if protocol == "pxweb":
            table = await fetch.fetch_pxweb(url, filters, max_rows, conn, area=area)
        elif protocol == "fmi_stored_query":
            table = await fetch.fetch_fmi(url, filters, max_rows, bbox)
        elif protocol == "wfs":
            table = await fetch.fetch_wfs(
                url, filters, max_rows, bbox, layer=layer, postal_code=postal_code
            )
        elif protocol == "odata":
            table = await fetch.fetch_odata(url, filters, columns, max_rows)
        elif protocol == "csv":
            table = await fetch.fetch_csv(url, filters, columns, max_rows)
        else:
            table = await fetch.fetch_json(url, filters, max_rows, conn)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        return fail(
            QuerySourceResult,
            "rate_limited" if code == 429 else "http_error",
            f"Lähde vastasi HTTP {code}.",
            dataset_id=ds_id,
            resource=res_ref,
            protocol=protocol,
        )
    except httpx.TimeoutException:
        return fail(
            QuerySourceResult,
            "timeout",
            "Lähde ei vastannut ajoissa.",
            dataset_id=ds_id,
            resource=res_ref,
            protocol=protocol,
        )
    except httpx.HTTPError as exc:
        return fail(
            QuerySourceResult,
            "connection_error",
            f"Yhteysvirhe: {exc}",
            dataset_id=ds_id,
            resource=res_ref,
            protocol=protocol,
        )

    provenance = Provenance(
        source=dataset.get("organization_title", "") or dataset.get("source", ""),
        source_url=table.request_url or url,
        license=dataset.get("license_title") or None,
        retrieved_at=now_iso(),
        dataset_id=ds_id,
        query=table.request_body,
    )
    notes = notes_pre + list(table.notes)
    if area_note:
        notes.insert(0, f"Aluerajaus: {area_note}")
    if protocol == "wfs" and table.layer:
        res_ref.layer = table.layer
    dims = [Dimension(**d) for d in table.dimensions] if table.dimensions is not None else None

    layer_call = _layer_call(ds_id, res_ref, table, layer)
    if table.error:
        example = _example_call(ds_id, table)
        hint = "Korjaa suodattimet dimensions-kentän koodeilla." if dims else None
        if table.layers and table.error_code == "area_not_supported":
            hint = "Kerrokset: " + ", ".join(table.layers[:10])
        return fail(
            QuerySourceResult,
            table.error_code or "query_failed",
            table.error,
            hint=hint,
            suggested_call=example,
            dataset_id=ds_id,
            resource=res_ref,
            protocol=protocol,
            dimensions=dims,
            layers=table.layers,
            notes=notes,
            provenance=provenance,
        )

    next_actions: list[NextAction] = []
    if layer_call:
        next_actions.append(layer_call)
    if dims is not None and not table.rows:
        example = _example_call(ds_id, table)
        if example:
            next_actions.append(example)

    payload = QuerySourceResult(
        dataset_id=ds_id,
        protocol=protocol,
        resource=res_ref,
        columns=table.columns,
        rows=table.rows,
        row_count=len(table.rows),
        total=table.total,
        truncated=table.truncated,
        dimensions=dims,
        codes=table.codes,
        layers=table.layers if layer_call else None,
        provenance=provenance,
        notes=notes,
        next_actions=next_actions,
    )
    if table.rows:
        summary = [
            f"{len(table.rows)} riviä ({protocol}) aineistosta {ds_id}"
            + (f", yhteensä {table.total}" if table.total is not None else "")
            + "."
        ]
        first = table.rows[0]
        summary.append("Ensimmäinen: " + ", ".join(f"{k}={v}" for k, v in list(first.items())[:6]))
    elif dims is not None:
        summary = [f"{len(dims)} dimensiota: " + ", ".join(f"{d.code} ({d.text})" for d in dims)]
    else:
        summary = ["Kysely ei palauttanut rivejä."]
    summary.append(f"Lähde: {provenance.source} — {provenance.license or 'lisenssi ei tiedossa'}")
    return respond(payload, summary)
