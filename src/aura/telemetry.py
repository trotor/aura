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
CREATE TABLE IF NOT EXISTS tool_patterns (
    kind       TEXT NOT NULL,
    pattern    TEXT NOT NULL,
    count      INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    PRIMARY KEY (kind, pattern)
);
"""

#: tool_patterns-taulun lajit. ``tool`` = yksittäinen työkalu, ``chain`` =
#: istunnon työkaluketju kuviona, ``unmatched`` = käsite jota laajennus ei
#: tunnistanut (esim. tunnusluvun nimi). Sama minimimuoto kuin
#: nollatuloksilla: kuvio ja laskuri, ei istuntoa eikä tapahtumia.
PATTERN_KINDS = frozenset({"tool", "chain", "unmatched"})

#: Ketjun enimmäispituus. Pidempi ketju katkaistaan — pitkä ketju on jo
#: itsessään signaali, eikä sen loppu kerro enempää.
MAX_CHAIN = 12

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


def _clean(text: str) -> str:
    return " ".join(_CONTROL_CHARS.sub(" ", text).split())[:MAX_QUERY_LENGTH]


def record_pattern(kind: str, pattern: str, env: Mapping[str, str] | None = None) -> bool:
    """Kirjaa kuvio laskuriin. Ei koskaan nosta poikkeusta (kutsuja on työkalupolulla)."""
    cleaned = _clean(pattern)
    path = telemetry_path(env)
    if not cleaned or path is None or kind not in PATTERN_KINDS:
        return False
    now = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=2.0) as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                """
                INSERT INTO tool_patterns (kind, pattern, count, first_seen, last_seen)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(kind, pattern) DO UPDATE SET
                    count = count + 1,
                    last_seen = excluded.last_seen
                """,
                (kind, cleaned, now, now),
            )
        return True
    except (sqlite3.Error, OSError) as exc:
        logger.debug("[telemetry] Kuvion kirjaus ohitettiin: %s", exc)
        return False


def top_patterns(
    kind: str, limit: int = 50, env: Mapping[str, str] | None = None
) -> list[dict[str, object]]:
    """Yleisimmät kuviot lajeittain, yleisin ensin."""
    path = telemetry_path(env)
    if path is None or not path.exists():
        return []
    try:
        with sqlite3.connect(path, timeout=2.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA)
            rows = conn.execute(
                "SELECT pattern, count, first_seen, last_seen FROM tool_patterns"
                " WHERE kind = ? ORDER BY count DESC, last_seen DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        return [{**dict(r), "pattern": _CONTROL_CHARS.sub(" ", str(r["pattern"]))} for r in rows]
    except sqlite3.Error as exc:
        logger.debug("[telemetry] Kuvioiden luku epäonnistui: %s", exc)
        return []


class ChainRecorder:
    """Kokoaa istunnon työkaluketjun muistissa ja kirjaa vain kuvion.

    Istuntotunnistetta käytetään **vain muistissa** ketjun kokoamiseen; se ei
    päädy kantaan. Ketju kirjataan kun istunto on ollut hiljaa
    ``idle_seconds`` tai ketju saavuttaa ``MAX_CHAIN``-pituuden.

    Tilaton HTTP (julkinen instanssi) ei anna istuntoa, jolloin jokainen
    kutsu on oma "ketjunsa" ja kirjautuu vain työkalumääränä. Se on
    tietosuojan kannalta paras tila ja riittää kertomaan mitä työkaluja
    käytetään; ketjut saadaan istunnollisilta asiakkailta (stdio, stateful HTTP).
    """

    def __init__(self, idle_seconds: float = 600.0) -> None:
        self.idle = idle_seconds
        self._chains: dict[str, tuple[list[str], float]] = {}

    def add(self, session: str | None, tool: str, now: float) -> None:
        record_pattern("tool", tool)
        self.flush_idle(now)
        if not session:
            return
        chain, _ = self._chains.get(session, ([], now))
        chain.append(tool)
        if len(chain) >= MAX_CHAIN:
            record_pattern("chain", " → ".join(chain) + " → …")
            self._chains.pop(session, None)
            return
        self._chains[session] = (chain, now)

    def flush_idle(self, now: float, *, all_: bool = False) -> int:
        done = [s for s, (_, t) in self._chains.items() if all_ or now - t > self.idle]
        for s in done:
            chain, _ = self._chains.pop(s)
            if chain:
                record_pattern("chain", " → ".join(chain))
        return len(done)


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
        return [{**dict(row), "query": _CONTROL_CHARS.sub(" ", str(row["query"]))} for row in rows]
    except sqlite3.Error as exc:
        logger.debug("[telemetry] Aukkolistan luku epäonnistui: %s", exc)
        return []


def clear_zero_results(env: Mapping[str, str] | None = None) -> int:
    """Tyhjennä kertymä: nollatulokset ja kuviot. Palauttaa poistettujen rivien määrän.

    Säilytysajan noudattaminen on ylläpitäjän vastuulla, ja se vaatii
    työkalun jolla kertymän saa pois — kaikki kertymä, ei vain osa.
    """
    path = telemetry_path(env)
    if path is None or not path.exists():
        return 0
    try:
        with sqlite3.connect(path, timeout=2.0) as conn:
            conn.executescript(_SCHEMA)
            count = 0
            for table in ("zero_results", "tool_patterns"):
                count += conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                conn.execute(f"DELETE FROM {table}")
        return int(count)
    except sqlite3.Error as exc:
        logger.debug("[telemetry] Tyhjennys epäonnistui: %s", exc)
        return 0
