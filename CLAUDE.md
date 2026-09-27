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
- MCP-server: FastMCP 4.x
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
│   ├── LukeHarvester (luke.py)
│   └── TraficomTilastotHarvester (traficom_tilastot.py) — liikennetilastot
│   (englanninkieliset otsikot haetaan /en/-puusta samalla polulla)
├── StaticHarvester (static.py) — konfiguraatiopohjainen, ei API-kutsuja
│   ├── FinaviaHarvester (finavia.py) — lentoliikennetilastot (XLSX)
│   ├── GtkHarvester (gtk.py)
│   ├── KunnatHarvester (kunnat.py) — 36 kunnan WMS/WFS/ArcGIS
│   ├── LipasHarvester (lipas.py) — Jyväskylän yliopisto liikuntapaikat
│   ├── LukeKarttaHarvester (luke_kartta.py)
│   ├── MetsakeskusHarvester (metsakeskus.py)
│   ├── MmlHarvester (mml.py) — Maanmittauslaitos
│   ├── OvertureHarvester (overture.py)
│   ├── PaituliHarvester (paituli.py) — CSC:n paikkatietopalvelu
│   ├── PrhHarvester (prh.py) — YTJ-koodistot (YTJ-rajapinta ja bulk tulevat avoindata.fi:stä)
│   ├── RuokavirastoHarvester (ruokavirasto.py)
│   ├── StatfinGeoHarvester (statfin_geo.py)
│   ├── StukHarvester (stuk.py) — Säteilyturvakeskus
│   ├── TaustakartatHarvester (taustakartat.py)
│   ├── TulospalveluHarvester (tulospalvelu.py) — oikeusministeriön vaalitulokset
│   ├── VaalirahoitusHarvester (vaalirahoitus.py)
│   └── VaylaHarvester (vayla.py) — Väylävirasto
├── DigitrafficHarvester (digitraffic.py) — OpenAPI-speksien parsinta
├── DigitransitHarvester (digitransit.py) — kansallinen joukkoliikenne (GTFS)
├── EduskuntaHarvester (eduskunta.py) — eduskunnan avoin data
├── FinapHarvester (finap.py) — NAP-liikennepalvelukatalogi
├── FmiHarvester (fmi.py) — WFS stored queries XML
├── KelastoHarvester (kelasto.py) — Kelaston raportit Tietotarjottimen artikkelista
├── KoodistotHarvester (koodistot.py) — Suomi.fi-koodistot
├── PohtivaHarvester (pohtiva.py) — puolueohjelmat (Tietoarkisto)
├── SanastotHarvester (sanastot.py) — Suomi.fi-sanastot
├── SotkanetHarvester (sotkanet.py) — THL Sotkanet REST API
├── TraficomHarvester (traficom.py) — OData v4
├── ValtiokonttoriHarvester (valtiokonttori.py) — Valtiokonttorin tuottavuusdata
└── VipunenHarvester (vipunen.py) — opetushallinnon tilastopalvelu (REST, kenttäskeemat)
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

Kolme profiilia (`AURA_TOOL_PROFILE`): **public** (oletus, datan käyttäjä, `/mcp`), **laatu** (julkaisijat ja ylläpitäjät, vain luku, `/mcp/laatu`) ja **admin** (kaikki). Repon `.mcp.json` käyttää admin-profiilia.

**Julkinen profiili — aikomustason työkalut, strukturoidut vastaukset:**

| Työkalu | Kuvaus |
|---------|--------|
| `find_data(query, region, ...)` | Aineistohaku kaikilla suodattimilla; `indicators`-kenttä jos laajennus tuntee tunnusluvun |
| `inspect_dataset(dataset_id)` | Kuvaus, resurssit, kentät, laatu, saatavuus, resepti (laajennus) |
| `query_source(dataset_id, filters, area, ...)` | Rivit lähteestä: PxWeb, WFS, FMI stored query, OData, CSV, JSON + provenance |
| `area_snapshot(region)` | Alueen tunnistus, hierarkia, tunnukset, datatarjonta; `key_figures` (laajennus) |
| `find_related(dataset_id)` | Samankaltaiset aineistot |

Jokaisella julkisella työkalulla on `outputSchema`, ja `tests/test_surface.py` validoi oikean vastauksen sitä vasten. Uusi julkinen työkalu: `@mcp.tool(tags={"public"}, output_schema=schema_of(Malli))`, palauta `aura.responses.respond(payload, yhteenveto)` ja virheet `fail(...)`:lla. Julkisessa profiilissa enintään 8 työkalua, ohjeteksti alle 1 500 merkkiä.

Laajennuspisteet (`aura.extensions`): `find_data.indicators`, `inspect_dataset.recipe`, `area_snapshot.key_figures` ja `add_instructions()`.

Aluetunnisteet tulkitaan aina `aura.areas.resolve_area()`:lla (nimi fi/sv taivutettuna, kuntakoodi, `KU837`, `MK06`, postinumero, lakkautettu kunta → seuraaja).

**Laatuprofiili** (tagi `quality`, oma palvelin `build_quality_server()`): `quality_summary`, `metadata_gaps`, `availability_report` + `find_data`, `inspect_dataset`, `log_finding`, `list_findings`. Ei kirjoittavia työkaluja eikä `health_check`ia — saatavuus luetaan tallennetuista tarkistuksista (`tests/test_laatu.py`).

**Admin-profiili:** kaikki alla olevat. Korvatut työkalut näkyvät kuvauksella "Vanhentunut: käytä X" (`aura.server.DEPRECATED_TOOLS`) yhden version ajan.

| Työkalu | Kuvaus |
|---------|--------|
| `search`, `search_structured`, `search_by_region`, `recommend` | → `find_data` |
| `describe`, `quality_report`, `get_enrichments_tool` | → `inspect_dataset` |
| `query_data` | → `query_source` |
| `area_profile`, `lookup_municipality`, `compare_municipalities` | → `area_snapshot` |
| `compare(dataset_ids)` | Vertaile datasettejä rinnakkain (2–5 kpl) |
| `suggest_questions(region, theme)` | Esimerkkikysymykset teemoittain ja alueittain |
| `municipality_bbox`, `find_map_sheets`, `map_sheet` | Rajausaineistot (EPSG:3067) |
| `quality_overview`, `quality_ranking`, `quality_gaps` | Laatu |
| `enrich`, `batch_enrich`, `suggest_yso_tags`, `log_finding`, `list_findings`, `save_session_findings` | Rikastus ja tutkimus |
| `reference_status`, `populate_reference` | Viiteaineistot (`areas`, `municipality_changes`, `municipalities`, ...) |
| `health_check`, `health_report` | Saatavuus |
| `stats`, `list_organizations`, `list_formats`, `harvest`, `list_sources`, `probe_sizes`, `probe_schemas` | Hallinta |

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

## Output — analyysien tallennus

Kun sessio tuottaa analyyttistä sisältöä (tilannekuvat, vertailut, selvitykset), tarjoa käyttäjälle tallennusta `output/sessions/`-kansioon. Kansio on gitignoressa eli paikallinen.

Tiedostomuoto: `output/sessions/YYYY-MM-DD-aihe.md` YAML-frontmatterilla:

```yaml
---
date: 2026-03-26
topic: Lyhyt otsikko
sources:
  - käytetyt datalähteet
tags: [aihe1, aihe2]
---
```

## Commit-käytännöt

Conventional Commits: `feat:`, `fix:`, `data:`, `docs:`, `refactor:`, `test:`, `chore:`, `release:`
