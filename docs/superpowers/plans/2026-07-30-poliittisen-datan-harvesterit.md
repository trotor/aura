# Poliittisen datan harvesterit — toteutussuunnitelma

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lisää Auraan eduskunnan, oikeusministeriön tulospalvelun ja POHTIVAn aineistot sekä täydennä vaalirahoitus puuttuvalla tiedostotyypillä.

**Architecture:** Kolme uutta harvesteria olemassa olevaan periytymishierarkiaan (`EduskuntaHarvester` ja `PohtivaHarvester` perivät `BaseHarvester`, `TulospalveluHarvester` perii `StaticHarvester`) sekä pieni muutos olemassa olevaan `VaalirahoitusHarvester`-luokkaan. Jaettuun koodiin ei kosketa.

**Tech Stack:** Python 3.11+, httpx (async), sqlite3, pytest, pytest-asyncio, ruff, mypy (strict).

## Global Constraints

- Kaikki Python-komennot venvin kautta: `source .venv/bin/activate`
- Testit **eivät saa mennä verkkoon** — HTTP mockataan `patch.object(h, "_make_client")`
- Uudet harvesterit rekisteröidään `src/aura/harvesters/__init__.py`:n `HARVESTERS`-dictiin
- Commit-viestit Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`
- `mypy src/aura` ei saa tuottaa uusia virheitä (lähtötaso: 5 ennestään olevaa)
- Kaikki käyttäjälle näkyvä teksti suomeksi
- Speksi: `docs/superpowers/specs/2026-07-30-poliittisen-datan-harvesterit-design.md`

---

### Task 1: Vaalirahoituksen E_JI-täydennys

Pienin muutos ja ainoa joka koskee olemassa olevaa koodia. Tehdään ensin, jotta muutos on erillään uusista tiedostoista.

**Files:**
- Modify: `src/aura/harvesters/vaalirahoitus.py:24-85` (`_ELECTIONS`), `:92-119` (`_election_dataset`)
- Test: `tests/test_vaalirahoitus.py`

**Interfaces:**
- Consumes: ei mitään aiemmasta taskista
- Produces: ei mitään myöhemmille taskeille (itsenäinen)

**Taustatieto:** VTV julkaisee neljä tiedostotyyppiä (`E_EI`, `RAHOITUSRIVIT_E_EI`, `E_VI`, `RAHOITUSRIVIT_E_VI`) kaikille vaaleille, ja viidennen — `E_JI` (jälki-ilmoitukset) — vain osalle. Varmennettu 2026-07-29: `E_JI` on olemassa vaaleille aluevaalit2022, eduskuntavaalit2023, europarlamenttivaalit2024 ja aluevaalit2025. Muille se palauttaa 404.

- [ ] **Step 1: Kirjoita kaatuva testi**

Luo `tests/test_vaalirahoitus.py` (tiedostoa ei ole vielä olemassa):

```python
"""Testit vaalirahoitus-harvesterille."""

import sqlite3

from aura.database import init_db
from aura.harvesters.vaalirahoitus import VaalirahoitusHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _dataset_config(ds_id: str) -> dict:
    """Hae yhden datasetin konfiguraatio id:n perusteella."""
    for cfg in VaalirahoitusHarvester.datasets_config:
        if cfg["id"] == ds_id:
            return cfg
    raise AssertionError(f"Datasettiä {ds_id} ei löydy")


class TestJalkiIlmoitukset:
    """E_JI lisätään vain niille vaaleille joilla se oikeasti on."""

    def test_election_with_ji_has_five_resources(self) -> None:
        cfg = _dataset_config("vaalirahoitus-eduskuntavaalit2023")
        assert len(cfg["resources"]) == 5

    def test_election_without_ji_has_four_resources(self) -> None:
        cfg = _dataset_config("vaalirahoitus-kuntavaalit2025")
        assert len(cfg["resources"]) == 4

    def test_ji_url_is_correct(self) -> None:
        cfg = _dataset_config("vaalirahoitus-aluevaalit2025")
        urls = [r["url"] for r in cfg["resources"]]
        assert (
            "https://www.vaalirahoitusvalvonta.fi/fi/index/vaalirahoitus/"
            "haetietoavaalirahoitusilmoituksista/tutkitietoaineistoja/"
            "aluevaalit2025/E_JI_aluevaalit2025.csv"
        ) in urls

    def test_only_four_elections_have_ji(self) -> None:
        """Tarkka lista — ei saa vuotaa muille vaaleille."""
        with_ji = [
            cfg["id"]
            for cfg in VaalirahoitusHarvester.datasets_config
            if any("E_JI" in r["url"] for r in cfg["resources"])
        ]
        assert sorted(with_ji) == [
            "vaalirahoitus-aluevaalit2022",
            "vaalirahoitus-aluevaalit2025",
            "vaalirahoitus-eduskuntavaalit2023",
            "vaalirahoitus-europarlamenttivaalit2024",
        ]


class TestExistingResourcesUnchanged:
    """Vanhat resurssit eivät saa muuttua."""

    def test_all_elections_still_have_evi(self) -> None:
        for cfg in VaalirahoitusHarvester.datasets_config:
            if not cfg["id"].startswith("vaalirahoitus-puoluerahoitus"):
                urls = " ".join(r["url"] for r in cfg["resources"])
                assert "E_VI_" in urls

    def test_party_year_datasets_untouched(self) -> None:
        cfg = _dataset_config("vaalirahoitus-puoluerahoitus-2024")
        assert len(cfg["resources"]) == 1
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `source .venv/bin/activate && pytest tests/test_vaalirahoitus.py -v`
Expected: FAIL — `test_election_with_ji_has_five_resources` saa 4, odottaa 5.

- [ ] **Step 3: Lisää `has_ji`-lippu neljälle vaalille**

Muokkaa `src/aura/harvesters/vaalirahoitus.py`. Lisää `"has_ji": True` näiden neljän vaalin dictiin — muihin **ei** lisätä mitään:

```python
    {
        "slug": "aluevaalit2022",
        "title": "Aluevaalit 2022",
        "year": 2022,
        "keywords": ["aluevaalit", "hyvinvointialue", "2022"],
        "has_ji": True,
    },
```

```python
    {
        "slug": "eduskuntavaalit2023",
        "title": "Eduskuntavaalit 2023",
        "year": 2023,
        "keywords": ["eduskuntavaalit", "2023"],
        "has_ji": True,
    },
```

```python
    {
        "slug": "europarlamenttivaalit2024",
        "title": "Europarlamenttivaalit 2024",
        "year": 2024,
        "keywords": ["europarlamenttivaalit", "EU-vaalit", "2024"],
        "has_ji": True,
    },
```

```python
    {
        "slug": "aluevaalit2025",
        "title": "Aluevaalit 2025",
        "year": 2025,
        "keywords": ["aluevaalit", "hyvinvointialue", "2025"],
        "has_ji": True,
    },
```

- [ ] **Step 4: Lisää E_JI-resurssi `_election_dataset()`-funktioon**

Korvaa `_election_dataset()`-funktion `resources`-lohko (rivit 96–105) tällä:

