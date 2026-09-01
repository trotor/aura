"""Agenttivalmius: pääseekö agentti dataan käsiksi ilman ihmistä.

Nykyinen laatupiste mittaa **metatiedon täydellisyyttä**. Se on hyvä siinä
mitä se mittaa, mutta se ei kerro pääseekö dataan käsiksi — ja agentille
juuri jälkimmäinen ratkaisee. Mitattuna 1.9.2026: 434 datasettiä saa
laatupisteet ≥ 85, ja niistä 67 on sellaisia joiden skeemaa ei tunneta
lainkaan.

Kolme suunnittelupäätöstä, kaikki issuen omiin kysymyksiin:

**Luku *ja* liput.** Luku järjestää, liput selittävät. Pelkkä luku
piilottaisi syyn ("miksi 40?"), pelkät liput eivät järjestäisi mitään.

**Mittaamaton ei ole nolla.** Probaamaton datasetti ei ole sama kuin
probattu ja epäonnistunut: ensimmäinen on meidän puutteemme, toinen
palvelun. Mittaamattomalle **ei kirjoiteta riviä lainkaan** — puuttuvan
tilan näkee, keksitty nolla valehtelee. Sama periaate kuin 429:n
kirjaamatta jättämisessä.

**Kokonaispisteisiin ei kosketa.** ``DIMENSION_WEIGHTS`` pysyy ennallaan,
joten ``overall`` tarkoittaa yhä samaa kuin ennen eikä yksikään olemassa
oleva luku liiku. Agenttivalmius on rinnakkainen mittari, ei korjaus
vanhaan.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

import aura.server  # noqa: F401 — ratkaise kiertoimport ennen tools-tuonteja
from aura.database import init_db
from aura.quality import (
    AgentFacts,
    calculate_agent_readiness,
    collect_agent_facts,
    save_quality_scores,
    score_all_datasets,
)
from aura.server import quality_report
from aura.tools.quality import (
    AGENT_READINESS,
    DIMENSION_LABELS,
    SCORED_DIMENSIONS,
)


class TestMittaamatonEiOleNolla:
    def test_probaamaton_ei_saa_pisteita_lainkaan(self) -> None:
        """Tämä on issuen tärkein vaatimus.

        Ilman tätä luku rankaisisi siitä ettei probea ole vielä ajettu, eli
        se mittaisi meidän ahkeruuttamme eikä aineiston käytettävyyttä.
        """
        assert calculate_agent_readiness(AgentFacts(probed=False)) is None

    def test_probattu_mutta_epaonnistunut_saa_pisteet(self) -> None:
        """Epäonnistuminen on mittaustulos, ei mittaamattomuutta."""
        tulos = calculate_agent_readiness(
            AgentFacts(probed=True, probe_ok=False, schema_known=False)
        )
        assert tulos is not None
        pisteet, _ = tulos
        assert pisteet < 50

    def test_kaksi_tilaa_eroavat_toisistaan(self) -> None:
        eiproba = calculate_agent_readiness(AgentFacts(probed=False))
        epaonnistui = calculate_agent_readiness(AgentFacts(probed=True))
        assert eiproba is None and epaonnistui is not None


class TestPisteytys:
    def test_taysi_valmius(self) -> None:
        tulos = calculate_agent_readiness(
            AgentFacts(
                probed=True, probe_ok=True, schema_known=True, available=True
            )
        )
        assert tulos is not None
        assert tulos[0] == 100.0

    def test_tunnistautuminen_laskee_pisteita(self) -> None:
        """Agentti ei voi rekisteröityä palveluun itse."""
        ilman = calculate_agent_readiness(
            AgentFacts(probed=True, probe_ok=True, schema_known=True, available=True)
        )
        kanssa = calculate_agent_readiness(
            AgentFacts(
                probed=True,
                probe_ok=True,
                schema_known=True,
                available=True,
                auth_required=True,
            )
        )
        assert ilman is not None and kanssa is not None
        assert kanssa[0] < ilman[0]

    def test_skeeman_puute_laskee_pisteita(self) -> None:
        """Ilman kenttätietoa agentti ei osaa muodostaa kyselyä."""
        with_ = calculate_agent_readiness(
            AgentFacts(probed=True, probe_ok=True, schema_known=True, available=True)
        )
        without = calculate_agent_readiness(
            AgentFacts(probed=True, probe_ok=True, schema_known=False, available=True)
        )
        assert with_ is not None and without is not None
        assert without[0] < with_[0]

    def test_liput_kertovat_syyn(self) -> None:
        """Luku järjestää, liput selittävät."""
        tulos = calculate_agent_readiness(
            AgentFacts(probed=True, probe_ok=True, schema_known=False, available=True)
        )
        assert tulos is not None
        _, tiedot = tulos
        assert tiedot["schema_known"] is False
        assert tiedot["endpoint_responds"] is True


class TestTallennus:
    def test_none_ei_kirjoita_rivia(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        save_quality_scores(conn, "d1", {"agent_readiness": None})
        rivit = conn.execute("SELECT COUNT(*) FROM quality_scores").fetchone()[0]
        assert rivit == 0
        conn.close()


class TestHavaintojenKeruu:
    @staticmethod
    def _kanta() -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        for ds in ("valmis", "eiprobattu", "rikki", "avaimella"):
            conn.execute(
                "INSERT INTO datasets (id, name, title, source)"
                " VALUES (?, ?, ?, 'testi')",
                (ds, ds, ds),
            )
            conn.execute(
                "INSERT INTO resources (id, dataset_id, name, format, url)"
                " VALUES (?, ?, ?, 'CSV', ?)",
                (f"r-{ds}", ds, ds, f"https://x.test/{ds}.csv"),
            )
        return conn

    def test_havainnot_luetaan_oikeista_tauluista(self) -> None:
        conn = self._kanta()
        conn.execute(
            "INSERT INTO probe_results (resource_id, dataset_id, probe_type,"
            " status, detail, probed_at) VALUES"
            " ('r-valmis','valmis','csv','ok','','2026-09-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO probe_results (resource_id, dataset_id, probe_type,"
            " status, detail, probed_at) VALUES"
            " ('r-rikki','rikki','csv','http_error','HTTP 404','2026-09-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO resource_schema (resource_id, dataset_id, field_name,"
            " field_type) VALUES ('r-valmis','valmis','kunta','string')"
        )
        conn.commit()

        havainnot = collect_agent_facts(conn)

        assert havainnot["valmis"].probed and havainnot["valmis"].probe_ok
        assert havainnot["valmis"].schema_known
        assert havainnot["rikki"].probed and not havainnot["rikki"].probe_ok
        assert not havainnot["rikki"].schema_known
        assert "eiprobattu" not in havainnot or not havainnot["eiprobattu"].probed
        conn.close()

    def test_auth_method_tunnistetaan_rikastuksesta(self) -> None:
        conn = self._kanta()
        conn.execute(
            "INSERT INTO probe_results (resource_id, dataset_id, probe_type,"
            " status, detail, probed_at) VALUES"
            " ('r-avaimella','avaimella','csv','http_error','HTTP 401',"
            " '2026-09-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type)"
            " VALUES ('avaimella','auth_method','api_key','probe')"
        )
        conn.commit()
        havainnot = collect_agent_facts(conn)
        assert havainnot["avaimella"].auth_required
        conn.close()

    def test_service_layers_kelpaa_skeemaksi(self) -> None:
        """WMS-palvelulla ei ole sarakkeita mutta on layerit."""
        conn = self._kanta()
        conn.execute(
            "INSERT INTO probe_results (resource_id, dataset_id, probe_type,"
            " status, detail, probed_at) VALUES"
            " ('r-valmis','valmis','wms','ok','','2026-09-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO enrichments (dataset_id, field, value, source_type)"
            " VALUES ('valmis','service_layers','[{\"name\":\"a\"}]','probe')"
        )
        conn.commit()
        assert collect_agent_facts(conn)["valmis"].schema_known
        conn.close()


class TestEiRikoNykyisia:
    def test_overall_ei_muutu(self) -> None:
        """Kokonaispisteet tarkoittavat yhä samaa kuin ennen."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO datasets (id, name, title, title_fi, notes_fi, source,"
            " metadata_modified) VALUES ('d1','d1','T','T','Kuvaus tähän','testi',"
            " '2026-08-01')"
        )
        conn.commit()

        score_all_datasets(conn)
        ennen = conn.execute(
            "SELECT score FROM quality_scores WHERE dataset_id='d1'"
            " AND dimension='overall'"
        ).fetchone()[0]

        score_all_datasets(conn)
        jalkeen = conn.execute(
            "SELECT score FROM quality_scores WHERE dataset_id='d1'"
            " AND dimension='overall'"
        ).fetchone()[0]
        assert ennen == jalkeen
        conn.close()

    def test_agenttivalmius_kirjautuu_probatuille(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO datasets (id, name, title, source)"
            " VALUES ('d1','d1','T','testi')"
        )
        conn.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES ('r1','d1','r','CSV','https://x.test/a.csv')"
        )
        conn.execute(
            "INSERT INTO probe_results (resource_id, dataset_id, probe_type,"
            " status, detail, probed_at) VALUES"
            " ('r1','d1','csv','ok','','2026-09-01T00:00:00')"
        )
        conn.commit()

        score_all_datasets(conn)
        rivi = conn.execute(
            "SELECT score FROM quality_scores WHERE dataset_id='d1'"
            " AND dimension='agent_readiness'"
        ).fetchone()
        assert rivi is not None, "agenttivalmius ei kirjautunut"
        conn.close()

    def test_probaamattomalle_ei_kirjoiteta_agenttivalmiutta(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO datasets (id, name, title, source)"
            " VALUES ('d1','d1','T','testi')"
        )
        conn.commit()

        score_all_datasets(conn)
        rivi = conn.execute(
            "SELECT score FROM quality_scores WHERE dataset_id='d1'"
            " AND dimension='agent_readiness'"
        ).fetchone()
        assert rivi is None, "mittaamattomalle keksittiin luku"
        conn.close()


