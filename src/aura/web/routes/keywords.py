"""Avainsanaselain: hakemisto ja avainsanakohtaiset sivut."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from aura.keywords import KeywordEntry, get_index, normalize
from aura.web.app import get_db
from aura.web.routes.search import resources_for

router = APIRouter()

PAGE_SIZE = 20


def _letter(entry: KeywordEntry) -> str:
    first = entry.key[:1].upper()
    return first if first.isalpha() else "#"


@router.get("/avainsanat")
async def keywords_index(request: Request) -> object:
    """Kaikki avainsanat aakkosittain ja yleisimmät erikseen."""
    index = get_index(get_db(request))
    groups: dict[str, list[KeywordEntry]] = {}
    for entry in index.entries():
        groups.setdefault(_letter(entry), []).append(entry)
    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "keywords.html",
        {"top": index.top(40), "groups": groups, "total": len(index.entries())},
    )


@router.get("/avainsana/{keyword:path}")
async def keyword_page(request: Request, keyword: str, page: int = 1) -> object:
    """Avainsanan aineistot, liittyvät ja samankaltaiset avainsanat."""
    conn = get_db(request)
    index = get_index(conn)
    entry = index.get(keyword)
    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    if entry is None:
        # Ehdotukset: avainsanat joissa haettu sana on osana.
        needle = normalize(keyword)
        suggestions = [e for e in index.top(5000) if needle and needle in e.key][:20]
        return templates.TemplateResponse(
            request,
            "keyword.html",
            {"keyword": keyword, "entry": None, "suggestions": suggestions},
            status_code=404,
        )

    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    ids = entry.dataset_ids
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT * FROM datasets WHERE id IN ({placeholders}) "
        "ORDER BY metadata_modified DESC, id LIMIT ? OFFSET ?",
        [*ids, PAGE_SIZE, offset],
    ).fetchall()
    results = [dict(r) for r in rows]
    return templates.TemplateResponse(
        request,
        "keyword.html",
        {
            "keyword": keyword,
            "entry": entry,
            "results": results,
            "resources_by_dataset": resources_for(conn, [r["id"] for r in results]),
            "related": index.related(entry.key),
            "similar": index.similar(entry.key),
            "page": page,
            "has_next": offset + PAGE_SIZE < entry.count,
        },
    )
