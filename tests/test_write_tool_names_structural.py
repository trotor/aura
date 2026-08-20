"""Rakenteellinen testi: jokainen kantaan kirjoittava @mcp.tool on WRITE_TOOL_NAMESissa.

Tausta (#C1-loppukatselmus): ``probe_schemas`` puuttui ``WRITE_TOOL_NAMES``-
joukosta, ja aiempi testi (``test_write_tool_names_are_the_expected_set``)
väitti vain että joukko on tasan tietty lista — muutosdetektori, joka naulaa
puutteen sen sijaan että havaitsisi sen. Tämä testi yrittää oikeasti
*havaita* kirjoittavan toolin ilman että sen nimi on lueteltu käsin etukäteen.
Samalla ajolla se löysi kolme muuta samaa luokkaa olevaa puutetta —
``suggest_yso_tags``, ``quality_report``, ``health_check`` — jotka on nyt
lisätty ``WRITE_TOOL_NAMES``iin server.py:ssä.

**Menetelmä.** Funktio tulkitaan kantaan kirjoittavaksi jos sen rungossa on
suora ``execute``-kutsu jonka SQL-teksti sisältää INSERT/UPDATE/DELETE-
avainsanan, JA funktiolla on parametri nimeltä ``conn`` — jälkimmäinen ehto
erottaa jaetun ``aura.db``-yhteyden kirjoitukset erillisen tiedoston
kirjoituksista (ks. ``aura.telemetry.record_zero_result``: tekee oman
``sqlite3.connect()``-kutsunsa erilliseen, tarkoituksella
kirjoitussuojauksen ulkopuolella olevaan telemetriakantaan eikä ota
``conn``-parametria — ilman tätä ehtoa testi vaatisi virheellisesti
``search``-toolin WRITE_TOOL_NAMESiin).

Kutsugraafi kootaan koko ``aura``-paketista nimen perusteella (myös
paikalliset ``import x as y``-aliakset ratkaistaan), ja kirjoittavuus
leviää siitä transitiivisesti tooliin asti kiintopisteiteraatiolla. Nimellä
sovittaminen ei ratkaise moduulirajoja tarkasti, joten tulos on yliarvio:
kahden eri moduulin samanniminen funktio voi sekoittua keskenään. Siksi
testi vaatii vain että havaitut kirjoittajat SISÄLTYVÄT
``WRITE_TOOL_NAMES``iin — ei että joukot ovat identtiset (ks. myös
``server.py``:n ``WRITE_TOOL_NAMES``-kommentti käsin ylläpidosta).

**_INFRA-poikkeus.** ``_get_conn``/``get_connection``/``init_db``/
``run_migrations`` on jätettävä pois todisteketjusta erikseen: ne ovat
jaettua plumbingia jota käytännössä JOKAINEN tooli kutsuu
(``conn = _server._get_conn(ctx)``), ja ``_get_conn``:n CLI/testi-
fallback-polku kutsuu ``init_db``:tä, joka aidosti kirjoittaa (migraatiot).
Ilman tätä rajausta kiintopiste leviäisi jokaiseen tooliin ja testi
menettäisi erottelukykynsä täysin — todennettu kokeilemalla: ilman
poikkeusta havaittu joukko oli 33/33 toolia.

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

#: Jaettu plumbing joka ei saa toimia todisteena kutsujalleen — ks. tiedoston
#: yläkommentti "_INFRA-poikkeus".
_INFRA = {"_get_conn", "_get_yso", "get_connection", "init_db", "run_migrations"}

#: Toolit joiden ainoa havaittu kirjoitus on jo suojattu niin ettei se voi
#: näkyä käyttäjälle eikä kaataa kutsua read-only-instanssilla — ks.
#: server.py:n WRITE_TOOL_NAMES-kommentti (query_data / best-effort
#: skeematallennus omassa except Exception -lohkossaan).
_SAFE_ALREADY_GUARDED = {"query_data"}

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


def _call_names(node: FuncDef, aliases: dict[str, str]) -> set[str]:
    """Kutsujen kohteiden nimet funktion rungosta, aliakset ratkaistuna."""
    names: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        if isinstance(fn, ast.Name):
            names.add(aliases.get(fn.id, fn.id))
        elif isinstance(fn, ast.Attribute):
            names.add(fn.attr)
    return names


def _has_conn_param(node: FuncDef) -> bool:
    """Onko funktiolla parametri nimeltä ``conn`` (jaettu kantayhteys)."""
    args = node.args
    all_args = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    return any(a.arg == "conn" for a in all_args)


def _writes_sql_directly(node: FuncDef, source: str) -> bool:
    """Onko funktion rungossa suora kirjoitus jaettuun ``conn``-yhteyteen."""
    if not _has_conn_param(node):
        return False
    segment = ast.get_source_segment(source, node) or ""
    if ".execute" not in segment:
        return False
    return bool(_WRITE_SQL.search(segment))


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


def _compute_writing_tools() -> set[str]:
    """Nimet kaikista @mcp.tool-funktioista jotka staattisesti kirjoittavat kantaan."""
    by_name: dict[str, list[FuncDef]] = {}
    writes: dict[int, bool] = {}
    calls: dict[int, set[str]] = {}
    tool_names: dict[int, str] = {}

    for path in sorted(_SRC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        module_aliases = _import_aliases(tree)
        for fn in _iter_functions(tree):
            key = id(fn)
            by_name.setdefault(fn.name, []).append(fn)
            local_aliases = {**module_aliases, **_import_aliases(fn)}
            writes[key] = _writes_sql_directly(fn, source)
            calls[key] = _call_names(fn, local_aliases)
            if _is_mcp_tool(fn):
                tool_names[key] = fn.name

    changed = True
    while changed:
        changed = False
        for key, called in calls.items():
            if writes[key]:
                continue
            for name in called:
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
    (ks. yläkommentin query_data-esimerkki).
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
    # (record_zero_result ei ota conn-parametria), ei jaettuun aura.db:hen.
    assert "search" not in kirjoittavat
    # stats() on puhdas luku — jos tämä on kirjoittavien joukossa,
    # _INFRA-poikkeus on rikki ja _get_conn saastuttaa koko graafin.
    assert "stats" not in kirjoittavat