@pytest.mark.parametrize(
    ("facts", "odotus"),
    [
        (AgentFacts(probed=True, probe_ok=True, schema_known=True, available=True), 100.0),
        (AgentFacts(probed=True, probe_ok=True, schema_known=False, available=True), 60.0),
        (AgentFacts(probed=True, probe_ok=False, schema_known=False), 20.0),
    ],
)
def test_pisteytyksen_rakenne(facts: AgentFacts, odotus: float) -> None:
    """Painot ovat 40 / 40 / 20 ja ne on valittu sen mukaan mikä estää agentin.

    Vastaamaton rajapinta ja tuntematon skeema ovat kumpikin täysiä esteitä,
    tunnistautuminen kolmas. Kaksi ensimmäistä painavat enemmän, koska
    tunnistautumisen voi ihminen hoitaa kerran, kun taas kaatuvaa rajapintaa
    ei voi kiertää mitenkään.
    """
    tulos = calculate_agent_readiness(facts)
    assert tulos is not None
    assert tulos[0] == odotus


class TestNakyvyysTyokaluissa:
    """Issuen kolmas suunnittelukysymys: oma työkalu vai uusi dimensio.

    Ratkaisu on dimensio, koska ``quality_scores`` on jo dimensiokohtainen ja
    ``quality_ranking`` osaa järjestää minkä tahansa dimension mukaan. Uusi
    työkalu olisi neljäs tapa kysyä samaa taulua.

    Yksi asia ei kuitenkaan yleisty: ``DIMENSION_LABELS`` on ``overall``-luvun
    **erittely**, ja siihen lisättynä agenttivalmius näyttäisi selittävän
    lukua johon se ei vaikuta. Siksi se renderöidään erikseen.
    """

    @staticmethod
    def _kanta(probattu: bool) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.execute(
            "INSERT INTO datasets (id, name, title, title_fi, source)"
            " VALUES ('d1','d1','T','T','testi')"
        )
        conn.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES ('r1','d1','r','CSV','https://x.test/a.csv')"
        )
        if probattu:
            conn.execute(
                "INSERT INTO probe_results (resource_id, dataset_id, probe_type,"
                " status, detail, probed_at) VALUES"
                " ('r1','d1','csv','ok','','2026-09-01T00:00:00')"
            )
        conn.commit()
        return conn

    def test_agenttivalmius_ei_ole_overallin_erittelyssa(self) -> None:
        """Jos tämä pettää, describe väittää luvun selittävän kokonaispisteitä."""
        assert AGENT_READINESS not in DIMENSION_LABELS

    def test_ranking_hyvaksyy_dimension(self) -> None:
        assert AGENT_READINESS in SCORED_DIMENSIONS

    def test_raportti_nayttaa_luvun_ja_liput(self) -> None:
        conn = self._kanta(probattu=True)
        score_all_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn):
            teksti = quality_report("d1")
        assert "Agenttivalmius" in teksti
        assert "rajapinta vastaa" in teksti
        conn.close()

    def test_raportti_sanoo_suoraan_jos_ei_mitattu(self) -> None:
        """Puuttuva luku on kerrottava, ei jätettävä huomaamatta."""
        conn = self._kanta(probattu=False)
        score_all_datasets(conn)
        with patch("aura.server._get_conn", return_value=conn):
            teksti = quality_report("d1")
        assert "ei mitattu" in teksti
        conn.close()
