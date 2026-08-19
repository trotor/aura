"""Testit aluerajauksen läpinäkyvyydelle.

``region`` lupaa työkaluskeemassa suodattamista, mutta toteutus laajentaa:
ehdon toinen haara päästää läpi jokaisen aineiston jolla on
``region_level``-enrichment, riippumatta pyydetystä alueesta. Se on
tahallista — koko maan taulu, jossa kunta on dimensioarvo, kattaa myös
Kuopion — mutta agentille se näyttää tarkalta rajaukselta.

Ero on mitattavissa vasta tuloksista: osa osumista täsmää aineiston omaan
kattavuuteen, osa tulee laajennuksesta. Kun vastaus ei kerro kumpaa se
katsoo, agentti päättelee koko maan taulusta paikallisen aineiston
olemassaolon.

Nämä testit vaativat että vastaus erottelee ne.
"""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

import pytest

import aura.server as _server
from aura.database import init_db
from aura.server import search, search_structured


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO ref_municipalities (code, name_fi, name_sv)"
        " VALUES ('297','Kuopio','Kuopio')"
    )
    # Oma kattavuus osuu Kuopioon.
    c.execute(
        "INSERT INTO datasets (id, name, title, title_fi, notes, source,"
        " geographical_coverage) VALUES"
        " ('oma','oma','Kuopion väestö','Kuopion väestö','väestö','testi','[\"Kuopio\"]')"
    )
    # Koko maan taulu: pääsee läpi vain region_level-haaran kautta.
    c.execute(
        "INSERT INTO datasets (id, name, title, title_fi, notes, source,"
        " geographical_coverage) VALUES"
        " ('koko-maa','koko-maa','Väestö kunnittain','Väestö kunnittain','väestö',"
        " 'testi','[\"Suomi\"]')"
    )
    c.execute(
        "INSERT INTO enrichments (dataset_id, field, value, source_type)"
        " VALUES ('koko-maa','region_level','kunta','harvest')"
    )
    c.commit()
    return c


async def _search(conn: sqlite3.Connection, **kwargs) -> str:
    with (
        patch.object(_server, "_get_conn", return_value=conn),
        patch.object(_server, "_expand_query", return_value=""),
    ):
        return await search("väestö", **kwargs)


class TestVastausKertooLaajennuksesta:
    @pytest.mark.anyio
    async def test_molemmat_haarat_loytyvat(self, conn: sqlite3.Connection) -> None:
        """Lähtötilanne: laajennus tuo koko maan taulun mukaan."""
        out = await _search(conn, region="Kuopio")
        assert "oma" in out.lower() or "Kuopion väestö" in out
        assert "Väestö kunnittain" in out

    @pytest.mark.anyio
    async def test_vastaus_erottelee_laajennetut(self, conn: sqlite3.Connection) -> None:
        out = await _search(conn, region="Kuopio")
        assert "Aluerajaus" in out
        # Yksi oman kattavuuden osuma, yksi laajennuksesta.
        assert "1" in out

    @pytest.mark.anyio
    async def test_ilman_aluetta_ei_lisarivia(self, conn: sqlite3.Connection) -> None:
        """Rivi kuuluu vain sinne missä laajennus tapahtui."""
        out = await _search(conn)
        assert "Aluerajaus" not in out

    @pytest.mark.anyio
    async def test_pelkka_oma_kattavuus_kerrotaan_myos(
        self, conn: sqlite3.Connection
    ) -> None:
        """Nolla laajennettua on yhtä lailla tietoa: rajaus oli tarkka."""
        conn.execute("DELETE FROM enrichments WHERE field = 'region_level'")
        conn.commit()
        out = await _search(conn, region="Kuopio")
        assert "Aluerajaus" in out


class TestStructuredKertooSamanKoneluettavasti:
    @pytest.mark.anyio
    async def test_region_kentta_vastauksessa(self, conn: sqlite3.Connection) -> None:
        with (
            patch.object(_server, "_get_conn", return_value=conn),
            patch.object(_server, "_expand_query", return_value=""),
        ):
            raw = await search_structured("väestö", region="Kuopio")
        data = json.loads(raw)
        assert "region" in data, data.keys()
        assert data["region"]["matched_own_coverage"] == 1
        assert data["region"]["matched_nationwide"] == 1

    @pytest.mark.anyio
    async def test_ilman_aluetta_ei_region_kenttaa(
        self, conn: sqlite3.Connection
    ) -> None:
        with (
            patch.object(_server, "_get_conn", return_value=conn),
            patch.object(_server, "_expand_query", return_value=""),
        ):
            raw = await search_structured("väestö")
        assert "region" not in json.loads(raw)
