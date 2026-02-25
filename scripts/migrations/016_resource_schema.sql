-- Resurssien kenttätason skeema (schema introspection)
CREATE TABLE IF NOT EXISTS resource_schema (
    resource_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_type TEXT DEFAULT '',
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (resource_id, field_name)
);

CREATE INDEX IF NOT EXISTS idx_resource_schema_dataset ON resource_schema(dataset_id);
CREATE INDEX IF NOT EXISTS idx_resource_schema_field ON resource_schema(field_name);
