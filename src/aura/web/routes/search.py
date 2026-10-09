"""Hakusivu ja HTMX-tulokset."""

from __future__ import annotations

import sqlite3
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aura.database import search_datasets
from aura.keywords import get_index, is_noise, normalize
from aura.web.app import get_db

router = APIRouter()

#: Hakutulosten yläpuolella näytettävien avainsanojen määrä.
RESULT_KEYWORDS = 10


def results_query(q: str, source: str, fmt: str, organization: str, page: int) -> str:
    """Seuraavan tulossivun kysely URL-koodattuna (hakusana voi sisältää &-merkin)."""
    return urlencode(
        {"q": q, "source": source, "fmt": fmt, "organization": organization, "page": page}
    )


def resources_for(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> dict[str, list[dict[str, object]]]:
    """Aineistojen resurssit yhdellä kyselyllä korttien formaattimerkintöjä varten."""
    by_dataset: dict[str, list[dict[str, object]]] = {}
    if not dataset_ids:
        return by_dataset
    placeholders = ",".join("?" * len(dataset_ids))
    rows = conn.execute(
        f"SELECT id, dataset_id, name, name_fi, format, url "
        f"FROM resources WHERE dataset_id IN ({placeholders})",
        dataset_ids,
    ).fetchall()
    for row in rows:
        rd = dict(row)
        by_dataset.setdefault(str(rd["dataset_id"]), []).append(rd)
    return by_dataset


def result_keywords(conn: sqlite3.Connection, results: list[dict[str, object]]) -> list[str]:
    """Tuloksissa toistuvat avainsanat, joilla haun voi jatkaa avainsanaan."""
    import json
    from collections import Counter

    index = get_index(conn)
    counts: Counter[str] = Counter()
    for row in results:
        try:
            keywords = json.loads(str(row.get("keywords_fi") or "[]"))
        except json.JSONDecodeError:
            continue
        counts.update(
            {normalize(k) for k in keywords if isinstance(k, str) and not is_noise(k)}
        )
    labels = []
    for key, _ in counts.most_common():
        entry = index.get(key)
        if entry is not None:
            labels.append(entry.label)
        if len(labels) >= RESULT_KEYWORDS:
            break
    return labels


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

    resources_by_dataset = resources_for(conn, [r["id"] for r in results])

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
            "next_query": results_query(q, source, fmt, organization, page + 1),
            "result_keywords": result_keywords(conn, results) if page == 1 else [],
        },
    )
