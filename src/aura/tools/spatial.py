"""Paikkatietotyökalut (#136): map_sheet, find_map_sheets.

Palvelevat ref_map_sheets-taulusta (kannassa jo bbox EPSG:3067) → toimivat myös
read-only-remotessa. Agentti voi rajata WFS/WCS/OGC-kyselyt karttalehden bbox:illa.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastmcp import Context

import aura.server as _server
from aura.limits import MAX_LIST_LIMIT, clamp
from aura.server import mcp


def _map_sheet_data(conn: sqlite3.Connection, sheet_id: str) -> dict[str, Any] | None:
    """Hae karttalehden tiedot (bbox, centroid, mittakaava) kannasta."""
    row = conn.execute(
        """
        SELECT id, scale, min_x, min_y, max_x, max_y, centroid_x, centroid_y
        FROM ref_map_sheets WHERE id = ? COLLATE NOCASE
        """,
        (sheet_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "scale": row["scale"],
        "min_x": row["min_x"],
        "min_y": row["min_y"],
        "max_x": row["max_x"],
        "max_y": row["max_y"],
        "centroid_x": row["centroid_x"],
        "centroid_y": row["centroid_y"],
    }


def _bbox_str(d: dict[str, Any]) -> str:
    """Valmis WFS/WCS-bbox EPSG:3067:ssä: minx,miny,maxx,maxy,EPSG:3067."""
    return f"{d['min_x']},{d['min_y']},{d['max_x']},{d['max_y']},EPSG:3067"


def _format_map_sheet(d: dict[str, Any]) -> str:
    return (
        f"Karttalehti {d['id']} (mittakaavataso {d['scale']}, EPSG:3067)\n"
        f"  bbox (WFS/WCS): {_bbox_str(d)}\n"
        f"  centroidi: {d['centroid_x']},{d['centroid_y']}\n\n"
        f"Käytä bbox-arvoa aluerajauksena WFS/WCS/OGC-kyselyssä."
    )


def _parse_floats(text: str, count: int) -> list[float] | None:
    """Pilko pilkuilla erotettu lukumerkkijono (esim. bbox tai piste)."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != count:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def _find_map_sheets(
    conn: sqlite3.Connection,
    *,
    scale: str,
    bbox: list[float] | None = None,
    point: list[float] | None = None,
    prefix: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Hae karttalehdet mittakaavatasolta suodattimilla (bbox/piste/prefiksi)."""
    sql = (
        "SELECT id, scale, min_x, min_y, max_x, max_y, centroid_x, centroid_y "
        "FROM ref_map_sheets WHERE scale = ?"
    )
    params: list[Any] = [scale]

    if prefix:
        sql += " AND id LIKE ? COLLATE NOCASE"
        params.append(f"{prefix}%")
    if bbox:
        # Leikkaavuus: EI (lehti kokonaan bbox:n ulkopuolella)
        sql += " AND NOT (max_x < ? OR min_x > ? OR max_y < ? OR min_y > ?)"
        params.extend([bbox[0], bbox[2], bbox[1], bbox[3]])
    if point:
        sql += " AND min_x <= ? AND max_x >= ? AND min_y <= ? AND max_y >= ?"
        params.extend([point[0], point[0], point[1], point[1]])

    sql += " ORDER BY id LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def find_map_sheets(
    scale: str,
    bbox: str | None = None,
    point: str | None = None,
    prefix: str | None = None,
    limit: int = 50,
    ctx: Context | None = None,
) -> str:
    """Etsi karttalehdet jotka osuvat alueelle (aluerajauksen apu).

    Anna **vähintään yksi** suodatin: ``bbox``, ``point`` tai ``prefix``.

    Args:
        scale: Mittakaavataso: 'utm200' (yleiskatsaus), 'utm50' (maakunnat),
            'utm25' (kaupungit), 'utm10' (yksityiskohdat).
        bbox: Rajauslaatikko EPSG:3067: 'minx,miny,maxx,maxy' — palauttaa leikkaavat lehdet.
        point: Piste EPSG:3067: 'x,y' — palauttaa lehden joka sisältää pisteen.
        prefix: Tunnusprefiksi (esim. 'L413') — hierarkkinen rajaus.
        limit: Tulosten enimmäismäärä (oletus 50).
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    if not (bbox or point or prefix):
        return (
            "Anna vähintään yksi suodatin: bbox ('minx,miny,maxx,maxy'), "
            "point ('x,y') tai prefix (esim. 'L413')."
        )

    bbox_vals = _parse_floats(bbox, 4) if bbox else None
    if bbox and bbox_vals is None:
        return "Virheellinen bbox. Muoto: 'minx,miny,maxx,maxy' (EPSG:3067)."
    point_vals = _parse_floats(point, 2) if point else None
    if point and point_vals is None:
        return "Virheellinen point. Muoto: 'x,y' (EPSG:3067)."

    conn = _server._get_conn(ctx)
    sheets = _find_map_sheets(
        conn,
        scale=scale.strip(),
        bbox=bbox_vals,
        point=point_vals,
        prefix=prefix.strip() if prefix else None,
        limit=limit,
    )
    if not sheets:
        return f"Ei karttalehtiä mittakaavatasolla '{scale}' annetuilla suodattimilla."

    lines = [f"Löytyi {len(sheets)} karttalehteä (mittakaavataso {scale}, EPSG:3067):"]
    for d in sheets:
        lines.append(f"  {d['id']}: bbox {_bbox_str(d)}")
    return "\n".join(lines)


