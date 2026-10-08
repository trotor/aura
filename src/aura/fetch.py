"""Strukturoitu datakysely: rivit sanakirjoina, ei markdown-taulukkona.

``query_data`` (vanha pinta) palauttaa markdownia, josta agentti joutuu
jäsentämään arvot takaisin. Tämä moduuli palauttaa saman datan
``Table``-rakenteena: sarakkeet, rivit, kokonaismäärä, katkaisu, kyselyn
täsmällinen URL ja muistiinpanot siitä mitä kysely teki käyttäjän puolesta.

Vanha ``query_data`` jätetään ennalleen: se poistuu seuraavassa versiossa,
eikä sen testattua käytöstä kannata muuttaa sen viimeisessä versiossa.

**Mitä tämä tekee toisin kuin query_data:**

- PxWeb: tuntematon suodatinarvo on virhe, ei hiljaa sellaisenaan välitetty
  arvo (joka tuotti HTTP 400:n ilman selitystä). Kuntakoodi ja lakkautetun
  kunnan nimi tulkitaan ``aura.areas``illa. Aikadimensio ymmärtää
  ``"uusin"``/``"latest"`` ja välit ``"2020-2024"``.
- FMI:n tallennetut kyselyt (``storedquery_id``) toimivat. Mitattu
  27.9.2026: yksikään agentti ei saanut säähavaintoa, koska parametri
  pudotettiin pyyntöä rakennettaessa.
- Sotkanet: rivin ``region`` on Sotkanetin oma tunnus, ei kuntakoodi.
  Mitattu samana päivänä: agentti luki Joensuun tunnuksen (74) väärin ja
  raportoi toisen kunnan luvun. Rivit saavat rinnalleen kuntakoodin ja
  -nimen.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import sqlite3
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx

from aura.constants import user_agent
from aura.net import public_client

logger = logging.getLogger(__name__)

TIMEOUT = 30.0
MAX_DOWNLOAD_BYTES = 2_097_152  # 2 MB
MAX_ROWS = 500
DEFAULT_ROWS = 50

#: Kuinka monta arvoa suodattamattomasta aikadimensiosta otetaan.
DEFAULT_TIME_VALUES = 5

_TIME_WORDS = (
    "vuosi",
    "year",
    "kuukausi",
    "month",
    "neljännes",
    "quarter",
    "aika",
    "time",
    "vuosineljännes",
    "päivä",
    "day",
    "viikko",
    "week",
)
_AREA_WORDS = ("alue", "kunta", "region", "area", "maakunta", "municipality")
_LATEST = frozenset({"uusin", "viimeisin", "latest", "last", "newest"})
_RANGE = re.compile(r"^\s*(\d{4})\s*[-–]\s*(\d{4})\s*$")


@dataclass
class Table:
    """Kyselyn tulos protokollasta riippumatta."""

    protocol: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    total: int | None = None
    truncated: bool = False
    request_url: str = ""
    request_body: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    dimensions: list[dict[str, Any]] | None = None
    codes: dict[str, dict[str, str]] | None = None
    error: str | None = None
    error_code: str | None = None
    #: WFS: palvelun kerrokset, jos kerros valittiin palvelun puolesta.
    layers: list[str] | None = None
    #: WFS: kerros jota kysely käytti, jos se tiedetään.
    layer: str | None = None


def _client() -> httpx.AsyncClient:
    # Osoitteet tulevat katalogista eli kolmansilta osapuolilta, ja niiden
    # uudelleenohjaukset voivat osoittaa minne tahansa: vain julkiset kohteet.
    return public_client(
        timeout=TIMEOUT, headers={"User-Agent": user_agent()}, follow_redirects=True
    )


def _num(value: Any) -> Any:
    """Muunna numeerinen merkkijono luvuksi, muut sellaisenaan.

    Etunollallinen kokonaisluku jätetään merkkijonoksi: se on koodi eikä
    luku. Postinumero ``00100`` muuttui muuten luvuksi 100 ja kuntakoodi
    ``091`` luvuksi 91 — ja kumpikaan ei enää osunut omaan suodattimeensa.
    """
    if isinstance(value, str):
        v = value.strip()
        if re.fullmatch(r"0\d+", v):
            return value
        if re.fullmatch(r"-?\d+", v):
            try:
                return int(v)
            except ValueError:
                return value
        if re.fullmatch(r"-?\d+[.,]\d+", v):
            return float(v.replace(",", "."))
    return value


async def _download(url: str, limit: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, bool]:
    """Lataa enintään ``limit`` tavua. Palauttaa (sisältö, katkaistiinko)."""
    async with _client() as client, client.stream("GET", url) as resp:
        resp.raise_for_status()
        content = b""
        async for chunk in resp.aiter_bytes():
            content += chunk
            if len(content) > limit:
                return content[:limit], True
    return content, False


def _match(cell: Any, wanted: list[str]) -> bool:
    text = str(cell if cell is not None else "").lower()
    return any(str(w).lower() == text or str(w).lower() in text for w in wanted)


def _filter_rows(
    rows: list[dict[str, Any]], filters: dict[str, list[str]] | None, max_rows: int
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Suodata client-side. Palauttaa (rivit, osumien määrä, tuntemattomat kentät)."""
    if not filters:
        return rows[:max_rows], len(rows), []
    keys = set(rows[0].keys()) if rows else set()
    unknown = [f for f in filters if f not in keys]
    active = {f: v for f, v in filters.items() if f in keys}
    matched = [r for r in rows if all(_match(r.get(f), v) for f, v in active.items())]
    return matched[:max_rows], len(matched), unknown


