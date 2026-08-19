# Probe-vaihe: skeema johdetaan rajapinnasta, ei metatiedosta

**Päivä:** 2026-08-19
**Tila:** suunniteltu
**Lähtökohta:** agenttiasiakkaan palaute (P1), ks. myös #146:n yhteydessä korjatut P0-viat

## Ongelma

Katalogi kertoo mitä aineistoja on, muttei mitä niissä on. Agentti näkee otsikon ja
kuvauksen; se ei näe sarakkeita, koordinaatistoa, avainkenttiä eikä sitä miten
rajapintaa kutsutaan. Nämä ovat konekielisesti johdettavissa itse rajapinnasta.

Mitattu tilanne (2026-08-19, `data/aura.db`, 12 918 datasettiä):

| kenttä | rivejä | provenienssi |
|---|---|---|
| `data_fields` | 2 275 | `harvest` — **vain PxWeb**: statfin 99,9 %, luke 100 %, muut ~0 % |
| `crs` | 2 107 | `harvest` |
| `access_instructions` | 1 292 | `harvest` |
| `joinable_keys` | 26 | `schema_analysis` — `query_data`:n sivutuote |
| `auth_method` | 1 | `health_check` |

Kattavuus ei siis puutu kokonaan vaan on yhden protokollan varassa. PxWeb-harvesteri
kirjoittaa dimensiot enrichmenteiksi; muut protokollat eivät kirjoita mitään.
`tools/schema.py` osaa jo tyyppipäättelyn ja avainheuristiikan, mutta se laukeaa vain
kun ihminen tai agentti sattuu kutsumaan `query_data`:a — 54 datasettiä 12 918:sta.

Kohteita formaatin mukaan, datasetit joilta kenttätieto puuttuu:

| formaatti | kpl | mitä probe saa irti |
|---|---|---|
| CSV | 4 569 | otsikkorivi + tyyppiarvaus |
| WMS | 1 671 | layerien nimet ja otsikot (ei sarakkeita) |
| WFS | 1 100 | sarakkeet, tyypit, DefaultCRS |
| PxWeb | 119 | dimensiot — jäänteet joita harvestointi ei tavoita |

## Rajaus

Mukana: WFS, WMS, PxWeb, CSV, `auth_method`, `example_request`, `joinable_keys`.

Ei mukana: JSON-resurssit (4 581 kpl). Katkaistu JSON ei jäsenny, joten probe
joutuisi lataamaan koko dokumentin tuntemattomasta koosta. Otetaan seuraavalle
kierrokselle, kun mittari on olemassa näyttämään paljonko se lisää.

**`use_case` ei ole probe-kenttä eikä siitä tule sellaista.** Se on ainoa
puuttuvista kentistä joka ei ole johdettavissa lähteestä, ja generoitu sisältö
muuttuu katalogissa faktaksi seuraavalle lukijalle.

## Arkkitehtuuri

Uusi paketti `src/aura/probe/`. Vaihtoehdot, jotka hylättiin:

- **Harvesterit saisivat `probe()`-metodin.** Probe on protokollakohtainen, ei
  lähdekohtainen: sama WFS-logiikka monistuisi 20 harvesteriin.
- **Laajennettaisiin `spatial_probe.py`:tä.** Sen työ on koon arviointi
  otosruuduilla — eri tehtävä. Yhdistäminen tekisi yhdestä moduulista kaksi.

```
src/aura/probe/
├── __init__.py      orkestrointi: kohteet, TTL, tahdinsäätö, jatkaminen
├── types.py         ProbeResult, ProbeStatus
├── wfs.py           GetCapabilities + DescribeFeatureType
├── wms.py           GetCapabilities
├── pxweb.py         taulun metadata
├── csv.py           range-pyyntö
└── derive.py        joinable_keys ja auth_method muiden tuloksesta
```

Kukin prober on funktio `async probe(resource: dict) -> ProbeResult`. Se ei kirjoita
kantaan eikä tiedä orkestroinnista; sen ainoa riippuvuus on HTTP-vastaus. Siksi
jokainen on testattavissa tallennetulla vastauksella ilman verkkoa.

Uudelleenkäytetään: `aura/wfs.py` (kykyjen luku, virheen tunnistus, neuvottelu),
`tools/schema.py` (`infer_type`, `_KEY_PATTERNS`), `tools/preview.py` (CSV:n
erottimen tunnistus), `health.py` (statuskoodien tulkinta).

## Tiedon sijainti

Kaksi eri asiaa, kaksi eri paikkaa.

