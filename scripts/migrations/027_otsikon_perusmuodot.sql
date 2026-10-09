-- Otsikon perusmuodot omaan FTS-sarakkeeseensa korkealla painolla.
--
-- Perusmuotosarake (018) painaa saman verran tuli sana otsikosta tai
-- kuvauksesta. Siksi taivutettu otsikko hävisi aineistolle, jonka otsikossa
-- sana on sellaisenaan: haku "kunnan tilinpäätös" nosti "Keminmaan kunnan
-- ostolaskut" (otsikossa "kunnan", kuvauksessa "tilinpäätöksen") taulun
-- "Kuntien tilinpäätökset" ohi, vaikka molemmat osuivat tiukkaan hakuun.
--
-- Sarake populoidaan erikseen: `python -m aura.cli lemmatize`.
-- FTS5 content-synced taulua ei voi ALTER:oida, joten se rakennetaan uudelleen.

ALTER TABLE datasets ADD COLUMN title_lemmas TEXT DEFAULT '';

DROP TRIGGER IF EXISTS datasets_ai;
DROP TRIGGER IF EXISTS datasets_ad;
DROP TRIGGER IF EXISTS datasets_au;

DROP TABLE IF EXISTS datasets_fts;

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
    lemmas,
    title_lemmas,
    content='datasets',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER datasets_ai AFTER INSERT ON datasets BEGIN
    INSERT INTO datasets_fts(
        rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title, lemmas, title_lemmas
    ) VALUES (
        new.rowid, new.name, new.title, new.title_fi, new.title_en, new.title_sv,
        new.notes, new.notes_fi, new.notes_en, new.notes_sv,
        new.keywords_fi, new.keywords_en, new.organization_title, new.lemmas, new.title_lemmas
    );
END;

CREATE TRIGGER datasets_ad AFTER DELETE ON datasets BEGIN
    INSERT INTO datasets_fts(
        datasets_fts, rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title, lemmas, title_lemmas
    ) VALUES (
        'delete', old.rowid, old.name, old.title, old.title_fi, old.title_en, old.title_sv,
        old.notes, old.notes_fi, old.notes_en, old.notes_sv,
        old.keywords_fi, old.keywords_en, old.organization_title, old.lemmas, old.title_lemmas
    );
END;

CREATE TRIGGER datasets_au AFTER UPDATE ON datasets BEGIN
    INSERT INTO datasets_fts(
        datasets_fts, rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title, lemmas, title_lemmas
    ) VALUES (
        'delete', old.rowid, old.name, old.title, old.title_fi, old.title_en, old.title_sv,
        old.notes, old.notes_fi, old.notes_en, old.notes_sv,
        old.keywords_fi, old.keywords_en, old.organization_title, old.lemmas, old.title_lemmas
    );
    INSERT INTO datasets_fts(
        rowid, name, title, title_fi, title_en, title_sv,
        notes, notes_fi, notes_en, notes_sv,
        keywords_fi, keywords_en, organization_title, lemmas, title_lemmas
    ) VALUES (
        new.rowid, new.name, new.title, new.title_fi, new.title_en, new.title_sv,
        new.notes, new.notes_fi, new.notes_en, new.notes_sv,
        new.keywords_fi, new.keywords_en, new.organization_title, new.lemmas, new.title_lemmas
    );
END;

INSERT INTO datasets_fts(datasets_fts) VALUES('rebuild');
