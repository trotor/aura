"""Yhteinen pohjaluokka viiteaineistojen populaattoreille."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import httpx

from aura.constants import user_agent
from aura.database import get_connection, run_migrations

logger = logging.getLogger(__name__)

# Retry-asetukset (samat kuin BaseHarvester)
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 2.0
DEFAULT_RETRY_MAX_DELAY = 30.0
DEFAULT_REQUEST_DELAY = 0.2

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class BasePopulator(ABC):
    """Pohjaluokka viiteaineistojen populaattoreille."""

    name: str = "base"
    description: str = ""
    source_url: str = ""

    max_retries: int = DEFAULT_MAX_RETRIES
    request_delay: float = DEFAULT_REQUEST_DELAY

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        if conn is None:
            conn = get_connection()
        self.conn = conn
        run_migrations(conn)

    @abstractmethod
    async def populate(self) -> int:
        """Lataa viitedata. Palauttaa rivimäärän."""
        ...

    def is_populated(self) -> bool:
        """Onko ref_metadata-rivi olemassa ja record_count > 0."""
        row = self.conn.execute(
            "SELECT record_count FROM ref_metadata WHERE name = ?",
            (self.name,),
        ).fetchone()
        return row is not None and row["record_count"] > 0

    def needs_update(self, max_age_days: int = 30) -> bool:
        """Onko populated_at vanhempi kuin max_age_days."""
        row = self.conn.execute(
            "SELECT populated_at FROM ref_metadata WHERE name = ?",
            (self.name,),
        ).fetchone()
        if row is None:
            return True
        populated_at = datetime.fromisoformat(row["populated_at"])
        age = datetime.now(UTC) - populated_at.replace(tzinfo=UTC)
        return age.days >= max_age_days

    def _update_metadata(self, record_count: int, version: str = "") -> None:
        """Päivitä ref_metadata upsertilla."""
        self.conn.execute(
            """
            INSERT INTO ref_metadata (name, record_count, version, populated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                record_count = excluded.record_count,
                version = excluded.version,
                populated_at = excluded.populated_at
            """,
            (self.name, record_count, version),
        )
        self.conn.commit()

    def _make_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """Luo HTTP-asiakas yhteisillä asetuksilla."""
        return httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent()},
        )

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """HTTP GET retryllä ja rate limitingillä."""
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            if attempt > 1 or self.request_delay > 0:
                await asyncio.sleep(self.request_delay)

            try:
                response = await client.get(url, **kwargs)

                if response.status_code == 429:
                    retry_after = float(
                        response.headers.get("Retry-After", DEFAULT_RETRY_BASE_DELAY)
                    )
                    logger.warning(
                        "[%s] 429 Too Many Requests, odotetaan %.0fs (yritys %d/%d)",
                        self.name, retry_after, attempt, self.max_retries,
                    )
                    await asyncio.sleep(retry_after)
                    last_exc = httpx.HTTPStatusError(
                        "429", request=response.request, response=response,
                    )
                    continue

                if response.status_code in RETRYABLE_STATUS_CODES:
                    delay = min(
                        DEFAULT_RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                        DEFAULT_RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "[%s] HTTP %d, retry %.0fs (yritys %d/%d)",
                        self.name, response.status_code,
                        delay, attempt, self.max_retries,
                    )
                    await asyncio.sleep(delay)
                    last_exc = httpx.HTTPStatusError(
                        str(response.status_code),
                        request=response.request,
                        response=response,
                    )
                    continue

                response.raise_for_status()
                return response

            except httpx.TransportError as exc:
                delay = min(
                    DEFAULT_RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                    DEFAULT_RETRY_MAX_DELAY,
                )
                logger.warning(
                    "[%s] Verkkovirhe: %s, retry %.0fs (yritys %d/%d)",
                    self.name, exc, delay, attempt, self.max_retries,
                )
                await asyncio.sleep(delay)
                last_exc = exc

        if last_exc is not None:
            raise last_exc
        msg = f"[{self.name}] _fetch epäonnistui ilman poikkeusta"
        raise RuntimeError(msg)
