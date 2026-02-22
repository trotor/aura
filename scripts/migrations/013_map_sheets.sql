-- TM35-karttalehtijako viitetaulu

CREATE TABLE IF NOT EXISTS ref_map_sheets (
    id TEXT PRIMARY KEY,          -- lehtitunnus, esim. "L4133A"
    scale TEXT NOT NULL,          -- taso: "utm200", "utm50", "utm25", "utm10"
    min_x REAL NOT NULL,          -- bbox EPSG:3067
    min_y REAL NOT NULL,
    max_x REAL NOT NULL,
    max_y REAL NOT NULL,
    centroid_x REAL,
    centroid_y REAL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ref_map_sheets_scale ON ref_map_sheets(scale);
