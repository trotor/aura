"""Resurssin formaatin päättely URL:sta, kun katalogi jättää sen tyhjäksi.

Ulkoinen arvio 27.9.2026: SYKE:n 1 257 resurssista 511:llä formaatti on
tyhjä, ja niistä 75 on WFS-palveluita (``.../geoserver/<työtila>/wfs``).
Tyhjä formaatti ei ole kyseltävä, joten ``query_source`` vastasi
"formaattia '?' ei voi kysellä" aineistolle jonka WFS-rajapinta oli
resurssilistalla näkyvissä.

**Säännöt ovat kapeita.** Päättely osuu vain URL-muotoihin jotka eivät voi
tarkoittaa muuta: polun viimeinen osa on ``wfs``/``wms`` tai kysely kertoo
``service=WFS``, tai tiedostopääte on yksiselitteinen. Muuten palautetaan
tyhjä, eikä arvata — väärä formaatti ohjaisi kyselyn protokollalle joka
epäonnistuu selittämättä, mikä on pahempi kuin rehellinen "ei tiedossa".
Katalogin oma formaatti voittaa aina: tätä käytetään vain kun se puuttuu.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from typing import Any

#: Tiedostopääte → formaatti. Pidempi pääte ensin (``.geojson`` ennen ``.json``).
_EXTENSIONS: tuple[tuple[str, str], ...] = (
    (".geojson", "GEOJSON"),
    (".json", "JSON"),
    (".csv", "CSV"),
    (".xlsx", "XLSX"),
    (".xls", "XLS"),
    (".zip", "ZIP"),
)

#: OGC-palvelut joiden nimi voi olla polun viimeinen osa tai ``service``-arvo.
_SERVICES = ("WFS", "WMS")


def infer_format(url: str) -> str:
    """Päättele formaatti URL:sta, tai palauta tyhjä jos se ei ole yksiselitteinen.

    >>> infer_format("https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs")
    'WFS'
    >>> infer_format("https://x.fi/ows?SERVICE=WMS&request=GetCapabilities")
    'WMS'
    >>> infer_format("https://x.fi/data/tilasto.csv")
    'CSV'
    >>> infer_format("https://www.syke.fi/avointieto")
    ''
    """
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url.strip())
    query = {k.lower(): v for k, v in urllib.parse.parse_qsl(parts.query)}
    service = query.get("service", "").upper()
    if service in _SERVICES:
        return service
    path = parts.path.rstrip("/").lower()
    last = path.rsplit("/", 1)[-1]
    if last.upper() in _SERVICES:
        return last.upper()
    for ext, fmt in _EXTENSIONS:
        if last.endswith(ext):
            return fmt
    return ""


def resource_format(resource: Mapping[str, Any]) -> str:
    """Resurssin formaatti isoin kirjaimin: katalogin oma, muuten URL:sta päätelty."""
    own = str(resource.get("format") or "").strip().upper()
    return own or infer_format(str(resource.get("url") or ""))
