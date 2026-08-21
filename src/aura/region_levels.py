"""Aluetason päättely datasetille.

**Ongelma.** Aluehaku suodatti vain ``geographical_coverage``-kentällä.
Se kenttä kertoo mitä *aluetta aineisto koskee* — "Suomi", "Kuopio" —
eikä sano mitään siitä, onko koko maan kattavassa aineistossa kunta
omana rivinään. Seuraus mitattiin 16.8.2026:
``search_by_region("Kuopio", "väestö")`` palautti tyhjän, vaikka
Kuopion väkiluku on sekä StatFinissä että Sotkanetissa, ja
``area_profile("Kuopio")`` väitti "Ei avointa väestö-dataa".

**Ratkaisu.** Merkitään erikseen ne aineistot joissa kunta on
*dimensioarvo*. Silloin aluehaku voi palauttaa ne omana ryhmänään,
selvästi erotettuna kuntakohtaisista aineistoista.

**Miksi merkintä on "voi sisältää" eikä "sisältää".** Kummastakaan
lähteestä ei saa varmuutta yhdestä kunnasta ilman erillistä kutsua:

- Sotkanetin ``/indicators`` ilmoittaa aluetasot per indikaattori, mutta
  ilmoitus on optimistinen. Kahdentoista indikaattorin otoksessa neljä
  ilmoitti "Kunta" vaikka datassa oli 0, 8, 87 tai 95 kuntaa 308:sta.
  Ilmoitus tarkoittaa "voidaan julkaista kuntatasolla", ei "kattaa
  kaikki kunnat".
- PxWeb-taulujen ``data_fields``-rikastus tallentaa dimension nimen ja
  arvomäärän mutta vain viisi esimerkkiarvoa, joten yksittäisen kunnan
  läsnäoloa ei voi todeta siitä.

Siksi hakutulos on merkittävä sanoilla jotka eivät lupaa liikaa. Väärä
lupaus olisi pahempi kuin nykyinen tyhjä tulos: tyhjästä tuloksesta
näkee heti ettei mitään löytynyt, mutta luvatun kunnan puuttuminen
selviää vasta datan haettua.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from typing import Any

logger = logging.getLogger(__name__)

#: Rikastuskenttä johon aluetaso kirjataan.
FIELD = "region_level"

#: Arvo joka kertoo kunnan olevan dimensioarvo.
KUNTA = "kunta"

#: Dimensionimet joiden takaa kuntajako löytyy PxWeb-tauluissa.
#: Pieninä kirjaimina; vertailu tehdään lower():llä.
PXWEB_REGION_NAMES = ("alue", "kunta", "region", "municipality", "kommun")

#: Kuinka monta arvoa aluedimensiossa on oltava, jotta se on kuntajako
#: eikä maakunta- tai hyvinvointialuejako. Kuntia on 308, maakuntia 19 ja
#: hyvinvointialueita 23, joten raja on väljästi niiden välissä: se
#: hyväksyy kuntajaon josta puuttuu kymmeniä rivejä mutta hylkää
#: seutukuntajaon (69).
MIN_REGION_VALUES = 150


def pxweb_has_municipality_dimension(data_fields: str) -> bool:
    """Onko PxWeb-taulun dimensioissa kuntajako?

    Args:
        data_fields: ``data_fields``-rikastuksen JSON-arvo.
    """
    try:
        dims = json.loads(data_fields)
    except (TypeError, ValueError):
        return False
    if not isinstance(dims, list):
        return False
    for dim in dims:
        if not isinstance(dim, dict):
            continue
        name = str(dim.get("name") or "").lower()
        if not any(n in name for n in PXWEB_REGION_NAMES):
            continue
        try:
            if int(dim.get("value_count") or 0) >= MIN_REGION_VALUES:
                return True
        except (TypeError, ValueError):
            continue
    return False


def sotkanet_municipality_ids(indicators: list[dict[str, Any]]) -> set[int]:
    """Indikaattorit jotka ilmoittavat kuntatason.

    Args:
        indicators: ``/rest/1.1/indicators``-vastaus sellaisenaan.
    """
    ids: set[int] = set()
    for item in indicators:
        classifications = item.get("classifications") or {}
        region = classifications.get("region") or {}
        values = region.get("values") or []
        if "Kunta" in values and item.get("id") is not None:
            ids.add(int(item["id"]))
    return ids


#: Rikastuksen lähdetyyppi. Erottaa koneellisen päättelyn käsin
#: tehdyistä rikastuksista ja tekee uudelleenajosta turvallisen.
SOURCE_TYPE = "inferred"


def mark(conn: sqlite3.Connection, dataset_ids: list[str]) -> int:
    """Merkitse datasetit kuntatasoisiksi.

    Poistaa ensin aiemmat päätellyt merkinnät: taulussa ei ole
    uniikkirajoitetta, joten uudelleenajo kertyisi muuten
    kaksoiskappaleiksi. Käsin tehtyihin merkintöihin ei kosketa.
    """
    conn.execute(
        "DELETE FROM enrichments WHERE field = ? AND source_type = ?",
        (FIELD, SOURCE_TYPE),
    )
    if not dataset_ids:
        conn.commit()
        return 0
    conn.executemany(
        """
        INSERT INTO enrichments (
            id, dataset_id, field, value, confidence, source_type, source_detail
        ) VALUES (?, ?, ?, ?, 'medium', ?, ?)
        """,
        [
            (
                str(uuid.uuid4()),
                ds_id,
                FIELD,
                KUNTA,
                SOURCE_TYPE,
                "kunta on dimensioarvo; kattavuus vaihtelee indikaattoreittain",
            )
            for ds_id in dataset_ids
        ],
    )
    conn.commit()
    return len(dataset_ids)


def find_pxweb(conn: sqlite3.Connection) -> list[str]:
    """PxWeb-taulut joissa on kuntajako dimensiona.

    Nojaa ``data_fields``-rikastukseen, joka syntyy ``enrich-pxweb``
    -ajossa. Rikastamaton taulu ei löydy — se on rajoitus, ei virhe.
    """
    rows = conn.execute(
        "SELECT dataset_id, value FROM enrichments WHERE field = 'data_fields'"
    ).fetchall()
    hits = [r["dataset_id"] for r in rows if pxweb_has_municipality_dimension(r["value"])]
    logger.info("Kuntatasoisia PxWeb-tauluja: %d / %d rikastettua", len(hits), len(rows))
    return hits


def find_sotkanet(conn: sqlite3.Connection, indicators: list[dict[str, Any]]) -> list[str]:
    """Sotkanet-datasetit joiden indikaattori ilmoittaa kuntatason."""
    ids = sotkanet_municipality_ids(indicators)
    rows = conn.execute("SELECT id FROM datasets WHERE source = 'sotkanet'").fetchall()
    hits = []
    for r in rows:
        _, _, suffix = str(r["id"]).partition("-")
        if suffix.isdigit() and int(suffix) in ids:
            hits.append(r["id"])
    logger.info("Kuntatasoisia Sotkanet-indikaattoreita: %d / %d", len(hits), len(rows))
    return hits


def refresh(conn: sqlite3.Connection, indicators: list[dict[str, Any]] | None = None) -> int:
    """Päättele ja kirjoita aluetasot kaikista tunnetuista lähteistä.

    Kirjoitus on yksi kutsu, koska :func:`mark` korvaa koko päätellyn
    joukon kerralla. Kahtena kutsuna jälkimmäinen pyyhkisi edellisen.
    """
    hits = find_pxweb(conn)
    if indicators:
        hits.extend(find_sotkanet(conn, indicators))
    return mark(conn, sorted(set(hits)))
