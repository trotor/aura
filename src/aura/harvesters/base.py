"""Yhteinen pohjaluokka kaikille harvestereille."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import httpx

from aura.constants import user_agent
from aura.database import add_enrichment, get_connection, init_db
from aura.models import Dataset
from aura.url_normalize import normalize_resource_url

logger = logging.getLogger(__name__)

# Retry-asetukset
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 2.0  # sekuntia
DEFAULT_RETRY_MAX_DELAY = 30.0  # sekuntia
DEFAULT_REQUEST_DELAY = 0.2  # sekuntia pyyntöjen välillä

# HTTP-statuskoodit joita yritetään uudelleen
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class BaseHarvester(ABC):
    """Pohjaluokka datalähteiden keräimille."""

    name: str = "base"
    description: str = ""
    url: str = ""

    # Aliluokat voivat yliajaa
    max_retries: int = DEFAULT_MAX_RETRIES
    request_delay: float = DEFAULT_REQUEST_DELAY

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        """Palauta lähteen konfiguraatio sources-taulua varten.

        Aliluokat voivat ylikirjoittaa lisätäkseen harvester_type,
        query_protocol ja api_base_url.
        """
        return {
            "name": cls.name,
            "description": cls.description,
            "url": cls.url,
            "harvester_type": "custom",
            "query_protocol": "none",
            "api_base_url": "",
        }

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        if conn is None:
            conn = get_connection()
        self.conn = conn
        init_db(conn)

    @abstractmethod
    async def harvest(self) -> int:
        """Hae kaikki datasetit lähteestä ja tallenna tietokantaan.

        Returns:
            Haettujen datasettien lukumäärä.
        """
        ...

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
        """HTTP GET retryllä ja rate limitingillä.

        - Eksponentiaalinen backoff transienteille virheille
        - 429 Retry-After -headerin kunnioitus
        - Pyyntöviive rate limitingiä varten
        """
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            # Rate limit: odota ennen pyyntöä
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

        # Kaikki yritykset käytetty
        if last_exc is not None:
            raise last_exc
        msg = f"[{self.name}] _fetch epäonnistui ilman poikkeusta"
        raise RuntimeError(msg)

    def _make_dataset(self, **kwargs: Any) -> Dataset:
        """Luo Dataset oletusarvoilla.

        Asettaa automaattisesti:
            - license_id: cc-by-4.0
            - license_title: CC BY 4.0
            - collection_type: Open Data
            - geographical_coverage: ["Suomi"]
            - source: self.name
            - metadata_modified: ISO-aikaleima (jos ei annettu)
        """
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
        defaults: dict[str, Any] = {
            "license_id": "cc-by-4.0",
            "license_title": "CC BY 4.0",
            "collection_type": "Open Data",
            "geographical_coverage": ["Suomi"],
            "source": self.name,
            "access_level": "open",
            "metadata_modified": now,
        }
        defaults.update(kwargs)
        dataset = Dataset(**defaults)
        _normalize_resource_urls(dataset)
        return dataset

    # Paikkatietoformaatit joille CRS on relevantti
    _SPATIAL_FORMATS = {"WFS", "WMS", "WCS", "GEOJSON", "GPKG", "SHP", "GML", "KML"}

    def _auto_enrich_crs(self, dataset: Dataset) -> None:
        """Aseta CRS-enrichment automaattisesti paikkatietoresursseille (#116).

        Suomalaisille paikkatietoaineistoille oletus on EPSG:3067 (ETRS-TM35FIN).
        """
        formats = {(r.format or "").upper() for r in dataset.resources}
        if not formats & self._SPATIAL_FORMATS:
            return

        # Oletus suomalaisille: EPSG:3067
        geo = dataset.geographical_coverage
        is_finnish = any(
            g.lower() in ("suomi", "finland") for g in geo
        ) if geo else True  # oletuksena suomalainen

        crs = "EPSG:3067" if is_finnish else "EPSG:4326"
        self._add_enrichment(dataset.id, "crs", crs)

    def _add_enrichment(
        self,
        dataset_id: str,
        field: str,
        value: str,
        *,
        confidence: str = "high",
        source_detail: str = "",
    ) -> None:
        """Lisää harvest-aikainen enrichment idempotentisti.

        Tarkistaa onko sama (dataset_id, field, value) jo olemassa
        ennen kuin luo uuden. Ei commitoi — kutsujan vastuulla.
        """
        if not value or not value.strip():
            return
        existing = self.conn.execute(
            """
            SELECT 1 FROM enrichments
            WHERE dataset_id = ? AND field = ? AND value = ?
            LIMIT 1
            """,
            (dataset_id, field, value),
        ).fetchone()
        if existing:
            return
        add_enrichment(
            self.conn, dataset_id, field, value,
            confidence=confidence,
            source_type="harvest",
            source_detail=source_detail or self.name,
        )


def _normalize_resource_urls(dataset: Dataset) -> None:
    """Korjaa datasetin resurssien tunnetusti rikkinäiset URL:t paikallaan.

    Tehdään täällä eikä yksittäisissä harvestereissa, koska ongelmaluokka ei
    ole lähdekohtainen: ylävirran katalogi julkaisee toimimattoman osoitteen,
    ja Aura tallentaa sen uskollisesti. Ks. aura.url_normalize — säännöt ovat
    kapeita ja tuntematon osoite palautuu koskemattomana.
    """
    for resource in dataset.resources:
        korjattu = normalize_resource_url(resource.url)
        if korjattu != resource.url:
            logger.info(
                "[%s] URL normalisoitu: %s -> %s",
                dataset.source or "?", resource.url, korjattu,
            )
            resource.url = korjattu
