# Probe-vaihe: skeema johdetaan rajapinnasta, ei metatiedosta

**Päivä:** 2026-08-19
**Tila:** suunniteltu
**Lähtökohta:** agenttiasiakkaan palaute (P1)

## Ongelma

Agentti näkee otsikon ja kuvauksen; se ei näe sarakkeita, koordinaatistoa,
avainkenttiä eikä sitä miten rajapintaa kutsutaan. Nämä ovat konekielisesti
johdettavissa itse rajapinnasta.

Palaute sanoi että kentät puuttuvat. Mitattuna tilanne on kolmijakoinen, ja vain
yksi kolmasosa on aito aukko:

| protokolla | tila | missä |
|---|---|---|
| CSV, JSON | **kaapataan, mutta lähes ajamatta** — 54 datasettiä 12 918:sta | `resource_schema`-taulu |
| PxWeb | **kaapataan kattavasti** harvestoinnissa (statfin 99,9 %, luke 100 %) | `data_fields`-enrichment |
| **WFS, WMS** | **ei kaapata missään** — 1 100 + 1 671 datasettiä | — |

Raportoija törmäsi juuri kolmanteen riviin: GTK:n aineistot ovat WFS:ää.

### Miksi CSV/JSON on kaapattu mutta ajamatta

`aura infer-schemas` (`cli.py:1026`) hakee datasetit joilla on CSV/JSON-resurssi
mutta ei skeemaa, lataa esikatselun ja tallentaa kentät. Se on jo probe-vaihe.
Sen puutteet ovat ne, jotka pitävät kattavuuden 54:ssä:

| ominaisuus | tila |
|---|---|
| CSV, JSON | on |
| WFS, WMS, PxWeb | **puuttuu** |
| jatkaminen (puuttuvat ensin) | on |
| TTL / uudelleenprobe | **puuttuu** — kerran tehty, ei koskaan uudelleen |
| epäonnistumisen kirjaus | **puuttuu** — virhe tulostetaan ja katoaa |
| tahdinsäätö per isäntä | **puuttuu** — kiinteä globaali viive |
| `auth_method`, esimerkkikutsu | **puuttuu** |

Logiikka asuu CLI-tiedostossa sadan rivin funktiona, mikä on myös syy siihen ettei
sitä voi kutsua MCP:stä eikä testata ilman CLI:tä.

## Rajaus

Mukana: WFS, WMS, PxWeb, CSV, JSON, `auth_method`, `example_request`,
`joinable_keys`.

**`use_case` ei ole probe-kenttä eikä siitä tule sellaista.** Se on ainoa
puuttuvista kentistä joka ei ole johdettavissa lähteestä, ja generoitu sisältö
muuttuu katalogissa faktaksi seuraavalle lukijalle. AI-tuotettu sisältö siirtyy
kenttään `use_case_suggested`, jolloin kentän **nimi** kertoo mistä on kyse —
provenienssimetatieto ei näy lukijalle samalla tavalla. Rivejä ei poisteta.

## Arkkitehtuuri

**Ei uutta komentoa vaan olemassa olevan laajennus.** `infer-schemas` tekee jo
oikeaa asiaa väärässä paikassa ja liian kapeasti. Logiikka siirtyy CLI:stä omaan
pakettiin, jolloin siihen voi lisätä protokollat, TTL:n ja kirjanpidon — ja
jolloin sen voi kutsua myös MCP:stä ja testata ilman CLI:tä.

```
src/aura/probe/
├── __init__.py      orkestrointi: kohteet, TTL, tahdinsäätö, jatkaminen
├── types.py         ProbeResult, ProbeStatus
├── wfs.py           GetCapabilities + DescribeFeatureType
├── wms.py           GetCapabilities
├── pxweb.py         taulun metadata
├── tabular.py       CSV ja JSON (nykyinen esikatselupolku)
└── derive.py        auth_method ja example_request muiden tuloksesta
```

Kukin prober on funktio `async probe(resource) -> ProbeResult`. Se ei kirjoita
kantaan eikä tiedä orkestroinnista; sen ainoa riippuvuus on HTTP-vastaus. Siksi
jokainen on testattavissa tallennetulla vastauksella ilman verkkoa.

Vaihtoehdot, jotka hylättiin:

- **Harvesterit saisivat `probe()`-metodin.** Probe on protokollakohtainen, ei
  lähdekohtainen: sama WFS-logiikka monistuisi 20 harvesteriin.
- **Laajennettaisiin `spatial_probe.py`:tä.** Sen työ on koon arviointi
  otosruuduilla — eri tehtävä. Yhdistäminen tekisi yhdestä moduulista kaksi.

