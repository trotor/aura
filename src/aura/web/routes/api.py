"""JSON API -endpointit (kartta, esikatselu)."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from aura.web.app import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

BOUNDARIES_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "boundaries"

# Cache kuntarajoille (muutettu EPSG:4326 GeoJSON)
_municipality_geojson_cache: dict[str, Any] | None = None


def _tm35_to_wgs84(e: float, n: float) -> tuple[float, float]:
    """Likimääräinen EPSG:3067 (TM35FIN) → EPSG:4326 (WGS84) muunnos.

    Käyttää yksinkertaista affiinista approksimaatiota joka riittää
    kuntarajojen visualisointiin karttapohjalla.
    """
    # TM35FIN keskimeridiaani 27°E, scale 0.9996
    # Yksinkertainen approksimaatio Suomen alueelle
    lat = n / 111320.0
    lon = 27.0 + (e - 500000.0) / (111320.0 * math.cos(math.radians(lat)))
    return lat, lon


def _load_municipality_geojson() -> dict[str, Any]:
    """Lataa kuntarajat GeoPackagesta ja muunna GeoJSON-muotoon."""
    global _municipality_geojson_cache
    if _municipality_geojson_cache is not None:
        return _municipality_geojson_cache

    gpkg_path = BOUNDARIES_DIR / "kuntajako_1000k.gpkg"
    if not gpkg_path.exists():
        return {"type": "FeatureCollection", "features": []}

    conn = sqlite3.connect(str(gpkg_path))
    conn.row_factory = sqlite3.Row

    features: list[dict[str, Any]] = []

    # Kokeile eri tapoja lukea kuntarajat (MbrMinX → RTree fallback)
    queries = [
        """
        SELECT natcode, namefin, nameswe,
               MbrMinX(multipolygon) as minx, MbrMinY(multipolygon) as miny,
               MbrMaxX(multipolygon) as maxx, MbrMaxY(multipolygon) as maxy
        FROM Kunta
        """,
        """
        SELECT k.natcode, k.namefin, k.nameswe,
               r.minx, r.miny, r.maxx, r.maxy
        FROM Kunta k
        JOIN rtree_Kunta_multipolygon r ON k.id = r.id
        """,
    ]

    rows = None
    for query in queries:
        try:
            rows = conn.execute(query).fetchall()
            break
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            continue

    if rows is None:
        logger.warning("Kuntarajoja ei voitu lukea GeoPackagesta")
        conn.close()
        return {"type": "FeatureCollection", "features": []}

    for row in rows:
        # Muunna bbox WGS84:ksi ja luo yksinkertainen rectangle-polygoni
        min_lat, min_lon = _tm35_to_wgs84(row["minx"], row["miny"])
        max_lat, max_lon = _tm35_to_wgs84(row["maxx"], row["maxy"])

        feature: dict[str, Any] = {
            "type": "Feature",
            "properties": {
                "code": row["natcode"],
                "name": row["namefin"],
                "name_sv": row["nameswe"] or "",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [min_lon, min_lat],
                    [max_lon, min_lat],
                    [max_lon, max_lat],
                    [min_lon, max_lat],
                    [min_lon, min_lat],
                ]],
            },
        }
        features.append(feature)

    conn.close()

    geojson: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
    }
    _municipality_geojson_cache = geojson
    return geojson


@router.get("/geo/municipalities")
async def municipalities_geojson() -> dict[str, Any]:
    """Kuntarajat GeoJSON-muodossa (EPSG:4326)."""
    return _load_municipality_geojson()


@router.get("/geo/dataset-counts")
async def dataset_counts_by_municipality(request: Request) -> dict[str, Any]:
    """Datasettimäärät kunnittain geographical_coverage-kentän perusteella."""
    conn = get_db(request)

    rows = conn.execute(
        """
        SELECT geographical_coverage FROM datasets
        WHERE geographical_coverage != '' AND geographical_coverage != '[]'
        """
    ).fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        try:
            coverage = json.loads(row["geographical_coverage"])
            if isinstance(coverage, list):
                for area in coverage:
                    area = area.strip().title()
                    counts[area] = counts.get(area, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    return {"counts": counts}


@router.get("/wms/capabilities")
async def wms_capabilities(url: str = Query(...)) -> dict[str, Any]:
    """Parsii WMS GetCapabilities XML:n ja palauttaa tasot."""
    import httpx

    try:
        base_url = url.split("?")[0]
        params = {
            "service": "WMS",
            "request": "GetCapabilities",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(base_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if "html" in ct:
                return {
                    "error": "URL palauttaa HTML-sivun eikä WMS-palvelua",
                    "layers": [],
                }
            xml_text = resp.text

        return _parse_wms_capabilities(xml_text)
    except Exception as e:
        return {"error": str(e), "layers": []}


def _parse_wms_capabilities(xml_text: str) -> dict[str, Any]:
    """Parsii WMS GetCapabilities XML:stä tasot."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return {"error": f"XML-parsintavirhe: {e}", "layers": []}

    # Etsi namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    layers: list[dict[str, str]] = []
    bbox: list[float] | None = None

    # Etsi kaikki Layer-elementit joilla on Name
    for layer_el in root.iter(f"{ns}Layer"):
        name_el = layer_el.find(f"{ns}Name")
        title_el = layer_el.find(f"{ns}Title")
        if name_el is not None and name_el.text:
            layers.append({
                "name": name_el.text,
                "title": (title_el.text or name_el.text) if title_el is not None else name_el.text,
            })

        # Koeta lukea bbox
        if bbox is None:
            bbox_el = layer_el.find(f"{ns}EX_GeographicBoundingBox")
            if bbox_el is not None:
                try:
                    bbox = [
                        float(bbox_el.findtext(f"{ns}westBoundLongitude", "0")),
                        float(bbox_el.findtext(f"{ns}southBoundLatitude", "0")),
                        float(bbox_el.findtext(f"{ns}eastBoundLongitude", "0")),
                        float(bbox_el.findtext(f"{ns}northBoundLatitude", "0")),
                    ]
                except (ValueError, TypeError):
                    pass

            # Vaihtoehtoinen bbox (WMS 1.1.1)
            if bbox is None:
                latlonbox = layer_el.find(f"{ns}LatLonBoundingBox")
                if latlonbox is not None:
                    try:
                        bbox = [
                            float(latlonbox.get("minx", "0")),
                            float(latlonbox.get("miny", "0")),
                            float(latlonbox.get("maxx", "0")),
                            float(latlonbox.get("maxy", "0")),
                        ]
                    except (ValueError, TypeError):
                        pass

    result: dict[str, Any] = {"layers": layers}
    if bbox:
        result["bbox"] = bbox
    return result


