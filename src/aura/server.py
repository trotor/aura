"""Aura MCP-server FastMCP:llä."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from aura.config import is_readonly
from aura.database import (
    get_connection,
    init_db,
)
from aura.yso import YsoClient, build_fts5_query

logger = logging.getLogger(__name__)


def warm_caches(conn: sqlite3.Connection) -> None:
    """Lataa laiskat rakenteet muistiin heti käynnistyksessä.

    ``simplemma`` lataa mallinsa laiskasti ensimmäisellä kutsulla, ja lataus
    maksaa satoja megatavuja: mitattuna prosessin RSS nousi 23 MB → 745 MB
    ensimmäisellä ``lemmatize_text``-kutsulla, toinen kutsu ei lisännyt mitään.

    Ilman esilatausta muistiprofiili valehtelee. Tuore kontti näyttää noin
    75 megatavulta, ja todellinen työjoukko paljastuu vasta kun ensimmäinen
    käyttäjän haku osuu — eli juuri silloin kun sitä ei odota. Jaetulla
    palvelimella se on huono tapa yllättää naapuri.

    Sama koskee yhdyssanasanastoa (``aura.decompound``): se rakennetaan
    kannasta ensimmäisellä haulla ja vie noin 13 MB. Pienempi kuin
    kielimalli, mutta sama periaate — mitattavan profiilin on vastattava
    todellista.

    Sivuhyöty: ensimmäinen haku ei ole enää muita hitaampi.
    """
    from aura.decompound import load_lexicon
    from aura.lemmatize import lemmatize_text

    lemmatize_text("lämmitys")
    load_lexicon(conn)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Hallitse tietokantayhteyttä serverin elinkaaren ajan."""
    readonly = is_readonly()
    conn = get_connection(check_same_thread=False, readonly=readonly)
    if not readonly:
        # init_db kirjoittaa (migraatiot/skeema) → ohitetaan read-only-moodissa.
        init_db(conn)
    warm_caches(conn)
    yso = YsoClient()
    try:
        yield {"db": conn, "findings": [], "yso": yso}
    finally:
        await yso.close()
        conn.close()


# Toolit jotka kirjoittavat tietokantaan → poistetaan read-only-remotessa.
# (log_finding/list_findings ovat session-muistia, eivät kirjoita kantaan.)
#
# TÄTÄ JOUKKOA EI VOI PÄÄTELLÄ TÄYSIN AUTOMAATTISESTI: joku toolit
# kirjoittavat vain dynaamisen kutsun kautta (esim. populate_reference
# valitsee populaattorin rekisteristä, aura.probe.run_probe valitsee
# proberin ``active.get(probe_type)``illä) — kutsun kohde ei näy nimenä
# lähdekoodissa, joten staattinen analyysi ei löydä sitä. UUSI KIRJOITTAVA
# TOOLI ON SIIS AINA LISÄTTÄVÄ TÄHÄN JOUKKOON KÄSIN.
#
# tests/test_write_tool_names_structural.py havaitsee suorat ja tavallisten
# kutsujen kautta löytyvät kirjoitukset staattisesti ja kaatuu jos jokin
# niistä puuttuu täältä — se olisi estänyt probe_schemas-puutteen (#C1-
# loppukatselmus). Samalla ajolla löytyi kolme muuta samaa luokkaa olevaa
# puutetta joita ei ollut aiemmin huomattu: suggest_yso_tags, quality_report
# ja health_check nostivat suojaamattoman sqlite3.OperationalErrorin
# read-only-etäpalvelimella samaan tapaan kuin probe_schemas.
#
# quality_report JA query_data EIVÄT OLE TÄSSÄ, vaikka rakenteellinen testi
# löysi kummankin: molempien kirjoitus on nyt suojattu omalla
# ``except Exception``illä eikä vaikuta palautettuun tulokseen, joten
# lukupolku toimii myös read-only-kannassa.
# - query_data() (tools/data.py): tallentaa opitun skeeman sivuvaikutuksena
#   (save_schema_from_markdown) — kirjoitus epäonnistuu hiljaa.
# - quality_report() (tools/quality.py): laskee laatupisteet lennossa jos
#   niitä ei ole VIELÄ kannassa, ja yrittää tallentaa ne — mutta
#   toimitettavassa kannassa jokainen datasetti on jo pisteytetty
#   (DISTINCT dataset_id FROM quality_scores == datasets-taulun rivimäärä,
#   12918 == 12918), joten kirjoitushaara on julkisella instanssilla
#   käytännössä kuollut. Gating olisi poistanut täysin toimivan
#   lukutyökalun turhaan. Vastaus muodostetaan lennossa lasketuista
#   pisteistä, ei kannasta uudelleenluettuna, joten luku toimii vaikka
#   tallennus epäonnistuisi.
# Kummankin poikkeuksen syy on dokumentoitu myös itse funktion vieressä.
WRITE_TOOL_NAMES = frozenset(
    {
        "harvest",
        "probe_sizes",
        "probe_schemas",
        "enrich",
        "batch_enrich",
        "save_session_findings",
        "populate_reference",
        "suggest_yso_tags",
        "health_check",
    }
)