def _municipality_row(conn: sqlite3.Connection, query: str) -> sqlite3.Row | None:
    """Hae kunta nimellä (fi/sv) tai kuntakoodilla."""
    row: sqlite3.Row | None
    if query.isdigit() and len(query) <= 3:
        code = query.zfill(3)
        row = conn.execute(
            "SELECT * FROM ref_municipalities WHERE code = ?", (code,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM ref_municipalities "
            "WHERE name_fi = ? COLLATE NOCASE OR name_sv = ? COLLATE NOCASE",
            (query, query),
        ).fetchone()
    return row


@mcp.tool()
def municipality_bbox(query: str, ctx: Context | None = None) -> str:
    """Hae kunnan bbox (EPSG:3067) aluerajaukseen.

    Palauttaa kunnan rajauslaatikon valmiina WFS/WCS-kyselyyn. Voit ketjuttaa:
    hae kunnan bbox → syötä se ``find_map_sheets(bbox=...)``-kutsuun.

    Args:
        query: Kunnan nimi (fi/sv) tai kuntakoodi (esim. 'Helsinki' tai '091').
    """
    conn = _server._get_conn(ctx)
    row = _municipality_row(conn, query.strip())
    if row is None:
        return f"Kuntaa '{query}' ei löytynyt."
    if row["min_x"] is None:
        return (
            f"Kunnan {row['name_fi']} bbox-tietoja ei ole ladattu. "
            "Aja ensin: `populate_reference('municipality_bbox')`."
        )
    bbox = f"{row['min_x']},{row['min_y']},{row['max_x']},{row['max_y']},EPSG:3067"
    return (
        f"Kunta {row['name_fi']} ({row['code']}, EPSG:3067)\n"
        f"  bbox (WFS/WCS): {bbox}\n\n"
        f"Käytä bbox-arvoa aluerajauksena tai find_map_sheets(bbox=...)-kutsussa."
    )


@mcp.tool()
def map_sheet(sheet_id: str, ctx: Context | None = None) -> str:
    """Hae karttalehden bbox (EPSG:3067) aluerajaukseen.

    Palauttaa karttalehden rajauslaatikon valmiina WFS/WCS-kyselyyn. Karttalehdet
    ovat MML:n TM35-ruutuja (esim. 'L4133', 'L4133A').

    Args:
        sheet_id: Karttalehtitunnus (esim. 'L4133A'). Kirjainkoolla ei väliä.
    """
    conn = _server._get_conn(ctx)
    data = _map_sheet_data(conn, sheet_id.strip())
    if data is None:
        return f"Karttalehteä '{sheet_id}' ei löytynyt."
    return _format_map_sheet(data)
