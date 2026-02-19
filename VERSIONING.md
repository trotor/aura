# Versionhallinta

Aura noudattaa [Semantic Versioning 2.0.0](https://semver.org/) -käytäntöä.

## Versioformaatti

```
MAJOR.MINOR.PATCH
```

| Osa | Milloin kasvaa | Esimerkki |
|-----|---------------|-----------|
| **MAJOR** | Yhteensopimaton API-muutos | 1.0.0 → 2.0.0 |
| **MINOR** | Uusi ominaisuus, taaksepäin yhteensopiva | 1.0.0 → 1.1.0 |
| **PATCH** | Bugikorjaus, taaksepäin yhteensopiva | 1.0.0 → 1.0.1 |

## Versioiden hallinta

### Missä versio määritellään

Versio on yhdessä paikassa: **`pyproject.toml`**

```toml
[project]
version = "0.1.0"
```

Koodi lukee version ajonaikaisesti `importlib.metadata`:lla:

```python
from importlib.metadata import version
__version__ = version("aura")
```

### Version päivitys

1. Päivitä versio `pyproject.toml`:ssa
2. Päivitä `CHANGELOG.md` uuden version muutoksilla
3. Commitoi: `git commit -m "release: v0.2.0"`
4. Luo tag: `git tag v0.2.0`
5. Push: `git push && git push --tags`

### Pre-release versiot

Kehitysversioissa käytetään:
- `0.1.0-alpha.1` — varhainen kehitys
- `0.1.0-beta.1` — testausvaihe
- `0.1.0-rc.1` — julkaisukandidaatti

## Git-käytännöt

### Branch-strategia

```
main            ← stabiili, julkaistu versio
└── dev         ← kehityshaara
    ├── feat/x  ← uusi ominaisuus
    ├── fix/y   ← bugikorjaus
    └── data/z  ← datapäivitys
```

### Commit-viestit

Noudatetaan [Conventional Commits](https://www.conventionalcommits.org/) -käytäntöä:

```
<tyyppi>: <kuvaus>

[valinnainen pidempi kuvaus]
```

| Tyyppi | Käyttö |
|--------|--------|
| `feat` | Uusi ominaisuus |
| `fix` | Bugikorjaus |
| `data` | Tietokantapäivitys (harvest) |
| `docs` | Dokumentaatio |
| `refactor` | Koodin uudelleenjärjestely |
| `test` | Testit |
| `chore` | Ylläpito (riippuvuudet, CI) |
| `release` | Uusi versio |

### Esimerkkejä

```bash
git commit -m "feat: lisää datasettien haku luonnollisella kielellä"
git commit -m "fix: korjaa CKAN API:n sivutuksen käsittely"
git commit -m "data: päivitä avoindata.fi metadata (2026-02-19)"
git commit -m "release: v0.2.0"
```

## Tietokantaversiointi

SQLite-tietokanta (`data/aura.db`) on osa git-repositoriota. Koska kyseessä on binääritiedosto:

1. **Skeemamuutokset** tehdään migraatioilla (`scripts/`-kansiossa)
2. **Datapäivitykset** (harvest) commitoidaan `data:`-tyyppisellä viestillä
3. Tietokanta voidaan aina generoida uudelleen harvesterilla — se on cache, ei lähde

### Migraatiot

Skeemamuutokset numeroidaan:

```
scripts/
├── 001_initial_schema.sql
├── 002_add_fts_index.sql
└── ...
```

## Roadmap

| Versio | Sisältö |
|--------|---------|
| 0.1.0 | MVP: avoindata.fi harvest + SQLite + perus MCP-server |
| 0.2.0 | Täystekstihaku (FTS5) + luonnollisen kielen kyselyt |
| 0.3.0 | Lisää datalähteitä (HRI, Tilastokeskus) |
| 1.0.0 | Stabiili API, tuotantovalmis |