def health_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    """Rakenna /health-vastauksen runko: tila + datasettien määrä (DB-tarkistus)."""
    count = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
    return {"status": "ok", "datasets": int(count)}


def apply_readonly_gating(
    server: FastMCP | None = None, *, readonly: bool | None = None
) -> list[str]:
    """Poista kirjoittavat toolit kun server on read-only-moodissa.

    Palauttaa poistettujen toolien nimet. Ei tee mitään jos ei read-only.
    """
    if server is None:
        server = mcp
    if readonly is None:
        readonly = is_readonly()
    if not readonly:
        return []
    removed: list[str] = []
    for name in WRITE_TOOL_NAMES:
        try:
            server.local_provider.remove_tool(name)
        except KeyError:
            # Jo poistettu. Gateys on idempotentti, koska ``mcp`` on
            # moduulitason singleton: sovellus voidaan rakentaa useammin
            # kuin kerran samassa prosessissa (testit, uudelleenlataus).
            continue
        removed.append(name)
    return removed


_INTRO = (
    "Suomalaisen avoimen datan discovery-palvelu. "
    "Hae ja ymmärrä Suomen avoimia datasettejä. "
)

# Löydösten kirjaus. log_finding/list_findings ovat session-muistia ja
# toimivat molemmissa moodeissa; save_session_findings kirjoittaa kantaan
# ja gataan pois read-only-moodissa (WRITE_TOOL_NAMES), joten remote-ohje
# ei saa kehottaa kutsumaan sitä.
_FINDINGS_LOCAL = (
    "Kun tutkit datasettejä ja löydät uutta tietoa niistä "
    "(kenttiä, käyttöohjeita, laatuhuomioita), "
    "kirjaa löydökset log_finding()-työkalulla tutkimuksen aikana. "
    "Lopuksi tallenna ne enrichmenteiksi save_session_findings()-kutsulla.\n\n"
)
_FINDINGS_REMOTE = (
    "Kun tutkit datasettejä ja löydät uutta tietoa niistä "
    "(kenttiä, käyttöohjeita, laatuhuomioita), "
    "kirjaa löydökset log_finding()-työkalulla ja näytä ne "
    "list_findings()-kutsulla. Tämä instanssi on read-only, joten "
    "löydöksiä ei tallenneta pysyvästi — ne elävät vain session ajan.\n\n"
)

# Toimii molemmissa moodeissa: query_data hakee ulkoisista rajapinnoista
# eikä nojaa paikalliseen tiedostojärjestelmään.
_API_USAGE = (
    "RAJAPINTOJEN SUORA KÄYTTÖ:\n"
    "Voit hakea dataa suoraan rajapinnoista käyttäjän puolesta! "
    "Etsi ensin Aurasta oikea datasetti (search/describe), "
    "sitten kysy dataa query_data()-työkalulla tai hae suoraan "
    "resurssin URL:sta. Tuettuja: REST/JSON, PxWeb, WFS, OData, CSV. "
    "Esim. junien aikataulut: rata.digitraffic.fi/api/v1/trains/{pvm}/{numero}, "
    "tilastot: query_data() PxWeb-suodattimilla, "
    "sää: query_data() WFS-rajapinnasta. "
    "Digitransit GraphQL vaatii API-avaimen (api.digitransit.fi).\n\n"
)

