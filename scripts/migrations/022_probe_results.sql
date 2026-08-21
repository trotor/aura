-- Probe-vaiheen kirjanpito: viimeisin tila per resurssi.
--
-- Erillinen taulu enrichmenteistä, koska TTL ja jatkaminen vaativat
-- indeksoituja kyselyitä ("mitkä ovat vanhentuneet", "mitä ei ole
-- yritetty"), ja enrichments on versioitu lisäystaulu johon kirjanpito
-- paisuisi.
--
-- Tämä on myös se paikka jossa epäonnistuminen näkyy. Aiemmin
-- infer-schemas tulosti virheen ja unohti sen: sama rikkinäinen resurssi
-- yritettiin uudestaan joka ajolla eikä kukaan tiennyt mikä on rikki.

CREATE TABLE IF NOT EXISTS probe_results (
    resource_id TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL,
    probe_type  TEXT NOT NULL,
    status      TEXT NOT NULL,
    detail      TEXT DEFAULT '',
    probed_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_probe_results_probed_at
    ON probe_results(probed_at);
CREATE INDEX IF NOT EXISTS idx_probe_results_dataset
    ON probe_results(dataset_id);
