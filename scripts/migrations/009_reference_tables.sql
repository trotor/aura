-- Viiteaineistotaulut populaattoreille

CREATE TABLE IF NOT EXISTS ref_metadata (
    name TEXT PRIMARY KEY,
    record_count INTEGER DEFAULT 0,
    version TEXT DEFAULT '',
    populated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ref_municipalities (
    code TEXT PRIMARY KEY,
    name_fi TEXT NOT NULL,
    name_sv TEXT NOT NULL,
    region_code TEXT,
    region_name_fi TEXT,
    ely_code TEXT,
    ely_name_fi TEXT,
    wellbeing_area_code TEXT,
    wellbeing_area_name_fi TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ref_muni_region ON ref_municipalities(region_code);