```python
    resources = [
        {
            "id": f"vaalirahoitus-{slug}-{prefix.lower().replace('_', '-')}",
            "name": f"{title} — {label}",
            "name_fi": f"{title} — {label}",
            "format": "CSV",
            "url": f"{VR_BASE}/{slug}/{prefix}_{slug}.csv",
        }
        for prefix, label in _CSV_TYPES
    ]
    # Jälki-ilmoitukset julkaistaan vain osalle vaaleista. Varmennettu
    # 2026-07-29: E_JI vastaa 200:lla neljälle vaalille, muille 404.
    # Älä lisää tätä _CSV_TYPES-listaan — se loisi kuolleita linkkejä
    # kuudelle vaalille.
    if election.get("has_ji"):
        resources.append({
            "id": f"vaalirahoitus-{slug}-e-ji",
            "name": f"{title} — Jälki-ilmoitukset",
            "name_fi": f"{title} — Jälki-ilmoitukset",
            "format": "CSV",
            "url": f"{VR_BASE}/{slug}/E_JI_{slug}.csv",
        })
```

- [ ] **Step 5: Aja testit ja varmista että ne menevät läpi**

Run: `source .venv/bin/activate && pytest tests/test_vaalirahoitus.py -v`
Expected: PASS, 6 testiä.

- [ ] **Step 6: Commit**

```bash
git add src/aura/harvesters/vaalirahoitus.py tests/test_vaalirahoitus.py
git commit -m "feat: lisää jälki-ilmoitukset vaalirahoitukseen

E_JI-tiedostotyyppi puuttui kokonaan. Se julkaistaan vain neljälle
vaalille kymmenestä, joten se lisätään lipulla eikä _CSV_TYPES-listaan
— muuten syntyisi kuusi kuollutta linkkiä."
```

---

### Task 2: TulospalveluHarvester

**Files:**
- Create: `src/aura/harvesters/tulospalvelu.py`
- Modify: `src/aura/harvesters/__init__.py`
- Test: `tests/test_tulospalvelu.py`

**Interfaces:**
- Consumes: `StaticHarvester` (`src/aura/harvesters/static.py`), joka lukee luokkamuuttujan `datasets_config: list[dict]` ja muuntaa sen Dataset-olioiksi
- Produces: `TulospalveluHarvester` rekisteröitynä nimellä `"tulospalvelu"`

**Taustatieto:** Latauskaava on `https://tulospalvelu.vaalit.fi/{KOODI}/{koodi}_{taso}_maa.{fmt}.zip`, jossa `{koodi}` on pienellä. Tiedostot ovat vaalihakemiston **juuressa**, eivät `fi/`-alihakemistossa — `fi/`-polku palauttaa 404. Tasot: `ehd` (ehdokkaat), `puo` (puolueet ja valitsijayhdistykset), `alu` (alueet). Varmennettu 2026-07-29: 11 vaalilla on toimiva lataus, presidentinvaaleilla (TPV) ei lainkaan.

Resurssien formaatiksi merkitään `ZIP`, koska tiedostot ovat zipattuja — tämä noudattaa Metsäkeskus-harvesterin käytäntöä. Sisältöformaatti näkyy resurssin nimessä.

- [ ] **Step 1: Kirjoita kaatuva testi**

Luo `tests/test_tulospalvelu.py`:

```python
"""Testit oikeusministeriön tulospalvelu-harvesterille."""

import sqlite3

from aura.database import init_db
from aura.harvesters.tulospalvelu import TulospalveluHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestConfig:
    def test_name(self) -> None:
        assert TulospalveluHarvester.name == "tulospalvelu"

    def test_eleven_elections(self) -> None:
        """11 vaalia joilla on varmennettu lataus — ei enempää eikä vähempää."""
        assert len(TulospalveluHarvester.datasets_config) == 11

    def test_no_presidential_elections(self) -> None:
        """TPV-vaaleilla ei ole latauksia, joten niitä ei saa olla mukana."""
        ids = " ".join(c["id"] for c in TulospalveluHarvester.datasets_config)
        assert "tpv" not in ids.lower()
        assert "presidentin" not in ids.lower()


class TestResources:
    def test_six_resources_per_election(self) -> None:
        for cfg in TulospalveluHarvester.datasets_config:
            assert len(cfg["resources"]) == 6, cfg["id"]

    def test_url_pattern(self) -> None:
        cfg = next(
            c for c in TulospalveluHarvester.datasets_config
            if c["id"] == "tulospalvelu-ekv-2023"
        )
        urls = {r["url"] for r in cfg["resources"]}
        assert (
            "https://tulospalvelu.vaalit.fi/EKV-2023/ekv-2023_ehd_maa.csv.zip"
            in urls
        )
        assert (
            "https://tulospalvelu.vaalit.fi/EKV-2023/ekv-2023_alu_maa.xml.zip"
            in urls
        )

    def test_files_are_not_under_fi_directory(self) -> None:
        """fi/-polku palauttaa 404 — kaava on juuressa."""
        for cfg in TulospalveluHarvester.datasets_config:
            for r in cfg["resources"]:
                assert "/fi/" not in r["url"], r["url"]

    def test_all_levels_present(self) -> None:
        cfg = TulospalveluHarvester.datasets_config[0]
        urls = " ".join(r["url"] for r in cfg["resources"])
        assert "_ehd_maa." in urls
        assert "_puo_maa." in urls
        assert "_alu_maa." in urls


class TestHarvest:
    async def test_harvest_writes_eleven_datasets(self) -> None:
        conn = _memory_db()
        h = TulospalveluHarvester(conn=conn)
        count = await h.harvest()
        assert count == 11
        rows = conn.execute(
            "SELECT COUNT(*) c FROM datasets WHERE source = 'tulospalvelu'"
        ).fetchone()
        assert rows["c"] == 11

    async def test_licence_is_open(self) -> None:
        conn = _memory_db()
        h = TulospalveluHarvester(conn=conn)
        await h.harvest()
        row = conn.execute(
            "SELECT license_id FROM datasets WHERE id = 'tulospalvelu-ekv-2023'"
        ).fetchone()
        assert row["license_id"] == "CC-BY-4.0"
```

Huom: `pytest.ini`/`pyproject.toml` asettaa `asyncio_mode`; jos `async def` -testit eivät aja, lisää `@pytest.mark.asyncio` -dekoraattori ja `import pytest` kuten `tests/test_valtiokonttori.py`:ssä.

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `source .venv/bin/activate && pytest tests/test_tulospalvelu.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.harvesters.tulospalvelu'`

- [ ] **Step 3: Kirjoita harvesteri**

Luo `src/aura/harvesters/tulospalvelu.py`:

```python
"""Harvester oikeusministeriön vaalitulospalvelulle."""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

BASE = "https://tulospalvelu.vaalit.fi"

# Tulostasot: ehdokkaat, puolueet ja valitsijayhdistykset, alueet
_LEVELS = [
    ("ehd", "ehdokaskohtaiset tulokset"),
    ("puo", "puolueiden ja valitsijayhdistysten tulokset"),
    ("alu", "aluekohtaiset tulokset"),
]

_FORMATS = ["csv", "xml"]

# Vain vaalit joilla on varmennettu lataus. Etusivu listaa 15 vaalia,
# mutta EKV-2011:llä on sivu ilman CSV:tä ja presidentinvaaleilla (TPV)
# ei ole latauksia lainkaan. Varmennettu 2026-07-29 HTTP-vastauksista.
_ELECTIONS: list[dict[str, Any]] = [
    {"code": "EKV-2019", "title": "Eduskuntavaalit 2019",
     "keywords": ["eduskuntavaalit", "2019"]},
    {"code": "EKV-2023", "title": "Eduskuntavaalit 2023",
     "keywords": ["eduskuntavaalit", "2023"]},
    {"code": "KV-2012", "title": "Kuntavaalit 2012",
     "keywords": ["kuntavaalit", "2012"]},
    {"code": "KV-2017", "title": "Kuntavaalit 2017",
     "keywords": ["kuntavaalit", "2017"]},
    {"code": "KV-2021", "title": "Kuntavaalit 2021",
     "keywords": ["kuntavaalit", "2021"]},
    {"code": "KV-2025", "title": "Kuntavaalit 2025",
     "keywords": ["kuntavaalit", "2025"]},
    {"code": "AV-2022", "title": "Aluevaalit 2022",
     "keywords": ["aluevaalit", "hyvinvointialue", "2022"]},
    {"code": "AV-2025", "title": "Aluevaalit 2025",
     "keywords": ["aluevaalit", "hyvinvointialue", "2025"]},
    {"code": "EPV-2014", "title": "Europarlamenttivaalit 2014",
     "keywords": ["europarlamenttivaalit", "EU-vaalit", "2014"]},
    {"code": "EPV-2019", "title": "Europarlamenttivaalit 2019",
     "keywords": ["europarlamenttivaalit", "EU-vaalit", "2019"]},
    {"code": "EPV-2024", "title": "Europarlamenttivaalit 2024",
     "keywords": ["europarlamenttivaalit", "EU-vaalit", "2024"]},
]


def _election_dataset(election: dict[str, Any]) -> dict[str, Any]:
    """Luo yhden vaalin tulosdatasetin konfiguraatio."""
    code = election["code"]
    low = code.lower()
    title = election["title"]

    # Tiedostot ovat vaalihakemiston juuressa. fi/-alihakemisto sisältää
    # vain HTML-sivut ja palauttaa latauksille 404.
    resources = [
        {
            "id": f"tulospalvelu-{low}-{level}-{fmt}",
            "name": f"{title} — {label} ({fmt.upper()})",
            "name_fi": f"{title} — {label} ({fmt.upper()})",
            "format": "ZIP",
            "url": f"{BASE}/{code}/{low}_{level}_maa.{fmt}.zip",
        }
        for level, label in _LEVELS
        for fmt in _FORMATS
    ]

    return {
        "id": f"tulospalvelu-{low}",
        "title": f"{title} — viralliset tulokset",
        "notes_fi": (
            f"{title}: oikeusministeriön viralliset vaalitulokset "
            "ehdokas-, puolue- ja aluetasolla. Aluetason tulokset ulottuvat "
            "äänestysaluetasolle asti. Saatavilla sekä CSV- että "
            "XML-muodossa zipattuna. Skeemakuvaukset ja kenttäselitteet "
            "löytyvät tulospalvelun ohjesivulta. "
            "Lähde: tulospalvelu.vaalit.fi (oikeusministeriö)."
        ),
        "keywords_fi": [
            "vaalitulokset", "vaalit", "äänestys", "ehdokkaat", "puolueet",
            "oikeusministeriö", *election["keywords"],
        ],
        "resources": resources,
    }


class TulospalveluHarvester(StaticHarvester):
    """Kerää oikeusministeriön vaalitulospalvelun tulostiedostot.

    Tulospalvelu julkaisee jokaisen vaalin viralliset tulokset kolmella
    tasolla (ehdokkaat, puolueet, alueet) sekä CSV- että XML-muodossa.
    Aineisto täydentää Tilastokeskuksen vaalitilastoja alkuperäisillä
    tulostiedostoilla.

    Käyttöehto sivustolla: "Tiedot ovat julkisia ja vapaasti käytettävissä."
    """

    name = "tulospalvelu"
    description = "Oikeusministeriön vaalitulospalvelu — viralliset vaalitulokset"
    url = "https://tulospalvelu.vaalit.fi"
    default_update_frequency = "vaaleittain"
    org_id = "oikeusministerio"
    org_name = "oikeusministerio"
    org_title = "Oikeusministeriö"

    datasets_config = [_election_dataset(e) for e in _ELECTIONS]
```

- [ ] **Step 4: Rekisteröi harvesteri**

Muokkaa `src/aura/harvesters/__init__.py`. Lisää import aakkosjärjestykseen (`traficom`-importin jälkeen):

```python
from aura.harvesters.tulospalvelu import TulospalveluHarvester
```

Lisää `HARVESTERS`-dictiin `"vaalirahoitus"`-rivin viereen:

```python
    "tulospalvelu": TulospalveluHarvester,
```

- [ ] **Step 5: Aja testit ja varmista että ne menevät läpi**

Run: `source .venv/bin/activate && pytest tests/test_tulospalvelu.py -v`
Expected: PASS, 9 testiä.

- [ ] **Step 6: Varmista ettei rekisteröinti riko muita testejä**

Run: `source .venv/bin/activate && pytest tests/ -q -x`
Expected: PASS, kaikki (1038 + uudet).

- [ ] **Step 7: Commit**

```bash
git add src/aura/harvesters/tulospalvelu.py src/aura/harvesters/__init__.py tests/test_tulospalvelu.py
git commit -m "feat: oikeusministeriön vaalitulospalvelu harvesteriksi

11 vaalia, kussakin ehdokas-, puolue- ja aluetason tulokset CSV:nä ja
XML:nä. Etusivu listaa 15 vaalia, mutta EKV-2011:llä ei ole CSV:tä ja
presidentinvaaleilla ei latauksia lainkaan — mukana vain varmennetut."
```

---

### Task 3: EduskuntaHarvester

**Files:**
- Create: `src/aura/harvesters/eduskunta.py`
- Modify: `src/aura/harvesters/__init__.py`
- Test: `tests/test_eduskunta.py`

**Interfaces:**
- Consumes: `BaseHarvester._make_client()`, `BaseHarvester._fetch(client, url)`, `BaseHarvester._make_dataset(**kwargs)` (`src/aura/harvesters/base.py`)
- Produces: `EduskuntaHarvester` rekisteröitynä nimellä `"eduskunta"`; metodi `_measure_rows(client, table) -> int`

**Taustatieto — lue tämä ennen toteutusta:**

API on `https://avoindata.eduskunta.fi/api/v1/tables/{Taulu}/rows?perPage=100&page=0`. Sivunumerointi alkaa nollasta. Vastaus on JSON, jossa `columnNames`, `rowData` (lista listoja) ja `hasMore` (bool).

**Endpoint `/api/v1/tables/counts` ei kerro taulujen rivimääriä.** Se palauttaa `rowCount`-kentän, joka väitti `SaliDBAanestys`-taulun kooksi 96, kun todellinen koko on ~43 500, ja `SeatingOfParliament`-taulua tyhjäksi, vaikka siinä on yli 100 riviä. Älä käytä sitä.

