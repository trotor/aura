# Aura

**Suomalaisen avoimen datan discovery- ja ymmärryspalvelu**

[**Dokumentaatio**](https://trotor.github.io/aura/) · [**What's New**](docs/WHATSNEW.md) · [**Datasettikatalogi**](docs/CATALOG.md) · [**Dataformaatit**](docs/formats.md) · [**Datalähteet**](docs/SOURCES.md)

> **12 900+ datasettiä** · **31 000+ resurssia** · **340+ organisaatiota** · **~2 TB** avointa dataa
>
> 41 datalähteestä: avoindata.fi, SYKE, HRI, Tilastokeskus, LUKE, Digitraffic, Digitransit, Finap/NAP, FMI, Paikkatietoikkuna, Suomi.fi-koodistot, Overture Maps, GTK, Traficom, Traficomin tilastotietokanta, Finavia, Finlex, Eduskunta, Metsäkeskus, MML, Väylävirasto, Valtiokonttori, Ruokavirasto, THL Sotkanet, STUK, LIPAS, PaItuli, Vaalirahoitusvalvonta, Lajitietokeskus, POHTIVA, Kuntien paikkatiedot (36 kuntaa) ym.

Aura kyntää suomalaisen avoimen datan esiin piilostaan ja tekee sen ymmärrettäväksi. Palvelu toimii MCP-serverinä tekoälyille sekä avoimena web-palveluna ihmisille.

> *Aura* — kyntöaura kääntää maan pintaan piiloutuneen esiin. Aura on myös valon kehä auringon tai kuun ympärillä — hohde joka tekee näkyväksi sen mikä muuten jää piiloon. Samalla tavalla tämä työkalu tuo esiin Suomen avoimen datan ja antaa sille näkyvyyden.

## Mitä Aura tekee?

- **Aggregoi** metadatan 30 avoimen datan lähteestä
- **Normalisoi** CKAN, PxWeb, OData, WFS, OpenAPI ja GTFS -formaatit yhtenäiseen muotoon
- **Tekee hakukelpoiseksi** — FTS5-täystekstihaku luonnollisella kielellä
- **Arvioi datakoon** — jokaiselle datasetille arvioitu koko
- **Laatupisteyttää** — automaattinen laadun arviointi neljällä dimensiolla
- **Rikastaa joukkoistamalla** — MCP-sessiot kerryttävät tietoa dataseteistä
- **Tunnistaa skeemoja** — päättelee kenttänimet ja tyypit esikatselusta
- **Palvelee tekoälyjä** MCP-serverin kautta (Claude, GPT, jne.)
- **Mahdollistaa reaaliaikakyselyt** — agentti voi hakea dataa suoraan rajapinnoista (Digitraffic, PxWeb, WFS, OData ym.)

## Kokeile ilman asennusta

Aurasta on ylläpidetty julkinen instanssi. Liitä se tekoälyavustajaasi ilman
asennusta ja kloonausta:

```json
{
  "mcpServers": {
    "aura": { "url": "https://aura.futuai.fi/mcp" }
  }
}
```

Aineistoja voi myös selata selaimessa: **[aura.futuai.fi](https://aura.futuai.fi/)**

Muutama asia joka kannattaa tietää instanssista:

- **Ei vaadi tunnuksia.** Endpoint on avoin.
- **Vain luku.** Hakutyökalut ovat käytössä, kantaa muokkaavat eivät —
  rikastukset ja tutkimuslöydökset tallentuvat vain omassa instanssissa.
- **Ylläpidetään erikseen.** Instanssi ei seuraa tämän repon `main`-haaraa
  automaattisesti, joten sen aineistomäärä voi poiketa siitä mitä saat
  ajamalla itse.

Oma instanssi on silti se täysi versio: sen kanta on kirjoitettavissa ja
kaikki työkalut ovat käytössä. Jatka lukemista alta.

## Vaatimukset

- **Python 3.11+** — tarkista: `python3 --version`
- **pip** tai [**uv**](https://docs.astral.sh/uv/) pakettien asennukseen
- **git** repon kloonaamiseen

SQLite tulee Python 3.11:n mukana (FTS5-tuki sisäänrakennettu). Erillistä SQLite-asennusta ei tarvita.

**Valinnainen:**
- **MML API-avain** — Maanmittauslaitoksen aineistoihin (ks. [Rajausaineistot](#rajausaineistot))

## Käyttöönotto

### Claude Code (toimii sellaisenaan)

Auran repo sisältää `.mcp.json`-tiedoston, joka konfiguroi MCP-serverin automaattisesti. Ei tarvitse tehdä mitään ylimääräistä:

```bash
git clone https://github.com/trotor/aura.git
cd aura
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

claude   # Aura MCP-server käynnistyy automaattisesti
```

Claude Code tunnistaa `.mcp.json`:n ja käynnistää serverin taustalle. Voit heti kysyä: *"Mitä avoimia datasettejä Helsingin kaupunki tarjoaa?"*

### Claude Desktop

Lisää Auran MCP-server Clauden asetustiedostoon:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aura": {
      "command": "/polku/aura/.venv/bin/python",
      "args": ["-m", "aura.cli", "serve"]
    }
  }
}
```

> Korvaa `/polku/aura` kloonatun repon absoluuttisella polulla. Käytä virtuaaliympäristön Pythonia (`.venv/bin/python`).

### Cursor

Lisää `.cursor/mcp.json` projektin juureen tai globaalisti `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "aura": {
      "command": "/polku/aura/.venv/bin/python",
      "args": ["-m", "aura.cli", "serve"]
    }
  }
}
```

### Windsurf

Lisää `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "aura": {
      "command": "/polku/aura/.venv/bin/python",
      "args": ["-m", "aura.cli", "serve"]
    }
  }
}
```

### Muu MCP-yhteensopiva työkalu

Aura on standardi MCP-server. Mikä tahansa työkalu joka tukee MCP-protokollaa voi käyttää Auraa. Käynnistyskomento:

```bash
/polku/aura/.venv/bin/python -m aura.cli serve
```

Tai `uv`:llä ilman erillistä asennusta:

```bash
uv --directory /polku/aura run aura serve
```

## Komentorivityökalu

```bash
source .venv/bin/activate

