"""MCP-resurssit ja -promptit.

Resurssit ovat alueita osoitteina: ``aura://kunta/837``,
``aura://maakunta/06``, ``aura://alue/seutukunta/064``. Asiakas voi liittää
alueen kontekstiin ilman työkalukutsua.

Promptit kantavat työnkulkujen esimerkit, jotka ennen olivat
instructions-tekstissä. Siellä ne maksoivat kontekstia joka vuorolla;
promptina vain kun niitä käytetään.
"""

from __future__ import annotations

import json
from typing import Any

import aura.server as _server
from aura.areas import Area, get_area, members, parents
from aura.server import PUBLIC_TAG, mcp


def _area_json(level: str, code: str) -> str:
    conn = _server._get_conn(None)
    area = get_area(conn, level, code)
    if area is None:
        return json.dumps(
            {"error": {"code": "unknown_area", "message": f"Ei aluetta {level} {code}"}},
            ensure_ascii=False,
        )
    out: dict[str, Any] = area.to_dict()
    if level == "kunta":
        out["parents"] = {k: v.to_dict() for k, v in parents(conn, code).items()}
    else:
        out["municipalities"] = [_short(m) for m in members(conn, area)]
    return json.dumps(out, ensure_ascii=False)


def _short(a: Area) -> dict[str, str]:
    return {"code": a.code, "name_fi": a.name_fi}


@mcp.resource(
    "aura://kunta/{koodi}",
    tags={PUBLIC_TAG},
    mime_type="application/json",
    description="Kunta kuntakoodilla: nimet, StatFin-koodi ja ylemmät aluetasot.",
)
def kunta_resource(koodi: str) -> str:
    return _area_json("kunta", koodi.zfill(3))


@mcp.resource(
    "aura://maakunta/{koodi}",
    tags={PUBLIC_TAG},
    mime_type="application/json",
    description="Maakunta koodilla (01–21) ja sen kunnat.",
)
def maakunta_resource(koodi: str) -> str:
    return _area_json("maakunta", koodi.zfill(2))


@mcp.resource(
    "aura://alue/{taso}/{koodi}",
    tags={PUBLIC_TAG},
    mime_type="application/json",
    description="Mikä tahansa aluetaso: hyvinvointialue, seutukunta, elinvoimakeskus, "
    "suuralue, nuts1–3, vaalipiiri.",
)
def alue_resource(taso: str, koodi: str) -> str:
    return _area_json(taso, koodi)


@mcp.prompt(name="kuntavertailu", tags={PUBLIC_TAG})
def kuntavertailu(kunnat: str, aihe: str) -> str:
    """Vertaa samaa tunnuslukua usean kunnan välillä."""
    return (
        f"Vertaa kuntia {kunnat} aiheesta '{aihe}'.\n"
        f"1. find_data(query='{aihe}') — valitse aineisto jossa kunta on dimensiona "
        "(coverage='nationwide' tai PxWeb-taulu).\n"
        "2. query_source(dataset_id, filters={'<aluedimensio>': [kunnat...], "
        "'<aikadimensio>': ['uusin']}) — yksi kutsu kaikille kunnille.\n"
        "3. Esitä taulukkona: kunta, arvo, yksikkö, ajankohta. Kerro lähde "
        "(provenance.source_url) ja lisenssi."
    )


@mcp.prompt(name="loyda-ja-hae", tags={PUBLIC_TAG})
def loyda_ja_hae(kysymys: str) -> str:
    """Löydä oikea aineisto ja hae siitä vastaus."""
    return (
        f"Kysymys: {kysymys}\n"
        "1. find_data(query=<avainsanat>, region=<alue jos mainittu>). Jos vastaus "
        "sisältää indicators-kentän, käytä sitä — arvo saadaan suoraan.\n"
        "2. Muuten query_source(dataset_id) ilman suodattimia: vastaus kertoo "
        "dimensiot ja koodit.\n"
        "3. query_source(dataset_id, filters=...). Aluedimensioon kelpaa nimi tai "
        "kuntakoodi, aikaan 'uusin' tai '2020-2024'.\n"
        "4. Vastaa arvolla, yksiköllä ja ajankohdalla; kerro lähde ja lisenssi."
    )


@mcp.prompt(name="aluekatsaus", tags={PUBLIC_TAG})
def aluekatsaus(alue: str) -> str:
    """Kokoa katsaus alueesta: hierarkia, tunnusluvut ja datatarjonta."""
    return (
        f"Kokoa katsaus alueesta {alue}.\n"
        f"1. area_snapshot('{alue}') — tunnistus, ylemmät tasot, tunnukset ja "
        "aineistot aiheittain (key_figures jos instanssi tarjoaa).\n"
        f"2. Täydennä tunnusluvut: find_data(query='väkiluku', region='{alue}') → "
        "query_source.\n"
        "3. Kerro mitä dataa alueelta puuttuu (gaps) ja mistä koko maan aineistosta "
        "sen voi korvata."
    )
