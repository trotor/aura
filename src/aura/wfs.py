"""WFS-protokollan tulkinta: kyvyt, virheet ja GML.

Erillinen moduuli siksi, että WFS-palvelimet eroavat toisistaan enemmän kuin
yhteinen standardi antaa ymmärtää, ja erot on käsiteltävä yhdessä paikassa.
GeoServer vastaa ``outputFormat=application/json``-pyyntöön GeoJSONilla ja
suostuu palauttamaan kohteita ilman ``typeNames``-parametria. ArcGIS Server
ei tee kumpaakaan: se hylkää MIME-merkkijonon (oma nimi on ``GEOJSON``) ja
vaatii kerroksen nimen aina.

Pahin yksityiskohta on että molemmat kieltäytymiset tulevat **HTTP 200:lla**
XML-muotoisena ExceptionReportina. Statuskoodi ei siis kerro virheestä
mitään, ja JSON-jäsennin kaatuu vastaukseen jonka palvelin piti onnistuneena.

``fetch_features`` hoitaa neuvottelun: ensin optimistinen JSON-pyyntö, ja
vasta jos vastaus ei ole JSONia, kysytään kyvyt ja yritetään uudelleen niillä.
Nopea polku pysyy siis yhtenä kutsuna niille palveluille jotka toimivat
suoraan — eli valtaosalle.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx

from aura.constants import user_agent

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0

#: Yläraja jäsennettävälle XML:lle. Vastaus tulee vieraalta palvelimelta,
#: ja ElementTree laajentaa entiteetit — rajaton syöte olisi rajaton työ.
_MAX_XML_BYTES = 4_194_304  # 4 MB

#: Formaatit joiden vastaus on JSONia, parhausjärjestyksessä. Vertailu on
#: tarkka: 'GEOJSON+ZIP' sisältää sanan mutta on zip-tiedosto.
JSON_OUTPUT_FORMATS = ("application/json", "geojson", "json")

#: GML-vastauksen kääre-elementit, joiden alta varsinainen kohde löytyy.
_MEMBER_TAGS = ("member", "featureMember", "featureMembers")

#: Elementit joita ei näytetä taulukossa: geometria on koordinaattilista,
#: joka veisi koko rivin eikä kerro ihmiselle mitään.
_GEOMETRY_HINTS = ("shape", "geometry", "the_geom", "geom", "boundedby")


@dataclass(frozen=True)
class Capabilities:
    """GetCapabilities-vastauksesta luetut kyvyt."""

    feature_types: list[str] = field(default_factory=list)
    output_formats: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    """Elementin nimi ilman nimiavaruutta."""
    return tag.rsplit("}", 1)[-1]


def _root(body: str) -> ET.Element | None:
    """Jäsennä XML, tai None jos vastaus ei ole XML:ää lainkaan."""
    if not body or not body.lstrip().startswith("<"):
        return None
    if len(body) > _MAX_XML_BYTES:
        logger.warning("WFS-vastaus liian suuri jäsennettäväksi: %d tavua", len(body))
        return None
    try:
        return ET.fromstring(body)
    except ET.ParseError:
        return None


#: Virhevastauksen juurielementti -> (tekstin kantava tagi, koodin
#: attribuutin nimi). OWS-muoto (WFS, GeoServer) kääri viestin omaan
#: ``ExceptionText``-lapsielementtiinsä ``Exception``-elementin sisällä.
#: WMS:n vanhempi ``ServiceExceptionReport``-muoto ei kääri: viesti on
#: suoraan ``ServiceException``-elementin tekstinä, ja koodi on sen omassa
#: ``code``-attribuutissa eikä ``exceptionCode``-attribuutissa.
_EXCEPTION_SHAPES = {
    "ExceptionReport": ("ExceptionText", "Exception", "exceptionCode"),
    "ServiceExceptionReport": ("ServiceException", "ServiceException", "code"),
}


def exception_text(body: str) -> str | None:
    """Palauta palvelimen virheteksti, tai None jos vastaus ei ole virhe.

    Tämä on ainoa tapa erottaa virhe datasta: statuskoodi on 200 myös
    silloin kun palvelin kieltäytyi. Kaksi eri virhemuotoa tunnistetaan,
    koska WMS-palvelimet käyttävät eri kääretasoa kuin WFS/GeoServer —
    ks. ``_EXCEPTION_SHAPES``.
    """
    root = _root(body)
    if root is None:
        return None
    shape = _EXCEPTION_SHAPES.get(_local(root.tag))
    if shape is None:
        return None
    text_tag, code_tag, code_attr = shape
    texts = [
        (el.text or "").strip()
        for el in root.iter()
        if _local(el.tag) == text_tag and (el.text or "").strip()
    ]
    if texts:
        return " ".join(texts)
    # Jotkin palvelimet jättävät tekstin pois ja kertovat syyn koodissa.
    codes = [
        el.get(code_attr, "")
        for el in root.iter()
        if _local(el.tag) == code_tag
    ]
    return " ".join(c for c in codes if c) or "Tuntematon WFS-virhe."


def parse_capabilities(body: str) -> Capabilities:
    """Lue featuretyypit ja GetFeaturen tukemat outputFormatit.

    Formaatit luetaan nimenomaan GetFeature-operaatiolta. Sama parametri on
    myös DescribeFeatureTypellä, joka mainostaa vain GML:ää — väärästä
    lohkosta luettuna palvelu näyttäisi siltä ettei se tue JSONia lainkaan.
    """
    root = _root(body)
    if root is None:
        return Capabilities()

    # Vain FeatureTypen oma nimi: pelkkä "Name"-haku osuisi myös palvelun
    # kuvailuun ja yhteystietoihin.
    feature_types = [
        (name.text or "").strip()
        for ft in root.iter()
        if _local(ft.tag) == "FeatureType"
        for name in ft
        if _local(name.tag) == "Name" and (name.text or "").strip()
    ]

    output_formats: list[str] = []
    for op in root.iter():
        if _local(op.tag) != "Operation" or op.get("name") != "GetFeature":
            continue
        for par in op.iter():
            if _local(par.tag) != "Parameter":
                continue
            if (par.get("name") or "").lower() != "outputformat":
                continue
            output_formats.extend(
                (v.text or "").strip()
                for v in par.iter()
                if _local(v.tag) == "Value" and (v.text or "").strip()
            )

    return Capabilities(feature_types=feature_types, output_formats=output_formats)


def pick_output_format(formats: list[str]) -> str | None:
    """Valitse JSONia palauttava outputFormat, tai None jos sellaista ei ole."""
    by_lower = {f.lower(): f for f in formats}
    for candidate in JSON_OUTPUT_FORMATS:
        if candidate in by_lower:
            return by_lower[candidate]
    return None


def _feature_elements(root: ET.Element) -> list[ET.Element]:
    """Kohde-elementit GML-vastauksesta kääreiden alta."""
    features: list[ET.Element] = []
    for el in root.iter():
        if _local(el.tag) not in _MEMBER_TAGS:
            continue
        for child in el:
            # featureMembers-kääre sisältää kohteet suoraan, member yhden.
            features.append(child)
    return features


def _is_geometry(el: ET.Element) -> bool:
    """Onko elementti geometria — joko nimensä tai lapsiensa perusteella."""
    if _local(el.tag).lower() in _GEOMETRY_HINTS:
        return True
    return any("/gml" in (child.tag or "") for child in el)


def parse_gml(body: str, max_rows: int) -> tuple[list[str], list[list[str]]]:
    """Poimi GML-vastauksesta ominaisuudet taulukoksi.

    Tarkoitus on esikatselu, ei täydellinen GML-tuki: geometria jätetään
    pois, koska koordinaattilista täyttäisi rivin eikä kertoisi lukijalle
    mitä aineisto sisältää.
    """
    root = _root(body)
    if root is None:
        return [], []

    headers: list[str] = []
    rows: list[list[str]] = []
    for feature in _feature_elements(root)[:max_rows]:
        values: dict[str, str] = {}
        for prop in feature:
            if _is_geometry(prop):
                continue
            name = _local(prop.tag)
            values[name] = (prop.text or "").strip()
            if name not in headers:
                headers.append(name)
        rows.append([values.get(h, "") for h in headers])

    # Ensimmäiset rivit rakennettiin ennen kuin kaikki sarakkeet tunnettiin.
    return headers, [row + [""] * (len(headers) - len(row)) for row in rows]


def reported_total(body: str) -> str | None:
    """Kohteiden kokonaismäärä GML-vastauksen juurielementistä."""
    root = _root(body)
    if root is None:
        return None
    for attr in ("numberMatched", "numberOfFeatures"):
        value = root.get(attr)
        if value and value.isdigit():
            return value
    return None


def request_params(
    url: str,
    max_rows: int,
    bbox: str | None = None,
    type_name: str | None = None,
    output_format: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Rakenna WFS GetFeature -pyyntö säilyttäen kerroksen nimi URL:sta.

    Resurssin URL on useimmiten GetCapabilities-osoite, jonka query-osa on
    turha — mutta osassa lähteitä se kantaa myös ``typeName``-parametrin.
    Jos se pudotetaan, palvelin vastaa "The query should specify either
    typeName..." eikä virheestä näe että kerros katosi kyselyä
    rakennettaessa. Siksi kerroksen nimi poimitaan talteen, ja vain jos sitä
    ei ole, käytetään kyvyistä löytynyttä ``type_name``-arvoa.
    """
    base_url = url.split("?")[0]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "outputFormat": output_format or "application/json",
        "count": str(max_rows),
    }

    query = urllib.parse.urlparse(url).query
    from_url = False
    for key, values in urllib.parse.parse_qs(query).items():
        if key.lower() in ("typename", "typenames") and values:
            params[key] = values[0]
            from_url = True
    if type_name and not from_url:
        params["typeNames"] = type_name
    if bbox:
        params["bbox"] = bbox

    return base_url, params


