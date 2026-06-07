# Aura Remote MCP @ AWS — suunnitelma

- **Päivämäärä:** 2026-06-06
- **Tila:** Hyväksytty suunta, odottaa spec-katselmointia
- **Tekijä:** Tero + Claude (brainstorming)

## 1. Tavoite ja rajaukset

Aura on tällä hetkellä paikallisesti ajettava MCP-server (FastMCP 3.x, stdio-transport).
Tavoitteena on julkaista **remote MCP -endpoint AWS:ään**, jotta kuka tahansa MCP-yhteensopiva
asiakas (Claude, ChatGPT ym.) voi käyttää Auraa ilman repon kloonausta.

**Reunaehdot (sovittu):**

- **Julkinen, avoin projekti** → ei salaisuuksia repossa missään muodossa. CI autentikoituu
  AWS:ään OIDC:llä, ei tallennettuja avaimia.
- **Täysin avoin pääsy** → ei API-avainta eikä OAuthia v1:ssä. Vain väärinkäytön esto (rate-limit).
- **Read-only remote** → remote tarjoaa vain luvun. Kirjoittavat toolit (enrichment, findings-tallennus,
  harvest, quality/schema-päivitykset) eivät ole käytössä remotessa. Rikastus tehdään lokaalisti ja
  committataan kantaan.
- **Helppo nyt, laajennettava myöhemmin.** Erityisesti **kannan etäpäivityksen** pitää muuttua helpoksi
  roadmapilla ilman koodideployta.

**Rajaukset (out of scope v1):**

- Web-palvelun (FastAPI `aura web`) hostaus — eri elinkaari, käsitellään myöhemmin (ks. roadmap).
- Remote-kirjoitukset / joukkoistus pilvessä.
- OAuth / käyttäjäkohtaisuus.
- Boundaries-gpkg-tiedostojen (299 MB) vienti pilveen — ei tarvita: paikkatieto tarjotaan
  kannasta MCP-työkaluilla (ks. §4.6), ei gpkg-tiedostoista.

## 2. Lähtötilanteen havainnot

- **Transport:** `cli.py serve` kutsuu `mcp.run()` → stdio. Remote vaatii streamable HTTP -transportin.
- **Ajonaikainen riippuvuus on vain `data/aura.db` (~87 MB)**, joka on jo gitissä. Boundaries-gpkg:t
  käytetään vain offline-populaattoreissa (`populators/map_sheets.py`) ja web-apissa
  (`web/routes/api.py`), **ei MCP-tooleissa**. Karttalehdet ovat jo `ref_map_sheets`-taulussa kannassa.
- **Kirjoitukset kantaan** tulevat: `tools/enrichment.py`, `tools/admin.py` (harvest), `tools/quality.py`,
  `tools/schema.py`, `tools/research.py` (save_session_findings). Nämä gateataan pois remotessa.
- **Server-instructions** (`server.py`) lupaa agentille, että se voi lukea `data/boundaries/*.gpkg`
  paikallisesta tiedostojärjestelmästä. Remotessa tätä FS:ää ei ole → tarvitaan remote-variantti
  instructions-tekstistä.

## 3. Arkkitehtuuri (v1)

```
                 ┌────────────────────────────────────────────┐
   MCP-client    │  AWS                                         │
  (Claude, GPT)  │                                              │
       │  HTTPS  │   ┌──────────────┐      ┌───────────────┐    │
       └────────────▶│  App Runner  │◀─────│      ECR      │    │
        /mcp     │   │  (Aura HTTP) │ pull │  aura:<tag>   │    │
                 │   │  read-only   │ img  └───────────────┘    │
                 │   │  stateless   │              ▲            │
                 │   └──────┬───────┘              │ push       │
                 │          │ stdout/err           │            │
                 │          ▼                       │            │
                 │   ┌──────────────┐       ┌──────────────┐    │
                 │   │  CloudWatch  │       │  GitHub       │    │
                 │   │  Logs/Metrics│       │  Actions(OIDC)│    │
                 │   └──────────────┘       └──────────────┘    │
                 └────────────────────────────────────────────┘
                                              ▲
                                              │ git push (main / tag)
                                       ┌──────────────┐
                                       │  Dev (lokaali)│  harvest + committaa aura.db
                                       └──────────────┘
```

**Komponentit:**