# Lokaali: agentilla on levyllä MML:n GeoPackaget, joita se voi kysellä suoraan.
_BOUNDARIES_LOCAL = (
    "RAJAUSAINEISTOT (data/boundaries/, EPSG:3067):\n"
    "1) karttalehtijako.gpkg — MML:n TM35-ruutujako. "
    "Tasot: utm200..utm5, utm1. Kenttä: lehtitunnus (esim. 'L4133A'). "
    "Hierarkia: L4→L41→L413→L4133→L4133A→L4133A3. "
    "Käytä bbox-rajauksia WFS/WCS-kyselyihin. "
    "Mittakaava: utm50 maakunnille, utm25 kaupungeille, utm10 yksityiskohdille.\n"
    "2) kuntajako_1000k.gpkg / kuntajako_10k.gpkg — MML:n hallinnolliset rajat. "
    "Tasot: Kunta (308), Maakunta (19), Hyvinvointialue (23), Valtakunta (1). "
    "Kentät: natcode (koodi), namefin (nimi fi), nameswe (nimi sv), landarea, totalarea. "
    "Käytä kunnan/maakunnan bbox:ia aluerajauksiin: "
    "SELECT MbrMinX(multipolygon),MbrMinY(multipolygon),"
    "MbrMaxX(multipolygon),MbrMaxY(multipolygon) "
    "FROM Kunta WHERE namefin='Helsinki'."
)

# Remote: levyllä ei ole mitään. Sama kyvykkyys tulee työkaluista, jotka
# lukevat kannasta (ref_municipalities, map_sheets) eivätkä GPKG-tiedostoista.
_BOUNDARIES_REMOTE = (
    "ALUERAJAUKSET (EPSG:3067):\n"
    "Tämä on etäpalvelu: sinulla ei ole pääsyä palvelimen tiedostojärjestelmään. "
    "Käytä aluerajauksiin näitä työkaluja — ne palauttavat saman tiedon:\n"
    "1) municipality_bbox(query) — kunnan rajauslaatikko valmiina WFS/WCS-kyselyyn. "
    "Hyväksyy nimen (fi/sv) tai kuntakoodin, esim. 'Helsinki' tai '091'.\n"
    "2) find_map_sheets(scale=..., municipality=... | bbox=... | point=... | "
    "prefix=...) — MML:n TM35-karttalehdet jotka osuvat alueelle. "
    "Mittakaava: utm50 maakunnille, utm25 kaupungeille, utm10 yksityiskohdille.\n"
    "3) map_sheet(sheet_id) — yksittäisen karttalehden tiedot ja bbox, "
    "esim. 'L4133A'. Kertoo myös vanhemman ja lapset. "
    "Hierarkia: L4→L41→L413→L4133→L4133A→L4133A3.\n"
    "4) query_data(dataset_id, area=...) — rajaa WFS-kyselyn suoraan alueeseen. "
    "area ottaa kunnan nimen tai koodin, lehtitunnuksen tai bbox:n, joten "
    "yllä olevien työkalujen tuloste kelpaa siihen sellaisenaan.\n"
    "Lyhin reitti: query_data(dataset_id, area='Tampere'). Tarkempaan "
    "rajaukseen: find_map_sheets(scale='utm25', municipality='Tampere') → "
    "query_data(dataset_id, area='<lehtitunnus>')."
)


def build_instructions(readonly: bool = False) -> str:
    """Rakenna server-instructions moodin mukaan (#137).

    Read-only-moodi tarkoittaa käytännössä etäpalvelinta, jossa agentilla ei
    ole pääsyä ``data/boundaries/*.gpkg``-tiedostoihin eikä kirjoittaviin
    työkaluihin. Ohjeen on vastattava sitä todellisuutta: väärä lupaus
    tuottaa virheellistä tietoa jokaiselle liittyvälle asiakkaalle.

    Args:
        readonly: True = etäpalvelin (ei local-FS:ää, ei kirjoittavia tooleja).
    """
    if readonly:
        return _INTRO + _FINDINGS_REMOTE + _API_USAGE + _BOUNDARIES_REMOTE
    return _INTRO + _FINDINGS_LOCAL + _API_USAGE + _BOUNDARIES_LOCAL


mcp = FastMCP(
    "Aura",
    instructions=build_instructions(is_readonly()),
    lifespan=_lifespan,
)


@mcp.custom_route("/health", methods=["GET"])
async def _health_route(request: Request) -> JSONResponse:
    """Kevyt terveystarkistus App Runnerille: 200 + datasettien määrä."""
    conn = get_connection(readonly=is_readonly())
    try:
        return JSONResponse(health_payload(conn))
    finally:
        conn.close()


_module_conn: sqlite3.Connection | None = None


def _get_conn(ctx: Context | None = None) -> sqlite3.Connection:
    """Hae tietokantayhteys lifespan-kontekstista tai luo uusi.

    Lifespan-yhteys on suositeltava (thread-safe, jaettu).
    Fallback käyttää singleton-yhteyttä (CLI-käyttö, testit).
    """
    global _module_conn
    if ctx is not None:
        try:
            conn: sqlite3.Connection = ctx.lifespan_context["db"]
            return conn
        except (AttributeError, KeyError):
            pass
    # Singleton-fallback: yksi jaettu yhteys (CLI, testit)
    if _module_conn is None:
        _module_conn = get_connection(check_same_thread=False)
        init_db(_module_conn)
    return _module_conn


