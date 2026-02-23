-- Lisää yso_concepts enrichments_fts-triggereihin.
-- Aiemmin vain keywords, tags, description_extended indeksoitiin.

-- Poista vanhat triggerit
DROP TRIGGER IF EXISTS enrichments_fts_ai;
DROP TRIGGER IF EXISTS enrichments_fts_ad;

-- Luo triggerit uudelleen yso_concepts mukana
CREATE TRIGGER enrichments_fts_ai AFTER INSERT ON enrichments
WHEN NEW.field IN ('keywords', 'tags', 'description_extended', 'yso_concepts')
BEGIN
    INSERT INTO enrichments_fts(rowid, dataset_id, value)
    VALUES (NEW.rowid, NEW.dataset_id, NEW.value);
END;

CREATE TRIGGER enrichments_fts_ad AFTER DELETE ON enrichments
WHEN OLD.field IN ('keywords', 'tags', 'description_extended', 'yso_concepts')
BEGIN
    INSERT INTO enrichments_fts(enrichments_fts, rowid, dataset_id, value)
    VALUES ('delete', OLD.rowid, OLD.dataset_id, OLD.value);
END;

-- Populoi olemassaolevat yso_concepts (muut kentät ovat jo indeksoitu)
INSERT INTO enrichments_fts(rowid, dataset_id, value)
SELECT rowid, dataset_id, value
FROM enrichments
WHERE field = 'yso_concepts'
AND rowid NOT IN (SELECT rowid FROM enrichments_fts);
