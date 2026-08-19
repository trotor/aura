# Probe-vaihe — toteutussuunnitelma

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skeema, koordinaatisto, avainkentät ja kutsutapa johdetaan itse
rajapinnasta jokaiselle koneluettavalle resurssille, ja epäonnistuminen kirjataan
näkyviin sen sijaan että se katoaisi.

**Architecture:** Olemassa oleva `aura infer-schemas` siirtyy CLI:stä pakettiin
`src/aura/probe/` ja laajenee WFS:ään, WMS:ään ja PxWebiin. Kukin prober on puhdas
funktio jonka ainoa riippuvuus on HTTP-vastaus; orkestrointi hoitaa kohteiden
valinnan, TTL:n, tahdinsäädön ja jatkamisen. Kirjanpito omaan tauluun, johdettu
tieto olemassa oleviin varastoihin.

**Tech Stack:** Python 3.11+, httpx, sqlite3, pytest, ruff, mypy (strict).

**Spec:** `docs/superpowers/specs/2026-08-19-probe-vaihe-design.md`

## Global Constraints

- Kaikki Python-komennot venvissä: `source .venv/bin/activate`
- Suomi on koodin, docstringien ja committien kieli
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- `ruff check` ja `mypy` (strict) läpi ennen jokaista committia
- Uudet migraatiot: `scripts/migrations/NNN_nimi.sql`, seuraava vapaa numero on **022**
- Enrichmentit kirjoitetaan `add_enrichment(conn, dataset_id, field, value, confidence, source_type, source_detail)`
- Probe-enrichmentien `source_type` on aina `"probe"`
- Ei uusia riippuvuuksia
- Testit eivät saa tehdä verkkokutsuja: jokainen prober testataan tallennetulla vastauksella

---

### Task 1: Kirjanpitotaulu ja tyypit

**Files:**
- Create: `scripts/migrations/022_probe_results.sql`
- Create: `src/aura/probe/__init__.py` (tyhjä toistaiseksi)
- Create: `src/aura/probe/types.py`
- Modify: `src/aura/database.py` (lisää `upsert_probe_result`, `get_probe_result`)
- Modify: `src/aura/prune.py:35-41` (lisää `probe_results` listaan `RELATED_TABLES`)
- Test: `tests/test_probe_results.py`

**Interfaces:**
- Consumes: `aura.database.get_connection`, `run_migrations`, `init_db`
- Produces:
  - `aura.probe.types.ProbeStatus` — merkkijonovakiot `OK`, `HTTP_ERROR`, `TIMEOUT`, `PARSE_ERROR`, `EMPTY`
  - `aura.probe.types.ProbeResult` — `@dataclass(frozen=True)` kentillä
    `status: str`, `detail: str = ""`, `fields: list[tuple[str, str]] = []`,
    `enrichments: list[tuple[str, str]] = []`, `http_status: int | None = None`
  - `aura.database.upsert_probe_result(conn, resource_id, dataset_id, probe_type, status, detail, probed_at) -> None`
  - `aura.database.get_probe_result(conn, resource_id) -> dict[str, Any] | None`

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_probe_results.py
"""Testit probe-kirjanpidolle.

Nykyinen infer-schemas tulostaa virheen ja unohtaa sen, joten sama
rikkinäinen resurssi yritetään uudestaan joka ajolla eikä kukaan tiedä mikä
on rikki. Kirjanpito on se ero: epäonnistuminen on tulos, ei tyhjä.
"""

from __future__ import annotations

import sqlite3

import pytest

from aura.database import get_probe_result, init_db, upsert_probe_result


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c


def test_tulos_tallentuu_ja_loytyy(conn: sqlite3.Connection) -> None:
    upsert_probe_result(conn, "r1", "d1", "wfs", "ok", "", "2026-08-19T10:00:00")
    row = get_probe_result(conn, "r1")
    assert row is not None
    assert row["status"] == "ok"
    assert row["probe_type"] == "wfs"


def test_uusi_tulos_korvaa_vanhan(conn: sqlite3.Connection) -> None:
    """Taulu kantaa viimeisimmän tilan, ei historiaa."""
    upsert_probe_result(conn, "r1", "d1", "wfs", "http_error", "HTTP 404", "2026-08-01T00:00:00")
    upsert_probe_result(conn, "r1", "d1", "wfs", "ok", "", "2026-08-19T00:00:00")
    row = get_probe_result(conn, "r1")
    assert row is not None
    assert row["status"] == "ok"
    assert row["detail"] == ""
    assert conn.execute("SELECT COUNT(*) FROM probe_results").fetchone()[0] == 1


def test_epaonnistuminen_kantaa_syyn(conn: sqlite3.Connection) -> None:
    upsert_probe_result(conn, "r2", "d1", "csv", "http_error", "HTTP 404", "2026-08-19T00:00:00")
    row = get_probe_result(conn, "r2")
    assert row is not None
    assert row["detail"] == "HTTP 404"


def test_tuntematon_resurssi_on_none(conn: sqlite3.Connection) -> None:
    assert get_probe_result(conn, "ei-ole") is None


def test_prune_siivoaa_taulun() -> None:
    """Kadonneen datasetin rivit eivät saa jäädä roikkumaan."""
    from aura.prune import RELATED_TABLES

    assert "probe_results" in RELATED_TABLES
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `source .venv/bin/activate && python -m pytest tests/test_probe_results.py -q`
Expected: FAIL — `ImportError: cannot import name 'get_probe_result'`

- [ ] **Step 3: Kirjoita migraatio**

```sql
-- scripts/migrations/022_probe_results.sql
-- Probe-vaiheen kirjanpito: viimeisin tila per resurssi.
--
-- Erillinen taulu enrichmenteistä, koska TTL ja jatkaminen vaativat
-- indeksoituja kyselyitä ("mitkä ovat vanhentuneet", "mitä ei ole
-- yritetty"), ja enrichments on versioitu lisäystaulu johon kirjanpito
-- paisuisi.
--
-- Tämä on myös se paikka jossa epäonnistuminen näkyy. Aiemmin
-- infer-schemas tulosti virheen ja unohti sen: sama rikkinäinen resurssi
-- yritettiin uudestaan joka ajolla eikä kukaan tiennyt mikä on rikki.

CREATE TABLE IF NOT EXISTS probe_results (
    resource_id TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL,
    probe_type  TEXT NOT NULL,
    status      TEXT NOT NULL,
    detail      TEXT DEFAULT '',
    probed_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_probe_results_probed_at
    ON probe_results(probed_at);
CREATE INDEX IF NOT EXISTS idx_probe_results_dataset
    ON probe_results(dataset_id);
```

- [ ] **Step 4: Kirjoita tyypit**

```python
# src/aura/probe/types.py
"""Probe-vaiheen tulostyypit.

Prober ei kirjoita kantaan eikä tiedä orkestroinnista. Se palauttaa tämän
rakenteen, ja orkestrointi päättää mitä sille tehdään. Siksi jokainen
prober on testattavissa tallennetulla vastauksella ilman kantaa ja verkkoa.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class ProbeStatus:
    """Probe-yrityksen lopputulos.

    Neljä epäonnistumistapaa erotellaan, koska ne tarkoittavat eri asioita
    ja johtavat eri TTL:ään: palvelu joka on poissa on eri asia kuin
    palvelu joka vastasi jotain odottamatonta.
    """

    OK = "ok"
    HTTP_ERROR = "http_error"      # palvelu vastasi kieltävästi
    TIMEOUT = "timeout"            # palvelu ei vastannut
    PARSE_ERROR = "parse_error"    # vastasi jotain muuta kuin lupasi
    EMPTY = "empty"                # vastasi oikein muttei sisältänyt kenttiä


@dataclass(frozen=True)
class ProbeResult:
    """Yhden proberin tulos.

    Attributes:
        status: ``ProbeStatus``-vakio.
        detail: Ihmisluettava syy epäonnistumiselle, esim. "HTTP 404".
        fields: Sarakkeet ``(nimi, tyyppi)`` — menevät resource_schemaan.
        enrichments: ``(kenttä, arvo)`` — menevät enrichmenteiksi.
        http_status: Viimeisin statuskoodi, josta auth_method johdetaan.
    """

    status: str
    detail: str = ""
    fields: list[tuple[str, str]] = field(default_factory=list)
    enrichments: list[tuple[str, str]] = field(default_factory=list)
    http_status: int | None = None

    @property
    def ok(self) -> bool:
        return self.status == ProbeStatus.OK
```

- [ ] **Step 5: Kirjoita kanta-apurit**

Lisää `src/aura/database.py`:hyn, `upsert_resource_schema`-funktion viereen:

```python
def upsert_probe_result(
    conn: sqlite3.Connection,
    resource_id: str,
    dataset_id: str,
    probe_type: str,
    status: str,
    detail: str,
    probed_at: str,
) -> None:
    """Kirjaa probe-yrityksen tulos. Korvaa saman resurssin edellisen.

    Taulu kantaa viimeisimmän tilan, ei historiaa: kirjanpidossa vanha tila
    ei kerro mitään jota uusi ei kertoisi paremmin. Historia kuuluu
    enrichmenteihin, joissa se jo on.
    """
    conn.execute(
        """
        INSERT INTO probe_results
            (resource_id, dataset_id, probe_type, status, detail, probed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_id) DO UPDATE SET
            dataset_id = excluded.dataset_id,
            probe_type = excluded.probe_type,
            status     = excluded.status,
            detail     = excluded.detail,
            probed_at  = excluded.probed_at
        """,
        (resource_id, dataset_id, probe_type, status, detail, probed_at),
    )


def get_probe_result(
    conn: sqlite3.Connection, resource_id: str
) -> dict[str, Any] | None:
    """Hae resurssin viimeisin probe-tulos."""
    row = conn.execute(
        "SELECT * FROM probe_results WHERE resource_id = ?", (resource_id,)
    ).fetchone()
    return dict(row) if row else None
```

Lisää `src/aura/prune.py`:n `RELATED_TABLES`-listaan rivi `"probe_results",`.

- [ ] **Step 6: Aja testit**

