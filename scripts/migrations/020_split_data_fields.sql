-- 020: Siirrä bbox- ja koordinaatistoarvot pois data_fields-kentästä
--
-- VIKA: `data_fields` oli päätynyt kaatoluokaksi. Kentän nimi lupaa
-- aineiston sarakenimiä, mutta 1 864 rivistä vain 7 oli sellaisia:
--
--     1 207  bbox-koordinaatteja      ("bbox: [W:19.09, S:59.60, ...]")
--       650  koordinaatistotunnuksia  ("EPSG:3067", "urn:ogc:def:crs:EPSG",
--                                       "http://www.opengis.net/def/crs/...",
--                                       "YKJ", "KKJ1", "4326", "ESPG:3067")
--         7  aitoja kenttälistoja     (JSON-taulukko)
--
-- Koordinaatistolle oli jo oma `crs`-kenttänsä (1 542 riviä), eli sama tieto
-- oli kahdessa paikassa eri nimellä. bbox:lle ei ollut kenttää lainkaan.
--
-- Seuraus ei ollut hakuvirhe: `enrichments_fts` indeksoi vain kentät
-- 'keywords', 'tags', 'description_extended' ja 'yso_concepts', joten nämä
-- rivit eivät olleet hakupolussa. Vika näkyi siellä missä rikastukset
-- esitetään sellaisenaan — `describe()` ja `get_enrichments_tool()` kertoivat
-- agentille bbox-koordinaatteja otsikolla "data_fields".
--
-- KORJAUS: bbox omaan kenttäänsä, koordinaatistot olemassa olevaan `crs`:ään,
-- ja `data_fields` jää tarkoittamaan sitä mitä nimi lupaa.
--
-- Luokittelusääntö on tyhjentävä eikä arvattu: kaikki arvot on lueteltu ja
-- tarkistettu. Kaikki mikä ei ole JSON-taulukko on joko bbox tai koordinaatisto.

-- 1) bbox omaan kenttäänsä. Tehdään ensin, jotta seuraava sääntö voi olla
--    yksinkertainen "kaikki muu paitsi JSON-lista".
UPDATE enrichments
   SET field = 'bbox'
 WHERE field = 'data_fields'
   AND TRIM(value) LIKE 'bbox:%';

-- 2) Loput koordinaatistoja — paitsi aidot kenttälistat, jotka jäävät.
UPDATE enrichments
   SET field = 'crs'
 WHERE field = 'data_fields'
   AND TRIM(value) NOT LIKE '[%';

-- 3) Siirto tuottaa täsmällisiä duplikaatteja siellä missä datasetillä oli jo
--    sama koordinaatisto `crs`-kentässä (93 riviä). Vanhin säilyy.
DELETE FROM enrichments
 WHERE id IN (
   SELECT id FROM (
     SELECT id,
            ROW_NUMBER() OVER (
              PARTITION BY dataset_id, field, value
              ORDER BY created_at, id
            ) AS rn
       FROM enrichments
      WHERE field IN ('crs', 'bbox')
   )
   WHERE rn > 1
 );
