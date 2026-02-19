# Datalähteet ja harvestoidut aineistot

Tämä sivu dokumentoi kaikki Auran harvesteroimat ja suunnitellut datalähteet.

> Päivitetty: 2026-02-19

## Yhteenveto

| Lähde | Tyyppi | Status | Datasettejä | Resursseja |
|-------|--------|--------|-------------|------------|
| [avoindata.fi](#avoindatafi) | CKAN API | Harvestoitu | 1 943 | 6 780 |
| [HRI (hri.fi)](#hri-helsinki-region-infoshare) | CKAN API | Harvestoitu | 549 | ~1 200 |
| [Tilastokeskus (StatFin)](#tilastokeskus-statfin) | PxWeb API | Harvestoitu | 374 | 748 |
| [Digitraffic](#digitraffic) | REST/OpenAPI | Harvestoitu | 162 | 162 |
| [LUKE](#luke-luonnonvarakeskus) | PxWeb API | Suunniteltu | 6 pääkategoriaa | |
| [Traficom](#traficom) | OData v4 | Suunniteltu | 31 tietojoukkoa | |
| [Ilmatieteen laitos (FMI)](#ilmatieteen-laitos-fmi) | WFS 2.0 | Suunniteltu | ~160 kyselyä | |
| [Museovirasto / Finna](#museovirasto--finna) | REST API | Suunniteltu | ~450 000 tietuetta | |
| [SYKE](#syke-suomen-ympäristökeskus) | ArcGIS REST | Suunniteltu | 221 (via avoindata) | |
| [Maanmittauslaitos](#maanmittauslaitos) | OGC API | Suunniteltu | 22 (via avoindata) | |

### Resurssityypit

Aura harvestoi sekä **rajapintoja** (API, WMS, WFS, OGC, PXWEB) että **aineistopaketteja** (CSV, XLSX, JSON, SHP, ZIP jne.):

| Tyyppi | Resursseja | Osuus |
|--------|-----------|-------|
| Rajapinnat (WMS, WFS, API, PXWEB) | ~2 100 | 24% |
| Aineistopaketit (CSV, XLSX, JSON, SHP...) | ~6 800 | 76% |

**Yhteensä: 3 028 datasettiä, 196 organisaatiota, 95 dataformaattia**

---

## Harvestoidut lähteet

### avoindata.fi

**URL:** https://avoindata.suomi.fi
**API:** CKAN 3 REST (`https://avoindata.suomi.fi/data/api/3/action/`)
**Autentikointi:** Ei tarvita
**Status:** Harvestoitu
**Datasettejä:** 2 492
**Resursseja:** 6 780
**Organisaatioita:** 195

Suomen kansallinen avoimen datan portaali. Aggregoi dataa kunnilta, ministeriöiltä, virastoilta ja tutkimuslaitoksilta.

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

#### Yleisimmät formaatit

| Formaatti | Resursseja | Tyyppi |
|----------|-----------|--------|
| WMS | 875 | Rajapinta |
| XLSX | 842 | Aineistopaketti |
| WFS | 570 | Rajapinta |
| CSV | 482 | Aineistopaketti |
| ZIP | 280 | Aineistopaketti |
| SHP | 269 | Aineistopaketti |
| PDF | 251 | Aineistopaketti |
| HTML | 190 | Aineistopaketti |
| TAB | 150 | Aineistopaketti |
| PXWEB | 140 | Rajapinta |
| JSON | 134 | Aineistopaketti |

---

## Suunnitellut lähteet

### HRI (Helsinki Region Infoshare)

**URL:** https://hri.fi
**API:** CKAN 3 REST (`https://hri.fi/data/api/3/action/`)
**Autentikointi:** Ei tarvita
**Status:** Harvestoitu
**Datasettejä:** 549

Pääkaupunkiseudun avoimen datan portaali (Helsinki, Espoo, Vantaa, Kauniainen). Sama CKAN-rajapinta kuin avoindata.fi.

### Tilastokeskus (StatFin)

**URL:** https://stat.fi
**API:** PxWeb REST (`https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/`)
**Autentikointi:** Ei tarvita
**Status:** Harvestoitu
**Datasettejä:** 374 tilastotaulua

Suomen virallinen tilastoviranomainen. Harvester käy rekursiivisesti läpi PxWeb-puun ja kerää jokaisen tilastotaulun metadatan.

**Aihealueita:** Asuminen, energia, hinnat, kansantalous, koulutus, oikeus, palkat, terveys, työ, väestö, ympäristö...

**Kielet:** fi, en, sv

### LUKE (Luonnonvarakeskus)

**URL:** https://luke.fi
**API:** PxWeb REST (`https://statdb.luke.fi/PxWeb/api/v1/fi/LUKE/`)
**Autentikointi:** Ei tarvita
**Kategoriat:** Maataloustilastot, metsätilastot, kala- ja riistatilastot, indikaattorit

Sama PxWeb-rajapinta kuin Tilastokeskuksella — sama harvester toimii molemmille.

### Traficom

**URL:** https://opendata.traficom.fi
**API:** OData v4 (`https://opendata.traficom.fi/api/v12/`)
**Autentikointi:** Ei tarvita
**Tietojoukkoja:** 31

Liikenne- ja viestintäviraston avoin data. Sisältää mm. ajoneuvorekisterin (5,1 miljoonaa ajoneuvoa), ilma-alusrekisterin, alusrekisterin, radioasematiedot.

### Digitraffic

**URL:** https://www.digitraffic.fi
**API:** REST/OpenAPI 3.0
**Autentikointi:** Ei tarvita (gzip-header vaaditaan)
**Status:** Harvestoitu
**Datasettejä:** 162 API-endpointtia

Kolme erillistä rajapintaa:

| Rajapinta | URL | Endpointteja |
|-----------|-----|--------------|
| Tieliikenne | https://tie.digitraffic.fi | 87 |
| Rautatieliikenne | https://rata.digitraffic.fi | 58 |
| Meriliikenne | https://meri.digitraffic.fi | 17 |

Reaaliaikaista ja lähes reaaliaikaista liikennedataa: mittausasemat, sääasemat, junien sijainnit, laivojen AIS-tiedot. Harvester parsii OpenAPI-speksit ja luo datasetin jokaisesta GET-endpointista.

### Ilmatieteen laitos (FMI)

**URL:** https://www.ilmatieteenlaitos.fi
**API:** OGC WFS 2.0 (`https://opendata.fmi.fi/wfs`)
**Autentikointi:** Ei tarvita
**Tallennettuja kyselyjä:** ~160

Sää-, ilmasto-, meri- ja säteilytietoa. WFS-rajapinta tarjoaa stored query -mekanismin jossa jokainen kysely on käytännössä oma datasettinsä.

**Datakategoriat:** Säähavainnot, ennusteet (HARMONIE, MEPS, ECMWF), tutka, meritaso, säteily, ilmanlaatu.

### Museovirasto / Finna

**URL:** https://api.finna.fi
**API:** Finna REST API (`https://api.finna.fi/v1/`)
**Autentikointi:** Ei tarvita
**Tietueita:** ~450 000 (Museovirasto-suodatin)

Kansallinen kulttuuriperintöhaku. Finna aggregoi museoiden, arkistojen ja kirjastojen aineistot.

### SYKE (Suomen ympäristökeskus)

**URL:** https://www.syke.fi
**API:** ArcGIS REST + WFS (`https://paikkatieto.ymparisto.fi/arcgis/rest/services/`)
**Autentikointi:** Ei tarvita
**Datasettejä:** 221 (avoindata.fi kautta)

Ympäristötietoa: vesistöt, maankäyttö, luonnonsuojelu, tulvariskit, CORINE-maanpeite.

### Maanmittauslaitos

**URL:** https://www.maanmittauslaitos.fi
**API:** OGC API Features (`https://avoin-paikkatieto.maanmittauslaitos.fi/`)
**Autentikointi:** API-avain vaaditaan (ilmainen rekisteröityminen)
**Datasettejä:** 22 (avoindata.fi kautta)

Maastotiedot, kiinteistötiedot, paikannimet, korkeusmallit, kartat.

---

## Harvester-arkkitehtuuri

Jokainen datalähde harvestoidaan omalla luokallaan joka perii `BaseHarvester`-pohjaluokan:

```
src/aura/harvesters/
├── __init__.py       # Rekisteri ja factory
├── base.py           # BaseHarvester-pohjaluokka
├── avoindata.py      # avoindata.fi (CKAN)
├── hri.py            # HRI (CKAN) — tulossa
├── statfin.py        # Tilastokeskus (PxWeb) — tulossa
├── luke.py           # LUKE (PxWeb) — tulossa
├── traficom.py       # Traficom (OData) — tulossa
├── digitraffic.py    # Digitraffic (REST) — tulossa
├── fmi.py            # FMI (WFS) — tulossa
└── finna.py          # Finna/Museovirasto (REST) — tulossa
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