@dataclass(frozen=True)
class Features:
    """Yhdestä GetFeature-kutsusta luettu tulos, formaatista riippumatta."""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    #: Kohteiden kokonaismäärä palvelussa, tai None jos palvelu ei kertonut.
    #: Rivimäärällä korvattuna luku väittäisi aineiston olevan sen kokoinen
    #: kuin esikatselu sattui pyytämään.
    total: str | None = None
    geometry_name: str | None = None
    output_format: str = ""
    error: str | None = None


def _from_geojson(data: dict[str, Any], max_rows: int) -> Features:
    features = data.get("features", [])
    props = [f.get("properties", {}) or {} for f in features[:max_rows]]
    headers = list(props[0].keys()) if props else []
    rows = [[str(p.get(h, "")) for h in headers] for p in props]
    geometry_name = next(
        (f.get("geometry_name") for f in features if f.get("geometry_name")), None
    )
    reported = data.get("totalFeatures", data.get("numberMatched"))
    return Features(
        headers=headers,
        rows=rows,
        total=str(reported) if reported is not None else None,
        geometry_name=geometry_name,
        output_format="json",
    )


def _read_body(body: str, max_rows: int) -> Features | None:
    """Tulkitse vastaus, tai None jos se ei ole kohteita eikä virhe.

    Järjestys on tärkeä: virhe on tunnistettava ennen jäsennysyritystä.
    Aiemmin JSON-jäsennin ajettiin suoraan vastaukseen, ja ExceptionReport
    tuotti viestin "Expecting value: line 2 column 1" — joka ei kerro
    lukijalle mitään siitä mitä palvelin oikeasti sanoi.
    """
    stripped = body.lstrip()
    if stripped.startswith("{"):
        try:
            return _from_geojson(json.loads(body), max_rows)
        except (json.JSONDecodeError, ValueError):
            return None

    error = exception_text(body)
    if error:
        return Features(error=error)

    headers, rows = parse_gml(body, max_rows)
    if headers or rows:
        return Features(
            headers=headers,
            rows=rows,
            total=reported_total(body),
            output_format="gml",
        )
    return None