@router.get("/wfs/capabilities")
async def wfs_capabilities(url: str = Query(...)) -> dict[str, Any]:
    """Parsii WFS GetCapabilities XML:n ja palauttaa featuretyypit."""
    import httpx

    try:
        base_url = url.split("?")[0]
        params = {
            "service": "WFS",
            "request": "GetCapabilities",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(base_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if "html" in ct:
                return {
                    "error": "URL palauttaa HTML-sivun eikä WFS-palvelua",
                    "feature_types": [],
                }
            xml_text = resp.text

        return _parse_wfs_capabilities(xml_text)
    except Exception as e:
        return {"error": str(e), "feature_types": []}


def _parse_wfs_capabilities(xml_text: str) -> dict[str, Any]:
    """Parsii WFS GetCapabilities XML:stä featuretyypit."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return {"error": f"XML-parsintavirhe: {e}", "feature_types": []}

    feature_types: list[dict[str, str]] = []

    # Etsi FeatureType-elementit kaikista namespacesta
    for el in root.iter():
        if el.tag.endswith("FeatureType") or el.tag == "FeatureType":
            name = ""
            title = ""
            for child in el:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "Name" and child.text:
                    name = child.text
                elif tag == "Title" and child.text:
                    title = child.text
            if name:
                feature_types.append({"name": name, "title": title or name})

    return {"feature_types": feature_types}


@router.get("/wfs/features")
async def wfs_features(
    url: str = Query(...),
    type_name: str = Query(..., alias="typeName"),
    max_features: int = Query(default=500, le=2000, alias="maxFeatures"),
) -> dict[str, Any]:
    """Hakee WFS-featuret GeoJSON-muodossa."""
    import httpx

    try:
        base_url = url.split("?")[0]
        params = {
            "service": "WFS",
            "request": "GetFeature",
            "typeName": type_name,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "maxFeatures": str(max_features),
            "count": str(max_features),  # WFS 2.0 käyttää count-parametria
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(base_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            geojson = resp.json()

        return {"geojson": geojson}
    except Exception as e:
        return {"error": str(e)}


@router.get("/preview/{resource_id}")
async def preview_resource(
    request: Request,
    resource_id: str,
    max_rows: int = Query(default=10, le=100),
) -> dict[str, Any]:
    """Resurssin esikatselu: hae ensimmäiset rivit ja palauta rakenteisena."""
    import httpx

    conn = get_db(request)
    row = conn.execute(
        "SELECT * FROM resources WHERE id = ?", (resource_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Resurssia ei löytynyt")

    resource = dict(row)
    url = resource.get("url", "")
    fmt = (resource.get("format", "") or "").upper()

    if not url:
        return {"type": "empty", "message": "Resurssilla ei ole URL:ia"}

    # JSON/API -esikatselu
    if fmt in ("JSON", "API", "GEOJSON"):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                text = resp.text

            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                # Virheellinen JSON — näytä raakadata esikatseluna
                snippet = text[:3000]
                return {"type": "text", "content": snippet, "url": url}

            if isinstance(data, list):
                return {"type": "table", "rows": data[:max_rows], "total": len(data)}
            if isinstance(data, dict):
                # Jos on GeoJSON FeatureCollection
                if data.get("type") == "FeatureCollection":
                    features = data.get("features", [])
                    rows_data = [f.get("properties", {}) for f in features[:max_rows]]
                    return {"type": "table", "rows": rows_data, "total": len(features)}
                return {"type": "json", "data": data}
        except httpx.HTTPStatusError as e:
            return {
                "type": "error",
                "message": f"Palvelin palautti virheen {e.response.status_code}",
                "url": url,
            }
        except Exception as e:
            msg = str(e)
            # Tee httpx-virheilmoituksista luettavampia
            if "timed out" in msg.lower() or "timeout" in msg.lower():
                msg = "Aikakatkaisu: palvelin ei vastannut ajoissa"
            elif "connect" in msg.lower():
                msg = "Yhteysvirhe: palvelimeen ei saatu yhteyttä"
            return {"type": "error", "message": msg}

    # CSV-esikatselu
    if fmt == "CSV":
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                async with client.stream("GET", url, follow_redirects=True) as resp:
                    resp.raise_for_status()
                    content = b""
                    async for chunk in resp.aiter_bytes():
                        content += chunk
                        if len(content) > 8192:
                            break

            import csv
            import io

            text = content.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows_list: list[list[str]] = []
            for csv_row in reader:
                rows_list.append(csv_row)
                if len(rows_list) > max_rows + 1:
                    break

            if rows_list:
                headers = rows_list[0]
                data_rows = rows_list[1:max_rows + 1]
                return {
                    "type": "csv",
                    "headers": headers,
                    "rows": data_rows,
                }
        except Exception as e:
            return {"type": "error", "message": str(e)}

    # WFS/WMS
    if fmt in ("WFS", "WMS", "WCS"):
        return {
            "type": "ogc",
            "service": fmt,
            "url": url,
            "message": f"{fmt}-palvelu: {url}",
        }

    # Muu formaatti
    return {"type": "link", "url": url, "format": fmt}
