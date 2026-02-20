# Datalähteet ja harvestoidut aineistot

Tämä sivu dokumentoi kaikki Auran harvesteroimat datalähteet.

> Päivitetty: 2026-02-20

## Yhteenveto

| Lähde | Tyyppi | Datasettejä | Resursseja | Arvioitu koko |
|-------|--------|-------------|------------|---------------|
| [avoindata.fi](#avoindatafi) | CKAN API | 1 943 | 5 188 | 114 GB |
| [HRI (hri.fi)](#hri-helsinki-region-infoshare) | CKAN API | 549 | 1 594 | 39 GB |
| [LUKE](#luke-luonnonvarakeskus) | PxWeb API | 495 | 990 | 2,3 GB |
| [Tilastokeskus (StatFin)](#tilastokeskus-statfin) | PxWeb API | 374 | 748 | 1,7 GB |
| [Digitraffic](#digitraffic) | REST/OpenAPI | 162 | 162 | 1,5 GB |
| [Ilmatieteen laitos (FMI)](#ilmatieteen-laitos-fmi) | WFS 2.0 | 160 | 160 | 14 GB |
| [Metsäkeskus](#metsäkeskus) | WFS/WCS/ZIP | 43 | 85 | 1,2 TB |
| [Traficom](#traficom) | OData v4 | 32 | 32 | 2,5 GB |
| **Yhteensä** | | **3 758** | **8 959** | **~1,3 TB** |

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

**Yhteensä: 3 758 datasettiä, 8 959 resurssia, 200 organisaatiota, ~1,3 TB**

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

## Harvester-arkkitehtuuri

Jokainen datalähde harvestoidaan omalla luokallaan joka perii `BaseHarvester`-pohjaluokan:

```
src/aura/harvesters/
├── __init__.py       # Rekisteri ja factory
├── base.py           # BaseHarvester-pohjaluokka
├── avoindata.py      # avoindata.fi (CKAN)
├── hri.py            # HRI (CKAN)
├── statfin.py        # Tilastokeskus (PxWeb)
├── luke.py           # LUKE (PxWeb)
├── digitraffic.py    # Digitraffic (OpenAPI)
├── fmi.py            # FMI (WFS)
├── traficom.py       # Traficom (OData)
└── metsakeskus.py    # Metsäkeskus (WFS/WCS)
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