- **AWS App Runner** — ajaa Aura-kontin, tarjoaa hallitun HTTPS-endpointin, autoscalingin ja
  custom domainin. Health check `/health`-polkuun. Deploy laukaistaan eksplisiittisesti (auto-deploy pois).
- **Amazon ECR** — kontti-imagejen rekisteri. Imageen leivottu `data/aura.db` (v1).
- **CloudWatch** — App Runnerin lokit ja metriikat (request count, latency, 5xx).
- **IAM OIDC -rooli** — GitHub Actions ottaa lyhytikäisen roolin (ei tallennettuja avaimia).
- **(Valinnainen) Route 53 + ACM** — custom domain ja sertifikaatti, esim. `mcp.aura.fi`.
- **(Roadmap, vaihe 2) S3** — `aura.db`:n jakelu ilman image-rebuildia.

### 3.1 Julkitaho-näkökulma (kohde + portability)

Palvelu on tulossa julkiselle taholle; lopullista AWS-tiliä, domainia ja toteutustapaa ei ole vielä
sovittu. Tämä **ei muuta v1-suositusta** (App Runner), mutta huomioidaan:

- **EU-region / dataresidenssi:** valitaan EU-region (eu-west-1 Irlanti tai eu-central-1 Frankfurt;
  **huom:** App Runner ei välttämättä ole eu-north-1 Tukholmassa — varmistettava region-valinnassa).
  Data on avointa julkista dataa ja read-only, joten residenssi ei ole kriittinen, mutta hyvä käytäntö.
- **Tilin omistus / landing zone:** jos julkitaho hostaa palvelun omassa AWS-organisaatiossaan, heidän
  guardrailinsa (sallitut palvelut, pakollinen VPC, tagit, verkkorakenne) voivat ohjata valintaa.
- **Portability on suunnittelun kantava periaate:** koska palvelu on **kontti** (stateless, read-only,
  yksi `/mcp`-endpoint), se siirtyy sellaisenaan App Runnerista ECS Fargateen / EKS:ään / julkitahon
  landing zoneen **ilman sovellusmuutoksia**. Region ja tili ovat Terraform-muuttujia. → App Runner on
  turvallinen ja nopea v1-valinta, joka ei lukitse pois julkitahon mahdollisia vaatimuksia.

## 4. Komponenttisuunnittelu

### 4.1 HTTP-transport-moodi

`cli.py serve` saa lipun transportin valintaan:

```bash
aura serve                       # stdio (nykyinen, oletus — ei rikota mitään)
aura serve --http --host 0.0.0.0 --port 8000   # streamable HTTP remotea varten
```

- Käytetään FastMCP:n streamable HTTP -transporttia, polku `/mcp`.
- **Stateless-moodi päälle** (read-only horisontaalisesti skaalautuva) → ei session-tilaa instanssien
  välillä, App Runner voi skaalata vapaasti.
- Portti ja host konfiguroidaan env-muuttujilla (`AURA_HTTP_HOST`, `AURA_HTTP_PORT`) ja/tai lipuilla.

### 4.2 Read-only-moodi

Ohjataan env-muuttujalla `AURA_READONLY=1` (asetetaan App Runnerissa):

- **SQLite avataan read-only** -tilassa (`file:...?mode=ro`, `immutable=1` jos kanta on muuttumaton
  imagessa) → estää vahingossa tapahtuvat kirjoitukset jo tasolla 0.
- **Kirjoittavat toolit eivät rekisteröidy** remote-moodissa. Toteutus: tool-rekisteröinti tarkistaa
  moodin ja ohittaa nämä: `enrich`, `batch_enrich`, `suggest_yso_tags(save=True)`,
  `save_session_findings`, `harvest`, `populate_reference`, `probe_sizes`, sekä quality/schema-kirjoitus.
  (`log_finding`/`list_findings` voivat jäädä, koska ne ovat session-muistissa, mutta tallennus pois.)
- Tämä pidetään yhdessä paikassa (esim. `aura/config.py: is_readonly()`) jottei moodilogiikka leviä.

### 4.3 Remote-instructions-variantti

`server.py`:n `instructions`-teksti viittaa local-FS:ään (`data/boundaries/*.gpkg`). Remote-moodissa:

- Korvataan FS-pohjaiset boundaries-ohjeet ohjeella käyttää **§4.6:n paikkatietotyökaluja**, jotka
  palvelevat saman tiedon kannasta (`ref_map_sheets` bbox jo valmiina). Agentti saa siis saman
  paikkatieto-osaamisen ilman tiedostojärjestelmää.
