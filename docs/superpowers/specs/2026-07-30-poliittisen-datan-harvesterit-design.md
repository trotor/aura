# Poliittisen datan harvesterit

**Päivä:** 2026-07-30
**Tila:** Hyväksytty, odottaa toteutussuunnitelmaa

## Tausta

Aurassa on 290 poliittista aineistoa. Ne kertovat tarkasti kuka valittiin,
millä äänillä ja kenen rahoilla: Statfinin 184 vaalitaulua ehdokastason
äänimäärineen, VTV:n vaali- ja puoluerahoitus 2010–2026, Sotkanetin
äänestysaktiivisuus.

Ne eivät kerro mitään siitä mitä valitut lupasivat tai ovat sen jälkeen
tehneet. Haku `puolueohjelma` antaa nolla osumaa. Eduskunnan omaan avoimeen
dataan ei viittaa yksikään resurssi.

Tämä speksi täyttää aukon kolmella uudella harvesterilla ja yhdellä
täydennyksellä.

## Lähdetutkimus

Kaikki alla oleva on mitattu 2026-07-29/30, ei oletettu.

### Eduskunnan avoin data

`https://avoindata.eduskunta.fi/api/v1/tables/` — 19 taulua, JSON,
sivutus `?perPage=&page=` (page on 0-alkuinen). Vastaus sisältää
`columnNames`, `rowData` ja `hasMore`.

Todelliset koot (bisektoitu sivutuksella):

| Taulu | Rivejä | Sisältö |
|---|---|---|
| `VaskiData` | 347 655 | Valtiopäiväasiakirjat XML:nä |
| `SaliDBPuheenvuoro` | ~146 600 | Täysistuntopuheenvuorot |
| `SaliDBAanestys` | ~43 500 | Äänestykset, vanhin 1996 |
| `MemberOfParliament` | 2 677 | Edustajat + XML-biografia |
| `SaliDBAanestysEdustaja` | >19 000 | Edustajan ääni per äänestys |

#### Ansa: `/counts` ei kerro taulujen kokoja

`GET /api/v1/tables/counts` palauttaa `rowCount`-kentän, joka **ei ole
taulun rivimäärä**. Se väitti:

- `SaliDBAanestys` = 96 → todellisuudessa ~43 500
- `SeatingOfParliament` = 0 → todellisuudessa yli 100 riviä, `hasMore: true`

Todennäköisesti se kertoo viimeksi tuoduista riveistä. Jos harvesteri
luottaisi siihen, aineistokuvauksiin tulisi täysin väärät kokoluvut ja
osa oikeasti sisällöllisistä tauluista jäisi pois tyhjinä.

**Kokojen ainoa luotettava lähde on sivutuksen bisektointi.**

#### Aidosti tyhjät taulut

Sivun 0 haulla varmennettuna tyhjiä ovat vain `HetekaData` ja
`SaliDBMessageLog`. `PrimaryKeys` (23 riviä) on teknistä metatietoa.
Nämä kolme jätetään pois; kaikki muut 16 taulua katetaan.

### Oikeusministeriön tulospalvelu

`https://tulospalvelu.vaalit.fi/{KOODI}-{VUOSI}/`

Latauskaava (huomaa: tiedostot ovat vaalihakemiston juuressa, eivät
`fi/`-alihakemistossa):

```
/{KOODI}-{VUOSI}/{koodi}-{vuosi}_{ehd|puo|alu}_maa.{csv|xml}.zip
```

`ehd` = ehdokastason tulokset, `puo` = puolueet ja valitsijayhdistykset,
`alu` = aluetason tulokset.

Etusivu listaa 15 vaalia, mutta latauksia on 11:llä. Varmennettu:

| Toimii | Ei toimi |
|---|---|
| EKV-2019, EKV-2023 | EKV-2011 (sivu on, CSV ei) |
| KV-2012, KV-2017, KV-2021, KV-2025 | TPV-2012, TPV-2018, TPV-2024 |
| AV-2022, AV-2025 | (presidentinvaaleilla ei latauksia) |
| EPV-2014, EPV-2019, EPV-2024 | |

Käyttöehto sivustolla: *"Tiedot ovat julkisia ja vapaasti käytettävissä."*

### POHTIVA

`https://www.fsd.tuni.fi/pohtiva/ohjelmalistat` listaa 95 puoluekoodia.
Puoluesivu `/ohjelmalistat/{PUOLUE}` sisältää jokaisen ohjelman id:n,
täyden otsikon ja ohjelmatyypin (`yleisohjelma`, `vaaliohjelma`,
`erityisohjelma`, `periaateohjelma`). Yhteensä 1 583 ohjelmaa 1880–2025.

