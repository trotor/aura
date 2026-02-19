"""Generoi datasettikatalogi Markdown-muodossa."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from aura.size_estimator import format_size


def main():
    db_path = Path(__file__).parent.parent / "data" / "aura.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Kokonaistilastot
    total_datasets = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
    total_resources = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
    total_orgs = conn.execute(
        "SELECT COUNT(DISTINCT organization_name) FROM datasets"
    ).fetchone()[0]
    total_size = conn.execute(
        "SELECT SUM(estimated_size_bytes) FROM datasets"
    ).fetchone()[0] or 0

    # Lähteet
    sources = conn.execute(
        "SELECT source, COUNT(*) as count, SUM(estimated_size_bytes) as size "
        "FROM datasets GROUP BY source ORDER BY count DESC"
    ).fetchall()

    print("# Aura — Datasettikatalogi")
    print()
    print(f"> **{total_datasets:,}** datasettiä | **{total_resources:,}** resurssia | "
          f"**{total_orgs}** organisaatiota | **{format_size(total_size)}** arvioitua dataa")
    print(f">")
    print(f"> Päivitetty: 2026-02-19")
    print()

    # Yhteenveto lähteittäin
    print("## Lähteet")
    print()
    print("| Lähde | Datasettejä | Arvioitu koko |")
    print("|-------|-------------|---------------|")
    for s in sources:
        print(f"| [{s['source']}](#{s['source'].replace('.', '').replace(' ', '-')}) "
              f"| {s['count']:,} | {format_size(s['size'] or 0)} |")
    print(f"| **Yhteensä** | **{total_datasets:,}** | **{format_size(total_size)}** |")
    print()

    # Yksityiskohtaiset listat per lähde
    for s in sources:
        source = s["source"]
        print(f"---\n")
        print(f"## {source}")
        print()

        # Organisaatiot tässä lähteessä
        orgs = conn.execute(
            "SELECT organization_title, COUNT(*) as count, "
            "SUM(estimated_size_bytes) as size "
            "FROM datasets WHERE source = ? AND organization_title != '' "
            "GROUP BY organization_title ORDER BY count DESC",
            (source,),
        ).fetchall()

        if len(orgs) > 1:
            print(f"### Organisaatiot ({len(orgs)})\n")
            print("| Organisaatio | Datasettejä | Arvioitu koko |")
            print("|-------------|-------------|---------------|")
            for o in orgs[:30]:
                print(f"| {o['organization_title']} | {o['count']} | {format_size(o['size'] or 0)} |")
            if len(orgs) > 30:
                print(f"| *...ja {len(orgs) - 30} muuta* | | |")
            print()

        # Datasetit
        datasets = conn.execute(
            "SELECT name, title, title_fi, organization_title, "
            "license_title, estimated_size_bytes, num_resources, "
            "metadata_modified, keywords_fi "
            "FROM datasets WHERE source = ? "
            "ORDER BY organization_title, title_fi, title",
            (source,),
        ).fetchall()

        print(f"### Datasetit ({len(datasets)})\n")
        print("<details>")
        print(f"<summary>Näytä kaikki {len(datasets)} datasettiä</summary>\n")
        print("| Datasetti | Organisaatio | Koko | Resursseja |")
        print("|----------|-------------|------|-----------|")
        for d in datasets:
            title = d["title_fi"] or d["title"] or d["name"]
            if len(title) > 70:
                title = title[:67] + "..."
            org = d["organization_title"] or "–"
            if len(org) > 35:
                org = org[:32] + "..."
            size = format_size(d["estimated_size_bytes"] or 0)
            print(f"| {title} | {org} | {size} | {d['num_resources']} |")
        print("\n</details>\n")


if __name__ == "__main__":
    main()
