"""Kiinteistötunnus aluerajauksena.

Kiinteistötunnus (14 numeroa: kunta 3, sijaintialue 3, ryhmä 4, yksikkö 4)
muutetaan kiinteistön palstojen rajoiksi, joilla rajataan WFS-kysely:
"mitä puustoa tilalla 174-401-3-6 on?" → Metsäkeskuksen kuviot palstoilta.

Rajojen lähteet, järjestyksessä:

1. Paikallinen indeksi (``aura.kiinteisto_index``): MML:n
   kiinteistörekisterikartta Kapsi.fi:n peilistä, ladattu kunnittain
   komennolla ``aura parcels <kunta>``. Koko Suomi, ei API-avainta.
2. Kunnan oma avoin WFS (``MUNICIPAL``) — ei latausta, mutta vain kyseinen
   kunta ja sen ylläpitämät (asemakaava-alueiden) kiinteistöt.

MML:n omat rajapinnat (kiinteistöt ja tiedostopalvelu) vaativat
API-avaimen; Kapsin peili jakaa saman avoimen aineiston (CC BY 4.0) ilman.
Palveluiden sisäisiä reittejä ei käytetä, koska ne eivät ole hyväksyttyjä
rajapintoja.

Omistajatietoja ei haeta. Henkilön omistaman kiinteistön tunnus on silti
henkilötieto, joten tunnusta ei kirjata vastauksen ulkopuolelle.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

import httpx

from aura.constants import user_agent
from aura.net import read_capped

#: 14-numeroinen muoto tai neljä numeroryhmää viivoin tai välilyönnein.
_DIGITS = re.compile(r"^\d{14}$", re.ASCII)
_GROUPS = re.compile(r"^(\d{1,3})[-\s](\d{1,3})[-\s](\d{1,4})[-\s](\d{1,4})$", re.ASCII)
#: Määräala: tunnuksen perässä "-M601". Määräala on kiinteistön osa, jolla ei
#: ole omia rajoja kiinteistörekisterikartalla samalla tavalla.
_MAARAALA = re.compile(r"^[\d\s-]+-M\d+$", re.IGNORECASE | re.ASCII)

_TIMEOUT = 30.0
_LIMIT = 20 * 1024 * 1024


def index_hint(tunnus: str) -> str:
    """Ohje kun rajoja ei ole: lataa kunnan kiinteistöt paikalliseen indeksiin."""
    kunta = tunnus[:3]
    return (
        f"Paikallisessa Aurassa: lataa kunnan {kunta} kiinteistörajat indeksiin komennolla "
        f"`aura parcels {kunta}` (MML:n avoin kiinteistörekisterikartta Kapsi.fi:n "
        "peilistä, ei API-avainta; kestää kunnan koosta riippuen sekunneista minuutteihin)."
    )


def parse_tunnus(text: str) -> str | None:
    """Kiinteistötunnus 14-numeroisena, tai None jos teksti ei ole tunnus.

    Hyväksyy muodot ``17440100030006``, ``174-401-3-6`` ja
    ``092-072-0032-0006``. Nostaa ``ValueError``in määräalasta, jotta käyttäjä
    saa syyn eikä "aluetta ei tunnistettu" -virhettä.
    """
    value = text.strip()
    if _MAARAALA.match(value):
        raise ValueError(
            f"'{value}' on määräalan tunnus. Määräalalla ei ole omia rajoja "
            "kiinteistörajapinnoissa; anna sen kiinteistön tunnus (ilman M-osaa)."
        )
    if _DIGITS.match(value):
        return value
    match = _GROUPS.match(value)
    if match is None:
        return None
    kunta, alue, ryhma, yksikko = match.groups()
    return f"{int(kunta):03d}{int(alue):03d}{int(ryhma):04d}{int(yksikko):04d}"


def format_tunnus(tunnus: str) -> str:
    """Lyhyt näyttömuoto: ``17440100030006`` → ``174-401-3-6``."""
    parts = (tunnus[:3], tunnus[3:6], tunnus[6:10], tunnus[10:14])
    return "-".join(str(int(p)) for p in parts)


Bbox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Parcel:
    """Yksi kiinteistön palsta: rajaava suorakaide EPSG:3067:ssä."""

    bbox: Bbox


@dataclass
class Lookup:
    """Rajojen haun tulos. ``provider`` on None, jos lähdettä ei ollut."""

    tunnus: str
    provider: str | None
    parcels: list[Parcel] = field(default_factory=list)
    #: Miten edetä, kun rajoja ei saatu (avaimen hankinta tms.).
    hint: str = ""
    error: str = ""
    #: Huomautus vastaukseen, esim. kunnan rajojen ensimmäinen lataus.
    note: str = ""


@dataclass(frozen=True)
class MunicipalWfs:
    """Kunnan avoin WFS, jossa kiinteistöt ovat alueina tunnuksineen."""

    name: str
    url: str
    layer: str
    field: str


#: Kuntakoodi → kunnan oma avoin kiinteistörajapinta. Vain palvelut joissa
#: kohde on kiinteistön alue (ei esim. rakennus) ja tunnus 14-numeroisena.
MUNICIPAL: dict[str, MunicipalWfs] = {
    "091": MunicipalWfs(
        name="Helsingin kaupunki (kartta.hel.fi)",
        url="https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
        layer="avoindata:Kiinteisto_alue",
        field="kiinteistotunnus",
    ),
}


def _bbox(coords: Any) -> Bbox | None:
    """GeoJSON-geometrian koordinaattien rajaava suorakaide."""
    xs: list[float] = []
    ys: list[float] = []

    def walk(node: Any) -> None:
        if (
            isinstance(node, list)
            and len(node) >= 2
            and all(isinstance(v, int | float) for v in node[:2])
        ):
            xs.append(float(node[0]))
            ys.append(float(node[1]))
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(coords)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


async def _municipal(
    tunnus: str, service: MunicipalWfs, transport: httpx.AsyncBaseTransport | None
) -> Lookup:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": service.layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:3067",
        "CQL_FILTER": f"{service.field}='{tunnus}'",
    }
    # Osoite on kiinteä konfiguraatio eikä käyttäjän tai katalogin antama,
    # joten public_clientin julkisuustarkistusta ei tarvita.
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": user_agent()}, transport=transport
    ) as client:
        response, body = await read_capped(client, service.url, limit=_LIMIT, params=params)
    response.raise_for_status()
    data = json.loads(body)
    parcels = []
    for feature in data.get("features", []):
        box = _bbox((feature.get("geometry") or {}).get("coordinates"))
        if box is not None:
            parcels.append(Parcel(bbox=box))
    return Lookup(tunnus=tunnus, provider=service.name, parcels=parcels)


#: Yksi kunta kerrallaan: samanaikaiset kyselyt samasta kunnasta eivät lataa
#: sitä kahdesti, eikä julkinen palvelin kuormita peiliä rinnakkain.
_LOAD_LOCK = asyncio.Lock()


def _auto_load_enabled() -> bool:
    """Ladataanko puuttuva kunta ensimmäisellä kyselyllä (oletus kyllä)."""
    return os.environ.get("AURA_KIINTEISTOT_AUTO", "1") != "0"


def _successor(conn: sqlite3.Connection, code: str) -> str:
    """Kuntakoodi, jonka rajoilla ladataan: lakkautettu kunta → seuraaja."""
    from aura.areas import resolve_area

    match = resolve_area(conn, code)
    if match is not None and match.area.level == "kunta":
        return match.area.code
    return code


async def _auto_load(conn: sqlite3.Connection, kunta: str) -> tuple[int | None, str]:
    """Lataa kunnan palstat indeksiin. Palauttaa (palstoja, virhe)."""
    from aura import kiinteisto_index

    async with _LOAD_LOCK:
        if kiinteisto_index.loaded(kiinteisto_index.index_path(), kunta):
            return 0, ""  # toinen kysely ehti ladata
        target = _successor(conn, kunta)
        aliases = (kunta,) if target != kunta else ()
        try:
            summary = await kiinteisto_index.load_municipality(conn, target, aliases=aliases)
        except (OSError, sqlite3.Error, httpx.HTTPError, ValueError) as exc:
            return None, f"Kiinteistörajojen lataus epäonnistui: {type(exc).__name__}"
    return summary.parcels, ""


async def find_parcels(
    tunnus: str,
    *,
    conn: sqlite3.Connection | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Lookup:
    """Kiinteistön palstat. Tyhjä ``parcels`` + ``hint`` kun lähdettä ei ole.

    Järjestys: paikallinen indeksi, kunnan oma WFS ja lopuksi kunnan lataus
    indeksiin (vain kun ``conn`` on annettu ja ``AURA_KIINTEISTOT_AUTO`` ei
    ole ``0``). Lataus kestää kunnan koosta riippuen sekunneista minuuttiin,
    ja se tehdään kerran kuntaa kohden.
    """
    from aura import kiinteisto_index

    path = kiinteisto_index.index_path()
    provider = kiinteisto_index.PROVIDER
    parcels = kiinteisto_index.lookup(path, tunnus)
    if parcels:
        return Lookup(tunnus=tunnus, provider=provider, parcels=parcels)

    kunta = tunnus[:3]
    service = MUNICIPAL.get(kunta)
    municipal_error = ""
    if service is not None:
        try:
            result = await _municipal(tunnus, service, transport)
        except (httpx.HTTPError, ValueError) as exc:
            municipal_error = f"{service.name} ei vastannut: {type(exc).__name__}"
        else:
            if result.parcels or conn is None or not _auto_load_enabled():
                result.hint = result.hint or index_hint(tunnus)
                return result

    if kiinteisto_index.loaded(path, kunta):
        # Kunta on ladattu, mutta tunnusta ei ole: tunnus on väärä tai lakannut.
        return Lookup(tunnus=tunnus, provider=provider)
    if conn is None or not _auto_load_enabled():
        return Lookup(
            tunnus=tunnus,
            provider=service.name if service and municipal_error else None,
            error=municipal_error,
            hint=index_hint(tunnus),
        )

    count, error = await _auto_load(conn, kunta)
    if count is None:
        return Lookup(tunnus=tunnus, provider=None, error=error, hint=index_hint(tunnus))
    note = (
        f"Kunnan {kunta} kiinteistörajat ladattiin indeksiin ensimmäistä kertaa "
        f"({count} palstaa)."
        if count
        else ""
    )
    return Lookup(
        tunnus=tunnus,
        provider=provider,
        parcels=kiinteisto_index.lookup(path, tunnus),
        note=note,
    )
