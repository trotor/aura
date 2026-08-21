"""Probe-vaihe: skeema johdetaan rajapinnosta, ei metatiedosta.

Tämä on ``aura infer-schemas`` laajennettuna. Vanha versio osasi CSV:n ja
JSONin, ajoi kerran eikä koskaan uudestaan, tulosti virheet ja unohti ne.
Kattavuus jäi 54 datasettiin 12 918:sta.

Kolme lisäystä ratkaisevat sen: WFS ja WMS mukaan, TTL joka porrastuu vian
luonteen mukaan, ja kirjanpito johon epäonnistuminen jää näkyviin.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from aura.constants import user_agent
from aura.database import add_enrichment, upsert_probe_result, upsert_resource_schema
from aura.probe import pxweb as pxweb_probe
from aura.probe import tabular as tabular_probe
from aura.probe import wfs as wfs_probe
from aura.probe import wms as wms_probe
from aura.probe.derive import auth_from_status
from aura.probe.types import ProbeResult, ProbeStatus
from aura.tools.schema import detect_joinable_keys

logger = logging.getLogger(__name__)

Prober = Callable[[dict[str, Any], httpx.AsyncClient], Awaitable[ProbeResult]]

#: Resurssiformaatti → probe_type.
PROBE_TYPES: dict[str, str] = {
    "WFS": "wfs",
    "WMS": "wms",
    "PXWEB": "pxweb",
    "CSV": "csv",
    "JSON": "json",
    "GEOJSON": "json",
}

#: TTL vian luonteen mukaan. Poissa oleva palvelu ei palaa viikossa, hidas
#: voi — ja 404:n uudelleenyrittäminen joka kierroksella on
#: kohteliaisuusongelma joka ei tuota mitään.
TTL_DAYS: dict[str, int] = {
    "ok": 30,
    "timeout": 7,
    "http_error_transient": 7,
    "http_error_permanent": 90,
    "parse_error": 30,
    "empty": 30,
}

#: Kutsua sekunnissa samalle isännälle. Luku ei ole arvaus: 6-rinnakkainen
#: ajo PxWebiä vasten menetti 3 808 taulua 3 928:sta, koska HTTP 429 näytti
#: tyhjältä tulokselta eikä virheeltä.
RATE_LIMIT_PER_SECOND = 2.0

_COMMIT_EVERY = 50
_TIMEOUT = 30.0

DEFAULT_PROBERS: dict[str, Prober] = {
    "wfs": wfs_probe.probe,
    "wms": wms_probe.probe,
    "pxweb": pxweb_probe.probe,
    "csv": tabular_probe.probe,
    "json": tabular_probe.probe,
}


def _ttl_key(status: str, detail: str) -> str:
    """TTL-avain tilasta ja syystä."""
    if status == ProbeStatus.HTTP_ERROR:
        pysyva = any(code in detail for code in ("404", "410"))
        return "http_error_permanent" if pysyva else "http_error_transient"
    return status


def select_targets(
    conn: Any,
    *,
    now: str,
    source: str = "",
    fmt: str = "",
    limit: int = 50,
    max_age_days: int = 0,
) -> list[dict[str, Any]]:
    """Valitse probattavat resurssit: probaamattomat ensin, sitten vanhimmat.

    Vanhentuneisuus lasketaan tilakohtaisella TTL:llä, joten SQL palauttaa
    ehdokkaat ja Python karsii ne joiden aika ei ole vielä tullut. Ehtojen
    kirjoittaminen SQL:ään vaatisi CASE-lausekkeen jokaiselle tilalle,
    eivätkä kohdemäärät ole sellaisia että sillä olisi väliä.

    ``max_age_days`` ohittaa tilakohtaisen TTL:n kokonaan: kohde valitaan jos
    ``probed_at`` on tätä vanhempi, riippumatta tilasta. 0 (oletus) käyttää
    normaalia tilakohtaista TTL:ää.
    """
    formats = ",".join(f"'{f}'" for f in PROBE_TYPES)
    sql = f"""
        SELECT r.id, r.dataset_id, r.format, r.url,
               p.status AS prev_status, p.detail AS prev_detail,
               p.probed_at AS prev_probed_at
        FROM resources r
        JOIN datasets d ON d.id = r.dataset_id
        LEFT JOIN probe_results p ON p.resource_id = r.id
        WHERE UPPER(r.format) IN ({formats})
          AND r.url != ''
    """
    params: list[Any] = []
    if source:
        sql += " AND d.source = ?"
        params.append(source)
    if fmt:
        sql += " AND UPPER(r.format) = ?"
        params.append(fmt.upper())
    sql += " ORDER BY (p.probed_at IS NULL) DESC, p.probed_at"

    nyt = datetime.fromisoformat(now)
    targets: list[dict[str, Any]] = []
    for row in conn.execute(sql, params):
        if row["prev_probed_at"]:
            if max_age_days > 0:
                ikaraja = nyt - timedelta(days=max_age_days)
            else:
                avain = _ttl_key(row["prev_status"] or "", row["prev_detail"] or "")
                ikaraja = nyt - timedelta(days=TTL_DAYS.get(avain, 30))
            if datetime.fromisoformat(row["prev_probed_at"]) > ikaraja:
                continue
        targets.append(dict(row))
        if len(targets) >= limit:
            break
    return targets


def _store(
    conn: Any, target: dict[str, Any], result: ProbeResult, now: str
) -> None:
    """Kirjaa yhden proben tulos: kirjanpito aina, tieto jos sitä tuli."""
    probe_type = PROBE_TYPES[(target["format"] or "").upper()]
    upsert_probe_result(
        conn,
        target["id"],
        target["dataset_id"],
        probe_type,
        result.status,
        result.detail,
        now,
    )
    # auth_method johdetaan statuskoodista ennen ok-vartijaa, ei sen
    # jälkeen: 401/403 kertovat autentikoinnista juuri silloin kun probe
    # epäonnistui ("http_error"), ja specin auth-taulukon neljästä rivistä
    # kolme on juuri näitä. Aiemmin tämä kutsu oli vartijan jälkeen, jolloin
    # se oli tavoittamatonta koodia paitsi 200 OK -tapauksessa.
    # ``result.final_url`` on vastauksen osoite uudelleenohjausten jälkeen —
    # ei ``target["url"]`` (pyyntöä edeltävä). Jos proberi ei täytä sitä,
    # se on tyhjä eikä auth_from_status arvaa sen perusteella mitään.
    for kentta, arvo in auth_from_status(result.http_status, result.final_url):
        _add_once(conn, target["dataset_id"], kentta, arvo)

    if not result.ok:
        return

    if result.fields:
        upsert_resource_schema(conn, target["id"], target["dataset_id"], result.fields)
        keys = detect_joinable_keys([nimi for nimi, _ in result.fields])
        if keys:
            _add_once(
                conn,
                target["dataset_id"],
                "joinable_keys",
                json.dumps(keys, ensure_ascii=False),
                confidence="medium",
                source_detail="Auto-detected from field names (heuristic)",
            )

    for kentta, arvo in result.enrichments:
        _add_once(conn, target["dataset_id"], kentta, arvo)


def _add_once(
    conn: Any,
    dataset_id: str,
    field: str,
    value: str,
    confidence: str = "high",
    source_detail: str = "",
) -> None:
    """Lisää enrichment ellei samaa arvoa jo ole.

    Probe ajetaan uudestaan TTL:n välein, eikä muuttumaton tulos saa kasvattaa
    riviä joka ajolla.
    """
    olemassa = conn.execute(
        "SELECT 1 FROM enrichments WHERE dataset_id = ? AND field = ? AND value = ?"
        " LIMIT 1",
        (dataset_id, field, value),
    ).fetchone()
    if olemassa:
        return
    add_enrichment(
        conn,
        dataset_id,
        field,
        value,
        confidence=confidence,
        source_type="probe",
        source_detail=source_detail,
    )


async def run_probe(
    conn: Any,
    *,
    source: str = "",
    fmt: str = "",
    limit: int = 50,
    now: str = "",
    client: httpx.AsyncClient | None = None,
    probers: dict[str, Prober] | None = None,
    max_age_days: int = 0,
) -> dict[str, int]:
    """Aja probe valituille kohteille ja kirjaa tulokset.

    ``max_age_days`` välitetään suoraan ``select_targets``:lle — ks. sen
    docstring.

    Returns:
        Yhteenveto tiloittain, esim. ``{"ok": 12, "http_error": 3}``.
    """
    timestamp = now or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")
    active = probers or DEFAULT_PROBERS
    targets = select_targets(
        conn, now=timestamp, source=source, fmt=fmt, limit=limit, max_age_days=max_age_days
    )
    summary: dict[str, int] = defaultdict(int)
    if not targets:
        return dict(summary)

    last_call: dict[str, float] = {}
    loop = asyncio.get_running_loop()

    async def _throttle(url: str) -> None:
        host = urlparse(url).netloc
        vali = 1.0 / RATE_LIMIT_PER_SECOND
        edellinen = last_call.get(host)
        nyt = loop.time()
        if edellinen is not None and nyt - edellinen < vali:
            await asyncio.sleep(vali - (nyt - edellinen))
        last_call[host] = loop.time()

    own_client = client is None
    http = client or httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": user_agent("probe")}
    )
    try:
        for i, target in enumerate(targets, 1):
            probe_type = PROBE_TYPES[(target["format"] or "").upper()]
            prober = active.get(probe_type)
            if prober is None:
                continue
            await _throttle(target["url"])
            try:
                result = await prober(target, http)
            except Exception as e:  # prober ei saa kaataa koko ajoa
                logger.warning("[probe] %s kaatui: %s", target["id"], e)
                result = ProbeResult(
                    status=ProbeStatus.PARSE_ERROR, detail=str(e)[:100]
                )

            # _store() ei myöskään saa kaataa koko ajoa: esim. WFS-resurssi
            # jonka typeNames kattaa useamman feature typen voi silti tuoda
            # kenttäluettelon joka rikkoo tietokannan oletuksia tavalla jota
            # prober ei ehkäissyt (ks. wfs.parse_feature_types). SAVEPOINTia
            # ei käytetä: add_enrichment() commitoi sisäisesti jokaisen
            # rikastuksen heti, mikä päättäisi ympäröivän SAVEPOINTin
            # ennenaikaisesti ("no such savepoint" seuraavalla RELEASEllä).
            # upsert_resource_schema on ainoa kohta josta tämä virhe on
            # toistaiseksi nähty tulevan, joten kesken jäänyt kirjoitus
            # siivotaan kohdennetusti sen sijaan että koko _store() olisi
            # transaktion sisällä.
            try:
                _store(conn, target, result, timestamp)
            except Exception as e:
                logger.warning("[probe] %s tallennus epäonnistui: %s", target["id"], e)
                try:
                    conn.execute(
                        "DELETE FROM resource_schema WHERE resource_id = ?",
                        (target["id"],),
                    )
                    upsert_probe_result(
                        conn,
                        target["id"],
                        target["dataset_id"],
                        probe_type,
                        ProbeStatus.PARSE_ERROR,
                        str(e)[:100],
                        timestamp,
                    )
                except Exception as cleanup_error:
                    # Palautuspolku ei myöskään saa kaataa koko ajoa. Jos
                    # kantaan ei tässä vaiheessa voi kirjoittaa lainkaan
                    # (esim. read-only-yhteys), tämä siivous itse nostaisi
                    # raa'an sqlite3.OperationalErrorin, joka ilman tätä
                    # try/exceptiä karkaisi run_probe():sta kokonaan ja
                    # pysäyttäisi koko ajon ensimmäiseen kohteeseen.
                    logger.warning(
                        "[probe] %s tallennuksen palautuskin epäonnistui: %s",
                        target["id"],
                        cleanup_error,
                    )
                summary[ProbeStatus.PARSE_ERROR] += 1
            else:
                summary[result.status] += 1
            if i % _COMMIT_EVERY == 0:
                conn.commit()
        conn.commit()
    finally:
        if own_client:
            await http.aclose()

    return dict(summary)


def format_probe_summary(summary: dict[str, int]) -> str:
    """Muotoile ajon yhteenveto ihmiselle.

    Epäonnistumiset näkyvät omina riveinään: kokonaisluku joka ei erottele
    onnistumista virheestä kertoo vähemmän kuin ei mitään.
    """
    if not summary:
        return "Ei probattavia kohteita (kaikki tuoreita tai ei sopivia resursseja)."
    rivit = [f"Probattu {sum(summary.values())} resurssia:"]
    for status in ("ok", "http_error", "timeout", "parse_error", "empty"):
        if summary.get(status):
            rivit.append(f"  {status:12} {summary[status]}")
    return "\n".join(rivit)
