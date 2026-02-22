-- Normalize organization data to own table
-- Populate from existing datasets, keep backward-compat columns

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    title TEXT DEFAULT '',
    title_fi TEXT DEFAULT '',
    title_en TEXT DEFAULT '',
    description TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    homepage TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_organizations_name ON organizations(name);

-- Populate from existing datasets
INSERT OR IGNORE INTO organizations (id, name, title)
SELECT DISTINCT organization_id, organization_name, organization_title
FROM datasets
WHERE organization_id != '';