# --- CSV ---


async def fetch_csv(
    url: str, filters: dict[str, list[str]] | None, columns: list[str] | None, max_rows: int
) -> Table:
    content, cut = await _download(url)
    text = content.decode("utf-8-sig", errors="replace")
    if cut:
        text = text.rsplit("\n", 1)[0]
    first = text.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    if first.count("\t") > max(first.count(";"), first.count(",")):
        delimiter = "\t"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    all_rows = [{k: _num(v) for k, v in r.items() if k is not None} for r in reader]
    rows, total, unknown = _filter_rows(all_rows, filters, max_rows)
    table = Table(protocol="csv", request_url=url, total=None if cut else total)
    table.notes.append(f"Erotin '{delimiter}'.")
    if cut:
        table.notes.append(
            f"Tiedosto on yli {MAX_DOWNLOAD_BYTES // 1_048_576} MB; käsiteltiin alku. "
            "Kokonaismäärää ei tiedetä."
        )
    if unknown:
        table.error_code = "unknown_filter"
        table.error = f"Tuntemattomat sarakkeet: {', '.join(unknown)}. Sarakkeet: {headers}"
    return _finish(table, headers, rows, columns, total)


def _finish(
    table: Table,
    headers: list[str],
    rows: list[dict[str, Any]],
    columns: list[str] | None,
    total: int | None,
) -> Table:
    if columns:
        headers = [h for h in headers if h in columns]
        rows = [{h: r.get(h) for h in headers} for r in rows]
    table.columns = headers
    table.rows = rows
    if total is not None:
        table.truncated = total > len(rows)
    return table


# --- JSON / GeoJSON ---


def _records(data: Any) -> tuple[list[dict[str, Any]], str]:
    """Etsi JSON-vastauksesta rivilista. Palauttaa (rivit, polku)."""
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        return [
            f.get("properties") or {} for f in data.get("features", [])
        ], "features[].properties"
    if isinstance(data, list):
        return ([r for r in data if isinstance(r, dict)], "$") if data else ([], "$")
    if isinstance(data, dict):
        for key in ("value", "data", "results", "items", "records", "features", "rows"):
            v = data.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v, key
        for key, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v, key
    return [], ""


