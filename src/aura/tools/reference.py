"""Viitedatatyökalut: reference_status, populate_reference, lookup_municipality."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.server import mcp


@mcp.tool()
def reference_status(ctx: Context | None = None) -> str:
    """Näytä viiteaineistojen tila: ladattu/puuttuu/vanhentunut.

    Kertoo mitkä viiteaineistot (kunnat, postinumerot) on populoitu
    ja milloin ne on viimeksi päivitetty.
    """
    conn = _server._get_conn(ctx)

    rows = conn.execute(
        "SELECT name, record_count, version, populated_at FROM ref_metadata ORDER BY name"
    ).fetchall()

    from aura.populators import POPULATORS

    lines = ["**Viiteaineistojen tila:**\n"]
    populated_names = {r["name"] for r in rows} if rows else set()

    for name, cls in sorted(POPULATORS.items()):
        if name in populated_names:
            row = next(r for r in rows if r["name"] == name)
            lines.append(
                f"- **{cls.description}** (`{name}`): "
                f"{row['record_count']} tietuetta, "
                f"päivitetty {row['populated_at'][:10]}"
            )
        else:
            lines.append(
                f"- **{cls.description}** (`{name}`): ❌ ei ladattu — "
                f"kutsu `populate_reference('{name}')`"
            )

    return "\n".join(lines)


@mcp.tool()
def populate_reference(
    source: str = "all",
    ctx: Context | None = None,
) -> str:
    """Lataa viiteaineistot paikalliseen kantaan.

    Args:
        source: Populaattorin nimi tai "all" kaikille.
            Vaihtoehdot: "municipalities", "postal_codes", "all"
    """
    from aura.populators import POPULATORS, get_populator

    conn = _server._get_conn(ctx)

    if source == "all":
        names = list(POPULATORS.keys())
    else:
        try:
            get_populator(source)
        except ValueError:
            available = ", ".join(POPULATORS.keys())
            return f"Tuntematon lähde '{source}'. Vaihtoehdot: {available}, all"
        names = [source]

    results = []
    for name in names:
        cls = POPULATORS[name]
        populator = cls(conn=conn)
        try:
            count = asyncio.run(populator.populate())
            results.append(f"- **{cls.description}**: {count} tietuetta ladattu")
        except Exception as e:
            results.append(f"- **{cls.description}**: virhe — {e}")

    return "**Viiteaineistot päivitetty:**\n\n" + "\n".join(results)


@mcp.tool()
def lookup_municipality(query: str, ctx: Context | None = None) -> str:
    """Hae kuntatietoja nimellä, koodilla tai postinumerolla.

    Tunnistaa automaattisesti onko kyseessä kunnan nimi (esim. "Tampere"),
    kuntakoodi (esim. "091") tai postinumero (esim. "33100").

    Args:
        query: Kunnan nimi, kuntakoodi tai postinumero
    """
    conn = _server._get_conn(ctx)
    query = query.strip()

    # Tarkista onko ref_municipalities populoitu
    meta = conn.execute(
        "SELECT record_count FROM ref_metadata WHERE name = 'municipalities'"
    ).fetchone()
    if not meta or meta["record_count"] == 0:
        return (
            "Kuntatietoja ei ole ladattu. "
            "Kutsu ensin: `populate_reference('municipalities')`"
        )

    # Tunnista tyyppi
    if query.isdigit() and len(query) == 5:
        # Postinumero → hae kunta
        postal = conn.execute(
            "SELECT * FROM ref_postal_codes WHERE code = ?", (query,)
        ).fetchone()
        if not postal:
            return f"Postinumeroa '{query}' ei löytynyt."
        muni_code = postal["municipality_code"]
        muni = conn.execute(
            "SELECT * FROM ref_municipalities WHERE code = ?", (muni_code,)
        ).fetchone()
        if not muni:
            return f"Postinumero {query} ({postal['name_fi']}) — kuntaa ei löytynyt."
        return _format_municipality(muni, postal_info=f"{query} {postal['name_fi']}")

    if query.isdigit() and len(query) <= 3:
        # Kuntakoodi
        code = query.zfill(3)
        muni = conn.execute(
            "SELECT * FROM ref_municipalities WHERE code = ?", (code,)
        ).fetchone()
        if not muni:
            return f"Kuntakoodilla '{code}' ei löytynyt kuntaa."
        return _format_municipality(muni)

    # Nimi-haku (case-insensitive)
    muni = conn.execute(
        "SELECT * FROM ref_municipalities WHERE name_fi LIKE ? OR name_sv LIKE ?",
        (query, query),
    ).fetchone()
    if not muni:
        # Osittainen haku
        munis = conn.execute(
            "SELECT * FROM ref_municipalities WHERE name_fi LIKE ? OR name_sv LIKE ? LIMIT 5",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        if not munis:
            return f"Kuntaa '{query}' ei löytynyt."
        lines = [f"Löytyi {len(munis)} kuntaa haulle '{query}':\n"]
        for m in munis:
            lines.append(f"- **{m['name_fi']}** ({m['code']})")
        return "\n".join(lines)

    return _format_municipality(muni)


def _format_municipality(
    muni: Any,
    postal_info: str = "",
) -> str:
    """Muotoile kuntatiedot luettavaksi."""
    lines = [f"## {muni['name_fi']}"]
    if muni["name_sv"]:
        lines.append(f"- **Ruotsiksi:** {muni['name_sv']}")
    lines.append(f"- **Kuntakoodi:** {muni['code']}")
    if postal_info:
        lines.append(f"- **Postinumero:** {postal_info}")
    if muni["region_name_fi"]:
        lines.append(f"- **Maakunta:** {muni['region_name_fi']}")
    if muni["ely_name_fi"]:
        lines.append(f"- **ELY-keskus:** {muni['ely_name_fi']}")
    if muni["wellbeing_area_name_fi"]:
        lines.append(f"- **Hyvinvointialue:** {muni['wellbeing_area_name_fi']}")
    return "\n".join(lines)
