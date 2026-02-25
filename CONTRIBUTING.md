# Osallistuminen Auraan

Aura on avoin projekti ja kaikki kontribuutiot ovat tervetulleita! Voit osallistua monella tavalla — koodin kirjoittamisesta datan rikastamiseen.

## Vaatimukset

- **Python 3.11+** — tarkista: `python3 --version`
- **git**

## Pikastartti

```bash
git clone https://github.com/trotor/aura.git
cd aura

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Varmista että kaikki toimii
pytest
ruff check src/
mypy src/
```

> Käytä **aina** virtuaaliympäristöä. Älä asenna paketteja globaalisti.

## Miten voit osallistua?

### 1. Rikasta dataa (helpoin tapa!)

Auran enrichment-järjestelmä mahdollistaa datan rikastamisen ilman koodaamista. Kun käytät Auraa MCP-serverin kautta, voit tallentaa löydöksiä suoraan tietokantaan.

**MCP-session aikana:**

AI kutsuu `enrich()`-työkalua automaattisesti kun se löytää uutta tietoa datasetistä — esim. mitä kenttiä data sisältää, miten sitä haetaan, tai millaista datan laatu on.

**Manuaalisesti:**

```bash
# Vie rikastukset JSON-tiedostoon
aura export-enrichments --output contributions/ruokavirasto-enrichments.json

# Tuo muiden rikastukset
aura import-enrichments contributions/*.json
```

**Kontribuoi rikastuksia:**

1. Käytä Auraa ja anna AI:n rikastaa datasettejä
2. `aura export-enrichments -o contributions/<kuvaus>.json`
3. Avaa pull request — rikastukset reviewataan ja yhdistetään

**Tuetut rikastuskentät:**

| Kenttä | Kuvaus |
|--------|--------|
| `description_extended` | Laajennettu kuvaus (mitä data oikeasti sisältää) |
| `data_fields` | Datasetin kentät/sarakkeet (JSON-lista, esim. `["id", "nimi"]`) |
| `keywords` | Lisäavainsanat (JSON-lista, esim. `["maatalous", "peltolohko"]`) |
| `tags` | Vapaamuotoiset tagit (JSON-lista, esim. `["paikkatietoaineisto"]`) |
| `joinable_keys` | Yhdistettävät avaimet (JSON, esim. `[{"field":"kunta","key":"kuntakoodi"}]`) |
| `related_services` | Palvelut jotka käyttävät dataa (JSON-lista) |
| `yso_concepts` | YSO-ontologian käsitteet (JSON-lista) |
| `api_endpoint` | Löydetty rajapinta-URL |
| `api_format` | Rajapinnan formaatti (REST, WFS, OData, jne.) |
| `access_instructions` | Ohjeet datan hakemiseen |
| `quality_notes` | Huomioita datan laadusta |
| `use_case` | Käyttötapausesimerkki |
| `related_datasets` | Liittyvät datasetit |
| `temporal_coverage` | Ajallinen kattavuus |
| `update_frequency_actual` | Havaittu päivitystiheys |
| `organization_context` | Taustatietoa julkaisijasta |
| `crs` | Koordinaattijärjestelmä (esim. EPSG:3067) |
| `auth_method` | Autentikointimenetelmä (none, apikey, oauth, registration) |
| `auth_registration_url` | URL josta pääsy haetaan |
| `auth_notes` | Muita huomioita pääsyvaatimuksista |

> Lista-kentät (`data_fields`, `keywords`, `tags`, `joinable_keys`, `related_services`, `yso_concepts`) tallennetaan JSON-taulukkoina. Muut kentät ovat vapaata tekstiä.

### 2. Lisää uusi datalähde

Uuden harvesterin lisääminen:

1. Luo `src/aura/harvesters/<nimi>.py`
2. Peri `BaseHarvester` (tai `CkanHarvester`/`PxWebHarvester` jos sama API-tyyppi)
3. Toteuta `name`, `description`, `url` ja `harvest() -> int`
4. Käytä `self._make_dataset(...)` datasettien luontiin
5. Rekisteröi `harvesters/__init__.py`:n `HARVESTERS`-dictiin
6. Kirjoita testit `tests/test_<nimi>.py`

Katso esimerkit:
- Staattinen konfiguraatio: `harvesters/gtk.py`, `harvesters/ruokavirasto.py`
- CKAN API: `harvesters/avoindata.py`
- PxWeb API: `harvesters/statfin.py`
- OpenAPI: `harvesters/digitraffic.py`

### 3. Paranna hakua ja MCP-työkaluja

