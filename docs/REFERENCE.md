# Aura – tekninen referenssi

Tämä sivu kokoaa Auran asennuksen, työkalut, komentorivin ja tietokannan
yksityiskohdat. Lyhyt esittely ja esimerkit ovat [README:ssä](../README.md).

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

Aura tarjoaa kolme työkaluprofiilia. Paikallisesti profiili valitaan `AURA_TOOL_PROFILE`-muuttujalla; HTTP-palvelin tarjoilee julkisen profiilin polussa `/mcp` ja laatuprofiilin polussa `/mcp/laatu`.

### Julkinen profiili (oletus)

Viisi aikomustason työkalua. Jokainen palauttaa strukturoidun vastauksen (`structuredContent`, julkaistu `outputSchema`) ja enintään viiden rivin tekstiyhteenvedon. Vastaus päättyy valmiisiin seuraaviin kutsuihin (`next_actions`), ja virheissä on koodi, vihje ja korjattu kutsu (`error.code`, `error.hint`, `error.suggested_call`).

| Työkalu | Tehtävä |
|---------|---------|
| `find_data` | Hae aineistoja kaikilla suodattimilla (lähde, formaatti, julkaisija, saatavuus, alue) |
| `inspect_dataset` | Aineiston kuvaus, resurssit, kentät, laatu, saatavuus ja kyselyohje |
| `query_source` | Aineiston sisältö riveinä: PxWeb, WFS, FMI:n tallennetut kyselyt, OData, CSV, JSON. Jokaisessa vastauksessa on kyselyn täsmällinen URL, lisenssi ja hakuaika |
| `area_snapshot` | Alueen tunnistus, ylemmät aluetasot, tunnukset ja datatarjonta aiheittain |
| `find_related` | Samankaltaiset aineistot |

Alueen voi antaa nimellä tai koodilla: `Tampere`, `837`, `KU837`, `Pirkanmaa`, `33100`. Lakkautettu kunta tulkitaan seuraajakseen, ja vastaus kertoo sen (esim. `Nastola` → Lahti, liitetty 2016). PxWeb-suodattimissa aikadimensio ymmärtää arvot `uusin` ja `2020-2024`.

Profiili tarjoaa myös MCP-resurssit alueille (`aura://kunta/{koodi}`, `aura://maakunta/{koodi}`, `aura://alue/{taso}/{koodi}`) sekä promptit `kuntavertailu`, `loyda-ja-hae` ja `aluekatsaus`.

### Laatuprofiili (`/mcp/laatu`, `AURA_TOOL_PROFILE=laatu`)

Julkaisijalle ja ylläpitäjälle: metatiedon laatu ja resurssien saatavuus. Kaikki työkalut ovat lukuoperaatioita, joten profiili toimii myös read-only-instanssissa. Rajaukseen riittää osa julkaisijan nimestä (`organization="Espoo"`).

| Työkalu | Tehtävä |
|---------|---------|
| `quality_summary` | Laatupisteet dimensioittain, jakauma, heikoimmat ja parhaat aineistot |
| `metadata_gaps` | Puuttuvat kentät (kuvaus, avainsanat, päivitystiheys, lisenssi, englanninkieliset) ja helpoimmin parannettavat aineistot |
| `availability_report` | Tallennettujen saatavuustarkistusten tulos ja ikä, rikkinäiset linkit |
| `find_data`, `inspect_dataset` | Yksittäisen aineiston tarkastelu |
| `log_finding`, `list_findings` | Havaintojen kirjaus istunnon ajaksi (vain oma instanssi; read-only-palvelimelta poistettu) |

Saatavuusraportti ei aja tarkistuksia; ne ajetaan ylläpidossa (`aura health`), ja raportti kertoo milloin viimeksi.

```json
{ "mcpServers": { "aura-laatu": { "url": "https://<instanssi>/mcp/laatu" } } }
```

### Admin-profiili (`AURA_TOOL_PROFILE=admin`)

Koko työkalupinta: ylläpito, laatu, rikastus, rajausaineistot ja vanhat hakutyökalut. Repon oma `.mcp.json` käyttää tätä profiilia.