Uudelleenkäytetään: `aura/wfs.py` (kykyjen luku, virheen tunnistus, neuvottelu),
`tools/schema.py` (`infer_type`, `detect_joinable_keys`, `save_schema_from_markdown`),
`tools/preview.py` (`_preview_csv`, `_preview_json`), `health.py` (statuskoodit).

## Tiedon sijainti

**Kolme varastoa kolmelle eri asialle.** Ne eivät ole päällekkäisiä vaan
erimuotoisia, ja niillä on eri kuluttajat. Yhteen pakottaminen rikkoisi
olemassa olevaa toimintaa.

| tieto | varasto | muoto | kuluttaja |
|---|---|---|---|
| sarakkeet (WFS, CSV, JSON) | `resource_schema`-taulu | `field_name`, `field_type`, per **resurssi** | `describe` |
| dimensiot (PxWeb) | `data_fields`-enrichment | `{code, name, value_count, examples}`, per datasetti | `region_levels`, `_preview_pxweb` |
| layerit (WMS) | `service_layers`-enrichment | `[{name, title}]` | `describe` |

Kolme perustetta tälle jaolle:

1. **Granulariteetti.** Sarakkeet kuuluvat resurssille: yhdellä datasetillä voi
   olla monta resurssia eri skeemoilla. `resource_schema` on jo oikeassa
   muodossa, ja `describe` ryhmittelee sen resurssin mukaan.
2. **`data_fields` ei ole vapaa.** `region_levels.py` lukee sen arvoa
   tunnistaakseen kuntadimension, ja se ohjaa hakutuloksen aluelaajennusta.
   Sarakelistan työntäminen samaan kenttään sekoittaisi tuon logiikan.
3. **Layer ei ole skeema.** WMS ei tarjoa sarakkeita lainkaan. Layer-listan
   esittäminen kenttätietona antaisi lukijalle väärän kuvan siitä mitä
   aineistosta saa irti.

Lisäksi probe kirjoittaa enrichmenteinä, `source_type='probe'`: `crs`,
`example_request`, `auth_method`, `auth_registration_url`.

`joinable_keys` syntyy jo `tools/schema.py`:n `detect_joinable_keys`-funktiosta
merkinnällä `confidence='medium'`, `source_detail='Auto-detected from field
names'`. Probe käyttää samaa funktiota ja samaa merkintää; `source_detail`
tarkennetaan muotoon `Auto-detected from field names (heuristic)`, jotta
heuristiikka lukee arvon vierestä eikä vain provenienssikentästä.

**`access_instructions` ei ole oikea kenttä esimerkkikutsulle.** Mitattuna sen
nykyiset 1 292 arvoa ovat ihmisluettavia yhteydenotto-ohjeita — yksi arvo on
kokonaisuudessaan `sijaintipalvelut@stat.fi`. Konekielinen esimerkkikutsu on eri
asia, ja samaan kenttään sekoitettuna kumpikin heikkenee. Siksi probe kirjoittaa
uuteen kenttään `example_request`.

### Kirjanpito

```sql
CREATE TABLE probe_results (
    resource_id TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL,
    probe_type  TEXT NOT NULL,     -- wfs | wms | pxweb | csv | json
    status      TEXT NOT NULL,     -- ok | http_error | timeout | parse_error | empty
    detail      TEXT DEFAULT '',   -- esim. "HTTP 404"
    probed_at   TEXT NOT NULL
);
CREATE INDEX idx_probe_results_probed_at ON probe_results(probed_at);
CREATE INDEX idx_probe_results_dataset ON probe_results(dataset_id);
```

`resource_id` on pääavain: taulu kantaa **viimeisimmän** tilan per resurssi, ei
historiaa. Historia kuuluu enrichmenteihin, joissa se jo on.

Erillinen taulu siksi, että TTL ja jatkaminen vaativat indeksoituja kyselyitä, ja
`enrichments` on versioitu lisäystaulu johon kirjanpito paisuisi.

Tämä taulu on myös se paikka jossa **epäonnistuminen näkyy**. "Ei saatu selville"
on agentille tietoa, ei tyhjä. Nykyinen `infer-schemas` tulostaa virheen ja
unohtaa sen, joten sama rikkinäinen resurssi yritetään uudestaan joka ajolla eikä
kukaan tiedä mikä on rikki.

`probe_results` lisätään `prune.py`:n `RELATED_TABLES`-listaan, jotta kadonneen
datasetin rivit siivoutuvat samalla kuin muutkin.

## Proberit

