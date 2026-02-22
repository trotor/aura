"""Datasetti-detaljisivu."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aura.database import get_dataset, get_latest_enrichments
from aura.web.app import get_db

router = APIRouter()


@router.get("/dataset/{dataset_id:path}")
async def dataset_detail(request: Request, dataset_id: str) -> object:
    """Datasetti-sivu resursseineen ja rikastuksineen."""
    conn = get_db(request)
    dataset = get_dataset(conn, dataset_id)

    if dataset is None:
        return HTMLResponse("<h1>Datasettiä ei löytynyt</h1>", status_code=404)

    enrichments = get_latest_enrichments(conn, dataset_id)

    # Ryhmitä enrichmentit kenttien mukaan
    enrichment_map: dict[str, str] = {}
    for e in enrichments:
        enrichment_map[e["field"]] = e["value"]

    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "dataset.html",
        {
            "dataset": dataset,
            "enrichments": enrichment_map,
            "resources": dataset.get("resources", []),
        },
    )