- Säilytetään rajapintojen suora käyttö -ohje (query_data toimii remotessa, koska outbound HTTP).
- Toteutus: `build_instructions(readonly: bool) -> str` tai kaksi vakiota.

### 4.6 Paikkatietotyökalut MCP:ssä (spatial enrichment)

**Tavoite (käyttäjän toive):** agentti osaa hyödyntää Auran valmista paikkatietoa — rajata
kyselyjä kohderajapintoihin (WFS/WCS/OGC) alueella ja ymmärtää mitä "paikkatieto" tarkoittaa
kussakin yhteydessä. Esim. *"millaisia tietoja meillä on karttalehdeltä L4133?"* → Aura palauttaa
lehden bbox:n + osaa rajata datakyselyt sille alueelle. Tämä toimii **täysin kannasta**, joten se
sopii read-only-remoteen.

**Data-valmius:**
- `ref_map_sheets` sisältää **jo** bbox:n (`min_x/min_y/max_x/max_y`), centroidin, mittakaavan ja
  hierarkkisen tunnuksen (`id`, esim. `L4133A`) → karttalehtirajaus heti mahdollista.
- `ref_municipalities` **ei** sisällä bbox:ia → tarvitaan pieni offline-populaattorilisäys (bbox-sarakkeet
  + täyttö `kuntajako_1000k.gpkg`:sta). Sama mekanismi kuin `ref_map_sheets` sai bbox:nsa.

**Uudet read-only-toolit (palvelevat kannasta):**
- `map_sheet(id)` — palauttaa karttalehden bbox:n (EPSG:3067), centroidin ja mittakaavan; valmis
  WFS/WCS-`bbox`-parametriksi.
- `find_map_sheets(bbox | point | municipality, scale)` — mitkä lehdet osuvat alueelle; lisäksi
  hierarkkinen rajaus tunnus-prefiksillä (esim. kaikki `L413%` -lehdet halutulla mittakaavalla).
- `municipality_bbox(name | code)` — kunnan bbox aluerajaukseen (vaatii populaattorilisäyksen).
- *(Harkittava)* `query_data`:n laajennus: valinnainen `map_sheet`/`municipality`-parametri, joka
  muuntaa alueen bbox:ksi ja syöttää sen WFS/OGC-kyselyyn automaattisesti → "rikastaa kyselyn targettiin".

**Hyöty:** sama paikkatieto-osaaminen toimii sekä lokaalisti että remotessa, ja se hyödyttää myös
nykyistä lokaalikäyttöä (ei enää riippuvuutta gpkg-tiedostoista perusrajauksissa).

### 4.4 Kontti-image (Dockerfile)

- Pohja: `python:3.11-slim`.
- Asennetaan vain runtime-riippuvuudet (`pip install .` ilman `dev`/`web`-extroja).
- Kopioidaan `src/` + `data/aura.db`. **Ei** boundaries-gpkg:itä (säästää ~299 MB).
- `.dockerignore`: `.venv`, `tests`, `data/boundaries`, `.git`, cachet, `output/`.
- Ajaa non-root-käyttäjänä. `EXPOSE 8000`. `CMD ["aura","serve","--http","--host","0.0.0.0","--port","8000"]`.
- Tavoite image-koko: < ~250 MB.

### 4.5 Health-endpoint

- Lisätään kevyt `/health` (200 OK + esim. datasettien määrä / DB-yhteyden tarkistus) FastMCP:n
  alla olevaan Starlette-appiin. App Runner käyttää tätä health checkinä.

## 5. Kannan jakelu ja päivitys

### Vaihe 1 (MVP) — DB leivottu imageen

- `aura.db` kopioidaan imageen build-aikana.
- **Päivitysflow:** lokaali `harvest` → committaa `aura.db` → `git push` → kun halutaan julkaista,
  laukaistaan manuaalinen deploy-triggeri → GitHub Actions buildaa imagen → ECR → App Runner -deploy.
- **Edut:** atominen (kanta + koodi samassa artefaktissa), versioitu, rollback image-tagilla, nolla
  lisäinfraa. Sopii nykyiseen "DB on gitissä" -workflowhun.

### Vaihe 2 (roadmap) — DB S3:sta, lataus käynnistyksessä

