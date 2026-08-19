"""SQLite-tietokantakerros FTS5-täystekstihaulla ja migraatioilla."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aura.constants import parse_json_list
from aura.decompound import load_lexicon
from aura.dedup import deduplicate
from aura.lemmatize import build_fts_query
from aura.models import Dataset
from aura.size_estimator import parse_file_size

logger = logging.getLogger(__name__)

#: Kanta paketin sijaintiin nähden. Käytetään kun ``AURA_DB`` ei ole asetettu.
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "aura.db"
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "scripts" / "migrations"

#: Ympäristömuuttuja jolla kannan polku ohitetaan.
DB_PATH_ENV = "AURA_DB"


def resolve_db_path(env: Mapping[str, str] | None = None) -> Path:
    """Selvitä tarjoiltavan kannan polku.

    Pakettipolku ei kelpaa konttiajossa: image asennetaan ``/app``:iin mutta
    kanta halutaan erilliseen volumeen, eikä johdettua pro-kantaa voi tarjoilla
    lainkaan ilman ohitusta.

    Tyhjä tai pelkkää tyhjämerkkiä sisältävä arvo tulkitaan asettamattomaksi.
    Se on yleinen vahinko (``AURA_DB=$UNSET``), ja tyhjänä polkuna se avaisi
    yhteyden hakemistoon ``.`` ja kaatuisi hämärästi paljon myöhemmin.

    Args:
        env: Ympäristö josta luetaan. Oletuksena ``os.environ``.
    """
    if env is None:
        env = os.environ
    raw = env.get(DB_PATH_ENV, "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    return Path(raw).expanduser()


def get_connection(
    db_path: Path | None = None,
    *,
    check_same_thread: bool = True,
    readonly: bool = False,
) -> sqlite3.Connection:
    """Avaa tietokantayhteys.

    Args:
        db_path: Polku tietokantatiedostoon. ``None`` = selvitä ``AURA_DB``:stä
            tai käytä pakettipolkua. Eksplisiittinen arvo voittaa aina
            ympäristömuuttujan.
        check_same_thread: Jos False, sallii yhteyden käytön eri threadeista.
            Turvallista WAL-moden kanssa read-heavy käytössä (esim. MCP-server).
        readonly: Jos True, avaa yhteys vain luettavaksi (``mode=ro``). Estää
            kaikki kirjoitukset jo SQLite-tasolla (remote read-only -moodi).
    """
    # Selvitetään kutsuhetkellä, ei oletusargumentissa: oletusargumentti
    # sidottaisiin importtihetkeen, jolloin muuttujan asettaminen sen jälkeen
    # ei vaikuttaisi mihinkään ja vika näkyisi vasta väärän kannan sisältönä.
    if db_path is None:
        db_path = resolve_db_path()

    if readonly:
        # mode=ro: ei mkdiriä eikä WAL-pragmaa (ne kirjoittaisivat levylle).
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=check_same_thread)
        conn.row_factory = sqlite3.Row
        return conn

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> int:
    """Aja pending-migraatiot tietokantaan.

    Migraatiot ovat numeroidut SQL-tiedostot kansiossa scripts/migrations/:
        001_initial_schema.sql
        002_add_something.sql
        ...

    Sovellettuja migraatioita seurataan schema_migrations-taulussa.

    Returns:
        Sovellettujen migraatioiden lukumäärä.
    """
    # Etsi migraatiotiedostot
    if not MIGRATIONS_DIR.exists():
        return 0

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        return 0

    # Exclusive lock estää rinnakkaiset migraatiot
    conn.execute("BEGIN EXCLUSIVE")
    try:
        # Luo seurantataulu (exclusive-transaktio estää kilpatilanteen)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  version INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  applied_at TEXT DEFAULT (datetime('now'))"
            ")"
        )

        # Hae jo sovelletut versiot
        applied = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        applied_count = 0
        for path in migration_files:
            # Parsii version numeron tiedostonimestä: "001_initial_schema.sql" -> 1
            try:
                version = int(path.stem.split("_", 1)[0])
            except (ValueError, IndexError):
                logger.warning("[migrations] Ohitetaan tiedosto: %s", path.name)
                continue

            if version in applied:
                continue

            # Suorita migraatio lauseittain (executescript commitoisi implisiittisesti)
            logger.info("[migrations] Ajetaan: %s", path.name)
            sql = path.read_text(encoding="utf-8")
            for statement in _split_sql(sql):
                conn.execute(statement)

            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, path.stem),
            )
            applied_count += 1
            logger.info("[migrations] Valmis: %s", path.name)

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return applied_count


def _split_sql(sql: str) -> list[str]:
    """Jaa SQL-skripti yksittäisiksi lauseiksi.

    Käsittelee BEGIN...END-lohkot (triggerit) yhdeksi lauseeksi.
    """
    statements: list[str] = []
    current: list[str] = []
    in_block = False

    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue

        current.append(line)

        # Tunnista BEGIN...END-lohkon alku (trigger)
        upper = stripped.upper()
        if upper.endswith("BEGIN") and not in_block:
            in_block = True
            continue

        # Lohkon loppu: "END;" tai "END ;"
        if in_block and upper.rstrip("; ").endswith("END"):
            in_block = False
            stmt = "\n".join(current).strip().rstrip(";")
            if stmt:
                statements.append(stmt)
            current = []
            continue

        # Normaali lause päättyy puolipisteeseen (ei lohkon sisällä)
        if not in_block and stripped.endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";")
            if stmt:
                statements.append(stmt)
            current = []

    # Viimeinen lause ilman puolipistettä
    remaining = "\n".join(current).strip().rstrip(";")
    if remaining:
        statements.append(remaining)

    return statements


def _backfill_file_size_bytes(conn: sqlite3.Connection) -> int:
    """Backfill file_size_bytes for resources with non-numeric file_size."""
    rows = conn.execute(
        "SELECT id, file_size FROM resources WHERE file_size != '' AND file_size_bytes = 0"
    ).fetchall()
    updated = 0
    for row in rows:
        size_bytes = parse_file_size(row["file_size"])
        if size_bytes > 0:
            conn.execute(
                "UPDATE resources SET file_size_bytes = ? WHERE id = ?",
                (size_bytes, row["id"]),
            )
            updated += 1
    if updated:
        conn.commit()
        logger.info("[backfill] Päivitetty %d resurssin file_size_bytes", updated)
    return updated


_initialized_connections: dict[int, sqlite3.Connection] = {}


def init_db(conn: sqlite3.Connection) -> None:
    """Alusta tietokanta: aja kaikki migraatiot (kerran per yhteys)."""
    conn_id = id(conn)
    if _initialized_connections.get(conn_id) is conn:
        return
    applied = run_migrations(conn)
    if applied > 0:
        _backfill_file_size_bytes(conn)
    _initialized_connections[conn_id] = conn


def upsert_organization(
    conn: sqlite3.Connection,
    org_id: str,
    name: str = "",
    title: str = "",
    title_fi: str = "",
    title_en: str = "",
    description: str = "",
    image_url: str = "",
    homepage: str = "",
) -> None:
    """Lisää tai päivitä organisaatio tietokantaan."""
    if not org_id:
        return
    # Use abbreviation 'o' for organizations to keep lines short
    conn.execute(
        """
        INSERT INTO organizations (
            id, name, title, title_fi, title_en,
            description, image_url, homepage
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = CASE WHEN excluded.name != ''
                THEN excluded.name ELSE organizations.name END,
            title = CASE WHEN excluded.title != ''
                THEN excluded.title ELSE organizations.title END,
            title_fi = CASE WHEN excluded.title_fi != ''
                THEN excluded.title_fi ELSE organizations.title_fi END,
            title_en = CASE WHEN excluded.title_en != ''
                THEN excluded.title_en ELSE organizations.title_en END,
            description = CASE WHEN excluded.description != ''
                THEN excluded.description ELSE organizations.description END,
            image_url = CASE WHEN excluded.image_url != ''
                THEN excluded.image_url ELSE organizations.image_url END,
            homepage = CASE WHEN excluded.homepage != ''
                THEN excluded.homepage ELSE organizations.homepage END
        """,
        (
            org_id,
            name,
            title,
            title_fi,
            title_en,
            description,
            image_url,
            homepage,
        ),
    )


def upsert_dataset(conn: sqlite3.Connection, dataset: Dataset) -> None:
    """Lisää tai päivitä datasetti tietokantaan.

    Käyttää savepointia taatakseen atomisen päivityksen:
    datasetti + resurssit päivittyvät joko kokonaan tai eivät ollenkaan.
    """
    conn.execute("SAVEPOINT upsert_ds")
    try:
        _upsert_dataset_inner(conn, dataset)
        conn.execute("RELEASE upsert_ds")
    except Exception:
        conn.execute("ROLLBACK TO upsert_ds")
        raise


def _normalize_geo_coverage(values: list[str]) -> list[str]:
    """Normalisoi geographical_coverage-arvot title-caseen."""
    return [v.strip().title() for v in values if v.strip()]


def _upsert_dataset_inner(conn: sqlite3.Connection, dataset: Dataset) -> None:
    # Normalisoi geographical_coverage ennen tallennusta
    updates: dict[str, Any] = {
        "geographical_coverage": _normalize_geo_coverage(dataset.geographical_coverage),
    }

    # Normalisoi lisenssi SPDX-muotoon (#119)
    if dataset.license_id:
        from aura.constants import normalize_license

        spdx_id, spdx_title = normalize_license(dataset.license_id)
        if spdx_id:
            updates["license_id"] = spdx_id
        if spdx_title:
            updates["license_title"] = spdx_title

    dataset = dataset.model_copy(update=updates)

    # Upsert organization if present
    if dataset.organization_id:
        upsert_organization(
            conn,
            org_id=dataset.organization_id,
            name=dataset.organization_name,
            title=dataset.organization_title,
        )

    num_resources = len(dataset.resources)
    conn.execute(
        """
        INSERT INTO datasets (
            id, name, title, title_fi, title_en, title_sv,
            notes, notes_fi, notes_en, notes_sv,
            license_id, license_title,
            organization_id, organization_name, organization_title,
            metadata_created, metadata_modified,
            keywords_fi, keywords_en, geographical_coverage,
            update_frequency, collection_type, num_resources, source,
            access_level, estimated_size_bytes
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?
        ) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, title=excluded.title,
            title_fi=excluded.title_fi, title_en=excluded.title_en, title_sv=excluded.title_sv,
            notes=excluded.notes, notes_fi=excluded.notes_fi,
            notes_en=excluded.notes_en, notes_sv=excluded.notes_sv,
            license_id=excluded.license_id, license_title=excluded.license_title,
            organization_id=excluded.organization_id,
            organization_name=excluded.organization_name,
            organization_title=excluded.organization_title,
            metadata_created=CASE
                WHEN excluded.metadata_created != '' AND excluded.metadata_created IS NOT NULL
                THEN excluded.metadata_created
                ELSE datasets.metadata_created
            END,
            metadata_modified=CASE
                WHEN excluded.metadata_modified != '' AND excluded.metadata_modified IS NOT NULL
                THEN excluded.metadata_modified
                ELSE datasets.metadata_modified
            END,
            keywords_fi=excluded.keywords_fi, keywords_en=excluded.keywords_en,
            geographical_coverage=excluded.geographical_coverage,
            update_frequency=excluded.update_frequency,
            collection_type=excluded.collection_type,
            num_resources=excluded.num_resources,
            source=excluded.source,
            access_level=excluded.access_level,
            estimated_size_bytes=excluded.estimated_size_bytes,
            harvested_at=datetime('now')
        """,
        (
            dataset.id,
            dataset.name,
            dataset.title,
            dataset.title_fi,
            dataset.title_en,
            dataset.title_sv,
            dataset.notes,
            dataset.notes_fi,
            dataset.notes_en,
            dataset.notes_sv,
            dataset.license_id,
            dataset.license_title,
            dataset.organization_id,
            dataset.organization_name,
            dataset.organization_title,
            dataset.metadata_created,
            dataset.metadata_modified,
            json.dumps(dataset.keywords_fi, ensure_ascii=False),
            json.dumps(dataset.keywords_en, ensure_ascii=False),
            json.dumps(dataset.geographical_coverage, ensure_ascii=False),
            dataset.update_frequency,
            dataset.collection_type,
            num_resources,
            dataset.source,
            dataset.access_level,
            dataset.estimated_size_bytes,
        ),
    )

    # Upsert resurssit: päivitä olemassaolevat, poista vain poistetut
    new_ids = {r.id for r in dataset.resources}
    existing = conn.execute(
        "SELECT id FROM resources WHERE dataset_id = ?", (dataset.id,)
    ).fetchall()
    existing_ids = {row[0] for row in existing}

    removed = existing_ids - new_ids
    if removed:
        placeholders = ",".join("?" for _ in removed)
        conn.execute(
            f"DELETE FROM resources WHERE id IN ({placeholders})",
            list(removed),
        )

    for r in dataset.resources:
        conn.execute(
            """
            INSERT INTO resources (
                id, dataset_id, name, name_fi, name_en,
                description, description_fi, description_en,
                format, url, file_size, file_size_bytes, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, name_fi=excluded.name_fi,
                name_en=excluded.name_en,
                description=excluded.description,
                description_fi=excluded.description_fi,
                description_en=excluded.description_en,
                format=excluded.format, url=excluded.url,
                file_size=excluded.file_size,
                file_size_bytes=excluded.file_size_bytes,
                last_modified=excluded.last_modified
            """,
            (
                r.id,
                dataset.id,
                r.name,
                r.name_fi,
                r.name_en,
                r.description,
                r.description_fi,
                r.description_en,
                r.format,
                r.url,
                r.file_size,
                r.file_size_bytes,
                r.last_modified,
            ),
        )


# BM25-kenttäpainot, järjestys = datasets_fts:n sarakejärjestys.
#
# Ilman painoja FTS5:n `rank` kohtelee otsikko-osumaa ja kuvauksen keskeltä
# löytyvää osumaa samanarvoisina, mikä on hakulaadun kannalta väärin: haku
# "asuntojen hinnat" nosti kärkeen sianlihan hinnat, koska sana "hinnat"
# esiintyi kuvaustekstissä yhtä painavasti kuin otsikossa.
_FTS_WEIGHTS_WITH_LEMMAS: tuple[float, ...] = (
    3.0,  # name
    8.0,  # title
    10.0,  # title_fi
    4.0,  # title_en
    2.0,  # title_sv
    1.5,  # notes
    2.0,  # notes_fi
    1.0,  # notes_en
    0.5,  # notes_sv
    6.0,  # keywords_fi
    3.0,  # keywords_en
    1.0,  # organization_title
    5.0,  # lemmas
)
_FTS_WEIGHTS_LEGACY: tuple[float, ...] = _FTS_WEIGHTS_WITH_LEMMAS[:-1]

# Jos tiukka AND-haku tuottaa vähemmän kuin tämän, löysennetään asteittain.
RELAX_THRESHOLD = 3

# Kuinka moninkertaisesti haetaan ennen deduplikointia. Duplikaatteja on
# mitattuna 5 % korpuksesta mutta ne kasautuvat yleisiin kyselyihin, joten
# kaksinkertainen haku riittää täyttämään sivun eri aineistoilla.
DEDUP_OVERFETCH = 2

# Laatupisteiden neutraali taso: tämän saa datasetti jolle pisteitä ei ole
# laskettu, jottei puuttuva tieto ole rangaistus.
NEUTRAL_QUALITY = 50.0

# Kuinka paljon laatu saa siirtää sijoitusta. 0,10 tarkoittaa että paras
# mahdollinen laatu parantaa bm25-pistettä 10 % ja huonoin heikentää saman
# verran — laatu ei siis voi nostaa epärelevanttia aineistoa relevantin ohi,
# vaan ratkaisee lähes tasaväkiset.
QUALITY_WEIGHT = 0.10

# Rangaistus datasetille, jonka kaikki tarkistetut resurssit ovat rikki.
# Huom: resource_health kattaa toistaiseksi vain ~1 % korpuksesta, joten
# vaikutus on pieni kunnes health-ajoja on tehty enemmän.
BROKEN_PENALTY = 0.25


def _ranking_expr() -> str:
    """Järjestyslauseke: bm25-piste laatu- ja saatavuussignaaleilla säädettynä.

    bm25 palauttaa **negatiivisia** lukuja, joissa pienempi on parempi. Siksi
    kerroin > 1 parantaa sijoitusta ja kerroin < 1 heikentää sitä.

    Kertominen on tietoinen valinta yhteenlaskun sijaan: bm25-pisteiden
    suuruusluokka vaihtelee kyselyn ja kenttäpainojen mukaan, joten kiinteä
    lisäys dominoisi heikkoja osumia ja katoaisi vahvoista. Suhteellinen
    säätö kohtelee molempia samoin.

    Enrichment-osumilla rank on 0, jolloin säätö ei vaikuta — ne jäävät
    listan häntään kuten ennenkin.
    """
    return (
        "COALESCE(fts.rank, 0) * (1"
        f" + {QUALITY_WEIGHT} * ((COALESCE(q.score, {NEUTRAL_QUALITY}) - "
        f"{NEUTRAL_QUALITY}) / {NEUTRAL_QUALITY})"
        f" - CASE WHEN h.any_available = 0 THEN {BROKEN_PENALTY} ELSE 0 END"
        ")"
    )


def _has_lemma_column(conn: sqlite3.Connection) -> bool:
    """Onko migraatio 018 (lemmas-sarake) ajettu tähän kantaan?"""
    cols = conn.execute("PRAGMA table_info(datasets)").fetchall()
    return any(row[1] == "lemmas" for row in cols)


def _bm25_expr(conn: sqlite3.Connection) -> str:
    """Rakenna painotettu bm25()-lauseke kannan sarakemäärän mukaan."""
    weights = _FTS_WEIGHTS_WITH_LEMMAS if _has_lemma_column(conn) else _FTS_WEIGHTS_LEGACY
    return "bm25(datasets_fts, " + ", ".join(str(w) for w in weights) + ")"


def build_dataset_filters(
    source: str = "",
    fmt: str = "",
    organization: str = "",
    access_level: str = "",
    region_names: list[str] | None = None,
) -> tuple[list[str], list[Any]]:
    """Rakenna hakusuodattimien SQL-ehdot ja parametrit.

    Ehdot olettavat että datasets-taulu on aliaksella ``d``.

    Julkinen siksi, että suodatin on määriteltävä **yhdessä paikassa**.
    Hakua täydentävät kerrokset (esim. pro-moottorin dimensiohaku) hakevat
    ehdokkaita ohi tämän funktion FTS-haun, ja niiden on rajattava samoilla
    ehdoilla. Omat kopiot ajautuisivat erilleen hiljaa: vastaus näyttäisi
    suodatetulta mutta sisältäisi rivejä joita suodatin ei päästäisi läpi.

    Args:
        source: Lähde tarkalleen (esim. "avoindata.fi").
        fmt: Formaatti — datasetti kelpaa jos sillä on resurssi siinä.
        organization: Organisaation nimen osa.
        access_level: "open" | "registration" | "restricted".
        region_names: Maantieteellinen kattavuus, ks. huomio alla.

    Returns:
        ``(ehdot, parametrit)`` — ehdot yhdistetään AND:lla.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if source:
        conditions.append("d.source = ?")
        params.append(source)
    if organization:
        conditions.append("d.organization_title LIKE ?")
        params.append(f"%{organization}%")
    if access_level:
        conditions.append("d.access_level = ?")
        params.append(access_level)
    if fmt:
        conditions.append(
            "d.id IN (SELECT dataset_id FROM resources WHERE format = ? COLLATE NOCASE)"
        )
        params.append(fmt)
    if region_names:
        # Kaksi tapaa olla alueellisesti relevantti. Ensimmäinen on
        # aineiston oma aluerajaus. Toinen on koko maan kattava aineisto
        # jossa kunta on dimensioarvo — se puuttui, ja siksi
        # "Kuopio + väestö" palautti tyhjän vaikka Kuopion väkiluku on
        # sekä StatFinissä että Sotkanetissa. Ks. aura.region_levels.
        #
        # Jälkimmäinen haara ei katso pyydettyä aluetta lainkaan, joten
        # aluerajaus on pehmeä: se laajentaa, ei rajaa. Kutsujan on
        # kerrottava se käyttäjälle — ks. _region_widening_note().
        coverage_conditions = " OR ".join(
            "d.geographical_coverage LIKE ?" for _ in region_names
        )
        conditions.append(
            f"(({coverage_conditions}) OR d.id IN ("
            "SELECT dataset_id FROM enrichments WHERE field = 'region_level'))"
        )
        params.extend(f"%{name}%" for name in region_names)

    return conditions, params


def search_datasets(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
    source: str = "",
    fmt: str = "",
    organization: str = "",
    access_level: str = "",
    expanded_query: str = "",
    region_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Hae datasettejä FTS5-täystekstihaulla ja suodattimilla.

    Haku etenee asteittain löysentäen, jotta tarkkuus säilyy silloin kun
    hyviä osumia on, ja kattavuus silloin kun ei ole:

    1. **Tiukka** — lemmatisoitu AND-haku (ks. ``aura.lemmatize``). Jokaisen
       hakusanan on osuttava, joko pinta- tai perusmuodossaan.
    2. **Löysä** — samat termit OR:lla, jos tiukka tuotti alle
       ``RELAX_THRESHOLD`` tulosta. BM25 suosii yhä useampaan termiin osuvia.
    3. **Laajennettu** — sanasto- ja YSO-termit (``expanded_query``), vasta
       jos edelliset eivät tuottaneet mitään.

    Vaihe 3 oli aiemmin *ensimmäinen* vaihe, mikä tuhosi tarkkuuden: kymmenien
    eri termien OR-lauseke sai bm25:n rankkaamaan kohinaa (haku
    "metsänhakkuut Pirkanmaa" palautti kärkitulokseksi Tampereen bussipysäkit).

    Args:
        query: Hakusanat.
        limit: Tulosten enimmäismäärä.
        offset: Ohita ensimmäiset N tulosta (sivutus).
        source: Suodata lähteen mukaan (esim. "avoindata.fi").
        fmt: Suodata formaatin mukaan (esim. "CSV") — datasetti sisältyy jos
             sillä on vähintään yksi resurssi kyseisessä formaatissa.
        organization: Suodata organisaation mukaan (osa nimestä riittää).
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted").
        expanded_query: Valmis FTS5-lauseke sanasto-/YSO-laajennuksesta.
            Käytetään vain viimeisenä keinona.
        region_names: Rajaa maantieteellisen kattavuuden mukaan.
    """
    # Suodattimet (yhteinen FTS- ja enrichment-haulle)
    filter_conditions, filter_params = build_dataset_filters(
        source=source,
        fmt=fmt,
        organization=organization,
        access_level=access_level,
        region_names=region_names,
    )

    filter_where = (" AND " + " AND ".join(filter_conditions)) if filter_conditions else ""

    lemma_col = "lemmas" if _has_lemma_column(conn) else None
    sql = f"""
        SELECT d.*, COALESCE(fts.rank, 0) as rank,
               COALESCE(q.score, {NEUTRAL_QUALITY}) AS quality_score,
               h.any_available AS resources_available
        FROM datasets d
        LEFT JOIN (
            SELECT rowid, {_bm25_expr(conn)} AS rank
            FROM datasets_fts
            WHERE datasets_fts MATCH ?
        ) fts ON d.rowid = fts.rowid
        LEFT JOIN quality_scores q
               ON q.dataset_id = d.id AND q.dimension = 'overall'
        LEFT JOIN (
            SELECT dataset_id, MAX(is_available) AS any_available
            FROM resource_health GROUP BY dataset_id
        ) h ON h.dataset_id = d.id
        WHERE (
            fts.rowid IS NOT NULL
            OR d.id IN (
                SELECT DISTINCT dataset_id FROM enrichments_fts
                WHERE enrichments_fts MATCH ?
            )
        )
        {filter_where}
        ORDER BY {_ranking_expr()}
        LIMIT ? OFFSET ?
    """

    # Haetaan limit+offset riviä per vaihe; sivutus leikataan vasta yhdistämisen
    # jälkeen, koska eri vaiheiden tulosjoukot ovat sisäkkäisiä.
    #
    # Ylihaku: deduplikointi pudottaa rivejä, joten ilman tätä sivullinen
    # tuloksia kutistuisi duplikaattien verran. Käyttäjän kuuluu saada
    # `limit` *eri* aineistoa, ei limit paikkaa joista osa on samaa taulua.
    fetch = (limit + offset) * DEDUP_OVERFETCH

    def _run(ds_query: str, enr_query: str) -> list[dict[str, Any]]:
        params: list[Any] = [ds_query, enr_query, *filter_params, fetch, 0]
        return [dict(row) for row in conn.execute(sql, params).fetchall()]

    # Rakenna yritykset tiukimmasta löysimpään. enrichments_fts:ssä ei ole
    # lemmas-saraketta, joten se saa oman lauseke­varianttinsa.
    # Yhdyssanojen osat annetaan VAIN löysään vaiheeseen. Tiukan vaiheen
    # osumat menevät aina kärkeen, joten osajako siellä nostaisi heikon
    # signaalin aitojen osumien ohi — sama virhe joka mitattiin
    # dimensioarvoilla. Löysässä vaiheessa se voi vain täydentää.
    lexicon = load_lexicon(conn) if _has_lemma_column(conn) else None

    attempts: list[tuple[str, str]] = []
    strict_ds = build_fts_query(query, strict=True, lemma_column=lemma_col)
    if strict_ds:
        attempts.append((strict_ds, build_fts_query(query, strict=True, lemma_column=None)))
        loose_ds = build_fts_query(query, strict=False, lemma_column=lemma_col, lexicon=lexicon)
        if loose_ds != strict_ds:
            attempts.append(
                (
                    loose_ds,
                    build_fts_query(query, strict=False, lemma_column=None, lexicon=lexicon),
                )
            )
    if expanded_query:
        attempts.append((expanded_query, expanded_query))
    if not attempts:
        # Kysely oli pelkkiä stopsanoja tai tokenisoinnin jälkeen tyhjä
        attempts.append((query, query))

    # Tulokset kasataan vaihe kerrallaan: tiukan haun osumat säilyvät kärjessä
    # ja löysemmät vaiheet vain täydentävät häntää. Tämä on olennaista — jos
    # löysä joukko *korvaisi* tiukan, harvinaisen mutta täsmällisen osuman
    # tilalle nousisi laaja OR-kohina.
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ds_query, enr_query in attempts:
        try:
            rows = _run(ds_query, enr_query)
        except sqlite3.OperationalError:
            logger.warning("[search] Kelvoton FTS5-lauseke: %r", ds_query)
            continue
        for row in rows:
            key = str(row.get("id", ""))
            if key not in seen:
                seen.add(key)
                merged.append(row)
        if len(merged) >= max(RELAX_THRESHOLD, fetch):
            break

    # Deduplikointi vasta kasauksen jälkeen: sama taulu voi tulla eri
    # vaiheista, ja ryhmän edustajaksi kuuluu parhaiten sijoittunut.
    return deduplicate(merged)[offset : offset + limit]


def get_dataset(conn: sqlite3.Connection, dataset_id: str) -> dict[str, Any] | None:
    """Hae yksittäinen datasetti ID:llä tai nimellä."""
    row = conn.execute(
        "SELECT * FROM datasets WHERE id = ? OR name = ?",
        (dataset_id, dataset_id),
    ).fetchone()
    if row is None:
        return None
    result: dict[str, Any] = dict(row)

    resources = conn.execute(
        "SELECT * FROM resources WHERE dataset_id = ?",
        (result["id"],),
    ).fetchall()
    result["resources"] = [dict(r) for r in resources]
    return result


def get_datasets_by_ids(conn: sqlite3.Connection, dataset_ids: list[str]) -> list[dict[str, Any]]:
    """Hae useita datasettejä ID:llä tai nimellä."""
    if not dataset_ids:
        return []
    placeholders = ",".join("?" for _ in dataset_ids)
    rows = conn.execute(
        f"SELECT * FROM datasets WHERE id IN ({placeholders}) OR name IN ({placeholders})",
        dataset_ids + dataset_ids,
    ).fetchall()
    results = []
    for row in rows:
        d: dict[str, Any] = dict(row)
        resources = conn.execute(
            "SELECT * FROM resources WHERE dataset_id = ?", (d["id"],)
        ).fetchall()
        d["resources"] = [dict(r) for r in resources]
        results.append(d)
    return results


def find_related_datasets(
    conn: sqlite3.Connection, dataset_id: str, limit: int = 5
) -> list[dict[str, Any]]:
    """Etsi samankaltaiset datasetit avainsanojen ja organisaation perusteella."""
    dataset = get_dataset(conn, dataset_id)
    if dataset is None:
        return []

    keywords = parse_json_list(dataset.get("keywords_fi", "[]"))

    org = dataset.get("organization_title", "")
    ds_id = dataset["id"]

    # Etsitään avainsanojen perusteella
    related: dict[str, dict[str, Any]] = {}
    for kw in keywords[:5]:
        try:
            rows = conn.execute(
                """
                SELECT d.*, rank
                FROM datasets_fts fts
                JOIN datasets d ON d.rowid = fts.rowid
                WHERE datasets_fts MATCH ?
                ORDER BY rank
                LIMIT 10
                """,
                (kw,),
            ).fetchall()
            for row in rows:
                d = dict(row)
                if d["id"] != ds_id and d["id"] not in related:
                    related[d["id"]] = d
        except Exception:  # noqa: BLE001
            continue

    # Lisätään organisaation muita datasettejä
    if org:
        org_rows = conn.execute(
            """
            SELECT * FROM datasets
            WHERE organization_title = ? AND id != ?
            ORDER BY metadata_modified DESC
            LIMIT 10
            """,
            (org, ds_id),
        ).fetchall()
        for row in org_rows:
            d = dict(row)
            if d["id"] not in related:
                related[d["id"]] = d

    return list(related.values())[:limit]


def get_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Palauta tilastot tietokannasta."""
    total = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
    orgs = conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]
    formats = conn.execute("SELECT COUNT(DISTINCT format) FROM resources").fetchone()[0]

    top_orgs = conn.execute(
        """
        SELECT organization_title, COUNT(*) as count
        FROM datasets
        WHERE organization_title != ''
        GROUP BY organization_title
        ORDER BY count DESC
        LIMIT 10
        """,
    ).fetchall()

    top_formats = conn.execute(
        """
        SELECT format, COUNT(*) as count
        FROM resources
        WHERE format != ''
        GROUP BY format
        ORDER BY count DESC
        LIMIT 10
        """,
    ).fetchall()

    return {
        "total_datasets": total,
        "total_organizations": orgs,
        "total_formats": formats,
        "top_organizations": [dict(r) for r in top_orgs],
        "top_formats": [dict(r) for r in top_formats],
    }


# --- Organizations ---


def get_organization(conn: sqlite3.Connection, org_id: str) -> dict[str, Any] | None:
    """Hae organisaatio ID:llä tai nimellä."""
    row = conn.execute(
        "SELECT * FROM organizations WHERE id = ? OR name = ?",
        (org_id, org_id),
    ).fetchone()
    return dict(row) if row else None


def get_organizations(
    conn: sqlite3.Connection,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Listaa organisaatiot datasettien lukumäärän mukaan."""
    rows = conn.execute(
        """
        SELECT o.*, COUNT(d.id) as dataset_count
        FROM organizations o
        LEFT JOIN datasets d ON d.organization_id = o.id
        GROUP BY o.id
        ORDER BY dataset_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- Enrichments ---


def _resolve_dataset_ids(conn: sqlite3.Connection, dataset_id: str) -> list[str]:
    """Palauta kaikki datasetin tunnisteet (id ja name).

    Enrichments voivat olla tallennettu joko UUID:llä tai slug-nimellä,
    joten haut pitää tehdä molemmilla.
    """
    row = conn.execute(
        "SELECT id, name FROM datasets WHERE id = ? OR name = ?",
        (dataset_id, dataset_id),
    ).fetchone()
    if row is None:
        return [dataset_id]
    ids = {row[0], row[1]}
    ids.discard("")
    return list(ids) if ids else [dataset_id]


def add_enrichment(
    conn: sqlite3.Connection,
    dataset_id: str,
    field: str,
    value: str,
    confidence: str = "medium",
    source_type: str = "mcp_session",
    source_detail: str = "",
) -> str:
    """Lisää rikastus datasettiin.

    Returns:
        Luodun enrichmentin id.
    """
    enrichment_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO enrichments (
            id, dataset_id, field, value,
            confidence, source_type, source_detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            enrichment_id,
            dataset_id,
            field,
            value,
            confidence,
            source_type,
            source_detail,
        ),
    )
    conn.commit()
    return enrichment_id


def get_enrichments(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Hae datasetin rikastukset, uusin ensin.

    Palauttaa kaikki rikastukset (myös vanhat versiot).
    Etsii sekä UUID:llä että slug-nimellä.
    """
    ids = _resolve_dataset_ids(conn, dataset_id)
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT * FROM enrichments
        WHERE dataset_id IN ({placeholders})
        ORDER BY field, created_at DESC
        """,
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_enrichments(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Hae datasetin uusimmat rikastukset (yksi per kenttä).

    Etsii sekä UUID:llä että slug-nimellä.
    """
    ids = _resolve_dataset_ids(conn, dataset_id)
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT e.*
        FROM enrichments e
        INNER JOIN (
            SELECT field, MAX(rowid) as max_rowid
            FROM enrichments
            WHERE dataset_id IN ({placeholders})
            GROUP BY field
        ) latest ON e.rowid = latest.max_rowid
        ORDER BY e.field
        """,
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


def get_enrichment_count(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> int:
    """Palauta datasetin uniikkien rikastuskenttien lukumäärä.

    Etsii sekä UUID:llä että slug-nimellä.
    """
    ids = _resolve_dataset_ids(conn, dataset_id)
    placeholders = ",".join("?" for _ in ids)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT field) FROM enrichments WHERE dataset_id IN ({placeholders})",
        ids,
    ).fetchone()
    return row[0] if row else 0


def get_conflicting_enrichments(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Hae datasetin ristiriitaiset rikastukset.

    Palauttaa kentät joilla on useampi eri arvo.
    Tuloksessa jokainen rivi on yksi enrichment, ryhmitettynä kentän mukaan.
    """
    ids = _resolve_dataset_ids(conn, dataset_id)
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT e.*
        FROM enrichments e
        WHERE e.dataset_id IN ({placeholders})
        AND e.field IN (
            SELECT field FROM enrichments
            WHERE dataset_id IN ({placeholders})
            GROUP BY field
            HAVING COUNT(DISTINCT value) > 1
        )
        ORDER BY e.field,
            CASE e.confidence
                WHEN 'verified' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            e.created_at DESC
        """,
        ids + ids,
    ).fetchall()
    return [dict(r) for r in rows]


def get_stale_enrichments(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Hae datasetin vanhentuneet rikastukset.

    Rikastus on vanhentunut jos datasetin metadata_modified on
    uudempi kuin rikastuksen created_at.
    """
    ids = _resolve_dataset_ids(conn, dataset_id)
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT e.*
        FROM enrichments e
        JOIN datasets d ON (e.dataset_id = d.id OR e.dataset_id = d.name)
        WHERE e.dataset_id IN ({placeholders})
        AND d.metadata_modified > e.created_at
        AND d.metadata_modified != ''
        """,
        ids,
    ).fetchall()
    return [dict(r) for r in rows]


def get_datasets_without_enrichment(
    conn: sqlite3.Connection,
    field: str,
    source: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Hae datasetit joilta puuttuu tietty enrichment.

    Args:
        field: Enrichment-kenttä (esim. "yso_concepts").
        source: Rajaa lähteeseen (tyhjä = kaikki).
        limit: Tulosten enimmäismäärä.

    Returns:
        Lista datasettejä joilla ei ole kyseistä enrichmentiä.
    """
    conditions = ["d.id NOT IN (SELECT dataset_id FROM enrichments WHERE field = ?)"]
    params: list[Any] = [field]

    # Myös name-kentällä tallennetut enrichmentit (slug-pohjainen id)
    conditions.append("d.name NOT IN (SELECT dataset_id FROM enrichments WHERE field = ?)")
    params.append(field)

    if source:
        conditions.append("d.source = ?")
        params.append(source)

    where = " AND ".join(conditions)
    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT d.*
        FROM datasets d
        WHERE {where}
        ORDER BY d.metadata_modified DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def prune_enrichments(
    conn: sqlite3.Connection,
    older_than_days: int = 365,
) -> int:
    """Poista vanhat rikastukset.

    Args:
        older_than_days: Poista rikastukset jotka ovat vanhempia kuin N päivää.

    Returns:
        Poistettujen rikastusten lukumäärä.
    """
    result = conn.execute(
        """
        DELETE FROM enrichments
        WHERE created_at < datetime('now', '-' || ? || ' days')
        """,
        (older_than_days,),
    )
    conn.commit()
    return result.rowcount


# --- Sources ---


def upsert_source(
    conn: sqlite3.Connection,
    config: dict[str, Any],
) -> None:
    """Lisää tai päivitä datalähde sources-tauluun.

    Args:
        config: Dict jossa avaimet vastaavat sources-taulun sarakkeita.
            Pakollinen: "name". Muut ovat valinnaisia.
    """
    name = config.get("name", "")
    if not name:
        return
    conn.execute(
        """
        INSERT INTO sources (
            name, description, url, harvester_type, query_protocol,
            api_base_url, config_json, dataset_count, last_harvested_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(name) DO UPDATE SET
            description = excluded.description,
            url = excluded.url,
            harvester_type = excluded.harvester_type,
            query_protocol = excluded.query_protocol,
            api_base_url = excluded.api_base_url,
            config_json = excluded.config_json,
            dataset_count = excluded.dataset_count,
            last_harvested_at = excluded.last_harvested_at,
            updated_at = datetime('now')
        """,
        (
            name,
            config.get("description", ""),
            config.get("url", ""),
            config.get("harvester_type", ""),
            config.get("query_protocol", ""),
            config.get("api_base_url", ""),
            config.get("config_json", "{}"),
            config.get("dataset_count", 0),
            config.get("last_harvested_at", ""),
        ),
    )


def get_source(
    conn: sqlite3.Connection,
    name: str,
) -> dict[str, Any] | None:
    """Hae yksittäinen datalähde nimellä."""
    row = conn.execute("SELECT * FROM sources WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def get_all_sources(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Hae kaikki datalähteet."""
    rows = conn.execute("SELECT * FROM sources ORDER BY dataset_count DESC, name").fetchall()
    return [dict(r) for r in rows]


# --- Resource Schema ---


def upsert_resource_schema(
    conn: sqlite3.Connection,
    resource_id: str,
    dataset_id: str,
    fields: list[tuple[str, str]],
) -> None:
    """Tallenna resurssin kenttätiedot (field_name, field_type) -parit.

    Korvaa olemassa olevat kentät samalle resurssille.
    """
    if not fields:
        return
    conn.execute("DELETE FROM resource_schema WHERE resource_id = ?", (resource_id,))
    conn.executemany(
        """
        INSERT INTO resource_schema (resource_id, dataset_id, field_name, field_type)
        VALUES (?, ?, ?, ?)
        """,
        [(resource_id, dataset_id, name, ftype) for name, ftype in fields],
    )


def upsert_probe_result(
    conn: sqlite3.Connection,
    resource_id: str,
    dataset_id: str,
    probe_type: str,
    status: str,
    detail: str,
    probed_at: str,
) -> None:
    """Kirjaa probe-yrityksen tulos. Korvaa saman resurssin edellisen.

    Taulu kantaa viimeisimmän tilan, ei historiaa: kirjanpidossa vanha tila
    ei kerro mitään jota uusi ei kertoisi paremmin. Historia kuuluu
    enrichmenteihin, joissa se jo on.
    """
    conn.execute(
        """
        INSERT INTO probe_results
            (resource_id, dataset_id, probe_type, status, detail, probed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_id) DO UPDATE SET
            dataset_id = excluded.dataset_id,
            probe_type = excluded.probe_type,
            status     = excluded.status,
            detail     = excluded.detail,
            probed_at  = excluded.probed_at
        """,
        (resource_id, dataset_id, probe_type, status, detail, probed_at),
    )


def get_probe_result(
    conn: sqlite3.Connection, resource_id: str
) -> dict[str, Any] | None:
    """Hae resurssin viimeisin probe-tulos."""
    row = conn.execute(
        "SELECT * FROM probe_results WHERE resource_id = ?", (resource_id,)
    ).fetchone()
    return dict(row) if row else None


def get_resource_schema(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Hae datasetin resurssien kenttätiedot.

    Palauttaa listan: resource_id, field_name, field_type, detected_at.
    """
    rows = conn.execute(
        """
        SELECT rs.resource_id, rs.field_name, rs.field_type, rs.detected_at
        FROM resource_schema rs
        WHERE rs.dataset_id = ?
        ORDER BY rs.resource_id, rs.rowid
        """,
        (dataset_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def export_enrichments(
    conn: sqlite3.Connection,
    source_type: str = "",
) -> list[dict[str, Any]]:
    """Vie kaikki rikastukset listana.

    Args:
        source_type: Suodata lähdetyypin mukaan (tyhjä = kaikki).
    """
    if source_type:
        rows = conn.execute(
            "SELECT * FROM enrichments WHERE source_type = ? ORDER BY created_at",
            (source_type,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM enrichments ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def import_enrichments(
    conn: sqlite3.Connection,
    enrichments: list[dict[str, Any]],
) -> int:
    """Tuo rikastukset tietokantaan. Ohittaa duplikaatit (sama id).

    Returns:
        Tuotujen (uusien) rikastusten lukumäärä.
    """
    imported = 0
    for e in enrichments:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO enrichments (
                    id, dataset_id, field, value,
                    confidence, source_type, source_detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    e["id"],
                    e["dataset_id"],
                    e["field"],
                    e["value"],
                    e.get("confidence", "medium"),
                    e["source_type"],
                    e.get("source_detail", ""),
                    e.get("created_at", ""),
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                imported += 1
        except (KeyError, sqlite3.Error) as exc:
            logger.warning("[enrichments] Ohitetaan virheellinen rivi: %s", exc)
    conn.commit()
    return imported
