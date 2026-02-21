-- Laajenna FTS5-indeksi: lisää title_sv, notes_sv, notes, name.
-- FTS5 content-synced taulua ei voi ALTER:oida, joten pudotetaan ja luodaan uudelleen.

-- Poista vanhat triggerit
DROP TRIGGER IF EXISTS datasets_ai;
DROP TRIGGER IF EXISTS datasets_ad;
DROP TRIGGER IF EXISTS datasets_au;

-- Poista vanha FTS-taulu
DROP TABLE IF EXISTS datasets_fts;

-- Luo uusi FTS5-taulu laajennetuilla sarakkeilla
CREATE VIRTUAL TABLE datasets_fts USING fts5(
    name,
    title,
    title_fi,
    title_en,
    title_sv,
    notes,
    notes_fi,
    notes_en,
    notes_sv,
    keywords_fi,
    keywords_en,
    organization_title,
    content='datasets',
    content_rowid='rowid',
    tokenize='unicode61'
);

-- Triggerit uusilla sarakkeilla
CREATE TRIGGER datasets_ai AFTER INSERT ON datasets BEGIN
    INSERT INTO datasets_fts(
        rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title
    ) VALUES (
        new.rowid, new.name, new.title, new.title_fi, new.title_en, new.title_sv,
        new.notes, new.notes_fi, new.notes_en, new.notes_sv,
        new.keywords_fi, new.keywords_en, new.organization_title
    );
END;

CREATE TRIGGER datasets_ad AFTER DELETE ON datasets BEGIN
    INSERT INTO datasets_fts(
        datasets_fts, rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title
    ) VALUES (
        'delete', old.rowid, old.name, old.title, old.title_fi, old.title_en, old.title_sv,
        old.notes, old.notes_fi, old.notes_en, old.notes_sv,
        old.keywords_fi, old.keywords_en, old.organization_title
    );
END;

CREATE TRIGGER datasets_au AFTER UPDATE ON datasets BEGIN
    INSERT INTO datasets_fts(
        datasets_fts, rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title
    ) VALUES (
        'delete', old.rowid, old.name, old.title, old.title_fi, old.title_en, old.title_sv,
        old.notes, old.notes_fi, old.notes_en, old.notes_sv,
        old.keywords_fi, old.keywords_en, old.organization_title
    );
    INSERT INTO datasets_fts(
        rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title
    ) VALUES (
        new.rowid, new.name, new.title, new.title_fi, new.title_en, new.title_sv,
        new.notes, new.notes_fi, new.notes_en, new.notes_sv,
        new.keywords_fi, new.keywords_en, new.organization_title
    );
END;

-- Rebuild: populoi FTS-indeksi olemassaolevasta datasta
INSERT INTO datasets_fts(datasets_fts) VALUES('rebuild');
