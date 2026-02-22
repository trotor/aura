"""Resurssien saatavuustarkistus (health check)."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Asetukset
DEFAULT_TIMEOUT = 15.0  # sekuntia per pyyntö
DEFAULT_MAX_CONCURRENT = 10  # samanaikaisia pyyntöjä
DEFAULT_RATE_PER_SECOND = 5  # pyyntöä/sekunti per domain
DEFAULT_STALE_DAYS = 7  # tarkista uudelleen N päivän jälkeen

# URL-patternit joille HEAD ei yleensä toimi
SKIP_HEAD_PATTERNS = ("wfs", "wms", "wcs", "ows", "geoserver")


class TokenBucket:
    """Token bucket -pohjainen rate limiter (pyyntöjä/sekunti)."""

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens = rate
        self._last = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self._rate, self._tokens + self._rate * (now - self._last))
        self._last = now

    async def acquire(self) -> None:
        """Odota kunnes token on saatavilla."""
        while True:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            await asyncio.sleep(1.0 / self._rate)


@dataclass
class HealthResult:
    """Yksittäisen resurssin tarkistustulos."""

    resource_id: str
    dataset_id: str
    url: str
    status_code: int | None = None
    response_time_ms: int | None = None
    content_type: str | None = None
    content_length: int | None = None
    is_available: bool = False
    error_message: str | None = None
    checked_at: str = ""

    def __post_init__(self) -> None:
        if not self.checked_at:
            self.checked_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class HealthSummary:
    """Tarkistuksen kokonaistulokset."""

    total: int = 0
    available: int = 0
    unavailable: int = 0
    errors: int = 0
    avg_response_ms: float = 0.0
    results: list[HealthResult] = field(default_factory=list)

    @property
    def availability_pct(self) -> float:
        """Saatavuusprosentti."""
        if self.total == 0:
            return 0.0
        return 100.0 * self.available / self.total


async def check_resource(
    client: httpx.AsyncClient,
    resource_id: str,
    dataset_id: str,
    url: str,
) -> HealthResult:
    """Tarkista yksittäisen resurssin saatavuus.

    Käyttää HEAD-pyyntöä, fallback GET:iin jos HEAD epäonnistuu.
    """
    result = HealthResult(
        resource_id=resource_id,
        dataset_id=dataset_id,
        url=url,
    )

    if not url or not url.startswith(("http://", "https://")):
        result.error_message = "Virheellinen URL"
        return result

    # Kokeile HEAD ensin (ellei tunneta ongelmalliseksi)
    use_head = not any(p in url.lower() for p in SKIP_HEAD_PATTERNS)
    methods = ["HEAD", "GET"] if use_head else ["GET"]

    for method in methods:
        start = time.monotonic()
        try:
            if method == "HEAD":
                response = await client.head(url, follow_redirects=True)
            else:
                # GET: lue vain headerit, älä lataa bodya
                response = await client.get(
                    url, follow_redirects=True,
                    headers={"Range": "bytes=0-0"},
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)

            result.status_code = response.status_code
            result.response_time_ms = elapsed_ms
            result.content_type = response.headers.get("content-type", "")
            cl = response.headers.get("content-length")
            if cl and cl.isdigit():
                result.content_length = int(cl)

            if response.status_code < 400:
                result.is_available = True
                return result

            # HEAD sai virheen — kokeile GET
            if method == "HEAD":
                continue

            result.error_message = f"HTTP {response.status_code}"
            return result

        except httpx.TimeoutException:
            result.error_message = "Timeout"
            result.response_time_ms = int(
                (time.monotonic() - start) * 1000
            )
            return result
        except httpx.TransportError as e:
            result.error_message = str(e)[:200]
            return result

    return result


def save_health_result(
    conn: sqlite3.Connection,
    result: HealthResult,
) -> None:
    """Tallenna tarkistustulos tietokantaan."""
    conn.execute(
        """
        INSERT OR REPLACE INTO resource_health
            (resource_id, dataset_id, url, status_code, response_time_ms,
             content_type, content_length, is_available, error_message, checked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.resource_id,
            result.dataset_id,
            result.url,
            result.status_code,
            result.response_time_ms,
            result.content_type,
            result.content_length,
            result.is_available,
            result.error_message,
            result.checked_at,
        ),
    )


