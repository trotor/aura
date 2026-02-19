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
# Kloonaa ja asenna
git clone https://github.com/trotor/aura.git
cd aura
pip install -e ".[dev]"

# Hae datasettien metatiedot avoindata.fi:stä
aura harvest

# Käynnistä MCP-server
aura serve
```

## Projektirakenne

```
aura/
├── src/aura/           # Pääpaketti
│   ├── __init__.py     # Versio ja paketin metadata
│   ├── server.py       # MCP-server (FastMCP)
│   ├── harvester.py    # Datan keräys avoindata.fi:stä
│   ├── database.py     # SQLite-tietokantakerros
│   ├── models.py       # Tietomallit
│   └── search.py       # Hakutoiminnot (FTS5)
├── data/               # SQLite-tietokanta (osa repoa)
│   └── aura.db         # Metadatatietokanta
├── tests/              # Testit
├── scripts/            # Apuskriptit
├── docs/               # Dokumentaatio
├── pyproject.toml      # Projektikonfiguraatio
├── CHANGELOG.md        # Versiohistoria
├── VERSIONING.md       # Versiointiohjeet
└── LICENSE             # MIT-lisenssi
```

## Tietokanta

Aura käyttää **SQLite:ä** paikallisena tietokantana. Tietokanta on osa git-repositoriota, koska se sisältää projektin ydindatan — aggregoidun metadatan suomalaisista avoimista dataseteistä.

SQLite valittiin koska:
- **FTS5-täystekstihaku** mahdollistaa luonnollisen kielen haut suoraan tietokannasta
- **Yksi tiedosto** — helppo jakaa ja versionhallita
- **Nolla riippuvuutta** — Python tukee SQLite:ä natiivisti
- **Riittävä suorituskyky** — ~2 500 datasetin metadatalle enemmän kuin tarpeeksi

## Datalähteet

| Lähde | Tyyppi | Status |
|-------|--------|--------|
| [avoindata.fi](https://avoindata.suomi.fi) | CKAN API + DCAT | MVP |
| Helsinki Region Infoshare (HRI) | CKAN API | Suunniteltu |
| Tilastokeskus (StatFin) | PxWeb API | Suunniteltu |
| Maanmittauslaitos | OGC/WFS | Suunniteltu |

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
# Asenna kehitysriippuvuudet
pip install -e ".[dev]"

# Aja testit
pytest

# Aja lintteri
ruff check src/

# Aja tyypintarkistus
mypy src/
```

## Versiointi

Aura noudattaa [Semantic Versioning 2.0.0](https://semver.org/) -käytäntöä. Katso [VERSIONING.md](VERSIONING.md) tarkemmat ohjeet.

## Lisenssi

[MIT](LICENSE)

## Tekijät

Aura on avoimen lähdekoodin projekti. Tervetuloa mukaan!
