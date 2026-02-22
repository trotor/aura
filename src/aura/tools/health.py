"""Saatavuustyökalut: health_check, health_report."""

from __future__ import annotations

from fastmcp import Context

import aura.server as _server
from aura.constants import format_date
from aura.server import mcp


@mcp.tool()
async def health_check(
    source: str = "",
    limit: int = 50,
    stale_days: int = 7,
    ctx: Context | None = None,
) -> str:
    """Tarkista resurssien saatavuus (HTTP HEAD/GET).

    Args:
        source: Rajaa lähteeseen (esim. "avoindata.fi")
        limit: Tarkistettavien resurssien enimmäismäärä (oletus 50)
        stale_days: Tarkista uudelleen vain N päivää vanhat (oletus 7)
    """
    from aura.health import check_all_resources as _check_all

    conn = _server._get_conn(ctx)
    summary = await _check_all(
        conn, source=source, stale_days=stale_days, limit=limit,
    )

    if summary.total == 0:
        return "Ei tarkistettavia resursseja."

    parts = [
        "# Resurssien saatavuustarkistus\n",
        "| Mittari | Arvo |",
        "|---------|------|",
        f"| Tarkistettu | {summary.total} |",
        f"| Saatavilla | {summary.available} |",
        f"| Ei saatavilla | {summary.unavailable} |",
        f"| Saatavuus | {summary.availability_pct:.1f}% |",
    ]
    if summary.avg_response_ms > 0:
        parts.append(f"| Vasteaika ka. | {summary.avg_response_ms:.0f} ms |")

    broken = [r for r in summary.results if not r.is_available]
    if broken:
        parts.append(f"\n## Ei saatavilla ({len(broken)})\n")
        for r in broken[:20]:
            err = r.error_message or f"HTTP {r.status_code}"
            parts.append(f"- {err}: {r.url}")

    return "\n".join(parts)


@mcp.tool()
def health_report(source: str = "", ctx: Context | None = None) -> str:
    """Näytä resurssien saatavuusraportti aiempien tarkistusten perusteella.

    Args:
        source: Rajaa lähteeseen (esim. "avoindata.fi")
    """
    from aura.health import get_health_summary, get_unavailable_resources

    conn = _server._get_conn(ctx)
    summary = get_health_summary(conn, source=source)

    if summary.get("total", 0) == 0:
        return (
            "Ei saatavuustarkistuksia. "
            "Aja ensin: health_check(source=..., limit=100)"
        )

    total = summary["total"]
    avail = summary.get("available", 0) or 0
    unavail = summary.get("unavailable", 0) or 0
    avg_ms = summary.get("avg_response_ms", 0) or 0
    pct = 100.0 * avail / total if total > 0 else 0

    parts = [
        "# Saatavuusraportti\n",
        "| Mittari | Arvo |",
        "|---------|------|",
        f"| Tarkistettu resursseja | {total} |",
        f"| Saatavilla | {avail} ({pct:.1f}%) |",
        f"| Ei saatavilla | {unavail} |",
        f"| Vasteaika ka. | {avg_ms:.0f} ms |",
        f"| Vanhin tarkistus | {format_date(summary.get('oldest_check'), include_time=True)} |",
        f"| Uusin tarkistus | {format_date(summary.get('newest_check'), include_time=True)} |",
    ]

    broken = get_unavailable_resources(conn, source=source, limit=15)
    if broken:
        parts.append(f"\n## Ei saatavilla ({len(broken)} näytetään)\n")
        for r in broken:
            err = r.get("error_message") or f"HTTP {r.get('status_code', '?')}"
            title = r.get("dataset_title", "")[:50]
            parts.append(f"- **{title}**: {err}")
            parts.append(f"  {r.get('url', '')}")

    return "\n".join(parts)
