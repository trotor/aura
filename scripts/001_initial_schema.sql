-- Aura: Alkuperäinen tietokantaskeema
-- Versio: 0.1.0
-- Tämä skeema luodaan automaattisesti database.py:n init_db()-funktiolla.
-- Tämä tiedosto on dokumentaatiota varten.

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

CREATE INDEX IF NOT EXISTS idx_resources_dataset ON resources(dataset_id);
CREATE INDEX IF NOT EXISTS idx_datasets_org ON datasets(organization_name);
CREATE INDEX IF NOT EXISTS idx_datasets_modified ON datasets(metadata_modified);

CREATE VIRTUAL TABLE IF NOT EXISTS datasets_fts USING fts5(
    title, title_fi, title_en,
    notes_fi, notes_en,
    keywords_fi, keywords_en,
    organization_title,
    content='datasets',
    content_rowid='rowid',
    tokenize='unicode61'
);
