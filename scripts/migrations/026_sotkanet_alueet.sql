-- Sotkanetin koko aluerekisteri omana taulunaan.
--
-- Ulkoinen arvio 27.9.2026: Sotkanetin rivin ``region`` tulkittiin vain
-- kunnille (ref_municipalities.sotkanet_id). Maakunnan, hyvinvointialueen,
-- seutukunnan tai koko maan rivit jäivät ilman nimeä ja koodia, ja agentti
-- joutui arvaamaan mitä alue 658 tarkoittaa (se on koko maa).
--
-- /rest/1.1/regions antaa 540 aluetta 15 kategoriassa (KUNTA, MAAKUNTA,
-- HYVINVOINTIALUE, SEUTUKUNTA, SAIRAANHOITOPIIRI, ELY-KESKUS, MAA, ...).
-- ``id`` on Sotkanetin oma aluetunnus, ``code`` kategorian oma koodi
-- (kotimaisissa Tilastokeskuksen koodi, esim. kunta 837, maakunta 06).
--
-- Populoi: municipalities-populaattori (sama haku kuin sotkanet_id-sarakkeille).

CREATE TABLE IF NOT EXISTS ref_sotkanet_regions (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    code TEXT,
    name_fi TEXT,
    name_sv TEXT,
    name_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_ref_sotkanet_regions_category
    ON ref_sotkanet_regions(category, code);
