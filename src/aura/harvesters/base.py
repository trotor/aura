"""Yhteinen pohjaluokka kaikille harvestereille."""

from __future__ import annotations

import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import Any

import httpx

from aura.database import get_connection, init_db
from aura.models import Dataset

logger = logging.getLogger(__name__)


class BaseHarvester(ABC):
    """Pohjaluokka datalähteiden keräimille."""

    name: str = "base"
    description: str = ""
    url: str = ""

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
            headers={"User-Agent": "Aura/0.1.0 (https://github.com/trotor/aura)"},
        )

    def _make_dataset(self, **kwargs: Any) -> Dataset:
        """Luo Dataset oletusarvoilla.

        Asettaa automaattisesti:
            - license_id: cc-by-4.0
            - license_title: CC BY 4.0
            - collection_type: Open Data
            - geographical_coverage: ["Suomi"]
            - source: self.name
        """
        defaults: dict[str, Any] = {
            "license_id": "cc-by-4.0",
            "license_title": "CC BY 4.0",
            "collection_type": "Open Data",
            "geographical_coverage": ["Suomi"],
            "source": self.name,
        }
        defaults.update(kwargs)
        return Dataset(**defaults)
