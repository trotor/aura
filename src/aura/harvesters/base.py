"""Yhteinen pohjaluokka kaikille harvestereille."""

from __future__ import annotations

import logging
import sqlite3
from abc import ABC, abstractmethod

import httpx

from aura.database import get_connection, init_db

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
