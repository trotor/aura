"""Karttasivu."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()


@router.get("/map")
async def map_page(request: Request) -> object:
    """Karttasivu Leaflet-visualisoinneilla."""
    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(request, "map.html", {})
