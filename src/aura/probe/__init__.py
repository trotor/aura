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
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from aura.constants import user_agent
from aura.database import add_enrichment, upsert_probe_result, upsert_resource_schema
from aura.probe import capture
from aura.probe import pxweb as pxweb_probe
from aura.probe import tabular as tabular_probe
from aura.probe import wfs as wfs_probe
from aura.probe import wms as wms_probe
from aura.probe.derive import auth_from_status
from aura.probe.types import ProbeResult, ProbeStatus
from aura.schema_infer import detect_joinable_keys

logger = logging.getLogger(__name__)

Prober = Callable[[dict[str, Any], httpx.AsyncClient], Awaitable[ProbeResult]]

#: Työntekijältä kirjoittajalle kulkeva paketti: kohde, sen probe_type,
#: proberin tulos ja samasta noudosta poimitut vastauksen tosiasiat.
_Paketti = tuple[dict[str, Any], str, ProbeResult, capture.ResponseFacts]

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

#: Montako isäntää probataan yhtä aikaa.
#:
#: Tahdinsäätö on isäntäkohtainen, joten rinnakkaisuus isäntien välillä ei
#: kiristä yhdenkään palvelun kohtelua. Katto on silti tarpeen: kannassa on
#: satoja eri isäntiä, ja ilman rajaa kattava ajo avaisi yhtä monta
#: yhteyttä kerralla.
#:
#: **Kahdeksaa suuremmasta ei ole hyötyä, ja syy on mitattu (1.9.2026).**
#: Probattavia resursseja on 16 979 ja eri isäntiä 192, mutta jakauma on
#: äärimmäisen vino: ``sotkanet.fi`` yksin on 7 545 resurssia eli 44 %
#: kaikesta. Kahden kutsun sekuntitahdilla koko kierros kestää sarjallisena
#: ~2,4 h ja tällä katolla ~1,0 h — ja se tunti **on** sotkanet.fi, ei
#: jonotus. Katon nostaminen ei siis lyhennä ajoa lainkaan.
#:
#: Jos kierrosta halutaan vielä lyhentää, ainoa tehoava keino on käsitellä
#: sotkanet.fi erikseen: sen 3 772 templatoitua CSV-URLia ja yhtä monta
#: JSON-URLia osoittavat samaan rajapintaan, joten ne eivät tarvitse
#: resurssikohtaista noutoa.
HOST_CONCURRENCY = 8

#: Montako peräkkäistä 429:ää ennen kuin isännästä luovutaan tämän ajon osalta.
#:
#: Mitattu tarve, ei varovaisuus: ensimmäinen kattava ajo (1.9.2026) teki
#: ``statfin.stat.fi``:lle 1 534 pyyntöä, joista **1 494 hylättiin koodilla
#: 429**. Tahdinsäätö toimi tuolloin oikein — lokista laskettuna 1,99
#: pyyntöä sekunnissa — joten kyse ei ollut liian nopeasta tahdista vaan
#: siitä että palvelun raja on tiukempi kuin kaksi kutsua sekunnissa.
#:
#: Ensimmäiset ~40 pyyntöä menivät läpi ja loput **13 minuuttia** hylättiin,
#: mikä on aikaikkunakohtaisen kiintiön käyttäytyminen eikä liukuvan
#: sekuntirajan. Sellaista ei voi odottaa pois järkevässä ajassa, joten
#: oikea vastaus on luovuttaa ja jättää loput seuraavaan ajoon.
#:
#: Kolme on tarkoituksella pieni: kiintiön täytyttyä *jokainen* seuraava
#: pyyntö hylätään, joten suurempi luku ostaisi vain lisää turhaa kuormaa.
RATE_LIMIT_GIVE_UP = 3

#: Pisin odotus jonka ``Retry-After`` saa aiheuttaa.
#:
#: Isäntiä on 174 ja yhtäaikaisia työntekijävuoroja kahdeksan. Kymmenen
#: minuutin odotus varaisi vuoron muilta isänniltä enemmän kuin voittaisi
#: tälle, joten pitkän ohjeen kohdalla luovutaan sen sijaan että odotetaan.
RATE_LIMIT_MAX_WAIT = 30.0

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


