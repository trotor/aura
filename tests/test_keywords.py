"""Avainsanaindeksi: normalisointi, kohinan suodatus, liittyvät ja samankaltaiset sanat."""

from __future__ import annotations

import sqlite3

import pytest

from aura.database import init_db, upsert_dataset
from aura.keywords import KeywordIndex, is_noise, normalize
from aura.models import Dataset


def _conn(rows: list[tuple[str, list[str]]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    for ds_id, keywords in rows:
        upsert_dataset(
            conn, Dataset(id=ds_id, name=ds_id, title=ds_id, source="t", keywords_fi=keywords)
        )
    conn.commit()
    return conn


@pytest.fixture
def index() -> KeywordIndex:
    return KeywordIndex.build(
        _conn(
            [
                ("a", ["Kuntatalous", "tilinpäätös", "kunta"]),
                ("b", ["kuntatalous", "tilinpäätös", "kuntayhtymä"]),
                ("c", ["kuntatalous", "kunta", "avoindata.fi"]),
                ("d", ["kunta", "väestö"]),
                ("e", ["väestö", "väestörakenne", "1._Ulkoiset_tilinpaatoslaskelmat"]),
                ("f", ["kunnat", "liikenne"]),
            ]
        )
    )


def test_normalisointi() -> None:
    assert normalize("  Kunta  Talous ") == "kunta talous"


@pytest.mark.parametrize(
    "keyword",
    [
        "avoindata.fi",
        "ei-inspire",
        "1._Ulkoiset_tilinpaatoslaskelmat",
        "06 Metsavarat",
        "ktt011",
        "Kuntien ja kuntayhtymien raportoimat tiedot 1975-2014",
        "uusin",
        "a",
        "",
    ],
)
def test_kohina_tunnistetaan(keyword: str) -> None:
    assert is_noise(keyword)


@pytest.mark.parametrize(
    "keyword", ["kunta", "väestörakenne", "pm2.5", "julkinen talous", "gtfs-rt", "co2-päästöt"]
)
def test_oikea_avainsana_ei_ole_kohinaa(keyword: str) -> None:
    assert not is_noise(keyword)


def test_kirjainkoko_yhdistetaan_ja_yleisin_muoto_naytetaan(index: KeywordIndex) -> None:
    entry = index.get("KUNTATALOUS")
    assert entry is not None
    assert entry.count == 3
    assert entry.label == "kuntatalous"
    assert sorted(entry.dataset_ids) == ["a", "b", "c"]


def test_kohina_ei_listoissa(index: KeywordIndex) -> None:
    labels = {e.label for e in index.entries()}
    assert "avoindata.fi" not in labels
    assert not any("_" in label for label in labels)


def test_liittyvat_sanat_yhteisesiintymisesta(index: KeywordIndex) -> None:
    related = [e.label for e in index.related("kuntatalous")]
    assert related[0] == "tilinpäätös"
    assert "kuntatalous" not in related
    assert "avoindata.fi" not in related


def test_samankaltaiset_sanat_perusmuodosta_ja_yhdyssanasta(index: KeywordIndex) -> None:
    similar = {e.label for e in index.similar("kunta")}
    assert {"kunnat", "kuntatalous", "kuntayhtymä"} <= similar
    assert "kunta" not in similar
    assert "väestö" not in similar


def test_suosituimmat(index: KeywordIndex) -> None:
    assert [e.label for e in index.top(2)] == ["kunta", "kuntatalous"]


def test_tuntematon_sana(index: KeywordIndex) -> None:
    assert index.get("ei-ole") is None
    assert index.related("ei-ole") == []
