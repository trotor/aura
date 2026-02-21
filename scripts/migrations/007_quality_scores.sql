-- Laatupisteytys: neljä dimensiota + kokonaispisteet per datasetti.
CREATE TABLE IF NOT EXISTS quality_scores (
    dataset_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    score REAL NOT NULL,
    details TEXT,
    calculated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (dataset_id, dimension)
);

CREATE INDEX IF NOT EXISTS idx_quality_dataset ON quality_scores(dataset_id);
CREATE INDEX IF NOT EXISTS idx_quality_dimension_score ON quality_scores(dimension, score);
