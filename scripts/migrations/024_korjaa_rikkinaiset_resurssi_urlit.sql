-- Korjaa kaksi tunnetusti rikkinäistä resurssi-URL-muotoa olemassa olevista
-- riveistä. Harvestointi korjaa ne jatkossa itse (aura.url_normalize kytkettynä
-- BaseHarvester._make_dataset-metodiin), mutta ilman tätä migraatiota korjaus
-- vaikuttaisi vasta seuraavan täyden harvestoinnin jälkeen.
--
-- Probe-vaiheen ensimmäinen ajo paljasti molemmat: noin 26 epäonnistumista
-- 65:stä johtui näistä eikä palvelun viasta. Aineistot näyttävät katalogissa
-- käyttökelpoisilta vaikka osoite ei toimi lainkaan.
--
-- Molemmat säännöt on todennettu elävää palvelua vasten, ja tuloksen
-- yhtäpitävyys aura.url_normalize-moduulin kanssa on tarkistettu rivi riviltä
-- kannan kopiolla ennen ajoa.
--
-- Migraatio on turvallinen ajaa kahdesti: WHERE-ehdot eivät osu enää
-- korjattuihin riveihin.

-- 1) stat.hel.fi: PxWebin selain-UI ei ole rajapinta (135 riviä).
--
--    /pxweb/fi/<db>/<db>__<taso>__<taso>/<taulu>.px/
--      -> /api/v1/fi/<db>/<taso>/<taso>/<taulu>.px
--
--    Yhdistetty segmentti purkautuu poluksi, koska tietokannan nimi on jo
--    omana segmenttinään. Tietokantoja on kannassa kaksi, ja ne käsitellään
--    erikseen: yhteinen etuliite tekisi yleisestä säännöstä vaikealukuisen.
--    Loppukauttaviiva poistetaan, koska API ei hyväksy sitä.

UPDATE resources
   SET url = rtrim(
         replace(
           replace(url,
                   '/pxweb/fi/Aluesarjat_Arkisto/Aluesarjat_Arkisto__',
                   '/api/v1/fi/Aluesarjat_Arkisto/'),
           '__', '/'),
         '/')
 WHERE url LIKE 'https://stat.hel.fi/pxweb/fi/Aluesarjat_Arkisto/Aluesarjat_Arkisto__%.px%';

UPDATE resources
   SET url = rtrim(
         replace(
           replace(url,
                   '/pxweb/fi/Aluesarjat/Aluesarjat__',
                   '/api/v1/fi/Aluesarjat/'),
           '__', '/'),
         '/')
 WHERE url LIKE 'https://stat.hel.fi/pxweb/fi/Aluesarjat/Aluesarjat__%.px%';

-- 2) Portti 80 https-osoitteessa (12 riviä).
--
--    Palvelin puhuu portissa 80 selväkielistä HTTP:tä, joten TLS-kättely
--    kaatuu virheeseen "SSL: WRONG_VERSION_NUMBER". Sama osoite ilman
--    porttia vastaa normaalisti. http-skeemalla portti 80 on turha muttei
--    väärä, eikä siihen kosketa.

UPDATE resources
   SET url = replace(url, 'https://geoserver.lounaistieto.fi:80/',
                          'https://geoserver.lounaistieto.fi/')
 WHERE url LIKE 'https://geoserver.lounaistieto.fi:80/%';
