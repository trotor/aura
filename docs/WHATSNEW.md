# What's New

Auran muutoshistoria versioittain. Katso myös [Datalähteet](SOURCES.md) ja [Datasettikatalogi](CATALOG.md).

---

## v0.3.1 (2026-03-06)

### Uudet datalähteet

- **Lajitietokeskus (FinBIF)** — Suomen Lajitietokeskuksen 11 tietovarantoa: havaintodata (45M+ havaintoa), taksonomia, kasviatlas, lintuatlas, uhanalaisarviointi, vieraslajiportaali, kokoelmat, paikkatietotuotteet, GBIF-integraatio, REST API ja R-paketti. API-avaintiedot dokumentoitu enrichmenteiksi.
- **SmartSMEAR** — Ilmakehätieteen mittausdata (SMEAR-asemat), HIKET-enrichmentit

### Korjaukset

- Sanastot API: vastausavain muuttui `terminologies` → `responseObjects`

---

## v0.3.0

### Uudet datalähteet

- **THL Sotkanet** — ~3 500 terveys- ja hyvinvointi-indikaattoria
- **Paikkatietoikkuna** — CSW-metadatapalvelun aineistot
- **LUKE opendata** — Luonnonvarakeskuksen CKAN-aineistot
- **LUKE kartta** — Luonnonvarakeskuksen karttapalvelut
- **SmartSMEAR** — Ilmakehämittausdata

### Uudet MCP-työkalut

- `suggest_questions` — ehdottaa esimerkkikysymyksiä teemoittain ja alueittain
- `compare_municipalities` — vertaile kuntien datatarjontaa rinnakkain
- `query_data` — esikatsele datasettien sisältöä (CSV, JSON, PxWeb, WFS, OData)
- `suggest_yso_tags` — ehdota YSO-ontologian avainsanoja datasetiille

### Parannukset

- Laatupisteet lasketaan automaattisesti harvestoinnin jälkeen
- Terveystarkastukset (health check) ja saatavuushistoria
- Skeemapäättely: kenttänimet ja tyypit esikatselusta
- Hakusanojen laajennus YSO-ontologialla ja domain-sanastoilla
- CRS-tieto automaattisesti paikkatietoresursseille
- Git LFS aura.db:lle
- Enrichment-järjestelmä: joukkoistamalla kerätyt rikastukset

---

## v0.2.0

### Uudet datalähteet

- **Kuntien paikkatiedot** — 36 kunnan WMS/WFS/ArcGIS-palvelut
- **STUK** — Säteilyturvakeskuksen valvonta-aineistot
- **LIPAS** — Jyväskylän yliopiston liikuntapaikkarekisteri
- **PaItuli** — CSC:n paikkatietopalvelu
- **Vaalirahoitusvalvonta** — Vaalirahoitusilmoitukset
- **MML** — Maanmittauslaitoksen aineistot
- **Väylävirasto** — Liikenneväylien aineistot
- **Overture Maps** — Overture Maps Foundation

### Uudet MCP-työkalut

- `area_profile` — alueprofiili: datasetit, laatu, puutteet
- `quality_report` / `quality_overview` / `quality_ranking` / `quality_gaps` — laatutyökalut
- `find_related` — samankaltaiset datasetit
- `search_by_region` — alueellinen haku (kunta, maakunta, postinumero)

### Parannukset

- Viiteaineistot: 308 kuntaa ja 3 784 postinumeroa
- Karttalehtijako TM35-ruuduiksi aluerajauksiin
- Web-käyttöliittymä (FastAPI + staattinen sivusto)

---

## v0.1.0

### Ensimmäinen julkaisu

- **Perusarkkitehtuuri:** SQLite + FTS5, MCP-server (FastMCP), CLI
- **Datalähteet:** avoindata.fi, HRI, SYKE, Tilastokeskus (StatFin), LUKE, Digitraffic, FMI, GTK, Traficom, Metsäkeskus, Suomi.fi-koodistot ja -sanastot, Ruokavirasto, Valtiokonttori
- **MCP-työkalut:** search, describe, recommend, compare, stats, list_organizations, list_formats, harvest, list_sources
