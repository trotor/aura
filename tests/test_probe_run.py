"""Testit probe-ajon orkestroinnille.

Kolme asiaa joita nykyinen infer-schemas ei tee, ja jotka pitävät
kattavuuden 54 datasetissä 12 918:sta: TTL, epäonnistumisen kirjaus ja
tahdinsäätö per isäntä.

TTL porrastuu vian luonteen mukaan. 404 ja timeout ovat eri asioita:
poissa oleva palvelu ei palaa viikossa, hidas palvelu voi.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from aura.database import init_db, upsert_probe_result
from aura.probe import TTL_DAYS, run_probe, select_targets
from aura.probe.types import ProbeResult, ProbeStatus

NOW = "2026-08-19T12:00:00"


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    for rid, fmt in (("r-wfs", "WFS"), ("r-csv", "CSV"), ("r-pdf", "PDF")):
        c.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES (?, 'd1', ?, ?, ?)",
            (rid, rid, fmt, f"https://example.test/{rid}"),
        )
    c.commit()
    return c


class TestKohteidenValinta:
    def test_vain_probattavat_formaatit(self, conn: sqlite3.Connection) -> None:
        idt = {t["id"] for t in select_targets(conn, now=NOW)}
        assert idt == {"r-wfs", "r-csv"}
        assert "r-pdf" not in idt

    def test_probaamattomat_ensin(self, conn: sqlite3.Connection) -> None:
        upsert_probe_result(conn, "r-wfs", "d1", "wfs", "ok", "", "2020-01-01T00:00:00")
        conn.commit()
        idt = [t["id"] for t in select_targets(conn, now=NOW)]
        assert idt[0] == "r-csv"

    def test_tuore_onnistuminen_ohitetaan(self, conn: sqlite3.Connection) -> None:
        upsert_probe_result(conn, "r-wfs", "d1", "wfs", "ok", "", "2026-08-18T00:00:00")
        conn.commit()
        assert "r-wfs" not in {t["id"] for t in select_targets(conn, now=NOW)}

    def test_vanhentunut_onnistuminen_yritetaan_uudestaan(
        self, conn: sqlite3.Connection
    ) -> None:
        upsert_probe_result(conn, "r-wfs", "d1", "wfs", "ok", "", "2026-01-01T00:00:00")
        conn.commit()
        assert "r-wfs" in {t["id"] for t in select_targets(conn, now=NOW)}

    def test_404_odottaa_pidempaan_kuin_timeout(
        self, conn: sqlite3.Connection
    ) -> None:
        """Poissa oleva palvelu ei palaa viikossa; hidas voi."""
        assert TTL_DAYS["http_error_permanent"] > TTL_DAYS["timeout"]

        upsert_probe_result(
            conn, "r-wfs", "d1", "wfs", "http_error", "HTTP 404", "2026-07-20T00:00:00"
        )
        upsert_probe_result(
            conn, "r-csv", "d1", "csv", "timeout", "", "2026-07-20T00:00:00"
        )
        conn.commit()
        idt = {t["id"] for t in select_targets(conn, now=NOW)}
        assert "r-csv" in idt, "timeout olisi pitänyt yrittää uudestaan"
        assert "r-wfs" not in idt, "404 ei kuulu yrittää joka kierroksella"

    def test_lahde_ja_formaatti_rajaavat(self, conn: sqlite3.Connection) -> None:
        assert {t["id"] for t in select_targets(conn, now=NOW, fmt="WFS")} == {"r-wfs"}
        assert select_targets(conn, now=NOW, source="ei-ole") == []

    def test_max_age_days_ohittaa_tilakohtaisen_ttl_n(
        self, conn: sqlite3.Connection
    ) -> None:
        """--max-age-days ohittaa TTL:n kokonaan, riippumatta tilasta.

        404 saisi normaalisti 90 vrk:n TTL:n (http_error_permanent) eikä
        yrittäisi uudestaan 2 vrk:n jälkeen. max_age_days=1 ohittaa sen.
        """
        upsert_probe_result(
            conn, "r-wfs", "d1", "wfs", "http_error", "HTTP 404", "2026-08-17T12:00:00"
        )
        conn.commit()
        idt = {t["id"] for t in select_targets(conn, now=NOW, max_age_days=1)}
        assert "r-wfs" in idt

    def test_max_age_days_oletus_kayttaytyy_kuten_ennen(
        self, conn: sqlite3.Connection
    ) -> None:
        """max_age_days=0 (oletus) ei muuta käytöstä: sama 404 pysyy TTL:n sisällä."""
        upsert_probe_result(
            conn, "r-wfs", "d1", "wfs", "http_error", "HTTP 404", "2026-08-17T12:00:00"
        )
        conn.commit()
        idt = {t["id"] for t in select_targets(conn, now=NOW)}
        assert "r-wfs" not in idt


class TestAjo:
    @pytest.mark.anyio
    async def test_tulokset_kirjautuvat_kantaan(self, conn: sqlite3.Connection) -> None:
        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK,
                fields=[("kuntakoodi", "string"), ("nimi", "string")],
                enrichments=[("crs", "EPSG:3067")],
                http_status=200,
            )

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        assert yhteenveto["ok"] == 2

        kentat = conn.execute(
            "SELECT field_name FROM resource_schema WHERE resource_id = 'r-wfs'"
        ).fetchall()
        assert {r["field_name"] for r in kentat} == {"kuntakoodi", "nimi"}

        crs = conn.execute(
            "SELECT value FROM enrichments WHERE field='crs' AND dataset_id='d1'"
        ).fetchone()
        assert crs["value"] == "EPSG:3067"

    @pytest.mark.anyio
    async def test_avainkentat_tunnistetaan_sarakkeista(
        self, conn: sqlite3.Connection
    ) -> None:
        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK, fields=[("kuntakoodi", "string")], http_status=200
            )

        await run_probe(conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe})
        rivi = conn.execute(
            "SELECT value, source_detail FROM enrichments WHERE field='joinable_keys'"
        ).fetchone()
        assert rivi is not None
        assert "kuntakoodi" in rivi["value"]
        assert "heuristic" in rivi["source_detail"]

    @pytest.mark.anyio
    async def test_epaonnistuminen_kirjataan_syineen(
        self, conn: sqlite3.Connection
    ) -> None:
        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.HTTP_ERROR, detail="HTTP 404", http_status=404
            )

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        assert yhteenveto["http_error"] == 2
        rivi = conn.execute(
            "SELECT status, detail FROM probe_results WHERE resource_id='r-wfs'"
        ).fetchone()
        assert rivi["status"] == "http_error"
        assert rivi["detail"] == "HTTP 404"

    @pytest.mark.anyio
    async def test_yhden_kaatuminen_ei_lopeta_ajoa(
        self, conn: sqlite3.Connection
    ) -> None:
        async def raivostuva(resource: dict[str, Any], client: Any) -> ProbeResult:
            raise RuntimeError("odottamaton")

        async def onnistuva(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")], http_status=200)

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": raivostuva, "csv": onnistuva}
        )
        assert yhteenveto["ok"] == 1
        rivi = conn.execute(
            "SELECT status FROM probe_results WHERE resource_id='r-wfs'"
        ).fetchone()
        assert rivi["status"] == "parse_error"

    @pytest.mark.anyio
    async def test_epaonnistuneen_tuloksen_sisaltoa_ei_tallenneta(
        self, conn: sqlite3.Connection
    ) -> None:
        """`_store()`:n vartija: epäonnistuneen proben sisältö ei saa läpäistä sitä.

        Prober voi teknisesti täyttää `fields`/`enrichments`-kentät vaikka
        status olisi epäonnistunut (esim. osittainen vastaus ennen virhettä).
        Vartijan pitää silti hylätä ne kokonaan — vain kirjanpitorivi jää.
        """

        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.HTTP_ERROR,
                detail="HTTP 500",
                fields=[("kuntakoodi", "string")],
                enrichments=[("crs", "EPSG:3067")],
                http_status=500,
            )

        await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )

        kentat = conn.execute(
            "SELECT field_name FROM resource_schema WHERE resource_id = 'r-wfs'"
        ).fetchall()
        assert kentat == []

        rikastukset = conn.execute(
            "SELECT field FROM enrichments WHERE dataset_id = 'd1'"
        ).fetchall()
        assert rikastukset == []

        rivi = conn.execute(
            "SELECT status FROM probe_results WHERE resource_id = 'r-wfs'"
        ).fetchone()
        assert rivi["status"] == "http_error"

    @pytest.mark.anyio
    async def test_max_age_days_valittyy_select_targets_lle(
        self, conn: sqlite3.Connection
    ) -> None:
        """run_probe():n on välitettävä max_age_days select_targets:lle.

        Ilman tätä lippu näyttäisi toimivalta CLI:ssä (parseri hyväksyy sen)
        muttei tekisi mitään — sama vikaluokka jonka takia tämä koko
        parametri lisättiin.
        """
        upsert_probe_result(
            conn, "r-wfs", "d1", "wfs", "http_error", "HTTP 404", "2026-08-17T12:00:00"
        )
        conn.commit()

        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")], http_status=200)

        yhteenveto = await run_probe(
            conn,
            now=NOW,
            limit=10,
            max_age_days=1,
            probers={"wfs": fake_probe, "csv": fake_probe},
        )
        # r-wfs (2 vrk vanha 404, ohitettu max_age_days:llä) + r-csv (probaamaton)
        assert yhteenveto["ok"] == 2

