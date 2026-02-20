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
│   └── HriHarvester (hri.py)
├── PxWebHarvester (pxweb.py) — rekursiivinen puunavigaatio
│   ├── StatfinHarvester (statfin.py)
│   └── LukeHarvester (luke.py)
├── DigitrafficHarvester (digitraffic.py) — OpenAPI-speksien parsinta
├── FmiHarvester (fmi.py) — WFS stored queries XML
├── GtkHarvester (gtk.py) — staattinen konfiguraatio
├── TraficomHarvester (traficom.py) — OData v4
└── MetsakeskusHarvester (metsakeskus.py) — GeoServer-konfiguraatio
```

### Uuden harvesterin lisääminen

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

| Työkalu | Kuvaus |
|---------|--------|
| `search(query, limit, offset, source, format, organization)` | Hae datasettejä suodattimilla |
| `search_structured(query, limit, offset, source, format, organization)` | Hae JSON-muodossa agenteille |
| `describe(dataset_id)` | Datasetin yksityiskohtaiset tiedot |
| `recommend(topic, limit)` | Suosittele parhaita datasettejä aiheesta |
| `compare(dataset_ids)` | Vertaile datasettejä rinnakkain (2–5 kpl) |
| `find_related(dataset_id, limit)` | Etsi samankaltaiset datasetit |
| `stats()` | Tilastot: datasetit, organisaatiot, formaatit |
| `list_organizations(limit)` | Julkaisijat datasettien mukaan |
| `list_formats(limit)` | Dataformaatit resurssien mukaan |
| `harvest(source)` | Hae metatiedot lähteistä |
| `list_sources()` | Datalähteet ja harvestoinnin tila |
| `probe_sizes(source)` | Mittaa paikkatietoaineistojen koot |

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
