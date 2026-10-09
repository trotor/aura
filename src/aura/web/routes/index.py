"""Etusivu kolmella kielellä ja koneluettava palvelukuvaus (``/llms.txt``)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from aura.database import get_stats
from aura.instance import describe_instance
from aura.keywords import get_index
from aura.web.app import get_db
from aura.web.i18n import (
    AUTHOR_EMAIL,
    AUTHOR_NAME,
    GITHUB_URL,
    LANGUAGES,
    PRO_URL,
    TEXTS,
    format_number,
    landing_path,
)

router = APIRouter()


def public_base_url(request: Request) -> str:
    """Palauta julkinen juuriosoite kauttaviivoineen.

    ``request.base_url`` kertoo skeeman jolla pyyntö saapui *sovellukseen*,
    ei sitä jolla käyttäjä saapui. Käänteisproxyn takana se on aina http,
    joten ländärin kopioitava MCP-konfiguraatio olisi väärä: asiakas
    yrittäisi http:tä ja päätyisi uudelleenohjaukseen.

    Luetaan siis ``X-Forwarded-Proto`` jos proxy sen asetti. Tämä ei nojaa
    uvicornin ``--forwarded-allow-ips``-asetukseen, joten se toimii myös
    silloin kun proxy näkyy kontista muuna kuin 127.0.0.1:nä.
    """
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    base = str(request.base_url)
    if forwarded in ("http", "https"):
        scheme, _, rest = base.partition("://")
        if scheme != forwarded:
            base = f"{forwarded}://{rest}"
    return base


def _catalog_numbers(conn: sqlite3.Connection) -> dict[str, int]:
    """Etusivun ja llms.txt:n luvut suoraan kannasta, ei käsin kirjoitettuina."""
    row = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT source), COUNT(DISTINCT organization_id) FROM datasets"
    ).fetchone()
    resources = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
    return {
        "datasets": row[0],
        "sources": row[1],
        "orgs": row[2],
        "resources": resources,
    }


def landing_html(t: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Tekstit joihin upotetaan linkki tai koodi, valmiiksi escapattuna.

    Käännös on tekstiä, mutta osaan siitä tulee HTML-elementti (osoite
    ``<code>``-tagissa, linkki). ``base_url`` tulee pyynnön Host-
    otsakkeesta eli käyttäjältä, joten sitä ei saa liittää HTML:ään
    merkkijonona. ``Markup.format`` escapaa argumentit ja ``escape``
    itse tekstin; mallipohja tulostaa tuloksen sellaisenaan.
    """
    pro_host = PRO_URL.removeprefix("https://")
    llms = Markup('<a href="/llms.txt"><code>/llms.txt</code></a>')
    github = Markup('<a href="{}">{}</a>').format(GITHUB_URL, GITHUB_URL.removeprefix("https://"))
    email = Markup('<a href="mailto:{0}">{0}</a>').format(AUTHOR_EMAIL)
    return {
        "connect_quality": escape(t["connect_quality"]).format(
            url=Markup("<code>{}</code>").format(base_url + "mcp/laatu")
        ),
        "ai_points": [escape(point).format(llms=llms) for point in t["ai_points"]],
        "pro_intro_elsewhere": escape(t["pro_intro_elsewhere"]).format(
            url=Markup('<a href="{}">{}</a>').format(PRO_URL, pro_host)
        ),
        "own_cta": escape(t["own_cta"]).format(github=github),
        "author_contact": escape(t["author_contact"]).format(email=email, github=github),
    }