Vanhat työkalut, jotka aikomustason pinta korvaa, näkyvät admin-profiilissa yhden version ajan. Niiden kuvaus alkaa sanoilla "Vanhentunut: käytä X":

| Vanha | Korvaaja |
|-------|----------|
| `search`, `search_structured`, `search_by_region`, `recommend` | `find_data` |
| `describe`, `quality_report`, `get_enrichments_tool` | `inspect_dataset` |
| `query_data` | `query_source` |
| `area_profile`, `lookup_municipality`, `compare_municipalities` | `area_snapshot` |

**Haku ja selaus (admin):**

| Työkalu | Kuvaus |
|---------|--------|
| `compare` | Vertaile datasettejä rinnakkain (2–5 kpl) |
| `suggest_questions` | Ehdota esimerkkikysymyksiä teemoittain ja alueittain |
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
> Agentti löytää Tilastokeskuksen PxWeb-taulun ja kyselee sen `query_source`-työkalulla: `filters={"Tiedot": ["Väestö 31.12."], "Vuosi": ["uusin"]}, area="Tampere"`.

**Sää:**
> *"Mikä on lämpötila Helsingissä?"*
>
> Agentti hakee Ilmatieteen laitoksen tallennetusta kyselystä reaaliaikahavainnon: `query_source("fmi-fmi::observations::weather::simple", filters={"place": ["Helsinki"], "parameters": ["t2m"]})`.

### Tuetut rajapintatyypit

| Rajapinta | Suora kysely | Esimerkkilähde |
|-----------|-------------|----------------|
| REST/JSON | `query_source` tai suora HTTP | Digitraffic (tie, rata, meri), Sotkanet |
| PxWeb | `query_source` (suodattimet, `area`) | Tilastokeskus, LUKE |
| WFS | `query_source` (`area`, suodattimet) | SYKE, MML, Väylävirasto |
| FMI:n tallennetut kyselyt | `query_source` (kyselyn parametrit suodattimina) | Ilmatieteen laitos |
| OData v4 | `query_source` (filter) | Traficom |
| CSV | `query_source` (rivit) | avoindata.fi, HRI |
| GTFS | GTFS-tiedostojen URL:t | Digitransit (32 operaattoria) |
| GraphQL | Vaatii rekisteröitymisen | Digitransit Routing API |

**Huom:** Osa rajapinnoista (Digitransit GraphQL, MML OGC API) vaatii API-avaimen. Agentti ohjaa rekisteröitymiseen tarvittaessa.

## Datalähteet

