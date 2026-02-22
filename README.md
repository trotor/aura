# Aura

**Suomalaisen avoimen datan discovery- ja ymmärryspalvelu**

> **5 690+ datasettiä** · **12 390+ resurssia** · **250+ organisaatiota** · **~1,6 TB** avointa dataa
>
> 23 datalähteestä: avoindata.fi, SYKE, HRI, Tilastokeskus, LUKE, Digitraffic, Ilmatieteen laitos, Overture Maps, GTK, Traficom, Metsäkeskus, Taustakartat, Ruokavirasto, Kuntien paikkatiedot (36 kuntaa) ym.

Aura kyntää suomalaisen avoimen datan esiin piilostaan ja tekee sen ymmärrettäväksi. Palvelu toimii MCP-serverinä tekoälyille sekä avoimena web-palveluna ihmisille.

> *Aura* — suomen kielen kyntämistä. Aura kyntää datan esiin.

## Mitä Aura tekee?

- **Aggregoi** metadatan 23 avoimen datan lähteestä
- **Normalisoi** CKAN, PxWeb, OData, WFS ja OpenAPI -formaatit yhtenäiseen muotoon
- **Tekee hakukelpoiseksi** — FTS5-täystekstihaku luonnollisella kielellä
- **Arvioi datakoon** — jokaiselle datasetille arvioitu koko
- **Rikastaa joukkoistamalla** — MCP-sessiot kerryttävät tietoa dataseteistä
- **Palvelee tekoälyjä** MCP-serverin kautta (Claude, GPT, jne.)

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

# Rikastukset
aura export-enrichments -o contributions/omat.json
aura import-enrichments contributions/*.json
```

> **Huom:** Tietokanta (`data/aura.db`) tulee repon mukana valmiina — ei tarvitse harvestoida erikseen.

## MCP-työkalut

| Työkalu | Kuvaus |
|---------|--------|
| `search` | Hae datasettejä luonnollisella kielellä (suodattimet: lähde, formaatti, organisaatio, saatavuus) |
| `search_structured` | Hae datasettejä ja palauta JSON tekoälyagenteille |
| `describe` | Kuvaa datasetti yksityiskohtaisesti (sis. rikastukset) |
| `recommend` | Suosittele parhaita datasettejä aiheesta |
| `compare` | Vertaile datasettejä rinnakkain (2–5 kpl) |
| `find_related` | Etsi samankaltaiset datasetit |
| `enrich` | Rikasta datasetin tietoja (avainsanat, kuvaukset, laatuhuomiot) |
| `get_enrichments_tool` | Näytä datasetin rikastukset |
| `stats` | Näytä tilastot tietokannasta |
| `list_organizations` | Listaa datan julkaisijat |
| `list_formats` | Listaa saatavilla olevat dataformaatit |
| `harvest` | Hae datasettien metatiedot lähteistä |
| `list_sources` | Listaa datalähteet ja harvestoinnin tila |
| `probe_sizes` | Mittaa paikkatietoaineistojen koot |

## Datalähteet

Katso täydellinen datasettikatalogi: **[docs/CATALOG.md](docs/CATALOG.md)**
Katso lähteiden tekniset tiedot: **[docs/SOURCES.md](docs/SOURCES.md)**

| Lähde | Tyyppi | Datasettejä | Arvioitu koko |
|-------|--------|-------------|---------------|
| [avoindata.fi](https://avoindata.suomi.fi) | CKAN API | 1 943 | 114 GB |
| [SYKE](https://ckan.ymparisto.fi) | CKAN API | ~615 | ~50 GB |
| [HRI (hri.fi)](https://hri.fi) | CKAN API | 549 | 39 GB |
| [LUKE](https://statdb.luke.fi) | PxWeb API | 495 | 2,3 GB |
| [Tilastokeskus](https://stat.fi) | PxWeb API | 374 | 1,7 GB |
| [Digitraffic](https://www.digitraffic.fi) | REST/OpenAPI | 162 | 1,5 GB |
| [Ilmatieteen laitos](https://www.ilmatieteenlaitos.fi) | WFS 2.0 | 160 | 14 GB |
| [Overture Maps](https://overturemaps.org) | GeoParquet (S3) | 6 | ~215 GB |
| [Metsäkeskus](https://avoin.metsakeskus.fi) | WFS/WCS/ZIP | 43 | 1,2 TB |
| [Traficom](https://opendata.traficom.fi) | OData v4 | 32 | 2,5 GB |
| [GTK](https://www.gtk.fi) | ArcGIS WFS/WMS | 5 | 7 GB |
| [Taustakartat](https://kartat.kapsi.fi) | TMS | 4 | ~20 GB |
| [Ruokavirasto](https://www.ruokavirasto.fi) | INSPIRE/GeoServer | 33 | — |
| Kuntien paikkatiedot | WMS/WFS/ArcGIS | 36 | — |
| **Yhteensä** | | **~5 690** | **~1,6 TB** |

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
│   └── harvesters/         # Datalähteiden keräimet (23 kpl)
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

Skeemamuutokset hoidetaan migraatiojärjestelmällä (`scripts/migrations/`). Migraatiot ajetaan automaattisesti `init_db()`:n yhteydessä — tietokanta ei nollaudu päivityksessä.

## Maantieteellinen kattavuus ja rajausaineistot

Aura tallentaa jokaiselle datasetille `geographical_coverage`-kentän, joka kertoo minkä alueen dataa datasetti sisältää. Tieto tulee pääasiassa harvestoinnin yhteydessä.

### Nykytila

| Tilasto | Arvo |
|---------|------|
| Datasettejä joilla aluetieto | ~1 200+ / 5 690 |
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

[Semantic Versioning 2.0.0](https://semver.org/) · [VERSIONING.md](VERSIONING.md) · [CHANGELOG.md](CHANGELOG.md)

## Lisenssi

[MIT](LICENSE)
