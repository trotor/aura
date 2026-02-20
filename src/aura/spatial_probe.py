"""Paikkatietoaineistojen koon mittaus otoskyselyillä.

Mittaa WFS- ja WCS-rajapinnoista palautuvan datan määrän pienillä
otosalueilla ja ekstrapoloi koko Suomen mittakaavalle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

# --- Vakiot ---

FINLAND_BBOX = (19.5, 59.5, 31.5, 70.1)  # EPSG:4326
FINLAND_AREA_KM2 = 338_440.0

# Otosalueet (~10×10 km)
SAMPLE_BBOXES: list[tuple[str, tuple[float, float, float, float]]] = [
    ("Helsinki", (24.90, 60.15, 25.05, 60.24)),
    ("Jyväskylä", (25.70, 62.20, 25.85, 62.29)),
    ("Kuopio", (27.60, 62.85, 27.75, 62.94)),
    ("Oulu", (25.40, 65.00, 25.55, 65.09)),
    ("Rovaniemi", (25.65, 66.48, 25.80, 66.57)),
]

USER_AGENT = "Aura/0.1.0 (https://github.com/trotor/aura)"
DEFAULT_TIMEOUT = 180.0
RATE_LIMIT_DELAY = 1.5  # sekuntia saman palvelimen kyselyjen välillä


# --- Tietorakenteet ---


@dataclass
class ProbeTarget:
    """Mittauskohde."""

    dataset_id: str
    endpoint_url: str
    service_type: str  # "WFS" tai "WCS"
    type_name: str = ""
    coverage_id: str = ""
    srs: str = "EPSG:4326"
    max_features: int = 100
    current_estimated_bytes: int = 0


@dataclass
class SampleResult:
    """Yksittäisen otoskyselyn tulos."""

    area_name: str
    feature_count: int = 0
    response_bytes: int = 0
    error: str = ""


@dataclass
class ProbeResult:
    """Mittaustulos yhdelle kohteelle."""

    dataset_id: str
    endpoint_url: str
    total_feature_count: int | None = None
    sample_bytes: int = 0
    bytes_per_feature: float = 0.0
    bytes_per_km2: float = 0.0
    extrapolated_size_bytes: int = 0
    current_estimated_bytes: int = 0
    error: str = ""
    samples: list[SampleResult] = field(default_factory=list)


# --- Metsäkeskus-kohteet ---

_MK_WFS_BASE = "https://avoin.metsakeskus.fi/rajapinnat/v1"

METSAKESKUS_WFS_TARGETS: list[ProbeTarget] = [
    ProbeTarget(
        dataset_id="metsakeskus-stand",
        endpoint_url=f"{_MK_WFS_BASE}/stand/ows",
        service_type="WFS",
        type_name="stand",
        current_estimated_bytes=50 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-gridcell",
        endpoint_url=f"{_MK_WFS_BASE}/gridcell/ows",
        service_type="WFS",
        type_name="gridcell",
        current_estimated_bytes=200 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-habitat",
        endpoint_url=f"{_MK_WFS_BASE}/habitat/ows",
        service_type="WFS",
        type_name="habitat",
        current_estimated_bytes=5 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-forestusedeclaration",
        endpoint_url=f"{_MK_WFS_BASE}/forestusedeclaration/ows",
        service_type="WFS",
        type_name="forestusedeclaration",
        current_estimated_bytes=10 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-forestmask",
        endpoint_url=f"{_MK_WFS_BASE}/forestmask/ows",
        service_type="WFS",
        type_name="forestmask",
        current_estimated_bytes=5 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-inventory_sampleplot",
        endpoint_url=f"{_MK_WFS_BASE}/inventory_sampleplot/ows",
        service_type="WFS",
        type_name="inventory_sampleplot",
        current_estimated_bytes=1 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-sampleplot",
        endpoint_url=f"{_MK_WFS_BASE}/sampleplot/ows",
        service_type="WFS",
        type_name="sampleplot",
        current_estimated_bytes=1 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-application_stand_06_16",
        endpoint_url=f"{_MK_WFS_BASE}/application_stand_06_16/ows",
        service_type="WFS",
        type_name="application_stand_06_16",
        current_estimated_bytes=500 * 1024**2,
    ),
]

METSAKESKUS_WCS_TARGETS: list[ProbeTarget] = [
    ProbeTarget(
        dataset_id="metsakeskus-chm_newest",
        endpoint_url=f"{_MK_WFS_BASE}/CHM_newest/ows",
        service_type="WCS",
        coverage_id="CHM_newest",
        current_estimated_bytes=100 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="metsakeskus-chm_2020",
        endpoint_url=f"{_MK_WFS_BASE}/CHM_2020/ows",
        service_type="WCS",
        coverage_id="CHM_2020",
        current_estimated_bytes=50 * 1024**3,
    ),
]

# --- GTK-kohteet ---

_GTK_BASE = "https://gtkdata.gtk.fi/arcgis/services/Rajapinnat"

GTK_WFS_TARGETS: list[ProbeTarget] = [
    ProbeTarget(
        dataset_id="gtk-kalliopera",
        endpoint_url=f"{_GTK_BASE}/GTK_Kalliopera_WFS/MapServer/WFSServer",
        service_type="WFS",
        type_name="",  # haetaan GetCapabilitiesista
        current_estimated_bytes=2 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="gtk-maapera",
        endpoint_url=f"{_GTK_BASE}/GTK_Maapera_WFS/MapServer/WFSServer",
        service_type="WFS",
        type_name="",
        current_estimated_bytes=3 * 1024**3,
    ),
    ProbeTarget(
        dataset_id="gtk-kiviainesvarannot",
        endpoint_url=f"{_GTK_BASE}/GTK_Kiviainesvarannot_WFS/MapServer/WFSServer",
        service_type="WFS",
        type_name="",
        current_estimated_bytes=int(0.5 * 1024**3),
    ),
]


# --- Apufunktiot ---


def _bbox_area_km2(bbox: tuple[float, float, float, float]) -> float:
    """Laske bbox:n pinta-ala karkeasti km²:nä (leveysastekorjaus)."""
    lon_min, lat_min, lon_max, lat_max = bbox
    import math

    mid_lat = math.radians((lat_min + lat_max) / 2)
    width_km = (lon_max - lon_min) * 111.32 * math.cos(mid_lat)
    height_km = (lat_max - lat_min) * 110.574
    return width_km * height_km


def _format_bytes(size_bytes: int | float) -> str:
    """Muotoile tavumäärä luettavaan muotoon."""
    if size_bytes < 1024:
        return f"{int(size_bytes)} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    else:
        return f"{size_bytes / 1024**3:.1f} GB"


def _get_server_host(url: str) -> str:
    """Palauta palvelimen hostname URL:sta."""
    from urllib.parse import urlparse

    return urlparse(url).netloc


# --- WFS-mittaus ---


async def discover_wfs_type_names(
    client: httpx.AsyncClient,
    endpoint_url: str,
) -> list[str]:
    """Parsii GetCapabilities-vastauksen ja palauttaa typeNamet."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetCapabilities",
    }
    try:
        resp = await client.get(endpoint_url, params=params)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.ReadTimeout) as e:
        logger.warning("[probe] GetCapabilities epäonnistui %s: %s", endpoint_url, e)
        return []

    type_names: list[str] = []
    try:
        root = ElementTree.fromstring(resp.content)
        # WFS 2.0 namespace
        ns = {
            "wfs": "http://www.opengis.net/wfs/2.0",
            "wfs11": "http://www.opengis.net/wfs",
        }
        # Kokeile WFS 2.0 ensin
        for ft in root.findall(".//wfs:FeatureType/wfs:Name", ns):
            if ft.text:
                type_names.append(ft.text)
        # Fallback WFS 1.1
        if not type_names:
            for ft in root.findall(".//wfs11:FeatureType/wfs11:Name", ns):
                if ft.text:
                    type_names.append(ft.text)
        # Fallback: ilman namespacea
        if not type_names:
            for ft in root.iter():
                if ft.tag.endswith("Name") and ft.text and "FeatureType" in (
                    ft.getparent().tag if hasattr(ft, "getparent") else ""
                ):
                    pass  # ElementTree ei tue getparent
            # Yksinkertainen haku ilman namespacea
            for ft in root.iter():
                tag = ft.tag.split("}")[-1] if "}" in ft.tag else ft.tag
                if tag == "Name":
                    parent = None
                    # Etsi parent FeatureType iteroimalla
                    for parent_el in root.iter():
                        parent_tag = (
                            parent_el.tag.split("}")[-1]
                            if "}" in parent_el.tag
                            else parent_el.tag
                        )
                        if parent_tag == "FeatureType" and ft in list(parent_el):
                            parent = parent_el
                            break
                    if parent is not None and ft.text:
                        type_names.append(ft.text)
    except ElementTree.ParseError as e:
        logger.warning("[probe] XML-parsinta epäonnistui %s: %s", endpoint_url, e)

    return type_names