Katso täydellinen datasettikatalogi: **[docs/CATALOG.md](CATALOG.md)**
Katso lähteiden tekniset tiedot: **[docs/SOURCES.md](SOURCES.md)**
Katso tuetut dataformaatit: **[docs/formats.md](formats.md)**

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
| [Vipunen](https://vipunen.fi) (opetushallinnon tilastopalvelu) | REST API | 47 | — |
| [Kelasto](https://tietotarjotin.fi/tilastotietokanta-kelasto) (Kelan raportit, ei datarajapintaa) | Raporttilomake | 86 | — |
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
| [Kirjastot.fi](https://tilastot.kirjastot.fi) (kirjastotilastot, Kirkanta API v4) | XLS/REST API | 2 | — |
| [PRH](https://avoindata.prh.fi) (YTJ-yrityshaku, koodistot ja postinumerot) | REST API | 3 | — |
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

Katso **[CONTRIBUTING.md](../CONTRIBUTING.md)** ohjeet uuden harvesterin luomiseen.

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
| Viitetaulut | 308 kuntaa, 3 784 postinumeroa, 477 aluetta 12 tasolla, 272 lakkautettua kuntaa |
| Oletusarvo | `["Suomi"]` (kaikki harvestarit ellei tarkempaa tietoa) |

Arvot tulevat eri lähteistä:
- **avoindata.fi** — API palauttaa kaupunkien ja alueiden nimet
- **Kuntien paikkatiedot** — 36 kuntaa omalla `geographical_coverage`-arvolla
- **Staattiset harvestarit** — konfiguraatiossa (esim. Overture Maps → `["Maailma"]`)
- **Muut** — oletusarvo `["Suomi"]`

### Aluetasot ja kuntaliitokset

Kaksi viiteaineistoa Tilastokeskuksen luokituspalvelusta (`aura populate areas`, `aura populate municipality_changes`):

- **Aluetasojen ristiintaulukko** (`ref_areas`, `ref_area_membership`): mihin seutukuntaan, maakuntaan, hyvinvointialueeseen, suuralueeseen, elinvoimakeskukseen, vaalipiiriin, kuntaryhmään ja NUTS 1–3 -alueeseen kunta kuuluu.
- **Kuntaliitoshistoria** (`ref_municipality_changes`): lakkautetun kunnan seuraaja ja liitosvuosi. Vuodet päätellään luokituksen vuosiversioista (1970–), seuraajat lakkautettujen kuntien luokitusavaimesta. Avainta uudemmat liitokset kirjataan käsin lähteineen (`aura.populators.areas.KNOWN_SUCCESSORS`).

`aura.areas.resolve_area()` tulkitsee alueen kaikille työkaluille samalla tavalla: nimi (fi/sv, myös taivutettuna), kuntakoodi, StatFin-koodi (`KU837`, `MK06`, `SK064`, `HVA08`), postinumero tai lakkautetun kunnan nimi.

### Kiinteistötunnus aluerajauksena

`query_source(area=...)` hyväksyy WFS-aineistoille kiinteistötunnuksen muodoissa `17440100030006`, `174-401-3-6` ja `092-072-0032-0006`. Kysely tehdään palsta kerrallaan kiinteistön palstojen suorakaiteilla, ja samat rivit yhdistetään. Suorakaiteeseen voi osua naapurikiinteistöjen kohteita, ja vastaus kertoo sen. Määräala (`…-M601`) hylätään, koska sillä ei ole omia rajoja.

Palstojen rajat haetaan järjestyksessä:

1. **Paikallinen indeksi** `data/boundaries/kiinteistot.sqlite` (gitignoressa, `AURA_KIINTEISTOT_DB`). Lähde on MML:n kiinteistörekisterikartta (CC BY 4.0) [Kapsi.fi:n peilistä](https://kartat.kapsi.fi/files/kiinteistorekisterikartta/) karttalehdittäin. API-avainta ei tarvita.
2. **Kunnan oma avoin WFS** (nyt Helsinki), jos indeksissä ei ole tunnusta. Kattaa vain kunnan ylläpitämät kiinteistöt.
3. **Lataus tarvittaessa:** jos kunta puuttuu indeksistä, ensimmäinen kysely lataa sen (Luhanka 1,5 s, Rovaniemi noin 30 s), ja seuraavat kyselyt käyttävät valmista indeksiä. Lakkautetun kunnan tunnus ladataan seuraajakunnan rajoilla. Kuntia ladataan yksi kerrallaan. Kytke pois asettamalla `AURA_KIINTEISTOT_AUTO=0`; silloin kunnat ladataan käsin komennolla `aura parcels Luhanka 435 …`.

Julkisessa palvelussa indeksi on pysyvällä levyllä (`AURA_KIINTEISTOT_DB=/data/kiinteistot/kiinteistot.sqlite`), koska kontti ajetaan vain luku -tilassa.

MML:n omat rajapinnat (kiinteistötietojen kyselypalvelu ja paikkatiedon tiedostopalvelu) vaativat maksuttoman API-avaimen, jonka saa MML:n Oma tili -palvelusta. Aura ei tarvitse sitä, koska Kapsin peili jakaa saman avoimen aineiston.

Omistajatietoja ei haeta eikä aineistossa ole. Henkilön omistaman kiinteistön tunnus on silti henkilötieto: telemetria korvaa tunnukset paikkamerkillä `<kiinteistötunnus>`, ja Metsäkeskuksen aineistojen ehdot muistuttavat henkilötietosäännöistä, jos tietoja yhdistetään henkilöihin.

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
find_data("joukkoliikenne", region="Helsinki")     # kaupunkitaso
find_data("ympäristödata", region="Uusimaa")        # maakuntataso → laajentuu kuntiin
find_data("palvelut", region="33100")            # postinumero → kunta
```

Hierarkkinen haku: haettaessa maakunnalla palautetaan myös maakunnan kuntien aineistot. Viitetaulut (308 kuntaa, 3 784 postinumeroa) mahdollistavat alueen tunnistuksen.

## Laajennuspisteet

Avoin Aura on metatietokatalogi. Laajennus voi tuoda työkaluvastauksiin valmiita tunnuslukuja tai laskelmia koskematta Auran omaan koodiin (`aura.extensions`). Koukku rekisteröidään nimellä `register(nimi, funktio)`:

| Koukku | Allekirjoitus | Mihin vastaukseen |
|---|---|---|
| `find_data.indicators` | `(conn, query, region) -> list[dict]` | `find_data`-vastauksen `indicators`-kenttä |
| `inspect_dataset.recipe` | `(conn, dataset) -> dict \| None` | aineiston todennettu kyselypohja |
| `area_snapshot.key_figures` | `(conn, area) -> list[dict]` | alueen tunnusluvut arvoineen ja lähteineen |

`add_instructions(teksti)` lisää rivin julkisen profiilin ohjeeseen. Koukun poikkeus kirjataan lokiin eikä kaada työkalua.

Esimerkki laajennuksesta: kiinteistön puuston hakkuuarvo. Kiinteistötunnus rajaa Metsäkeskuksen metsävarakuviot (`metsakeskus-stand`), joiden tukki- ja kuitupuun määrät kerrotaan Luken kantohinnoilla (`luke-0100_teokau.px`). Avoin Aura antaa molemmat aineistot lähteineen; laskun voi tehdä tekoälyavustaja, oma työkalu tai laajennus. Pro-versio käyttää samoja koukkuja tunnuslukuihinsa.

## Kehitys

```bash
source .venv/bin/activate
pip install -e ".[dev]"

pytest              # testit
ruff check src/     # lintteri
mypy src/           # tyypintarkistus
```

Katso **[CONTRIBUTING.md](../CONTRIBUTING.md)** tarkemmat ohjeet.

### Käyttötelemetria (oletuksena pois)

Oman instanssin ylläpitäjä voi kytkeä päälle suppean käyttökirjauksen asettamalla `AURA_TELEMETRY_DB=/polku/telemetria.db`. Raportti: `aura telemetry [--days 30] [--json]`.

Kantaan tallentuu:

- käyttö päivittäin työkaluittain ja asiakasohjelmittain: kutsut, virheet ja keskimääräinen kesto. Asiakasohjelma on User-Agentin tuotenimi ilman versiota, esim. `claude-user`.
- mitä kysytään: hakusanat, alueet, aineistotunnisteet ja tunnusluvut (työkalujen `query`-, `question`-, `region`-, `area(s)`-, `dataset_id`- ja `indicator`-argumentit) laskureina
- nollatulokselliset haut ja käsitteet, joita laajennus ei tunnistanut
- virheet muodossa `työkalu:koodi`
- istunnon työkaluketjut kuviona, kun asiakkaalla on istunto. Tilaton HTTP ei anna istuntoa.

Kantaan ei tallennu istuntoa, IP-osoitetta, käyttäjää eikä yksittäisiä tapahtumia. Sama arvo on yksi rivi, jonka laskuri kasvaa. Kellonaikaa ei tallenneta, ainoastaan päivä sekä kuvion ensimmäinen ja viimeinen esiintymä. Ohjausmerkit poistetaan kirjoitettaessa ja kentät katkaistaan 200 merkkiin. `aura gaps --clear` tyhjentää koko kertymän.

## Versiointi

[Semantic Versioning 2.0.0](https://semver.org/) · [What's New](WHATSNEW.md) · [VERSIONING.md](../VERSIONING.md) · [CHANGELOG.md](../CHANGELOG.md)
