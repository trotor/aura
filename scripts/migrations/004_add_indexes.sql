-- Lisää puuttuvat indeksit yleisille suodatinkentille.

CREATE INDEX IF NOT EXISTS idx_datasets_source ON datasets(source);
CREATE INDEX IF NOT EXISTS idx_datasets_access_level ON datasets(access_level);
CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets(name);
CREATE INDEX IF NOT EXISTS idx_resources_format ON resources(format);
