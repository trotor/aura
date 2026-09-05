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

    #: Lähteet jotka kaatuivat, syineen. Erillään ``counts``:sta
    #: tarkoituksella: kaatunut lähde on **mittaamaton**, ei tyhjä, ja nolla
    #: määränä tarkoittaisi "haettiin, ei löytynyt mitään".
    failures: dict[str, str] = field(default_factory=dict)


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
        try:
            count = await harvester.harvest()
        except Exception as exc:
            # Yksi kaatuva lähde ei saa viedä koko keruuta. Mitattu 5.9.2026:
            # opendata.luke.fi oli lakannut olemasta CKAN-instanssi ja vastasi
            # 302:lla, harvesteri nosti käsittelemättömän poikkeuksen, ja ajo
            # päättyi siihen — 41 lähteestä kolmea ei yritetty lainkaan.
            # Yksi ohitetuista oli sotkanet, katalogin suurin lähde.
            #
            # Nieleminen vaihtaisi vian vain toiseen, joten syy kerätään
            # talteen ja raportoidaan. Docstring varoittaa hiljaisesta
            # nollasta; tämä on sen peilikuva.
            if source != "all":
                # Nimetty lähde: ei ole mitään jonka puolesta jatkaa, ja
                # hiljainen tyhjä tulos näyttäisi komentorivillä onnistumiselta.
                raise
            outcome.failures[name] = f"{type(exc).__name__}: {exc}"[:200]
            logger.error("[harvest] %s kaatui: %s", name, exc)
            if on_progress:
                on_progress(name, None)
            continue

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