| prober | kutsut | tuottaa |
|---|---|---|
| `wfs` | GetCapabilities + DescribeFeatureType | `resource_schema`, `crs`, `example_request` |
| `wms` | GetCapabilities | `service_layers`, `crs` |
| `pxweb` | taulun metadata | `data_fields` |
| `tabular` | 1 esikatselupyyntö | `resource_schema` (nykyinen polku) |

**WFS.** DescribeFeatureType antaa tyypitetyt sarakkeet sekä ArcGIS- että
GeoServer-palvelimilla, mutta eri nimiavaruusprefiksillä (`xsd:` / `xs:`), joten
jäsennys tehdään prefiksistä riippumatta — sama `_local()`-apuri kuin
`aura/wfs.py` käyttää. Geometriakentät (`gml:*PropertyType`) merkitään
geometriaksi eikä sarakkeiksi. DefaultCRS luetaan GetCapabilitiesin
FeatureTypestä.

**WMS.** GetCapabilities antaa layerien nimet ja otsikot. Ei sarakkeita.

**PxWeb.** Sama logiikka kuin harvesterissa jo on; probe kattaa ne 119 joita
harvestointi ei tavoita.

**`tabular`** on nykyinen `infer-schemas`-polku siirrettynä: `_preview_csv` tai
`_preview_json`, sitten `save_schema_from_markdown`. Käytös ei muutu — vain
sijainti, TTL ja epäonnistumisen kirjaus.

**`auth_method` ja `auth_registration_url`** johdetaan muiden proberien
vastauskoodeista, ei omalla kutsulla: 200 → `none`, 401 → `apikey`, 403 →
`restricted`, 30x rekisteröintisivulle → `registration`. Oma HEAD-kutsu jokaiselle
resurssille kaksinkertaistaisi liikenteen kertomatta mitään uutta.

**`example_request`** on konkreettinen kutsu, ei sanallinen ohje. WFS:lle se on se
pyyntö joka juuri todistettiin toimivaksi — `aura/wfs.py`:n neuvottelun
sivutuote: kun `fetch_features` on selvittänyt mikä yhdistelmä toimii, se
yhdistelmä *on* ohje.

## Orkestrointi

Kohteiden valinta — probaamattomat ensin, sitten vanhimmat:

```sql
SELECT r.id, r.dataset_id, r.format, r.url
FROM resources r LEFT JOIN probe_results p ON p.resource_id = r.id
WHERE UPPER(r.format) IN ('WFS','WMS','PXWEB','CSV','JSON','GEOJSON')
  AND (p.probed_at IS NULL OR p.probed_at < :vanhentunut)
ORDER BY (p.probed_at IS NULL) DESC, p.probed_at
LIMIT :limit
```

**TTL erottelee pysyvän ja ohimenevän vian:**

| tila | TTL | peruste |
|---|---|---|
| `ok` | 30 vrk | skeema muuttuu harvoin |
| `timeout`, `http_error` 5xx | 7 vrk | palvelu voi palata |
| `http_error` 404/410 | 90 vrk | uudelleenyrittäminen on kohteliaisuusongelma eikä tuota mitään |
| `parse_error`, `empty` | 30 vrk | vika on rakenteessa, ei hetkessä |

**Tahdinsäätö on 2 kutsua sekunnissa per isäntä**, rinnakkaisuus isäntien välillä.
Tämä ei ole arvaus: aura-pron dimensiohaku menetti 3 808 taulua 3 928:sta kun
6-rinnakkainen ajo törmäsi PxWebin 429-rajoitukseen — ja 429 näytti tyhjältä
tulokselta, ei virheeltä. Nykyinen `--delay 0.3` on globaali eikä katso isäntää,
joten se on yhtä aikaa liian hidas monelle palvelimelle ja liian nopea yhdelle.

**Jatkaminen** on kirjoitus per resurssi, commit joka 50. Keskeytys menettää
korkeintaan 50 kohdetta.

## Pinta

```
aura probe [--source X] [--format WFS] [--limit N] [--max-age-days 30] [--dry-run]
```

`infer-schemas` jää aliakseksi, joka tulostaa varoituksen uudesta nimestä. Nimi
`probe-sizes` on jo varattu koon mittaukselle eikä siihen kosketa.

MCP-työkalu `probe_schemas(source, limit)` — sama muoto kuin `probe_sizes`.
Kirjoittavana se rajautuu automaattisesti pois read-only-etäpalvelusta.

**Uutta status-työkalua ei tule.** Epäonnistuminen näkyy siellä missä sitä
katsotaan: `describe(dataset_id)` kertoo kenttätietojen kohdalla `Skeemaa ei saatu
selville: HTTP 404 (2026-08-19)`, ja `stats()` näyttää kokonaiskattavuuden.

## Virheenkäsittely