Run: `python -m pytest tests/test_probe_results.py tests/test_prune.py -q`
Expected: PASS

- [ ] **Step 7: Lint, tyypit ja commit**

```bash
source .venv/bin/activate
ruff check src/aura/probe src/aura/database.py src/aura/prune.py tests/test_probe_results.py
mypy src/aura/probe src/aura/database.py
git add scripts/migrations/022_probe_results.sql src/aura/probe src/aura/database.py src/aura/prune.py tests/test_probe_results.py
git commit -m "feat: probe-kirjanpito omaan tauluun

Epäonnistuminen on tulos, ei tyhjä. Nykyinen infer-schemas tulostaa virheen
ja unohtaa sen, joten sama rikkinäinen resurssi yritetään uudestaan joka
ajolla eikä kukaan tiedä mikä on rikki.

Taulu kantaa viimeisimmän tilan per resurssi. Historia kuuluu
enrichmenteihin, joissa se jo on."
```

---

### Task 2: Uudet enrichment-kentät ja use_case-migraatio

**Files:**
- Create: `scripts/migrations/023_use_case_suggested.sql`
- Modify: `src/aura/tools/enrichment.py:17-26` (`VALID_ENRICHMENT_FIELDS`)
- Test: `tests/test_enrichment_fields.py`

**Interfaces:**
- Consumes: `aura.tools.enrichment.VALID_ENRICHMENT_FIELDS`
- Produces: kentät `service_layers`, `example_request`, `use_case_suggested`
  hyväksyttyinä enrichment-kenttinä

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_enrichment_fields.py
"""Testit probe-vaiheen uusille enrichment-kentille.

use_case on ainoa puuttuvista kentistä joka ei ole johdettavissa
lähteestä. Generoitu sisältö muuttuu katalogissa faktaksi seuraavalle
lukijalle, joten se ei saa asua samassa kentässä kuin ihmisen kirjoittama.
Erillinen kenttä kertoo sen **nimellä** — provenienssimetatieto ei näy
lukijalle samalla tavalla.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aura.database import init_db
from aura.tools.enrichment import VALID_ENRICHMENT_FIELDS


@pytest.mark.parametrize(
    "kentta", ["service_layers", "example_request", "use_case_suggested"]
)
def test_uusi_kentta_on_sallittu(kentta: str) -> None:
    assert kentta in VALID_ENRICHMENT_FIELDS


def test_use_case_sailyy_sallittuna() -> None:
    """Ihmisen kirjoittama use_case ei katoa mihinkään."""
    assert "use_case" in VALID_ENRICHMENT_FIELDS


def test_migraatio_siirtaa_ai_rivit() -> None:
    """Migraation SQL ajetaan käsin, koska init_db on jo ajanut sen.

    init_db ajaa kaikki migraatiot, joten testidata syntyy vasta migraation
    jälkeen eikä toinen run_migrations-kutsu tekisi mitään. Tässä testataan
    migraation SQL, ei migraatiokirjanpitoa.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    conn.execute(
        "INSERT INTO enrichments (dataset_id, field, value, source_type)"
        " VALUES ('d1','use_case','Generoitu kuvaus','ai_analysis')"
    )
    conn.execute(
        "INSERT INTO enrichments (dataset_id, field, value, source_type)"
        " VALUES ('d1','use_case','Ihmisen kirjoittama','mcp_session')"
    )
    conn.commit()

    sql = Path("scripts/migrations/023_use_case_suggested.sql").read_text(
        encoding="utf-8"
    )
    conn.executescript(sql)

    siirretty = conn.execute(
        "SELECT value FROM enrichments WHERE field = 'use_case_suggested'"
    ).fetchall()
    assert [r["value"] for r in siirretty] == ["Generoitu kuvaus"]

    jaljella = conn.execute(
        "SELECT value FROM enrichments WHERE field = 'use_case'"
    ).fetchall()
    assert [r["value"] for r in jaljella] == ["Ihmisen kirjoittama"]
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_enrichment_fields.py -q`
Expected: FAIL — `assert 'service_layers' in VALID_ENRICHMENT_FIELDS`

- [ ] **Step 3: Lisää kentät**

`src/aura/tools/enrichment.py`, `VALID_ENRICHMENT_FIELDS`-joukkoon:

```python
    "crs", "joinable_keys",
    # Probe-vaiheen kentät (#146-palaute, P1). service_layers on WMS:n
    # layer-lista: se ei ole skeema, koska WMS ei tarjoa sarakkeita, eikä
    # sitä pidä esittää sellaisena. example_request on konkreettinen kutsu
    # — access_instructions sisältää yhteydenotto-ohjeita, ja niiden
    # sekoittaminen tekisi kummastakin arvaamattoman.
    "service_layers", "example_request",
    # Kielimallin ehdottama käyttötapaus. Erillään use_casesta, jotta
    # kentän nimi kertoo mistä on kyse.
    "use_case_suggested",
```

- [ ] **Step 4: Kirjoita migraatio**

```sql
-- scripts/migrations/023_use_case_suggested.sql
-- Kielimallin ehdottamat käyttötapaukset omaan kenttäänsä.
--
-- use_case on ainoa kenttä joka ei ole johdettavissa lähteestä. Generoitu
-- sisältö muuttuu katalogissa faktaksi seuraavalle lukijalle, ja
-- source_type='ai_analysis' ei näy siinä kohdassa jossa arvo luetaan.
-- Kentän nimi näkyy.
--
-- Rivejä ei poisteta: sisältö säilyy, vain sen nimi muuttuu todeksi.

UPDATE enrichments
   SET field = 'use_case_suggested'
 WHERE field = 'use_case'
   AND source_type = 'ai_analysis';
```

- [ ] **Step 5: Aja testit**

Run: `python -m pytest tests/test_enrichment_fields.py tests/test_enrichments.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
ruff check src/aura/tools/enrichment.py tests/test_enrichment_fields.py
git add scripts/migrations/023_use_case_suggested.sql src/aura/tools/enrichment.py tests/test_enrichment_fields.py
git commit -m "feat: probe-kentät ja use_case_suggested

Kielimallin ehdottama käyttötapaus siirtyy omaan kenttäänsä. Kentän nimi
kertoo mistä on kyse; source_type ei näy siinä kohdassa jossa arvo luetaan.
Rivejä ei poisteta."
```

---

### Task 3: WFS-prober

**Files:**
- Create: `src/aura/probe/wfs.py`
- Create: `tests/fixtures/wfs_describefeaturetype_arcgis.xml`
- Create: `tests/fixtures/wfs_describefeaturetype_geoserver.xml`
- Test: `tests/test_probe_wfs.py`

**Interfaces:**
- Consumes: `aura.wfs.parse_capabilities`, `aura.wfs.exception_text`,
  `aura.wfs._local`, `aura.probe.types.ProbeResult`, `ProbeStatus`
- Produces: `aura.probe.wfs.parse_feature_types(body: str) -> list[tuple[str, str]]`
  ja `aura.probe.wfs.probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult`

- [ ] **Step 1: Hae fixturet oikeilta palvelimilta**

```bash
ARC="https://gtkdata.gtk.fi/arcgis/services/Rajapinnat/GTK_Maapera_WFS/MapServer/WFSServer"
curl -s "$ARC?service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames=Rajapinnat_GTK_Maapera_WFS:postglasiaalisiirros" \
  -o tests/fixtures/wfs_describefeaturetype_arcgis.xml
curl -s "https://kartta.hel.fi/ws/geoserver/avoindata/wfs?service=WFS&version=2.0.0&request=DescribeFeatureType&typeName=avoindata:Seutukartta_liikenne_metroasemat" \
  -o tests/fixtures/wfs_describefeaturetype_geoserver.xml
head -c 200 tests/fixtures/wfs_describefeaturetype_arcgis.xml
```

Molempien on sisällettävä `<xsd:element ... name="..." type="..."/>` -rivejä.
ArcGIS käyttää prefiksiä `xsd:`, ja tyyppi `gml:MultiCurvePropertyType`
merkitsee geometriaa.

- [ ] **Step 2: Kirjoita kaatuva testi**

```python
# tests/test_probe_wfs.py
"""Testit WFS-proberille.

WFS on se aukko johon raportoija törmäsi: GTK:n aineistot ovat WFS:ää,
eikä niiden skeemaa kaapattu missään.

Fixturet ovat oikeita vastauksia kahdelta eri palvelintyypiltä.
Nimiavaruusprefiksi eroaa (`xsd:` / `xs:`), ja käsin kirjoitettu XML olisi
yksinkertaistanut juuri sen eron pois.
"""

from __future__ import annotations

from pathlib import Path

from aura.probe.wfs import parse_feature_types

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestSarakkeidenLuku:
    def test_geoserver_sarakkeet_ja_tyypit(self) -> None:
        kentat = dict(_fixture("wfs_describefeaturetype_geoserver.xml") and
                      parse_feature_types(_fixture("wfs_describefeaturetype_geoserver.xml")))
        assert kentat["tietopalvelu_id"] == "integer"
        assert kentat["metroasema"] == "string"

    def test_arcgis_sarakkeet_ja_tyypit(self) -> None:
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_arcgis.xml")))
        assert kentat["OBJECTID"] == "integer"

    def test_geometria_merkitaan_geometriaksi(self) -> None:
        """Koordinaattikenttä ei ole sarake, mutta sen olemassaolo on tietoa."""
        kentat = dict(parse_feature_types(_fixture("wfs_describefeaturetype_geoserver.xml")))
        assert kentat.get("geom") == "geometry"

    def test_tyyppikartta_kattaa_xsd_perustyypit(self) -> None:
        xml = (
            '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            '<xsd:element name="a" type="xsd:double"/>'
            '<xsd:element name="b" type="xsd:dateTime"/>'
            '<xsd:element name="c" type="xsd:boolean"/>'
            "</xsd:schema>"
        )
        assert dict(parse_feature_types(xml)) == {
            "a": "float", "b": "date", "c": "boolean",
        }

    def test_tyhja_vastaus_ei_kaada(self) -> None:
        assert parse_feature_types("") == []