Koko selvitetään bisektoimalla sivunumeroa: etsi suurin sivu jolla on rivejä, ja laske `sivu * 100 + kyseisen sivun rivimäärä`.

- [ ] **Step 1: Kirjoita kaatuva testi bisektoinnille**

Luo `tests/test_eduskunta.py`:

```python
"""Testit eduskunnan avoimen datan harvesterille."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.eduskunta import PAGE_SIZE, EduskuntaHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _mock_client(sizes: dict[str, int]) -> AsyncMock:
    """Mock joka simuloi sivutettua API:a annetuilla taulukoilla.

    sizes: {taulun nimi: rivimäärä}
    """
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()

        table = url.split("/tables/")[1].split("/")[0]
        page = int(url.split("page=")[1].split("&")[0])
        total = sizes.get(table, 0)

        start = page * PAGE_SIZE
        n = max(0, min(PAGE_SIZE, total - start))
        resp.json.return_value = {
            "columnNames": ["a", "b"],
            "rowData": [["x", "y"] for _ in range(n)],
            "hasMore": start + n < total,
        }
        return resp

    client.get = AsyncMock(side_effect=mock_get)
    return client


class TestMeasureRows:
    """Bisektointi löytää todellisen rivimäärän."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("total", [0, 1, 99, 100, 101, 2677, 43512, 347655])
    async def test_measures_exact_size(self, total: int) -> None:
        h = EduskuntaHarvester(conn=_memory_db())
        client = _mock_client({"T": total})
        assert await h._measure_rows(client, "T") == total

    @pytest.mark.asyncio
    async def test_does_not_call_counts_endpoint(self) -> None:
        """/counts valehtelee — sitä ei saa käyttää."""
        h = EduskuntaHarvester(conn=_memory_db())
        client = _mock_client({"T": 5000})
        await h._measure_rows(client, "T")
        called = [c.args[0] for c in client.get.call_args_list]
        assert not any("counts" in u for u in called)

    @pytest.mark.asyncio
    async def test_bisection_is_logarithmic(self) -> None:
        """Bisektointi ei saa selata sivuja yksitellen."""
        h = EduskuntaHarvester(conn=_memory_db())
        client = _mock_client({"T": 347655})
        await h._measure_rows(client, "T")
        assert client.get.call_count < 40


class TestDatasets:
    def test_seven_datasets(self) -> None:
        assert len(EduskuntaHarvester.DATASETS) == 7

    def test_excludes_empty_tables(self) -> None:
        """HetekaData ja SaliDBMessageLog ovat tyhjiä, PrimaryKeys teknistä."""
        tables = {
            t for d in EduskuntaHarvester.DATASETS for t in d["tables"]
        }
        assert "HetekaData" not in tables
        assert "SaliDBMessageLog" not in tables
        assert "PrimaryKeys" not in tables

    def test_covers_sixteen_tables(self) -> None:
        tables = {
            t for d in EduskuntaHarvester.DATASETS for t in d["tables"]
        }
        assert len(tables) == 16

    def test_includes_tables_counts_endpoint_calls_empty(self) -> None:
        """/counts väitti näitä tyhjiksi mutta niissä on rivejä."""
        tables = {
            t for d in EduskuntaHarvester.DATASETS for t in d["tables"]
        }
        assert "SeatingOfParliament" in tables
        assert "SaliDBAanestysKieli" in tables


class TestHarvest:
    @pytest.mark.asyncio
    async def test_harvest_creates_seven_datasets(self) -> None:
        conn = _memory_db()
        h = EduskuntaHarvester(conn=conn)
        client = _mock_client({"MemberOfParliament": 2677, "VaskiData": 347655})

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 7
        row = conn.execute(
            "SELECT COUNT(*) c FROM datasets WHERE source = 'eduskunta'"
        ).fetchone()
        assert row["c"] == 7

    @pytest.mark.asyncio
    async def test_measured_size_appears_in_notes(self) -> None:
        conn = _memory_db()
        h = EduskuntaHarvester(conn=conn)
        client = _mock_client({"MemberOfParliament": 2677})

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT notes_fi FROM datasets WHERE id = 'eduskunta-kansanedustajat'"
        ).fetchone()
        assert "2 677" in row["notes_fi"] or "2677" in row["notes_fi"]

    @pytest.mark.asyncio
    async def test_resource_urls_point_at_tables(self) -> None:
        conn = _memory_db()
        h = EduskuntaHarvester(conn=conn)
        client = _mock_client({})

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        urls = [
            r["url"] for r in conn.execute(
                "SELECT url FROM resources WHERE dataset_id = 'eduskunta-asiakirjat'"
            )
        ]
        assert (
            "https://avoindata.eduskunta.fi/api/v1/tables/VaskiData/rows" in urls
        )
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `source .venv/bin/activate && pytest tests/test_eduskunta.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.harvesters.eduskunta'`

- [ ] **Step 3: Kirjoita harvesteri**

Luo `src/aura/harvesters/eduskunta.py`:

```python
"""Harvester eduskunnan avoimelle datalle."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

API = "https://avoindata.eduskunta.fi/api/v1/tables"
PAGE_SIZE = 100

# Bisektoinnin yläraja. Suurin taulu (VaskiData) on ~348 000 riviä, joten
# miljoona ylittää sen kolminkertaisesti. Raja on olemassa vain siltä
# varalta että API alkaa palauttaa rivejä loputtomiin.
MAX_ROWS = 1_000_000

# Kuratoidut aineistot. Aineisto vastaa käyttötarkoitusta, ei API:n
# taulurakennetta: 19 taulusta 16 on sisällöllisiä, ja ne ryhmitellään
# seitsemäksi aineistoksi.
#
# Pois jätetyt: HetekaData ja SaliDBMessageLog ovat aidosti tyhjiä
# (varmennettu hakemalla sivu 0), PrimaryKeys (23 riviä) on teknistä
# metatietoa.
DATASETS: list[dict[str, Any]] = [
    {
        "id": "eduskunta-kansanedustajat",
        "title": "Kansanedustajat",
        "tables": ["MemberOfParliament", "SeatingOfParliament"],
        "notes_fi": (
            "Kansanedustajien perustiedot: nimi, eduskuntaryhmä, "
            "ministeriys sekä laaja XML-muotoinen henkilökuvaus "
            "(elämäkerta, toimikaudet, valiokuntajäsenyydet). Mukana myös "
            "istuntosalin istumajärjestys."
        ),
        "keywords_fi": [
            "kansanedustajat", "eduskunta", "edustajat", "eduskuntaryhmät",
            "ministerit", "politiikka",
        ],
    },
    {
        "id": "eduskunta-aanestykset",
        "title": "Täysistuntojen äänestykset",
        "tables": [
            "SaliDBAanestys", "SaliDBAanestysJakauma",
            "SaliDBAanestysAsiakirja", "SaliDBAanestysKieli",
        ],
        "notes_fi": (
            "Täysistuntojen äänestykset vuodesta 1996 alkaen: äänestyksen "
            "otsikko, käsittelyvaihe, tulos (jaa/ei/tyhjiä/poissa) sekä "
            "linkki pöytäkirjaan ja valtiopäiväasiaan. Äänijakaumat "
            "eduskuntaryhmittäin omana tauluna."
        ),
        "keywords_fi": [
            "äänestykset", "täysistunto", "eduskunta", "äänestystulokset",
            "politiikka", "lainsäädäntö",
        ],
    },
    {
        "id": "eduskunta-aanestykset-edustajittain",
        "title": "Äänestykset edustajittain",
        "tables": ["SaliDBAanestysEdustaja"],
        "notes_fi": (
            "Yksittäisen kansanedustajan ääni jokaisessa täysistunnon "
            "äänestyksessä: edustajan nimi, henkilönumero, "
            "eduskuntaryhmä ja annettu ääni. Yhdistettävissä "
            "äänestysaineistoon AanestysId-kentällä."
        ),
        "keywords_fi": [
            "äänestykset", "kansanedustajat", "äänestyskäyttäytyminen",
            "eduskunta", "politiikka",
        ],
    },
    {
        "id": "eduskunta-puheenvuorot",
        "title": "Täysistuntojen puheenvuorot",
        "tables": ["SaliDBPuheenvuoro"],
        "notes_fi": (
            "Täysistuntojen puheenvuorot: puhuja, eduskuntaryhmä, "
            "ministeriys, puheenvuoron tyyppi ja ajankohta sekä "
            "XML-muotoinen puheen sisältö."
        ),
        "keywords_fi": [
            "puheenvuorot", "täysistunto", "eduskunta", "puheet",
            "kansanedustajat", "politiikka",
        ],
    },
    {
        "id": "eduskunta-istunnot",
        "title": "Täysistunnot ja käsittelykohdat",
        "tables": [
            "SaliDBIstunto", "SaliDBKohta", "SaliDBKohtaAanestys",
            "SaliDBKohtaAsiakirja", "SaliDBTiedote",
        ],
        "notes_fi": (
            "Täysistuntojen rakenne: istunnot, käsittelykohdat ja niiden "
            "kytkennät äänestyksiin ja asiakirjoihin. Mukana myös "
            "täysistuntotiedotteet."
        ),
        "keywords_fi": [
            "täysistunto", "istunnot", "eduskunta", "esityslista",
            "valtiopäivät", "politiikka",
        ],
    },
    {
        "id": "eduskunta-asiakirjat",
        "title": "Valtiopäiväasiakirjat",
        "tables": ["VaskiData"],
        "notes_fi": (
            "Kaikki valtiopäiväasiakirjat XML-muodossa: hallituksen "
            "esitykset, valiokuntamietinnöt, kirjalliset kysymykset, "
            "lakialoitteet ja pöytäkirjat. Jokaisella asiakirjalla on "
            "eduskuntatunnus (esim. 'HE 1/2023 vp')."
        ),
        "keywords_fi": [
            "valtiopäiväasiakirjat", "hallituksen esitykset",
            "kirjalliset kysymykset", "lakialoitteet", "valiokunnat",
            "eduskunta", "lainsäädäntö",
        ],
    },
    {
        "id": "eduskunta-liitteet",
        "title": "Asiakirjojen liitteet",
        "tables": ["Attachment", "AttachmentGroup"],
        "notes_fi": (
            "Valtiopäiväasiakirjoihin liittyvät liitetiedostot ja niiden "
            "ryhmittely. Kytkeytyy asiakirja-aineistoon "
            "AttachmentGroupId-kentällä."
        ),
        "keywords_fi": [
            "liitteet", "valtiopäiväasiakirjat", "eduskunta",
        ],
    },
]


class EduskuntaHarvester(BaseHarvester):
    """Kerää eduskunnan avoimen datan rajapinnan aineistot.

    Eduskunta julkaisee täysistuntojen äänestykset, puheenvuorot,
    kansanedustajatiedot ja kaikki valtiopäiväasiakirjat sivutettuna
    JSON-rajapintana. Rajapinta ei vaadi avainta.

    Rivimäärät mitataan bisektoimalla sivutusta — katso ``_measure_rows``.
    """

    name = "eduskunta"
    description = "Eduskunnan avoin data — äänestykset, puheenvuorot, asiakirjat"
    url = "https://avoindata.eduskunta.fi"

    DATASETS = DATASETS

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "api",
            "query_protocol": "rest",
            "api_base_url": API,
        })
        return config

    async def _page_rows(
        self, client: httpx.AsyncClient, table: str, page: int
    ) -> int:
        """Palauta rivimäärä yhdeltä sivulta."""
        url = f"{API}/{table}/rows?perPage={PAGE_SIZE}&page={page}"
        response = await self._fetch(client, url)
        data = response.json()
        rows = data.get("rowData") or []
        return len(rows)

    async def _measure_rows(
        self, client: httpx.AsyncClient, table: str
    ) -> int:
        """Mittaa taulun rivimäärä bisektoimalla sivunumeroa.

        ÄLÄ korvaa tätä /api/v1/tables/counts -kutsulla. Se on yksi pyyntö
        272:n sijaan, mutta se ei palauta taulun rivimäärää: se väitti
        SaliDBAanestys-taulun kooksi 96 (todellinen ~43 500) ja
        SeatingOfParliament-taulua tyhjäksi (todellisuudessa rivejä on).
        Todennäköisesti se kertoo viimeksi tuoduista riveistä.
        """
        first = await self._page_rows(client, table, 0)
        if first == 0:
            return 0
        if first < PAGE_SIZE:
            return first

        # Etsi suurin sivu jolla on rivejä.
        lo = 0
        hi = MAX_ROWS // PAGE_SIZE
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if await self._page_rows(client, table, mid) > 0:
                lo = mid
            else:
                hi = mid

        last = await self._page_rows(client, table, lo)
        return lo * PAGE_SIZE + last

    async def harvest(self) -> int:
        count = 0
        async with self._make_client() as client:
            for cfg in self.DATASETS:
                sizes: dict[str, int] = {}
                for table in cfg["tables"]:
                    try:
                        sizes[table] = await self._measure_rows(client, table)
                    except (httpx.HTTPError, ValueError, KeyError) as exc:
                        # Yksittäisen taulun mittaus ei saa kaataa koko ajoa,
                        # mutta se ei myöskään saa kadota hiljaisesti.
                        logger.warning(
                            "[%s] Taulun %s koon mittaus epäonnistui: %s",
                            self.name, table, exc,
                        )

                resources = [
                    Resource(
                        id=f"{cfg['id']}-{table.lower()}",
                        name=f"{table} (JSON-rajapinta)",
                        name_fi=f"{table} — JSON-rajapinta",
                        format="API",
                        url=f"{API}/{table}/rows",
                    )
                    for table in cfg["tables"]
                ]

                measured = ", ".join(
                    f"{t}: {n:,} riviä".replace(",", " ")
                    for t, n in sizes.items()
                )
                notes = cfg["notes_fi"]
                if measured:
                    notes = f"{notes} Mitatut rivimäärät: {measured}."

                dataset = self._make_dataset(
                    id=cfg["id"],
                    name=cfg["id"],
                    title=cfg["title"],
                    title_fi=cfg["title"],
                    notes_fi=notes,
                    organization_id="eduskunta",
                    organization_name="eduskunta",
                    organization_title="Eduskunta",
                    keywords_fi=cfg["keywords_fi"],
                    update_frequency="päivittäin",
                    num_resources=len(resources),
                    resources=resources,
                )
                upsert_dataset(self.conn, dataset)
                count += 1

        self.conn.commit()
        logger.info("[%s] Harvest valmis: %d datasettiä", self.name, count)
        return count
```

