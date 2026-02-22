"""Resurssin katselusivu."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from aura.web.app import get_db

router = APIRouter()

# Formaattien ryhmittely katselutyypin mukaan
MAP_FORMATS = {"WMS", "WFS", "GEOJSON"}
TABLE_FORMATS = {"CSV", "JSON", "API"}
PXWEB_FORMATS = {"PXWEB", "PX"}


@router.get("/view/{resource_id}")
async def view_resource(request: Request, resource_id: str) -> object:
    """Kokoruudun katselusivu resurssille."""
    conn = get_db(request)

    row = conn.execute(
        "SELECT r.*, d.title_fi, d.title, d.name as dataset_name, d.id as dataset_id "
        "FROM resources r JOIN datasets d ON r.dataset_id = d.id "
        "WHERE r.id = ?",
        (resource_id,),
    ).fetchone()

    if row is None:
        return HTMLResponse("<h1>Resurssia ei löytynyt</h1>", status_code=404)

    resource = dict(row)
    fmt = (resource.get("format", "") or "").upper()
    url = resource.get("url", "")
    dataset_title = resource["title_fi"] or resource["title"] or resource["dataset_name"]
    resource_name = resource.get("name_fi") or resource.get("name") or url[:60]

    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]

    ctx = {
        "resource": resource,
        "resource_name": resource_name,
        "dataset_title": dataset_title,
        "dataset_id": resource["dataset_id"],
        "url": url,
        "fmt": fmt,
    }

    if fmt in MAP_FORMATS:
        ctx["viewer_type"] = fmt.lower()
        return templates.TemplateResponse(request, "view_map.html", ctx)

    if fmt in TABLE_FORMATS:
        return templates.TemplateResponse(request, "view_table.html", ctx)

    if fmt in PXWEB_FORMATS:
        return templates.TemplateResponse(request, "view_pxweb.html", ctx)

    # WCS ja muut OGC → näytä karttatemplate info-tilassa
    if fmt in ("WCS", "OGC API", "WMTS"):
        ctx["viewer_type"] = "info"
        return templates.TemplateResponse(request, "view_map.html", ctx)

    # Tuntematon formaatti → redirect takaisin datasettisivulle
    return RedirectResponse(f"/dataset/{resource['dataset_id']}", status_code=302)