**Johdettu tieto → `enrichments`, `source_type='probe'`.** Olemassa oleva
provenienssimalli riittää. Probe kirjoittaa: `data_fields`, `joinable_keys`, `crs`,
`example_request`, `auth_method`, `auth_registration_url`. Tämä on sama polku jota
PxWeb-harvesteri jo käyttää, joten `describe`, `search` ja laatupisteet näkevät
tuloksen ilman uutta lukupolkua.

### Arvojen muodot ovat jo päätetty — niitä ei keksitä uudestaan

`data_fields` on JSON-lista, jonka PxWeb-harvesteri kirjoittaa muodossa
`{code, name, value_count, examples}` ja jota `_preview_pxweb` lukee. Sarakkeet
mahtuvat samaan avainjoukkoon, kun lisätään kaksi valinnaista avainta:

```json
[{"name": "OBJECTID", "type": "integer", "kind": "column"},
 {"name": "Onnettomuustyyppi", "code": "onnettomuustyyp_2", "value_count": 12,
  "examples": ["Yhteensä"], "kind": "dimension"}]
```

`kind` on `column` (WFS, CSV), `dimension` (PxWeb) tai `layer` (WMS). Ilman sitä
lukija olettaisi WMS:n layer-listan olevan skeema — WMS ei tarjoa sarakkeita
lainkaan, ja sen tulos on eri laatua kuin muiden.

`joinable_keys` on jo muodossa `[{"field": "Y-tunnus", "key": "y-tunnus",
"standard": "PRH 8-num"}]`, jonka `tools/schema.py` tuottaa. Probe käyttää samaa
funktiota ja samaa muotoa.

**`access_instructions` ei ole oikea kenttä esimerkkikutsulle.** Mitattuna sen
nykyiset 1 292 arvoa ovat ihmisluettavia yhteydenotto-ohjeita — yksi arvo on
kokonaisuudessaan `sijaintipalvelut@stat.fi`. Konekielinen esimerkkikutsu on eri
asia, ja samaan kenttään sekoitettuna kumpikin heikkenee: lukija ei tiedä
kummankaan muotoa etukäteen. Siksi probe kirjoittaa uuteen kenttään
`example_request`.

**Kirjanpito → uusi taulu `probe_results`:**

```sql
CREATE TABLE probe_results (
    resource_id TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL,
    probe_type  TEXT NOT NULL,     -- wfs | wms | pxweb | csv
    status      TEXT NOT NULL,     -- ok | http_error | timeout | parse_error | empty
    detail      TEXT DEFAULT '',   -- esim. "HTTP 404"
    probed_at   TEXT NOT NULL
);
CREATE INDEX idx_probe_results_probed_at ON probe_results(probed_at);
CREATE INDEX idx_probe_results_dataset ON probe_results(dataset_id);
```

`resource_id` on pääavain: taulu kantaa **viimeisimmän** tilan per resurssi, ei
historiaa. Historia kuuluu enrichmenteihin, joissa se jo on; kirjanpidossa vanha
tila ei kerro mitään jota uusi ei kertoisi paremmin.

Erillinen taulu siksi, että TTL ja jatkaminen vaativat indeksoituja kyselyitä
("mitkä ovat vanhentuneet", "mitä ei ole yritetty"), ja `enrichments` on versioitu
lisäystaulu johon kirjanpito paisuisi.

Tämä taulu on myös se paikka jossa **epäonnistuminen näkyy**. "Ei saatu selville" on
agentille tietoa, ei tyhjä.

### Kaksi tarkennusta

`joinable_keys` merkitään heuristiikaksi arvossa itsessään: `confidence='low'`,
`source_detail='column-name-heuristic'`. Pelkkä provenienssi ei riitä, koska lukija
näkee arvon ennen kuin näkee mistä se tuli.

AI-tuotettu käyttötapauskuvaus siirtyy uuteen kenttään `use_case_suggested`.
Kentän **nimi** kertoo mistä on kyse — provenienssimetatieto ei näy lukijalle
samalla tavalla. `use_case` jää ihmisen kirjoittamaksi.

Toteutus: `use_case_suggested` ja `example_request` lisätään
`VALID_ENRICHMENT_FIELDS`-joukkoon, ja skeemamigraatio siirtää nykyiset viisi
`field='use_case' AND source_type='ai_analysis'` -riviä uudelle kentälle. Rivejä ei
poisteta — sisältö säilyy, vain sen nimi muuttuu todeksi.

## Proberit