# Hae datasettejä
aura search "väestö helsinki"
aura search "joukkoliikenne"

# Tilastot ja lähteet
aura stats
aura sources

# Päivitä data
aura harvest              # kaikki lähteet
aura harvest avoindata.fi  # yksittäinen lähde
aura harvest --list        # listaa saatavilla olevat
aura refresh              # harvest + laatupisteet + health + skeema
aura infer-schemas        # päättele kenttätyypit esikatselusta

# Rikastukset
aura export-enrichments -o contributions/omat.json
aura import-enrichments contributions/*.json
```

> **Huom:** Tietokanta (`data/aura.db`) tulee repon mukana valmiina — ei tarvitse harvestoida erikseen.

## MCP-työkalut

**Haku ja selaus:**

| Työkalu | Kuvaus |
|---------|--------|
| `search` | Hae datasettejä luonnollisella kielellä (suodattimet: lähde, formaatti, organisaatio, saatavuus, alue) |
| `search_structured` | Hae datasettejä ja palauta JSON tekoälyagenteille |
| `search_by_region` | Hae alueellisesti (kunta, maakunta, postinumero) |
| `describe` | Kuvaa datasetti yksityiskohtaisesti (sis. skeema, laatu, rikastukset) |
| `query_data` | Esikatsele tai kyselöi datasetin sisältöä (CSV, JSON, PxWeb, WFS, OData); `area`-parametri rajaa WFS-kyselyn kuntaan, karttalehteen tai bbox:iin |
| `recommend` | Suosittele parhaita datasettejä aiheesta |
| `compare` | Vertaile datasettejä rinnakkain (2–5 kpl) |
| `find_related` | Etsi samankaltaiset datasetit |
| `suggest_questions` | Ehdota esimerkkikysymyksiä teemoittain ja alueittain |

**Alueanalyysi:**

| Työkalu | Kuvaus |
|---------|--------|
| `area_profile` | Alueprofiili: datasetit, laatu, puutteet |
| `compare_municipalities` | Vertaile kuntien datatarjontaa rinnakkain (2–5 kpl) |
| `lookup_municipality` | Hae kuntatiedot nimellä, koodilla tai postinumerolla |
| `municipality_bbox` | Kunnan rajauslaatikko (EPSG:3067) WFS/WCS-kyselyyn |
| `find_map_sheets` | MML:n TM35-karttalehdet jotka osuvat alueelle (kunta, bbox, piste, prefiksi) |
| `map_sheet` | Karttalehden bbox, centroidi sekä vanhempi- ja lapsilehdet |

**Laatu:**

| Työkalu | Kuvaus |
|---------|--------|
| `quality_report` | Datasetin laatupisteet dimensioittain |
| `quality_overview` | Yhteenveto laatupisteistä |
| `quality_ranking` | Parhaiten pisteytetyt datasetit |
| `quality_gaps` | Metatiedon puutteet ja parannusehdotukset |

**Rikastus ja tutkimus:**

| Työkalu | Kuvaus |
|---------|--------|
| `enrich` | Rikasta datasetin tietoja (avainsanat, kuvaukset, laatuhuomiot) |
| `batch_enrich` | Tallenna useita rikastuksia kerralla |
| `get_enrichments_tool` | Näytä datasetin rikastukset |
| `suggest_yso_tags` | Ehdota YSO-ontologian avainsanoja |
| `log_finding` | Kirjaa löydös tutkimuksen aikana |
| `list_findings` | Näytä session löydökset |
| `save_session_findings` | Tallenna löydökset enrichmenteiksi |

**Hallinta:**

| Työkalu | Kuvaus |
|---------|--------|
| `stats` | Näytä tilastot tietokannasta |
| `list_organizations` | Listaa datan julkaisijat |
| `list_formats` | Listaa saatavilla olevat dataformaatit |
| `harvest` | Hae datasettien metatiedot lähteistä |
| `list_sources` | Listaa datalähteet ja harvestoinnin tila |
| `probe_sizes` | Mittaa paikkatietoaineistojen koot |
| `health_check` | Tarkista resurssien saatavuus (HTTP) |
| `health_report` | Saatavuusraportti aiempien tarkistusten perusteella |
| `reference_status` | Viiteaineistojen tila |
| `populate_reference` | Lataa viiteaineistot kantaan |

## Rajapintojen suora käyttö agentissa

Aura ei ole pelkkä hakemisto — tekoälyagentti voi **hakea dataa suoraan** rajapinnoista käyttäjän puolesta. Kun käyttäjä kysyy esimerkiksi junan aikataulua, agentti etsii Aurasta oikean rajapinnan ja kyselee sitä reaaliajassa.

### Esimerkkejä

**Junaliikenne:**
> *"Moneltako IC147 saapuu Kuopioon tänään?"*
>
> Agentti etsii Aurasta Digitraffic rata-API:n ja hakee aikataulun: `rata.digitraffic.fi/api/v1/trains/2026-03-30/147`

**Tilastot:**
> *"Mikä on Tampereen väkiluku?"*
>
> Agentti löytää Tilastokeskuksen PxWeb-taulun ja kyselee sen `query_data`-työkalulla.

**Sää:**
> *"Mikä on lämpötila Helsingissä?"*
>
> Agentti hakee Ilmatieteen laitoksen WFS-rajapinnasta reaaliaikahavainnon.

### Tuetut rajapintatyypit

| Rajapinta | Suora kysely | Esimerkkilähde |
|-----------|-------------|----------------|
| REST/JSON | `query_data` tai suora HTTP | Digitraffic (tie, rata, meri), Sotkanet |
| PxWeb | `query_data` (suodattimet) | Tilastokeskus, LUKE |
| WFS | `query_data` (`area`, suodattimet) | FMI, SYKE, MML, Väylävirasto |
| OData v4 | `query_data` (filter) | Traficom |
| CSV | `query_data` (rivit) | avoindata.fi, HRI |
| GTFS | GTFS-tiedostojen URL:t | Digitransit (32 operaattoria) |
| GraphQL | Vaatii rekisteröitymisen | Digitransit Routing API |

**Huom:** Osa rajapinnoista (Digitransit GraphQL, MML OGC API) vaatii API-avaimen. Agentti ohjaa rekisteröitymiseen tarvittaessa.

## Datalähteet

Katso täydellinen datasettikatalogi: **[docs/CATALOG.md](docs/CATALOG.md)**
Katso lähteiden tekniset tiedot: **[docs/SOURCES.md](docs/SOURCES.md)**
Katso tuetut dataformaatit: **[docs/formats.md](docs/formats.md)**

| Lähde | Tyyppi | Datasettejä | Arvioitu koko |
|-------|--------|-------------|---------------|
| [avoindata.fi](https://avoindata.suomi.fi) | CKAN API | 1 738 | 102 GB |
| [Tilastokeskus](https://stat.fi) | PxWeb API | 1 524 | 7,1 GB |
| [Paikkatietoikkuna](https://paikkatietoikkuna.fi) | Oskari API | 689 | — |
| [LUKE](https://statdb.luke.fi) | PxWeb API | 662 | 3,1 GB |
| [SYKE](https://ckan.ymparisto.fi) | CKAN API | 614 | 18 GB |
| [HRI (hri.fi)](https://hri.fi) | CKAN API | 549 | 39 GB |
| [Suomi.fi-koodistot](https://koodistot.suomi.fi) | REST API | 511 | — |
| [Digitraffic](https://www.digitraffic.fi) | REST/OpenAPI | 162 | 1,5 GB |
| [Ilmatieteen laitos](https://www.ilmatieteenlaitos.fi) | WFS 2.0 | 160 | 14 GB |
| [Digitransit](https://digitransit.fi) | GTFS/GraphQL | 40 | — |
| [LUKE avoin tutkimusdata](https://opendata.luke.fi) | CKAN | 124 | 2,1 GB |
| [Valtiokonttori](https://avoindata.tutkihallintoa.fi) | REST API | 48 | — |
| [Metsäkeskus](https://avoin.metsakeskus.fi) | WFS/WCS/ZIP | 43 | 1,2 TB |
| Kuntien paikkatiedot (36 kuntaa) | WMS/WFS/ArcGIS | 36 | 57 GB |
| [Ruokavirasto](https://www.ruokavirasto.fi) | INSPIRE/GeoServer | 33 | — |
| [Traficom](https://opendata.traficom.fi) | OData v4 | 32 | 2,5 GB |
| [Vaalirahoitusvalvonta](https://www.vaalirahoitusvalvonta.fi) | CSV | 27 | — |
| [LUKE paikkatietopalvelu](https://kartta.luke.fi) | WMS/WFS | 10 | 70 GB |
| [Tilastokeskus paikkatieto](https://geo.stat.fi) | WMS/WFS | 9 | 1,5 GB |
| [MML](https://www.maanmittauslaitos.fi) | WMS/WFS/OGC API | 7 | 184 GB |
| [Overture Maps](https://overturemaps.org) | GeoParquet (S3) | 6 | 215 GB |
| [Väylävirasto](https://vayla.fi) | WMS/WFS/OGC API | 5 | 8,8 GB |
| [GTK](https://www.gtk.fi) | ArcGIS WFS/WMS | 5 | 7 GB |
| [PaItuli (CSC)](https://paituli.csc.fi) | WMS/WFS | 5 | 88 GB |
| [Taustakartat](https://kartat.kapsi.fi) | TMS | 4 | 19 GB |
| [LIPAS](https://www.jyu.fi/sport/fi/yhteistyo/lipas) | WMS/WFS | 3 | 1 GB |
| [STUK](https://stuk.fi) | WMS/REST | 2 | — |
| [Finap/NAP](https://finap.fi) | Portaali | 5 | — |
| [Suomi.fi-sanastot](https://sanastot.suomi.fi) | REST API | — | — |
| [THL Sotkanet](https://sotkanet.fi) | REST API | ~3 500 | — |
| **Yhteensä** | | **~10 500+** | **~2 TB** |

## Osallistuminen

Auraan voi osallistua monella tavalla — myös ilman koodaamista.

### Rikasta dataa (helpoin tapa)

Jokaisella Aura MCP -sessiolla kertyy arvokasta tietoa dataseteistä: mitä kenttiä data sisältää, miten sitä haetaan, millainen laatu on. Tämä tieto voidaan tallentaa pysyvästi `enrich()`-työkalulla.

**MCP-session aikana** tekoäly voi kutsua `enrich()`-työkalua automaattisesti:

```
"Tutki Ruokaviraston peltolohkorekisterin sisältö ja tallenna löydökset."
```

AI tutkii datasetin, löytää kentät ja metatiedot, ja kutsuu:
```python
enrich("ruokavirasto-peltolohkorekisteri-2024", "data_fields",
       '["lohko_id", "kasvilaji", "pinta_ala_ha"]', confidence="high")
enrich("ruokavirasto-peltolohkorekisteri-2024", "keywords",
       '["maatalous", "CAP", "tukialue"]')
```

**Kontribuoi rikastuksia muille:**

```bash
aura export-enrichments -o contributions/omat-rikastukset.json
git add contributions/
git commit -m "data: enrich Ruokaviraston datasettejä"
# Avaa pull request
```

**Tuetut rikastuskentät:**

| Kenttä | Tyyppi | Kuvaus |
|--------|--------|--------|
| `keywords` | lista | Lisäavainsanat (`'["maatalous", "peltolohko"]'`) |
| `tags` | lista | Vapaamuotoiset tagit (`'["paikkatietoaineisto"]'`) |
| `data_fields` | lista | Datasetin kentät (`'["id", "nimi", "pinta_ala"]'`) |
| `joinable_keys` | lista | Yhdistettävät avaimet (`'[{"field":"kunta","key":"kuntakoodi"}]'`) |
| `related_services` | lista | Palvelut jotka käyttävät dataa |
| `yso_concepts` | lista | YSO-ontologian käsitteet |
| `description_extended` | teksti | Laajennettu kuvaus |
| `api_endpoint` | teksti | Löydetty rajapinta-URL |
| `api_format` | teksti | Rajapinnan formaatti |
| `access_instructions` | teksti | Ohjeet datan hakemiseen |
| `quality_notes` | teksti | Huomioita datan laadusta |
| `use_case` | teksti | Käyttötapausesimerkki |
| `related_datasets` | teksti | Liittyvät datasetit |
| `temporal_coverage` | teksti | Ajallinen kattavuus |
| `update_frequency_actual` | teksti | Havaittu päivitystiheys |
| `organization_context` | teksti | Taustatietoa julkaisijasta |
| `crs` | teksti | Koordinaattijärjestelmä (esim. EPSG:3067) |
| `auth_method` | teksti | Autentikointimenetelmä (none, apikey, oauth) |
| `auth_registration_url` | teksti | URL josta pääsy haetaan |
| `auth_notes` | teksti | Muita huomioita pääsyvaatimuksista |

### Lisää uusia datalähteitä

Katso **[CONTRIBUTING.md](CONTRIBUTING.md)** ohjeet uuden harvesterin luomiseen.

### Raportoi ja ehdota

Avaa [issue GitHubissa](https://github.com/trotor/aura/issues).

## Projektirakenne

```
aura/
├── src/aura/               # Pääpaketti
│   ├── server.py           # MCP-server (FastMCP)
│   ├── database.py         # SQLite + FTS5 + enrichments
│   ├── models.py           # Pydantic-tietomallit
│   ├── search.py           # Hakutoiminnot ja muotoilu
│   ├── cli.py              # Komentorivityökalu
│   └── harvesters/         # Datalähteiden keräimet (29 kpl)
├── data/
│   ├── aura.db             # SQLite-tietokanta (osa repoa)
│   └── boundaries/         # Rajausaineistot GeoPackage (gitignore)
├── contributions/          # Jaetut rikastukset (JSON)
├── scripts/migrations/     # Tietokantamigraatiot
├── docs/                   # Dokumentaatio
└── tests/                  # Testit
```

## Tietokanta

SQLite + FTS5 -täystekstihaku. Tietokanta on osa git-repoa — ei tarvitse harvestoida erikseen.

> **Git LFS** — `data/aura.db` tallennetaan [Git LFS:llä](https://git-lfs.github.com/) repon koon hallitsemiseksi. Kloonaaminen vaatii `git lfs`:n:
> ```bash
> brew install git-lfs   # macOS
> git lfs install        # kerran per kone
> git clone https://github.com/trotor/aura.git  # LFS-tiedostot haetaan automaattisesti
> ```

Skeemamuutokset hoidetaan migraatiojärjestelmällä (`scripts/migrations/`). Migraatiot ajetaan automaattisesti `init_db()`:n yhteydessä — tietokanta ei nollaudu päivityksessä.

## Maantieteellinen kattavuus ja rajausaineistot

Aura tallentaa jokaiselle datasetille `geographical_coverage`-kentän, joka kertoo minkä alueen dataa datasetti sisältää. Tieto tulee pääasiassa harvestoinnin yhteydessä.

### Nykytila

| Tilasto | Arvo |
|---------|------|
| Datasettejä joilla aluetieto | ~1 200+ / 7 024 |
| Yleisimmät arvot | `Helsinki`, `Turku`, `Oulu`, `Espoo`, `Vantaa` |
| Viitetaulut | 308 kuntaa, 3 784 postinumeroa |
| Oletusarvo | `["Suomi"]` (kaikki harvestarit ellei tarkempaa tietoa) |

Arvot tulevat eri lähteistä:
- **avoindata.fi** — API palauttaa kaupunkien ja alueiden nimet
- **Kuntien paikkatiedot** — 36 kuntaa omalla `geographical_coverage`-arvolla
- **Staattiset harvestarit** — konfiguraatiossa (esim. Overture Maps → `["Maailma"]`)
- **Muut** — oletusarvo `["Suomi"]`

### Rajausaineistot

Paikallisina rajausaineistoina käytetään GeoPackage-tiedostoja `data/boundaries/`-kansiossa. Kansio on gitignoressa — aineistot ladataan erikseen. Lähde: [Kapsi.fi](https://kartat.kapsi.fi/files/) (MML:n avoin data, CC BY 4.0).

```bash
# Lataa kaikki rajausaineistot yhdellä komennolla (~40 MB)
bash scripts/download_boundaries.sh
```

Skripti on idempotentti — ohittaa jo ladatut tiedostot.

#### Karttalehtijako (TM35)

MML:n karttalehtijako kattaa koko Suomen ETRS-TM35FIN (EPSG:3067) -koordinaatistossa. 7 hierarkiatasoa:

| Taso | Mittakaava | Koodimuoto | Ruudun koko | Ruutuja |
|------|-----------|------------|-------------|---------|
| 1 | 1:200 000 | `L4` | 192 × 96 km | 65 |
| 2 | 1:100 000 | `L41` | 96 × 48 km | 208 |
| 3 | 1:50 000 | `L413` | 48 × 24 km | 832 |
| 4 | 1:25 000 | `L4133` | 24 × 12 km | 3 328 |
| 5 | 1:10 000 | `L4133A` | 6 × 6 km | 26 624 |
| 6 | 1:5 000 | `L4133A3` | 3 × 3 km | 106 496 |
| 7 | 1:1 000 | `L4133A3_1` | 1 × 1 km | 398 286 |

#### Kuntajako (hallinnolliset rajat)

MML:n hallinnolliset aluejaot: 308 kuntaa, 19 maakuntaa, 23 hyvinvointialuetta, Suomen raja. Kaksi mittakaavaa: 1:1M (yleiskäyttö) ja 1:10k (tarkka geometria).

#### Kiinteistörajat

Kiinteistörajat haetaan MML:n rajapintapalvelusta (liian suuria lokaaliin tallennukseen).

#### MML API-avain

MML:n OGC API Processes -tiedostopalvelu vaatii ilmaisen API-avaimen. Kapsi.fi-peili toimii ilman avainta, mutta muihin MML-aineistoihin avain tarvitaan:

1. Rekisteröidy: https://omatili.maanmittauslaitos.fi/user/new/avoimet-rajapintapalvelut
2. Luo API-avain OmaTili-palvelussa
3. Tallenna `.env`-tiedostoon: `MML_API_KEY=avaimesi`

### Hakusuodatin

`region`-suodatin MCP-työkaluissa:

```python
search("joukkoliikenne", region="Helsinki")     # kaupunkitaso
search("ympäristödata", region="Uusimaa")        # maakuntataso → laajentuu kuntiin
search("palvelut", region="33100")               # postinumero → kunta
```

Hierarkkinen haku: haettaessa maakunnalla palautetaan myös maakunnan kuntien aineistot. Viitetaulut (308 kuntaa, 3 784 postinumeroa) mahdollistavat alueen tunnistuksen.

## Kehitys

```bash
source .venv/bin/activate
pip install -e ".[dev]"

pytest              # testit
ruff check src/     # lintteri
mypy src/           # tyypintarkistus
```

Katso **[CONTRIBUTING.md](CONTRIBUTING.md)** tarkemmat ohjeet.

## Versiointi

[Semantic Versioning 2.0.0](https://semver.org/) · [What's New](docs/WHATSNEW.md) · [VERSIONING.md](VERSIONING.md) · [CHANGELOG.md](CHANGELOG.md)

## Aura etäpalveluna

Aura toimii tällä hetkellä paikallisena palveluna — jokainen käyttäjä ajaa oman instanssinsa. Etsimme organisaatiota, joka haluaisi tarjota Auran keskitettynä etäpalveluna: **remote MCP -palvelin**, johon kuka tahansa voisi yhdistää AI-assistenttinsa.

Teknisesti palvelu on kevyt — SQLite-kanta, Python-prosessi ja ajastettu harvestointi. Koodi on MIT-lisenssillä vapaasti käytettävissä.

Tämä sopisi erityisesti taholle, jonka tehtävänä on edistää suomalaisen datan löydettävyyttä: tutkimusinfrastruktuurin ylläpitäjä, avoimen datan edistäjä, julkishallinnon digitalisaatiotaho tai kirjasto- ja arkistosektori.

Kiinnostuitko? **[Lue lisää ja ota yhteyttä (issue #130)](https://github.com/trotor/aura/issues/130)**

## Lisenssi

[MIT](LICENSE)
