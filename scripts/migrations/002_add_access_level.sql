-- Lisää access_level-kenttä dataseteille.
-- Arvot: "open" (oletus), "registration", "restricted"

ALTER TABLE datasets ADD COLUMN access_level TEXT DEFAULT 'open';
