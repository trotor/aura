# Changelog

Kaikki merkittävät muutokset dokumentoidaan tähän tiedostoon.

Formaatti perustuu [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) -käytäntöön.

## [Unreleased]

Kolme teemaa: hakupinon perustason korjaus, poliittisen datan lähteet ja
tarjoiltavan palvelun kokoaminen yhdeksi prosessiksi.

Hakupinon vaikutus mitattiin 30 kyselyn setillä: recall@50 0,771 → 0,830,
nDCG@10 0,563 → 0,624, MRR@10 0,767 → 0,818. Korpus kasvoi 11 202 → 12 806
datasettiin. Lisäksi korjattiin 7 544 kuollutta resurssilinkkiä — noin
neljännes koko katalogista.

### Added
- **Traficomin tilastotietokanta** (`traficom-tilastot`): 81 taulua
  liikenteen viranomaistilastoa, jota ei ole StatFinissä — ajokortit,
  ensirekisteröinnit, henkilöliikennetutkimus, ilmailulupakirjat, julkisen
  liikenteen suoritetilasto, katsastuksen vikatilastot, kuljettajantutkinnot,
  taksiliikenteen kustannusindeksi, vesiliikenne ja vesiliikenneonnettomuudet.
  Traficomilla on **kolme** erillistä avoimen datan rajapintaa, ja tämä oli
  ainoa kattamaton: kysymykseen "onko meillä Traficomin data" sai kahdesta
  ensimmäisestä (OData 32/32, avoindata.fi 28/28) täyden vastauksen.
  Standardi PxWeb, joten `PxWebHarvester` riitti sellaisenaan
- **Finavian lentoliikennetilastot** (`finavia`): kahdeksan datasettiä,
  neljätoista Excel-tiedostoa — matkustajat ja rahti lentoasemittain sekä
  Helsinki-Vantaalta, lentojen ja matkustajalentojen määrät, kansainvälinen
  reitti- ja tilausliikenne maittain. Kuukausiversio ja pitkä aikasarja
  (1998–2025 / 2013–2025) ovat saman tilaston kaksi resurssia, eivät kahta
  datasettiä. Suomen lentoliikennetilastot eivät ole avoimen datan
  portaalissa: avoindata.fi tuntee Finavialta nolla datasettiä. Käyttöehtoja
  ei ilmoiteta, joten lisenssikenttä jätetään tyhjäksi
- **Yhdyssanojen pilkkominen** (`aura.decompound`): evaluaation suurin
  yksittäinen hakupuute. Lemmatisointi tuottaa koko yhdyssanan perusmuodon
  (`satotilastot` → `satotilasto`), mutta korpuksessa on osat — kysely
  `maatalouden satotilastot` sai recall 0,00 vaikka Lukella on kuusi
  satoaineistoa. Sanasto rakennetaan korpuksesta itsestään, ei ulkoisesta
  sanakirjasta: sana kelpaa sananrajaksi jos se esiintyy itsenäisenä
  useammassa kuin yhdessä datasetissä. Osat annetaan **vain löysään
  hakuvaiheeseen** ja saman tokenin OR-haaraan, joten ne eivät voi syrjäyttää
  tiukan vaiheen osumia. Mitattu 30 kyselyn setillä: recall@50 0,830 → 0,861,
  nDCG@10 0,624 → 0,628, gap_precision pysyi 1,00
- **Katot työkaluparametreille** (`aura.limits`): hakupinnalla ei ollut
  ylärajaa, joten `search(limit=1000000)` olisi rakentanut vastauksen kaikista
  osumista. `query_data` oli rajattu alusta asti, haku ei. Katot: haku 100,
  listaukset ja raportit 200, vertailu 5 datasettiä. Negatiivinen arvo
  nostetaan minimiin, koska SQLite tulkitsee negatiivisen `LIMIT`in
  rajattomaksi. Katot on kirjattu myös työkalujen kuvauksiin, ja testi lukee
  ne MCP:n työkalulistalta — kuvaus ja toteutus eivät pääse eriytymään
- **Web-UI ja MCP samasta prosessista** (`aura.asgi`): `aura serve --http`
  tarjoilee nyt FastAPIn juuressa ja FastMCP:n polussa `/mcp`. Aiemmin se ajoi
  pelkkää MCP:tä, joten juuri palautti 404 vaikka web-templatet olivat olemassa
  — käyttöliittymä oli ajettavissa vain erillisellä `aura web` -komennolla.
  Yksi portti, yksi prosessi
