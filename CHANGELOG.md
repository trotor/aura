# Changelog

Kaikki merkittävät muutokset dokumentoidaan tähän tiedostoon.

Formaatti perustuu [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) -käytäntöön.

## [0.3.0] - 2026-02-25

### Added
- Schema introspection: `resource_schema`-taulu, kenttänimien ja tyyppien päättely esikatselusta (#115)
- `aura refresh` -komento: harvest + laatupisteet + health check + schema introspection yhdellä komennolla (#123)
- `aura infer-schemas` -komento: batch-skeemapäättely (#124)
- CRS-tieto paikkatietoresursseille — automaattinen EPSG:3067-tunnistus WFS/WMS/GeoJSON-aineistoille (#116)
- Joinable keys -tunnistus: kuntakoodi, postinumero, y-tunnus, maakuntakoodi, ELY-koodi ym. kenttänimistä (#117)
- SPDX-lisenssien normalisointi (cc-by-4.0 → CC-BY-4.0) (#119)
- Auth-vaatimusten tunnistus health check -vastauksista (401/403 → auth_method-enrichment) (#126)
- Laatupisteet automaattisesti harvestin jälkeen (#127)
- Auth-rikastuskentät: `auth_method`, `auth_registration_url`, `auth_notes` (#118)
- `harvested_at` näkyviin describe()- ja search_structured-vastauksissa (#122)
- Rajapinnan versiotiedot (query_protocol, api_base_url) describe-vastaukseen (#120)
- Saatavuustieto (health status) hakutuloksiin (#121)
- Git LFS `data/aura.db`-tiedostolle

### Changed
- CLI harvest päivittää nyt myös sources-taulun (#125)
- Datasetit: 5 800+ → 7 000+, organisaatiot: 250+ → 290+

## [0.2.0] - 2026-02-20

### Added
- Metsäkeskus-harvesteriin spesifiset lataus-URLit aineistopaketeille (ZIP)
- CHM- ja Kemera-datasetteihin ZIP-latausresurssit
- Korjuukelpoisuus-aineisto (download-only, ~130 ZIP-tiedostoa)
- WCS-palveluille HTML-infosivu geneerisen ZIP-linkin sijaan
- Testit Metsäkeskus-harvesterille (10 testiä)

### Changed
- Metsäkeskus: 42 → 43 datasettiä, 53 → 85 resurssia

## [0.1.0] - 2026-02-19

### Added
- Projektin perusrakenne
- README ja dokumentaatio
- pyproject.toml-konfiguraatio
- SQLite-tietokantakerros FTS5-tuella
- Tietomallit avoindata.fi:n dataseteille
- Harvester avoindata.fi:n CKAN API:lle
- MCP-server FastMCP:llä
- Hakutoiminnot luonnollisella kielellä
- Versiointiohjeet (VERSIONING.md)
