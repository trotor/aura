[Takaisin etusivulle](./)

# Auran liittäminen tekoälytyökaluihin

Aura on MCP-palvelin (Model Context Protocol), joka antaa tekoälyn hakea, ymmärtää ja rikastaa suomalaisia avoimia datasettejä.

Liittää voi kahdella tavalla:

| | **Julkinen instanssi** | **Oma asennus** |
|---|---|---|
| Vaatii | ei mitään | repon kloonaus + venv |
| Aineisto | ylläpidetty, ~12 900 datasettiä | oma, päivitettävissä `aura harvest` |
| Työkalut | haku ja tutkiminen | kaikki, myös kirjoittavat |
| Rikastukset | eivät tallennu | tallentuvat omaan kantaan |

**Aloita julkisesta instanssista.** Siirry omaan asennukseen jos tarvitset kirjoittavia työkaluja, oman aineistovalikoiman tai haluat kehittää Auraa.

---

# 1. Julkinen instanssi (ei asennusta)

Osoite on `https://aura.futuai.fi/mcp` — streamable HTTP, ei tunnuksia.

## Claude Code

```bash
claude mcp add --transport http aura https://aura.futuai.fi/mcp
```

Tai lisää projektin `.mcp.json`-tiedostoon:

```json
{
  "mcpServers": {
    "aura": {
      "type": "http",
      "url": "https://aura.futuai.fi/mcp"
    }
  }
}
```

Tarkista `/mcp`-komennolla että palvelin näkyy yhdistettynä.

## Claude Desktop

Uusissa versioissa etäpalvelin lisätään käyttöliittymästä: **Settings → Connectors → Add custom connector**, ja osoitteeksi `https://aura.futuai.fi/mcp`.

Jos versiosi ei tarjoa tätä, käytä `mcp-remote`-välityspalvelinta `claude_desktop_config.json`-tiedostossa:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aura": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://aura.futuai.fi/mcp"]
    }
  }
}
```

## Cursor

Lisää `.cursor/mcp.json` projektin juureen tai globaalisti `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "aura": {
      "url": "https://aura.futuai.fi/mcp"
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
      "serverUrl": "https://aura.futuai.fi/mcp"
    }
  }
}
```

## Muu MCP-yhteensopiva työkalu

Aura on standardi MCP-palvelin streamable HTTP -transportilla. Anna asiakkaalle osoite:

```
https://aura.futuai.fi/mcp
```

Yhteyden voi todentaa ilman asiakasta:

```bash
curl https://aura.futuai.fi/health
# {"status":"ok","datasets":12912}
```

## Mitä julkisesta instanssista puuttuu

Instanssi ajetaan **vain luku -tilassa**, joten kantaa muokkaavat työkalut eivät ole käytössä: `enrich`, `batch_enrich`, `save_session_findings`, `suggest_yso_tags`, `harvest`, `populate_reference`, `probe_sizes`, `probe_schemas` ja `health_check`.

Haku, `describe`, `query_data` ja alueanalyysi toimivat normaalisti. `log_finding` ja `list_findings` toimivat session ajan, mutta löydökset eivät tallennu pysyvästi.

Instanssia ylläpidetään erikseen eikä se seuraa tämän repon `main`-haaraa automaattisesti, joten sen aineistomäärä voi poiketa siitä mitä saat ajamalla itse.

---

# 2. Oma asennus

Vaatii repon ja virtuaaliympäristön:

```bash
git clone https://github.com/trotor/aura.git
cd aura
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Tietokanta tulee repon mukana valmiina — harvestointia ei tarvitse ajaa käyttöä varten.

## Claude Code (toimii sellaisenaan)

Repo sisältää `.mcp.json`-tiedoston, joka konfiguroi kaiken automaattisesti:

```bash
cd /polku/aura
claude   # MCP-palvelin käynnistyy automaattisesti
```

Ei tarvitse muokata asetustiedostoja.

## Claude Desktop

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

`.cursor/mcp.json` projektin juureen tai `~/.cursor/mcp.json`:

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

`~/.codeium/windsurf/mcp_config.json`:

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

---

# Työkalut

### Haku ja tutkiminen

| Työkalu | Kuvaus | Esimerkki |
|---------|--------|-----------|
| `search` | Hae datasettejä suodattimilla | `search("väestö", source="hri.fi", format="CSV")` |
| `search_structured` | Hae JSON-muodossa | `search_structured("väestö", limit=5)` |
| `describe` | Datasetin tiedot + rikastukset | `describe("hri-vaestotilasto")` |
| `query_data` | Esikatsele tai kysele datasetin sisältöä | `query_data("ds-1", area="Tampere")` |
| `recommend` | Suosittele datasettejä | `recommend("liikenne Helsinki")` |
| `compare` | Vertaile datasettejä | `compare(["ds-1", "ds-2"])` |
| `find_related` | Samankaltaiset datasetit | `find_related("hri-vaestotilasto")` |

### Rikastaminen (vain oma asennus)

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
| `list_sources` | Lähteiden tila | `list_sources()` |
| `harvest` | Hae metatiedot *(vain oma asennus)* | `harvest("avoindata.fi")` |
| `probe_sizes` | Paikkatietojen koot *(vain oma asennus)* | `probe_sizes("gtk")` |

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

### Julkinen instanssi

**"Palvelin ei vastaa"** — tarkista ensin että endpoint on pystyssä:

```bash
curl https://aura.futuai.fi/health
```

Jos tämä vastaa mutta asiakas ei yhdistä, kyse on lähes aina konfiguraation muodosta: asiakkaat eroavat siinä käyttävätkö ne avainta `url` (Cursor), `serverUrl` (Windsurf) vai erillistä `type: "http"` -kenttää (Claude Code). Tarkista asiakkaan oma dokumentaatio.

**"Työkalua ei löydy"** — kirjoittavat työkalut on poistettu julkisesta instanssista, ks. *Mitä julkisesta instanssista puuttuu*.

### Oma asennus

**"Palvelin ei käynnisty"**

1. Tarkista venv: `ls .venv/bin/python`
2. Asenna riippuvuudet: `source .venv/bin/activate && pip install -e .`
3. Testaa: `source .venv/bin/activate && aura serve`

**"Ei hakutuloksia"** — tietokanta tulee repon mukana valmiina. Jos se on tyhjä, aja harvestointi:

```bash
source .venv/bin/activate
aura harvest
```

**"Polku ei toimi"** — käytä absoluuttista polkua `.venv/bin/python`-tiedostoon asetustiedostoissa.
