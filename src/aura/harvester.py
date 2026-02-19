"""Datan keräys avoindata.fi:n CKAN API:sta."""

from __future__ import annotations

import logging
import sqlite3

import httpx

from aura.database import get_connection, init_db, upsert_dataset
from aura.models import Dataset

logger = logging.getLogger(__name__)

CKAN_BASE_URL = "https://avoindata.suomi.fi/data/api/3/action"
DEFAULT_BATCH_SIZE = 100


async def fetch_datasets(
    client: httpx.AsyncClient,
    rows: int = DEFAULT_BATCH_SIZE,
    start: int = 0,
) -> dict:
    """Hae datasettejä CKAN API:sta."""
    response = await client.get(
        f"{CKAN_BASE_URL}/package_search",
        params={"rows": rows, "start": start, "sort": "metadata_modified desc"},
    )
    response.raise_for_status()
    return response.json()


async def harvest_all(conn: sqlite3.Connection | None = None) -> int:
    """Hae kaikki datasetit avoindata.fi:stä ja tallenna tietokantaan.

    Returns:
        Haettujen datasettien lukumäärä.
    """
    if conn is None:
        conn = get_connection()
    init_db(conn)

    total_harvested = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Hae ensin kokonaismäärä
        result = await fetch_datasets(client, rows=1, start=0)
        total_count = result["result"]["count"]
        logger.info("Datasettejä yhteensä: %d", total_count)

        # Hae kaikki erinä
        start = 0
        while start < total_count:
            result = await fetch_datasets(client, rows=DEFAULT_BATCH_SIZE, start=start)
            datasets = result["result"]["results"]

            for raw in datasets:
                dataset = Dataset.from_ckan(raw)
                upsert_dataset(conn, dataset)
                total_harvested += 1

            conn.commit()
            start += DEFAULT_BATCH_SIZE
            logger.info("Haettu %d / %d", min(start, total_count), total_count)

    logger.info("Harvest valmis: %d datasettiä", total_harvested)
    return total_harvested
