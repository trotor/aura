# Aura — Kehitysohjeet

## Python ja virtuaaliympäristö

**Käytä AINA virtuaaliympäristöä (venv) kaikkiin Python-operaatioihin.**

```bash
# Aktivoi venv ennen mitä tahansa Python-komentoa
source .venv/bin/activate

# Asenna riippuvuudet venviin
pip install -e ".[dev]"

# Aja skriptit aina venvin kautta
python -m aura.cli harvest
pytest tests/
```

Älä koskaan asenna paketteja globaalisti. Venv-hakemisto `.venv/` on .gitignorettu.

## Projektikäytännöt

- Kieli: Python 3.11+
- Tietokanta: SQLite (data/aura.db) — osa git-repoa
- MCP-server: FastMCP 3.x
- Testit: pytest
- Lintteri: ruff
- Tyypintarkistus: mypy (strict)

## Harvester-arkkitehtuuri

Periytymishierarkia:

```
BaseHarvester (base.py)
├── CkanHarvester (ckan.py) — paginoitu CKAN API
│   ├── AvoindataHarvester (avoindata.py)
│   ├── HriHarvester (hri.py)
│   ├── SykeHarvester (syke.py)
│   └── LukeOpendataHarvester (luke_opendata.py)
├── PxWebHarvester (pxweb.py) — rekursiivinen puunavigaatio
│   ├── StatfinHarvester (statfin.py)
│   └── LukeHarvester (luke.py)
├── StaticHarvester (static.py) — konfiguraatiopohjainen, ei API-kutsuja
│   ├── GtkHarvester (gtk.py)
│   ├── KunnatHarvester (kunnat.py) — 36 kunnan WMS/WFS/ArcGIS
│   ├── LipasHarvester (lipas.py) — Jyväskylän yliopisto liikuntapaikat
│   ├── LukeKarttaHarvester (luke_kartta.py)
│   ├── MetsakeskusHarvester (metsakeskus.py)
│   ├── MmlHarvester (mml.py) — Maanmittauslaitos
│   ├── OvertureHarvester (overture.py)
│   ├── PaituliHarvester (paituli.py) — CSC:n paikkatietopalvelu
│   ├── RuokavirastoHarvester (ruokavirasto.py)
│   ├── StatfinGeoHarvester (statfin_geo.py)
│   ├── StukHarvester (stuk.py) — Säteilyturvakeskus
│   ├── TaustakartatHarvester (taustakartat.py)
│   ├── VaalirahoitusHarvester (vaalirahoitus.py)
│   └── VaylaHarvester (vayla.py) — Väylävirasto
├── DigitrafficHarvester (digitraffic.py) — OpenAPI-speksien parsinta
├── FmiHarvester (fmi.py) — WFS stored queries XML
├── KoodistotHarvester (koodistot.py) — Suomi.fi-koodistot
├── SanastotHarvester (sanastot.py) — Suomi.fi-sanastot
├── SotkanetHarvester (sotkanet.py) — THL Sotkanet REST API
├── TraficomHarvester (traficom.py) — OData v4
└── ValtiokonttoriHarvester (valtiokonttori.py) — Valtiokonttorin tuottavuusdata
```

### Uuden harvesterin lisääminen

**Staattinen lähde (ei API-kutsuja):**
1. Luo tiedosto `src/aura/harvesters/<nimi>.py`
2. Peri `StaticHarvester` ja määrittele `datasets_config`-lista
3. Rekisteröi `harvesters/__init__.py`:n `HARVESTERS`-dictiin
4. Kirjoita testit `tests/test_<nimi>.py`

**Dynaaminen lähde (API-kutsut):**
1. Luo tiedosto `src/aura/harvesters/<nimi>.py`
2. Peri `BaseHarvester` (tai `CkanHarvester`/`PxWebHarvester` jos sama API-tyyppi)
3. Määrittele `name`, `description`, `url` ja toteuta `harvest() -> int`
4. Käytä `self._make_dataset(...)` Dataset-olioiden luontiin (asettaa oletusarvot)
5. Rekisteröi `harvesters/__init__.py`:n `HARVESTERS`-dictiin
6. Kirjoita testit `tests/test_<nimi>.py`

### `_make_dataset()` -apumetodi

`BaseHarvester._make_dataset(**kwargs)` luo Dataset-olion näillä oletusarvoilla:
- `license_id="cc-by-4.0"`, `license_title="CC BY 4.0"`
- `collection_type="Open Data"`, `geographical_coverage=["Suomi"]`
- `source=self.name`

Ohita oletusarvot antamalla ne kwargs:ssa.

## MCP-työkalut

**Haku ja selaus:**