def _get_yso(ctx: Context | None) -> YsoClient | None:
    """Hae YsoClient lifespan-kontekstista."""
    if ctx:
        try:
            return ctx.lifespan_context.get("yso")
        except (AttributeError, KeyError):
            pass
    return None


async def _expand_with_yso(query: str, ctx: Context | None) -> str:
    """Laajenna hakutermi YSO-ontologialla.

    Palauttaa FTS5-hakulausekkeen tai tyhjän merkkijonon jos
    laajennusta ei tehdä.
    """
    yso = _get_yso(ctx)
    if not yso:
        return ""
    try:
        terms = await yso.expand_query(query)
        if len(terms) > 1:
            return build_fts5_query(terms)
    except Exception:
        logger.warning("[yso] Hakulaajennus epäonnistui: '%s'", query, exc_info=True)
    return ""


async def _expand_query(query: str, ctx: Context | None) -> str:
    """Laajenna hakutermi sanastoilla ja YSO-ontologialla.

    Yhdistää paikallisen sanastolaajennuksen (instant, ei API-kutsuja)
    ja YSO-laajennuksen. Palauttaa FTS5-hakulausekkeen.

    Monisanaiset haut pilkotaan tokeneiksi ja jokainen laajennetaan
    erikseen. Termit yhdistetään OR-operaattorilla, joten riittää
    että yksi sana osuu.
    """
    from aura.vocabularies import expand_with_vocabularies

    tokens = query.split()
    all_terms: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            all_terms.append(term)

    # Lisää kaikki yksittäiset sanat
    for token in tokens:
        _add(token)

    # 1. Sanastolaajennus (instant) — token-kohtaisesti
    for token in tokens:
        for term in expand_with_vocabularies(token):
            _add(term)

    # Kokeile myös koko hakua sanastoavaimeena (esim. "kevyt liikenne")
    if len(tokens) > 1:
        for term in expand_with_vocabularies(query):
            _add(term)

    # 2. YSO-laajennus (API-kutsu) — token-kohtaisesti (max 3)
    yso = _get_yso(ctx)
    if yso:
        for token in tokens[:3]:
            try:
                yso_terms = await yso.expand_query(token)
                for term in yso_terms:
                    _add(term)
            except Exception:
                logger.warning("[yso] Hakulaajennus epäonnistui: '%s'", token, exc_info=True)

    if len(all_terms) > 1:
        return build_fts5_query(all_terms)
    return ""


# Rekisteröi kaikki @mcp.tool()-funktiot alimoduuleista
import aura.tools  # noqa: E402, F401
from aura.preview import preview_data  # noqa: E402, F401

# Re-export kaikki toolit ja apufunktiot taaksepäinyhteensopivuutta varten
# (testit importoivat suoraan: from aura.server import search, describe, ...)
from aura.tools.admin import (  # noqa: E402, F401
    harvest,
    list_formats,
    list_organizations,
    list_sources,
    probe_sizes,
    stats,
)
from aura.tools.area import area_profile, compare_municipalities  # noqa: E402, F401
from aura.tools.data import query_data  # noqa: E402, F401
from aura.tools.describe import compare, describe  # noqa: E402, F401
from aura.tools.enrichment import (  # noqa: E402, F401
    batch_enrich,
    enrich,
    get_enrichments_tool,
    suggest_yso_tags,
)
from aura.tools.health import health_check, health_report  # noqa: E402, F401
from aura.tools.quality import (  # noqa: E402, F401
    quality_gaps,
    quality_overview,
    quality_ranking,
    quality_report,
)
from aura.tools.query import query_pxweb  # noqa: E402, F401
from aura.tools.reference import (  # noqa: E402, F401
    lookup_municipality,
    populate_reference,
    reference_status,
)
from aura.tools.research import (  # noqa: E402, F401
    _fallback_findings,
    list_findings,
    log_finding,
    reset_findings,
    save_session_findings,
)
from aura.tools.search import (  # noqa: E402, F401
    _resolve_region,
    find_related,
    recommend,
    search,
    search_by_region,
    search_structured,
)
from aura.tools.spatial import (  # noqa: E402, F401
    find_map_sheets,
    map_sheet,
    municipality_bbox,
)
from aura.tools.suggest import suggest_questions  # noqa: E402, F401
