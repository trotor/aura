"""Rakenteellinen testi: jokainen kantaan kirjoittava @mcp.tool on WRITE_TOOL_NAMESissa.

Tausta (#C1-loppykatselmus): ``probe_schemas`` puuttui ``WRITE_TOOL_NAMES``-
joukosta, ja aiempi testi (``test_write_tool_names_are_the_expected_set``)
väitti vain että joukko on tasan tietty lista — muutosdetektori, joka naulaa
puutteen sen sijaan että havaitsisi sen. Tämä testi yrittää oikeasti
*havaita* kirjoittavan toolin ilman että sen nimi on lueteltu käsin etukäteen.
Samalla ajolla se löysi kolme muuta samaa luokkaa olevaa puutetta —
``suggest_yso_tags``, ``quality_report``, ``health_check``. Kahdelle
ensimmäiselle korjaus oli gating; ``quality_report``:lle korjaus oli
kirjoituksen suojaaminen omalla ``except Exception``illä, koska sen
kirjoitushaara on toimitettavassa kannassa käytännössä kuollut (jokainen
datasetti on jo pisteytetty) — ks. ``_SAFE_ALREADY_GUARDED``.

**Menetelmä.** Funktio tulkitaan kantaan kirjoittavaksi jos sen rungossa on
suora ``<nimi>.execute``-kutsu jonka SQL-teksti sisältää INSERT/UPDATE/
DELETE-avainsanan, missä ``<nimi>`` viittaa jaettuun ``aura.db``-yhteyteen.
"Jaettuun yhteyteen viittaava nimi" ei ole pelkkä parametri nimeltä
``conn`` — se olisi jättänyt kiinni ottamatta juuri sen kutsukonvention
jota ``@mcp.tool``-funktiot käyttävät (ne ottavat ``ctx``:n, hakevat
yhteyden PAIKALLISMUUTTUJAAN, ja se muuttuja voi kantautua edelleen
apufunktiolle jonka oma parametri on nimetty miten tahansa). Kaksivaiheinen
päättely:

1. **Lähteet per funktio.** Nimi on jaettuun yhteyteen viittaava jos se on
   joko (a) parametri nimeltä ``conn``, tai (b) paikallismuuttuja joka on
   sijoitettu suoraan ``_get_conn()``- tai ``get_connection()``-kutsun
   tulokseksi — näitä kahta funktiota kutsutaan JUURI tämän yhteyden
   hakemiseen koko koodikannassa, joten kutsun KOHDE (ei muuttujan nimi)
   on luotettava signaali.
2. **Levitys kutsurajan yli (kiintopiste).** Jos funktio ``f`` kutsuu
   funktiota ``g`` ja kutsun argumentti tietyssä positiossa/avainsanalla on
   ``f``:n oma jaettuun yhteyteen viittaava nimi, ``g``:n VASTAAVA
   parametri merkitään myös jaettuun yhteyteen viittaavaksi — riippumatta
   siitä miksi ``g`` on sen itse nimennyt (``conn``, ``db``, mikä tahansa).
   Tämä suljetaan kiintopisteellä, koska ketju voi olla useamman kutsun
   pituinen.

Vasta näiden nimien selvittyä tarkistetaan onko funktion rungossa
``<nimi>.execute(...)``-kutsu jonka SQL-teksti on kirjoittava.

``with sqlite3.connect(...) as conn:`` ei koskaan täsmää sääntöön (1),
koska ``connect`` ei ole ``_get_conn``/``get_connection`` — tämä erottaa
``aura.telemetry.record_zero_result``:n oman, erillisen ja tarkoituksella
kirjoitussuojauksen ulkopuolella olevan telemetriakannan jaetusta
``aura.db``-yhteydestä ilman erillistä poikkeuslistaa.

Kutsugraafi kootaan koko ``aura``-paketista nimen perusteella (myös
paikalliset ``import x as y``-aliakset ratkaistaan), ja "kirjoittaa"-tila
leviää siitä transitiivisesti tooliin asti omalla, erillisellä
kiintopisteellään bare name -täsmäyksen kautta. Nimellä sovittaminen ei
ratkaise moduulirajoja tarkasti, joten tulos on yliarvio: kahden eri
moduulin samanniminen funktio voi sekoittua keskenään. Siksi testi vaatii
vain että havaitut kirjoittajat SISÄLTYVÄT ``WRITE_TOOL_NAMES``iin — ei
että joukot ovat identtiset (ks. myös ``server.py``:n ``WRITE_TOOL_NAMES``-
kommentti käsin ylläpidosta).

**_INFRA-poikkeus.** ``_get_conn``/``get_connection``/``init_db``/
``run_migrations`` on jätettävä pois "kirjoittaa"-tilan TODISTEENA
kutsujalleen (mutta ei pois säännöstä 1 — ne OVAT edelleen yhteyden
lähteitä): ne ovat jaettua plumbingia jota käytännössä JOKAINEN tooli
kutsuu (``conn = _server._get_conn(ctx)``), ja ``_get_conn``:n
CLI/testi-fallback-polku kutsuu ``init_db``:tä, joka aidosti kirjoittaa
(migraatiot). Ilman tätä rajausta kiintopiste leviäisi jokaiseen tooliin
ja testi menettäisi erottelukykynsä täysin — todennettu kokeilemalla:
ilman poikkeusta havaittu joukko oli 33/33 toolia.

**Tunnettu rajoitus.** Dynaamisesti valittua kutsua (esim.
``prober = active.get(probe_type); await prober(...)`` proben orkestroin-
nissa, tai ``populate_reference``:n populaattorirekisteri) ei seurata,
koska kutsun kohde ei näy nimenä lähdekoodissa. Jos uusi kirjoittava tooli
päätyy kantaan vain tällaisen epäsuoran polun kautta, tämä testi ei sitä
löydä — silloin ``WRITE_TOOL_NAMES`` on päivitettävä käsin, ja syy on
dokumentoitava tuonne (ks. server.py).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from aura.server import WRITE_TOOL_NAMES

_SRC = Path(__file__).resolve().parent.parent / "src" / "aura"

#: Kirjoittava SQL-lauseke. Rajattu tunnettuihin muotoihin (ei pelkkää
#: "UPDATE"-sanaa), jotta kenttien nimet (esim. "update_frequency_actual")
#: eivät osu vahingossa. \b ei laukea sanan sisällä olevaan alaviivaan,
#: joten "update_frequency_actual" ei täsmää "UPDATE "-vaatimukseen.
_WRITE_SQL = re.compile(
    r"\b(INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b",
    re.IGNORECASE,
)

#: Funktiot joita kutsutaan JUURI jaetun aura.db-yhteyden hakemiseen —
#: paikallismuuttuja joka on sijoitettu jommankumman tulokseksi viittaa
#: jaettuun yhteyteen riippumatta muuttujan nimestä. Ks. moduulin
#: yläkommentin sääntö 1.
_CONN_SOURCE_CALLS = {"_get_conn", "get_connection"}

#: Jaettu plumbing joka ei saa toimia TODISTEENA kutsujalleen — ks.
#: tiedoston yläkommentti "_INFRA-poikkeus".
_INFRA = {"_get_conn", "_get_yso", "get_connection", "init_db", "run_migrations"}

#: Toolit joiden ainoa havaittu kirjoitus on jo suojattu niin ettei se voi
#: näkyä käyttäjälle eikä kaataa kutsua read-only-instanssilla — ks.
#: server.py:n WRITE_TOOL_NAMES-kommentti.
#: - query_data: opitun skeeman best-effort-tallennus omassa
#:   except Exception -lohkossaan (tools/data.py).
#: - quality_report: laskee pisteet lennossa ja YRITTÄÄ tallentaa ne omassa
#:   except Exception -lohkossaan, mutta muodostaa vastauksen lennossa
#:   lasketuista pisteistä riippumatta tallennuksen onnistumisesta
#:   (tools/quality.py) — lukupolku toimii read-only-kannassa.
_SAFE_ALREADY_GUARDED = {"query_data", "quality_report"}

FuncDef = ast.FunctionDef | ast.AsyncFunctionDef


def _iter_functions(tree: ast.Module) -> list[FuncDef]:
    """Kaikki funktiot moduulista, myös sisäkkäiset ja metodit."""
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _import_aliases(node: ast.AST) -> dict[str, str]:
    """``asname -> oikea nimi`` kaikista tämän solmun import-lausekkeista."""
    aliases: dict[str, str] = {}
    for n in ast.walk(node):
        if isinstance(n, ast.ImportFrom):
            for alias in n.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
        elif isinstance(n, ast.Import):
            for alias in n.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name.rsplit(".", 1)[-1]
    return aliases


def _call_target_name(call: ast.Call, aliases: dict[str, str]) -> str | None:
    """Yhden kutsun kohteen nimi (alias ratkaistuna), tai None jos ei tunnisteta."""
    fn = call.func
    if isinstance(fn, ast.Name):
        return aliases.get(fn.id, fn.id)
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _call_names(node: FuncDef, aliases: dict[str, str]) -> set[str]:
    """Kaikkien kutsujen kohteiden nimet funktion rungosta."""
    names: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            target = _call_target_name(n, aliases)
            if target is not None:
                names.add(target)
    return names


def _is_mcp_tool(node: FuncDef) -> bool:
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "tool"
            and isinstance(target.value, ast.Name)
            and target.value.id == "mcp"
        ):
            return True
    return False


def _param_names(node: FuncDef) -> list[str]:
    """Positioparametrien nimet järjestyksessä (posonly + tavalliset)."""
    return [a.arg for a in (*node.args.posonlyargs, *node.args.args)]


def _seed_conn_names(node: FuncDef, source: str, aliases: dict[str, str]) -> set[str]:
    """Sääntö 1: parametri ``conn``, tai paikallismuuttuja _get_conn/get_connection-kutsusta."""
    names: set[str] = set()
    all_args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if any(a.arg == "conn" for a in all_args):
        names.add("conn")
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            if _call_target_name(n.value, aliases) in _CONN_SOURCE_CALLS:
                for target in n.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
    return names


def _compute_writing_tools() -> set[str]:
    """Nimet kaikista @mcp.tool-funktioista jotka staattisesti kirjoittavat kantaan."""
    by_name: dict[str, list[FuncDef]] = {}
    sources: dict[int, str] = {}
    aliases_by_fn: dict[int, dict[str, str]] = {}
    tool_names: dict[int, str] = {}

    for path in sorted(_SRC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        module_aliases = _import_aliases(tree)
        for fn in _iter_functions(tree):
            key = id(fn)
            by_name.setdefault(fn.name, []).append(fn)
            sources[key] = source
            aliases_by_fn[key] = {**module_aliases, **_import_aliases(fn)}
            if _is_mcp_tool(fn):
                tool_names[key] = fn.name

    # Vaihe 1: sääntö 1 -nimet per funktio (ei riipu muista funktioista).
    conn_names: dict[int, set[str]] = {}
    for fn_list in by_name.values():
        for fn in fn_list:
            key = id(fn)
            conn_names[key] = _seed_conn_names(fn, sources[key], aliases_by_fn[key])

    # Vaihe 2: levitä nimet kutsurajan yli kiintopisteellä (sääntö 2).
    # Positio- ja avainsana-argumentit molemmat: jos kutsuja välittää oman
    # jaettuun yhteyteen viittaavan nimensä argumenttina, kutsutun funktion
    # VASTAAVA parametri on myös jaettuun yhteyteen viittaava — riippumatta
    # siitä miksi kutsuttu funktio on sen itse nimennyt.
    changed = True
    while changed:
        changed = False
        for fn_list in by_name.values():
            for fn in fn_list:
                key = id(fn)
                caller_names = conn_names[key]
                if not caller_names:
                    continue
                aliases = aliases_by_fn[key]
                for call in ast.walk(fn):
                    if not isinstance(call, ast.Call):
                        continue
                    target = _call_target_name(call, aliases)
                    if target is None:
                        continue
                    for callee in by_name.get(target, ()):
                        ckey = id(callee)
                        positional = _param_names(callee)
                        for i, arg in enumerate(call.args):
                            if not (isinstance(arg, ast.Name) and arg.id in caller_names):
                                continue
                            if i < len(positional) and positional[i] not in conn_names[ckey]:
                                conn_names[ckey].add(positional[i])
                                changed = True
                        for kw in call.keywords:
                            if kw.arg is None or not isinstance(kw.value, ast.Name):
                                continue
                            if kw.value.id not in caller_names:
                                continue
                            if kw.arg not in conn_names[ckey]:
                                conn_names[ckey].add(kw.arg)
                                changed = True

    # Vaihe 3: kirjoittaako funktio suoraan itse, nyt kun jaettuun
    # yhteyteen viittaavat nimet ovat täysin selvillä.
    writes: dict[int, bool] = {}
    calls_names: dict[int, set[str]] = {}
    for fn_list in by_name.values():
        for fn in fn_list:
            key = id(fn)
            names = conn_names[key]
            segment = sources[key] and (ast.get_source_segment(sources[key], fn) or "")
            writes[key] = bool(names) and any(
                f"{n}.execute" in segment for n in names
            ) and bool(_WRITE_SQL.search(segment))
            calls_names[key] = _call_names(fn, aliases_by_fn[key])

    # Vaihe 4: levitä "kirjoittaa"-tila kutsugraafin läpi (bare name, _INFRA huomioiden).
    changed = True
    while changed:
        changed = False
        for fn_list in by_name.values():
            for fn in fn_list:
                key = id(fn)
                if writes[key]:
                    continue
                for name in calls_names[key]:
                    if name in _INFRA:
                        continue
                    if any(writes[id(f)] for f in by_name.get(name, ())):
                        writes[key] = True
                        changed = True
                        break

    return {name for key, name in tool_names.items() if writes[key]}


def test_kirjoittavat_toolit_ovat_write_tool_namesissa() -> None:
    """Jokainen kantaan (staattisesti havaittavasti) kirjoittava tooli on gatattu.

    Jos tämä testi kaatuu, uusi tooli kirjoittaa jaettuun ``conn``-kantaan
    muttei ole ``WRITE_TOOL_NAMES``issa server.py:ssä. Lisää se sinne — tai
    jos kirjoitus on jo turvallisesti suojattu muulla tavalla, dokumentoi
    miksi ja lisää se ``_SAFE_ALREADY_GUARDED``-joukkoon tässä tiedostossa
    (ks. yläkommentin query_data/quality_report-esimerkit).
    """
    kirjoittavat = _compute_writing_tools() - _SAFE_ALREADY_GUARDED
    puuttuvat = kirjoittavat - WRITE_TOOL_NAMES
    assert not puuttuvat, (
        f"Nämä toolit kirjoittavat kantaan muttei ole WRITE_TOOL_NAMESissa: "
        f"{sorted(puuttuvat)}. Lisää ne server.py:n WRITE_TOOL_NAMESiin."
    )


def test_havaitsija_loytaa_tunnetut_kirjoittavat_toolit() -> None:
    """Tunnistus toimii oikeasti — ei vain palauta tyhjää joukkoa.

    Ilman tätä testiä ``test_kirjoittavat_toolit_ovat_write_tool_namesissa``
    voisi olla vihreä koska tunnistus on rikki, ei koska mikään ei ole vialla.
    """
    kirjoittavat = _compute_writing_tools()
    # Suora SQL-kirjoitus kutsuketjun päässä (probe_schemas -> run_probe).
    assert "probe_schemas" in kirjoittavat
    # Ehdollinen kirjoitus (save=True) — ketju add_enrichment-kutsun kautta.
    assert "suggest_yso_tags" in kirjoittavat
    assert "quality_report" in kirjoittavat
    assert "health_check" in kirjoittavat
    # search() kirjoittaa vain erilliseen telemetriakantaan
    # (record_zero_result ei ota conn-parametria eikä hae sitä
    # _get_conn/get_connection-kutsulla), ei jaettuun aura.db:hen.
    assert "search" not in kirjoittavat
    # stats() on puhdas luku — jos tämä on kirjoittavien joukossa,
    # _INFRA-poikkeus on rikki ja _get_conn saastuttaa koko graafin.
    assert "stats" not in kirjoittavat


def test_paikallismuuttujaan_sidottu_yhteys_havaitaan() -> None:
    """Tunnistin ei saa naulautua ``conn``-parametrin kirjaimelliseen nimeen.

    @mcp.tool-funktiot ottavat aina ``ctx``:n, eivät ``conn``:ia
    parametrina — ne hakevat yhteyden PAIKALLISMUUTTUJAAN
    (``conn = _server._get_conn(ctx)``). Kolme tapaa joilla uusi
    kirjoittava tooli voitaisiin toteuttaa, kaikki löydettävä:
    suora kirjoitus toolin rungossa, apufunktio jonka parametri on
    ``conn``, ja apufunktio jonka parametri on jokin muu nimi (esim.
    ``db``) — vain argumentin ALKUPERÄ ratkaisee, ei parametrin oma nimi.
    """
    fake_source = (
        "from aura.server import mcp\n"
        "import aura.server as _server\n"
        "\n"
        "@mcp.tool()\n"
        "def _t1(dataset_id, ctx=None):\n"
        "    conn = _server._get_conn(ctx)\n"
        "    conn.execute(\"INSERT INTO t VALUES (?)\", (dataset_id,))\n"
        "\n"
        "def _helper_conn(conn, dataset_id):\n"
        "    conn.execute(\"INSERT INTO t VALUES (?)\", (dataset_id,))\n"
        "\n"
        "@mcp.tool()\n"
        "def _t2(dataset_id, ctx=None):\n"
        "    conn = _server._get_conn(ctx)\n"
        "    _helper_conn(conn, dataset_id)\n"
        "\n"
        "def _helper_db(db, dataset_id):\n"
        "    db.execute(\"INSERT INTO t VALUES (?)\", (dataset_id,))\n"
        "\n"
        "@mcp.tool()\n"
        "def _t3(dataset_id, ctx=None):\n"
        "    conn = _server._get_conn(ctx)\n"
        "    _helper_db(conn, dataset_id)\n"
    )

    # Yksinkertaisin luotettava tapa ajaa täsmälleen sama koneisto tälle
    # synteettiselle moduulille kuin oikealle koodikannalle: kirjoita se
    # väliaikaiseksi tiedostoksi _SRC:n alle (jonka _compute_writing_tools
    # löytää rglob:illa) ja siivoa lopuksi.
    tmp = _SRC / "_tmp_structural_selftest.py"
    tmp.write_text(fake_source, encoding="utf-8")
    try:
        tulos = _compute_writing_tools()
    finally:
        tmp.unlink()

    assert "_t1" in tulos, "suora kirjoitus toolin rungossa ei löytynyt"
    assert "_t2" in tulos, "apufunktio jolla on conn-parametri ei löytynyt"
    assert "_t3" in tulos, "apufunktio jonka parametri on db ei löytynyt"
