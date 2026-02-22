-- Postinumerotaulu

CREATE TABLE IF NOT EXISTS ref_postal_codes (
    code TEXT PRIMARY KEY,
    name_fi TEXT NOT NULL,
    name_sv TEXT NOT NULL,
    municipality_code TEXT REFERENCES ref_municipalities(code),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ref_postal_muni ON ref_postal_codes(municipality_code);
