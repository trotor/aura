# Aura

**Suomalaisen avoimen datan discovery- ja ymmärryspalvelu**

> **3 758+ datasettiä** · **8 959+ resurssia** · **200 organisaatiota** · **~1,3 TB** avointa dataa
>
> 9 datalähteestä: avoindata.fi, HRI, Tilastokeskus, LUKE, Digitraffic, Ilmatieteen laitos, GTK, Traficom, Metsäkeskus

Aura kyntää suomalaisen avoimen datan esiin piilostaan ja tekee sen ymmärrettäväksi. Palvelu toimii MCP-serverinä tekoälyille sekä avoimena web-palveluna ihmisille.

> *Aura* — suomen kielen kyntämistä. Aura kyntää datan esiin.

## Mitä Aura tekee?

- **Aggregoi** metadatan 9 suomalaisesta avoimen datan lähteestä
- **Normalisoi** CKAN, PxWeb, OData, WFS ja OpenAPI -formaatit yhtenäiseen muotoon
- **Tekee hakukelpoiseksi** — FTS5-täystekstihaku luonnollisella kielellä
- **Arvioi datakoon** — jokaiselle datasetille arvioitu koko
- **Palvelee tekoälyjä** MCP-serverin kautta (Claude, GPT, jne.)
- **Palvelee ihmisiä** avoimen web-rajapinnan kautta

## Käyttöönotto (tekoälylle)

Jos käytät Claudea tai muuta MCP-yhteensopivaa tekoälyä, lisää Aura MCP-serveriksi:

```json
{
  "mcpServers": {
    "aura": {
      "command": "uv",
      "args": ["--directory", "/polku/aura", "run", "aura", "serve"]
    }
  }
}
```

Tai jos `uv` ei ole käytössä:

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

Tämän jälkeen tekoäly voi käyttää Auran työkaluja suoraan: etsiä datasettejä, kuvata niitä ja listata organisaatioita.

## Pikastartti (ihmiselle)

```bash
# Kloonaa
git clone https://github.com/trotor/aura.git
cd aura

# Luo virtuaaliympäristö ja asenna
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Tietokanta tulee repon mukana valmiina — voit hakea heti:
aura search "väestö helsinki"
aura search "joukkoliikenne"
aura stats

# Päivitä data uusimmaksi:
aura harvest

# Käynnistä MCP-server:
aura serve
```

> **Huom:** Käytä aina virtuaaliympäristöä (venv). Älä asenna globaalisti.

## Datalähteet

Katso täydellinen datasettikatalogi: **[docs/CATALOG.md](docs/CATALOG.md)**
Katso lähteiden tekniset tiedot: **[docs/SOURCES.md](docs/SOURCES.md)**

| Lähde | Tyyppi | Datasettejä | Arvioitu koko |
|-------|--------|-------------|---------------|
| [avoindata.fi](https://avoindata.suomi.fi) | CKAN API | 1 943 | 114 GB |
| [HRI (hri.fi)](https://hri.fi) | CKAN API | 549 | 39 GB |
| [LUKE](https://statdb.luke.fi) | PxWeb API | 495 | 2,3 GB |
| [Tilastokeskus](https://stat.fi) | PxWeb API | 374 | 1,7 GB |
| [Digitraffic](https://www.digitraffic.fi) | REST/OpenAPI | 162 | 1,5 GB |
| [Ilmatieteen laitos](https://www.ilmatieteenlaitos.fi) | WFS 2.0 | 160 | 14 GB |
| [Metsäkeskus](https://avoin.metsakeskus.fi) | WFS/WCS/ZIP | 43 | 1,2 TB |
| [Traficom](https://opendata.traficom.fi) | OData v4 | 32 | 2,5 GB |
| [GTK](https://www.gtk.fi) | ArcGIS WFS/WMS | 5 | 7 GB |
| **Yhteensä** | | **3 763** | **~1,3 TB** |

## MCP-työkalut

Aura tarjoaa tekoälyille seuraavat MCP-työkalut:

| Työkalu | Kuvaus |
|---------|--------|
| `search` | Hae datasettejä luonnollisella kielellä (+ suodattimet: lähde, formaatti, organisaatio) |
| `search_structured` | Hae datasettejä ja palauta rakenteellinen JSON tekoälyagenteille |
| `describe` | Kuvaa yksittäinen datasetti yksityiskohtaisesti |
| `recommend` | Suosittele parhaita datasettejä aiheesta |
| `compare` | Vertaile datasettejä rinnakkain |
| `find_related` | Etsi samankaltaiset datasetit |
| `stats` | Näytä tilastot tietokannasta |
| `list_organizations` | Listaa datan julkaisijat |
| `list_formats` | Listaa saatavilla olevat dataformaatit |
| `harvest` | Hae datasettien metatiedot lähteistä |
| `list_sources` | Listaa datalähteet ja harvestoinnin tila |
| `probe_sizes` | Mittaa paikkatietoaineistojen koot |

## Projektirakenne

```
aura/
├── src/aura/               # Pääpaketti
│   ├── server.py           # MCP-server (FastMCP)
│   ├── database.py         # SQLite + FTS5
│   ├── models.py           # Pydantic-tietomallit
│   ├── search.py           # Hakutoiminnot
│   ├── size_estimator.py   # Datakoon arviointi
│   ├── cli.py              # Komentorivityökalu
│   ├── spatial_probe.py    # Paikkatietojen kokoluotaus
│   └── harvesters/         # Datalähteiden keräimet (9 kpl)
│       ├── base.py         # BaseHarvester + _make_dataset()
│       ├── ckan.py         # CkanHarvester-kantaluokka
│       ├── pxweb.py        # PxWebHarvester-kantaluokka
│       └── ...             # Lähdekohtaiset harvesterit
├── data/aura.db            # SQLite-tietokanta (osa repoa)
├── docs/
│   ├── CATALOG.md          # Kaikki datasetit listattuna
│   └── SOURCES.md          # Lähteiden tekniset tiedot
├── scripts/                # Migraatiot ja apuskriptit
│   └── migrations/         # Tietokantamigraatiot
└── tests/
```

## Tekoälykehittäjille

Projektin `.mcp.json` konfiguroi MCP-palvelimen automaattisesti Claude Codelle. Katso [docs/MCP_SETUP.md](docs/MCP_SETUP.md) lisäohjeet Claude Desktopille ja muille MCP-yhteensopiville työkaluille.

## Tietokanta

SQLite + FTS5 -täystekstihaku. Tietokanta on osa git-repoa — ei tarvitse harvestoida erikseen.

Skeemamuutokset hoidetaan migraatiojärjestelmällä (`scripts/migrations/`). Katso [docs/SOURCES.md](docs/SOURCES.md).

## Kehitys

```bash
# Aktivoi venv (aina ensin!)
source .venv/bin/activate

# Asenna
pip install -e ".[dev]"

# Testit
pytest

# Lintteri
ruff check src/

# Tyypintarkistus
mypy src/
```

## Versiointi

[Semantic Versioning 2.0.0](https://semver.org/) · [VERSIONING.md](VERSIONING.md) · [CHANGELOG.md](CHANGELOG.md)

## Lisenssi

[MIT](LICENSE)
