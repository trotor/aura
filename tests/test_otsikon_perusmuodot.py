"""Otsikon perusmuodot omassa FTS-sarakkeessaan (migraatio 027).

Perusmuotosarake painoi saman verran tuli sana otsikosta tai kuvauksesta.
Taivutettu otsikko hävisi siksi aineistolle, jonka otsikossa sana on
sellaisenaan: "kunnan tilinpäätös" nosti ostolaskut taulun
"Kuntien tilinpäätökset" ohi (mitattu 9.10.2026).
"""

from __future__ import annotations

import sqlite3

import pytest

from aura.database import init_db, search_datasets, upsert_dataset
from aura.lemmatize import LEMMATIZER_AVAILABLE, index_lemmas
from aura.models import Dataset

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


def test_taivutettu_sana_haetaan_vain_perusmuotona() -> None:
    """Pinta- ja perusmuoto OR:lla laskivat saman sanan bm25:ssä kahdesti."""
    from aura.lemmatize import build_fts_query

    expr = build_fts_query(
        "kunnan tilinpäätös", lemma_column="{lemmas title_lemmas}", lemma_only=True
    )
    assert expr == '{lemmas title_lemmas} : "kunta" AND "tilinpäätös"'


def test_ilman_lemma_only_lippua_pintamuoto_sailyy() -> None:
    """Vanhat kannat (ei migraatiota 027) hakevat kuten ennenkin."""
    from aura.lemmatize import build_fts_query

    expr = build_fts_query("kunnan tilinpäätös", lemma_column="lemmas")
    assert expr == '("kunnan" OR lemmas : "kunta") AND "tilinpäätös"'


def test_tallennus_tayttaa_perusmuodot_heti() -> None:
    """Keruun jälkeen aineisto löytyy taivutetulla sanalla ilman index_lemmas-ajoa."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    upsert_dataset(
        conn,
        Dataset(id="x", name="x", title="Kuntien tilinpäätökset", source="t"),
    )
    row = conn.execute("SELECT lemmas, title_lemmas FROM datasets WHERE id = 'x'").fetchone()
    assert row["title_lemmas"] == "kunta tilinpäätös"
    assert [r["id"] for r in search_datasets(conn, "kuntien tilinpäätöksiä")] == ["x"]
