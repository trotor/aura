"""WFS-prober: sarakkeet, tyypit ja koordinaatisto kyvyistä.

DescribeFeatureType antaa tyypitetyt sarakkeet sekä ArcGIS- että
GeoServer-palvelimilla, mutta eri nimiavaruusprefiksillä (``xsd:`` / ``xs:``).
Siksi jäsennys tehdään prefiksistä riippumatta.
"""

from __future__ import annotations

from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus
from aura.wfs import _local, _root, exception_text, parse_capabilities, request_params

#: XSD-perustyypit Auran tyyppinimiksi. Tuntematon tyyppi on "string":
#: väärä arvaus olisi pahempi kuin yleisin oikea.
_XSD_TYPES = {
    "int": "integer", "integer": "integer", "long": "integer", "short": "integer",
    "double": "float", "float": "float", "decimal": "float",
    "date": "date", "dateTime": "date",
    "boolean": "boolean",
}


def parse_feature_types(body: str) -> list[tuple[str, str]]:
    """Poimi DescribeFeatureType-vastauksesta sarakkeet ja tyypit.

    Geometriakenttä (``gml:*PropertyType``) merkitään tyypillä "geometry"
    eikä pudoteta: sen olemassaolo kertoo että aineisto on paikkatietoa,
    vaikka koordinaattilista itsessään ei kuulu sarakelistaan.
    """
    root = _root(body)
    if root is None:
        return []

    fields: list[tuple[str, str]] = []
    for el in root.iter():
        if _local(el.tag) != "element":
            continue
        name = el.get("name")
        raw_type = el.get("type") or ""
        if not name or not raw_type:
            continue
        if raw_type.startswith("gml:"):
            fields.append((name, "geometry"))
            continue
        # Ylin element on featuretyyppi itse, ei sarake: sen type-attribuutti
        # viittaa complexTypeen jonka nimi päättyy "Type" (ArcGIS: "...FeatureType",
        # GeoServer: "...Type"). XSD-perustyypit eivät koskaan pääty "Type".
        if raw_type.endswith("Type"):
            continue
        local_type = raw_type.split(":")[-1]
        fields.append((name, _XSD_TYPES.get(local_type, "string")))
    return fields


async def probe(
    resource: dict[str, Any], client: httpx.AsyncClient
) -> ProbeResult:
    """Hae WFS-resurssin skeema, koordinaatisto ja toimiva esimerkkikutsu."""
    url = resource.get("url", "")
    base_url = url.split("?")[0]
    caps_params = {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"}

    try:
        caps_resp = await client.get(base_url, params=caps_params, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="GetCapabilities")
    if caps_resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {caps_resp.status_code}",
            http_status=caps_resp.status_code,
        )

    caps = parse_capabilities(caps_resp.text)
    if not caps.feature_types:
        virhe = exception_text(caps_resp.text) or "GetCapabilities ei sisältänyt featuretyyppejä"
        return ProbeResult(
            status=ProbeStatus.PARSE_ERROR, detail=virhe, http_status=caps_resp.status_code
        )

    type_name = caps.feature_types[0]
    dft_params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "DescribeFeatureType",
        "typeNames": type_name,
    }
    try:
        dft_resp = await client.get(base_url, params=dft_params, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="DescribeFeatureType")
    if dft_resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {dft_resp.status_code}",
            http_status=dft_resp.status_code,
        )

    fields = parse_feature_types(dft_resp.text)
    if not fields:
        virhe = exception_text(dft_resp.text) or "DescribeFeatureType ei sisältänyt kenttiä"
        return ProbeResult(
            status=ProbeStatus.EMPTY, detail=virhe, http_status=dft_resp.status_code
        )

    enrichments: list[tuple[str, str]] = []
    crs = _default_crs(caps_resp.text, type_name)
    if crs:
        enrichments.append(("crs", crs))

    _base, params = request_params(url, 20, type_name=type_name)
    example = base_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    enrichments.append(("example_request", example))

    return ProbeResult(
        status=ProbeStatus.OK,
        fields=fields,
        enrichments=enrichments,
        http_status=dft_resp.status_code,
    )


def _default_crs(caps_body: str, type_name: str) -> str:
    """Featuretyypin DefaultCRS GetCapabilities-vastauksesta."""
    root = _root(caps_body)
    if root is None:
        return ""
    for ft in root.iter():
        if _local(ft.tag) != "FeatureType":
            continue
        nimi = next(
            (c.text or "" for c in ft if _local(c.tag) == "Name"), ""
        ).strip()
        if nimi != type_name:
            continue
        for c in ft:
            if _local(c.tag) in ("DefaultCRS", "DefaultSRS"):
                return (c.text or "").strip()
    return ""
