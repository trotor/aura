-- Aluetasojen ristiintaulukko ja kuntaliitoshistoria.
--
-- Kuntataulu (ref_municipalities) tietää kunnan maakunnan ja
-- hyvinvointialueen, mutta ei seutukuntaa, suuraluetta, NUTS-tasoja eikä
-- elinvoimakeskusta. Jokainen uusi taso olisi ollut kaksi uutta saraketta
-- lisää. Yleinen muoto on pienempi: alue on (taso, koodi), ja kunnan
-- jäsenyys tasolla on yksi rivi.
--
-- Kuntaliitoshistoria on oma taulunsa, koska se vastaa eri kysymykseen:
-- mikä *nykyinen* kunta on koodin X seuraaja. Ilman sitä aikasarja joka
-- ylittää liitoksen katkeaa hiljaa — vanhan kunnan koodi ei osu mihinkään.

CREATE TABLE IF NOT EXISTS ref_areas (
    level TEXT NOT NULL,
    code TEXT NOT NULL,
    name_fi TEXT NOT NULL,
    name_sv TEXT,
    vintage INTEGER NOT NULL,
    PRIMARY KEY (level, code)
);

CREATE INDEX IF NOT EXISTS idx_ref_areas_name ON ref_areas(name_fi COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS ref_area_membership (
    municipality_code TEXT NOT NULL,
    level TEXT NOT NULL,
    area_code TEXT NOT NULL,
    vintage INTEGER NOT NULL,
    PRIMARY KEY (municipality_code, level)
);

CREATE INDEX IF NOT EXISTS idx_ref_area_membership_area
    ON ref_area_membership(level, area_code);

-- effective_year NULL = liitos on vanhempi kuin luokituspalvelun
-- vuosiversiot (ensimmäinen on 2012), joten vuotta ei voi päätellä.
CREATE TABLE IF NOT EXISTS ref_municipality_changes (
    old_code TEXT PRIMARY KEY,
    old_name_fi TEXT NOT NULL,
    new_code TEXT NOT NULL,
    new_name_fi TEXT NOT NULL,
    effective_year INTEGER,
    source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ref_municipality_changes_new
    ON ref_municipality_changes(new_code);
