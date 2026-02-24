[Takaisin etusivulle](./)

# Dataformaatit

Aura indeksoi avointa dataa useissa eri formaateissa. Tämä sivu kuvaa yleisimmät formaatit ja niiden ominaisuudet.

## Rajapintaformaatit

### WFS — Web Feature Service

OGC-standardin mukainen rajapinta **vektorimuotoisen paikkatiedon** jakamiseen. Asiakas voi hakea kohteita aluerajauksella, suodattimella ja haluamassaan koordinaatistossa. Palauttaa tyypillisesti GML- tai GeoJSON-muotoista dataa.

- **Käyttökohde:** Paikkatietokohteiden haku ja analyysi (rakennukset, tiet, kiinteistöt)
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** FMI, GTK, kunnat, MML, SYKE, Metsäkeskus, avoindata.fi (845 resurssia)

### WMS — Web Map Service

OGC-standardin mukainen **karttakuvapalvelu**. Palauttaa renderöityjä karttakuvia (PNG/JPEG), ei raakadataa. Sopii visualisointiin mutta ei data-analyysiin.

- **Käyttökohde:** Karttatasojen visualisointi, taustakartat
- **Koneluettava:** Ei (kuvia)
- **Lähteitä Aurassa:** kunnat, MML, GTK, LIPAS, PaItuli, avoindata.fi (1 051 resurssia)

### WCS — Web Coverage Service

OGC-standardin mukainen rajapinta **rasteriaineistojen** (esim. korkeusmallit, satelliittikuvat) jakamiseen. Palauttaa numeerista ruutukkodataa, ei renderöityjä kuvia.

- **Käyttökohde:** Korkeusmallit, maaperäkartat, ilmakuvat
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** MML, Metsäkeskus, SYKE, avoindata.fi (54 resurssia)

### OGC API

Uuden sukupolven OGC-rajapintastandardi, joka korvaa WFS/WMS/WCS-palvelut REST-pohjaisella arkkitehtuurilla. Palauttaa JSON/GeoJSON-muotoista dataa.

- **Käyttökohde:** Moderni paikkatietorajapinta
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** MML, Väylävirasto, avoindata.fi (97 resurssia)

### PxWeb

Tilastollisten taulukkojen rajapinta, jota käyttävät pohjoismaiset tilastoviranomaiset. Mahdollistaa dimensioiden valinnan ja pienten dataleikkausten haun JSON-stat-muodossa.

- **Käyttökohde:** Tilastotaulukot (väestö, talous, ympäristö)
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** Tilastokeskus (StatFin), LUKE, HRI (2 326 resurssia)

### OData

Microsoftin kehittämä REST-pohjainen dataprotokolla. Tukee suodatusta, lajittelua ja paginointia URL-parametreilla.

- **Käyttökohde:** Hallinnolliset rekisterit ja tietokannat
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** Traficom (32 resurssia)

### API (yleinen)

REST- tai muu HTTP-rajapinta, joka ei noudata tiettyä standardia. Kattaa mm. JSON-pohjaisia palveluita.

- **Käyttökohde:** Vaihtelee — reaaliaikaiset palvelut, rekisterit
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** Digitraffic, kunnat, MML, Ruokavirasto, STUK (260 resurssia)

## Tiedostoformaatit

### CSV — Comma-Separated Values

Yksinkertainen taulukkomuotoinen tekstitiedosto, jossa sarakkeet erotetaan pilkulla tai puolipisteellä. Laajimmin tuettu avoin dataformaatti.

- **Käyttökohde:** Taulukkodata, tilastot, listat
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi, HRI, LUKE, Vaalirahoitusvalvonta (550 resurssia)

### JSON — JavaScript Object Notation

Rakenteellinen tekstimuotoinen dataformaatti. Kevyt ja laajasti tuettu API-vastauksissa ja konfiguraatiotiedostoissa.

- **Käyttökohde:** API-vastaukset, konfiguraatiot, hierarkkinen data
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi, HRI, LUKE (142 resurssia)

### GeoJSON

JSON-pohjainen formaatti maantieteellisten kohteiden kuvaamiseen. Sisältää geometriat (pisteet, viivat, polygonit) ja ominaisuustiedot.

- **Käyttökohde:** Paikkatietokohteet verkkokartoissa
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi, HRI (23 resurssia)

### GeoPackage (GPKG)

SQLite-pohjainen paikkatietokanta, joka sisältää vektori- ja/tai rasteridataa. OGC-standardi, korvaa Shapefile-formaatin.