def _render_landing(request: Request, lang: str) -> object:
    conn = get_db(request)
    stats = get_stats(conn)
    sources = conn.execute(
        """
        SELECT source, COUNT(*) as count, MAX(harvested_at) as last_harvest
        FROM datasets
        GROUP BY source
        ORDER BY count DESC
        """
    ).fetchall()
    numbers = _catalog_numbers(conn)
    base_url = public_base_url(request)

    templates: Jinja2Templates = router.templates  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stats": stats,
            "sources": [dict(s) for s in sources],
            "base_url": base_url,
            "instance": describe_instance(),
            "lang": lang,
            "t": TEXTS[lang],
            "html": landing_html(TEXTS[lang], base_url),
            "n": {k: format_number(v, lang) for k, v in numbers.items()},
            "alternates": [
                (code, TEXTS[code]["lang_name"], landing_path(code)) for code in LANGUAGES
            ],
            "self_path": landing_path(lang),
            "top_keywords": get_index(conn).top(24),
            "pro_url": PRO_URL,
        },
    )


@router.get("/")
async def index(request: Request) -> object:
    """Etusivu suomeksi."""
    return _render_landing(request, "fi")


@router.get("/en")
async def index_en(request: Request) -> object:
    """Etusivu englanniksi."""
    return _render_landing(request, "en")


@router.get("/sv")
async def index_sv(request: Request) -> object:
    """Etusivu ruotsiksi."""
    return _render_landing(request, "sv")


@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(request: Request) -> str:
    """Koneluettava kuvaus palvelusta kielimallille (llmstxt.org-muoto).

    Agentti joka löytää palvelun verkosta lukee tämän ennen kuin se arvaa
    etusivun HTML:stä mitä palvelu tekee. Siksi tässä ovat endpoint,
    työkalujen järjestys ja esimerkkikutsut, ei markkinointia.
    """
    conn = get_db(request)
    num = _catalog_numbers(conn)
    base = public_base_url(request)
    instance = describe_instance()
    lines = [
        "# Aura",
        "",
        "> Discovery service for Finland's open data. Aura indexes "
        f"{num['datasets']:,} datasets from {num['sources']} sources "
        f"({num['orgs']} publishers) and fetches rows straight from the "
        "publishers' APIs (PxWeb, WFS, OData, CSV, JSON, FMI stored queries). "
        "Answers include source URL and licence.",
        "",
        "Catalogue metadata is mostly in Finnish; queries in Finnish, Swedish "
        "and English work. Areas accept names (inflected Finnish/Swedish), "
        "municipality codes (837, KU837), region codes (MK06), postcodes "
        "(33100) and abolished municipalities (resolved to the successor).",
        "",
        "## MCP",
        "",
        f"- Endpoint (streamable HTTP, no auth, read-only): {base}mcp",
        f"- Publisher quality profile: {base}mcp/laatu",
        f"- Claude Code: `claude mcp add --transport http aura {base}mcp`",
        "",
        "## Tools (public profile)",
        "",
        "1. find_data(query, region, source, format, organization) – start here; "
        "returns datasets and, when known, ready-made indicators",
        "2. inspect_dataset(dataset_id) – description, fields, licence, quality, "
        "availability, query recipe",
        "3. query_source(dataset_id, filters, area) – rows from the source. "
        "PxWeb: call without filters first to get dimension codes; time accepts "
        '"uusin" (latest) or "2020-2024"',
        "- area_snapshot(region) – area hierarchy, codes and available data",
        "- find_related(dataset_id) – similar datasets",
        "",
        "Every response is structured (outputSchema). Follow `next_actions`; "
        "errors carry `error.hint` and `error.suggested_call`. Cite "
        "`provenance.source_url` and `license` to the user.",
    ]
    if instance.is_extended:
        lines += [
            "",
            "## This instance",
            "",
            "Also available here: get_facts(indicator|question, areas, period), "
            "time_series(indicator, area) and compare_areas(indicator, areas) "
            "for 200+ ready-made indicators, plus search inside table "
            "classifications and spatial column names.",
        ]
    lines += [
        "",
        "## Optional",
        "",
        f"- Author: {AUTHOR_NAME} ({AUTHOR_EMAIL}). Public service made possible by Futuai Oy.",
        f"- Source code (MIT): {GITHUB_URL}. The same harvester + catalogue + MCP "
        "structure can be pointed at an organisation's own data sources.",
        f"- Human-readable pages: {base} (fi), {base}en, {base}sv",
    ]
    return "\n".join(lines) + "\n"
