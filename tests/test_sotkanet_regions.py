"""Sotkanetin koko aluerekisteri: tallennus ja rivien tulkinta kaikilla tasoilla.

Ulkoinen arvio 27.9.2026: Sotkanetin rivin ``region`` tulkittiin vain
kunnille. Maakunnan, hyvinvointialueen tai koko maan rivi jäi ilman nimeä,
ja alue 658 (koko maa) näytti tuntemattomalta tunnukselta.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura import fetch
from aura.database import EXPECTED_SCHEMA_VERSION, init_db, schema_version
from aura.populators.municipalities import MunicipalityPopulator

REGIONS: list[dict[str, Any]] = [
    {"id": 186, "code": "837", "category": "KUNTA", "title": {"fi": "Tampere", "sv": "Tammerfors"}},
    {"id": 493, "code": "06", "category": "MAAKUNTA", "title": {"fi": "Pirkanmaa"}},
    {
        "id": 969,
        "code": "08",
        "category": "HYVINVOINTIALUE",
        "title": {"fi": "Pirkanmaan hyvinvointialue", "en": "Pirkanmaa wellbeing services county"},
    },
    {"id": 529, "code": "064", "category": "SEUTUKUNTA", "title": {"fi": "Tampereen seutukunta"}},
    {"id": 658, "code": "358", "category": "MAA", "title": {"fi": "Koko maa"}},
    {"id": 1045, "code": "246", "category": "POHJOISMAAT", "title": {"fi": "Suomi"}},
]


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_migraatio_luo_taulun_ja_nostaa_tason() -> None:
    conn = _db()
    assert EXPECTED_SCHEMA_VERSION == 26
    assert schema_version(conn) == 26
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ref_sotkanet_regions)")]
    assert cols == ["id", "category", "code", "name_fi", "name_sv", "name_en"]


@pytest.mark.asyncio
async def test_populaattori_tallentaa_kaikki_kategoriat() -> None:
    conn = _db()
    conn.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv, region_code, wellbeing_area_code)"
        " VALUES ('837', 'Tampere', 'Tammerfors', '06', '08')"
    )
    conn.commit()
    p = MunicipalityPopulator(conn=conn)
    resp = MagicMock()
    resp.json.return_value = REGIONS
    with patch.object(p, "_fetch", AsyncMock(return_value=resp)):
        await p._populate_sotkanet_ids()
    rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM ref_sotkanet_regions")}
    assert len(rows) == len(REGIONS)
    assert rows[969]["name_en"] == "Pirkanmaa wellbeing services county"
    assert rows[658]["category"] == "MAA"
    # Kuntataulun sillat päivittyvät kuten ennenkin.
    m = conn.execute(
        "SELECT sotkanet_id, sotkanet_region_id, sotkanet_wellbeing_area_id"
        " FROM ref_municipalities WHERE code = '837'"
    ).fetchone()
    assert tuple(m) == (186, 493, 969)
    # Uusi ajo korvaa taulun eikä kasvata sitä.
    with patch.object(p, "_fetch", AsyncMock(return_value=resp)):
        await p._populate_sotkanet_ids()
    assert conn.execute("SELECT COUNT(*) FROM ref_sotkanet_regions").fetchone()[0] == len(REGIONS)


def _annotated(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], fetch.Table]:
    table = fetch.Table(protocol="json")
    records = [{"region": rid, "value": 1.0} for rid in (186, 493, 969, 529, 658, 1045, 9999)]
    return fetch._annotate_sotkanet(conn, records, table), table


def test_rivit_saavat_koodin_nimen_ja_tason_kaikilla_tasoilla() -> None:
    conn = _db()
    conn.executemany(
        "INSERT INTO ref_sotkanet_regions (id, category, code, name_fi) VALUES (?, ?, ?, ?)",
        [(r["id"], r["category"], r["code"], r["title"]["fi"]) for r in REGIONS],
    )
    rows, table = _annotated(conn)
    by = {r["region"]: (r["region_code"], r["region_name"], r["region_level"]) for r in rows}
    assert by[186] == ("837", "Tampere", "kunta")
    assert by[493] == ("06", "Pirkanmaa", "maakunta")
    assert by[969] == ("08", "Pirkanmaan hyvinvointialue", "hyvinvointialue")
    assert by[529] == ("064", "Tampereen seutukunta", "seutukunta")
    assert by[658] == ("SSS", "Koko maa", "koko_maa")
    assert by[1045] == ("246", "Suomi", "maa_pohjoismaat")
    assert by[9999] == (None, None, None)
    assert "region_level" in table.notes[0]


def test_ilman_rekisteritaulua_vain_kunnat_kuten_ennen() -> None:
    conn = _db()
    conn.execute("DROP TABLE ref_sotkanet_regions")
    conn.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv, sotkanet_id)"
        " VALUES ('837', 'Tampere', 'Tammerfors', 186)"
    )
    rows, table = _annotated(conn)
    by = {r["region"]: (r["region_code"], r["region_name"], r["region_level"]) for r in rows}
    assert by[186] == ("837", "Tampere", "kunta")
    assert by[493] == (None, None, None)
    assert "tyhjä = alue ei ole kunta" in table.notes[0]


def test_tyhja_kanta_ei_koske_riveihin() -> None:
    conn = _db()
    records = [{"region": 186, "value": 1.0}]
    table = fetch.Table(protocol="json")
    assert fetch._annotate_sotkanet(conn, records, table) == records
    assert table.notes == []