```

- [ ] **Step 3: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_wfs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.probe.wfs'`

- [ ] **Step 4: Kirjoita prober**

```python
# src/aura/probe/wfs.py
"""WFS-prober: sarakkeet, tyypit ja koordinaatisto kyvyistä.

DescribeFeatureType antaa tyypitetyt sarakkeet sekä ArcGIS- että
GeoServer-palvelimilla, mutta eri nimiavaruusprefiksillä (``xsd:`` / ``xs:``).
Siksi jäsennys tehdään prefiksistä riippumatta.
"""

from __future__ import annotations

from typing import Any

import httpx

from aura.wfs import _local, _root, exception_text, parse_capabilities, request_params
from aura.probe.types import ProbeResult, ProbeStatus

#: XSD-perustyypit Auran tyyppinimiksi. Tuntematon tyyppi on "string":
#: väärä arvaus olisi pahempi kuin yleisin oikea.
_XSD_TYPES = {
    "int": "integer", "integer": "integer", "long": "integer", "short": "integer",
    "double": "float", "float": "float", "decimal": "float",
    "date": "date", "dateTime": "date",
    "boolean": "boolean",
}


def parse_feature_types(body: str) -> list[tuple[str, str]]:
    """Poimi DescribeFeatureType-vastauksesta sarakkeet ja tyypit.

    Geometriakenttä (``gml:*PropertyType``) merkitään tyypillä "geometry"
    eikä pudoteta: sen olemassaolo kertoo että aineisto on paikkatietoa,
    vaikka koordinaattilista itsessään ei kuulu sarakelistaan.
    """
    root = _root(body)
    if root is None:
        return []

    fields: list[tuple[str, str]] = []
    for el in root.iter():
        if _local(el.tag) != "element":
            continue
        name = el.get("name")
        raw_type = el.get("type") or ""
        if not name or not raw_type:
            continue
        # Ylin element on featuretyyppi itse, ei sarake.
        if raw_type.endswith("FeatureType") or raw_type.endswith("Type") and "gml:" not in raw_type and ":" in raw_type and _local(raw_type) not in _XSD_TYPES:
            if raw_type.split(":")[-1].endswith("Type") and not raw_type.startswith("gml:"):
                continue
        local_type = raw_type.split(":")[-1]
        if raw_type.startswith("gml:"):
            fields.append((name, "geometry"))
            continue
        fields.append((name, _XSD_TYPES.get(local_type, "string")))
    return fields


async def probe(
    resource: dict[str, Any], client: httpx.AsyncClient
) -> ProbeResult:
    """Hae WFS-resurssin skeema, koordinaatisto ja toimiva esimerkkikutsu."""
    url = resource.get("url", "")
    base_url = url.split("?")[0]
    caps_params = {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"}

    try:
        caps_resp = await client.get(base_url, params=caps_params, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="GetCapabilities")
    if caps_resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {caps_resp.status_code}",
            http_status=caps_resp.status_code,
        )

    caps = parse_capabilities(caps_resp.text)
    if not caps.feature_types:
        virhe = exception_text(caps_resp.text) or "GetCapabilities ei sisältänyt featuretyyppejä"
        return ProbeResult(
            status=ProbeStatus.PARSE_ERROR, detail=virhe, http_status=caps_resp.status_code
        )

    type_name = caps.feature_types[0]
    dft_params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "DescribeFeatureType",
        "typeNames": type_name,
    }
    try:
        dft_resp = await client.get(base_url, params=dft_params, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="DescribeFeatureType")
    if dft_resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {dft_resp.status_code}",
            http_status=dft_resp.status_code,
        )

    fields = parse_feature_types(dft_resp.text)
    if not fields:
        virhe = exception_text(dft_resp.text) or "DescribeFeatureType ei sisältänyt kenttiä"
        return ProbeResult(
            status=ProbeStatus.EMPTY, detail=virhe, http_status=dft_resp.status_code
        )

    enrichments: list[tuple[str, str]] = []
    crs = _default_crs(caps_resp.text, type_name)
    if crs:
        enrichments.append(("crs", crs))

    _base, params = request_params(url, 20, type_name=type_name)
    example = base_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    enrichments.append(("example_request", example))

    return ProbeResult(
        status=ProbeStatus.OK,
        fields=fields,
        enrichments=enrichments,
        http_status=dft_resp.status_code,
    )


def _default_crs(caps_body: str, type_name: str) -> str:
    """Featuretyypin DefaultCRS GetCapabilities-vastauksesta."""
    root = _root(caps_body)
    if root is None:
        return ""
    for ft in root.iter():
        if _local(ft.tag) != "FeatureType":
            continue
        nimi = next(
            (c.text or "" for c in ft if _local(c.tag) == "Name"), ""
        ).strip()
        if nimi != type_name:
            continue
        for c in ft:
            if _local(c.tag) in ("DefaultCRS", "DefaultSRS"):
                return (c.text or "").strip()
    return ""
```

- [ ] **Step 5: Aja testit**

Run: `python -m pytest tests/test_probe_wfs.py -q`
Expected: PASS. Jos `parse_feature_types` palauttaa myös featuretyypin oman
elementin, yksinkertaista sen ohitusehto: ohita elementit joiden `type`
päättyy `FeatureType`-merkkijonoon.

- [ ] **Step 6: Lisää probe-testi valeasiakkaalla**

```python
# tests/test_probe_wfs.py, jatkoa
from unittest.mock import AsyncMock, MagicMock

import pytest

from aura.probe.types import ProbeStatus
from aura.probe.wfs import probe


def _client(responses: list[tuple[int, str]]) -> AsyncMock:
    calls: list[dict] = []

    async def _get(url, params=None, **kwargs):
        calls.append({"params": dict(params or {})})
        status, body = responses[min(len(calls) - 1, len(responses) - 1)]
        resp = MagicMock()
        resp.status_code = status
        resp.text = body
        return resp

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_get)
    client.calls = calls
    return client


class TestProbe:
    @pytest.mark.anyio
    async def test_onnistunut_probe_tuottaa_kentat_ja_crs(self) -> None:
        client = _client([
            (200, _fixture("wfs_capabilities_arcgis.xml")),
            (200, _fixture("wfs_describefeaturetype_arcgis.xml")),
        ])
        tulos = await probe({"url": "https://example.test/wfs"}, client)
        assert tulos.status == ProbeStatus.OK
        assert any(nimi == "OBJECTID" for nimi, _ in tulos.fields)
        assert dict(tulos.enrichments)["crs"].endswith("3067")
        assert "typeNames=" in dict(tulos.enrichments)["example_request"]

    @pytest.mark.anyio
    async def test_virhevastaus_kirjautuu_syyna(self) -> None:
        """HTTP 200 + ExceptionReport on WFS:n tavallisin kieltäytyminen."""
        client = _client([(200, _fixture("wfs_exception_arcgis.xml"))])
        tulos = await probe({"url": "https://example.test/wfs"}, client)
        assert tulos.status == ProbeStatus.PARSE_ERROR
        assert "typeNames" in tulos.detail or "application/json" in tulos.detail

    @pytest.mark.anyio
    async def test_http_virhe_kirjautuu_koodina(self) -> None:
        client = _client([(404, "")])
        tulos = await probe({"url": "https://example.test/wfs"}, client)
        assert tulos.status == ProbeStatus.HTTP_ERROR
        assert tulos.detail == "HTTP 404"
        assert tulos.http_status == 404
```

- [ ] **Step 7: Aja testit ja commit**

```bash
python -m pytest tests/test_probe_wfs.py -q
ruff check src/aura/probe/wfs.py tests/test_probe_wfs.py
mypy src/aura/probe/wfs.py
git add src/aura/probe/wfs.py tests/test_probe_wfs.py tests/fixtures/wfs_describefeaturetype_*.xml
git commit -m "feat: WFS-prober lukee sarakkeet ja koordinaatiston kyvyistä

WFS on se aukko johon agenttipalaute törmäsi: 1 100 datasettiä joiden
skeemaa ei kaapattu missään. DescribeFeatureType antaa tyypitetyt sarakkeet
molemmilla palvelintyypeillä, mutta eri nimiavaruusprefiksillä."
```

---

### Task 4: WMS-prober

**Files:**
- Create: `src/aura/probe/wms.py`
- Create: `tests/fixtures/wms_capabilities.xml`
- Test: `tests/test_probe_wms.py`

**Interfaces:**
- Consumes: `aura.wfs._local`, `aura.wfs._root`, `aura.probe.types.ProbeResult`
- Produces: `aura.probe.wms.parse_layers(body: str) -> list[dict[str, str]]`
  ja `aura.probe.wms.probe(resource, client) -> ProbeResult`

- [ ] **Step 1: Hae fixture**

```bash
curl -s "https://kartta.hel.fi/ws/geoserver/avoindata/wms?service=WMS&version=1.3.0&request=GetCapabilities" \
  -o tests/fixtures/wms_capabilities.xml
grep -c "<Layer" tests/fixtures/wms_capabilities.xml
```

Jos tiedosto on yli 500 kt, karsi se säilyttäen XML-rakenne: otsikko,
`<Service>`-lohko ja kolme ensimmäistä `<Layer>`-elementtiä.

- [ ] **Step 2: Kirjoita kaatuva testi**