- **Laskeutumissivu etusivulle**: mitä Aura on, kopioitava MCP-konfiguraatio ja
  ohjeet oman instanssin ajamiseen. Osoite luetaan pyynnöstä, joten se on oikea
  sekä paikallisesti että käänteisproxyn takana
- **Poliittisen datan harvesterit**: eduskunnan avoin data (7 aineistoa,
  16 taulua — äänestykset vuodesta 1996, puheenvuorot, kansanedustajat,
  valtiopäiväasiakirjat), oikeusministeriön vaalitulospalvelu (11 vaalia)
  ja POHTIVAn puolueohjelmat (1 586 ohjelmaa 1880–2025). Ennen tätä haku
  `puolueohjelma` antoi nolla osumaa eikä eduskunnan omaan dataan
  viitannut yksikään resurssi
- Vaalirahoitukseen jälki-ilmoitukset (`E_JI`) neljälle vaalille joilla
  tiedosto on olemassa
- **Remote-instructions ilman local-FS-lupauksia** (#137): read-only-moodissa
  palvelin ohjaa paikkatietotyökaluihin (`municipality_bbox`,
  `find_map_sheets`, `map_sheet`) eikä lupaa pääsyä
  `data/boundaries/*.gpkg`-tiedostoihin, joita kontissa ei ole
- **`AURA_DB`-ympäristömuuttuja** kannan polulle (#149): pakettipolku ei
  kelpaa konttiajossa, jossa kanta elää volumessa. Polku selvitetään
  kutsuhetkellä, joten oletusargumenttiin sitoutuva importtihetki ei
  kaappaa arvoa
- **Suomen lemmatisointi hakuindeksiin** (`aura.lemmatize`): tokenisointi,
  stopsanakarsinta, simplemma-perusmuotoistus ja FTS5-kyselynrakennin.
  Ilman sitä `pyörätiet` ei löytänyt aineistoa `Pyörätie` — FTS5:n
  unicode61 ei osaa suomen taivutusta. Sarake `datasets.lemmas` (migraatio 018)
- `aura lemmatize` -komento perusmuotojen indeksointiin
- **BM25-kenttäpainot ja asteittainen löysennys**: tiukka AND-haku ensin,
  löysennys vasta jos osumia on liian vähän. Aiempi YSO-termien
  OR-räjäytys tuhosi tarkkuuden — `metsänhakkuut Pirkanmaa` palautti
  Tampereen bussipysäkit
- **`aura prune`**: poistaa lähteestä kadonneet datasetit. Oletuksena
  kuiva-ajo. Ikäraja 30 päivää lähteen omasta viimeisimmästä ajosta, jottei
  yksittäinen epäonnistunut harvestointi poista mitään. Kuratoidut
  rikastukset estävät poiston ilman `--force`
- **Määrävertailu harvestointiin**: varoittaa jos lähde tuottaa nollan tai yli
  20 % vähemmän kuin edellisellä ajolla. Harvesterit jotka nappaavat
  fetch-poikkeuksen ja palauttavat tyhjän listan muuttavat ylävirran
  rikkoutumisen hiljaiseksi nollaksi, joka näyttää onnistuneelta ajolta
- **Hakutulosten deduplikointi** (`aura.dedup`): sama taulu esiintyy monella
  tunnisteella (Tilastokeskuksen taulukoodit, katalogien peilaukset).
  Duplikaatteja ei piiloteta vaan niputetaan, ja määrä näytetään
  tuloksessa. Vaikutus: recall@50 +0,015
- **Laatu- ja saatavuussignaalit hakujärjestykseen**: `quality_scores.overall`
  ja `resource_health` säätävät bm25-pistettä ±10 %. Signaalit ovat
  tarkoituksella heikkoja — ne ratkaisevat lähes tasaväkiset eivätkä voi
  nostaa epärelevanttia relevantin ohi. Vaikutus: nDCG@10 +0,019, MRR@10 +0,022
- Yksikkötestit lemmatisoinnille (45), prunelle (25), deduplikoinnille (20),
  rankkaussignaaleille (8) ja harvestointiputkelle (9)

### Changed
- **`fastapi`, `jinja2` ja `uvicorn` ydinriippuvuuksiksi**: `aura serve --http`
  tarjoilee nyt myös web-UI:n, joten ne eivät ole enää valinnaisia.
  `pip install -e .` riittää — aiemmin ne olivat `[web]`-extrassa ja
  dokumentoitu asennusohje olisi tuottanut `ModuleNotFoundError`in. Extra jää
  tyhjänä paikalleen yhteensopivuuden vuoksi
- **Konttiimage 194 MB pienempi**: Dockerfilen viimeinen vaihe oli
  `RUN useradd ... && chown -R app:app /app`, ja rekursiivinen chown kirjoitti
  `/app`:n koko sisällön uudelleen omaan kerrokseensa — 149 MB:n duplikaatti
  kannasta ja riippuvuuksista jokaisessa imagessa. Omistajuus asetetaan nyt
  `COPY --chown`illa ja kanta kopioidaan viimeisenä. Mitattu 848 MB → 654 MB
- **Harvestointi yhdessä paikassa** (`aura.pipeline`): `aura harvest` ja
  `aura refresh` olivat ehtineet eriytyä — määrävertailu oli vain toisessa
  eikä kumpikaan indeksoinut lemmoja. `harvest` on nyt `refresh`in lyhyt muoto
- **Virkistysputkeen kaksi uutta vaihetta**: vanhentuneiden rivien raportti
  (kuiva-ajo) harvestoinnin jälkeen ja lemmaindeksointi pakollisena vaiheena
- Harvestointivaroitukset tulostetaan myös ajon lopuksi, koska pitkän ajon
  alussa tulostettu häviää vieritykseen

### Fixed
- **Taulukkoformaatit puuttuivat koneluettavien listalta**: 402 datasettiä sai
  `format_score` 40/100 samalla kun WMS-kuvapalvelu sai täydet sata, vaikka
  openpyxl lukee XLSX:n ja OOXML on ISO/IEC 29500 -standardi. Lista ohjasi
  myös hakutulosten järjestystä ja alueprofiilin koneluettavuusosuutta.
  Samalla erotettiin kaksi eri kysymystä, jotka olivat olleet yhdessä
  joukossa: *koneluettavuus* (laatu, järjestys) ja *kyseltävyys*
  (`query_data`). XLSX on koneluettava mutta esikatselu ei osaa avata sitä,
  ja ilman erottelua sen lisääminen olisi saanut esikatselun valitsemaan
  XLSX:n silloinkin kun samalla datasetillä on luettava CSV. Ero näkyi jo
  koodissa poikkeuksena `fmt not in ("WMS", "WCS")`. Katalogin
  accessibility-keskiarvo 86,3 → 86,7
- **PxWeb-taulujen verkkosivulinkit olivat 404** kaikilla PxWeb-lähteillä:
  2 195 datasetin HTML-resurssi osoitti sivulle jota ei ole. PxWebin
  selainkäyttöliittymä koodaa kansiopolun kaksoisalaviivoilla, ei
  kauttaviivoilla — API-polku `StatFin/adopt` on selaimessa
  `StatFin/StatFin__adopt`. Vika ei näkynyt missään mittarissa, koska haku ja
  `query_data` käyttävät PXWEB-resurssia; vain ihmiselle tarkoitettu linkki oli
  rikki. Korjattu kantaluokassa ja ajettu statfin (1 532/1 534) ja luke
  (663/663) uudelleen. Kaksi jäljelle jäänyttä ovat Tilastokeskuksen
  lakkauttamia tauluja, jotka `prune` siivoaa
- **`data_fields`-rikastuskenttä oli päätynyt kaatoluokaksi** (migraatio 020):
  1 864 rivistä vain 7 oli aineiston sarakenimiä. Loput olivat
  bbox-koordinaatteja (1 207) ja koordinaatistotunnuksia (650) — jälkimmäisille
  oli jo oma `crs`-kenttänsä, eli sama tieto oli kahdessa paikassa eri nimellä.
  bbox sai oman kenttänsä, koordinaatistot siirtyivät `crs`:ään (93 täsmällistä
  duplikaattia poistettiin). Nämä rivit eivät olleet hakupolussa —
  `enrichments_fts` indeksoi vain neljä kenttää — mutta `describe()` ja
  `get_enrichments_tool()` esittivät agentille bbox-koordinaatteja otsikolla
  "data_fields"
- **Tarjoiltava kanta jäi WAL-tilaan**: repon kanta on WAL, mikä on oikein
  kehityksessä missä harvestointi kirjoittaa, mutta imagessa kirjoittajaa ei
  ole. WAL-kanta ei aukea edes lukutilassa tiedostojärjestelmästä johon ei voi
  kirjoittaa, ja WAL-tilassa SQLite loi `-shm`- ja `-wal`-tiedostot kontin
  kirjoituskerrokseen. Kanta käännetään nyt buildissa `journal_mode=DELETE`:ksi;
  kontti toimii tämän jälkeen myös täysin kirjoitussuojatulla
  tiedostojärjestelmällä (`--read-only`)
- **Sotkanetin data-URLit olivat kuolleita linkkejä**: kaikki 3 772 CSV- ja
  3 772 JSON-resurssia osoittivat muotoon `/rest/1.1/csv?indicator=N`, joka
  palauttaa HTTP 400 — noin neljännes koko katalogin resursseista. Rajapinta
  vaatii sekä `years` että `genders`; URLit rakennetaan nyt indikaattorin omasta
  vuosivälistä, joka oli jo haettuna mutta käytettiin vain aikakattavuuden
  näyttämiseen. `health_check` ei ollut näitä tavoittanut
- **Laskeutumissivun MCP-osoite käänteisproxyn takana**: `request.base_url`
  kertoo skeeman jolla pyyntö saapui sovellukseen, eli proxyn takana aina
  `http`. Kopioitu konfiguraatio olisi vienyt asiakkaan uudelleenohjauksen
  taakse. Luetaan nyt `X-Forwarded-Proto` sovelluksessa, jolloin se ei riipu
  uvicornin `--forwarded-allow-ips` -asetuksesta ja on yksikkötestattavissa
- **Eduskunnan koonmittaus latasi satoja megatavuja turhaan**: bisektointi haki
  100 rivin sivuja pelkkään kysymykseen "onko sivulla rivejä", ja VaskiDatan
  rivit ovat kokonaisia XML-asiakirjoja (3,4 MB ja 5,6 s per pyyntö).
  Koetin käyttää nyt pienintä mahdollista sivua; ajo lyheni yli puolesta
  tunnista 2,5 minuuttiin. Bisektoinnin kattoon osunut mittaus kirjataan
  muodossa "yli N riviä" eikä uskottavan näköisenä tasalukuna
- **`enrichments_fts`-poistotriggeri** (migraatio 019): taulu on tavallinen
  FTS5-taulu, mutta triggeri käytti ulkoisen sisällön tauluille tarkoitettua
  `'delete'`-erikoiskomentoa. Minkä tahansa rikastuksen poisto epäonnistui,
  jos sen kenttä oli `keywords`, `tags`, `description_extended` tai
  `yso_concepts` — mikä esti myös `aura prune-enrichments` -komennon
- **Valtiokonttorin harvesteri**: Azure APIM siirsi taustarajapinnan pois
  portaalidomainilta ja API-tunnisteet muuttuivat. Osoite luetaan nyt
  portaalin `/config.json`:sta ajonaikaisesti (0 → 48 datasettiä)
- Tuoreustestit eivät enää riipu ajopäivästä (#147)
- mypy strict: `quality.py`:n float/int-virheet (#148)

### Data
- **Korpus siivottu: 12 819 → 11 202 datasettiä.** Poistetuista 1 593 oli
  Tilastokeskuksen vanhoja duplikaattitunnisteita, joiden osoitteet vastaavat
  HTTP 400:lla — Tilastokeskus vaihtoi PxWeb-taulujen tunniste- ja
  osoiteskeeman kesken vuoden. Loput 24 ovat lähteistä oikeasti poistuneita
- Harvestointi 26.7.2026 kaikista lähteistä staattiset mukaan lukien
- Korpus 11 202 → 12 806 datasettiä: kolme uutta poliittisen datan lähdettä
  (eduskunta 7, tulospalvelu 11, POHTIVA 1 586) ja vaalirahoitukseen neljä
  jälki-ilmoitusresurssia

## [0.3.1] - 2026-03-06

### Added
- Lajitietokeskus-harvesteri (lajihavaintoaineistot)
- What's New -sivu (`docs/WHATSNEW.md`)

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
