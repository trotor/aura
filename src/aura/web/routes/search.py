"""Hakusivu ja HTMX-tulokset."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aura.database import search_datasets
from aura.web.app import get_db

router = APIRouter()


@router.get("/search")
async def search_page(
    request: Request,
    q: str = "",
    source: str = "",
    fmt: str = "",
    organization: str = "",
) -> object:
    """Hakusivu suodattimilla. URL-parametrit esitäyttävät lomakkeen."""
    conn = get_db(request)

    # Suodatinvaihtoehdot
    sources = conn.execute(
        "SELECT DISTINCT source FROM datasets ORDER BY source"
    ).fetchall()
    formats = conn.execute(
        "SELECT DISTINCT format FROM resources WHERE format != '' ORDER BY format"
    ).fetchall()
    organizations = conn.execute(
        """
        SELECT DISTINCT organization_title FROM datasets
        WHERE organization_title != ''
        ORDER BY organization_title
        """
    ).fetchall()

    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "search.html",
        {
            "sources": [r["source"] for r in sources],
            "formats": [r["format"] for r in formats],
            "organizations": [r["organization_title"] for r in organizations],
            "q": q,
            "source": source,
            "fmt": fmt,
            "organization": organization,
        },
    )


@router.get("/search/results", response_class=HTMLResponse)
async def search_results(
    request: Request,
    q: str = "",
    source: str = "",
    fmt: str = "",
    organization: str = "",
    page: int = 1,
) -> object:
    """HTMX-fragmentti: hakutulokset."""
    conn = get_db(request)
    limit = 20
    offset = (page - 1) * limit

    if not q and not source and not fmt and not organization:
        # Ei hakua → näytä uusimmat
        results = conn.execute(
            "SELECT * FROM datasets ORDER BY metadata_modified DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        results = [dict(r) for r in results]
        conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]  # for future pagination
    else:
        if q:
            results = search_datasets(
                conn, q, limit=limit, offset=offset,
                source=source, fmt=fmt, organization=organization,
            )
        else:
            # Pelkät suodattimet ilman hakusanoja
            conditions = ["1=1"]
            params: list[object] = []
            if source:
                conditions.append("d.source = ?")
                params.append(source)
            if fmt:
                conditions.append(
                    "d.id IN (SELECT dataset_id FROM resources WHERE format = ? COLLATE NOCASE)"
                )
                params.append(fmt)
            if organization:
                conditions.append("d.organization_title LIKE ?")
                params.append(f"%{organization}%")

            where = " AND ".join(conditions)
            total_row = conn.execute(
                f"SELECT COUNT(*) FROM datasets d WHERE {where}", params
            ).fetchone()
            _ = total_row[0] if total_row else 0  # count saatavilla tarvittaessa

            rows = conn.execute(
                f"""
                SELECT d.* FROM datasets d
                WHERE {where}
                ORDER BY metadata_modified DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
            results = [dict(r) for r in rows]

        # Laske kokonaismäärä hakutuloksille
        if q:
            pass  # total ei tarvita tässä vaiheessa

    has_next = len(results) == limit

    # Hae resurssit hakutulosten dataseteille (yksi kysely)
    dataset_ids = [r["id"] for r in results]
    resources_by_dataset: dict[str, list[dict[str, object]]] = {}
    if dataset_ids:
        placeholders = ",".join("?" * len(dataset_ids))
        res_rows = conn.execute(
            f"SELECT id, dataset_id, name, name_fi, format, url "
            f"FROM resources WHERE dataset_id IN ({placeholders})",
            dataset_ids,
        ).fetchall()
        for r in res_rows:
            rd = dict(r)
            ds_id = str(rd["dataset_id"])
            resources_by_dataset.setdefault(ds_id, []).append(rd)

    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "_search_results.html",
        {
            "results": results,
            "resources_by_dataset": resources_by_dataset,
            "q": q,
            "source": source,
            "fmt": fmt,
            "organization": organization,
            "page": page,
            "has_next": has_next,
        },
    )