async def fetch_features(
    url: str,
    max_rows: int,
    *,
    bbox: str | None = None,
    cql_filter: str | None = None,
    timeout: float = _TIMEOUT,
) -> Features:
    """Hae kohteita WFS-palvelusta, neuvotellen tarvittaessa.

    Ensimmäinen yritys on optimistinen: ``application/json`` ja URL:n oma
    kerros. Se riittää GeoServerille eli valtaosalle, eikä maksa
    ylimääräistä kutsua. Jos vastaus ei ole kohteita, kysytään kyvyt ja
    yritetään uudelleen niillä — ArcGIS Server vaatii sekä oman
    formaattinimensä (``GEOJSON``) että ``typeNames``-parametrin, ja
    kieltäytyy molemmista puutteista HTTP 200:lla.
    """
    base_url, params = request_params(url, max_rows, bbox=bbox)
    if cql_filter:
        params["CQL_FILTER"] = cql_filter

    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": user_agent()}
    ) as client:
        resp = await client.get(base_url, params=params, follow_redirects=True)
        resp.raise_for_status()
        result = _read_body(resp.text, max_rows)
        if result is not None and result.error is None:
            return result
        first_error = result.error if result else None

        # Neuvottelu: kysy mitä palvelu oikeasti tukee. Jos kyvyt eivät
        # vastaa, alkuperäinen virhe on silti paras tieto käyttäjälle —
        # neuvottelun oma virhe peittäisi sen syyn jota oltiin selvittämässä.
        try:
            caps_resp = await client.get(
                base_url,
                params={
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetCapabilities",
                },
                follow_redirects=True,
            )
            caps_resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.debug("WFS GetCapabilities epäonnistui: %s", e)
            return Features(error=first_error or f"Palvelu ei vastannut: {e}")
        caps = parse_capabilities(caps_resp.text)

        output_format = pick_output_format(caps.output_formats)
        type_name = caps.feature_types[0] if caps.feature_types else None
        if output_format is None and type_name is None:
            return Features(error=first_error or "Palvelu ei kertonut kyvyistään.")

        # Ilman JSON-formaattia otetaan palvelun ensimmäinen tarjoama, joka
        # on käytännössä GML — se osataan jäsentää.
        retry_format = output_format or (
            caps.output_formats[0] if caps.output_formats else None
        )
        base_url, params = request_params(
            url,
            max_rows,
            bbox=bbox,
            type_name=type_name,
            output_format=retry_format,
        )
        if cql_filter:
            params["CQL_FILTER"] = cql_filter

        try:
            retry = await client.get(base_url, params=params, follow_redirects=True)
            retry.raise_for_status()
        except httpx.HTTPError as e:
            logger.debug("WFS-uusintayritys epäonnistui: %s", e)
            return Features(error=first_error or f"Palvelu ei vastannut: {e}")
        result = _read_body(retry.text, max_rows)

    if result is None:
        return Features(error=first_error or "Vastausta ei osattu tulkita.")
    if result.error and first_error and result.error != first_error:
        return Features(error=f"{first_error} | {result.error}")
    return result