Koko metatiedon saa siis 96 pyynnöllä (puoluelista + 95 puoluesivua) —
yksittäisiä ohjelmasivuja ei tarvitse hakea.

**Lisenssi puuttuu.** Sivustolla on vain viittausohje, ei mainintaa
uudelleenkäytön ehdoista.

### Vaalirahoitus (olemassa oleva harvesteri)

Kaikki 10 vaalia vastaavat 200. Aineistoja ei ole ennen vuotta 2018 —
VTV:n CSV-palvelu alkaa siitä.

Harvesterista puuttuu tiedostotyyppi **`E_JI`** (jälki-ilmoitukset).
Varmennettu saatavuus:

| On | Ei ole |
|---|---|
| aluevaalit2022, eduskuntavaalit2023 | kuntavaalit2025, presidentinvaali2024 |
| europarlamenttivaalit2024, aluevaalit2025 | (ja vanhemmat) |

## Arkkitehtuuri

Kolme uutta harvesteria ja yksi täydennys. Kaikki noudattavat olemassa
olevaa periytymishierarkiaa eivätkä muuta jaettua koodia.

```
BaseHarvester
├── EduskuntaHarvester (eduskunta.py)      — uusi, API-kutsut
├── PohtivaHarvester (pohtiva.py)          — uusi, HTML-jäsennys
└── StaticHarvester
    ├── TulospalveluHarvester (tulospalvelu.py) — uusi
    └── VaalirahoitusHarvester (vaalirahoitus.py) — täydennetään
```

Rekisteröinti `harvesters/__init__.py`:n `HARVESTERS`-dictiin. Kolme
uutta lähdettä ilmestyvät `list_sources()`-listaukseen automaattisesti.

## Komponentit

### 1. `EduskuntaHarvester`

Perii `BaseHarvester`. Tuottaa **7 kuratoitua aineistoa**, jotka kattavat
16 sisällöllistä taulua. Aineisto vastaa käyttötarkoitusta, ei API:n
taulurakennetta.

| Aineisto | Taulut |
|---|---|
| `eduskunta-kansanedustajat` | `MemberOfParliament`, `SeatingOfParliament` |
| `eduskunta-aanestykset` | `SaliDBAanestys`, `SaliDBAanestysJakauma`, `SaliDBAanestysAsiakirja`, `SaliDBAanestysKieli` |
| `eduskunta-aanestykset-edustajittain` | `SaliDBAanestysEdustaja` |
| `eduskunta-puheenvuorot` | `SaliDBPuheenvuoro` |
| `eduskunta-istunnot` | `SaliDBIstunto`, `SaliDBKohta`, `SaliDBKohtaAanestys`, `SaliDBKohtaAsiakirja`, `SaliDBTiedote` |
| `eduskunta-asiakirjat` | `VaskiData` |
| `eduskunta-liitteet` | `Attachment`, `AttachmentGroup` |

Jokainen taulu on oma resurssi, formaatti `API`, url
`https://avoindata.eduskunta.fi/api/v1/tables/{Taulu}/rows`.

**Kokojen mittaus.** Harvestointi bisektoi jokaisen taulun koon sivutuksen
avulla ja kirjoittaa tuloksen `notes_fi`-kenttään. Yksi taulu maksaa noin
17 pyyntöä, koko harvesterin ajo noin 270. Tämä on tietoinen valinta:
`/counts` olisi yksi pyyntö mutta antaisi väärän luvun.

Bisektointi eristetään omaan funktioonsa `_measure_rows(table) -> int`,
jotta se on testattavissa erikseen. Yläraja on 1 000 000 riviä: se ylittää
suurimman taulun kolminkertaisesti, mutta pysäyttää silmukan jos API
alkaa palauttaa rivejä loputtomiin.

Ansa dokumentoidaan koodikommenttina mittausfunktion yhteyteen, jottei
sitä myöhemmin "optimoida" takaisin `/counts`-kutsuksi.

### 2. `TulospalveluHarvester`

Perii `StaticHarvester`. **11 aineistoa**, yksi per vaali, kussakin
6 resurssia (kolme tasoa × CSV ja XML).

Vaalilista on koodissa vakiona, koska se muuttuu vain vaalien myötä.
Lista on varmennettu, joten kuolleita linkkejä ei synny heti; myöhemmän
ajautumisen havaitsee `aura health`.