| Työkalu | Kuvaus |
|---------|--------|
| `search(query, ...)` | Hae datasettejä suodattimilla (source, format, organization, region) |
| `search_structured(query, ...)` | Hae JSON-muodossa agenteille |
| `search_by_region(region, query)` | Hae alueellisesti (kunta, maakunta, postinumero) |
| `describe(dataset_id)` | Datasetin yksityiskohtaiset tiedot |
| `query_data(dataset_id, ...)` | Esikatsele datasetin sisältöä (CSV, JSON, PxWeb, WFS, OData) |
| `recommend(topic, limit)` | Suosittele parhaita datasettejä aiheesta |
| `compare(dataset_ids)` | Vertaile datasettejä rinnakkain (2–5 kpl) |
| `find_related(dataset_id, limit)` | Etsi samankaltaiset datasetit |

**Alueanalyysi:**

| Työkalu | Kuvaus |
|---------|--------|
| `area_profile(region)` | Alueprofiili: datasetit, laatu, puutteet |
| `compare_municipalities(municipalities, theme)` | Vertaile kuntien datatarjontaa rinnakkain (2–5 kpl) |

**Laatu:**

| Työkalu | Kuvaus |
|---------|--------|
| `quality_report(dataset_id)` | Datasetin laatupisteet dimensioittain |
| `quality_overview(source, min_score)` | Yhteenveto laatupisteistä |
| `quality_ranking(dimension, source, limit)` | Parhaiten pisteytetyt datasetit |
| `quality_gaps(source, limit)` | Metatiedon puutteet ja parannusehdotukset |

**Rikastus ja tutkimus:**

| Työkalu | Kuvaus |
|---------|--------|
| `enrich(dataset_id, field, value, ...)` | Rikasta datasetin tietoja |
| `batch_enrich(enrichments)` | Tallenna useita rikastuksia kerralla |
| `get_enrichments_tool(dataset_id)` | Näytä datasetin rikastukset |
| `suggest_yso_tags(dataset_id, save)` | Ehdota YSO-ontologian avainsanoja |
| `log_finding(dataset_id, finding, category)` | Kirjaa löydös tutkimuksen aikana |
| `list_findings()` | Näytä session löydökset |
| `save_session_findings()` | Tallenna löydökset enrichmenteiksi |

**Viiteaineistot:**

| Työkalu | Kuvaus |
|---------|--------|
| `lookup_municipality(query)` | Hae kuntatiedot nimellä, koodilla tai postinumerolla |
| `reference_status()` | Viiteaineistojen tila |
| `populate_reference(source)` | Lataa viiteaineistot kantaan |

**Terveystarkastus:**

| Työkalu | Kuvaus |
|---------|--------|
| `health_check(source, limit)` | Tarkista resurssien saatavuus (HTTP) |
| `health_report(source)` | Saatavuusraportti aiempien tarkistusten perusteella |

**Hallinta:**

| Työkalu | Kuvaus |
|---------|--------|
| `stats()` | Tilastot: datasetit, organisaatiot, formaatit |
| `list_organizations(limit)` | Julkaisijat datasettien mukaan |
| `list_formats(limit)` | Dataformaatit resurssien mukaan |
| `harvest(source)` | Hae metatiedot lähteistä (päivittää sources-taulun) |
| `list_sources()` | Datalähteet ja harvestoinnin tila (lukee sources-taulusta) |
| `probe_sizes(source)` | Mittaa paikkatietoaineistojen koot |

## Rajausaineistot ja karttalehtijako

Paikallisina rajausaineistoina käytetään GeoPackage-tiedostoja `data/boundaries/`-kansiossa (gitignore). Aineistot ladataan MML:stä — katso README:n ohjeet.

### Karttalehtijako (`data/boundaries/karttalehtijako.gpkg`)

MML:n TM35-karttalehtijako on hierarkkinen ruutujako EPSG:3067-koordinaatistossa. GeoPackage sisältää tasot `utm200`...`utm5` + `utm1`. Jokaisessa ruudussa on `lehtitunnus` (esim. "L4133A") ja `geometry` (polygoni).

**Käyttö aluerajauksissa:** Kun haet dataa WFS/WCS/OGC-rajapinnoista tietylle alueelle, käytä karttalehtitunnusta tai karttalehdeltä saatavaa bbox:ia aluerajauksena:

```python
import sqlite3

gpkg = sqlite3.connect("data/boundaries/karttalehtijako.gpkg")

# Hae karttalehdeltä bbox WFS-kyselyä varten
row = gpkg.execute("""
    SELECT MbrMinX(geometry) as minx, MbrMinY(geometry) as miny,
           MbrMaxX(geometry) as maxx, MbrMaxY(geometry) as maxy
    FROM utm25 WHERE lehtitunnus = 'L4133'
""").fetchone()
bbox = f"{row[0]},{row[1]},{row[2]},{row[3]},EPSG:3067"

# Etsi mitkä karttalehdet osuvat tietylle alueelle
sheets = gpkg.execute("""
    SELECT lehtitunnus FROM utm50
    WHERE MbrMinX(geometry) < 400000 AND MbrMaxX(geometry) > 350000
      AND MbrMinY(geometry) < 6700000 AND MbrMaxY(geometry) > 6650000
""").fetchall()
```

**Hierarkianavigointi:** Karttalehtitunnus on hierarkkinen — `L413` sisältää lehdet `L4131`–`L4134`, jotka sisältävät `L4131A`–`L4134H` jne. Voit rajata alatason lehtiä tunnus-prefiksillä:

```python
# Kaikki 1:10000-lehdet karttalehdeltä L413 (1:50000)
sheets = gpkg.execute(
    "SELECT lehtitunnus FROM utm10 WHERE lehtitunnus LIKE 'L413%'"
).fetchall()
```

**Mittakaavavalinta:** Valitse taso datakutsun koon mukaan:
- `utm200` (65 ruutua) — koko Suomen kattava yleiskatsaus
- `utm50` (832) — maakuntatasoiset haut, WFS-kyselyt isolla alueella
- `utm25` (3 328) — kaupunkitasoiset haut
- `utm10` (26 624) — yksityiskohtaiset paikkatietohaut

### Kuntajako (`data/boundaries/kuntajako_1000k.gpkg` ja `kuntajako_10k.gpkg`)

MML:n hallinnolliset aluejaot sisältävät Suomen hallinnolliset rajat. Kaksi mittakaavaa: 1:1M (928 KB, yleiskäyttö) ja 1:10k (35 MB, tarkka). Molemmat sisältävät 4 tasoa:

| Taso | Sisältö | Attribuutit |
|------|---------|-------------|
| `Kunta` (308) | Kunnat | `natcode` (kuntanumero), `namefin`, `nameswe`, `landarea`, `totalarea` |
| `Maakunta` (19) | Maakunnat | `natcode` (maakuntakoodi), `namefin`, `nameswe` |
| `Hyvinvointialue` (23) | Hyvinvointialueet | `natcode`, `namefin`, `nameswe` |
| `Valtakunta` (1) | Suomen raja | `natcode`, `namefin`, `nameswe` |

**Käyttö aluerajauksissa:**

```python
import sqlite3

kj = sqlite3.connect("data/boundaries/kuntajako_1000k.gpkg")

# Hae kunnan bbox WFS-kyselyä varten
row = kj.execute("""
    SELECT MbrMinX(multipolygon) as minx, MbrMinY(multipolygon) as miny,
           MbrMaxX(multipolygon) as maxx, MbrMaxY(multipolygon) as maxy
    FROM Kunta WHERE namefin = 'Helsinki'
""").fetchone()
bbox = f"{row[0]},{row[1]},{row[2]},{row[3]},EPSG:3067"

# Listaa maakunnan kunnat
kunnat = kj.execute("""
    SELECT k.natcode, k.namefin FROM Kunta k, Maakunta m
    WHERE m.namefin = 'Uusimaa'
      AND ST_Within(ST_Centroid(k.multipolygon), m.multipolygon)
""").fetchall()
# Huom: SpatiaLite-funktiot vaativat mod_spatialite-laajennuksen.
# Ilman sitä käytä bbox-vertailua:
kunnat = kj.execute("""
    SELECT k.natcode, k.namefin FROM Kunta k, Maakunta m
    WHERE m.namefin = 'Uusimaa'
      AND MbrMinX(k.multipolygon) > MbrMinX(m.multipolygon)
      AND MbrMaxX(k.multipolygon) < MbrMaxX(m.multipolygon)
      AND MbrMinY(k.multipolygon) > MbrMinY(m.multipolygon)
      AND MbrMaxY(k.multipolygon) < MbrMaxY(m.multipolygon)
""").fetchall()
```

## MCP-testaus Claude Codella

Projektin `.mcp.json` konfiguroi MCP-palvelimen automaattisesti:

```json
{
  "mcpServers": {
    "aura": {
      "command": ".venv/bin/python",
      "args": ["-m", "aura.cli", "serve"]
    }
  }
}
```

## Commit-käytännöt

Conventional Commits: `feat:`, `fix:`, `data:`, `docs:`, `refactor:`, `test:`, `chore:`, `release:`
