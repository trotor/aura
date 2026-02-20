-- Joukkoistettava tiedon rikastaminen (crowdsourced enrichments).
-- Erillinen taulu harvestoidusta datasta — ei ylikirjoiteta harvestissa.
-- Ei FK-rajoitetta: dataset_id voi viitata myös datasettiin jota ei ole vielä harvestoitu.

CREATE TABLE IF NOT EXISTS enrichments (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium',
    source_type TEXT NOT NULL,
    source_detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_enrichments_dataset
    ON enrichments(dataset_id);

CREATE INDEX IF NOT EXISTS idx_enrichments_dataset_field
    ON enrichments(dataset_id, field);