- Kontti lataa käynnistyessä `aura.db`:n S3:sta paikalliseen ephemeral-levyyn jos
  `AURA_DB_S3_URI` on asetettu (muuten käyttää imageen leivottua).
- **Päivitysflow:** `aura db-publish` lataa kannan S3:een (versioitu bucket) ja triggeröi App Runner
  -redeployn → ei koodimuutosta, ei image-rebuildia. Repo voi lopulta lakata kantamasta 87 MB binääriä.
- **Suunnitellaan jo v1:ssä:** käynnistyslataaja kirjoitetaan niin, että S3-lähde on pelkkä
  env-muuttuja → vaihe 2 on additiivinen, ei refaktorointia.

## 6. IaC — Terraform

Pieni, luettava moduulisetti `infra/`-kansioon:

- `ecr.tf` — ECR-repo (lifecycle policy vanhojen tagien siivoukseen).
- `apprunner.tf` — App Runner -service: image ECR:stä, portti 8000, health check `/health`,
  autoscaling (min 1, max esim. 3), env: `AURA_READONLY=1`.
- `iam.tf` — GitHub OIDC provider + deploy-rooli (ECR push + App Runner update), App Runnerin
  access-rooli ECR:ään.
- `dns.tf` (valinnainen) — ACM-sertti + custom domain App Runnerille.
- `variables.tf` / `outputs.tf` — region, image-tag, domain; output: palvelun URL.

**Salassapito (julkinen repo):** mitään AWS-tunnistetta ei kovakoodata reposovittuun koodiin.
Arkaluontoiset arvot (account id, region, OIDC-rooli-ARN, ECR-URI, domain) annetaan `*.tfvars`-
tiedostona joka on **.gitignoressa**. Terraform-state private S3-backendissä (+ DynamoDB lock) —
ei koskaan julkiseen repoon. `.gitignore`: `*.tfvars`, `.terraform/`, `*.tfstate*`,
`.terraform.lock.hcl` (lock voi jäädä, mutta state ei).

> Vaihtoehto: AWS CDK (Python) jos halutaan infra samalla kielellä kuin projekti. Valittu Terraform
> "helppo + kypsä App Runner -tuki" -syystä. Päätös kirjataan issueen.

## 7. CI/CD — GitHub Actions + OIDC

Workflow `.github/workflows/deploy.yml`:

1. **Trigger:** **vain `workflow_dispatch`** (manuaalinen, eksplisiittinen "oma deployment-triggeri").
   Ei auto-deployta pushista eikä App Runnerin auto-deploya. Deploy ajetaan Actions-napista tai
   `gh workflow run deploy.yml`. Suojataan **GitHub Environmentilla** (`production`), joka voi vaatia
   hyväksynnän ennen ajoa.
2. **Salassapito (julkinen repo):** kaikki AWS-tunnisteet (account id, region, OIDC-rooli-ARN, ECR-URI,
   domain) tallennetaan **GitHub Actions secrets/variables** -muotoon (yksityisiä myös julkisessa
   repossa) tai suojattuun Environmentiin — **ei koskaan koodiin**.
3. **Auth:** `aws-actions/configure-aws-credentials` OIDC:llä → lyhytikäinen rooli. Ei secrets-storea
   pitkäikäisille avaimille.
4. **Build & push:** Docker build → tag (git SHA + `latest`) → push ECR:ään.
5. **Deploy:** eksplisiittinen App Runner `start-deployment` -API-kutsu (auto-deploy pois).
6. **(Valinnainen) Smoke test:** deployn jälkeen kutsu `/health` ja yksi MCP-`stats`-kutsu.

Erillinen `ci.yml` (jos ei jo): ruff + mypy + pytest PR:issä (ei AWS-riippuvuutta).

## 8. Tietoturva ja väärinkäytön esto

- **Avoin endpoint** → ei autentikointia v1. Riski: väärinkäyttö / kustannukset.
- **Rate-limit:** App Runnerissa ei natiivia rate-limitiä. v1: luotetaan App Runnerin max-instanssirajaan
  + CloudWatch-hälytys epätavallisesta liikenteestä. Roadmap: CloudFront + AWS WAF rate-based -sääntö
  endpointin eteen jos väärinkäyttöä ilmenee.
- **Read-only + stateless** → ei dataa rikottavaksi, ei session-tilaa vuodettavaksi.
- **Ei salaisuuksia** imagessa, repossa eikä lokeissa. Outbound-kutsut (query_data) menevät julkisiin
  avoimen datan rajapintoihin.
