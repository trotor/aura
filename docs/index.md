# Aura — Suomalaisen avoimen datan discovery-palvelu

Aura kyntää suomalaisen avoimen datan esiin piilostaan ja tekee sen ymmärrettäväksi. Palvelu kokoaa yhteen metadatan 27 avoimen datan lähteestä ja tarjoaa sen haettavaksi tekoälyille ja ihmisille.

---

## Lukuina

| | |
|---|---|
| **7 000+** datasettiä | **17 000+** resurssia |
| **290+** organisaatiota | **27** datalähdettä |
| **~2 TB** arvioitua dataa | **308** kuntaa viitetaulussa |

---

## Datalähteet

| Lähde | Tyyppi | Datasettejä | Organisaatioita |
|-------|--------|-------------|-----------------|
| [avoindata.fi](https://avoindata.suomi.fi) | CKAN API | 1 738 | 172 |
| [Tilastokeskus (StatFin)](https://stat.fi) | PxWeb API | 1 524 | 1 |
| [Paikkatietoikkuna](https://paikkatietoikkuna.fi) | Oskari API | 689 | 61 |
| [LUKE](https://statdb.luke.fi) | PxWeb API | 662 | 1 |
| [SYKE](https://ckan.ymparisto.fi) | CKAN API | 614 | 7 |
| [HRI (hri.fi)](https://hri.fi) | CKAN API | 549 | 28 |
| [Suomi.fi-koodistot](https://koodistot.suomi.fi) | REST API | 511 | 1 |
| [Digitraffic](https://www.digitraffic.fi) | REST/OpenAPI | 162 | 1 |
| [Ilmatieteen laitos](https://www.ilmatieteenlaitos.fi) | WFS 2.0 | 160 | 1 |
| [LUKE avoin tutkimusdata](https://opendata.luke.fi) | CKAN | 124 | 1 |
| [Valtiokonttori](https://avoindata.tutkihallintoa.fi) | REST API | 48 | 1 |
| [Metsäkeskus](https://avoin.metsakeskus.fi) | WFS/WCS/ZIP | 43 | 1 |
| Kuntien paikkatiedot (36 kuntaa) | WMS/WFS/ArcGIS | 36 | 36 |
| [Ruokavirasto](https://www.ruokavirasto.fi) | INSPIRE/GeoServer | 33 | 1 |
| [Traficom](https://opendata.traficom.fi) | OData v4 | 32 | 1 |
| [Vaalirahoitusvalvonta](https://www.vaalirahoitusvalvonta.fi) | CSV | 27 | 1 |
| + 11 muuta lähdettä | | 72 | |

[Tarkemmat tiedot lähteistä](SOURCES.md)

---

## Suurimmat julkaisijat

| Organisaatio | Datasettejä | Lähteet |
|-------------|-------------|---------|
| Tilastokeskus | 1 560 | avoindata.fi, StatFin, Paikkatietoikkuna |
| Luonnonvarakeskus (LUKE) | 676 | LUKE PxWeb, LUKE kartta |
| SYKE — Paikkatiedot ja kaukokartoitus | 446 | SYKE CKAN |
| Väylävirasto | 341 | avoindata.fi, Väylävirasto WFS, Paikkatietoikkuna |
| Turku | 231 | avoindata.fi |
| Valtiovarainministeriö | 220 | avoindata.fi |
| Helsingin kaupunginkanslia | 198 | HRI |
| Ilmatieteen laitos | 190 | avoindata.fi, FMI WFS |
| Fintraffic / Digitraffic | 162 | Digitraffic |
| Luonnonvarakeskus (tutkimusdata) | 124 | LUKE opendata |

[Kaikki organisaatiot](organisaatiot.md)

---

## Teemat

Auran dataseteista löytyy dataa laajasti eri aihepiireistä:

| Teema | Datasettejä | Esimerkkejä |
|-------|-------------|-------------|
| **Liikenne** | ~760 | Nopeusrajoitukset, joukkoliikennereitit, tieliikennemäärät |
| **Ympäristö** | ~560 | Vesistöjen tila, ilmanlaatu, luonnonsuojelualueet |
| **Kartat ja paikkatieto** | ~370 | Maastotietokanta, kiinteistörajat, osoitedata |
| **Asuminen ja rakentaminen** | ~340 | Asuntokanta, rakennusluvat, kaavat |
| **Väestö** | ~180 | Väestörakenne, muuttoliike, syntyvyys |
| **Talous ja työllisyys** | ~140 | Työttömyysaste, yritysrekisteri, kuntatalous |
| **Maatalous** | ~120 | Peltolohkot, maataloustilastot, viljelyskasvit |
| **Koulutus** | ~70 | Oppilaitokset, opiskelijamäärät, PISA |
| **Terveys** | ~50 | Sairastavuus, terveyspalvelut, hoitotakuu |
| **Energia** | ~50 | Sähkönkulutus, kaukolämpö, tuulivoima |

---

## Alueellinen kattavuus

Yli 1 100 datasettiä on kohdistettu tietyille alueille. Eniten aluekohtaista dataa on saatavilla:

| Alue | Datasettejä |
|------|-------------|
| Helsinki | 222 |
| Turku | 94 |
| Oulu | 80 |
| Vantaa | 64 |
| Espoo | 58 |
| Pääkaupunkiseutu | 53 |
| Tampere | 65 |
| Varsinais-Suomi | 22 |

Lisäksi valtaosa dataseteista kattaa koko Suomen — esimerkiksi Tilastokeskuksen tilastot ovat saatavilla kuntatasolla.

[Kaikki 163 kuntaa maakunnittain](kunnat.md)

---

## Dataformaatit

| Formaatti | Resursseja | Tyyppi |
|-----------|-----------|--------|
| WMS | 3 092 | Karttakuvapalvelu |
| HTML | 2 942 | Verkkosivut ja katselunäkymät |
| PxWeb | 2 326 | Tilastotaulukot |
| WFS | 1 549 | Paikkatietorajapinta |
| XLSX | 860 | Excel-taulukot |
| CSV | 1 061 | Taulukkodata |
| PDF | 338 | Dokumentit |
| ZIP | 335 | Pakatut aineistot |
| SHP | 270 | Shapefile-paikkatieto |
| API | 260 | REST-rajapinnat |

[Formaattien kuvaukset](formats.md)

---

## Käyttöönotto

Aura on MCP-server (Model Context Protocol), joka antaa tekoälyn hakea, ymmärtää ja rikastaa datasettejä.

```bash
git clone https://github.com/trotor/aura.git
cd aura
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

claude   # Aura MCP-server käynnistyy automaattisesti
```

Tietokanta tulee repon mukana valmiina — ei tarvitse harvestoida erikseen.

[MCP-käyttöönotto eri työkaluille](MCP_SETUP.md)

---

## Dokumentaatio

- [**Dataformaatit**](formats.md) — Auran tukemat 20 dataformaattia
- [**Organisaatiot**](organisaatiot.md) — 290+ datan julkaisijaa
- [**Kunnat**](kunnat.md) — 163 kuntaa maakunnittain, linkkeineen
- [**Datasettikatalogi**](CATALOG.md) — Täydellinen lista lähteittäin
- [**Datalähteet**](SOURCES.md) — Lähteiden tekniset tiedot
- [**MCP-käyttöönotto**](MCP_SETUP.md) — Auran liittäminen tekoälytyökaluihin

## Lähdekoodi

[GitHub: trotor/aura](https://github.com/trotor/aura) · [CONTRIBUTING](https://github.com/trotor/aura/blob/main/CONTRIBUTING.md) · [MIT-lisenssi](https://github.com/trotor/aura/blob/main/LICENSE)