async def fetch_json(
    url: str,
    filters: dict[str, list[str]] | None,
    max_rows: int,
    conn: sqlite3.Connection | None = None,
) -> Table:
    server_filtered = False
    if filters and "api.vipunen.fi" in url:
        url, server_filtered = vipunen_filter_url(url, filters), True
    content, cut = await _download(url)
    table = Table(protocol="json", request_url=url)
    try:
        data = json.loads(content.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        table.error_code = "not_json"
        table.error = "Vastaus ei ole kelvollista JSONia" + (" (katkaistu)" if cut else "")
        return table
    records, path = _records(data)
    if not records and server_filtered:
        table.notes.append("Vipunen: palvelin suodatti, eikä yksikään rivi täsmännyt.")
        return _finish(table, [], [], None, 0)
    if server_filtered:
        table.notes.append(
            "Vipunen: suodatus tehtiin palvelimella (filter-parametri), joten rivit "
            "kattavat koko tietojoukon eivätkä vain ensimmäistä sivua."
        )
    if not records:
        table.error_code = "no_rows"
        table.error = "JSON-rakenteesta ei löytynyt rivilistaa."
        table.notes.append(json.dumps(data, ensure_ascii=False)[:500])
        return table
    if conn is not None and "sotkanet.fi" in url:
        records = _annotate_sotkanet(conn, records, table)
    headers = list(records[0].keys())
    rows, total, unknown = _filter_rows(records, filters, max_rows)
    # Osumien määrä kerrotaan vain kokonaan luetusta vastauksesta: katkaistun
    # vastauksen luku väittäisi lähteen olevan esikatselun kokoinen.
    table.total = None if cut else total
    reported = _reported_total(data)
    if reported is not None and not filters and reported > len(records):
        # Sivutettu rajapinta (YTJ totalResults, Kirkanta total): sivun
        # rivimäärä ei ole lähteen koko, joten lähteen oma luku voittaa.
        table.total = reported
        table.notes.append(
            f"Lähde kertoo {reported} osumaa; vastauksessa oli yksi sivu ({len(records)} riviä)."
        )
    if path and path != "$":
        table.notes.append(f"Rivit polusta '{path}'.")
    if unknown:
        table.error_code = "unknown_filter"
        table.error = f"Tuntemattomat kentät: {', '.join(unknown)}. Kentät: {headers}"
    return _finish(table, headers, rows, None, table.total if table.total is not None else total)


def _reported_total(data: Any) -> int | None:
    """Lähteen oma osumamäärä JSON-vastauksen juuresta, jos se kerrotaan."""
    if not isinstance(data, dict):
        return None
    for key in ("totalResults", "total", "totalCount", "count"):
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def vipunen_filter_url(url: str, filters: dict[str, list[str]]) -> str:
    """Vipusen RSQL-suodatin URL:iin: ``kenttä=="arvo"`` tai ``kenttä=in=(...)``.

    Ilman tätä suodatus osui vain ensimmäiseen 1 000 rivin sivuun, ja
    rivitason tietojoukossa se on yleensä vanhin lukuvuosi: kysytty rivi
    jäi löytymättä, vaikka se oli lähteessä.
    """
    parts = []
    for key, values in filters.items():
        vals = [str(v).replace('"', "") for v in (values if isinstance(values, list) else [values])]
        if len(vals) == 1:
            parts.append(f'{key}=="{vals[0]}"')
        elif vals:
            parts.append(f"{key}=in=({','.join(chr(34) + v + chr(34) for v in vals)})")
    split = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(split.query))
    query["filter"] = ";".join(parts)
    return urllib.parse.urlunsplit(split._replace(query=urllib.parse.urlencode(query)))


#: Sotkanetin aluekategoria → Auran aluetaso (``aura.areas``in nimet
#: niille jotka Aura tuntee). Muut kategoriat pienaakkosin sellaisenaan.
_SOTKANET_LEVELS = {
    "KUNTA": "kunta",
    "MAAKUNTA": "maakunta",
    "HYVINVOINTIALUE": "hyvinvointialue",
    "SEUTUKUNTA": "seutukunta",
    "SUURALUE": "suuralue",
    "NUTS1": "nuts1",
    "MAA": "koko_maa",
    "ELY-KESKUS": "ely",
    "ALUEHALLINTOVIRASTO": "avi",
    "SAIRAANHOITOPIIRI": "sairaanhoitopiiri",
    "ERVA": "erva",
    "YTA": "yta",
    "EUROOPPA": "maa_eurooppa",
    "POHJOISMAAT": "maa_pohjoismaat",
    "EURALUEET": "maaryhma",
}


