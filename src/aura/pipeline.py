"""Jaettu harvestointiputki.

Harvestointi tapahtui aiemmin kahdessa paikassa — ``aura harvest`` ja
``aura refresh`` — ja ne ehtivät eriytyä: määrävertailu oli vain toisessa,
eikä kumpikaan indeksoinut lemmoja. Molemmat virheet purivat käytännössä
saman päivän aikana (SYKEn pudonnut sivu jäi huomaamatta; uudet rivit
jäivät näkymättömiksi perusmuotohaulle).

Tämä moduuli on se yksi paikka jossa harvestointi tapahtuu.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from aura.database import upsert_source
from aura.harvesters import get_all_harvesters, get_harvester
from aura.harvesters.static import StaticHarvester
from aura.prune import check_count_regression

logger = logging.getLogger(__name__)

# (lähteen nimi, määrä tai None kun aloitetaan)
ProgressCallback = Callable[[str, int | None], None]


@dataclass
class HarvestOutcome:
    """Yhden harvestointiajon tulos."""

    total: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


async def harvest_sources(
    conn: sqlite3.Connection,
    *,
    source: str = "all",
    include_static: bool = False,
    now: str = "",
    on_progress: ProgressCallback | None = None,
) -> HarvestOutcome:
    """Harvestoi yksi lähde tai kaikki, jaettuun yhteyteen.

    Vertaa jokaisen lähteen tulosta edelliseen ajoon **ennen** kuin
    ``sources``-rivi ylikirjoitetaan, ja kerää varoitukset talteen. Harvesterit
    jotka nappaavat fetch-poikkeuksen ja palauttavat tyhjän listan muuttavat
    ylävirran rikkoutumisen hiljaiseksi nollaksi, joka näyttää onnistuneelta
    ajolta.
    """
    timestamp = now or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")
    outcome = HarvestOutcome()

    if source == "all":
        candidates = list(get_all_harvesters().items())
    else:
        candidates = [(source, get_harvester(source))]

    for name, cls in candidates:
        if (
            source == "all"
            and issubclass(cls, StaticHarvester)
            and not include_static
        ):
            outcome.skipped.append(name)
            continue

        if on_progress:
            on_progress(name, None)

        harvester = cls(conn=conn)
        count = await harvester.harvest()
        outcome.counts[name] = count
        outcome.total += count

        warning = check_count_regression(conn, name, count)
        if warning:
            outcome.warnings.append(warning)
            logger.warning("[harvest] %s", warning)

        src_cfg = cls.source_config()
        src_cfg["dataset_count"] = count
        src_cfg["last_harvested_at"] = timestamp
        upsert_source(conn, src_cfg)

        if on_progress:
            on_progress(name, count)

    conn.commit()
    return outcome
