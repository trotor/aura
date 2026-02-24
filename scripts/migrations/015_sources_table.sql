-- Sources-taulu: datalähteiden konfiguraatio ja metatiedot
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    url TEXT DEFAULT '',
    harvester_type TEXT DEFAULT '',
    query_protocol TEXT DEFAULT '',
    api_base_url TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    dataset_count INTEGER DEFAULT 0,
    last_harvested_at TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
