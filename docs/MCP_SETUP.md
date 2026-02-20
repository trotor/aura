# Auran liittäminen Claudeen

Aura on MCP-palvelin (Model Context Protocol), joka antaa Claude-tekoälyn hakea ja ymmärtää suomalaisia avoimia datasettejä.

## Claude Code

Claude Code löytää `.mcp.json`-tiedoston automaattisesti projektin juuresta:

```bash
cd /polku/auraan
claude  # MCP-palvelin käynnistyy automaattisesti
```

## Claude Desktop

Lisää `claude_desktop_config.json`-tiedostoon:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aura": {
      "command": "/polku/auraan/.venv/bin/python",
      "args": ["-m", "aura.cli", "serve"]
    }
  }
}
```

**Tärkeää:** Käytä virtuaaliympäristön Python-polkua (`.venv/bin/python`).

## Esimerkkipromptit

### Suomeksi
- "Mitä avoimia datasettejä Helsingin kaupunki tarjoaa?"
- "Etsi ilmanlaatudataa ja kerro mitä formaatteja on saatavilla"
- "Vertaile joukkoliikenteen datasettejä eri lähteistä"
- "Kuinka tuoretta data on? Tarkista harvestoinnin tila."

### In English
- "What open datasets are available about Finnish weather?"
- "Find traffic data APIs and describe their endpoints"
- "Show statistics about the open data catalog"

## Työkalut

| Työkalu | Kuvaus | Esimerkki |
|---------|--------|-----------|
| `search` | Hae datasettejä (suodattimilla) | `search("väestö", source="hri.fi", format="CSV")` |
| `search_structured` | Hae JSON-muodossa | `search_structured("väestö", limit=5)` |
| `describe` | Datasetin tiedot | `describe("hri-vaestotilasto")` |
| `recommend` | Suosittele datasettejä | `recommend("liikenne Helsinki")` |
| `compare` | Vertaile datasettejä | `compare(["ds-1", "ds-2"])` |
| `find_related` | Samankaltaiset datasetit | `find_related("hri-vaestotilasto")` |
| `stats` | Tilastot | `stats()` |
| `list_organizations` | Julkaisijat | `list_organizations(limit=10)` |
| `list_formats` | Formaatit | `list_formats()` |
| `harvest` | Hae metatiedot | `harvest("avoindata.fi")` |
| `list_sources` | Lähteiden tila | `list_sources()` |
| `probe_sizes` | Paikkatietojen koot | `probe_sizes("gtk")` |

## Vianmääritys

### "Palvelin ei käynnisty"

1. Tarkista venv: `ls .venv/bin/python`
2. Asenna riippuvuudet: `source .venv/bin/activate && pip install -e .`
3. Testaa: `source .venv/bin/activate && aura serve`

### "Ei hakutuloksia"

Tietokanta voi olla tyhjä. Aja harvestointi:

```bash
source .venv/bin/activate
aura harvest
```

### "Polku ei toimi"

Käytä absoluuttista polkua `.venv/bin/python`-tiedostoon `claude_desktop_config.json`:ssä.