- **Kustannuskatto:** AWS Budgets -hälytys.

## 9. Observability

- CloudWatch Logs (stdout/stderr), metriikat: request count, latency, 4xx/5xx, instanssimäärä.
- CloudWatch-hälytykset: 5xx-piikki, poikkeava request-volyymi, kustannusbudjetti.

## 10. Kustannusarvio (karkea)

- App Runner: ~5–25 $/kk (min 1 pieni instanssi idlenä; skaalautuu liikenteellä).
- ECR: muutama sentti/kk (image-tallennus).
- CloudWatch / Route53: muutama dollari/kk.
- **Yhteensä luokkaa ~10–30 $/kk** matalalla liikenteellä.

## 11. Testaus

- **Yksikkö:** read-only-gateys (kirjoittavia tooleja ei rekisteröidy kun `AURA_READONLY=1`),
  remote-instructions-variantti, RO-SQLite-yhteys.
- **Integraatio:** `aura serve --http` käynnistyy, `/health` vastaa 200, MCP-`initialize` +
  `stats`-kutsu HTTP:n yli onnistuu.
- **Kontti:** image buildaa, käynnistyy, `/health` vastaa kontissa.
- **CI:** ruff + mypy(strict) + pytest säilyvät vihreinä.
- Olemassa olevat testit importoivat `from aura.server import ...` → varmistetaan ettei moodilogiikka
  riko importteja (oletus stdio + ei-readonly testeissä).

## 12. Tulevaisuuden roadmap

Vaiheistettu, kukin oma epic/spec myöhemmin:

1. **Vaihe 2 — DB S3:sta + `aura db-publish`** (kts. §5): kannan etäpäivitys ilman koodideployta.
2. **Web-palvelun hostaus** (`aura web`): sama kontti tai erillinen App Runner -service; staattinen
   build CloudFront+S3:een tai SSR App Runnerissa. Oma elinkaari.
3. **Väärinkäytön esto:** CloudFront + WAF rate-limiting jos avoin endpoint sitä vaatii.
4. **Paikkatietotyökalujen laajennus:** §4.6:n peruskalut (map_sheet, find_map_sheets,
   municipality_bbox) ovat v1:ssä. Laajennus: `query_data`-rikastus alueparametrilla, hierarkkinen
   lehtinavigointi, point-in-polygon-haut tarkemmalla `kuntajako_10k`-aineistolla.
5. **Remote-kirjoitukset / joukkoistus:** jos halutaan crowdsourcing pilvessä → erillinen kirjoitus-store
   (DynamoDB tai EFS-SQLite) tai PR-pohjainen kontribuutio. Vaatii oman suunnittelun.
6. **OAuth / käyttäjäkohtaisuus:** MCP-spec OAuth jos tarvitaan kiintiöitä per käyttäjä.
7. **MCP-rekisteröinti:** listaus julkisiin MCP-hakemistoihin (julkaisija hankittu) kun endpoint vakaa.
8. **Monialueisuus / korkea saatavuus:** App Runner on jo moni-AZ; useampi region vasta jos tarve.

## 13. Toteutusjärjestys (epic → issuet)

Epic: **AWS deployment (remote MCP)**. Issuet karkeassa riippuvuusjärjestyksessä:

1. HTTP-transport-moodi `serve`-komentoon (`--http`, stateless).
2. Read-only-moodi: tool-gateys + RO-SQLite + `config.is_readonly()`.
3. Paikkatietotyökalut (§4.6): `map_sheet`, `find_map_sheets` (kannasta, valmis heti) +
   `ref_municipalities`-bbox-populaattori + `municipality_bbox`. *(Harkittava `query_data`-laajennus.)*
4. Remote-instructions-variantti (ohjaa §4.6-työkaluihin, ei local-FS-lupauksia).
5. `/health`-endpoint.
6. Dockerfile + `.dockerignore` (vain `aura.db`, ei boundaries).
7. Terraform: ECR + App Runner + IAM OIDC (+ valinnainen domain).
8. GitHub Actions deploy-workflow (OIDC → build → push → deploy).
9. Observability + budjetti + smoke test.
10. Dokumentaatio: README "Remote MCP" -osio + asiakaskonfiguraatiot.
11. (Roadmap-issue) Vaihe 2: DB S3:sta + `aura db-publish`.