```python
# tests/test_probe_wms.py
"""Testit WMS-proberille.

WMS ei tarjoa sarakkeita lainkaan — vain layereita. Siksi tulos ei mene
resource_schemaan vaan omaan service_layers-kenttäänsä: layer-listan
esittäminen kenttätietona antaisi lukijalle väärän kuvan siitä mitä
aineistosta saa irti.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aura.probe.types import ProbeStatus
from aura.probe.wms import parse_layers, probe

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_layerit_loytyvat_nimineen(self=None) -> None:
    layers = parse_layers(_fixture("wms_capabilities.xml"))
    assert layers, "yhtään layeria ei löytynyt"
    assert all("name" in lay for lay in layers)


def test_nimeton_kokoava_layer_ohitetaan() -> None:
    """WMS-juuri on nimetön kääre, ei kysyttävä kerros."""
    xml = (
        '<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability>'
        "<Layer><Title>Kaikki</Title>"
        "<Layer><Name>kunnat</Name><Title>Kunnat</Title></Layer>"
        "</Layer></Capability></WMS_Capabilities>"
    )
    assert parse_layers(xml) == [{"name": "kunnat", "title": "Kunnat"}]


def test_tyhja_vastaus_ei_kaada() -> None:
    assert parse_layers("") == []


@pytest.mark.anyio
async def test_probe_tuottaa_service_layers_enrichmentin() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.text = _fixture("wms_capabilities.xml")
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/wms"}, client)
    assert tulos.status == ProbeStatus.OK
    assert tulos.fields == [], "WMS ei tuota sarakkeita"
    arvot = dict(tulos.enrichments)
    layers = json.loads(arvot["service_layers"])
    assert layers and "name" in layers[0]
```

- [ ] **Step 3: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_wms.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.probe.wms'`

- [ ] **Step 4: Kirjoita prober**

```python
# src/aura/probe/wms.py
"""WMS-prober: layerien nimet ja otsikot.

WMS ei tarjoa sarakkeita. Sen tulos ei siksi mene resource_schemaan vaan
omaan service_layers-kenttäänsä — layer-listan esittäminen kenttätietona
antaisi lukijalle väärän kuvan siitä mitä aineistosta saa irti.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus
from aura.wfs import _local, _root, exception_text


def parse_layers(body: str) -> list[dict[str, str]]:
    """Poimi kysyttävät layerit GetCapabilities-vastauksesta.

    Nimetön layer on kokoava kääre, ei kerros jota voi kysyä; se ohitetaan.
    """
    root = _root(body)
    if root is None:
        return []
    layers: list[dict[str, str]] = []
    for el in root.iter():
        if _local(el.tag) != "Layer":
            continue
        nimi = next((c.text or "" for c in el if _local(c.tag) == "Name"), "").strip()
        if not nimi:
            continue
        otsikko = next((c.text or "" for c in el if _local(c.tag) == "Title"), "").strip()
        layers.append({"name": nimi, "title": otsikko})
    return layers


async def probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Hae WMS-palvelun layerit."""
    base_url = resource.get("url", "").split("?")[0]
    params = {"service": "WMS", "version": "1.3.0", "request": "GetCapabilities"}
    try:
        resp = await client.get(base_url, params=params, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="GetCapabilities")
    if resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {resp.status_code}",
            http_status=resp.status_code,
        )

    layers = parse_layers(resp.text)
    if not layers:
        virhe = exception_text(resp.text) or "GetCapabilities ei sisältänyt layereita"
        return ProbeResult(
            status=ProbeStatus.EMPTY, detail=virhe, http_status=resp.status_code
        )

    arvo = json.dumps(layers, ensure_ascii=False)
    return ProbeResult(
        status=ProbeStatus.OK,
        enrichments=[("service_layers", arvo)],
        http_status=resp.status_code,
    )
```

- [ ] **Step 5: Aja testit ja commit**

```bash
python -m pytest tests/test_probe_wms.py -q
ruff check src/aura/probe/wms.py tests/test_probe_wms.py && mypy src/aura/probe/wms.py
git add src/aura/probe/wms.py tests/test_probe_wms.py tests/fixtures/wms_capabilities.xml
git commit -m "feat: WMS-prober lukee layerit omaan kenttäänsä

WMS ei tarjoa sarakkeita. Layer-listan esittäminen kenttätietona antaisi
väärän kuvan siitä mitä aineistosta saa irti, joten se menee omaan
service_layers-kenttäänsä eikä resource_schemaan."
```

---

### Task 5: PxWeb-prober

**Files:**
- Create: `src/aura/probe/pxweb.py`
- Create: `tests/fixtures/pxweb_metadata.json`
- Test: `tests/test_probe_pxweb.py`

**Interfaces:**
- Consumes: `aura.probe.types.ProbeResult`, `ProbeStatus`
- Produces: `aura.probe.pxweb.parse_dimensions(payload: dict) -> list[dict[str, Any]]`
  ja `aura.probe.pxweb.probe(resource, client) -> ProbeResult`

- [ ] **Step 1: Hae fixture**

```bash
curl -s "https://statfin.stat.fi/PxWeb/api/v1/fi/StatFin/tyti/statfin_tyti_pxt_135y.px" \
  -o tests/fixtures/pxweb_metadata.json
python -c "import json;d=json.load(open('tests/fixtures/pxweb_metadata.json'));print(len(d['variables']))"
```

- [ ] **Step 2: Kirjoita kaatuva testi**

```python
# tests/test_probe_pxweb.py
"""Testit PxWeb-proberille.

Muoto on jo päätetty: harvesteri kirjoittaa data_fields-enrichmentin
muodossa {code, name, value_count, examples}, ja region_levels.py lukee sitä
tunnistaakseen kuntadimension. Probe tuottaa saman muodon — eri muoto
rikkoisi hakutuloksen aluelaajennuksen.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aura.probe.pxweb import parse_dimensions, probe
from aura.probe.types import ProbeStatus

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> dict:
    return json.loads((FIXTURES / "pxweb_metadata.json").read_text(encoding="utf-8"))


def test_dimensiot_saavat_harvesterin_muodon() -> None:
    dims = parse_dimensions(_payload())
    assert dims
    eka = dims[0]
    assert set(eka) >= {"code", "name", "value_count", "examples"}
    assert isinstance(eka["value_count"], int)


def test_esimerkkeja_enintaan_viisi() -> None:
    """Koko luokitus veisi tilan kertomatta enempää."""
    for dim in parse_dimensions(_payload()):
        assert len(dim["examples"]) <= 5


def test_muuttujaton_vastaus_on_empty() -> None:
    assert parse_dimensions({"title": "x", "variables": []}) == []


@pytest.mark.anyio
async def test_probe_tuottaa_data_fields_enrichmentin() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=_payload())
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)

    tulos = await probe({"url": "https://example.test/px"}, client)
    assert tulos.status == ProbeStatus.OK
    arvot = dict(tulos.enrichments)
    dims = json.loads(arvot["data_fields"])
    assert dims[0]["code"]
```

- [ ] **Step 3: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_pxweb.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.probe.pxweb'`

- [ ] **Step 4: Kirjoita prober**

```python
# src/aura/probe/pxweb.py
"""PxWeb-prober: taulun dimensiot ja luokitusarvot.

Muoto on harvesterin määräämä: {code, name, value_count, examples}.
region_levels.py lukee sitä tunnistaakseen kuntadimension, ja se ohjaa
hakutuloksen aluelaajennusta — eri muoto rikkoisi sen hiljaa.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus

#: Esimerkkiarvoja per dimensio. Koko luokitus veisi tilan kertomatta enempää.
_MAX_EXAMPLES = 5


def parse_dimensions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Muunna PxWeb-metadata harvesterin data_fields-muotoon."""
    dims: list[dict[str, Any]] = []
    for var in payload.get("variables", []):
        values = var.get("values", [])
        texts = var.get("valueTexts", []) or values
        dims.append(
            {
                "code": var.get("code", ""),
                "name": var.get("text", var.get("code", "")),
                "value_count": len(values),
                "examples": [str(t) for t in texts[:_MAX_EXAMPLES]],
            }
        )
    return dims


async def probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Hae PxWeb-taulun dimensiot."""
    url = resource.get("url", "")
    try:
        resp = await client.get(url, follow_redirects=True)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="metadata")
    if resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {resp.status_code}",
            http_status=resp.status_code,
        )

    try:
        payload = resp.json()
    except ValueError:
        return ProbeResult(
            status=ProbeStatus.PARSE_ERROR,
            detail="Vastaus ei ole JSONia",
            http_status=resp.status_code,
        )

    dims = parse_dimensions(payload)
    if not dims:
        return ProbeResult(
            status=ProbeStatus.EMPTY,
            detail="Taululla ei ole dimensioita",
            http_status=resp.status_code,
        )

    return ProbeResult(
        status=ProbeStatus.OK,
        enrichments=[("data_fields", json.dumps(dims, ensure_ascii=False))],
        http_status=resp.status_code,
    )
```

- [ ] **Step 5: Aja testit ja commit**

```bash
python -m pytest tests/test_probe_pxweb.py -q
ruff check src/aura/probe/pxweb.py tests/test_probe_pxweb.py && mypy src/aura/probe/pxweb.py
git add src/aura/probe/pxweb.py tests/test_probe_pxweb.py tests/fixtures/pxweb_metadata.json
git commit -m "feat: PxWeb-prober kattaa harvestoinnin ulottumattomat taulut

Muoto on harvesterin määräämä, koska region_levels lukee sitä
tunnistaakseen kuntadimension — eri muoto rikkoisi hakutuloksen
aluelaajennuksen hiljaa."
```

---

### Task 6: Taulukkoprober — nykyinen polku siirrettynä

**Files:**
- Create: `src/aura/probe/tabular.py`
- Test: `tests/test_probe_tabular.py`

**Interfaces:**
- Consumes: `aura.tools.preview._preview_csv`, `_preview_json`,
  `aura.tools.schema.parse_md_table`, `infer_type`
- Produces: `aura.probe.tabular.probe(resource, client) -> ProbeResult`