Lisenssi: julkinen ja vapaasti käytettävissä.

### 3. `PohtivaHarvester`

Perii `BaseHarvester`, koska tarvitsee HTTP-kutsut. Kaksi vaihetta:

1. Hae `/ohjelmalistat`, poimi 95 puoluekoodia
2. Hae kunkin puolueen sivu, poimi ohjelmien id, otsikko ja tyyppi

Tuottaa **1 583 aineistoa**:

- tunniste `pohtiva-{puolue}-{id}` (esim. `pohtiva-vihr-1485`)
- otsikko = ohjelman oma nimi
- avainsanat = puoluekoodi, ohjelmatyyppi, vuosi jos otsikosta löytyy
- resurssi = HTML-linkki ohjelmasivulle, formaatti `HTML`

**Ohjelmatekstejä ei kopioida.** Aura tallentaa metatiedot ja linkin.

**Lisenssi jätetään tyhjäksi.** `_make_dataset()` asettaisi oletuksena
`license_id="cc-by-4.0"`, mikä olisi väite jota lähde ei tue. Harvesteri
ohittaa oletuksen antamalla `license_id=""` ja `license_title=""`, ja
kirjaa kuvaukseen että tekijänoikeus on puolueella ja aineistoa ylläpitää
Yhteiskuntatieteellinen tietoarkisto.

Pyyntöjen väliin rajoitin, jotta 96 peräkkäistä hakua ei kuormita
palvelinta.

### 4. `VaalirahoitusHarvester` — täydennys

`_CSV_TYPES`-listaan ei voi lisätä `E_JI`:tä suoraan, koska se koskee vain
neljää vaalia kymmenestä. Lisätään `_ELECTIONS`-alkioihin valinnainen
lippu `has_ji: True`, ja `_election_dataset()` lisää resurssin vain kun
lippu on.

Varmennuspäivä kirjataan kommenttiin.

## Virheenkäsittely

Harvesterit eivät saa muuttaa ylävirran rikkoutumista hiljaiseksi nollaksi
— tämä on juuri se vika joka löytyi Valtiokonttorista ja SYKEstä. Siksi:

- Yksittäisen puolueen tai taulun epäonnistuminen lokitetaan ja ohitetaan,
  mutta ei niellä hiljaisesti
- Koko lähteen epäonnistuminen saa nousta poikkeuksena
- Putken `check_count_regression()` havaitsee jatkossa jos jokin näistä
  tippuu nollaan tai putoaa yli 20 %

Bisektointi tarvitsee ylärajan, jottei rikkinäinen API johda päättymättömään
silmukkaan.

## Testaus

Yksikkötestit per harvesteri, `tests/test_{nimi}.py`. **Testit eivät mene
verkkoon** — HTTP mockataan.

Katettavat asiat:

- `EduskuntaHarvester`: bisektointi löytää oikean koon mockatulla
  sivutuksella; `/counts` ei ole käytössä; 7 aineistoa syntyy; jokainen
  resurssi osoittaa oikeaan tauluun
- `TulospalveluHarvester`: 11 aineistoa, 6 resurssia kussakin, URL-kaava
  oikein (tiedostot juuressa, eivät `fi/`-hakemistossa)
- `PohtivaHarvester`: puoluelistan ja ohjelmalistan jäsennys; lisenssi jää
  tyhjäksi; tunnisteen muoto
- `VaalirahoitusHarvester`: `E_JI` lisätään vain lipulla merkityille
  vaaleille, ei muille

## Vaikutus

Korpus **11 202 → ~12 800 aineistoa**.

POHTIVA on noin 12 % korpuksesta. Määrä on linjassa nykyisten lähteiden
kanssa: sotkanet on jo 31 % ja statfin 14 %.

Kolme uutta lähdettä `list_sources()`-listaukseen.

## Rajaukset

Tähän työhön **ei** kuulu:

- Rividatan tuonti kantaan. Aura pysyy metatietokataloginä.
- Ohjelmatekstien indeksointi tai tallennus.
- Presidentinvaalien tulostiedostot — niitä ei ole tarjolla.
- Vaalirahoitus ennen vuotta 2018 — sitä ei ole tarjolla.
- Kultaisen setin laajentaminen poliittisilla kyselyillä. Se on
  erillinen työ, joka kannattaa tehdä vasta kun nämä aineistot ovat
  kannassa.
