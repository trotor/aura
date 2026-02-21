"""SQLite-tietokantakerros FTS5-täystekstihaulla ja migraatioilla."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from aura.models import Dataset

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "aura.db"
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "scripts" / "migrations"


def get_connection(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    """Avaa tietokantayhteys.

    Args:
        db_path: Polku tietokantatiedostoon.
        check_same_thread: Jos False, sallii yhteyden käytön eri threadeista.
            Turvallista WAL-moden kanssa read-heavy käytössä (esim. MCP-server).
    """
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
    # Luo seurantataulu
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # Hae jo sovelletut versiot
    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    # Etsi migraatiotiedostot
    if not MIGRATIONS_DIR.exists():
        return 0

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
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

        # Suorita migraatio
        logger.info("[migrations] Ajetaan: %s", path.name)
        sql = path.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, path.stem),
            )
            conn.commit()
            applied_count += 1
            logger.info("[migrations] Valmis: %s", path.name)
        except Exception as e:
            logger.error("[migrations] Virhe ajettaessa %s: %s", path.name, e)
            raise

    return applied_count


def init_db(conn: sqlite3.Connection) -> None:
    """Alusta tietokanta: aja kaikki migraatiot."""
    run_migrations(conn)


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


def _upsert_dataset_inner(conn: sqlite3.Connection, dataset: Dataset) -> None:
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
            dataset.id, dataset.name, dataset.title,
            dataset.title_fi, dataset.title_en, dataset.title_sv,
            dataset.notes, dataset.notes_fi, dataset.notes_en, dataset.notes_sv,
            dataset.license_id, dataset.license_title,
            dataset.organization_id, dataset.organization_name, dataset.organization_title,
            dataset.metadata_created, dataset.metadata_modified,
            json.dumps(dataset.keywords_fi, ensure_ascii=False),
            json.dumps(dataset.keywords_en, ensure_ascii=False),
            json.dumps(dataset.geographical_coverage, ensure_ascii=False),
            dataset.update_frequency, dataset.collection_type,
            dataset.num_resources, dataset.source,
            dataset.access_level, dataset.estimated_size_bytes,
        ),
    )

    # Upsert resurssit
    conn.execute("DELETE FROM resources WHERE dataset_id = ?", (dataset.id,))
    for r in dataset.resources:
        conn.execute(
            """
            INSERT INTO resources (
                id, dataset_id, name, name_fi, name_en,
                description, description_fi, description_en,
                format, url, file_size, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r.id, dataset.id, r.name, r.name_fi, r.name_en,
                r.description, r.description_fi, r.description_en,
                r.format, r.url, r.file_size, r.last_modified,
            ),
        )


def search_datasets(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
    source: str = "",
    fmt: str = "",
    organization: str = "",
    access_level: str = "",
) -> list[dict[str, Any]]:
    """Hae datasettejä FTS5-täystekstihaulla ja suodattimilla.

    Hakee sekä FTS5-indeksistä että enrichment-avainsanoista (keywords, tags,
    description_extended). FTS-osumat tulevat ensin, enrichment-osumat perässä.

    Args:
        query: Hakusanat.
        limit: Tulosten enimmäismäärä.
        offset: Ohita ensimmäiset N tulosta (sivutus).
        source: Suodata lähteen mukaan (esim. "avoindata.fi").
        fmt: Suodata formaatin mukaan (esim. "CSV") — datasetti sisältyy jos
             sillä on vähintään yksi resurssi kyseisessä formaatissa.
        organization: Suodata organisaation mukaan (osa nimestä riittää).
        access_level: Suodata saatavuuden mukaan ("open", "registration", "restricted").
    """
    # Suodattimet (yhteinen FTS- ja enrichment-haulle)
    filter_conditions: list[str] = []
    filter_params: list[Any] = []

    if source:
        filter_conditions.append("d.source = ?")
        filter_params.append(source)
    if organization:
        filter_conditions.append("d.organization_title LIKE ?")
        filter_params.append(f"%{organization}%")
    if access_level:
        filter_conditions.append("d.access_level = ?")
        filter_params.append(access_level)
    if fmt:
        filter_conditions.append(
            "d.id IN (SELECT dataset_id FROM resources WHERE format = ? COLLATE NOCASE)"
        )
        filter_params.append(fmt)

    filter_where = (" AND " + " AND ".join(filter_conditions)) if filter_conditions else ""

    # Enrichment-avainsanahaku: etsi datasetit joiden keywords/tags/description
    # sisältää hakutermin (LIKE-haku enrichments-taulusta)
    enrich_like = f"%{query}%"

    # Parametrit: FTS match, enrichment LIKE ×2 (id + name), suodattimet ×1, limit, offset
    params: list[Any] = [query, enrich_like, enrich_like, *filter_params, limit, offset]

    rows = conn.execute(
        f"""
        SELECT d.*, COALESCE(fts.rank, 0) as rank
        FROM datasets d
        LEFT JOIN (
            SELECT rowid, rank
            FROM datasets_fts
            WHERE datasets_fts MATCH ?
        ) fts ON d.rowid = fts.rowid
        WHERE (
            fts.rowid IS NOT NULL
            OR d.id IN (
                SELECT DISTINCT dataset_id FROM enrichments
                WHERE field IN ('keywords', 'tags', 'description_extended')
                AND value LIKE ?
            )
            OR d.name IN (
                SELECT DISTINCT dataset_id FROM enrichments
                WHERE field IN ('keywords', 'tags', 'description_extended')
                AND value LIKE ?
            )
        )
        {filter_where}
        ORDER BY rank
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


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


def get_datasets_by_ids(
    conn: sqlite3.Connection, dataset_ids: list[str]
) -> list[dict[str, Any]]:
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

    keywords_raw = dataset.get("keywords_fi", "[]")
    if isinstance(keywords_raw, str):
        try:
            keywords: list[str] = json.loads(keywords_raw)
        except json.JSONDecodeError:
            keywords = []
    else:
        keywords = keywords_raw

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
    orgs = conn.execute("SELECT COUNT(DISTINCT organization_name) FROM datasets").fetchone()[0]
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


# --- Enrichments ---


def _resolve_dataset_ids(
    conn: sqlite3.Connection, dataset_id: str
) -> list[str]:
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
            enrichment_id, dataset_id, field, value,
            confidence, source_type, source_detail,
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
        rows = conn.execute(
            "SELECT * FROM enrichments ORDER BY created_at"
        ).fetchall()
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
                    e["id"], e["dataset_id"], e["field"], e["value"],
                    e.get("confidence", "medium"),
                    e["source_type"],
                    e.get("source_detail", ""),
                    e.get("created_at", ""),
                ),
            )
            if conn.execute(
                "SELECT changes()"
            ).fetchone()[0] > 0:
                imported += 1
        except (KeyError, sqlite3.Error) as exc:
            logger.warning(
                "[enrichments] Ohitetaan virheellinen rivi: %s", exc
            )
    conn.commit()
    return imported
