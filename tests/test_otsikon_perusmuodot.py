"""Otsikon perusmuodot omassa FTS-sarakkeessaan (migraatio 027).

Perusmuotosarake painoi saman verran tuli sana otsikosta tai kuvauksesta.
Taivutettu otsikko hävisi siksi aineistolle, jonka otsikossa sana on
sellaisenaan: "kunnan tilinpäätös" nosti ostolaskut taulun
"Kuntien tilinpäätökset" ohi (mitattu 9.10.2026).
"""

from __future__ import annotations

import sqlite3

from aura.database import init_db, search_datasets, upsert_dataset
from aura.lemmatize import LEMMATIZER_AVAILABLE, index_lemmas
from aura.models import Dataset

import pytest

pytestmark = pytest.mark.skipif(not LEMMATIZER_AVAILABLE, reason="simplemma puuttuu")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    upsert_dataset(
        conn,
        Dataset(
            id="ostolaskut",
            name="ostolaskut",
            title="Keminmaan kunnan ostolaskut 2025",
            title_fi="Keminmaan kunnan ostolaskut 2025",
            notes_fi="Kunta julkaisee vuosittain ostolaskutiedot tilinpäätöksen valmistuttua.",
            source="avoindata.fi",
        ),
    )
    upsert_dataset(
        conn,
        Dataset(
            id="tilinpaatokset",
            name="tilinpaatokset",
            title="Kuntien tilinpäätökset 2020",
            title_fi="Kuntien tilinpäätökset 2020",
            notes_fi="Kuntien ja kuntayhtymien talous ja toiminta.",
            source="statfin",
        ),
    )
    # Täyteaineistot: kahden dokumentin korpuksessa BM25:n IDF on lähes
    # nolla, eikä painoilla olisi vaikutusta.
    for i, aihe in enumerate(
        ["väestö", "liikenne", "metsävarat", "ilmanlaatu", "koulutus", "asuminen",
         "työttömyys", "vesistöt", "kirjastot", "vaalit", "terveys", "energia"]
    ):
        upsert_dataset(
            conn,
            Dataset(id=f"muu-{i}", name=f"muu-{i}", title=f"{aihe} {i}",
                    title_fi=f"{aihe} {i}", notes_fi=f"Aineisto aiheesta {aihe}.",
                    source="t"),
        )
    conn.commit()
    index_lemmas(conn)
    return conn


def test_otsikon_perusmuodot_indeksoidaan() -> None:
    conn = _conn()
    row = conn.execute(
        "SELECT title_lemmas FROM datasets WHERE id = 'tilinpaatokset'"
    ).fetchone()
    assert row["title_lemmas"].split()[:2] == ["kunta", "tilinpäätös"]


def test_taivutettu_otsikko_voittaa_kuvausosuman() -> None:
    conn = _conn()
    ids = [r["id"] for r in search_datasets(conn, "kunnan tilinpäätös")]
    assert ids[0] == "tilinpaatokset", ids


def test_perusmuodolla_kirjoitettu_kysely() -> None:
    conn = _conn()
    ids = [r["id"] for r in search_datasets(conn, "kunta tilinpäätös")]
    assert ids[0] == "tilinpaatokset", ids