- **Käyttökohde:** Paikkatietoaineistojen jakelu ja arkistointi
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi, HRI, Ruokavirasto (28 resurssia)

### XML — Extensible Markup Language

Rakenteellinen merkintäkieli, jota käytetään mm. INSPIRE-metatiedoissa ja vanhoissa rajapinnoissa.

- **Käyttökohde:** Metatiedot, konfiguraatiot, vanhat rajapinnat
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi, HRI, SYKE (112 resurssia)

### XLSX / XLS — Excel

Microsoftin taulukkolaskentaformaatti. XLSX on uudempi XML-pohjainen versio, XLS vanha binääriformaatti.

- **Käyttökohde:** Taulukkomuotoinen data, raportit
- **Koneluettava:** Osittain (vaatii kirjaston, ei suoraan tekstipohjainen)
- **Lähteitä Aurassa:** avoindata.fi, HRI, SYKE (860 + 113 resurssia)

### Shapefile (SHP)

ESRIn kehittämä paikkatietoformaatti. Koostuu useista tiedostoista (.shp, .dbf, .shx, .prj). Laajasti käytetty mutta teknisesti vanhentunut — GeoPackage on suositeltu korvaaja.

- **Käyttökohde:** Paikkatietoaineistojen siirto ja jakelu
- **Koneluettava:** Kyllä (vaatii GIS-kirjaston)
- **Lähteitä Aurassa:** avoindata.fi, HRI (270 resurssia)

### KML — Keyhole Markup Language

XML-pohjainen formaatti maantieteellisten kohteiden kuvaamiseen. Googlen kehittämä, käytetään mm. Google Earthissa.

- **Käyttökohde:** Paikkatiedon visualisointi ja jakelu
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi, HRI (73 resurssia)

### GeoTIFF / TIFF

Rasterikuvaformaatti, joka sisältää paikkatiedon (koordinaatisto, sijainti) kuvan metatiedoissa. Käytetään mm. ilmakuvissa ja korkeusmalleissa.

- **Käyttökohde:** Ilmakuvat, korkeusmallit, satelliittikuvat
- **Koneluettava:** Kyllä (vaatii rasterityökalun)
- **Lähteitä Aurassa:** avoindata.fi, HRI (35 + 17 resurssia)

### KuntaGML

Suomalainen XML-pohjainen formaatti kuntien kaava- ja rakennustiedon siirtoon. Perustuu INSPIRE-direktiiviin.

- **Käyttökohde:** Asemakaavat, rakennusluvat, kuntarekisterit
- **Koneluettava:** Kyllä
- **Lähteitä Aurassa:** avoindata.fi (71 resurssia)

### PDF

Adoben dokumenttiformaatti. Ei ole koneluettava dataformaatti — sisältää tyypillisesti raportteja, selvityksiä tai karttaesityksiä.

- **Käyttökohde:** Raportit, selvitykset, karttaesitykset
- **Koneluettava:** Ei
- **Lähteitä Aurassa:** avoindata.fi, SYKE (338 resurssia)

### HTML

Verkkosivuformaatti. Aurassa HTML-resurssit ovat tyypillisesti linkkejä tietosivuille tai datan katselunäkymiin, eivät raakadataa.

- **Käyttökohde:** Dokumentaatio, käyttöliittymät, tietosivut
- **Koneluettava:** Ei (vaatii parsintaa)
- **Lähteitä Aurassa:** avoindata.fi, LUKE, Metsäkeskus, Ruokavirasto (2 409 resurssia)

### ZIP

Pakattu arkistotiedosto, joka voi sisältää mitä tahansa dataa. Usein käytetään Shapefile-aineistojen tai suurten CSV-tiedostojen jakeluun.

- **Käyttökohde:** Suurten aineistojen jakelu
- **Koneluettava:** Riippuu sisällöstä
- **Lähteitä Aurassa:** avoindata.fi, LUKE, Metsäkeskus, SYKE (335 resurssia)

## Formaattien koneluettavuus

Aura luokittelee seuraavat formaatit koneluettaviksi:

**CSV**, **JSON**, **GeoJSON**, **WFS**, **WMS**, **WCS**, **OData**, **XML**, **API**, **Parquet**, **GeoParquet**, **GPKG**, **SQLite**

Koneluettavuus tarkoittaa, että data on suoraan ohjelmallisesti käsiteltävissä ilman ihmisen tulkintaa. Formaatit kuten PDF, HTML ja kuvatiedostot eivät ole koneluettavia, vaikka ne voivat sisältää arvokasta tietoa.