MCP-työkalut ovat tiedostossa `src/aura/server.py`. Haku- ja muotoilulogiikka on eriytetty:
- `database.py` — SQL-kyselyt ja tietokantatoiminnot
- `search.py` — tulosten muotoilu
- `server.py` — MCP-tool-rajapinnat (ohuet wrapperit)

### 4. Raportoi bugeja ja ehdota ominaisuuksia

Avaa [issue GitHubissa](https://github.com/trotor/aura/issues).

## Arkkitehtuuri

```
Käyttäjä / AI
    ↓
server.py          ← MCP-tool-rajapinnat (FastMCP)
    ↓
database.py        ← SQL-kyselyt, CRUD, migraatiot
search.py          ← Tulosten muotoilu
    ↓
models.py          ← Pydantic-tietomallit (Dataset, Resource)
    ↓
harvesters/        ← Datalähteiden keräimet
    base.py        ← BaseHarvester + _make_dataset()
    ckan.py        ← CkanHarvester (avoindata.fi, HRI, SYKE)
    pxweb.py       ← PxWebHarvester (Tilastokeskus, LUKE)
    ...            ← Lähdekohtaiset harvesterit
```

Enrichment-järjestelmä noudattaa samaa kerroksittaista arkkitehtuuria:
- **database.py** — kaikki CRUD-operaatiot (`add_enrichment`, `get_enrichments`, `export/import`)
- **search.py** — muotoilu (`format_enrichments`)
- **server.py** — MCP-tool-wrapperit (`enrich()`, `get_enrichments_tool()`)
- **cli.py** — CLI-komennot (`export-enrichments`, `import-enrichments`)

## Koodikäytännöt

- **Python 3.11+**, tyypitetty (`mypy --strict`)
- **Testit**: `pytest` — jokainen harvester ja feature testataan
- **Lintteri**: `ruff check` — kaikki virheet korjattava
- **Commit-viestit**: Conventional Commits (`feat:`, `fix:`, `data:`, `docs:`, `refactor:`, `test:`, `chore:`)
- Kieli: koodi englanniksi, dokumentaatio ja UI suomeksi

## Tietokantamuutokset

Skeemamuutokset tehdään migraatioina:

1. Luo `scripts/migrations/NNN_kuvaus.sql`
2. Migraatio ajetaan automaattisesti seuraavan `init_db()`-kutsun yhteydessä
3. Versionumero parsitaan tiedostonimestä (`003_...` → versio 3)

## Rajausaineistot (valinnainen)

Paikkatietoaineistojen aluerajauksia varten tarvitaan karttalehtijako. Se ei tule repon mukana:

```bash
mkdir -p data/boundaries
curl -L -o /tmp/karttalehtijako.zip \
  "https://kartat.kapsi.fi/files/karttalehtijako_ruudukko/kaikki/etrs89/gpkg/TM35_karttalehtijako_GeoPackage.zip"
unzip -o /tmp/karttalehtijako.zip -d data/boundaries/
mv data/boundaries/TM35_karttalehtijako.gpkg data/boundaries/karttalehtijako.gpkg
```

Rajausaineistot eivät ole pakollisia — testit ja perusominaisuudet toimivat ilman niitä.

## Yleisiä ongelmia

### "No module named aura"

Virtuaaliympäristö ei ole aktiivinen:

```bash
source .venv/bin/activate
```

### "fts5: syntax error" tai FTS5-haku ei toimi

Python-versiosi SQLite ei tue FTS5:tä. Päivitä Python >=3.11 joka sisältää SQLite >=3.37 FTS5-tuella.

```bash
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
# Pitäisi olla >=3.9.0 (mieluiten >=3.37.0)
```

### WAL-tiedostot git statusissa

`data/aura.db-shm` ja `data/aura.db-wal` ovat SQLiten transientteja tiedostoja. Ne ovat `.gitignore`-tiedostossa — jos näet ne git statusissa, päivitä `.gitignore`:

```bash
git checkout .gitignore
```

### Testit epäonnistuvat rajausaineistojen puuttuessa

Osa testeistä voi ohittua ilman `data/boundaries/`-aineistoja. Lataa ne yllä olevien ohjeiden mukaisesti.

## Pull request -prosessi

1. Forkkaa repo ja luo feature-branch
2. Tee muutokset ja kirjoita testit
3. Varmista: `pytest && ruff check src/ tests/ && mypy src/`
4. Avaa PR kuvaavalla otsikolla
5. Rikastukset: liitä `contributions/`-kansioon exportattu JSON

## Lisenssi

Osallistumalla hyväksyt, että kontribuutiosi julkaistaan [MIT-lisenssillä](LICENSE).
