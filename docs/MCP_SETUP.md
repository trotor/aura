# Auran liittäminen tekoälytyökaluihin

Aura on MCP-palvelin (Model Context Protocol), joka antaa tekoälyn hakea, ymmärtää ja rikastaa suomalaisia avoimia datasettejä.

## Claude Code (toimii sellaisenaan)

Auran repo sisältää `.mcp.json`-tiedoston, joka konfiguroi kaiken automaattisesti:

```bash
cd /polku/aura
claude   # MCP-palvelin käynnistyy automaattisesti
```

Ei tarvitse muokata asetustiedostoja. Claude Code tunnistaa `.mcp.json`:n ja käynnistää serverin taustalle.

## Claude Desktop

Lisää `claude_desktop_config.json`-tiedostoon:

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

> Käytä virtuaaliympäristön absoluuttista Python-polkua (`.venv/bin/python`).

## Cursor

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

## Windsurf

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

## Muu MCP-yhteensopiva työkalu

Käynnistyskomento mille tahansa MCP-clientille:

```bash
/polku/aura/.venv/bin/python -m aura.cli serve
```

Tai `uv`:llä:

```bash
uv --directory /polku/aura run aura serve
```

## Työkalut

### Haku ja tutkiminen

| Työkalu | Kuvaus | Esimerkki |
|---------|--------|-----------|
| `search` | Hae datasettejä suodattimilla | `search("väestö", source="hri.fi", format="CSV")` |
| `search_structured` | Hae JSON-muodossa | `search_structured("väestö", limit=5)` |
| `describe` | Datasetin tiedot + rikastukset | `describe("hri-vaestotilasto")` |
| `recommend` | Suosittele datasettejä | `recommend("liikenne Helsinki")` |
| `compare` | Vertaile datasettejä | `compare(["ds-1", "ds-2"])` |
| `find_related` | Samankaltaiset datasetit | `find_related("hri-vaestotilasto")` |

### Rikastaminen

| Työkalu | Kuvaus | Esimerkki |
|---------|--------|-----------|
| `enrich` | Tallenna löydetty tieto | `enrich("ds-1", "keywords", '["sää", "lämpötila"]')` |
| `get_enrichments_tool` | Näytä rikastukset | `get_enrichments_tool("ds-1")` |

### Ylläpito

| Työkalu | Kuvaus | Esimerkki |
|---------|--------|-----------|
| `stats` | Tilastot | `stats()` |
| `list_organizations` | Julkaisijat | `list_organizations(limit=10)` |
| `list_formats` | Formaatit | `list_formats()` |
| `harvest` | Hae metatiedot | `harvest("avoindata.fi")` |
| `list_sources` | Lähteiden tila | `list_sources()` |
| `probe_sizes` | Paikkatietojen koot | `probe_sizes("gtk")` |

## Esimerkkipromptit

### Suomeksi
- "Mitä avoimia datasettejä Helsingin kaupunki tarjoaa?"
- "Etsi ilmanlaatudataa ja kerro mitä formaatteja on saatavilla"
- "Vertaile joukkoliikenteen datasettejä eri lähteistä"
- "Tutki Ruokaviraston peltolohkorekisterin sisältö ja tallenna löydökset"

### In English
- "What open datasets are available about Finnish weather?"
- "Find traffic data APIs and describe their endpoints"
- "Show statistics about the open data catalog"

## Vianmääritys

### "Palvelin ei käynnisty"

1. Tarkista venv: `ls .venv/bin/python`
2. Asenna riippuvuudet: `source .venv/bin/activate && pip install -e .`
3. Testaa: `source .venv/bin/activate && aura serve`

### "Ei hakutuloksia"

Tietokanta tulee repon mukana valmiina. Jos se on tyhjä, aja harvestointi:

```bash
source .venv/bin/activate
aura harvest
```

### "Polku ei toimi"

Käytä absoluuttista polkua `.venv/bin/python`-tiedostoon asetustiedostoissa.
