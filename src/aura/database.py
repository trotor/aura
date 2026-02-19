"""SQLite-tietokantakerros FTS5-täystekstihaulla ja migraatioilla."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "aura.db"
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "scripts" / "migrations"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Avaa tietokantayhteys."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
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
    """Lisää tai päivitä datasetti tietokantaan."""
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
            estimated_size_bytes
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?
        ) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, title=excluded.title,
            title_fi=excluded.title_fi, title_en=excluded.title_en, title_sv=excluded.title_sv,
            notes=excluded.notes, notes_fi=excluded.notes_fi,
            notes_en=excluded.notes_en, notes_sv=excluded.notes_sv,
            license_id=excluded.license_id, license_title=excluded.license_title,
            organization_id=excluded.organization_id,
            organization_name=excluded.organization_name,
            organization_title=excluded.organization_title,
            metadata_created=excluded.metadata_created,
            metadata_modified=excluded.metadata_modified,
            keywords_fi=excluded.keywords_fi, keywords_en=excluded.keywords_en,
            geographical_coverage=excluded.geographical_coverage,
            update_frequency=excluded.update_frequency,
            collection_type=excluded.collection_type,
            num_resources=excluded.num_resources,
            source=excluded.source,
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
            dataset.estimated_size_bytes,
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
) -> list[dict]:
    """Hae datasettejä FTS5-täystekstihaulla."""
    rows = conn.execute(
        """
        SELECT d.*, rank
        FROM datasets_fts fts
        JOIN datasets d ON d.rowid = fts.rowid
        WHERE datasets_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_dataset(conn: sqlite3.Connection, dataset_id: str) -> dict | None:
    """Hae yksittäinen datasetti ID:llä tai nimellä."""
    row = conn.execute(
        "SELECT * FROM datasets WHERE id = ? OR name = ?",
        (dataset_id, dataset_id),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)

    resources = conn.execute(
        "SELECT * FROM resources WHERE dataset_id = ?",
        (result["id"],),
    ).fetchall()
    result["resources"] = [dict(r) for r in resources]
    return result


def get_stats(conn: sqlite3.Connection) -> dict:
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
