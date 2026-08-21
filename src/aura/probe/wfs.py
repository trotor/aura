"""WFS-prober: sarakkeet, tyypit ja koordinaatisto kyvyistä.

DescribeFeatureType antaa tyypitetyt sarakkeet sekä ArcGIS- että
GeoServer-palvelimilla, mutta rakenne eroaa yksityiskohdissa jotka
nimestä ei näe: ArcGIS jättää ``type``-attribuutin merkkijonokentistä
kokonaan pois ja ilmaisee tyypin sisäkkäisellä rajoituksella, ja
GeoServer nimeää featuretyypin kääre-complexTypen samalla ``...Type``-
päätteellä jota käytetään myös aidoissa nimetyissä sarake-tyypeissä
(esim. INSPIRE-koodistokentät kuten ``ns:TilaType``). Siksi sarake
erotetaan kääre-elementistä sijainnin perusteella: sarake on aina
``xsd:sequence``:n sisällä, kääre-elementti on ``xsd:schema``:n suora
lapsi.
"""

from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus
from aura.wfs import (
    _local,
    _root,
    exception_text,
    parse_capabilities,
    pick_output_format,
    request_params,
)

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

    Vain ``xsd:sequence``-lohkon sisällä olevat elementit ovat sarakkeita.
    Featuretyypin oma kääre-elementti on ``xsd:schema``:n suora lapsi eikä
    koskaan minkään sequence-lohkon sisällä — tämä rakenteellinen sijainti
    erottaa sen luotettavasti, kun taas nimi (``...Type``/``...FeatureType``)
    ei: GeoServer nimeää kääretyypin samalla kaavalla kuin aito nimetty
    sarake-tyyppi (esim. INSPIRE-koodistokenttä ``ns:TilaType``).

    Geometriakenttä (``gml:*PropertyType``) merkitään tyypillä "geometry"
    eikä pudoteta: sen olemassaolo kertoo että aineisto on paikkatietoa,
    vaikka koordinaattilista itsessään ei kuulu sarakelistaan.

    ``typeNames``-parametri voi pyytää useamman feature typen kerralla
    (esim. Lounaistiedon ``hame_keski_suomi``), jolloin vastaus sisältää
    oman ``complexType``/``sequence``-lohkon jokaiselle tyypille. Eri
    feature typeillä on aidosti usein samannimisiä attribuutteja (``nimi``,
    ``kunta``, ``id``) — se ei ole datavirhe, vaan yleistä kun useampi
    kerros jakaa yhteisen attribuuttimallin. ``resource_schema``-taulu on
    kuitenkin resurssikohtainen, ei feature type -kohtainen (avain on
    ``resource_id + field_name``), joten sama nimi kelpaa vain kerran:
    ensimmäinen esiintymä voittaa. Tämä dedup kuuluu tänne eikä
    tietokantakerrokseen, koska vain prober tietää että toisto tässä on
    odotettua eikä merkki rikkinäisestä vastauksesta.
    """
    root = _root(body)
    if root is None:
        return []

    fields: list[tuple[str, str]] = []
    seen: set[str] = set()
    for seq in root.iter():
        if _local(seq.tag) != "sequence":
            continue
        for el in seq:
            if _local(el.tag) != "element":
                continue
            name = el.get("name")
            if not name or name in seen:
                continue
            fields.append((name, _field_type(el)))
            seen.add(name)
    return fields


def _field_type(el: ET.Element) -> str:
    """Sarakkeen Aura-tyyppi elementin ``type``-attribuutista.

    ArcGIS jättää ``type``-attribuutin pois merkkijonokentistä ja ilmaisee
    tyypin sisäkkäisellä ``<xsd:simpleType><xsd:restriction base="..."/>``
    -rakenteella. Ilman tätä katsantoa nuo kentät katoaisivat äänettömästi,
    vaikka niillä on ``name``.
    """
    raw_type = el.get("type") or _restriction_base(el) or ""
    if raw_type.startswith("gml:"):
        return "geometry"
    local_type = raw_type.split(":")[-1]
    return _XSD_TYPES.get(local_type, "string")


def _restriction_base(el: ET.Element) -> str | None:
    """Sisäkkäisen ``xsd:simpleType``-rajoituksen ``base``-attribuutti."""
    for child in el.iter():
        if _local(child.tag) == "restriction":
            return child.get("base")
    return None


def _url_type_name(url: str) -> str | None:
    """typeName/typeNames-parametri resurssin URL:sta, jos sellainen on.

    ``aura.wfs.request_params`` tekee saman valinnan GetFeature-kutsulle
    samasta syystä: resurssin URL on usein GetCapabilities-osoite jonka
    query-osa kantaa myös kerroksen nimen. Ilman tätä probe valitsisi
    aina kykyjen ensimmäisen featuretyypin — joka voi olla eri kerros
    kuin se jota resurssi oikeasti kuvaa.
    """
    query = urllib.parse.urlparse(url).query
    for key, values in urllib.parse.parse_qs(query).items():
        if key.lower() in ("typename", "typenames") and values:
            return values[0]
    return None


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
    except httpx.HTTPError as e:
        # ConnectError, SSL- ja DNS-virheet — ei timeout eikä statuskoodi.
        # Ilman tätä ne putoavat run_probe():n yleiseen except Exceptioniin
        # parse_erroriksi ja saavat 30 vrk TTL:n 7:n sijaan.
        return ProbeResult(status=ProbeStatus.HTTP_ERROR, detail=str(e)[:100])
    if caps_resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {caps_resp.status_code}",
            http_status=caps_resp.status_code,
            final_url=str(caps_resp.url),
        )

    caps = parse_capabilities(caps_resp.text)
    if not caps.feature_types:
        virhe = exception_text(caps_resp.text) or "GetCapabilities ei sisältänyt featuretyyppejä"
        return ProbeResult(
            status=ProbeStatus.PARSE_ERROR,
            detail=virhe,
            http_status=caps_resp.status_code,
            final_url=str(caps_resp.url),
        )

    # Resurssin oma typeName voittaa kykyjen ensimmäisen: sama periaate
    # kuin request_params()-funktiossa GetFeature-kutsulle.
    type_name = _url_type_name(url) or caps.feature_types[0]
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
    except httpx.HTTPError as e:
        return ProbeResult(status=ProbeStatus.HTTP_ERROR, detail=str(e)[:100])
    if dft_resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {dft_resp.status_code}",
            http_status=dft_resp.status_code,
            final_url=str(dft_resp.url),
        )

    fields = parse_feature_types(dft_resp.text)
    if not fields:
        virhe = exception_text(dft_resp.text) or "DescribeFeatureType ei sisältänyt kenttiä"
        return ProbeResult(
            status=ProbeStatus.EMPTY,
            detail=virhe,
            http_status=dft_resp.status_code,
            final_url=str(dft_resp.url),
        )

    enrichments: list[tuple[str, str]] = []
    crs = _default_crs(caps_resp.text, type_name)
    if crs:
        enrichments.append(("crs", crs))

    # ArcGIS hylkää oletusarvoisen application/json-arvauksen HTTP 200:lla
    # (ExceptionReport) — se ei tue sitä lainkaan, vain omaa nimeään
    # "GEOJSON" (ks. aura.wfs-moduulin docstring). Julkaistun example_
    # requestin on siis käytettävä palvelun oikeasti kykyjen mukaan
    # tukemaa formaattia, samaan tapaan kuin fetch_features() tekee:
    # ensin JSON-yhteensopiva formaatti, ja jos sellaista ei ole, kykyjen
    # ensimmäinen tarjoama (käytännössä GML, jonka esikatselu osaa lukea).
    output_format = pick_output_format(caps.output_formats) or (
        caps.output_formats[0] if caps.output_formats else None
    )
    _base, params = request_params(
        url, 20, type_name=type_name, output_format=output_format
    )
    # urlencode(), ei käsin f-stringillä liitetty query: outputFormat voi
    # olla esim. "text/xml; subtype=gml/3.2" (GML-fallback-haara) —
    # välilyönti ja puolipiste enkoodaamattomina tuottaisivat kutsun jota
    # mikään palvelin ei hyväksyisi. Julkaistun kutsun PITÄÄ toimia, ei
    # vain näyttää oikealta.
    example = base_url + "?" + urllib.parse.urlencode(params)
    enrichments.append(("example_request", example))

    return ProbeResult(
        status=ProbeStatus.OK,
        fields=fields,
        enrichments=enrichments,
        http_status=dft_resp.status_code,
        final_url=str(dft_resp.url),
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
