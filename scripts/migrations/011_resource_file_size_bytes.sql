-- Add file_size_bytes numeric column to resources
-- Parsed from file_size TEXT using size_estimator.parse_file_size()
-- Backfill happens in Python (run_migrations post-hook)

ALTER TABLE resources ADD COLUMN file_size_bytes INTEGER DEFAULT 0;

-- Backfill simple numeric values directly in SQL
UPDATE resources SET file_size_bytes = CAST(file_size AS INTEGER)
WHERE file_size != '' AND file_size GLOB '[0-9]*' AND file_size NOT GLOB '*[^0-9]*';
