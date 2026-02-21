-- FTS5-indeksi enrichmenteille: korvaa hidas LIKE-haku täystekstihaulla.
-- Indeksoi vain hakuun relevantit kentät (keywords, tags, description_extended).

CREATE VIRTUAL TABLE IF NOT EXISTS enrichments_fts USING fts5(
    dataset_id UNINDEXED,
    value,
    tokenize='unicode61'
);

-- Triggerit: pidä FTS synkassa enrichments-taulun kanssa
CREATE TRIGGER IF NOT EXISTS enrichments_fts_ai AFTER INSERT ON enrichments
WHEN NEW.field IN ('keywords', 'tags', 'description_extended')
BEGIN
    INSERT INTO enrichments_fts(rowid, dataset_id, value)
    VALUES (NEW.rowid, NEW.dataset_id, NEW.value);
END;

CREATE TRIGGER IF NOT EXISTS enrichments_fts_ad AFTER DELETE ON enrichments
WHEN OLD.field IN ('keywords', 'tags', 'description_extended')
BEGIN
    INSERT INTO enrichments_fts(enrichments_fts, rowid, dataset_id, value)
    VALUES ('delete', OLD.rowid, OLD.dataset_id, OLD.value);
END;

-- Populoi olemassaolevat enrichmentit
INSERT INTO enrichments_fts(rowid, dataset_id, value)
SELECT rowid, dataset_id, value
FROM enrichments
WHERE field IN ('keywords', 'tags', 'description_extended');
