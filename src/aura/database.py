"""SQLite-tietokantakerros FTS5-täystekstihaulla."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from aura.models import Dataset, Resource

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "aura.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Avaa tietokantayhteys."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Luo tietokantataulut ja FTS5-indeksit."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            title TEXT DEFAULT '',
            title_fi TEXT DEFAULT '',
            title_en TEXT DEFAULT '',
            title_sv TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            notes_fi TEXT DEFAULT '',
            notes_en TEXT DEFAULT '',
            notes_sv TEXT DEFAULT '',
            license_id TEXT DEFAULT '',
            license_title TEXT DEFAULT '',
            organization_id TEXT DEFAULT '',
            organization_name TEXT DEFAULT '',
            organization_title TEXT DEFAULT '',
            metadata_created TEXT DEFAULT '',
            metadata_modified TEXT DEFAULT '',
            keywords_fi TEXT DEFAULT '[]',
            keywords_en TEXT DEFAULT '[]',
            geographical_coverage TEXT DEFAULT '[]',
            update_frequency TEXT DEFAULT '',
            collection_type TEXT DEFAULT '',
            num_resources INTEGER DEFAULT 0,
            source TEXT DEFAULT 'avoindata.fi',
            harvested_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS resources (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            name TEXT DEFAULT '',
            name_fi TEXT DEFAULT '',
            name_en TEXT DEFAULT '',
            description TEXT DEFAULT '',
            description_fi TEXT DEFAULT '',
            description_en TEXT DEFAULT '',
            format TEXT DEFAULT '',
            url TEXT DEFAULT '',
            file_size TEXT DEFAULT '',
            last_modified TEXT,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        );

        CREATE INDEX IF NOT EXISTS idx_resources_dataset
            ON resources(dataset_id);

        CREATE INDEX IF NOT EXISTS idx_datasets_org
            ON datasets(organization_name);

        CREATE INDEX IF NOT EXISTS idx_datasets_modified
            ON datasets(metadata_modified);

        CREATE VIRTUAL TABLE IF NOT EXISTS datasets_fts USING fts5(
            title,
            title_fi,
            title_en,
            notes_fi,
            notes_en,
            keywords_fi,
            keywords_en,
            organization_title,
            content='datasets',
            content_rowid='rowid',
            tokenize='unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS datasets_ai AFTER INSERT ON datasets BEGIN
            INSERT INTO datasets_fts(
                rowid, title, title_fi, title_en,
                notes_fi, notes_en, keywords_fi, keywords_en,
                organization_title
            ) VALUES (
                new.rowid, new.title, new.title_fi, new.title_en,
                new.notes_fi, new.notes_en, new.keywords_fi, new.keywords_en,
                new.organization_title
            );
        END;

        CREATE TRIGGER IF NOT EXISTS datasets_ad AFTER DELETE ON datasets BEGIN
            INSERT INTO datasets_fts(
                datasets_fts, rowid, title, title_fi, title_en,
                notes_fi, notes_en, keywords_fi, keywords_en,
                organization_title
            ) VALUES (
                'delete', old.rowid, old.title, old.title_fi, old.title_en,
                old.notes_fi, old.notes_en, old.keywords_fi, old.keywords_en,
                old.organization_title
            );
        END;

        CREATE TRIGGER IF NOT EXISTS datasets_au AFTER UPDATE ON datasets BEGIN
            INSERT INTO datasets_fts(
                datasets_fts, rowid, title, title_fi, title_en,
                notes_fi, notes_en, keywords_fi, keywords_en,
                organization_title
            ) VALUES (
                'delete', old.rowid, old.title, old.title_fi, old.title_en,
                old.notes_fi, old.notes_en, old.keywords_fi, old.keywords_en,
                old.organization_title
            );
            INSERT INTO datasets_fts(
                rowid, title, title_fi, title_en,
                notes_fi, notes_en, keywords_fi, keywords_en,
                organization_title
            ) VALUES (
                new.rowid, new.title, new.title_fi, new.title_en,
                new.notes_fi, new.notes_en, new.keywords_fi, new.keywords_en,
                new.organization_title
            );
        END;
    """)
    conn.commit()


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
            update_frequency, collection_type, num_resources, source
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?
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