Käytös ei muutu — vain sijainti, ja se että tulos palautuu `ProbeResult`ina
sen sijaan että kirjoittautuisi suoraan kantaan.

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_probe_tabular.py
"""Testit CSV/JSON-proberille.

Tämä on nykyinen infer-schemas-polku siirrettynä. Käytös ei muutu, joten
testit kiinnittävät sen: samat kentät, sama tyyppipäättely. Uutta on vain
se että tulos palautuu eikä kirjoittaudu suoraan kantaan — ilman sitä
epäonnistumista ei voi kirjata eikä TTL:ää laskea.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aura.probe.tabular import probe
from aura.probe.types import ProbeStatus


@pytest.mark.anyio
async def test_csv_otsikkorivi_tuottaa_kentat() -> None:
    markdown = (
        "| kuntakoodi | nimi | vaesto |\n"
        "| --- | --- | --- |\n"
        "| 091 | Helsinki | 664000 |\n"
    )
    with patch("aura.probe.tabular._preview_csv", AsyncMock(return_value=markdown)):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.OK
    kentat = dict(tulos.fields)
    assert kentat["nimi"] == "string"
    assert kentat["vaesto"] == "integer"


@pytest.mark.anyio
async def test_tyhja_esikatselu_on_empty() -> None:
    with patch("aura.probe.tabular._preview_csv", AsyncMock(return_value="CSV-tiedosto on tyhjä.")):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.EMPTY


@pytest.mark.anyio
async def test_verkkovirhe_kirjautuu() -> None:
    import httpx

    with patch(
        "aura.probe.tabular._preview_csv",
        AsyncMock(side_effect=httpx.TimeoutException("hidas")),
    ):
        tulos = await probe(
            {"url": "https://example.test/a.csv", "format": "CSV"}, AsyncMock()
        )
    assert tulos.status == ProbeStatus.TIMEOUT
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_tabular.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.probe.tabular'`

- [ ] **Step 3: Kirjoita prober**

```python
# src/aura/probe/tabular.py
"""CSV- ja JSON-prober: nykyinen esikatselupolku siirrettynä.

Käytös on sama kuin ``infer-schemas``-komennolla ennen: esikatselu, sitten
tyyppipäättely otsikkorivistä. Ero on että tulos palautuu eikä kirjoittaudu
suoraan kantaan — ilman sitä epäonnistumista ei voi kirjata eikä TTL:ää
laskea.
"""

from __future__ import annotations

from typing import Any

import httpx

from aura.probe.types import ProbeResult, ProbeStatus
from aura.tools.preview import _preview_csv, _preview_json
from aura.tools.schema import infer_type, parse_md_table

_PREVIEW_ROWS = 10


async def probe(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Päättele sarakkeet ja tyypit esikatselusta.

    ``client`` on mukana rajapinnan yhtenäisyyden vuoksi; esikatselufunktiot
    avaavat oman yhteytensä.
    """
    url = resource.get("url", "")
    fmt = (resource.get("format") or "").upper()

    try:
        if fmt == "CSV":
            body = await _preview_csv(url, _PREVIEW_ROWS)
        else:
            body = await _preview_json(url, _PREVIEW_ROWS)
    except httpx.TimeoutException:
        return ProbeResult(status=ProbeStatus.TIMEOUT, detail="esikatselu")
    except httpx.HTTPStatusError as e:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {e.response.status_code}",
            http_status=e.response.status_code,
        )
    except httpx.HTTPError as e:
        return ProbeResult(status=ProbeStatus.HTTP_ERROR, detail=str(e)[:100])

    headers, rows = parse_md_table(body)
    if not headers:
        return ProbeResult(status=ProbeStatus.EMPTY, detail=body[:100])

    fields: list[tuple[str, str]] = []
    for i, header in enumerate(headers):
        col_values = [r[i] for r in rows if i < len(r)]
        fields.append((header, infer_type(col_values)))

    return ProbeResult(status=ProbeStatus.OK, fields=fields, http_status=200)
```

- [ ] **Step 4: Aja testit ja commit**

```bash
python -m pytest tests/test_probe_tabular.py -q
ruff check src/aura/probe/tabular.py tests/test_probe_tabular.py && mypy src/aura/probe/tabular.py
git add src/aura/probe/tabular.py tests/test_probe_tabular.py
git commit -m "refactor: CSV/JSON-skeeman päättely CLI:stä probe-pakettiin

Käytös ei muutu. Ero on että tulos palautuu eikä kirjoittaudu suoraan
kantaan — ilman sitä epäonnistumista ei voi kirjata eikä TTL:ää laskea."
```

---

### Task 7: Johdetut kentät — auth_method

**Files:**
- Create: `src/aura/probe/derive.py`
- Test: `tests/test_probe_derive.py`

**Interfaces:**
- Consumes: `aura.probe.types.ProbeResult`
- Produces: `aura.probe.derive.auth_from_status(http_status: int | None, final_url: str = "") -> list[tuple[str, str]]`

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_probe_derive.py
"""Testit vastauskoodista johdetulle autentikointitiedolle.

auth_method ei ansaitse omaa kutsuaan: muut proberit tekevät saman pyynnön
joka tapauksessa, ja erillinen HEAD kaksinkertaistaisi liikenteen
kertomatta mitään uutta.
"""

from __future__ import annotations

import pytest

from aura.probe.derive import auth_from_status


@pytest.mark.parametrize(
    ("status", "odotus"),
    [(200, "none"), (401, "apikey"), (403, "restricted")],
)
def test_koodi_kertoo_menetelman(status: int, odotus: str) -> None:
    assert dict(auth_from_status(status))["auth_method"] == odotus


def test_rekisterointisivu_tunnistetaan() -> None:
    arvot = dict(auth_from_status(200, "https://example.test/register?next=/data"))
    assert arvot["auth_method"] == "registration"
    assert arvot["auth_registration_url"].endswith("/register?next=/data")


def test_tuntematon_koodi_ei_arvaa() -> None:
    """Väärä arvaus on pahempi kuin puuttuva tieto."""
    assert auth_from_status(500) == []
    assert auth_from_status(None) == []
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_derive.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aura.probe.derive'`

- [ ] **Step 3: Kirjoita johtaminen**

```python
# src/aura/probe/derive.py
"""Vastauskoodista johdetut kentät.

auth_method ei ansaitse omaa kutsuaan: muut proberit tekevät saman pyynnön
joka tapauksessa, ja erillinen HEAD jokaiselle resurssille
kaksinkertaistaisi liikenteen kertomatta mitään uutta.
"""

from __future__ import annotations

#: Osoitteen osat jotka kertovat rekisteröintisivusta.
_REGISTRATION_HINTS = ("register", "signup", "rekister", "tunnus", "login")

_BY_STATUS = {200: "none", 401: "apikey", 403: "restricted"}


def auth_from_status(
    http_status: int | None, final_url: str = ""
) -> list[tuple[str, str]]:
    """Päättele autentikointitapa statuskoodista ja päätyneestä osoitteesta.

    Tuntematon koodi ei tuota mitään: väärä arvaus katalogissa on pahempi
    kuin puuttuva tieto, koska lukija ei näe kumpi se on.
    """
    if http_status is None:
        return []

    if final_url and any(h in final_url.lower() for h in _REGISTRATION_HINTS):
        return [
            ("auth_method", "registration"),
            ("auth_registration_url", final_url),
        ]

    method = _BY_STATUS.get(http_status)
    if method is None:
        return []
    return [("auth_method", method)]
```

- [ ] **Step 4: Aja testit ja commit**

```bash
python -m pytest tests/test_probe_derive.py -q
ruff check src/aura/probe/derive.py tests/test_probe_derive.py && mypy src/aura/probe/derive.py
git add src/aura/probe/derive.py tests/test_probe_derive.py
git commit -m "feat: auth_method johdetaan vastauskoodista, ei omalla kutsulla

Erillinen HEAD jokaiselle resurssille kaksinkertaistaisi liikenteen
kertomatta mitään uutta. Tuntematon koodi ei tuota mitään: väärä arvaus
katalogissa on pahempi kuin puuttuva tieto."
```

---

### Task 8: Orkestrointi

**Files:**
- Modify: `src/aura/probe/__init__.py`
- Test: `tests/test_probe_run.py`

**Interfaces:**
- Consumes: kaikki proberit, `aura.database.upsert_probe_result`,
  `upsert_resource_schema`, `add_enrichment`,
  `aura.tools.schema.detect_joinable_keys`
