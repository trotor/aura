"""Taaksepäin yhteensopiva wrapper — käytä aura.harvesters-pakettia."""

from __future__ import annotations

import sqlite3

from aura.harvesters.avoindata import AvoindataHarvester


async def harvest_all(conn: sqlite3.Connection | None = None) -> int:
    """Hae kaikki datasetit avoindata.fi:stä."""
    harvester = AvoindataHarvester(conn=conn)
    return await harvester.harvest()