- [ ] **Step 4: Rekisteröi harvesteri**

Muokkaa `src/aura/harvesters/__init__.py`. Lisää import (`digitransit`-importin jälkeen, aakkosjärjestykseen):

```python
from aura.harvesters.eduskunta import EduskuntaHarvester
```

Lisää `HARVESTERS`-dictiin:

```python
    "eduskunta": EduskuntaHarvester,
```

- [ ] **Step 5: Aja testit ja varmista että ne menevät läpi**

Run: `source .venv/bin/activate && pytest tests/test_eduskunta.py -v`
Expected: PASS, 17 testiä (8 parametrisoitua `test_measures_exact_size`
+ 9 muuta).

- [ ] **Step 6: Aja koko sarja ja tyyppitarkistus**

Run: `source .venv/bin/activate && pytest tests/ -q && mypy src/aura 2>&1 | tail -3`
Expected: kaikki testit PASS; mypy enintään 5 virhettä (lähtötaso).

- [ ] **Step 7: Commit**

```bash
git add src/aura/harvesters/eduskunta.py src/aura/harvesters/__init__.py tests/test_eduskunta.py
git commit -m "feat: eduskunnan avoin data harvesteriksi

Seitsemän kuratoitua aineistoa kattaen 16 sisällöllistä taulua:
äänestykset vuodesta 1996, puheenvuorot, kansanedustajat ja kaikki
valtiopäiväasiakirjat.

Rivimäärät mitataan bisektoimalla, ei /counts-endpointista: se väitti
43 500 rivin taulun kooksi 96 ja yhtä sisällöllistä taulua tyhjäksi."
```

---

### Task 4: PohtivaHarvester

**Files:**
- Create: `src/aura/harvesters/pohtiva.py`
- Modify: `src/aura/harvesters/__init__.py`
- Test: `tests/test_pohtiva.py`

**Interfaces:**
- Consumes: `BaseHarvester._make_client()`, `BaseHarvester._fetch(client, url)`, `BaseHarvester._make_dataset(**kwargs)`
- Produces: `PohtivaHarvester` rekisteröitynä nimellä `"pohtiva"`; funktiot `parse_party_codes(html) -> list[str]` ja `parse_programmes(html) -> list[dict]`

**Taustatieto:** Puoluelista on `https://www.fsd.tuni.fi/pohtiva/ohjelmalistat`, puoluesivu `/ohjelmalistat/{KOODI}`. Puoluesivu on HTML-taulukko, jonka sarakkeet ovat Otsikko (linkki), Puolue, Vuosi, Tyyppi, Kieli. Alla olevat regexit on **validoitu oikeaa sivua vasten 2026-07-30**: VIHR-sivulla ne osuvat 169 riviin, mikä täsmää sivun omaan ilmoitukseen "Yhteensä 169 ohjelmaa". Puoluelistalta löytyy 96 koodia.

HTML on epämuodostunutta — `<tr>`-elementtejä ei suljeta. Siksi regex kohdistuu solujen sarjaan eikä riviin.

**Lisenssi jätetään tyhjäksi.** `_make_dataset()` asettaisi oletuksena `license_id="cc-by-4.0"`. POHTIVAn sivuilla ei mainita uudelleenkäytön ehtoja lainkaan, vain viittausohje, joten oletusta ei saa jättää voimaan.

- [ ] **Step 1: Kirjoita kaatuva testi jäsentimille**

Luo `tests/test_pohtiva.py`:

```python
"""Testit POHTIVA-harvesterille (puolueohjelmat)."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.pohtiva import (
    PohtivaHarvester,
    parse_party_codes,
    parse_programmes,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


PARTY_LIST_HTML = """
<main>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/KOK">Kansallinen kokoomus</a>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR">Vihreä liitto</a>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/SDP">SDP</a>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat">Takaisin</a>
</main>
"""

# Rakenne kopioitu oikealta VIHR-sivulta: <tr> jää sulkematta.
PROGRAMME_HTML = """
<tbody>
  <tr>
     <td>
        <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR/1563">
        Aluevaaliohjelma 2025 - Arki ratkaisee
        </a>
     </td>
     <td>Vihre&auml; liitto</td>
     <td>2025</td>
     <td>vaaliohjelma</td>
     <td>FI</td>
  <tr>
     <td>
        <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR/1526">
        Elinkeinopoliittinen ohjelma
        </a>
     </td>
     <td>Vihre&auml; liitto</td>
     <td>2023</td>
     <td>erityisohjelma</td>
     <td>FI</td>
</tbody>
"""


class TestParsePartyCodes:
    def test_finds_codes(self) -> None:
        assert parse_party_codes(PARTY_LIST_HTML) == ["KOK", "SDP", "VIHR"]

    def test_ignores_list_page_itself(self) -> None:
        """Takaisin-linkki osoittaa listasivulle — se ei ole puoluekoodi."""
        assert "ohjelmalistat" not in parse_party_codes(PARTY_LIST_HTML)

    def test_empty_html_yields_nothing(self) -> None:
        assert parse_party_codes("<html></html>") == []


class TestParseProgrammes:
    def test_finds_both_programmes(self) -> None:
        assert len(parse_programmes(PROGRAMME_HTML)) == 2

    def test_extracts_all_fields(self) -> None:
        first = parse_programmes(PROGRAMME_HTML)[0]
        assert first["party"] == "VIHR"
        assert first["pid"] == "1563"
        assert first["title"] == "Aluevaaliohjelma 2025 - Arki ratkaisee"
        assert first["party_name"] == "Vihreä liitto"
        assert first["year"] == "2025"
        assert first["ptype"] == "vaaliohjelma"

    def test_unescapes_html_entities(self) -> None:
        """&auml; pitää muuttua ä:ksi."""
        assert parse_programmes(PROGRAMME_HTML)[0]["party_name"] == "Vihreä liitto"

    def test_malformed_html_does_not_crash(self) -> None:
        assert parse_programmes("<tbody><tr><td>rikki") == []


def _mock_client() -> AsyncMock:
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.rstrip("/").endswith("ohjelmalistat"):
            resp.text = PARTY_LIST_HTML
        else:
            resp.text = PROGRAMME_HTML
        return resp

    client.get = AsyncMock(side_effect=mock_get)
    return client


class TestHarvest:
    @pytest.mark.asyncio
    async def test_creates_dataset_per_programme(self) -> None:
        """3 puoluetta × 2 ohjelmaa = 6 aineistoa."""
        conn = _memory_db()
        h = PohtivaHarvester(conn=conn)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=_mock_client())
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await h.harvest()

        assert count == 6

    @pytest.mark.asyncio
    async def test_dataset_id_format(self) -> None:
        conn = _memory_db()
        h = PohtivaHarvester(conn=conn)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=_mock_client())
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT title_fi FROM datasets WHERE id = 'pohtiva-vihr-1563'"
        ).fetchone()
        assert row is not None
        assert row["title_fi"] == "Aluevaaliohjelma 2025 - Arki ratkaisee"

    @pytest.mark.asyncio
    async def test_licence_is_left_empty(self) -> None:
        """POHTIVA ei ilmoita lisenssiä — sitä ei saa keksiä."""
        conn = _memory_db()
        h = PohtivaHarvester(conn=conn)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=_mock_client())
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT license_id, license_title FROM datasets "
            "WHERE id = 'pohtiva-vihr-1563'"
        ).fetchone()
        assert row["license_id"] == ""
        assert row["license_title"] == ""

    @pytest.mark.asyncio
    async def test_resource_links_to_programme_page(self) -> None:
        conn = _memory_db()
        h = PohtivaHarvester(conn=conn)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=_mock_client())
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT url, format FROM resources WHERE dataset_id = 'pohtiva-vihr-1563'"
        ).fetchone()
        assert row["url"] == (
            "https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR/1563"
        )
        assert row["format"] == "HTML"

    @pytest.mark.asyncio
    async def test_keywords_include_party_and_type(self) -> None:
        conn = _memory_db()
        h = PohtivaHarvester(conn=conn)

        with patch.object(h, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=_mock_client())
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await h.harvest()

        row = conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'pohtiva-vihr-1563'"
        ).fetchone()
        kw = row["keywords_fi"]
        assert "puolueohjelma" in kw
        assert "vaaliohjelma" in kw
        assert "Vihreä liitto" in kw
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `source .venv/bin/activate && pytest tests/test_pohtiva.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.harvesters.pohtiva'`