- Produces:
  - `aura.probe.PROBE_TYPES: dict[str, str]` — formaatti → probe_type
  - `aura.probe.TTL_DAYS: dict[str, int]`
  - `aura.probe.select_targets(conn, *, now, source="", fmt="", limit=50) -> list[dict[str, Any]]`
  - `aura.probe.run_probe(conn, *, source="", fmt="", limit=50, now="", client=None) -> dict[str, int]`

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_probe_run.py
"""Testit probe-ajon orkestroinnille.

Kolme asiaa joita nykyinen infer-schemas ei tee, ja jotka pitävät
kattavuuden 54 datasetissä 12 918:sta: TTL, epäonnistumisen kirjaus ja
tahdinsäätö per isäntä.

TTL porrastuu vian luonteen mukaan. 404 ja timeout ovat eri asioita:
poissa oleva palvelu ei palaa viikossa, hidas palvelu voi.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from aura.database import init_db, upsert_probe_result
from aura.probe import TTL_DAYS, run_probe, select_targets
from aura.probe.types import ProbeResult, ProbeStatus

NOW = "2026-08-19T12:00:00"


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    for rid, fmt in (("r-wfs", "WFS"), ("r-csv", "CSV"), ("r-pdf", "PDF")):
        c.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES (?, 'd1', ?, ?, ?)",
            (rid, rid, fmt, f"https://example.test/{rid}"),
        )
    c.commit()
    return c


class TestKohteidenValinta:
    def test_vain_probattavat_formaatit(self, conn: sqlite3.Connection) -> None:
        idt = {t["id"] for t in select_targets(conn, now=NOW)}
        assert idt == {"r-wfs", "r-csv"}
        assert "r-pdf" not in idt

    def test_probaamattomat_ensin(self, conn: sqlite3.Connection) -> None:
        upsert_probe_result(conn, "r-wfs", "d1", "wfs", "ok", "", "2020-01-01T00:00:00")
        conn.commit()
        idt = [t["id"] for t in select_targets(conn, now=NOW)]
        assert idt[0] == "r-csv"

    def test_tuore_onnistuminen_ohitetaan(self, conn: sqlite3.Connection) -> None:
        upsert_probe_result(conn, "r-wfs", "d1", "wfs", "ok", "", "2026-08-18T00:00:00")
        conn.commit()
        assert "r-wfs" not in {t["id"] for t in select_targets(conn, now=NOW)}

    def test_vanhentunut_onnistuminen_yritetaan_uudestaan(
        self, conn: sqlite3.Connection
    ) -> None:
        upsert_probe_result(conn, "r-wfs", "d1", "wfs", "ok", "", "2026-01-01T00:00:00")
        conn.commit()
        assert "r-wfs" in {t["id"] for t in select_targets(conn, now=NOW)}

    def test_404_odottaa_pidempaan_kuin_timeout(
        self, conn: sqlite3.Connection
    ) -> None:
        """Poissa oleva palvelu ei palaa viikossa; hidas voi."""
        assert TTL_DAYS["http_error_permanent"] > TTL_DAYS["timeout"]

        upsert_probe_result(
            conn, "r-wfs", "d1", "wfs", "http_error", "HTTP 404", "2026-07-20T00:00:00"
        )
        upsert_probe_result(
            conn, "r-csv", "d1", "csv", "timeout", "", "2026-07-20T00:00:00"
        )
        conn.commit()
        idt = {t["id"] for t in select_targets(conn, now=NOW)}
        assert "r-csv" in idt, "timeout olisi pitänyt yrittää uudestaan"
        assert "r-wfs" not in idt, "404 ei kuulu yrittää joka kierroksella"

    def test_lahde_ja_formaatti_rajaavat(self, conn: sqlite3.Connection) -> None:
        assert {t["id"] for t in select_targets(conn, now=NOW, fmt="WFS")} == {"r-wfs"}
        assert select_targets(conn, now=NOW, source="ei-ole") == []


class TestAjo:
    @pytest.mark.anyio
    async def test_tulokset_kirjautuvat_kantaan(self, conn: sqlite3.Connection) -> None:
        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK,
                fields=[("kuntakoodi", "string"), ("nimi", "string")],
                enrichments=[("crs", "EPSG:3067")],
                http_status=200,
            )

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        assert yhteenveto["ok"] == 2

        kentat = conn.execute(
            "SELECT field_name FROM resource_schema WHERE resource_id = 'r-wfs'"
        ).fetchall()
        assert {r["field_name"] for r in kentat} == {"kuntakoodi", "nimi"}

        crs = conn.execute(
            "SELECT value FROM enrichments WHERE field='crs' AND dataset_id='d1'"
        ).fetchone()
        assert crs["value"] == "EPSG:3067"

    @pytest.mark.anyio
    async def test_avainkentat_tunnistetaan_sarakkeista(
        self, conn: sqlite3.Connection
    ) -> None:
        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK, fields=[("kuntakoodi", "string")], http_status=200
            )

        await run_probe(conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe})
        rivi = conn.execute(
            "SELECT value, source_detail FROM enrichments WHERE field='joinable_keys'"
        ).fetchone()
        assert rivi is not None
        assert "kuntakoodi" in rivi["value"]
        assert "heuristic" in rivi["source_detail"]

    @pytest.mark.anyio
    async def test_epaonnistuminen_kirjataan_syineen(
        self, conn: sqlite3.Connection
    ) -> None:
        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.HTTP_ERROR, detail="HTTP 404", http_status=404
            )

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        assert yhteenveto["http_error"] == 2
        rivi = conn.execute(
            "SELECT status, detail FROM probe_results WHERE resource_id='r-wfs'"
        ).fetchone()
        assert rivi["status"] == "http_error"
        assert rivi["detail"] == "HTTP 404"

    @pytest.mark.anyio
    async def test_yhden_kaatuminen_ei_lopeta_ajoa(
        self, conn: sqlite3.Connection
    ) -> None:
        async def raivostuva(resource: dict[str, Any], client: Any) -> ProbeResult:
            raise RuntimeError("odottamaton")

        async def onnistuva(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")], http_status=200)

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": raivostuva, "csv": onnistuva}
        )
        assert yhteenveto["ok"] == 1
        rivi = conn.execute(
            "SELECT status FROM probe_results WHERE resource_id='r-wfs'"
        ).fetchone()
        assert rivi["status"] == "parse_error"
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_run.py -q`
Expected: FAIL — `ImportError: cannot import name 'run_probe' from 'aura.probe'`

- [ ] **Step 3: Kirjoita orkestrointi**

```python
# src/aura/probe/__init__.py
"""Probe-vaihe: skeema johdetaan rajapinnasta, ei metatiedosta.

Tämä on ``aura infer-schemas`` laajennettuna. Vanha versio osasi CSV:n ja
JSONin, ajoi kerran eikä koskaan uudestaan, tulosti virheet ja unohti ne.
Kattavuus jäi 54 datasettiin 12 918:sta.

Kolme lisäystä ratkaisevat sen: WFS ja WMS mukaan, TTL joka porrastuu vian
luonteen mukaan, ja kirjanpito johon epäonnistuminen jää näkyviin.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from aura.constants import user_agent
from aura.database import add_enrichment, upsert_probe_result, upsert_resource_schema
from aura.probe import pxweb as pxweb_probe
from aura.probe import tabular as tabular_probe
from aura.probe import wfs as wfs_probe
from aura.probe import wms as wms_probe
from aura.probe.derive import auth_from_status
from aura.probe.types import ProbeResult, ProbeStatus
from aura.tools.schema import detect_joinable_keys

logger = logging.getLogger(__name__)

Prober = Callable[[dict[str, Any], httpx.AsyncClient], Awaitable[ProbeResult]]

#: Resurssiformaatti → probe_type.
PROBE_TYPES: dict[str, str] = {
    "WFS": "wfs",
    "WMS": "wms",
    "PXWEB": "pxweb",
    "CSV": "csv",
    "JSON": "json",
    "GEOJSON": "json",
}

#: TTL vian luonteen mukaan. Poissa oleva palvelu ei palaa viikossa, hidas
#: voi — ja 404:n uudelleenyrittäminen joka kierroksella on
#: kohteliaisuusongelma joka ei tuota mitään.
TTL_DAYS: dict[str, int] = {
    "ok": 30,
    "timeout": 7,
    "http_error_transient": 7,
    "http_error_permanent": 90,
    "parse_error": 30,
    "empty": 30,
}

#: Kutsua sekunnissa samalle isännälle. Luku ei ole arvaus: 6-rinnakkainen
#: ajo PxWebiä vasten menetti 3 808 taulua 3 928:sta, koska HTTP 429 näytti
#: tyhjältä tulokselta eikä virheeltä.
RATE_LIMIT_PER_SECOND = 2.0

_COMMIT_EVERY = 50
_TIMEOUT = 30.0

DEFAULT_PROBERS: dict[str, Prober] = {
    "wfs": wfs_probe.probe,
    "wms": wms_probe.probe,
    "pxweb": pxweb_probe.probe,
    "csv": tabular_probe.probe,
    "json": tabular_probe.probe,
}


def _ttl_key(status: str, detail: str) -> str:
    """TTL-avain tilasta ja syystä."""
    if status == ProbeStatus.HTTP_ERROR:
        pysyva = any(code in detail for code in ("404", "410"))
        return "http_error_permanent" if pysyva else "http_error_transient"
    return status


