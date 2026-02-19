"""Hae tilastot tietokannasta SOURCES.md:tä varten."""

import sqlite3

conn = sqlite3.connect("data/aura.db")
conn.row_factory = sqlite3.Row

orgs = conn.execute(
    "SELECT organization_title, COUNT(*) as count "
    "FROM datasets WHERE organization_title != '' "
    "GROUP BY organization_title ORDER BY count DESC LIMIT 20"
).fetchall()

print("TOP ORGS:")
for o in orgs:
    print(f"| {o['organization_title']} | {o['count']} |")

print("\nFORMAT BREAKDOWN:")
fmts = conn.execute(
    "SELECT format, COUNT(*) as count "
    "FROM resources WHERE format != '' "
    "GROUP BY format ORDER BY count DESC LIMIT 20"
).fetchall()
for f in fmts:
    print(f"| {f['format']} | {f['count']} |")

api_count = conn.execute(
    "SELECT COUNT(*) FROM resources WHERE format IN ('WMS','WFS','API','PXWEB','OGC','WMTS')"
).fetchone()[0]
total_res = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
print(f"\nAPI/rajapinta resursseja: {api_count}/{total_res}")
print(f"Aineistopaketti resursseja: {total_res - api_count}/{total_res}")