def get_resources_to_check(
    conn: sqlite3.Connection,
    source: str = "",
    stale_days: int = DEFAULT_STALE_DAYS,
) -> list[dict[str, str]]:
    """Hae resurssit jotka tarvitsevat tarkistusta.

    Palauttaa resurssit joita ei ole tarkistettu tai joiden tarkistus
    on vanhempi kuin stale_days päivää.
    """
    cutoff = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    # Yksinkertaistettu: vähennetään päivät ISO-merkkijonosta
    # SQLite osaa vertailla ISO-aikaleimoja merkkijonoina

    query = """
        SELECT r.id as resource_id, r.dataset_id, r.url
        FROM resources r
        JOIN datasets d ON r.dataset_id = d.id
        LEFT JOIN resource_health h ON r.id = h.resource_id
        WHERE r.url IS NOT NULL
          AND r.url != ''
          AND r.url LIKE 'http%'
    """
    params: list[Any] = []

    if source:
        query += " AND d.source = ?"
        params.append(source)

    query += """
          AND (h.checked_at IS NULL
               OR julianday(?) - julianday(h.checked_at) > ?)
        ORDER BY h.checked_at IS NULL DESC, h.checked_at ASC
    """
    params.extend([cutoff, stale_days])

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


async def check_all_resources(
    conn: sqlite3.Connection,
    source: str = "",
    stale_days: int = DEFAULT_STALE_DAYS,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    timeout: float = DEFAULT_TIMEOUT,
    limit: int = 0,
) -> HealthSummary:
    """Tarkista kaikkien resurssien saatavuus.

    Args:
        conn: Tietokantayhteys.
        source: Rajaa tiettyyn lähteeseen.
        stale_days: Ohita alle N päivää vanhat tarkistukset.
        max_concurrent: Samanaikaisten pyyntöjen maksimi.
        timeout: HTTP-timeout sekunteina.
        limit: Rajoita tarkistettavien resurssien määrää (0 = kaikki).

    Returns:
        Kokonaistulokset.
    """
    resources = get_resources_to_check(conn, source=source, stale_days=stale_days)
    if limit > 0:
        resources = resources[:limit]

    if not resources:
        return HealthSummary()

    summary = HealthSummary(total=len(resources))

    # Rate limiter: token bucket per domain
    from urllib.parse import urlparse

    domain_buckets: dict[str, TokenBucket] = defaultdict(
        lambda: TokenBucket(DEFAULT_RATE_PER_SECOND)
    )
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": "Aura/0.2.0 health-check"},
    ) as client:

        async def _check_one(res: dict[str, str]) -> HealthResult:
            async with semaphore:
                domain = urlparse(res["url"]).netloc
                await domain_buckets[domain].acquire()
                return await check_resource(
                    client,
                    res["resource_id"],
                    res["dataset_id"],
                    res["url"],
                )

        tasks = [_check_one(r) for r in resources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    response_times: list[int] = []

    for r in results:
        if isinstance(r, BaseException):
            summary.errors += 1
            continue

        result: HealthResult = r
        summary.results.append(result)
        save_health_result(conn, result)

        if result.is_available:
            summary.available += 1
        else:
            summary.unavailable += 1

        if result.response_time_ms is not None:
            response_times.append(result.response_time_ms)

    conn.commit()

    if response_times:
        summary.avg_response_ms = sum(response_times) / len(response_times)

    logger.info(
        "[health] Tarkistettu %d resurssia: %d saatavilla, %d ei saatavilla, %d virhettä",
        summary.total, summary.available, summary.unavailable, summary.errors,
    )

    return summary


def get_health_summary(
    conn: sqlite3.Connection,
    source: str = "",
) -> dict[str, Any]:
    """Hae health check -yhteenveto tietokannasta."""
    query = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN h.is_available THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN NOT h.is_available THEN 1 ELSE 0 END) as unavailable,
            ROUND(AVG(h.response_time_ms), 0) as avg_response_ms,
            MIN(h.checked_at) as oldest_check,
            MAX(h.checked_at) as newest_check
        FROM resource_health h
    """
    params: list[str] = []
    if source:
        query += " JOIN datasets d ON h.dataset_id = d.id WHERE d.source = ?"
        params.append(source)

    row = conn.execute(query, params).fetchone()
    if not row or row["total"] == 0:
        return {"total": 0}

    return dict(row)


def get_unavailable_resources(
    conn: sqlite3.Connection,
    source: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Hae ei-saatavilla olevat resurssit."""
    query = """
        SELECT h.resource_id, h.dataset_id, h.url,
               h.status_code, h.error_message, h.checked_at,
               COALESCE(d.title_fi, d.title) as dataset_title,
               d.source
        FROM resource_health h
        JOIN datasets d ON h.dataset_id = d.id
        WHERE NOT h.is_available
    """
    params: list[Any] = []
    if source:
        query += " AND d.source = ?"
        params.append(source)

    query += " ORDER BY h.checked_at DESC LIMIT ?"
    params.append(limit)

    return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_dataset_health(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Hae yksittäisen datasetin resurssien health-tiedot."""
    rows = conn.execute(
        """
        SELECT resource_id, url, status_code, response_time_ms,
               content_type, content_length, is_available,
               error_message, checked_at
        FROM resource_health
        WHERE dataset_id = ?
        ORDER BY url
        """,
        (dataset_id,),
    ).fetchall()
    return [dict(r) for r in rows]
