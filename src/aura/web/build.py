"""Staattisen GitHub Pages -sivun generointi."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from aura.constants import format_date
from aura.database import get_connection, get_organizations, get_stats, init_db

BUILD_TEMPLATES_DIR = Path(__file__).parent / "build_templates"


def build_static_site(output_dir: str = "docs/site") -> None:
    """Generoi staattinen sivu tietokannasta."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    init_db(conn)

    stats = get_stats(conn)
    organizations = get_organizations(conn, limit=20)

    # Lähdekohtaiset tiedot
    sources = conn.execute(
        """
        SELECT source, COUNT(*) as count, MAX(harvested_at) as last_harvest
        FROM datasets
        GROUP BY source
        ORDER BY count DESC
        """
    ).fetchall()

    # Kevyt dataset-indeksi client-side hakua varten
    datasets = conn.execute(
        """
        SELECT id, name, title_fi, title, organization_title, source,
               keywords_fi, notes_fi, num_resources
        FROM datasets
        ORDER BY metadata_modified DESC
        """
    ).fetchall()

    data_json = [
        {
            "id": d["id"],
            "t": d["title_fi"] or d["title"] or d["name"],
            "o": d["organization_title"] or "",
            "s": d["source"],
            "k": d["keywords_fi"] or "[]",
            "n": (d["notes_fi"] or "")[:150],
            "r": d["num_resources"],
        }
        for d in datasets
    ]

    # Kirjoita data.json
    data_json_path = out / "data.json"
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump(data_json, f, ensure_ascii=False)

    # Renderöi HTML
    env = Environment(loader=FileSystemLoader(str(BUILD_TEMPLATES_DIR)))
    env.filters["format_date"] = lambda v: format_date(v)

    template = env.get_template("overview.html")
    html = template.render(
        stats=stats,
        organizations=organizations,
        sources=[dict(s) for s in sources],
        total_datasets=len(data_json),
    )

    index_path = out / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    conn.close()

    print(f"Staattinen sivu generoitu: {out}")
    print(f"  index.html: {index_path.stat().st_size / 1024:.1f} KB")
    print(f"  data.json:  {data_json_path.stat().st_size / 1024:.1f} KB")
