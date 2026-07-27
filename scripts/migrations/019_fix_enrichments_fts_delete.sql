-- 019: Korjaa enrichments_fts:n poisto- ja päivitystriggerit
--
-- VIKA: enrichments_fts on tavallinen FTS5-taulu (se säilyttää oman
-- sisältönsä), mutta triggerit käyttivät ulkoisen sisällön tauluille
-- tarkoitettua erikoiskomentoa:
--
--     INSERT INTO enrichments_fts(enrichments_fts, rowid, ...) VALUES ('delete', ...)
--
-- Tavallisella FTS5-taululla tuo nostaa "SQL logic error". Seuraus: minkä
-- tahansa rikastuksen poisto epäonnistui, jos sen field oli yksi
-- indeksoiduista ('keywords', 'tags', 'description_extended', 'yso_concepts').
-- Vika esti sekä `aura prune-enrichments` -komennon toiminnan näiden rivien
-- osalta että datasettien poiston.
--
-- KORJAUS: tavallisesta FTS5-taulusta poistetaan tavallisella DELETEllä.

DROP TRIGGER IF EXISTS enrichments_fts_ad;
DROP TRIGGER IF EXISTS enrichments_fts_au;

CREATE TRIGGER enrichments_fts_ad AFTER DELETE ON enrichments
BEGIN
    DELETE FROM enrichments_fts WHERE rowid = OLD.rowid;
END;

-- Päivitys: poista vanha rivi indeksistä ja lisää uusi, jos uusi kenttä
-- kuuluu indeksoitaviin. Ehto on rivin sisällä, koska WHEN-ehto ei voi
-- kattaa molempia suuntia (indeksoitu -> ei-indeksoitu ja päinvastoin).
CREATE TRIGGER enrichments_fts_au AFTER UPDATE ON enrichments
BEGIN
    DELETE FROM enrichments_fts WHERE rowid = OLD.rowid;
    INSERT INTO enrichments_fts(rowid, dataset_id, value)
    SELECT NEW.rowid, NEW.dataset_id, NEW.value
    WHERE NEW.field IN ('keywords', 'tags', 'description_extended', 'yso_concepts');
END;
