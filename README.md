# Aura

**Suomalaisen avoimen datan discovery- ja ymmärryspalvelu**

Aura kyntää suomalaisen avoimen datan esiin piilostaan ja tekee sen ymmärrettäväksi. Palvelu toimii MCP-serverinä tekoälyille sekä avoimena web-palveluna ihmisille.

> *Aura* — suomen kielen kyntämistä. Aura kyntää datan esiin.

## Mitä Aura tekee?

- **Aggregoi** Suomessa saatavilla olevan avoimen datan metadatan (aloittaen [avoindata.fi](https://avoindata.suomi.fi):stä)
- **Normalisoi** eri lähteistä tulevat metatiedot yhtenäiseen muotoon
- **Tekee hakukelpoiseksi** — täystekstihaku luonnollisella kielellä
- **Palvelee tekoälyjä** MCP-serverin kautta (Claude, GPT, jne.)
- **Palvelee ihmisiä** avoimen web-rajapinnan kautta

## Pikastartti

```bash
# Kloonaa
git clone https://github.com/trotor/aura.git
cd aura

# Luo virtuaaliympäristö ja asenna
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Hae datasettien metatiedot
aura harvest

# Käynnistä MCP-server
aura serve
```

> **Huom:** Käytä aina virtuaaliympäristöä (venv). Älä asenna globaalisti.

## Projektirakenne

```
aura/
├── src/aura/               # Pääpaketti
│   ├── __init__.py         # Versio ja paketin metadata
│   ├── server.py           # MCP-server (FastMCP)
│   ├── database.py         # SQLite-tietokantakerros
│   ├── models.py           # Tietomallit
│   ├── search.py           # Hakutoiminnot (FTS5)
│   ├── cli.py              # Komentorivityökalu
│   └── harvesters/         # Datalähteiden keräimet
│       ├── __init__.py
│       ├── base.py         # Yhteinen harvester-pohjaluokka
│       └── avoindata.py    # avoindata.fi (CKAN)
├── data/                   # SQLite-tietokanta (osa repoa)
│   └── aura.db
├── tests/                  # Testit
├── scripts/                # SQL-migraatiot
├── docs/                   # Dokumentaatio
│   └── SOURCES.md          # Harvestoidut lähteet ja datasetit
├── pyproject.toml          # Projektikonfiguraatio
├── CHANGELOG.md            # Versiohistoria
├── VERSIONING.md           # Versiointiohjeet
└── LICENSE                 # MIT-lisenssi
```

## Tietokanta

Aura käyttää **SQLite:ä** paikallisena tietokantana. Tietokanta on osa git-repositoriota, koska se sisältää projektin ydindatan — aggregoidun metadatan suomalaisista avoimista dataseteistä.

SQLite valittiin koska:
- **FTS5-täystekstihaku** mahdollistaa luonnollisen kielen haut suoraan tietokannasta
- **Yksi tiedosto** — helppo jakaa ja versionhallita
- **Nolla riippuvuutta** — Python tukee SQLite:ä natiivisti
- **Riittävä suorituskyky** — ~2 500 datasetin metadatalle enemmän kuin tarpeeksi

## Datalähteet

Katso täydellinen lista harvestoiduista lähteistä ja dataseteistä: **[docs/SOURCES.md](docs/SOURCES.md)**

| Lähde | Tyyppi | Status | Datasettejä |
|-------|--------|--------|-------------|
| [avoindata.fi](https://avoindata.suomi.fi) | CKAN API | Harvestoitu | 1 943 |
| [HRI (hri.fi)](https://hri.fi) | CKAN API | Harvestoitu | 549 |
| [Tilastokeskus (StatFin)](https://stat.fi) | PxWeb API | Harvestoitu | 374 |
| [Digitraffic](https://www.digitraffic.fi) | REST/OpenAPI | Harvestoitu | 162 |
| [Ilmatieteen laitos](https://www.ilmatieteenlaitos.fi) | WFS 2.0 | Suunniteltu | ~160 |
| [Maanmittauslaitos](https://www.maanmittauslaitos.fi) | OGC API | Suunniteltu | ~22 |

## MCP-työkalut

Aura tarjoaa tekoälyille seuraavat MCP-työkalut:

| Työkalu | Kuvaus |
|---------|--------|
| `search_datasets` | Hae datasettejä luonnollisella kielellä |
| `describe_dataset` | Kuvaa yksittäinen datasetti ymmärrettävästi |
| `list_organizations` | Listaa datan julkaisijat |
| `list_formats` | Listaa saatavilla olevat dataformaatit |
| `get_dataset_resource` | Hae datasetin yksittäisen resurssin tiedot |

## Kehitys

```bash
# Luo virtuaaliympäristö (vain kerran)
python3 -m venv .venv
source .venv/bin/activate

# Asenna kehitysriippuvuudet
pip install -e ".[dev]"

# Aja testit
pytest

# Aja lintteri
ruff check src/

# Aja tyypintarkistus
mypy src/
```

> **Tärkeää:** Kaikki Python-komennot ajetaan aina venvin sisällä. Aktivoi venv aina uuden terminaali-istunnon alussa: `source .venv/bin/activate`

## Versiointi

Aura noudattaa [Semantic Versioning 2.0.0](https://semver.org/) -käytäntöä. Katso [VERSIONING.md](VERSIONING.md) tarkemmat ohjeet.

## Lisenssi

[MIT](LICENSE)

## Tekijät

Aura on avoimen lähdekoodin projekti. Tervetuloa mukaan!
