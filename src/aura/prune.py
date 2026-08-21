"""Vanhentuneiden datasettien poisto.

Harvestointi upsertaa eikä poista koskaan, joten kantaan kertyy rivejä
aineistoista jotka on poistettu lähteestä — tai joiden tunniste on lähteessä
muuttunut. Jälkimmäinen on merkittävämpi: Tilastokeskus vaihtoi PxWeb-taulujen
tunniste- ja osoiteskeeman kesken vuoden 2026, jolloin 1 593 riviä jäi kantaan
osoitteilla jotka vastaavat HTTP 400:lla.

**Turvasääntö.** Datasetti katsotaan vanhentuneeksi vasta kun sitä ei ole nähty
``STALE_AFTER_DAYS`` päivään *lähteen viimeisimmästä harvestoinnista laskien*.
Kaksi syytä:

1. Yksittäinen epäonnistunut ajo ei saa poistaa mitään. ``CkanHarvester``
   ohittaa HTTP-virheen sattuessa kokonaisen sadan datasetin sivun, ja ajo
   päättyy silti onnistuneena. Ikäraja antaa niiden palata seuraavassa ajossa.
2. Vertailukohta on lähteen oma viimeisin ajo, ei nykyhetki. Muuten lähde jota
   ei ole harvestoitu puoleen vuoteen tyhjenisi kokonaan.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Kuinka monta päivää lähteen viimeisimmästä ajosta datasetin on oltava
# näkemättä ennen kuin se katsotaan poistetuksi.
STALE_AFTER_DAYS = 30

# Taulut joissa on dataset_id ja jotka on siivottava käsin: kannassa ei ole
# vierasavainpakotusta (PRAGMA foreign_keys = 0).
RELATED_TABLES = (
    "resources",
    "enrichments",
    "quality_scores",
    "resource_health",
    "resource_schema",
    "probe_results",
)

# Rikastukset joita harvesteri ei ole itse tuottanut. Näiden takana on ihmisen
# tai agentin työtä, joka ei saa kadota hiljaa.
AUTOMATIC_SOURCE_TYPES = ("harvest",)


@dataclass
class StaleReport:
    """Yhden lähteen tilanne."""

    source: str
    latest_harvest: str
    stale: int
    remaining: int


# Kuinka suuri pudotus edellisestä ajosta katsotaan epäilyttäväksi.
DROP_WARNING_RATIO = 0.2


def check_count_regression(
    conn: sqlite3.Connection, source: str, count: int
) -> str:
    """Vertaa juuri harvestoitua määrää edelliseen ajoon.

    Harvesterit jotka nappaavat fetch-poikkeuksen ja palauttavat tyhjän listan
    muuttavat ylävirran rikkoutumisen **hiljaiseksi nollaksi**: ajo päättyy
    exit-koodilla 0 eikä mikään kerro että data katosi. Näin kävi
    Valtiokonttorille (48 → 0) ja SYKElle (642 → 542, yksi pudonnut sivu).

    Palauttaa varoitustekstin tai tyhjän merkkijonon. Kutsutaan ennen kuin
    ``sources``-taulun rivi ylikirjoitetaan.
    """
    row = conn.execute(
        "SELECT dataset_count FROM sources WHERE name = ?", (source,)
    ).fetchone()
    if row is None:
        return ""
    previous = int(row[0] or 0)
    if previous <= 0:
        return ""

    if count == 0:
        return f"{source}: 0 datasettiä (edellinen ajo {previous}) — lähde rikki?"
    if count < previous * (1 - DROP_WARNING_RATIO):
        pudotus = round((1 - count / previous) * 100)
        return (
            f"{source}: {count} datasettiä, edellinen ajo {previous} "
            f"(−{pudotus} %) — tarkista onko lähde muuttunut vai ajo vajaa"
        )
    return ""


def _stale_where(source: str) -> tuple[str, list[Any]]:
    """WHERE-ehto vanhentuneille riveille, sekä sen parametrit."""
    clause = """
        d.harvested_at != ''
        AND julianday(t.viimeisin) - julianday(d.harvested_at) > ?
    """
    params: list[Any] = []
    if source:
        clause += " AND d.source = ?"
        params.append(source)
    return clause, params


def stale_dataset_ids(
    conn: sqlite3.Connection, days: int = STALE_AFTER_DAYS, source: str = ""
) -> list[str]:
    """Vanhentuneiden datasettien tunnisteet, aakkosjärjestyksessä."""
    clause, extra = _stale_where(source)
    rows = conn.execute(
        f"""
        WITH tuorein AS (
            SELECT source, MAX(harvested_at) AS viimeisin
            FROM datasets WHERE harvested_at != '' GROUP BY source
        )
        SELECT d.id FROM datasets d
        JOIN tuorein t ON t.source = d.source
        WHERE {clause}
        ORDER BY d.id
        """,
        [days, *extra],
    ).fetchall()
    return [str(row[0]) for row in rows]


def find_stale(
    conn: sqlite3.Connection, days: int = STALE_AFTER_DAYS, source: str = ""
) -> list[StaleReport]:
    """Lähdekohtainen yhteenveto. Lähteet joilla ei ole vanhentuneita ohitetaan."""
    clause, extra = _stale_where(source)
    rows = conn.execute(
        f"""
        WITH tuorein AS (
            SELECT source, MAX(harvested_at) AS viimeisin
            FROM datasets WHERE harvested_at != '' GROUP BY source
        )
        SELECT d.source, t.viimeisin,
               SUM(CASE WHEN {clause} THEN 1 ELSE 0 END) AS vanhentuneita,
               COUNT(*) AS yhteensa
        FROM datasets d
        JOIN tuorein t ON t.source = d.source
        GROUP BY d.source, t.viimeisin
        HAVING vanhentuneita > 0
        ORDER BY vanhentuneita DESC
        """,
        [days, *extra],
    ).fetchall()
    return [
        StaleReport(
            source=str(row[0]),
            latest_harvest=str(row[1]),
            stale=int(row[2]),
            remaining=int(row[3]) - int(row[2]),
        )
        for row in rows
    ]


def curated_enrichments(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> list[dict[str, Any]]:
    """Rikastukset joita harvesteri ei tuottanut — ihmisen tai agentin työtä."""
    if not dataset_ids:
        return []
    placeholders = ",".join("?" for _ in dataset_ids)
    automatic = ",".join("?" for _ in AUTOMATIC_SOURCE_TYPES)
    rows = conn.execute(
        f"""
        SELECT * FROM enrichments
        WHERE dataset_id IN ({placeholders})
          AND COALESCE(source_type, '') NOT IN ({automatic})
        """,
        [*dataset_ids, *AUTOMATIC_SOURCE_TYPES],
    ).fetchall()
    return [dict(row) for row in rows]


def prune_datasets(
    conn: sqlite3.Connection,
    days: int = STALE_AFTER_DAYS,
    source: str = "",
    *,
    apply: bool = False,
    force: bool = False,
) -> dict[str, int]:
    """Poista vanhentuneet datasetit ja niihin liittyvät rivit.

    Args:
        days: Kuinka monta päivää lähteen viimeisimmästä ajosta datasetin on
            oltava näkemättä.
        source: Rajaa yhteen lähteeseen. Tyhjä = kaikki.
        apply: Ilman tätä kyseessä on kuiva-ajo — mitään ei poisteta.
        force: Salli poisto vaikka mukana olisi kuratoituja rikastuksia.

    Raises:
        ValueError: Jos poisto hävittäisi kuratoituja rikastuksia eikä
            ``force`` ole asetettu.
    """
    ids = stale_dataset_ids(conn, days=days, source=source)
    curated = curated_enrichments(conn, ids)
    stats = {"datasets": len(ids), "curated_enrichments": len(curated)}

    if not ids:
        return stats

    if curated and apply and not force:
        raise ValueError(
            f"Poisto hävittäisi {len(curated)} kuratoitua rikastusta "
            f"({len({c['dataset_id'] for c in curated})} datasetissä). "
            "Vie ne talteen (aura export-enrichments) tai käytä --force."
        )

    if not apply:
        return stats

    placeholders = ",".join("?" for _ in ids)
    for table in RELATED_TABLES:
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE dataset_id IN ({placeholders})", ids
        )
        stats[table] = cursor.rowcount

    # datasets_fts pysyy synkassa datasets_ad-triggerin kautta.
    conn.execute(f"DELETE FROM datasets WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    logger.info("[prune] Poistettu %d datasettiä", len(ids))
    return stats