| prober | kutsut | tuottaa |
|---|---|---|
| `wfs` | GetCapabilities + DescribeFeatureType | `data_fields` (nimi + tyyppi), `crs`, `example_request` |
| `wms` | GetCapabilities | `data_fields` = layerit, `crs` |
| `pxweb` | taulun metadata | `data_fields` = dimensiot ja luokitusarvot |
| `csv` | 1 range-pyyntö (~8 kt) | `data_fields` otsikkorivistä + `infer_type` |

**WFS.** DescribeFeatureType antaa tyypitetyt sarakkeet sekä ArcGIS- että
GeoServer-palvelimilla, mutta eri nimiavaruusprefiksillä (`xsd:` / `xs:`), joten
jäsennys tehdään prefiksistä riippumatta — sama `_local()`-apuri kuin `aura/wfs.py`
käyttää. Geometriakentät (`gml:*PropertyType`) merkitään geometriaksi eikä
sarakkeiksi. DefaultCRS luetaan GetCapabilitiesin FeatureTypestä.

**WMS** ei tarjoa sarakkeita lainkaan. Sen tulos merkitään `kind='layer'`, kuten
arvojen muodoissa on kuvattu.

**CSV.** Range-pyyntö ensimmäisistä ~8 kilotavusta. Erottimen tunnistus on jo
olemassa `preview.py`:ssä. Palvelin joka ei tue range-pyyntöjä palauttaa koko
tiedoston; lukeminen katkaistaan samaan rajaan.

**`auth_method` ja `auth_registration_url`** johdetaan muiden proberien
vastauskoodeista, ei omalla kutsulla: 200 → `none`, 401 → `apikey`, 403 →
`restricted`, 30x rekisteröintisivulle → `registration`. Oma HEAD-kutsu jokaiselle
resurssille kaksinkertaistaisi liikenteen kertomatta mitään uutta.

**`example_request`** on konkreettinen kutsu, ei sanallinen ohje. WFS:lle se on se
pyyntö joka juuri todistettiin toimivaksi —
`aura/wfs.py`:n neuvottelun sivutuote: kun `fetch_features` on selvittänyt mikä
yhdistelmä toimii, se yhdistelmä *on* ohje.

## Orkestrointi

Kohteiden valinta — probaamattomat ensin, sitten vanhimmat:

```sql
SELECT r.id, r.dataset_id, r.format, r.url
FROM resources r LEFT JOIN probe_results p ON p.resource_id = r.id
WHERE UPPER(r.format) IN ('WFS','WMS','PXWEB','CSV')
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
tulokselta, ei virheeltä.

**Jatkaminen** on kirjoitus per resurssi, commit joka 50. Keskeytys menettää
korkeintaan 50 kohdetta.

## Pinta

```
aura probe [--source X] [--format WFS] [--limit N] [--max-age-days 30] [--dry-run]
```

MCP-työkalu `probe_schemas(source, limit)` — sama muoto kuin olemassa olevalla
`probe_sizes`-työkalulla. Kirjoittavana se rajautuu automaattisesti pois
read-only-etäpalvelusta, kuten `harvest`.

**Uutta status-työkalua ei tule.** Epäonnistuminen näkyy siellä missä sitä
katsotaan: `describe(dataset_id)` kertoo `Skeemaa ei saatu selville: HTTP 404
(2026-08-19)`, ja `stats()` näyttää kokonaiskattavuuden. Agentti kohtaa tiedon
samassa kutsussa jossa se muutenkin kysyy datasetistä.

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
   ovat jo olemassa (GTK:n ArcGIS). Palautteen pyytämä ArcGIS-regressio syntyy tästä.
   Uudet fixturet: WMS GetCapabilities, PxWeb-metadata, CSV-otsikkorivi.
2. **Orkestrointi** — valeprobereilla muistikannassa: kohteiden valinta, TTL-rajat
   tilaa kohden, jatkaminen kesken ajon, tahdinsäätö.
3. **Näkyvyys** — `describe` kertoo epäonnistuneesta probesta, `stats` laskee
   kattavuuden.

Onnistumisen mitta: WFS- ja CSV-kohteiden `data_fields`-kattavuus nousee ~0 %:sta,
ja `joinable_keys` 26 rivistä. Tarkka luku mitataan ensimmäisen täyden ajon
jälkeen — se on tulos, ei tavoite jonka voisi asettaa etukäteen.

## Riippuvuudet ja järjestys

Perustuu PR #151:n `aura/wfs.py`-moduuliin (kykyjen luku, virheen tunnistus).
Se on siis mergettävä ensin.

Ei riipu P2:sta (laatupisteiden jako), mutta tuottaa sille syötteen: "pystyykö
agentti hakemaan tästä dataa ilman ihmistä" tarvitsee juuri probe-vaiheen tuloksen.