- [ ] **Step 3: Kirjoita harvesteri**

Luo `src/aura/harvesters/pohtiva.py`:

```python
"""Harvester POHTIVAlle — poliittisten ohjelmien tietovaranto."""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Resource

logger = logging.getLogger(__name__)

BASE = "https://www.fsd.tuni.fi/pohtiva"
LIST_URL = f"{BASE}/ohjelmalistat"

# Puoluekoodit listasivulta. Listasivu linkittää myös itseensä
# ("Takaisin"), joten pelkkä /ohjelmalistat ilman koodia suodatetaan pois
# vaatimalla vähintään yksi merkki koodille.
_PARTY_RE = re.compile(
    r'href="https://www\.fsd\.tuni\.fi/pohtiva/ohjelmalistat/([A-Za-zÅÄÖåäö0-9]+)"'
)

# Ohjelmarivi puoluesivun taulukosta. Sarakkeet: Otsikko (linkki), Puolue,
# Vuosi, Tyyppi, Kieli.
#
# Sivun HTML on epämuodostunutta — <tr>-elementtejä ei suljeta — joten
# regex kohdistuu solujen sarjaan eikä <tr>-lohkoon. Validoitu oikeaa
# VIHR-sivua vasten 2026-07-30: 169 osumaa, mikä täsmää sivun omaan
# ilmoitukseen "Yhteensä 169 ohjelmaa".
_PROGRAMME_RE = re.compile(
    r'<a href="[^"]*ohjelmalistat/(?P<party>[^/"]+)/(?P<pid>\d+)"\s*>\s*'
    r'(?P<title>.*?)\s*</a>\s*</td>\s*'
    r'<td>(?P<party_name>[^<]*)</td>\s*'
    r'<td>(?P<year>[^<]*)</td>\s*'
    r'<td>(?P<ptype>[^<]*)</td>\s*'
    r'<td>(?P<lang>[^<]*)</td>',
    re.S,
)


def parse_party_codes(page: str) -> list[str]:
    """Poimi puoluekoodit listasivulta, järjestettynä ja uniikkeina."""
    return sorted(set(_PARTY_RE.findall(page)))


def parse_programmes(page: str) -> list[dict[str, str]]:
    """Poimi ohjelmat puoluesivun taulukosta."""
    programmes = []
    for match in _PROGRAMME_RE.finditer(page):
        row = {k: html.unescape(v).strip() for k, v in match.groupdict().items()}
        programmes.append(row)
    return programmes


class PohtivaHarvester(BaseHarvester):
    """Kerää POHTIVAn puolueohjelmien metatiedot.

    POHTIVA on Yhteiskuntatieteellisen tietoarkiston ylläpitämä
    poliittisten ohjelmien tietovaranto: 1 583 ohjelmaa vuosilta
    1880–2025, 95 puolueelta.

    Rajapintaa ei ole, joten metatiedot luetaan puoluesivujen
    HTML-taulukoista. Koko aineiston metatiedot saa 96 pyynnöllä —
    yksittäisiä ohjelmasivuja ei haeta.

    **Ohjelmatekstejä ei kopioida.** Aura tallentaa metatiedot ja linkin.
    """

    name = "pohtiva"
    description = "POHTIVA — poliittisten ohjelmien tietovaranto (Tietoarkisto)"
    url = LIST_URL
    # POHTIVA on pieni yliopistopalvelu, ei tuotantorajapinta. Väljempi
    # viive kuin oletus, koska peräkkäisiä pyyntöjä on lähes sata.
    request_delay = 0.5

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "scrape",
            "query_protocol": "html",
        })
        return config

    async def harvest(self) -> int:
        count = 0
        async with self._make_client() as client:
            response = await self._fetch(client, LIST_URL)
            codes = parse_party_codes(response.text)
            logger.info("[%s] Löytyi %d puoluekoodia", self.name, len(codes))

            for code in codes:
                try:
                    page = await self._fetch(client, f"{LIST_URL}/{code}")
                except httpx.HTTPError as exc:
                    # Yksittäisen puolueen epäonnistuminen ei saa kaataa
                    # koko ajoa, mutta se ei saa myöskään kadota.
                    logger.warning(
                        "[%s] Puolueen %s sivu epäonnistui: %s",
                        self.name, code, exc,
                    )
                    continue

                for prog in parse_programmes(page.text):
                    self._store(prog)
                    count += 1

        self.conn.commit()
        logger.info("[%s] Harvest valmis: %d ohjelmaa", self.name, count)
        return count

    def _store(self, prog: dict[str, str]) -> None:
        """Tallenna yksi ohjelma datasettinä."""
        party = prog["party"]
        pid = prog["pid"]
        ds_id = f"pohtiva-{party.lower()}-{pid}"
        url = f"{LIST_URL}/{party}/{pid}"

        keywords = ["puolueohjelma", "politiikka", party]
        if prog.get("party_name"):
            keywords.append(prog["party_name"])
        if prog.get("ptype"):
            keywords.append(prog["ptype"])
        if prog.get("year"):
            keywords.append(prog["year"])

        year = prog.get("year", "")
        suffix = f" ({year})" if year else ""
        notes = (
            f"{prog['party_name']}: {prog['title']}{suffix}. "
            "Puolueohjelman metatiedot POHTIVAsta. Ohjelman teksti "
            "luettavissa linkin takaa. Tekijänoikeus on puolueella; "
            "aineistoa ylläpitää Yhteiskuntatieteellinen tietoarkisto."
        )

        dataset = self._make_dataset(
            id=ds_id,
            name=ds_id,
            title=prog["title"],
            title_fi=prog["title"],
            notes_fi=notes,
            organization_id="fsd",
            organization_name="fsd",
            organization_title="Yhteiskuntatieteellinen tietoarkisto",
            keywords_fi=keywords,
            # POHTIVA ei ilmoita uudelleenkäytön ehtoja, vain viittausohjeen.
            # _make_dataset() asettaisi oletuksena cc-by-4.0, mikä olisi
            # väite jota lähde ei tue.
            license_id="",
            license_title="",
            update_frequency="satunnaisesti",
            num_resources=1,
            resources=[
                Resource(
                    id=f"{ds_id}-html",
                    name=prog["title"],
                    name_fi=prog["title"],
                    format="HTML",
                    url=url,
                )
            ],
        )
        upsert_dataset(self.conn, dataset)
```

