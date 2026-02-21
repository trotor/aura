-- Resurssien saatavuustarkistusten tulokset
CREATE TABLE IF NOT EXISTS resource_health (
    resource_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    content_type TEXT,
    content_length INTEGER,
    is_available BOOLEAN NOT NULL,
    error_message TEXT,
    checked_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id)
);

CREATE INDEX IF NOT EXISTS idx_health_dataset ON resource_health(dataset_id);
CREATE INDEX IF NOT EXISTS idx_health_available ON resource_health(is_available);
CREATE INDEX IF NOT EXISTS idx_health_checked ON resource_health(checked_at);
