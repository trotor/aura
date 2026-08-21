"""Nollatuloskirjaus: mitä haettiin kun mitään ei löytynyt.

**Miksi.** Koko katalogin aukkoja on tähän asti arvattu käsin. Tämän session
löydöt — Finavian lentoliikennetilastot, Traficomin tilastotietokanta,
Suomi.fi-koodistot — löytyivät siksi että joku *epäili* niiden puuttuvan, ei
siksi että joku olisi etsinyt niitä turhaan ja se olisi jäänyt talteen.
Nollatulos on ainoa signaali jossa käyttäjä kertoo suoraan mitä katalogista
puuttuu.

**Mitä tallennetaan.** Vain hakusana ja laskuri. Ei istuntoa, ei
tunnistetta, ei IP:tä, ei tapahtumakohtaista aikaleimaa — vain ensimmäinen ja
viimeinen esiintymä. Sama kysely on yksi rivi jonka `count` kasvaa, ei
kasvava tapahtumaloki. Tämä on tarkoituksellisesti kaikkein suppein muoto
jolla kysymykseen "mitä etsittiin turhaan" voi vastata.

**Missä.** Omassa kannassaan, ei katalogissa. Katalogi avataan tuotannossa
lukutilassa ja kontti ajetaan ``--read-only``, joten katalogiin kirjoittaminen
ei ole vaihtoehto — eikä sen kuuluisi olla, koska johdettu kanta on
muuttumaton artefakti.

**Vikasietoisuus on tärkein ominaisuus.** Jos kirjoitus ei onnistu — polku
puuttuu, levy on kirjoitussuojattu, kanta on lukossa — se ohitetaan
hiljaisesti. Telemetria ei ole syy jonka takia haku saa kaatua. Siksi jokainen
kutsu on ``try``:n sisällä ja virhe menee vain debug-lokiin.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

#: Ympäristömuuttuja jolla telemetriakanta osoitetaan. Tyhjä = pois käytöstä.
TELEMETRY_DB_ENV = "AURA_TELEMETRY_DB"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS zero_results (
    query      TEXT PRIMARY KEY,
    count      INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);
"""

# Ylipitkä kysely ei ole hakusana vaan liite. Katkaisu rajaa myös sen
# määrän henkilötietoa joka voi vahingossa päätyä kenttään.
MAX_QUERY_LENGTH = 200

# Ohjausmerkit pois. **Tämä on turvallisuuskorjaus, ei siistimistä.**
#
# Kysely tulee etäkäyttäjältä ja päätyy ylläpitäjän terminaaliin komennolla
# ``aura gaps``. Ilman suodatusta hakuun voi upottaa ANSI-koodeja, jotka
# terminaali tottelee: rivin voi pyyhkiä, tekstiä voi väärentää (``\x1b[2K``
# + oma teksti näyttää työkalun omalta tulosteelta) ja joissakin
# terminaaleissa pahempaakin. Whitespace-normalisointi ei riitä, koska ESC
# ei ole whitespacea.
#
# Suodatus tehdään **kirjoitettaessa**, jotta kanta ei koskaan sisällä
# ohjausmerkkejä — silloin mikään lukija ei voi vahingossa tulostaa niitä.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def telemetry_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Telemetriakannan polku, tai None jos kirjaus ei ole käytössä.

    Kirjaus on **oletuksena pois päältä**. Se kytketään päälle asettamalla
    ``AURA_TELEMETRY_DB``, koska kyselytekstin tallentaminen on
    tietosuojapäätös eikä oletusarvo.
    """
    if env is None:
        env = os.environ
    raw = env.get(TELEMETRY_DB_ENV, "").strip()
    return Path(raw) if raw else None


def record_zero_result(query: str, env: Mapping[str, str] | None = None) -> bool:
    """Kirjaa nollatuloksellinen kysely. Palauttaa True jos kirjaus onnistui.

    Ei koskaan nosta poikkeusta: kutsuja on hakupolulla.
    """
    cleaned = " ".join(_CONTROL_CHARS.sub(" ", query).split())[:MAX_QUERY_LENGTH]
    if not cleaned:
        return False

    path = telemetry_path(env)
    if path is None:
        return False

    now = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=2.0) as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                """
                INSERT INTO zero_results (query, count, first_seen, last_seen)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(query) DO UPDATE SET
                    count = count + 1,
                    last_seen = excluded.last_seen
                """,
                (cleaned, now, now),
            )
        return True
    except (sqlite3.Error, OSError) as exc:
        # Hiljainen ohitus on tässä oikea käytös: kirjoitussuojattu
        # tiedostojärjestelmä on tuotannon **tarkoitettu** tila.
        logger.debug("[telemetry] Nollatuloksen kirjaus ohitettiin: %s", exc)
        return False


def zero_result_gaps(
    limit: int = 50, env: Mapping[str, str] | None = None
) -> list[dict[str, object]]:
    """Yleisimmät nollatulokselliset kyselyt, yleisin ensin."""
    path = telemetry_path(env)
    if path is None or not path.exists():
        return []
    try:
        with sqlite3.connect(path, timeout=2.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT query, count, first_seen, last_seen FROM zero_results "
                "ORDER BY count DESC, last_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
        # Vanhat rivit on voitu kirjata ennen suodatusta, joten siivotaan
        # myös luettaessa. Kaksi kertaa siivottu ei ole haitaksi; kerran
        # siivoamatta jäänyt on.
        return [
            {**dict(row), "query": _CONTROL_CHARS.sub(" ", str(row["query"]))}
            for row in rows
        ]
    except sqlite3.Error as exc:
        logger.debug("[telemetry] Aukkolistan luku epäonnistui: %s", exc)
        return []


def clear_zero_results(env: Mapping[str, str] | None = None) -> int:
    """Tyhjennä kertymä. Palauttaa poistettujen rivien määrän.

    Säilytysajan noudattaminen on ylläpitäjän vastuulla, ja se vaatii
    työkalun jolla kertymän saa pois.
    """
    path = telemetry_path(env)
    if path is None or not path.exists():
        return 0
    try:
        with sqlite3.connect(path, timeout=2.0) as conn:
            count = conn.execute("SELECT count(*) FROM zero_results").fetchone()[0]
            conn.execute("DELETE FROM zero_results")
        return int(count)
    except sqlite3.Error as exc:
        logger.debug("[telemetry] Tyhjennys epäonnistui: %s", exc)
        return 0
