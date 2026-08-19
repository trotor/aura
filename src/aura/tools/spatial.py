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


#: Ainoa koordinaatisto jota karttalehti- ja kuntarajaukset käyttävät.
CRS = "EPSG:3067"

#: Aluerajaus bbox-nelikkona (minx, miny, maxx, maxy) EPSG:3067:ssä.
Bbox = tuple[float, float, float, float]


def _bbox_param(bbox: Bbox) -> str:
    """Valmis WFS/WCS-bbox EPSG:3067:ssä: minx,miny,maxx,maxy,EPSG:3067."""
    return f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{CRS}"


def _bbox_str(d: dict[str, Any]) -> str:
    """Rivin bbox samassa muodossa kuin :func:`_bbox_param`."""
    return _bbox_param((d["min_x"], d["min_y"], d["max_x"], d["max_y"]))


def _parent_sheet(conn: sqlite3.Connection, sheet_id: str) -> dict[str, Any] | None:
    """Hae lehden vanhempi pisimpänä olemassa olevana prefiksinä.

    Hierarkiassa on aukkoja: kannassa on utm200, utm50, utm25 ja utm10,
    mutta ei utm100:aa. Kiinteä merkkimäärä (yksi pois) putoaisi siis
    tyhjään tasoon, joten vanhempi on haettava sillä mitä kannassa on.
    """
    row = conn.execute(
        "SELECT id, scale FROM ref_map_sheets "
        "WHERE ? LIKE id || '%' AND LENGTH(id) < LENGTH(?) "
        "ORDER BY LENGTH(id) DESC LIMIT 1",
        (sheet_id, sheet_id),
    ).fetchone()
    return dict(row) if row else None


def _child_sheets(conn: sqlite3.Connection, sheet_id: str) -> list[dict[str, Any]]:
    """Hae lehden suorat lapset eli seuraavan olemassa olevan tason lehdet."""
    rows = conn.execute(
        "SELECT id, scale FROM ref_map_sheets "
        "WHERE id LIKE ? || '%' AND LENGTH(id) > LENGTH(?) "
        "ORDER BY LENGTH(id), id",
        (sheet_id, sheet_id),
    ).fetchall()
    if not rows:
        return []
    next_level = len(rows[0]["id"])
    return [dict(r) for r in rows if len(r["id"]) == next_level]


def _format_map_sheet(conn: sqlite3.Connection, d: dict[str, Any]) -> str:
    lines = [
        f"Karttalehti {d['id']} (mittakaavataso {d['scale']}, EPSG:3067)",
        f"  bbox (WFS/WCS): {_bbox_str(d)}",
        f"  centroidi: {d['centroid_x']},{d['centroid_y']}",
    ]
    parent = _parent_sheet(conn, d["id"])
    if parent:
        lines.append(f"  vanhempi: {parent['id']} ({parent['scale']})")
    children = _child_sheets(conn, d["id"])
    if children:
        ids = ", ".join(c["id"] for c in children)
        lines.append(f"  lapset ({children[0]['scale']}): {ids}")
    lines.append("")
    lines.append("Käytä bbox-arvoa aluerajauksena WFS/WCS/OGC-kyselyssä tai anna")
    lines.append(f"lehtitunnus suoraan: query_data(dataset_id, area='{d['id']}').")
    return "\n".join(lines)