Neljä epäonnistumistapaa erotellaan, koska ne tarkoittavat eri asioita:

| status | merkitys |
|---|---|
| `http_error` | palvelu vastasi kieltävästi |
| `timeout` | palvelu ei vastannut |
| `parse_error` | vastasi jotain muuta kuin lupasi |
| `empty` | vastasi oikein muttei sisältänyt kenttiä |

Yksikään probe ei epäonnistu hiljaa: jokainen kirjoittaa rivin `probe_results`-tauluun.

## Testaus

Kolme tasoa, kaikki ilman verkkoa:

1. **Proberit** — tallennetuilla oikeilla vastauksilla. `tests/fixtures/wfs_*.xml`
   ovat jo olemassa (GTK:n ArcGIS). Palautteen pyytämä ArcGIS-regressio syntyy
   tästä. Uudet fixturet: WMS GetCapabilities, PxWeb-metadata, CSV-otsikkorivi.
2. **Orkestrointi** — valeprobereilla muistikannassa: kohteiden valinta, TTL-rajat
   tilaa kohden, jatkaminen kesken ajon, tahdinsäätö per isäntä.
3. **Näkyvyys** — `describe` kertoo epäonnistuneesta probesta, `stats` laskee
   kattavuuden.

Onnistumisen mitta: WFS- ja WMS-kohteiden kattavuus nousee nollasta, ja
CSV/JSON-kattavuus 54:stä. Ensimmäinen mittausajo (2026-08-20, kopiolla
tuotantokannasta, 132 resurssia: WFS 52, WMS 30, CSV 30, PXWEB 20) nosti
`resource_schema`-taulun 772 rivistä / 54 datasetista 1777 riviin / 74
datasettiin ja `joinable_keys`-enrichmentit 26:sta 34:ään. Tilajakauma:
ok 67 (51 %), parse_error 45 (34 %), empty 16 (12 %), http_error 4 (3 %) —
formaateittain WFS ok 25/52, WMS ok 18/30, CSV ok 24/30, **PXWEB ok 0/20**.

Ajo ei ollut kitkaton, ja se kuuluu tähän yhtä lailla kuin onnistuminen.
`probe --format WFS` kaatui käsittelemättömään `IntegrityErroriin` kun
resurssin URL:ssa on pilkuilla erotettu lista useampaa feature typeä (esim.
Lounaistiedon `hame_keski_suomi`-aineisto): `_store()`-kutsua ei ollut
suojattu poikkeukselta kuten proberin omaa kutsua, ja koska kaatunut kohde
jäi pysyvästi "probaamattomaksi", pelkkä komennon uudelleenajo jäi jumiin
samaan kohteeseen eikä edennyt. Tässä mitatut luvut on kerätty ohittamalla
tuo yksi kaatava kohde käsin kannasta — vika korjattiin myöhemmin
commitissa `3a65f36` (dedup `parse_feature_types`-funktioon wfs.py:ssä,
`_store()`-kutsu suojattu run_probe():ssa), joten uusi ajo ei enää jää
jumiin tähän kohteeseen.
PXWEB:n 0/20 ei yleisty koko formaattiin: kaikki 20 valikoitunutta kohdetta
osuivat samaan isäntään (stat.hel.fi), jonka harvestoitu resurssi-URL osoittaa
selattavaan HTML-sivuun eikä PxWeb-API:in ("Vastaus ei ole JSONia"); pistokoe
vahvisti että statfin/luke-API:t palauttavat oikeaa JSONia samalla proberilla.
WMS:n 12 epäonnistumisesta 11 on sama yksittäinen URL-vika (`https://…:80/…`
— TLS-skeema HTTP-portissa) yhdellä isännällä. WFS:n 15 "empty"-tapausta ovat
kaikki INSPIRE-yhteensopivia palveluita (Ruokavirasto, FMI:n tallennetut
kyselyt) joiden DescribeFeatureType viittaa skeemaan `xsd:import`/`include`:lla
sen sijaan että määrittelisi kentät paikallisesti — proberi ei seuraa
viittausta, ja "empty" on siksi oikea, ei virheellinen, luokitus. Luku ei siis
tiivisty yhdeksi kattavuusprosentiksi vaan tähän profiiliin.

## Riippuvuudet ja järjestys

Perustuu PR #151:n `aura/wfs.py`-moduuliin (kykyjen luku, virheen tunnistus,
neuvottelu). Se on mergettävä ensin.

Ei riipu P2:sta (laatupisteiden jako), mutta tuottaa sille syötteen: "pystyykö
agentti hakemaan tästä dataa ilman ihmistä" tarvitsee juuri probe-vaiheen
tuloksen — sekä onnistumisen että epäonnistumisen.
