# Changelog

Kaikki merkittävät muutokset dokumentoidaan tähän tiedostoon.

Formaatti perustuu [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) -käytäntöön.

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