def _sotkanet_regions(conn: sqlite3.Connection) -> dict[int, tuple[str | None, str, str]]:
    """Sotkanetin aluetunnus → (koodi, nimi, taso).

    Ensisijaisesti koko rekisteri (``ref_sotkanet_regions``, migraatio 26).
    Vanhemmassa kannassa taulua ei ole: silloin vain kunnat
    ``ref_municipalities.sotkanet_id``-sarakkeesta, kuten ennenkin.
    """
    try:
        rows = conn.execute(
            "SELECT id, category, code, name_fi FROM ref_sotkanet_regions"
        ).fetchall()
    except sqlite3.Error:
        rows = []
    out: dict[int, tuple[str | None, str, str]] = {}
    for rid, category, code, name in rows:
        level = _SOTKANET_LEVELS.get(category, str(category).lower())
        # Koko maan koodi 358 on suuntanumero; Tilastokeskuksen koodi on SSS.
        out[int(rid)] = ("SSS" if category == "MAA" else code, name or "", level)
    if out:
        return out
    try:
        kunnat = conn.execute(
            "SELECT sotkanet_id, code, name_fi FROM ref_municipalities"
            " WHERE sotkanet_id IS NOT NULL"
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {int(r[0]): (r[1], r[2], "kunta") for r in kunnat}


def _annotate_sotkanet(
    conn: sqlite3.Connection, records: list[dict[str, Any]], table: Table
) -> list[dict[str, Any]]:
    """Lisää Sotkanetin aluetunnuksen rinnalle alueen koodi, nimi ja taso."""
    by_id = _sotkanet_regions(conn)
    if not by_id:
        return records
    full = any(level != "kunta" for _, _, level in by_id.values())
    out = []
    for rec in records:
        rid = rec.get("region")
        code, name, level = (
            by_id.get(int(rid), (None, "", "")) if isinstance(rid, int) else (None, "", "")
        )
        out.append(
            {
                **rec,
                "region_code": code or None,
                "region_name": name or None,
                "region_level": level or None,
            }
        )
    if full:
        table.notes.append(
            "Sotkanet: 'region' on Sotkanetin oma aluetunnus, EI kuntakoodi. Alueen "
            "koodi, nimi ja taso ovat kentissä region_code, region_name ja region_level "
            "(kunta, maakunta, hyvinvointialue, seutukunta, koko_maa ...). Suodata esim. "
            '{"region_name": ["Joensuu"]}.'
        )
    else:
        table.notes.append(
            "Sotkanet: 'region' on Sotkanetin oma aluetunnus, EI kuntakoodi. "
            "Kuntakoodi ja nimi ovat kentissä region_code ja region_name "
            '(tyhjä = alue ei ole kunta). Suodata esim. {"region_name": ["Joensuu"]}.'
        )
    return out


# --- OData ---


def _odata_literal(value: str) -> str:
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return value
    return "'" + value.replace("'", "''") + "'"


async def fetch_odata(
    url: str, filters: dict[str, list[str]] | None, columns: list[str] | None, max_rows: int
) -> Table:
    params: dict[str, str] = {"$top": str(max_rows), "$count": "true"}
    if filters:
        parts = []
        for f, values in filters.items():
            ors = [f"{f} eq {_odata_literal(v)}" for v in values]
            parts.append(ors[0] if len(ors) == 1 else "(" + " or ".join(ors) + ")")
        params["$filter"] = " and ".join(parts)
    if columns:
        params["$select"] = ",".join(columns)
    sep = "&" if "?" in url else "?"
    query_url = url + sep + urllib.parse.urlencode(params, safe="$,'() ")
    table = Table(protocol="odata", request_url=query_url)
    async with _client() as client:
        resp = await client.get(query_url)
        resp.raise_for_status()
        data = resp.json()
    rows = data.get("value", []) if isinstance(data, dict) else []
    headers = [k for k in (rows[0].keys() if rows else []) if not k.startswith("@")]
    total = data.get("@odata.count") if isinstance(data, dict) else None
    clean = [{h: r.get(h) for h in headers} for r in rows]
    return _finish(table, headers, clean, None, int(total) if total is not None else None)


# --- WFS ---


#: Postinumerokentät WFS-kerroksissa. Paavon tilastokerros käyttää nimeä
#: ``postinumeroalue``, rajakerros ``posti_alue``.
POSTAL_FIELDS = ("postinumeroalue", "posti_alue", "postinumero", "postinro", "postal_code")

#: Kuinka monta kerrosta muistiinpanossa luetellaan.
_MAX_LAYERS_LISTED = 10


def _cql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _postal_field(headers: list[str]) -> str | None:
    by_lower = {h.lower(): h for h in headers}
    return next((by_lower[f] for f in POSTAL_FIELDS if f in by_lower), None)


async def fetch_wfs(
    url: str,
    filters: dict[str, list[str]] | None,
    max_rows: int,
    bbox: tuple[float, ...] | None,
    *,
    layer: str = "",
    postal_code: str = "",
) -> Table:
    """WFS-kysely. ``layer`` valitsee kerroksen, ``postal_code`` rajaa postinumeroon.

    Postinumerorajaus on attribuuttisuodatin eikä bbox: postinumeroalueen
    rajaus laatikkona osuisi naapurialueisiin. Se toimii vain kerroksessa
    jossa on postinumerokenttä (``POSTAL_FIELDS``); kenttä tunnistetaan
    yhden kohteen koehaulla, koska tallennettu kenttäskeema voi olla eri
    kerroksesta (ks. inspect_dataset).
    """
    from aura.wfs import fetch_features, type_name_from_url, with_layer

    if layer:
        url = with_layer(url, layer)
    explicit_layer = bool(layer) or type_name_from_url(url) is not None

    parts: list[str] = []
    for f, values in (filters or {}).items():
        ors = [f"{f}={_cql_literal(v)}" for v in values]
        parts.append(ors[0] if len(ors) == 1 else "(" + " OR ".join(ors) + ")")

    probe = None
    layers: list[str] = []
    if postal_code:
        probe = await fetch_features(url, 1, timeout=TIMEOUT)
        if probe.error:
            return Table(
                protocol="wfs", request_url=url, error_code="service_error", error=probe.error
            )
        layers = list(probe.feature_types)
        used = probe.type_name or type_name_from_url(url) or "?"
        postal_field = _postal_field(list(probe.headers))
        if postal_field is None:
            return Table(
                protocol="wfs",
                request_url=url,
                error_code="area_not_supported",
                error=(
                    f"Postinumero {postal_code} tunnistettiin, mutta kerroksessa {used} ei ole "
                    "postinumerokenttää (kentät: "
                    + ", ".join(list(probe.headers)[:12])
                    + "). Valitse kerros jossa se on (layer) tai käytä kunnan nimeä."
                ),
                layers=layers or None,
                layer=used,
            )
        if probe.type_name and not explicit_layer:
            # Sama kerros varsinaiseen hakuun kuin jolla kenttä tunnistettiin.
            url = with_layer(url, probe.type_name)
        parts.append(f"{postal_field}={_cql_literal(postal_code)}")

    cql = None
    bbox_param = None
    if parts and bbox is not None:
        probe = probe or await fetch_features(url, 1, timeout=TIMEOUT)
        if probe.geometry_name is None:
            return Table(
                protocol="wfs",
                request_url=url,
                error_code="bbox_and_filters",
                error="Aluerajausta ei voi yhdistää suodattimiin: palvelu ei kerro "
                "geometriakentän nimeä. Aja kysely ilman toista niistä.",
            )
        parts.append(
            f"BBOX({probe.geometry_name},{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},'EPSG:3067')"
        )
    if parts:
        cql = " AND ".join(parts)
    elif bbox is not None:
        bbox_param = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:3067"
    result = await fetch_features(url, max_rows, bbox=bbox_param, cql_filter=cql, timeout=TIMEOUT)
    table = Table(protocol="wfs", request_url=url)
    layers = list(result.feature_types) or layers
    probed = probe.type_name if probe else None
    table.layer = result.type_name or probed or type_name_from_url(url)
    if layers:
        table.layers = layers
    if result.error:
        table.error_code = "service_error"
        table.error = result.error
        return table
    if len(layers) > 1 and not explicit_layer:
        listed = ", ".join(layers[:_MAX_LAYERS_LISTED])
        extra = len(layers) - _MAX_LAYERS_LISTED
        more = f" (+{extra} muuta)" if extra > 0 else ""
        table.notes.append(
            f"Palvelussa on {len(layers)} kerrosta; käytettiin ensimmäistä ({table.layer}). "
            f"Valitse kerros layer-parametrilla: {listed}{more}."
        )
    rows = [{h: _num(v) for h, v in zip(result.headers, r, strict=False)} for r in result.rows]
    total = int(result.total) if result.total and str(result.total).isdigit() else None
    if total is None:
        table.notes.append("Palvelu ei kertonut kohteiden kokonaismäärää.")
    if cql:
        table.notes.append(f"CQL_FILTER: {cql}")
    return _finish(table, list(result.headers), rows, None, total)


# --- FMI:n tallennetut kyselyt ---

_BSWFS = "{http://xml.fmi.fi/schema/wfs/2.0}"


def is_stored_query(url: str) -> bool:
    return "storedquery_id=" in url.lower()


async def fetch_fmi(
    url: str, filters: dict[str, list[str]] | None, max_rows: int, bbox: tuple[float, ...] | None
) -> Table:
    """FMI:n tallennettu kysely. Suodattimet ovat kyselyn parametreja.

    Esim. ``{"place": ["Helsinki"], "parameters": ["t2m,ws_10min"]}`` tai
    ``{"fmisid": ["100971"]}``. Vain ``::simple``-muotoiset kyselyt
    palauttavat rivimuotoista dataa; muille ehdotetaan simple-varianttia.
    """
    base, _, query = url.partition("?")
    params = dict(urllib.parse.parse_qsl(query))
    sq = params.get("storedquery_id", "")
    table = Table(protocol="fmi_stored_query")
    if not sq.endswith("::simple"):
        simple = re.sub(r"::(multipointcoverage|timevaluepair|grid)$", "::simple", sq)
        table.notes.append(
            f"Kysely {sq} palauttaa hilamuotoa; rivit saadaan simple-variantista {simple}."
        )
        params["storedquery_id"] = simple
    for key, values in (filters or {}).items():
        params[key] = ",".join(values)
    if (
        bbox is not None
        and "bbox" not in params
        and "place" not in params
        and "fmisid" not in params
    ):
        params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:3067"
    request_url = base + "?" + urllib.parse.urlencode(params, safe=":,")
    table.request_url = request_url
    async with _client() as client:
        resp = await client.get(request_url)
    if resp.status_code >= 400:
        from aura.wfs import exception_text

        table.error_code = "service_error"
        table.error = (exception_text(resp.text) or f"HTTP {resp.status_code}")[:500]
        table.notes.append(
            "Tallennettu kysely tarvitsee yleensä paikan: place (esim. 'Helsinki'), "
            "fmisid (asematunnus) tai bbox."
        )
        return table
    if len(resp.content) > MAX_DOWNLOAD_BYTES:
        table.error_code = "too_large"
        table.error = (
            "Vastaus on liian suuri. Rajaa: parameters (esim. 't2m'), starttime, "
            "tai yksi asema (fmisid/place)."
        )
        return table
    # Sama raja kuin aura.wfs:ssä: ElementTree laajentaa entiteetit, joten
    # vieraan palvelimen syötteen koko on rajattava ennen jäsennystä.
    root = ET.fromstring(resp.content)
    rows: list[dict[str, Any]] = []
    for el in root.iter(f"{_BSWFS}BsWfsElement"):
        pos = el.findtext(".//{http://www.opengis.net/gml/3.2}pos") or ""
        rows.append(
            {
                "time": el.findtext(f"{_BSWFS}Time"),
                "parameter": el.findtext(f"{_BSWFS}ParameterName"),
                "value": _num(el.findtext(f"{_BSWFS}ParameterValue") or ""),
                "position": pos.strip(),
            }
        )
    total = len(rows)
    # Uusimmat ensin: säähavaintokysymys koskee lähes aina viimeisintä arvoa.
    rows.sort(key=lambda r: r.get("time") or "", reverse=True)
    if total:
        table.notes.append("Rivit uusin ensin. Arvo 'NaN' = havainto puuttuu.")
    return _finish(table, ["time", "parameter", "value", "position"], rows[:max_rows], None, total)


# --- PxWeb ---


def _is_time(var: dict[str, Any]) -> bool:
    if var.get("time"):
        return True
    text = f"{var.get('code', '')} {var.get('text', '')}".lower()
    return any(w in text for w in _TIME_WORDS)


def _is_area(var: dict[str, Any]) -> bool:
    text = f"{var.get('code', '')} {var.get('text', '')}".lower()
    return any(w in text for w in _AREA_WORDS)


def describe_dimensions(meta: dict[str, Any]) -> list[dict[str, Any]]:
    """PxWeb-metatieto → dimensiot esimerkkeineen (koodi + nimi)."""
    out = []
    for var in meta.get("variables", []):
        values = var.get("values", [])
        texts = var.get("valueTexts", []) or values
        pairs = list(zip(values, texts, strict=False))
        examples = pairs[-5:] if _is_time(var) else pairs[:5]
        out.append(
            {
                "code": var.get("code", ""),
                "text": var.get("text", ""),
                "values": len(values),
                "time": _is_time(var),
                "area": _is_area(var),
                "optional": bool(var.get("elimination")),
                "examples": [{"code": c, "text": t} for c, t in examples],
            }
        )
    return out


def resolve_pxweb_values(
    var: dict[str, Any], wanted: list[str], conn: sqlite3.Connection | None
) -> tuple[list[str], list[str], list[str]]:
    """Käyttäjän arvot → taulun koodit. Palauttaa (koodit, tuntemattomat, muistiinpanot)."""
    values: list[str] = var.get("values", [])
    texts: list[str] = var.get("valueTexts", []) or values
    by_text = {t.lower(): c for c, t in zip(values, texts, strict=False)}
    codes: list[str] = []
    unknown: list[str] = []
    notes: list[str] = []
    for raw in wanted:
        w = str(raw).strip()
        low = w.lower()
        if _is_time(var):
            if low in _LATEST:
                codes.append(values[-1])
                continue
            m = _RANGE.match(w)
            if m:
                lo, hi = m.group(1), m.group(2)
                span = [v for v in values if lo <= v[:4] <= hi]
                if span:
                    codes.extend(span)
                    continue
        if w in values:
            codes.append(w)
            continue
        if low in by_text:
            codes.append(by_text[low])
            continue
        # Nimen alku: "Tampere" osuu "Tampere - Tammerfors"; "MK06" osuu "MK06 Pirkanmaa".
        prefix = [c for t, c in by_text.items() if t.startswith(low + " ") or t.startswith(low)]
        if len(prefix) == 1:
            codes.append(prefix[0])
            continue
        if _is_area(var) and conn is not None:
            from aura.areas import resolve_area

            match = resolve_area(conn, w)
            if match and match.area.statfin_code in values:
                codes.append(match.area.statfin_code)
                if match.note:
                    notes.append(match.note)
                continue
            if match and match.area.code in values:
                codes.append(match.area.code)
                continue
        exact_sub = [c for t, c in by_text.items() if low in t]
        if len(exact_sub) == 1:
            codes.append(exact_sub[0])
            continue
        unknown.append(w)
    return codes, unknown, notes


def _default_selection(var: dict[str, Any]) -> tuple[list[str] | None, str]:
    """Valinta suodattamattomalle dimensiolle. None = jätetään pois (eliminointi)."""
    values: list[str] = var.get("values", [])
    texts: list[str] = var.get("valueTexts", []) or values
    name = var.get("text") or var.get("code")
    if _is_time(var):
        chosen = values[-DEFAULT_TIME_VALUES:]
        return chosen, f"{name}: ei suodatinta → {len(chosen)} uusinta ({chosen[0]}–{chosen[-1]})."
    if len(values) <= 50:
        return values, ""
    if var.get("elimination"):
        return None, f"{name}: ei suodatinta → jätettiin pois (taulu laskee summan)."
    for c, t in zip(values, texts, strict=False):
        if c in ("SSS", "S", "0", "SSS00") or t.lower().startswith(
            ("koko maa", "yhteensä", "total")
        ):
            return [c], f"{name}: ei suodatinta → '{t}'."
    return [values[0]], f"{name}: ei suodatinta → ensimmäinen arvo '{texts[0]}'."


async def pxweb_metadata(api_url: str) -> dict[str, Any]:
    async with _client() as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data


async def fetch_pxweb(
    api_url: str,
    filters: dict[str, list[str]] | None,
    max_rows: int,
    conn: sqlite3.Connection | None = None,
    area: str = "",
) -> Table:
    meta = await pxweb_metadata(api_url)
    variables: list[dict[str, Any]] = meta.get("variables", [])
    table = Table(protocol="pxweb", request_url=api_url)
    table.dimensions = describe_dimensions(meta)
    filters = dict(filters or {})
    if area:
        area_var = next((v for v in variables if _is_area(v)), None)
        if area_var is None:
            table.error_code = "no_area_dimension"
            table.error = "Taulussa ei ole aluedimensiota; area ei rajaa tätä taulua."
            return table
        filters.setdefault(area_var["code"], [area])
    if not filters:
        title = meta.get("title", "")
        table.notes.append(
            f"{title}. Ei suodattimia: palautetaan dimensiot. Anna filters, esim. "
            + json.dumps(_example_filters(variables), ensure_ascii=False)
        )
        return table

    by_code = {v["code"]: v for v in variables}
    by_text = {v.get("text", "").lower(): v for v in variables}
    selection: list[dict[str, Any]] = []
    unknown_dims: list[str] = []
    unknown_values: dict[str, list[str]] = {}
    used: set[str] = set()
    for key, wanted in filters.items():
        var = by_code.get(key) or by_text.get(key.lower())
        if var is None:
            unknown_dims.append(key)
            continue
        codes, unknown, notes = resolve_pxweb_values(var, list(wanted), conn)
        table.notes.extend(notes)
        if unknown:
            unknown_values[var["code"]] = unknown
        if codes:
            selection.append(
                {"code": var["code"], "selection": {"filter": "item", "values": codes}}
            )
            used.add(var["code"])
    if unknown_dims or unknown_values:
        table.error_code = "unknown_filter"
        parts = []
        if unknown_dims:
            parts.append(
                "tuntemattomat dimensiot "
                + ", ".join(unknown_dims)
                + " (käytössä: "
                + ", ".join(f"{v['code']} = {v.get('text')}" for v in variables)
                + ")"
            )
        for code, vals in unknown_values.items():
            parts.append(f"dimensiossa {code} ei arvoja {vals}")
        table.error = "; ".join(parts) + ". Katso dimensions-kentän esimerkit."
        return table
    for var in variables:
        if var["code"] in used:
            continue
        chosen, note = _default_selection(var)
        if note:
            table.notes.append(note)
        if chosen is not None:
            selection.append(
                {"code": var["code"], "selection": {"filter": "item", "values": chosen}}
            )

    body = {"query": selection, "response": {"format": "json-stat2"}}
    table.request_body = body
    async with _client() as client:
        resp = await client.post(api_url, json=body)
    if resp.status_code == 429:
        table.error_code = "rate_limited"
        table.error = "Tilastopalvelu rajoitti kyselyitä (HTTP 429). Yritä hetken päästä uudelleen."
        return table
    if resp.status_code >= 400:
        table.error_code = "service_error"
        table.error = f"PxWeb HTTP {resp.status_code}: {resp.text[:300]}"
        return table
    data = resp.json()
    rows, code_map, total = flatten_jsonstat(data, max_rows)
    table.codes = code_map
    columns = [data["dimension"][d].get("label", d) for d in data.get("id", [])] + ["value"]
    if any("status" in r for r in rows):
        columns.append("status")
    unit = _unit(data)
    if unit:
        table.notes.append(f"Yksikkö: {unit}.")
    return _finish(table, columns, rows, None, total)


def _example_filters(variables: list[dict[str, Any]]) -> dict[str, list[str]]:
    ex: dict[str, list[str]] = {}
    for var in variables:
        texts = var.get("valueTexts", []) or var.get("values", [])
        if not texts:
            continue
        ex[var["code"]] = ["uusin"] if _is_time(var) else [texts[0]]
    return ex


def _unit(data: dict[str, Any]) -> str:
    """Yksikkö json-stat2:n sisältödimensiosta, jos se on kerrottu."""
    for dim in data.get("dimension", {}).values():
        unit = dim.get("category", {}).get("unit")
        if isinstance(unit, dict) and unit:
            units = {u.get("base") or u.get("label", "") for u in unit.values()}
            units.discard("")
            if units:
                return ", ".join(sorted(units))
    return ""


def flatten_jsonstat(
    data: dict[str, Any], max_rows: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], int]:
    """json-stat2 → rivit nimillä + koodikartta. Palauttaa (rivit, koodit, kokonaismäärä)."""
    ids: list[str] = data.get("id", [])
    sizes: list[int] = data.get("size", [])
    dims = data.get("dimension", {})
    ordered: list[list[tuple[str, str]]] = []
    labels: list[str] = []
    codes: dict[str, dict[str, str]] = {}
    for dim_id in ids:
        info = dims.get(dim_id, {})
        cat = info.get("category", {})
        index = cat.get("index", {})
        lab = cat.get("label", {})
        if isinstance(index, dict):
            order = [c for c, _ in sorted(index.items(), key=lambda x: x[1])]
        else:
            order = list(index)
        pairs = [(c, lab.get(c, c)) for c in order]
        ordered.append(pairs)
        name = info.get("label", dim_id)
        labels.append(name)
        codes[name] = {t: c for c, t in pairs}
    values = data.get("value", [])
    status = data.get("status") or {}
    total = 1
    for s in sizes:
        total *= s
    rows: list[dict[str, Any]] = []
    for flat in range(min(total, max_rows)):
        rem = flat
        pos = [0] * len(ids)
        for i in range(len(ids) - 1, -1, -1):
            pos[i] = rem % sizes[i]
            rem //= sizes[i]
        row: dict[str, Any] = {labels[i]: ordered[i][pos[i]][1] for i in range(len(ids))}
        value = values[flat] if flat < len(values) else None
        row["value"] = value
        st = (
            status.get(str(flat))
            if isinstance(status, dict)
            else (status[flat] if isinstance(status, list) and flat < len(status) else None)
        )
        if st:
            row["status"] = st
        rows.append(row)
    return rows, codes, total
