[Takaisin etusivulle](./)

# Datalähteet ja harvestoidut aineistot

Tämä sivu dokumentoi kaikki Auran harvesteroimat datalähteet.

> Päivitetty: 2026-02-22

## Yhteenveto

| Lähde | Tyyppi | Datasettejä | Resursseja | Arvioitu koko |
|-------|--------|-------------|------------|---------------|
| [avoindata.fi](#avoindatafi) | CKAN API | 1 943 | 5 188 | 114 GB |
| [SYKE](#syke-suomen-ympäristökeskus) | CKAN API | ~615 | ~1 200 | ~50 GB |
| [HRI (hri.fi)](#hri-helsinki-region-infoshare) | CKAN API | 549 | 1 594 | 39 GB |
| [LUKE](#luke-luonnonvarakeskus) | PxWeb API | 495 | 990 | 2,3 GB |
| [Tilastokeskus (StatFin)](#tilastokeskus-statfin) | PxWeb API | 374 | 748 | 1,7 GB |
| [Digitraffic](#digitraffic) | REST/OpenAPI | 162 | 162 | 1,5 GB |
| [Ilmatieteen laitos (FMI)](#ilmatieteen-laitos-fmi) | WFS 2.0 | 160 | 160 | 14 GB |
| [Overture Maps](#overture-maps) | GeoParquet (S3) | 6 | 12 | ~215 GB |
| [Metsäkeskus](#metsäkeskus) | WFS/WCS/ZIP | 43 | 85 | 1,2 TB |
| [Traficom](#traficom) | OData v4 | 32 | 32 | 2,5 GB |
| [Ruokavirasto](#ruokavirasto) | INSPIRE/GeoServer | 33 | 97 | — |
| [MML](#mml-maanmittauslaitos) | WFS/WMS/WMTS | 7 | 16 | ~184 GB |
| [Tilastokeskus geo](#tilastokeskus-paikkatiedot) | WFS/WMS | 9 | 18 | ~5 GB |
| [Väylävirasto](#väylävirasto) | WFS/WMS/OGC API | 5 | 13 | ~9 GB |
| [PaItuli (CSC)](#paituli-csc) | WMS/WFS | 5 | 9 | ~88 GB |
| [LIPAS](#lipas) | WFS/WMS | 3 | 6 | ~1 GB |
| [Kuntien paikkatiedot](#kuntien-paikkatiedot) | WFS/WMS/ArcGIS | 36 | ~70 | ~57 GB |
| [Paikkatietoikkuna](#paikkatietoikkuna) | Oskari API | 689 | 3 329 | — |
| [STUK](#stuk-säteilyturvakeskus) | API | 2 | 2 | ~150 MB |
| [GTK](#gtk) | ArcGIS WFS/WMS | 5 | 8 | 7 GB |
| [Taustakartat](#taustakartat) | TMS | 4 | 4 | ~20 GB |
| **Yhteensä** | | **~6 500** | **~16 200** | **~2 TB** |

### Resurssityypit

Aura harvestoi sekä **rajapintoja** (API, WMS, WFS, OGC, PXWEB) että **aineistopaketteja** (CSV, XLSX, JSON, SHP, ZIP jne.):

| Formaatti | Resursseja |
|----------|-----------|
| HTML | 1 063 |
| PXWEB | 1 009 |
| WMS | 875 |
| XLSX | 842 |
| WFS | 753 |
| CSV | 482 |
| ZIP | 319 |
| SHP | 270 |
| PDF | 251 |
| API | 194 |

**Yhteensä: ~4 421 datasettiä, ~10 280 resurssia, 200+ organisaatiota, ~1,6 TB**

---

## avoindata.fi

**URL:** https://avoindata.suomi.fi
**API:** CKAN 3 REST (`https://avoindata.suomi.fi/data/api/3/action/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 1 943
**Resursseja:** 5 188
**Arvioitu koko:** 114 GB

Suomen kansallinen avoimen datan portaali. Aggregoi dataa kunnilta, ministeriöiltä, virastoilta ja tutkimuslaitoksilta.

#### Harvester-toteutus

`src/aura/harvesters/avoindata.py` — Käyttää CKAN:n `package_search` -endpointia sivuttaen 100 datasettiä kerrallaan. Jokainen CKAN-paketti muunnetaan `Dataset`-olioksi `Dataset.from_ckan()`-luokkametodilla.

#### Suurimmat julkaisijat

| Organisaatio | Datasettejä |
|-------------|-------------|
| Paikkatietohakemisto (ulkoinen lähde) | 245 |
| Turku | 231 |
| Suomen ympäristökeskus (SYKE) | 221 |
| Valtiovarainministeriö | 220 |
| Helsingin kaupunginkanslia | 198 |
| Väylävirasto | 193 |
| Helsingin kaupunkiympäristön toimiala | 94 |
| Oulu | 87 |
| Helsingin seudun ympäristöpalvelut (HSY) | 67 |
| Varsinais-Suomen liitto | 52 |

---

## HRI (Helsinki Region Infoshare)

**URL:** https://hri.fi
**API:** CKAN 3 REST (`https://hri.fi/data/api/3/action/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 549
**Resursseja:** 1 594
**Arvioitu koko:** 39 GB

Pääkaupunkiseudun avoimen datan portaali (Helsinki, Espoo, Vantaa, Kauniainen). Sama CKAN-rajapinta kuin avoindata.fi — harvester on lähes identtinen.

#### Harvester-toteutus

`src/aura/harvesters/hri.py` — Sama `package_search`-logiikka kuin avoindata.fi:lle, mutta eri base URL ja `source="hri.fi"`.

---

## LUKE (Luonnonvarakeskus)

**URL:** https://luke.fi
**API:** PxWeb REST (`https://statdb.luke.fi/PxWeb/api/v1/fi/LUKE/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 495
**Resursseja:** 990
**Arvioitu koko:** 2,3 GB

Luonnonvarakeskuksen tilastotietokannat. Maatalous-, metsä-, kala- ja riistatilastoja.

#### Harvester-toteutus

`src/aura/harvesters/luke.py` — Käy rekursiivisesti läpi PxWeb-puurakenteen. Kansiot (type `l`) käydään läpi, taulut (type `t`) tallennetaan datasetteiksi. Sama logiikka kuin Tilastokeskuksen harvesterissa.

**Pääkategoriat:** 01 Maatalous, 02 Metsä, 03 Kala ja riista, 04 Kansantalous, 06 Indikaattorit

---

## Tilastokeskus (StatFin)

**URL:** https://stat.fi
**API:** PxWeb REST (`https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 374
**Resursseja:** 748
**Arvioitu koko:** 1,7 GB

Suomen virallinen tilastoviranomainen. Harvester käy rekursiivisesti läpi PxWeb-puun ja kerää jokaisen tilastotaulun metadatan.

#### Harvester-toteutus

`src/aura/harvesters/statfin.py` — PxWeb-puun rekursiivinen läpikäynti. Jokainen taulu saa kaksi resurssia: PxWeb API -endpoint ja ihmisluettava web-sivu.

**Aihealueita:** Asuminen, energia, hinnat, kansantalous, koulutus, oikeus, palkat, terveys, työ, väestö, ympäristö...

---

## Digitraffic

**URL:** https://www.digitraffic.fi
**API:** REST/OpenAPI 3.0
**Autentikointi:** Ei tarvita (gzip-header suositeltava)
**Datasettejä:** 162
**Resursseja:** 162
**Arvioitu koko:** 1,5 GB

Reaaliaikaista ja lähes reaaliaikaista liikennedataa. Kolme erillistä rajapintaa:

| Rajapinta | URL | Endpointteja |
|-----------|-----|--------------|
| Tieliikenne | https://tie.digitraffic.fi | ~87 |
| Rautatieliikenne | https://rata.digitraffic.fi | ~58 |
| Meriliikenne | https://meri.digitraffic.fi | ~17 |

#### Harvester-toteutus

`src/aura/harvesters/digitraffic.py` — Parsii kunkin rajapinnan OpenAPI/Swagger-speksin ja luo datasetin jokaisesta GET-endpointista. Endpoint URL on resurssin osoite.

**Datatyyppejä:** Mittausasemat, sääasemat, LAM-pisteet, junien sijainnit, AIS-tiedot, vesiliikenteen varoitukset.

---

## Ilmatieteen laitos (FMI)

**URL:** https://www.ilmatieteenlaitos.fi
**API:** OGC WFS 2.0 (`https://opendata.fmi.fi/wfs`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 160
**Resursseja:** 160
**Arvioitu koko:** 14 GB

Sää-, ilmasto-, meri- ja säteilytietoa. WFS-rajapinta tarjoaa stored query -mekanismin jossa jokainen kysely on käytännössä oma datasettinsä.

#### Harvester-toteutus

`src/aura/harvesters/fmi.py` — Hakee `ListStoredQueries`-operaation XML-vastauksen ja parsii jokaisen `StoredQuery`-elementin. Kategorisoi kyselyt tittelinsä perusteella (sää, tutka, meri, ennuste, säteily, ilmanlaatu) ja arvioi koon sen mukaisesti.

**Datakategoriat:** Säähavainnot (reaaliaikainen + historia), sääennusteet (HARMONIE, MEPS, ECMWF), tutkakuvat, meritasotiedot, säteilyvalvonta, ilmanlaatu.

---

## Metsäkeskus

**URL:** https://avoin.metsakeskus.fi
**API:** GeoServer WFS/WCS + ZIP-aineistopaketit
**Autentikointi:** Ei tarvita
**Datasettejä:** 43
**Resursseja:** 85
**Arvioitu koko:** 1,2 TB

Suomen metsävaratiedot — ylivoimaisesti suurin yksittäinen datalähde kooltaan. Sisältää sekä rajapinnat (WFS/WCS) että ladattavat aineistopaketit (ZIP).

#### Harvester-toteutus

`src/aura/harvesters/metsakeskus.py` — Ei käytä WFS `GetCapabilities` -mekanismia, vaan listaa palvelut manuaalisesti (endpointit ovat hyvin dokumentoitu mutta hajanaisesti). Neljä pääkategoriaa:

1. **Metsävaratieto-palvelut** — Kuviotiedot, hilaruudukot, elinympäristöt, metsänkäyttöilmoitukset (GeoServer WFS + ZIP-lataukset)
2. **Latvusmalliaineistot (CHM)** — Vuosittaiset puuston latvusmallit 2008–2022 (WCS + ZIP-lataukset)
3. **Kemera-aineistot** — Metsätalouden tuet ja hoitotyöt (GeoServer WFS + ZIP-lataukset)
4. **Lataus-only-aineistot** — Korjuukelpoisuus ym. (~130 ZIP-tiedostoa, ei API-endpointia)

**Suurimmat aineistot:**
- Hilaruudukkotiedot: ~200 GB
- Latvusmallit (per vuosi): ~50 GB × 8 vuotta = ~400 GB
- Metsikkökuviotiedot: ~50 GB

---

## Traficom

**URL:** https://opendata.traficom.fi
**API:** OData v4 (`https://opendata.traficom.fi/api/v12/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 32
**Resursseja:** 32
**Arvioitu koko:** 2,5 GB

Liikenne- ja viestintäviraston avoin data.

#### Harvester-toteutus

`src/aura/harvesters/traficom.py` — OData entity set -harvester, jossa jokainen entity set on oma datasettinsä. Koko arvioidaan rekisterien koon perusteella (tietuemäärä × rivikoko).

**Suurimmat aineistot:**
- Ajoneuvorekisteri: ~5,1 miljoonaa ajoneuvoa (~1,3 GB)
- Viestintämarkkinatiedot, taajuusluvat, katsastustiedot
- Ilma-alusrekisteri, alusrekisteri, rautatiekalusto

---

## GTK

**URL:** https://www.gtk.fi
**API:** ArcGIS WFS/WMS (`https://gtkdata.gtk.fi/arcgis/services/Rajapinnat/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 5
**Resursseja:** 8
**Arvioitu koko:** 7 GB

Geologian tutkimuskeskus (GTK) tarjoaa Suomen kallioperä-, maaperä- ja kiviainestietoja ArcGIS-rajapintojen kautta.

#### Harvester-toteutus

`src/aura/harvesters/gtk.py` — Staattinen konfiguraatio. WFS-palveluille (kallioperä, maaperä, kiviainesvarannot) luodaan kaksi resurssia (WFS + WMS), WMS-only-palveluille (geofysiikka, pohjatutkimukset) yksi.

---

## SYKE (Suomen ympäristökeskus)

**URL:** https://ckan.ymparisto.fi
**API:** CKAN 3 REST (`https://ckan.ymparisto.fi/api/3/action/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** ~615
**Resursseja:** ~1 200
**Arvioitu koko:** ~50 GB

Suomen ympäristökeskus (SYKE) julkaisee ympäristö-, vesistö- ja paikkatietoja. Sisältää mm. pohjavesialueet, Natura 2000 -alueet, maankäyttö-, vedenlaatu- ja satelliittihavaintodataa.

#### Harvester-toteutus

`src/aura/harvesters/syke.py` — Käyttää `CkanHarvester`-kantaluokkaa. Sama `package_search`-logiikka kuin avoindata.fi:lle ja HRI:lle, mutta hakee SYKE:n omasta CKAN-portaalista (`ckan.ymparisto.fi`).

---

## Taustakartat

**URL:** https://kartat.kapsi.fi
**Tyyppi:** TMS-tiilipalvelut
**Autentikointi:** Ei tarvita
**Datasettejä:** 4
**Resursseja:** 4
**Arvioitu koko:** ~20 GB

Karttatiilipalvelut joita voi käyttää sovellusten pohjakarttoina. Sisältää Maanmittauslaitoksen kartat Kapsin kautta sekä OpenStreetMap-standardikartan.

| Palvelu | URL-template | Lisenssi |
|---------|-------------|----------|
| MML Peruskartta | `tiles.kartat.kapsi.fi/peruskartta/{z}/{x}/{y}.jpg` | CC BY 4.0 |
| MML Taustakartta | `tiles.kartat.kapsi.fi/taustakartta/{z}/{x}/{y}.jpg` | CC BY 4.0 |
| MML Ortokuva | `tiles.kartat.kapsi.fi/ortokuva/{z}/{x}/{y}.jpg` | CC BY 4.0 |
| OpenStreetMap | `tile.openstreetmap.org/{z}/{x}/{y}.png` | ODbL |

#### Harvester-toteutus

`src/aura/harvesters/taustakartat.py` — Staattinen konfiguraatioharvester. Jokaisesta tiilipalvelusta luodaan yksi Dataset ja TMS-resurssi URL-templatella.

---

## Overture Maps

**URL:** https://overturemaps.org
**Tyyppi:** GeoParquet (S3 + HTTPS)
**Autentikointi:** Ei tarvita
**Datasettejä:** 6
**Resursseja:** 12
**Arvioitu koko:** ~215 GB

Overture Maps Foundation tuottaa avoimen, maailmanlaajuisen kartta-aineiston GeoParquet-muodossa. Data on saatavilla S3:ssä ja source.coop:ssa. Jokaiselle teemalle kaksi resurssia: S3 GeoParquet ja HTTPS-lataus.

| Teema | Kuvaus | Arvioitu koko |
|-------|--------|---------------|
| buildings | Rakennukset | 50 GB |
| transportation | Liikenneverkko | 80 GB |
| places | Paikat ja POI:t | 10 GB |
| addresses | Osoitteet | 30 GB |
| divisions | Hallinnolliset alueet | 5 GB |
| base | Perusgeometria (vesistöt, maasto) | 40 GB |

#### Harvester-toteutus

`src/aura/harvesters/overture.py` — Staattinen konfiguraatioharvester. Kuvauksissa DuckDB-kyselyesimerkit Suomen bbox-rajauksella. Lisenssi: ODbL, kattavuus: Maailma.

---

## Ruokavirasto

**URL:** https://www.ruokavirasto.fi
**API:** INSPIRE GeoServer (`https://inspire.ruokavirasto-awsa.com/geoserver/`)
**Autentikointi:** Ei tarvita (avoimet); viranomaiskäyttö (rajoitetut)
**Datasettejä:** 33
**Resursseja:** 97

Ruokavirasto (Finnish Food Authority) tarjoaa maatalouden paikkatietoaineistoja, avoin tieto -dashboardeja ja rajoitettuja viranomaiskäytön rajapintoja.

### A. INSPIRE-paikkatiedot (20 datasettiä)

| Aineisto | Vuodet | Resurssit | Lisenssi |
|----------|--------|-----------|----------|
| Peltolohkorekisteri | 2020–2024 | WMS, WFS, GPKG | CC BY 4.0 |
| Maatalousmaa | 2020–2024 | WMS, WFS, GPKG | CC BY 4.0 |
| Kasvulohkot | 2020–2024 | WMS, WFS, GPKG | CC BY 4.0 |
| Maisemapiirteet | 2020–2024 | WMS, WFS, GPKG | CC BY 4.0 |

### B. Avoin tieto -dashboardit (5 datasettiä)

Qlik-dashboardit osoitteessa avointieto.ruokavirasto.fi. Elintarvikevalvonta, eläinten terveys, kasvinterveys ja EU-tukimaksut.

### C. Rajoitetut rajapinnat (8 datasettiä)

Liityntäkatalogi.suomi.fi:ssä rekisteröidyt viranomaiskäytön rajapinnat (`access_level="restricted"`): eläinrekisteri, teurastamotiedot, luomutoimijarekisteri, kasvinsuojeluainerekisteri, rehurekisteri, lannoiterekisteri, vierasainerekisteri, elintarvikehuoneistorekisteri.

#### Harvester-toteutus

`src/aura/harvesters/ruokavirasto.py` — Staattinen konfiguraatioharvester. INSPIRE-aineistoista luodaan vuosi × tyyppi -datasetit (3 resurssia: WMS + WFS + GeoPackage). Dashboardeista HTML-resurssi. Rajoitetuista palveluista API-resurssi liityntäkatalogiin.

---

## MML (Maanmittauslaitos)

**URL:** https://www.maanmittauslaitos.fi/rajapinnat
**API:** WFS/WMS/WMTS/OGC API Features
**Autentikointi:** Ilmainen API-avain (rekisteröityminen)
**Datasettejä:** 7
**Resursseja:** 16
**Arvioitu koko:** ~184 GB

Maanmittaulaitoksen avoimet paikkatietorajapinnat. Vaatii ilmaisen API-avaimen.

### MML API-avaimen hankkiminen

1. Mene osoitteeseen https://omatili.maanmittauslaitos.fi/
2. Kirjaudu sisään (Suomi.fi-tunnistautuminen) tai luo tili
3. Valitse "API-avaimet" → "Luo uusi avain"
4. Valitse tuotteet: "Avoimet aineistot" (kaikki avoimet rajapinnat yhdellä avaimella)
5. Kopioi API-avain — käytä URL-parametrina: `?api-key=AVAIN`

| Aineisto | Resurssit | Arvioitu koko |
|----------|-----------|---------------|
| Maastotietokanta | WFS, WMS, OGC API | 10 GB |
| Kiinteistöjaotus | WFS, WMS | 3 GB |
| Paikannimet | WFS, WMS | 500 MB |
| Peruskartta (rasteri) | WMTS | 20 GB |
| Ortokuvat (ilmakuvat) | WMTS | 50 GB |
| Korkeusmalli 2 m | WCS, WMS | 100 GB |
| Hallinnolliset rajat | WFS, WMS | 50 MB |

#### Harvester-toteutus

`src/aura/harvesters/mml.py` — StaticHarvester. Kaikki datasetit merkitty `access_level="registration"`. API-avain on ilmainen mutta vaatii rekisteröitymisen.

---

## Tilastokeskus (paikkatiedot)

**URL:** https://geo.stat.fi
**API:** GeoServer WFS/WMS
**Autentikointi:** Ei tarvita
**Datasettejä:** 9
**Resursseja:** 18
**Arvioitu koko:** ~5 GB

Tilastokeskuksen paikkatietoaineistot GeoServer-palvelimelta. Väestö-, rakennus-, yritys- ja kuntapohjaiset ruutuaineistot.

#### Harvester-toteutus

`src/aura/harvesters/statfin_geo.py` — StaticHarvester. Jokaisesta aineistosta WFS- ja WMS-resurssi.

---

## Väylävirasto

**URL:** https://vayla.fi/vaylista/aineistot/avoindata
**API:** WFS/WMS/OGC API Features (`https://avoinapi.vaylapilvi.fi/vaylatiedot/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 5
**Resursseja:** 13
**Arvioitu koko:** ~9 GB

Tie-, rata- ja vesiväyläaineistot. 307 WMS-tasoa / 301 WFS-featuretyyppiä.

| Aineisto | Resurssit | Arvioitu koko |
|----------|-----------|---------------|
| Tiestötiedot | WFS, WMS, OGC API | 5 GB |
| Digiroad | WFS, WMS | 3 GB |
| Ratatiedot | WFS, WMS | 500 MB |
| Vesiväylätiedot | WFS, WMS | 200 MB |
| Taitorakenteet | WFS, WMS | 100 MB |

#### Harvester-toteutus

`src/aura/harvesters/vayla.py` — StaticHarvester. Kaikki resurssit osoittavat `avoinapi.vaylapilvi.fi`-palvelimelle.

---

## PaItuli (CSC)

**URL:** https://paituli.csc.fi
**API:** GeoServer WMS/WFS (`https://paituli.csc.fi/geoserver/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 5
**Resursseja:** 9
**Arvioitu koko:** ~88 GB

CSC:n PaItuli-palvelu tarjoaa tutkimuksen ja opetuksen paikkatietoaineistoja. 628 WMS-tasoa.

| Aineisto | Resurssit | Arvioitu koko |
|----------|-----------|---------------|
| LUKE metsävaratiedot | WMS, WFS | 50 GB |
| MML historialliset karttasarjat | WMS | 30 GB |
| Tilastokeskuksen ruutuaineistot | WMS, WFS | 5 GB |
| CORINE maanpeiteaineisto | WMS, WFS | 2 GB |
| DVV osoitetiedot | WMS, WFS | 1 GB |

#### Harvester-toteutus

`src/aura/harvesters/paituli.py` — StaticHarvester.

---

## LIPAS

**URL:** https://www.jyu.fi/sport/fi/yhteistyo/lipas
**API:** GeoServer WFS/WMS (`http://lipas.cc.jyu.fi/geoserver/lipas/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 3
**Resursseja:** 6
**Arvioitu koko:** ~1 GB

Jyväskylän yliopiston LIPAS-rekisteri sisältää Suomen julkiset liikuntapaikat ja virkistysalueet. 210 WMS/WFS-tasoa.

| Aineisto | Resurssit |
|----------|-----------|
| Liikuntapaikat (kaikki) | WFS, WMS |
| Ulkoilureitit | WFS, WMS |
| Virkistysalueet | WFS, WMS |

#### Harvester-toteutus

`src/aura/harvesters/lipas.py` — StaticHarvester. Huom: palvelin käyttää HTTP:tä (ei HTTPS).

---

## Kuntien paikkatiedot

**URL:** (eri kaupungit)
**API:** WFS/WMS/ArcGIS (GeoServer, Tekla OGC Web, Pirkanmaan pirnet.fi)
**Autentikointi:** Ei tarvita
**Datasettejä:** 36
**Resursseja:** ~70
**Arvioitu koko:** ~57 GB

36 kunnan avoimet paikkatietoaineistot (WMS/WFS-rajapinnat). Kunnat on ryhmitelty palvelualustan mukaan.

#### GeoServer-kunnat

| Kunta | Rajapinta |
|-------|-----------|
| Espoo | WFS, WMS |
| Helsinki | WFS, WMS |
| Hämeenlinna | WFS, WMS |
| Joensuu | WFS, WMS |
| Jyväskylä | WFS, WMS |
| Kajaani | WFS, WMS |
| Kokkola | WFS, WMS |
| Kotka | WFS, WMS |
| Kouvola | WFS, WMS |
| Kuopio | WFS, WMS |
| Lahti | WFS, WMS |
| Lappeenranta | WFS, WMS |
| Mikkeli | WFS, WMS |
| Naantali | WFS, WMS |
| Oulu | WMS |
| Pori | WFS, WMS |
| Raisio | WFS, WMS |
| Rauma | WFS, WMS |
| Rovaniemi | WFS, WMS |
| Salo | WFS, WMS |
| Seinäjoki | WFS, WMS |
| Tampere | WFS, WMS |
| Turku | WMS |
| Vantaa | WFS, WMS |

#### Tekla OGC Web -kunnat

| Kunta | Rajapinta |
|-------|-----------|
| Hyvinkää | WFS, WMS |
| Kauniainen | WFS, WMS |
| Nurmijärvi | WFS, WMS |
| Tuusula | WFS, WMS |
| Vihti | WFS, WMS |

#### Pirkanmaan pirnet.fi (ArcGIS)

| Kunta | Rajapinta |
|-------|-----------|
| Hämeenkyrö | ArcGIS |
| Kangasala | ArcGIS |
| Lempäälä | ArcGIS |
| Nokia | ArcGIS |
| Orivesi | ArcGIS |
| Pirkkala | ArcGIS |
| Ylöjärvi | ArcGIS |

#### Harvester-toteutus

`src/aura/harvesters/kunnat.py` — StaticHarvester. Jokaiselle kunnalle oma datasetti ja organisaatio.

---

## Paikkatietoikkuna

**URL:** https://paikkatietoikkuna.fi
**API:** Oskari Action Routes (`https://kartta.paikkatietoikkuna.fi/action`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 689
**Resursseja:** 3 329
**Organisaatioita:** 61

Kansallinen paikkatietoportaali, jota ylläpitää Maanmittauslaitos. Kokoaa 2 796 karttatasoa 60+ organisaatiolta. Aineistot on luokiteltu INSPIRE-teemoittain (39 ryhmää).

Karttatasotyypit: 2 041 WMS, 698 WFS, 41 WMTS, 8 3D Tiles, 6 tilastotasoa, 2 ArcGIS.

Suurimmat tiedontuottajat:

| Organisaatio | Karttatasoja |
|---|---|
| Tilastokeskus | 786 |
| Luonnonvarakeskus | 363 |
| Jyväskylän yliopisto (LIPAS) | 319 |
| Suomen ympäristökeskus | 303 |
| Väylävirasto | 204 |
| Helsingin kaupunki | 159 |
| Suomen metsäkeskus | 76 |
| Maanmittauslaitos | 74 |
| Traficom | 68 |
| Tampereen kaupunki | 68 |

**Huom:** Osa aineistoista esiintyy myös muissa Auran lähteissä (SYKE, MML, LIPAS jne.). Paikkatietoikkunan kautta saadaan INSPIRE-luokittelu ja taso-kohtaiset WMS/WFS-osoitteet.

#### Harvester-toteutus

`src/aura/harvesters/paikkatietoikkuna.py` — BaseHarvester. Kaksivaiheinen: (1) kaikki tasot `GetHierarchicalMapLayerGroups`-kutsulla, (2) CSW-metatiedot `GetCSWData`-kutsulla jokaiselle uniikille datasetille.

---

## STUK (Säteilyturvakeskus)

**URL:** https://stuk.fi/avoin-data
**API:** Sammio REST (`https://sammio.stuk.fi`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 2
**Resursseja:** 2
**Arvioitu koko:** ~150 MB

STUK:n säteilyvalvonnan mittaustulokset. Ulkoisen säteilyn reaaliaikaiset mittaukset ~260 asemalta sekä ympäristönäytteiden radioaktiivisuusmittaukset.

#### Harvester-toteutus

`src/aura/harvesters/stuk.py` — StaticHarvester. Päivitystaajuus: reaaliaikainen.

---

## Harvester-arkkitehtuuri

Jokainen datalähde harvestoidaan omalla luokallaan joka perii `BaseHarvester`-pohjaluokan:

```
src/aura/harvesters/
├── __init__.py       # Rekisteri ja factory
├── base.py           # BaseHarvester-pohjaluokka
├── ckan.py           # CkanHarvester-kantaluokka
├── pxweb.py          # PxWebHarvester-kantaluokka
├── static.py         # StaticHarvester-kantaluokka
├── avoindata.py      # avoindata.fi (CKAN)
├── hri.py            # HRI (CKAN)
├── syke.py           # SYKE (CKAN)
├── statfin.py        # Tilastokeskus (PxWeb)
├── statfin_geo.py    # Tilastokeskus paikkatiedot (WFS/WMS)
├── luke.py           # LUKE (PxWeb)
├── digitraffic.py    # Digitraffic (OpenAPI)
├── fmi.py            # FMI (WFS)
├── gtk.py            # GTK (ArcGIS WFS/WMS)
├── traficom.py       # Traficom (OData)
├── metsakeskus.py    # Metsäkeskus (WFS/WCS)
├── taustakartat.py   # Taustakartat (TMS)
├── overture.py       # Overture Maps (GeoParquet)
├── ruokavirasto.py   # Ruokavirasto (INSPIRE/GeoServer)
├── mml.py            # MML (WFS/WMS/WMTS)
├── vayla.py          # Väylävirasto (WFS/WMS/OGC API)
├── stuk.py           # STUK (Sammio API)
├── lipas.py          # LIPAS (WFS/WMS)
├── paituli.py        # PaItuli/CSC (WMS/WFS)
└── kunnat.py         # Kuntien paikkatiedot (WFS/WMS)
```

### Käyttö

```bash
# Harvestoi kaikki lähteet
aura harvest

# Harvestoi yksittäinen lähde
aura harvest avoindata.fi

# Listaa saatavilla olevat lähteet
aura harvest --list

# Näytä lähteiden tila
aura sources
```

## Tietokantamigraatiot

Skeemamuutokset hoidetaan numeroiduilla SQL-migraatiotiedostoilla:

```
scripts/migrations/
├── 001_initial_schema.sql    # Alkuperäinen skeema
├── 002_add_something.sql     # Seuraava muutos
└── ...
```

Migraatiot ajetaan automaattisesti `init_db()`:n yhteydessä. Sovelletut migraatiot kirjataan `schema_migrations`-tauluun — samaa migraatiota ei ajeta kahdesti.

```bash
# Aja migraatiot manuaalisesti
aura migrate
```

### Uuden migraation luominen

1. Luo tiedosto `scripts/migrations/NNN_kuvaus.sql` (NNN = seuraava numero)
2. Kirjoita SQL-komennot (ALTER TABLE, CREATE INDEX, jne.)
3. Aja `aura migrate` tai migraatio ajetaan automaattisesti seuraavan harvest/search/serve -komennon yhteydessä