async def probe_wfs_hits(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    timeout: float = DEFAULT_TIMEOUT,
) -> int | None:
    """Kysy WFS:ltä featurejen kokonaismäärä resultType=hits-kyselyllä."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "resultType": "hits",
    }
    if target.type_name:
        params["typeNames"] = target.type_name

    try:
        resp = await client.get(
            target.endpoint_url,
            params=params,
            timeout=timeout,
        )
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.ReadTimeout) as e:
        logger.info(
            "[probe] hits-kysely epäonnistui %s: %s", target.dataset_id, e
        )
        return None

    # Parsii numberMatched XML-vastauksesta
    try:
        root = ElementTree.fromstring(resp.content)
        # numberMatched voi olla attribuutissa tai elementissä
        num = root.get("numberMatched")
        if num and num != "unknown":
            return int(num)
        num = root.get("numberOfFeatures")
        if num:
            return int(num)
    except (ElementTree.ParseError, ValueError) as e:
        logger.info(
            "[probe] hits-vastauksen parsinta epäonnistui %s: %s",
            target.dataset_id,
            e,
        )

    return None


async def probe_wfs_sample(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    bbox: tuple[float, float, float, float],
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, int]:
    """Hae WFS-otos bbox-alueelta. Palauttaa (feature_count, response_bytes)."""
    lon_min, lat_min, lon_max, lat_max = bbox
    bbox_str = f"{lat_min},{lon_min},{lat_max},{lon_max},{target.srs}"

    params: dict[str, str | int] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "bbox": bbox_str,
        "maxFeatures": target.max_features,
        "outputFormat": "application/json",
    }
    if target.type_name:
        params["typeNames"] = target.type_name

    resp = await client.get(
        target.endpoint_url,
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()

    response_bytes = len(resp.content)
    feature_count = 0

    try:
        data = resp.json()
        features = data.get("features", [])
        feature_count = len(features)
    except Exception:
        # Jos JSON-parsinta ei onnistu, arvioidaan featurejen määrä
        pass

    return feature_count, response_bytes


# --- WCS-mittaus ---


async def probe_wcs_sample(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    bbox: tuple[float, float, float, float],
    timeout: float = DEFAULT_TIMEOUT,
) -> int:
    """Hae WCS-otos bbox-alueelta. Palauttaa response_bytes."""
    lon_min, lat_min, lon_max, lat_max = bbox

    params = {
        "service": "WCS",
        "version": "2.0.1",
        "request": "GetCoverage",
        "CoverageId": target.coverage_id,
        "subset": [f"Lat({lat_min},{lat_max})", f"Long({lon_min},{lon_max})"],
        "format": "image/tiff",
    }

    resp = await client.get(
        target.endpoint_url,
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    return len(resp.content)


# --- Mittauslogiikka ---


async def probe_target(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    timeout: float = DEFAULT_TIMEOUT,
) -> ProbeResult:
    """Mittaa yhden kohteen koko otoskyselyillä."""
    result = ProbeResult(
        dataset_id=target.dataset_id,
        endpoint_url=target.endpoint_url,
        current_estimated_bytes=target.current_estimated_bytes,
    )

    if target.service_type == "WFS":
        return await _probe_wfs_target(client, target, result, timeout)
    elif target.service_type == "WCS":
        return await _probe_wcs_target(client, target, result, timeout)
    else:
        result.error = f"Tuntematon palvelutyyppi: {target.service_type}"
        return result


async def _probe_wfs_target(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    result: ProbeResult,
    timeout: float,
) -> ProbeResult:
    """WFS-mittauslogiikka."""
    # Jos typenameä ei ole, yritä löytää GetCapabilitiesista
    if not target.type_name:
        type_names = await discover_wfs_type_names(client, target.endpoint_url)
        if type_names:
            target.type_name = type_names[0]
            logger.info(
                "[probe] %s: löydettiin typeName '%s'",
                target.dataset_id,
                target.type_name,
            )

    # Kokeile hits-kyselyä
    total_hits = await probe_wfs_hits(client, target, timeout)
    result.total_feature_count = total_hits

    # Otoskyselyt
    total_features = 0
    total_bytes = 0
    sample_areas_km2 = 0.0

    for area_name, bbox in SAMPLE_BBOXES:
        sample = SampleResult(area_name=area_name)
        try:
            fc, rb = await probe_wfs_sample(client, target, bbox, timeout)
            sample.feature_count = fc
            sample.response_bytes = rb
            total_features += fc
            total_bytes += rb
            sample_areas_km2 += _bbox_area_km2(bbox)
        except (httpx.HTTPError, httpx.ReadTimeout) as e:
            sample.error = str(e)
            logger.info(
                "[probe] %s otos %s epäonnistui: %s",
                target.dataset_id,
                area_name,
                e,
            )
        result.samples.append(sample)
        time.sleep(RATE_LIMIT_DELAY)

    result.sample_bytes = total_bytes

    if total_features > 0:
        result.bytes_per_feature = total_bytes / total_features

    if sample_areas_km2 > 0:
        result.bytes_per_km2 = total_bytes / sample_areas_km2

    # Ekstrapolointi
    if total_hits is not None and total_hits > 0 and result.bytes_per_feature > 0:
        # Feature-pohjainen ekstrapolointi (tarkempi)
        result.extrapolated_size_bytes = int(
            total_hits * result.bytes_per_feature
        )
    elif result.bytes_per_km2 > 0:
        # Pinta-alapohjainen fallback
        result.extrapolated_size_bytes = int(
            result.bytes_per_km2 * FINLAND_AREA_KM2
        )

    return result


async def _probe_wcs_target(
    client: httpx.AsyncClient,
    target: ProbeTarget,
    result: ProbeResult,
    timeout: float,
) -> ProbeResult:
    """WCS-mittauslogiikka."""
    total_bytes = 0
    sample_areas_km2 = 0.0

    for area_name, bbox in SAMPLE_BBOXES:
        sample = SampleResult(area_name=area_name)
        try:
            rb = await probe_wcs_sample(client, target, bbox, timeout)
            sample.response_bytes = rb
            total_bytes += rb
            sample_areas_km2 += _bbox_area_km2(bbox)
        except (httpx.HTTPError, httpx.ReadTimeout) as e:
            sample.error = str(e)
            logger.info(
                "[probe] %s otos %s epäonnistui: %s",
                target.dataset_id,
                area_name,
                e,
            )
        result.samples.append(sample)
        time.sleep(RATE_LIMIT_DELAY)

    result.sample_bytes = total_bytes

    if sample_areas_km2 > 0:
        result.bytes_per_km2 = total_bytes / sample_areas_km2
        result.extrapolated_size_bytes = int(
            result.bytes_per_km2 * FINLAND_AREA_KM2
        )

    return result


# --- Kohteiden haku ---


def get_targets(source: str = "all") -> list[ProbeTarget]:
    """Palauta mittauskohteet lähteen perusteella."""
    targets: list[ProbeTarget] = []

    if source in ("metsakeskus", "all"):
        targets.extend(METSAKESKUS_WFS_TARGETS)
        targets.extend(METSAKESKUS_WCS_TARGETS)

    if source in ("gtk", "all"):
        targets.extend(GTK_WFS_TARGETS)

    return targets


# --- Orkestrointi ---


async def probe_all(
    source: str = "all",
    timeout: float = DEFAULT_TIMEOUT,
) -> list[ProbeResult]:
    """Mittaa kaikkien kohteiden koot."""
    targets = get_targets(source)
    if not targets:
        logger.warning("[probe] Ei kohteita lähteelle: %s", source)
        return []

    results: list[ProbeResult] = []
    last_request_per_host: dict[str, float] = {}

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for target in targets:
            host = _get_server_host(target.endpoint_url)

            # Rate limiting per host
            now = time.monotonic()
            if host in last_request_per_host:
                elapsed = now - last_request_per_host[host]
                if elapsed < RATE_LIMIT_DELAY:
                    time.sleep(RATE_LIMIT_DELAY - elapsed)

            logger.info("[probe] Mitataan: %s", target.dataset_id)
            try:
                result = await probe_target(client, target, timeout)
                results.append(result)
            except Exception as e:
                logger.error(
                    "[probe] Virhe mitattaessa %s: %s", target.dataset_id, e
                )
                results.append(
                    ProbeResult(
                        dataset_id=target.dataset_id,
                        endpoint_url=target.endpoint_url,
                        current_estimated_bytes=target.current_estimated_bytes,
                        error=str(e),
                    )
                )

            last_request_per_host[host] = time.monotonic()

    return results


# --- Raportti ---


def format_probe_report(results: list[ProbeResult]) -> str:
    """Muotoile mittaustulokset tekstitaulukoksi."""
    if not results:
        return "Ei mittaustuloksia."

    lines: list[str] = []
    header = (
        f"{'Datasetti':<40s} | {'Palvelu':>7s} | {'Featureja':>12s} | "
        f"{'Otos':>10s} | {'Ekstrapoloitu':>13s} | {'Nyk.arvio':>10s} | Suhde"
    )
    lines.append(header)
    lines.append("-" * len(header))

    for r in results:
        url_lower = r.endpoint_url.lower()
        service = "WFS" if "wfs" in url_lower or "ows" in url_lower else "WCS"
        # Tunnista palvelutyyppi targeteista
        for targets in (
            METSAKESKUS_WFS_TARGETS,
            GTK_WFS_TARGETS,
        ):
            if any(t.dataset_id == r.dataset_id for t in targets):
                service = "WFS"
                break
        for targets in (METSAKESKUS_WCS_TARGETS,):
            if any(t.dataset_id == r.dataset_id for t in targets):
                service = "WCS"
                break

        features_str = (
            f"{r.total_feature_count:>12,}" if r.total_feature_count else "—".rjust(12)
        )
        sample_str = _format_bytes(r.sample_bytes).rjust(10)
        extrap_str = (
            _format_bytes(r.extrapolated_size_bytes).rjust(13)
            if r.extrapolated_size_bytes
            else "—".rjust(13)
        )
        current_str = _format_bytes(r.current_estimated_bytes).rjust(10)

        if r.extrapolated_size_bytes and r.current_estimated_bytes:
            ratio = r.extrapolated_size_bytes / r.current_estimated_bytes
            ratio_str = f"{ratio:.2f}×"
        else:
            ratio_str = "—"

        if r.error:
            extrap_str = f"VIRHE: {r.error[:30]}".rjust(13)
            ratio_str = "—"

        lines.append(
            f"{r.dataset_id:<40s} | {service:>7s} | {features_str} | "
            f"{sample_str} | {extrap_str} | {current_str} | {ratio_str}"
        )

    return "\n".join(lines)