def select_targets(
    conn: Any,
    *,
    now: str,
    source: str = "",
    fmt: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Valitse probattavat resurssit: probaamattomat ensin, sitten vanhimmat.

    Vanhentuneisuus lasketaan tilakohtaisella TTL:llä, joten SQL palauttaa
    ehdokkaat ja Python karsii ne joiden aika ei ole vielä tullut. Ehtojen
    kirjoittaminen SQL:ään vaatisi CASE-lausekkeen jokaiselle tilalle,
    eivätkä kohdemäärät ole sellaisia että sillä olisi väliä.
    """
    formats = ",".join(f"'{f}'" for f in PROBE_TYPES)
    sql = f"""
        SELECT r.id, r.dataset_id, r.format, r.url,
               p.status AS prev_status, p.detail AS prev_detail,
               p.probed_at AS prev_probed_at
        FROM resources r
        JOIN datasets d ON d.id = r.dataset_id
        LEFT JOIN probe_results p ON p.resource_id = r.id
        WHERE UPPER(r.format) IN ({formats})
          AND r.url != ''
    """
    params: list[Any] = []
    if source:
        sql += " AND d.source = ?"
        params.append(source)
    if fmt:
        sql += " AND UPPER(r.format) = ?"
        params.append(fmt.upper())
    sql += " ORDER BY (p.probed_at IS NULL) DESC, p.probed_at"

    nyt = datetime.fromisoformat(now)
    targets: list[dict[str, Any]] = []
    for row in conn.execute(sql, params):
        if row["prev_probed_at"]:
            avain = _ttl_key(row["prev_status"] or "", row["prev_detail"] or "")
            ikaraja = nyt - timedelta(days=TTL_DAYS.get(avain, 30))
            if datetime.fromisoformat(row["prev_probed_at"]) > ikaraja:
                continue
        targets.append(dict(row))
        if len(targets) >= limit:
            break
    return targets


def _store(
    conn: Any, target: dict[str, Any], result: ProbeResult, now: str
) -> None:
    """Kirjaa yhden proben tulos: kirjanpito aina, tieto jos sitä tuli."""
    probe_type = PROBE_TYPES[(target["format"] or "").upper()]
    upsert_probe_result(
        conn,
        target["id"],
        target["dataset_id"],
        probe_type,
        result.status,
        result.detail,
        now,
    )
    if not result.ok:
        return

    if result.fields:
        upsert_resource_schema(conn, target["id"], target["dataset_id"], result.fields)
        keys = detect_joinable_keys([nimi for nimi, _ in result.fields])
        if keys:
            _add_once(
                conn,
                target["dataset_id"],
                "joinable_keys",
                json.dumps(keys, ensure_ascii=False),
                confidence="medium",
                source_detail="Auto-detected from field names (heuristic)",
            )

    for kentta, arvo in result.enrichments:
        _add_once(conn, target["dataset_id"], kentta, arvo)

    for kentta, arvo in auth_from_status(result.http_status, target["url"]):
        _add_once(conn, target["dataset_id"], kentta, arvo)


def _add_once(
    conn: Any,
    dataset_id: str,
    field: str,
    value: str,
    confidence: str = "high",
    source_detail: str = "",
) -> None:
    """Lisää enrichment ellei samaa arvoa jo ole.

    Probe ajetaan uudestaan TTL:n välein, eikä muuttumaton tulos saa kasvattaa
    riviä joka ajolla.
    """
    olemassa = conn.execute(
        "SELECT 1 FROM enrichments WHERE dataset_id = ? AND field = ? AND value = ?"
        " LIMIT 1",
        (dataset_id, field, value),
    ).fetchone()
    if olemassa:
        return
    add_enrichment(
        conn,
        dataset_id,
        field,
        value,
        confidence=confidence,
        source_type="probe",
        source_detail=source_detail,
    )


async def run_probe(
    conn: Any,
    *,
    source: str = "",
    fmt: str = "",
    limit: int = 50,
    now: str = "",
    client: httpx.AsyncClient | None = None,
    probers: dict[str, Prober] | None = None,
) -> dict[str, int]:
    """Aja probe valituille kohteille ja kirjaa tulokset.

    Returns:
        Yhteenveto tiloittain, esim. ``{"ok": 12, "http_error": 3}``.
    """
    timestamp = now or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")
    active = probers or DEFAULT_PROBERS
    targets = select_targets(
        conn, now=timestamp, source=source, fmt=fmt, limit=limit
    )
    summary: dict[str, int] = defaultdict(int)
    if not targets:
        return dict(summary)

    last_call: dict[str, float] = {}
    loop = asyncio.get_running_loop()

    async def _throttle(url: str) -> None:
        host = urlparse(url).netloc
        vali = 1.0 / RATE_LIMIT_PER_SECOND
        edellinen = last_call.get(host)
        nyt = loop.time()
        if edellinen is not None and nyt - edellinen < vali:
            await asyncio.sleep(vali - (nyt - edellinen))
        last_call[host] = loop.time()

    own_client = client is None
    http = client or httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": user_agent("probe")}
    )
    try:
        for i, target in enumerate(targets, 1):
            probe_type = PROBE_TYPES[(target["format"] or "").upper()]
            prober = active.get(probe_type)
            if prober is None:
                continue
            await _throttle(target["url"])
            try:
                result = await prober(target, http)
            except Exception as e:  # prober ei saa kaataa koko ajoa
                logger.warning("[probe] %s kaatui: %s", target["id"], e)
                result = ProbeResult(
                    status=ProbeStatus.PARSE_ERROR, detail=str(e)[:100]
                )
            _store(conn, target, result, timestamp)
            summary[result.status] += 1
            if i % _COMMIT_EVERY == 0:
                conn.commit()
        conn.commit()
    finally:
        if own_client:
            await http.aclose()

    return dict(summary)
```

- [ ] **Step 4: Aja testit**

Run: `python -m pytest tests/test_probe_run.py -q`
Expected: PASS

- [ ] **Step 5: Lint, tyypit ja commit**

```bash
ruff check src/aura/probe tests/test_probe_run.py && mypy src/aura/probe
git add src/aura/probe/__init__.py tests/test_probe_run.py
git commit -m "feat: probe-ajo TTL:llä, kirjanpidolla ja isäntäkohtaisella tahdilla

Kolme asiaa joita infer-schemas ei tehnyt ja jotka pitivät kattavuuden
54 datasetissä: TTL joka porrastuu vian luonteen mukaan, epäonnistumisen
kirjaus, ja tahdinsäätö per isäntä globaalin viiveen sijaan.

Yhden proberin kaatuminen ei lopeta ajoa — se kirjautuu tuloksena."
```

---

### Task 9: Pinta — CLI ja MCP

**Files:**
- Modify: `src/aura/cli.py` (eriytä `build_parser`, lisää `probe`, tee `infer-schemas`:sta alias, poista `_infer_schemas`)
- Modify: `src/aura/tools/admin.py` (uusi `probe_schemas`-työkalu)
- Test: `tests/test_probe_cli.py`

**Interfaces:**
- Consumes: `aura.probe.run_probe`
- Produces: `aura.probe.format_probe_summary(summary: dict[str, int]) -> str`,
  CLI-komento `aura probe`, MCP-työkalu `probe_schemas`

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_probe_cli.py
"""Testit probe-komennon pinnalle.

infer-schemas jää aliakseksi: vanha nimi ei saa kadota käsistä, mutta uusi
nimi kertoo mitä komento tekee. probe-sizes on eri komento (koon mittaus)
eikä siihen kosketa.
"""

from __future__ import annotations

from aura.cli import build_parser
from aura.probe import format_probe_summary


def test_probe_komento_on_olemassa() -> None:
    parser = build_parser()
    args = parser.parse_args(["probe", "--limit", "5", "--format", "WFS"])
    assert args.command == "probe"
    assert args.limit == 5
    assert args.format == "WFS"


def test_infer_schemas_on_alias() -> None:
    parser = build_parser()
    args = parser.parse_args(["infer-schemas", "--limit", "5"])
    assert args.command == "infer-schemas"


def test_probe_sizes_sailyy_erillisena() -> None:
    parser = build_parser()
    args = parser.parse_args(["probe-sizes"])
    assert args.command == "probe-sizes"


def test_yhteenveto_kertoo_epaonnistumiset() -> None:
    teksti = format_probe_summary({"ok": 12, "http_error": 3, "timeout": 1})
    assert "12" in teksti and "3" in teksti
    assert "http_error" in teksti or "virhe" in teksti.lower()


def test_tyhja_ajo_sanotaan_aaneen() -> None:
    assert format_probe_summary({}).strip() != ""
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_cli.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_parser' from 'aura.cli'`

Parseri rakennetaan tällä hetkellä `main()`-funktion sisällä (`cli.py:16-18`),
joten sitä ei voi testata ajamatta komentoa.

- [ ] **Step 2b: Eriytä parseri omaksi funktiokseen**

Siirrä `main()`:n alusta kaikki `argparse`-määrittelyt funktioon
`build_parser() -> argparse.ArgumentParser`, joka palauttaa valmiin parserin.
`main()` alkaa tämän jälkeen riveillä:

```python
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
```

Muuta ei siirretä. Aja `python -m pytest tests/test_cli.py -q` ja varmista
että kaikki menee yhä läpi ennen kuin jatkat — tämä on puhdas siirto.

- [ ] **Step 3: Lisää yhteenvedon muotoilu**

`src/aura/probe/__init__.py`:hyn:

```python
def format_probe_summary(summary: dict[str, int]) -> str:
    """Muotoile ajon yhteenveto ihmiselle.

    Epäonnistumiset näkyvät omina riveinään: kokonaisluku joka ei erottele
    onnistumista virheestä kertoo vähemmän kuin ei mitään.
    """
    if not summary:
        return "Ei probattavia kohteita (kaikki tuoreita tai ei sopivia resursseja)."
    rivit = [f"Probattu {sum(summary.values())} resurssia:"]
    for status in ("ok", "http_error", "timeout", "parse_error", "empty"):
        if summary.get(status):
            rivit.append(f"  {status:12} {summary[status]}")
    return "\n".join(rivit)
```

- [ ] **Step 4: Lisää CLI-komento**

`src/aura/cli.py`, `probe-sizes`-parserin jälkeen:

```python
    for nimi, ohje in (
        ("probe", "Johda skeema rajapinnoista (WFS, WMS, PxWeb, CSV, JSON)"),
        ("infer-schemas", "Vanha nimi komennolle 'probe'"),
    ):
        p = subparsers.add_parser(nimi, help=ohje)
        p.add_argument("--source", default="", help="Rajaa lähteeseen")
        p.add_argument("--format", default="", help="Rajaa formaattiin (esim. WFS)")
        p.add_argument("--limit", type=int, default=50, help="Kohteiden määrä (oletus 50)")
        p.add_argument(
            "--max-age-days",
            type=int,
            default=0,
            help="Ohita TTL ja probaa kaikki tätä vanhemmat",
        )
        p.add_argument("--dry-run", action="store_true", help="Näytä kohteet, älä aja")
```

Poista vanha `infer-schemas`-parseri ja `_infer_schemas`-funktio. Käsittelijä:

```python
    elif args.command in ("probe", "infer-schemas"):
        if args.command == "infer-schemas":
            print("Huom: 'infer-schemas' on nyt 'probe'. Vanha nimi toimii yhä.")
        asyncio.run(
            _probe(
                source=args.source,
                fmt=args.format,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        )
```

ja funktio:

```python
async def _probe(
    source: str = "", fmt: str = "", limit: int = 50, dry_run: bool = False
) -> None:
    """Aja probe-vaihe."""
    import aura.server  # noqa: F401 — ratkaise kiertoimport ennen tools-tuonteja
    from datetime import UTC, datetime

    from aura.database import get_connection, run_migrations
    from aura.probe import format_probe_summary, run_probe, select_targets

    conn = get_connection()
    run_migrations(conn)
    now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")

    if dry_run:
        targets = select_targets(conn, now=now, source=source, fmt=fmt, limit=limit)
        print(f"{len(targets)} kohdetta:")
        for t in targets[:20]:
            print(f"  {t['format']:8} {t['url'][:90]}")
        return

    summary = await run_probe(conn, source=source, fmt=fmt, limit=limit, now=now)
    print(format_probe_summary(summary))
```

- [ ] **Step 5: Lisää MCP-työkalu**

`src/aura/tools/admin.py`, `probe_sizes`-työkalun viereen:

```python
@mcp.tool()
async def probe_schemas(
    source: str = "", limit: int = 50, ctx: Context | None = None
) -> str:
    """Johda datasettien skeema suoraan rajapinnoista (WFS, WMS, PxWeb, CSV).

    Kirjoittaa tuloksen kantaan: sarakkeet resurssin skeemaksi, dimensiot ja
    layerit rikastuksiksi. Epäonnistuminen kirjataan syineen, ja se näkyy
    describe()-vastauksessa.

    Args:
        source: Rajaa lähteeseen (esim. "gtk"). Tyhjä = kaikki.
        limit: Probattavien resurssien enimmäismäärä (oletus 50).
    """
    from aura.probe import format_probe_summary, run_probe

    conn = _server._get_conn(ctx)
    summary = await run_probe(conn, source=source, limit=limit)
    return format_probe_summary(summary)
```

- [ ] **Step 6: Aja testit ja commit**

```bash
python -m pytest tests/test_probe_cli.py tests/test_cli.py -q
ruff check src/aura/cli.py src/aura/probe src/aura/tools/admin.py tests/test_probe_cli.py
mypy src/aura/cli.py src/aura/probe src/aura/tools/admin.py
git add src/aura/cli.py src/aura/probe/__init__.py src/aura/tools/admin.py tests/test_probe_cli.py
git commit -m "feat: aura probe -komento ja probe_schemas-työkalu

infer-schemas jää aliakseksi. Logiikka siirtyi CLI:stä pakettiin, joten se
on nyt kutsuttavissa myös MCP:stä — aiemmin sadan rivin funktio
CLI-tiedostossa oli saavuttamaton kummallekin."
```

---

### Task 10: Näkyvyys — describe ja stats

**Files:**
- Modify: `src/aura/tools/describe.py:148-170` (`_format_schema_section`)
- Modify: `src/aura/database.py` (`get_stats`) ja `src/aura/search.py` (`format_stats`)
- Test: `tests/test_probe_visibility.py`

**Interfaces:**
- Consumes: `probe_results`-taulu
- Produces: `aura.tools.describe._format_probe_failure(conn, dataset_id) -> str`

- [ ] **Step 1: Kirjoita kaatuva testi**

```python
# tests/test_probe_visibility.py
"""Testit sille että epäonnistunut probe näkyy siellä missä sitä katsotaan.

"Ei saatu selville" on agentille tietoa, ei tyhjä. Ilman tätä puuttuva
skeema näyttää samalta kuin skeema jota ei ole yritettykään hakea, ja
agentti päättelee aineiston olevan käyttökelvoton.
"""

from __future__ import annotations

import sqlite3

import pytest

from aura.database import init_db, upsert_probe_result
from aura.tools.describe import _format_probe_failure


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    c.commit()
    return c


def test_epaonnistuminen_nakyy_syineen(conn: sqlite3.Connection) -> None:
    upsert_probe_result(
        conn, "r1", "d1", "wfs", "http_error", "HTTP 404", "2026-08-19T10:00:00"
    )
    conn.commit()
    teksti = _format_probe_failure(conn, "d1")
    assert "HTTP 404" in teksti
    assert "2026-08-19" in teksti


def test_onnistunut_probe_ei_lisaa_rivia(conn: sqlite3.Connection) -> None:
    upsert_probe_result(conn, "r1", "d1", "wfs", "ok", "", "2026-08-19T10:00:00")
    conn.commit()
    assert _format_probe_failure(conn, "d1") == ""


def test_probaamaton_ei_lisaa_rivia(conn: sqlite3.Connection) -> None:
    assert _format_probe_failure(conn, "d1") == ""
```

- [ ] **Step 2: Aja testi ja varmista että se kaatuu**

Run: `python -m pytest tests/test_probe_visibility.py -q`
Expected: FAIL — `ImportError: cannot import name '_format_probe_failure'`

- [ ] **Step 3: Toteuta näkyvyys**

`src/aura/tools/describe.py`:hyn, `_format_schema_section`-funktion viereen:

```python
def _format_probe_failure(conn: Any, dataset_id: str) -> str:
    """Kerro epäonnistuneesta skeemanhausta, tai tyhjä jos ei ole.

    Puuttuva skeema näyttää muuten samalta kuin skeema jota ei ole
    yritettykään hakea. Ero on agentille olennainen: ensimmäinen on
    palvelun vika, toinen katalogin.
    """
    rows = conn.execute(
        "SELECT probe_type, status, detail, probed_at FROM probe_results"
        " WHERE dataset_id = ? AND status != 'ok' ORDER BY probed_at DESC",
        (dataset_id,),
    ).fetchall()
    if not rows:
        return ""
    parts = ["\n\n### Skeemaa ei saatu selville\n"]
    for row in rows:
        paiva = (row["probed_at"] or "")[:10]
        syy = row["detail"] or row["status"]
        parts.append(f"- {row['probe_type'].upper()}: {syy} ({paiva})")
    return "\n".join(parts)
```

Kutsu se `describe`-funktiossa heti `_format_schema_section`-kutsun jälkeen ja
liitä tulos samaan vastaukseen.

Kattavuus `stats`-vastaukseen. `stats`-työkalu delegoi
(`format_stats(get_stats(conn))`), joten muutos menee molempiin päihin.

`src/aura/database.py`, `get_stats`-funktion palauttamaan sanakirjaan:

```python
    probe_rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM probe_results GROUP BY status"
    ).fetchall()
    stats["probe_total"] = sum(r["n"] for r in probe_rows)
    stats["probe_ok"] = next((r["n"] for r in probe_rows if r["status"] == "ok"), 0)
```

`src/aura/search.py`, `format_stats`-funktion `parts`-listaan ennen
`return`-riviä:

```python
    if stats.get("probe_total"):
        parts.append(
            f"\n**Skeema johdettu:** {stats['probe_ok']}/{stats['probe_total']} "
            "resurssista onnistuneesti"
        )
```

Huom: `get_stats` rakentaa `stats`-sanakirjan paikallisesti; lisää rivit
siihen kohtaan jossa sanakirja on jo olemassa mutta ei vielä palautettu.

- [ ] **Step 4: Aja testit**

Run: `python -m pytest tests/test_probe_visibility.py tests/test_server.py -q`
Expected: PASS

- [ ] **Step 5: Aja koko paketti ja commit**

```bash
python -m pytest tests/ -q
ruff check src/ tests/ | tail -3
mypy src/aura | tail -3
git add src/aura/tools/describe.py src/aura/database.py src/aura/search.py tests/test_probe_visibility.py
git commit -m "feat: epäonnistunut probe näkyy describe-vastauksessa

Puuttuva skeema näytti samalta kuin skeema jota ei ole yritettykään hakea.
Ero on agentille olennainen: ensimmäinen on palvelun vika, toinen
katalogin."
```

---

### Task 11: Ensimmäinen ajo ja mittaus

**Files:**
- Modify: `docs/superpowers/specs/2026-08-19-probe-vaihe-design.md` (mitatut luvut)

Suunnitelma ei aseta kattavuustavoitetta etukäteen, koska se olisi arvaus.
Tämä tehtävä mittaa tuloksen.

- [ ] **Step 1: Aja migraatiot ja kuivaharjoitus**

```bash
source .venv/bin/activate
python -m aura.cli migrate
python -m aura.cli probe --format WFS --limit 20 --dry-run
```

- [ ] **Step 2: Aja WFS-erä ja katso mitä tuli**

```bash
python -m aura.cli probe --format WFS --limit 50
python -c "
import sqlite3
c = sqlite3.connect('data/aura.db'); c.row_factory = sqlite3.Row
for r in c.execute('SELECT status, COUNT(*) n FROM probe_results GROUP BY status'):
    print(f'{r[\"status\"]:14} {r[\"n\"]}')
print('sarakkeita:', c.execute('SELECT COUNT(*) FROM resource_schema').fetchone()[0])
"
```

- [ ] **Step 3: Tarkista yksi onnistunut ja yksi epäonnistunut käsin**

```bash
python -c "
import sqlite3
c = sqlite3.connect('data/aura.db'); c.row_factory = sqlite3.Row
for tila in ('ok', 'http_error'):
    r = c.execute('SELECT * FROM probe_results WHERE status=? LIMIT 1', (tila,)).fetchone()
    if r: print(dict(r))
"
```

Onnistuneen kohdalla `resource_schema`-rivien on vastattava palvelun
todellisia sarakkeita — tarkista yksi selaimella. Epäonnistuneen kohdalla
`detail`-kentän on kerrottava syy, ei pelkkää tilaa.

- [ ] **Step 4: Aja loput erissä ja kirjaa luvut**

```bash
for i in 1 2 3 4 5; do python -m aura.cli probe --limit 200; done
```

- [ ] **Step 5: Päivitä spec mitatuilla luvuilla ja commit**

Korvaa specin "Onnistumisen mitta" -kappaleen viimeinen virke todellisilla
luvuilla: montako resurssia probattiin, montako onnistui tilaa kohden, ja
paljonko `resource_schema` ja `joinable_keys` kasvoivat.

```bash
git add docs/superpowers/specs/2026-08-19-probe-vaihe-design.md
git commit -m "docs: probe-vaiheen ensimmäisen ajon mitatut luvut"
```

---

## Itsetarkastus

**Spec-kattavuus.** Specin jokainen kohta osuu tehtävään: kolme varastoa
(taskit 3–6), `probe_results` (task 1), TTL-porrastus (task 8), tahdinsäätö
per isäntä (task 8), `infer-schemas`-laajennus ja alias (taskit 6 ja 9),
`use_case_suggested` (task 2), `example_request` (taskit 2 ja 3),
`auth_method` (task 7), epäonnistumisen näkyvyys (task 10), mittaus (task 11).

**Nimien yhtenäisyys.** `ProbeResult.fields` on `list[tuple[str, str]]` kaikissa
probereissa ja `upsert_resource_schema` ottaa saman muodon.
`ProbeResult.enrichments` on `list[tuple[str, str]]`, jonka `_store` purkaa
`_add_once`-kutsuiksi. `PROBE_TYPES` kartoittaa formaatin proberin avaimeksi, ja
`DEFAULT_PROBERS` käyttää samoja avaimia.

**Tiedossa oleva epävarmuus.** Task 3:n `parse_feature_types` sisältää ehdon
joka erottaa featuretyypin oman elementin sarakkeista. Ehto on kirjoitettu
fixturen mukaan, ja step 5 kertoo mitä tehdä jos se ei riitä: yksinkertaista
ehdoksi "ohita elementit joiden type päättyy FeatureType-merkkijonoon".
Tämä on ainoa kohta jossa toteuttaja saattaa joutua säätämään koodia testin
ohjaamana.