- [ ] **Step 4: Rekisteröi harvesteri**

Muokkaa `src/aura/harvesters/__init__.py`. Lisää import (`paituli`-importin jälkeen, aakkosjärjestykseen):

```python
from aura.harvesters.pohtiva import PohtivaHarvester
```

Lisää `HARVESTERS`-dictiin:

```python
    "pohtiva": PohtivaHarvester,
```

- [ ] **Step 5: Aja testit ja varmista että ne menevät läpi**

Run: `source .venv/bin/activate && pytest tests/test_pohtiva.py -v`
Expected: PASS, 12 testiä.

- [ ] **Step 6: Aja koko sarja, lintteri ja tyyppitarkistus**

Run: `source .venv/bin/activate && pytest tests/ -q && ruff check src/aura tests && mypy src/aura 2>&1 | tail -3`
Expected: kaikki testit PASS; ruff puhdas; mypy enintään 5 virhettä.

- [ ] **Step 7: Commit**

```bash
git add src/aura/harvesters/pohtiva.py src/aura/harvesters/__init__.py tests/test_pohtiva.py
git commit -m "feat: POHTIVAn puolueohjelmat harvesteriksi

1 583 puolueohjelmaa vuosilta 1880-2025, yksi aineisto per ohjelma.
Metatiedot luetaan puoluesivujen taulukoista; ohjelmatekstejä ei
kopioida.

Lisenssi jätetään tyhjäksi: POHTIVA ei ilmoita uudelleenkäytön ehtoja,
joten _make_dataset():n cc-by-4.0-oletus olisi perusteeton väite."
```

---

### Task 5: Harvestointi ja dokumentaatio

**Files:**
- Modify: `CLAUDE.md` (harvesteripuu ja MCP-taulukko)
- Modify: `CHANGELOG.md` (`## [Unreleased]`)
- Data: `data/aura.db`

**Interfaces:**
- Consumes: kaikki neljä edellistä taskia
- Produces: päivitetty korpus ja dokumentaatio

- [ ] **Step 1: Aja uudet harvesterit**

```bash
source .venv/bin/activate
python -m aura.cli harvest tulospalvelu
python -m aura.cli harvest eduskunta
python -m aura.cli harvest pohtiva
python -m aura.cli harvest vaalirahoitus
```

Odotettu: tulospalvelu 11, eduskunta 7, pohtiva ~1 583, vaalirahoitus 27.

Jos jokin palauttaa nollan, **älä jatka** — se on juuri se hiljainen
nollavika jonka `check_count_regression()` on tarkoitettu havaitsemaan.
Selvitä syy ensin.

- [ ] **Step 2: Indeksoi lemmat ja pisteytä laatu**

```bash
source .venv/bin/activate
python -m aura.cli lemmatize
python -m aura.cli quality
```

Ilman lemmaindeksointia uudet rivit eivät löydy perusmuotohaulla.

- [ ] **Step 3: Tarkista tulos**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('data/aura.db')
for s in ('eduskunta','tulospalvelu','pohtiva','vaalirahoitus'):
    n = c.execute('SELECT COUNT(*) FROM datasets WHERE source=?', (s,)).fetchone()[0]
    print(f'{n:6d}  {s}')
print('yhteensä:', c.execute('SELECT COUNT(*) FROM datasets').fetchone()[0])
"
```

Expected: yhteensä noin 12 800.

- [ ] **Step 4: Kokeile hakua**

```bash
source .venv/bin/activate
python -m aura.cli search "puolueohjelma"
python -m aura.cli search "kansanedustajien äänestykset"
```

Expected: molemmat palauttavat osumia. Ennen tätä työtä `puolueohjelma`
antoi nolla osumaa.

- [ ] **Step 5: Päivitä CLAUDE.md**

Lisää harvesteripuuhun `BaseHarvester`-haaraan:

```
├── EduskuntaHarvester (eduskunta.py) — eduskunnan avoin data
├── PohtivaHarvester (pohtiva.py) — puolueohjelmat (Tietoarkisto)
```

ja `StaticHarvester`-haaraan aakkosjärjestykseen:

```
│   ├── TulospalveluHarvester (tulospalvelu.py) — oikeusministeriön vaalitulokset
```

- [ ] **Step 6: Päivitä CHANGELOG.md**

Lisää `## [Unreleased]`-osion `### Added`-lohkoon:

```markdown
- **Poliittisen datan harvesterit**: eduskunnan avoin data (7 aineistoa,
  16 taulua — äänestykset vuodesta 1996, puheenvuorot, kansanedustajat,
  valtiopäiväasiakirjat), oikeusministeriön vaalitulospalvelu (11 vaalia)
  ja POHTIVAn puolueohjelmat (1 583 ohjelmaa 1880–2025). Ennen tätä haku
  `puolueohjelma` antoi nolla osumaa eikä eduskunnan omaan dataan
  viitannut yksikään resurssi
- Vaalirahoitukseen jälki-ilmoitukset (`E_JI`) neljälle vaalille joilla
  tiedosto on olemassa
```

ja `### Data`-lohkoon:

```markdown
- Korpus 11 202 → ~12 800 datasettiä: kolme uutta poliittisen datan lähdettä
```

- [ ] **Step 7: Commit**

```bash
source .venv/bin/activate
sqlite3 data/aura.db "PRAGMA wal_checkpoint(TRUNCATE);"
git add data/aura.db CLAUDE.md CHANGELOG.md
git commit -m "data: harvestoi eduskunta, tulospalvelu ja POHTIVA

Korpus 11 202 -> ~12 800. Haku 'puolueohjelma' antaa nyt osumia; ennen
se antoi nollan."
```

WAL-checkpoint on pakollinen — ilman sitä git ei näe muutosta
tietokantatiedostossa.

---

## Toteutuksen jälkeen

Kun kaikki viisi taskia on valmiina:

1. Aja `pytest tests/ -q` — kaikkien pitää mennä läpi
2. Aja `mypy src/aura` — enintään 5 virhettä (lähtötaso)
3. Aja `ruff check src/aura tests` — puhdas
4. Harkitse kultaisen setin laajentamista poliittisilla kyselyillä.
   Se on erillinen työ, ja se kannattaa tehdä vasta kun nämä aineistot
   ovat kannassa — muuten uusia kyselyitä ei voi labeloida.