def _store_health(
    conn: Any, target: dict[str, Any], havainnot: capture.ResponseFacts, now: str
) -> None:
    """Kirjaa saatavuus ja datan muutosaika samasta vastauksesta.

    Nämä ovat aiemmin vaatineet oman kierroksensa (``aura.health``), joka
    hakee täsmälleen samat osoitteet uudelleen. Kun probe joka tapauksessa
    noutaa jokaisen resurssin, toinen nouto on pelkkää kuormaa sekä meille
    että 192 ulkopuoliselle palvelimelle.

    ``Last-Modified`` tallennetaan rikastuksena ``data_modified``, koska se
    vastaa eri kysymykseen kuin katalogin ``metadata_modified``: milloin
    **data** muuttui, ei milloin metatietue muuttui. Laatupisteiden
    ``timeliness`` (keskiarvo 58/100, toiseksi heikoin dimensio) lasketaan
    tällä hetkellä jälkimmäisestä.
    """
    if havainnot.status_code is None:
        # Pyyntö ei koskaan saanut vastausta (timeout, DNS, yhteysvirhe).
        # Rivi kirjataan silti: "ei vastannut" on saatavuustieto sekin.
        conn.execute(
            "INSERT OR REPLACE INTO resource_health (resource_id, dataset_id,"
            " url, status_code, response_time_ms, content_type, content_length,"
            " is_available, error_message, checked_at)"
            " VALUES (?, ?, ?, NULL, NULL, '', NULL, 0, ?, ?)",
            (target["id"], target["dataset_id"], target["url"], "ei vastausta", now),
        )
        return

    conn.execute(
        "INSERT OR REPLACE INTO resource_health (resource_id, dataset_id, url,"
        " status_code, response_time_ms, content_type, content_length,"
        " is_available, error_message, checked_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?)",
        (
            target["id"],
            target["dataset_id"],
            havainnot.url or target["url"],
            havainnot.status_code,
            havainnot.response_time_ms,
            havainnot.content_type,
            havainnot.content_length,
            1 if havainnot.saatavilla else 0,
            now,
        ),
    )
    if havainnot.last_modified:
        _add_once(
            conn,
            target["dataset_id"],
            "data_modified",
            havainnot.last_modified,
            confidence="high",
            source_detail="Last-Modified-otsake",
        )


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

    # Ryhmittely isännän mukaan on koko rinnakkaisuuden perusta. Kun jokaisella
    # isännällä on täsmälleen yksi työntekijä, tahdinsäätö ei enää tarvitse
    # jaettua kirjanpitoa vaan seuraa rakenteesta: työntekijä odottaa oman
    # edellisen kutsunsa jälkeen. Aiempi ``last_call``-sanakirja olisi ollut
    # rinnakkaisessa ajossa tarkista-sitten-toimi -kilpailu.
    ryhmat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for kohde in targets:
        ryhmat[urlparse(kohde["url"]).netloc].append(kohde)

    own_client = client is None
    http = client or httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": user_agent("probe")},
        event_hooks=capture.event_hooks(),
    )

    # Valmiit tulokset kulkevat jonon kautta yhdelle kirjoittajalle. SQLite-
    # yhteys ei kestä rinnakkaista kirjoitusta, joten *pyynnöt* rinnakkaistuvat
    # mutta *kirjaus* pysyy sarjallisena. Katto pitää jonon lyhyenä, jottei
    # koko tulosjoukko kerry muistiin ennen kirjoitusta.
    jono: asyncio.Queue[_Paketti | None] = asyncio.Queue(
        maxsize=HOST_CONCURRENCY * 2
    )
    vuorot = asyncio.Semaphore(HOST_CONCURRENCY)

    async def _koeta(
        kohde: dict[str, Any], prober: Prober
    ) -> tuple[ProbeResult, capture.ResponseFacts]:
        """Yksi probe-yritys. Poiminta alustetaan ennen jokaista.

        Poiminta on taskikohtainen, joten rinnakkaiset työntekijät eivät
        sekoita toistensa vastauksia keskenään.
        """
        havainnot = capture.aloita()
        try:
            return await prober(kohde, http), havainnot
        except Exception as e:  # prober ei saa kaataa koko ajoa
            logger.warning("[probe] %s kaatui: %s", kohde["id"], e)
            return (
                ProbeResult(status=ProbeStatus.PARSE_ERROR, detail=str(e)[:100]),
                havainnot,
            )

    async def _tyontekija(isanta: str, kohteet: list[dict[str, Any]]) -> None:
        """Aja yhden isännän kohteet sarjallisesti, tahtia noudattaen."""
        async with vuorot:
            loop = asyncio.get_running_loop()
            vali = 1.0 / RATE_LIMIT_PER_SECOND
            edellinen: float | None = None
            perakkaisia_rajoituksia = 0
            for jarjestys, kohde in enumerate(kohteet):
                probe_type = PROBE_TYPES[(kohde["format"] or "").upper()]
                prober = active.get(probe_type)
                if prober is None:
                    continue
                if edellinen is not None:
                    nyt = loop.time()
                    if nyt - edellinen < vali:
                        await asyncio.sleep(vali - (nyt - edellinen))
                edellinen = loop.time()

                tulos, havainnot = await _koeta(kohde, prober)

                # Palvelun oma ohje voittaa meidän arvauksemme — mutta vain
                # jos se on lyhyt. Pitkä odotus varaisi työntekijävuoron
                # muilta isänniltä enemmän kuin voittaisi tälle.
                if havainnot.rajoitettu:
                    odotus = havainnot.odotus()
                    if odotus is not None and odotus <= RATE_LIMIT_MAX_WAIT:
                        await asyncio.sleep(odotus)
                        tulos, havainnot = await _koeta(kohde, prober)

                if havainnot.rajoitettu:
                    # 429:ää **ei kirjata**. Se ei kerro resurssista mitään —
                    # palvelu ei edes katsonut sitä. Kirjattuna se väittäisi
                    # aineiston olevan rikki, ja koska ``select_targets``
                    # kohtelee kirjattua eri tavalla kuin probaamatonta, väärä
                    # tila jäisi elämään TTL:n ajaksi. Puuttuva tila on tässä
                    # rehellisempi kuin keksitty.
                    perakkaisia_rajoituksia += 1
                    if perakkaisia_rajoituksia >= RATE_LIMIT_GIVE_UP:
                        logger.warning(
                            "[probe] %s rajoittaa (%d peräkkäistä 429) — "
                            "%d kohdetta jätetään seuraavaan ajoon",
                            isanta,
                            perakkaisia_rajoituksia,
                            len(kohteet) - jarjestys - 1,
                        )
                        return
                    continue

                perakkaisia_rajoituksia = 0
                await jono.put((kohde, probe_type, tulos, havainnot))

    async def _kaikki_isannat() -> None:
        # Vartija ajetaan finallyssä: ilman sitä työntekijän poikkeus
        # jättäisi kuluttajan odottamaan jonoa ikuisesti.
        try:
            await asyncio.gather(*(_tyontekija(h, k) for h, k in ryhmat.items()))
        finally:
            await jono.put(None)

    tuottaja = asyncio.create_task(_kaikki_isannat())
    try:
        i = 0
        while True:
            paketti = await jono.get()
            if paketti is None:
                break
            target, probe_type, result, havainnot = paketti
            i += 1
            # Saatavuustiedot samasta noudosta. Erillinen try, koska
            # terveystiedon puuttuminen ei saa estää skeeman tallennusta.
            try:
                _store_health(conn, target, havainnot, timestamp)
            except Exception as e:
                logger.warning(
                    "[probe] %s terveystiedon kirjaus epäonnistui: %s",
                    target["id"],
                    e,
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
        # Nostaa työntekijässä tapahtuneen poikkeuksen. Ilman tätä ajo
        # päättyisi näennäisen siististi vaikka osa isännistä olisi kaatunut.
        await tuottaja
    finally:
        if not tuottaja.done():
            tuottaja.cancel()
            with suppress(asyncio.CancelledError):
                await tuottaja
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