def _parse_floats(text: str, count: int) -> list[float] | None:
    """Pilko pilkuilla erotettu lukumerkkijono (esim. bbox tai piste)."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != count:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def _strip_crs(text: str) -> tuple[str, str | None]:
    """Irrota mahdollinen koordinaatistopääte bbox-merkkijonosta.

    Sekä :func:`municipality_bbox` että :func:`find_map_sheets` tulostavat
    bbox-arvon muodossa ``minx,miny,maxx,maxy,EPSG:3067`` ja kehottavat
    syöttämään sen seuraavaan kutsuun. Ilman tätä irrotusta kehotus
    johtaa virheeseen: viisiosainen arvo ei kelpaa neliosaiseen kenttään,
    ja ketju katkeaa juuri siinä kohtaa jossa ohje lupaa sen toimivan.

    Palauttaa ``(numero-osa, koordinaatisto tai None)``.
    """
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if parts and ":" in parts[-1]:
        return ",".join(parts[:-1]), parts[-1].upper()
    return ",".join(parts), None


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
    municipality: str | None = None,
    limit: int = 50,
    ctx: Context | None = None,
) -> str:
    """Etsi karttalehdet jotka osuvat alueelle (aluerajauksen apu).

    Anna **vähintään yksi** suodatin: ``bbox``, ``point``, ``prefix`` tai
    ``municipality``.

    Args:
        scale: Mittakaavataso: 'utm200' (yleiskatsaus), 'utm50' (maakunnat),
            'utm25' (kaupungit), 'utm10' (yksityiskohdat).
        bbox: Rajauslaatikko EPSG:3067: 'minx,miny,maxx,maxy'. Myös
            muoto '...,EPSG:3067' kelpaa, eli municipality_bbox():n ja
            tämän oma tuloste voidaan syöttää sellaisenaan takaisin.
        point: Piste EPSG:3067: 'x,y' — palauttaa lehden joka sisältää pisteen.
        prefix: Tunnusprefiksi (esim. 'L413') — hierarkkinen rajaus.
        municipality: Kunnan nimi (fi/sv) tai koodi — sama kuin antaisi
            kunnan bbox:n, ilman välikutsua municipality_bbox():iin.
        limit: Tulosten enimmäismäärä (oletus 50).
    """
    limit = clamp(limit, MAX_LIST_LIMIT)
    if not (bbox or point or prefix or municipality):
        return (
            "Anna vähintään yksi suodatin: bbox ('minx,miny,maxx,maxy'), "
            "point ('x,y'), prefix (esim. 'L413') tai municipality ('Tampere')."
        )
    if bbox and municipality:
        return "Anna joko bbox tai municipality, ei molempia."

    conn = _server._get_conn(ctx)

    bbox_vals = None
    if municipality:
        area_bbox, detail = _resolve_municipality_bbox(conn, municipality.strip())
        if area_bbox is None:
            return detail
        bbox_vals = list(area_bbox)
    if bbox:
        numbers, crs = _strip_crs(bbox)
        # Väärä koordinaatisto on hylättävä äänekkäästi: hiljaa ohitettuna
        # WGS84-koordinaatit osuisivat Suomen ruudukossa mereen eikä
        # tyhjä tulos kertoisi syytä.
        if crs and crs != CRS:
            return f"Koordinaatisto {crs} ei kelpaa. Karttalehtijako on {CRS}:ssä."
        bbox_vals = _parse_floats(numbers, 4)
        if bbox_vals is None:
            return f"Virheellinen bbox. Muoto: 'minx,miny,maxx,maxy' ({CRS})."
    point_vals = None
    if point:
        numbers, crs = _strip_crs(point)
        if crs and crs != CRS:
            return f"Koordinaatisto {crs} ei kelpaa. Karttalehtijako on {CRS}:ssä."
        point_vals = _parse_floats(numbers, 2)
        if point_vals is None:
            return f"Virheellinen point. Muoto: 'x,y' ({CRS})."

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
        row = conn.execute("SELECT * FROM ref_municipalities WHERE code = ?", (code,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM ref_municipalities "
            "WHERE name_fi = ? COLLATE NOCASE OR name_sv = ? COLLATE NOCASE",
            (query, query),
        ).fetchone()
    return row


def _resolve_municipality_bbox(
    conn: sqlite3.Connection, query: str
) -> tuple[Bbox | None, str]:
    """Kunnan bbox nimellä tai koodilla; virhetilanteessa (None, syy)."""
    row = _municipality_row(conn, query)
    if row is None:
        return None, f"Kuntaa '{query}' ei löytynyt."
    if row["min_x"] is None:
        return None, (
            f"Kunnan {row['name_fi']} bbox-tietoja ei ole ladattu. "
            "Aja ensin: `populate_reference('municipality_bbox')`."
        )
    bbox = (row["min_x"], row["min_y"], row["max_x"], row["max_y"])
    return bbox, f"{row['name_fi']} ({row['code']})"


def _resolve_area(
    conn: sqlite3.Connection, area: str
) -> tuple[Bbox | None, str]:
    """Ratkaise aluerajaus bbox:ksi: kunta, karttalehti tai raaka bbox.

    Tunnistus tehdään kannasta hakemalla eikä merkkijonoa arvaamalla —
    kuntien nimet ja lehtitunnukset ovat molemmat vapaata tekstiä, ja
    väärin arvattu tyyppi rajaisi kyselyn hiljaa väärään paikkaan.

    Palauttaa ``(bbox, kuvaus)`` onnistuessa ja ``(None, virheviesti)``
    muuten. Virhe on aina kerrottava: hiljaa ohitettu aluerajaus tuottaisi
    oikealta näyttävän vastauksen väärältä alueelta.
    """
    text = area.strip()
    if not text:
        return None, "Tyhjä aluerajaus."

    # 1) Raaka bbox — pilkut erottavat sen nimistä ja lehtitunnuksista.
    numbers, crs = _strip_crs(text)
    if "," in numbers:
        if crs and crs != CRS:
            return None, f"Koordinaatisto {crs} ei kelpaa. Aluerajaus on {CRS}:ssä."
        vals = _parse_floats(numbers, 4)
        if vals is None:
            return None, (
                f"Virheellinen bbox '{text}'. Muoto: 'minx,miny,maxx,maxy' ({CRS})."
            )
        return (vals[0], vals[1], vals[2], vals[3]), "annettu bbox"

    # 2) Karttalehti.
    sheet = _map_sheet_data(conn, text)
    if sheet is not None:
        bbox = (sheet["min_x"], sheet["min_y"], sheet["max_x"], sheet["max_y"])
        return bbox, f"karttalehti {sheet['id']} ({sheet['scale']})"

    # 3) Kunta nimellä tai koodilla.
    if _municipality_row(conn, text) is not None:
        return _resolve_municipality_bbox(conn, text)

    return None, (
        f"Aluetta '{text}' ei tunnistettu: ei kuntaa, ei karttalehteä eikä "
        f"bbox:ia. Anna kunnan nimi tai koodi, lehtitunnus (esim. 'L4133A') "
        f"tai bbox 'minx,miny,maxx,maxy' ({CRS})."
    )


@mcp.tool()
def municipality_bbox(query: str, ctx: Context | None = None) -> str:
    """Hae kunnan bbox (EPSG:3067) aluerajaukseen.

    Palauttaa kunnan rajauslaatikon valmiina WFS/WCS-kyselyyn. Useimmiten
    tätä ei tarvita erikseen: ``query_data(dataset_id, area='Helsinki')`` ja
    ``find_map_sheets(scale=..., municipality='Helsinki')`` ottavat kunnan
    nimen suoraan.

    Args:
        query: Kunnan nimi (fi/sv) tai kuntakoodi (esim. 'Helsinki' tai '091').
    """
    conn = _server._get_conn(ctx)
    name = query.strip()
    bbox, detail = _resolve_municipality_bbox(conn, name)
    if bbox is None:
        return detail
    return (
        f"Kunta {detail} {CRS}\n"
        f"  bbox (WFS/WCS): {_bbox_param(bbox)}\n\n"
        f"Käytä bbox-arvoa aluerajauksena, tai anna kunnan nimi suoraan: "
        f"query_data(dataset_id, area='{name}')."
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
    return _format_map_sheet(conn, data)
