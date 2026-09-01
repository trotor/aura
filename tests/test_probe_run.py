"""Testit probe-ajon orkestroinnille.

Kolme asiaa joita nykyinen infer-schemas ei tee, ja jotka pitävät
kattavuuden 54 datasetissä 12 918:sta: TTL, epäonnistumisen kirjaus ja
tahdinsäätö per isäntä.

TTL porrastuu vian luonteen mukaan. 404 ja timeout ovat eri asioita:
poissa oleva palvelu ei palaa viikossa, hidas palvelu voi.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from typing import Any

import pytest

import aura.probe as probe_mod
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
    async def test_401_tuottaa_auth_method_apikey_vaikka_probe_epaonnistuu(
        self, conn: sqlite3.Connection
    ) -> None:
        """Päästä päähän (I1): 401 tallentuu auth_method='apikey'-enrichmentiksi.

        ``auth_from_status()``:n yksikkötesti (test_probe_derive.py) testasi
        vain puhdasta funktiota — se oli vihreä ``_store()``:n kuolleen
        polun päällä, koska ``if not result.ok: return`` esti kutsun ennen
        kuin auth_from_status() ehti ajaa muissa kuin 200 OK -tapauksissa.
        Tämä testi kulkee koko ketjun run_probe -> _store -> kanta asti.
        """

        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.HTTP_ERROR, detail="HTTP 401", http_status=401
            )

        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        assert yhteenveto["http_error"] == 2
        rivi = conn.execute(
            "SELECT value FROM enrichments WHERE field='auth_method' AND dataset_id='d1'"
        ).fetchone()
        assert rivi is not None
        assert rivi["value"] == "apikey"

    @pytest.mark.anyio
    async def test_auth_kayttaa_final_urlia_ei_kohteen_alkuperaista_urlia(
        self, conn: sqlite3.Connection
    ) -> None:
        """Rekisteröintipäätelmä (I2) käyttää vastauksen final_url:ia.

        Resurssin url on ``https://example.test/r-wfs`` — ei sisällä
        rekisteröinti-vihjettä. Jos ``result.final_url`` ei propagoituisi
        kantaan asti, uudelleenohjaus rekisteröintisivulle jäisi
        näkymättömiin.
        """

        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.HTTP_ERROR,
                detail="HTTP 401",
                http_status=401,
                final_url="https://example.test/account/login",
            )

        await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        rivi = conn.execute(
            "SELECT value FROM enrichments WHERE field='auth_method' AND dataset_id='d1'"
        ).fetchone()
        assert rivi["value"] == "registration"
        url_rivi = conn.execute(
            "SELECT value FROM enrichments"
            " WHERE field='auth_registration_url' AND dataset_id='d1'"
        ).fetchone()
        assert url_rivi["value"] == "https://example.test/account/login"

    @pytest.mark.anyio
    async def test_tyhja_final_url_ei_arvaa_kohteen_urlista(
        self, conn: sqlite3.Connection
    ) -> None:
        """(I2) Tyhjä final_url ei saa langeta takaisin target['url']:iin.

        Resurssin url sisältää sanan 'login' vahingossa (esim.
        tiedostonimen osana) — ennen korjausta ``_store()`` antoi
        ``auth_from_status()``:lle aina ``target['url']:n`` kun proberi ei
        täyttänyt final_url:ia, mikä olisi merkinnyt tämän
        rekisteröintisivuksi vaikka mitään uudelleenohjausta ei nähty.
        """
        conn.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES ('r-login', 'd1', 'r-login', 'WFS',"
            " 'https://example.test/login-2024.csv')"
        )
        conn.commit()

        async def fake_probe(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.HTTP_ERROR, detail="HTTP 401", http_status=401
            )

        await run_probe(
            conn, now=NOW, limit=10, probers={"wfs": fake_probe, "csv": fake_probe}
        )
        assert (
            conn.execute(
                "SELECT 1 FROM enrichments WHERE field='auth_registration_url'"
            ).fetchone()
            is None
        )

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


    @pytest.mark.anyio
    async def test_kaksoiskappale_sarakenimi_ei_kaada_ajoa(
        self, conn: sqlite3.Connection
    ) -> None:
        """resource_schema:n avain (resource_id, field_name) ei siedä kahta
        samannimistä saraketta samalle resurssille.

        WFS-prober voi tuottaa tämän kun ``typeNames`` kattaa useamman
        feature typen joilla on yhteisiä attribuuttinimiä (havaittu
        Lounaistiedon hame_keski_suomi-aineistolla: ``probe --format WFS``
        kaatui käsittelemättömään IntegrityErroriin, ja koska
        select_targets asettaa probaamattomat aina ensin, uudelleenajo
        osui täsmälleen samaan kohteeseen — ajo oli pysyvästi jumissa).

        Kaatuminen tässä ei saa nousta Python-poikkeuksena asti: kohde jää
        kirjatuksi parse_error-tilaan, eikä resource_schema-tauluun jää
        puolitiehen kirjoitettua riviä.
        """

        async def kaksoiskappale(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK,
                fields=[("nimi", "string"), ("nimi", "string")],
                http_status=200,
            )

        yhteenveto = await run_probe(
            conn,
            now=NOW,
            limit=10,
            probers={"wfs": kaksoiskappale, "csv": kaksoiskappale},
        )
        assert yhteenveto == {"parse_error": 2}

        rivi = conn.execute(
            "SELECT status, detail FROM probe_results WHERE resource_id = 'r-wfs'"
        ).fetchone()
        assert rivi is not None
        assert rivi["status"] == "parse_error"
        assert rivi["detail"] != ""

        kentat = conn.execute(
            "SELECT field_name FROM resource_schema WHERE resource_id = 'r-wfs'"
        ).fetchall()
        assert kentat == []

    @pytest.mark.anyio
    async def test_tallennuksen_epaonnistuminen_ei_pysayta_ajoa(
        self, conn: sqlite3.Connection
    ) -> None:
        """Yhden kohteen _store()-kaatuminen ei saa estää seuraavan käsittelyä."""

        async def kaksoiskappale(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK,
                fields=[("nimi", "string"), ("nimi", "string")],
                http_status=200,
            )

        async def onnistuva(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")], http_status=200)

        yhteenveto = await run_probe(
            conn,
            now=NOW,
            limit=10,
            probers={"wfs": kaksoiskappale, "csv": onnistuva},
        )
        assert yhteenveto == {"parse_error": 1, "ok": 1}

        wfs_rivi = conn.execute(
            "SELECT status FROM probe_results WHERE resource_id = 'r-wfs'"
        ).fetchone()
        assert wfs_rivi["status"] == "parse_error"

        csv_rivi = conn.execute(
            "SELECT status FROM probe_results WHERE resource_id = 'r-csv'"
        ).fetchone()
        assert csv_rivi["status"] == "ok"

        kentat = conn.execute(
            "SELECT field_name FROM resource_schema WHERE resource_id = 'r-csv'"
        ).fetchall()
        assert {r["field_name"] for r in kentat} == {"a"}

    @pytest.mark.anyio
    async def test_palautuspolun_oma_kirjoitusvirhe_ei_pysayta_ajoa(
        self, conn: sqlite3.Connection
    ) -> None:
        """(C1) Jos siivouskin epäonnistuu, run_probe ei saa kaatua kokonaan.

        ``_store()``:n oma virhe (kaksoiskappale-sarakenimi) laukaisee
        palautuspolun, joka yrittää ``DELETE FROM resource_schema`` +
        ``upsert_probe_result``. Jos senkin ``conn.execute()`` nostaa
        OperationalErrorin (esim. "attempt to write a readonly database" —
        täsmälleen se mitä probe_schemas nosti read-only-etäpalvelimella
        ennen kuin se lisättiin WRITE_TOOL_NAMESiin), se ei saa karata
        ``run_probe()``:sta asti eikä pysäyttää muiden kohteiden käsittelyä.
        """

        class _EpaonnistuvaSiivous:
            """Oikea yhteys, paitsi r-wfs:n TOINEN resource_schema-DELETE.

            upsert_resource_schema() tekee itsekin saman DELETE:n normaalina
            osana onnistunutta kirjoitusta (poistaa vanhan skeeman ennen
            uuden lisäystä) — sitä ei saa rikkoa, tai r-csv:n onnistunut
            polku hajoaisi testissä turhaan. Vain run_probe():n
            palautuspolun OMA, toinen DELETE r-wfs:lle epäonnistuu.
            """

            def __init__(self, real: sqlite3.Connection) -> None:
                self._real = real
                self._delete_calls: dict[str, int] = {}

            def execute(self, sql: str, *args: Any) -> Any:
                stripped = sql.strip()
                if stripped.startswith("DELETE FROM resource_schema") and args:
                    resource_id = args[0][0]
                    count = self._delete_calls.get(resource_id, 0) + 1
                    self._delete_calls[resource_id] = count
                    if resource_id == "r-wfs" and count == 2:
                        raise sqlite3.OperationalError(
                            "attempt to write a readonly database"
                        )
                return self._real.execute(sql, *args)

            def __getattr__(self, name: str) -> Any:
                return getattr(self._real, name)

        async def kaksoiskappale(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK,
                fields=[("nimi", "string"), ("nimi", "string")],
                http_status=200,
            )

        async def onnistuva(resource: dict[str, Any], client: Any) -> ProbeResult:
            return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")], http_status=200)

        wrapped = _EpaonnistuvaSiivous(conn)
        yhteenveto = await run_probe(
            wrapped,  # type: ignore[arg-type]
            now=NOW,
            limit=10,
            probers={"wfs": kaksoiskappale, "csv": onnistuva},
        )
        # Molemmat kohteet käsiteltiin loppuun asti — ajo ei kaatunut
        # ensimmäiseen, vaikka sen palautuskin epäonnistui.
        assert yhteenveto["ok"] == 1
        assert yhteenveto["parse_error"] == 1

        csv_rivi = conn.execute(
            "SELECT status FROM probe_results WHERE resource_id = 'r-csv'"
        ).fetchone()
        assert csv_rivi["status"] == "ok"


class TestTahdinsaatoJaRinnakkaisuus:
    """Kolmas asia jonka moduulin docstring lupaa, mutta jota ei testattu.

    Speksi (``docs/superpowers/specs/2026-08-19-probe-vaihe-design.md``) sanoo:
    *"Tahdinsäätö on 2 kutsua sekunnissa per isäntä, rinnakkaisuus isäntien
    välillä."* Molemmat puoliskot tarvitaan ja ne ovat vastakkaisia — pelkkä
    tahdinsäätö ilman rinnakkaisuutta tekee kattavasta ajosta mahdottoman
    (31 466 probattavaa resurssia), ja pelkkä rinnakkaisuus ilman
    isäntäkohtaista tahtia törmää 429-rajoitukseen.

    Testit mittaavat kestoa, joten kynnykset ovat väljiä: väite on
    "sarjallinen vs. rinnakkainen", ei tarkka sekuntimäärä.
    """

    @staticmethod
    def _conn_isannilla(hosts: list[str]) -> sqlite3.Connection:
        """Kanta jossa on yksi CSV-resurssi kutakin annettua isäntää kohti."""
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        init_db(c)
        c.execute(
            "INSERT INTO datasets (id, name, title, source)"
            " VALUES ('d1','d1','D','testi')"
        )
        for i, host in enumerate(hosts):
            c.execute(
                "INSERT INTO resources (id, dataset_id, name, format, url)"
                " VALUES (?, 'd1', ?, 'CSV', ?)",
                (f"r{i}", f"r{i}", f"https://{host}/data{i}.csv"),
            )
        c.commit()
        return c

    @staticmethod
    def _hidas_prober(kesto: float) -> Any:
        async def prober(resource: dict[str, Any], client: Any) -> ProbeResult:
            await asyncio.sleep(kesto)
            return ProbeResult(status=ProbeStatus.OK, http_status=200)

        return prober

    @pytest.mark.anyio
    async def test_eri_isannat_ajetaan_rinnakkain(self) -> None:
        """Neljä isäntää, jokainen 0,1 s — rinnakkaisena ~0,1 s, ei 0,4 s."""
        conn = self._conn_isannilla([f"h{i}.test" for i in range(4)])
        alku = time.monotonic()
        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"csv": self._hidas_prober(0.1)}
        )
        kesto = time.monotonic() - alku
        assert yhteenveto["ok"] == 4
        assert kesto < 0.25, f"näyttää sarjalliselta: {kesto:.2f} s"

    @pytest.mark.anyio
    async def test_saman_isannan_kutsut_pysyvat_sarjallisina(self) -> None:
        """Sama isäntä neljästi: tahdin on säilyttävä, ei saa rinnakkaistua."""
        conn = self._conn_isannilla(["sama.test"] * 4)
        alku = time.monotonic()
        yhteenveto = await run_probe(
            conn, now=NOW, limit=10, probers={"csv": self._hidas_prober(0.1)}
        )
        kesto = time.monotonic() - alku
        assert yhteenveto["ok"] == 4
        assert kesto >= 0.3, f"saman isännän kutsut rinnakkaistuivat: {kesto:.2f} s"

    @pytest.mark.anyio
    async def test_saman_isannan_kutsujen_vali_on_tahdin_mukainen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tahdinsäätö itsessään, ilman että proberin kesto peittää sen."""
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_PER_SECOND", 20.0)
        conn = self._conn_isannilla(["sama.test"] * 3)
        hetket: list[float] = []

        async def prober(resource: dict[str, Any], client: Any) -> ProbeResult:
            hetket.append(time.monotonic())
            return ProbeResult(status=ProbeStatus.OK, http_status=200)

        await run_probe(conn, now=NOW, limit=10, probers={"csv": prober})
        assert len(hetket) == 3
        valit = [b - a for a, b in zip(hetket, hetket[1:], strict=False)]
        # 1/20 s = 0,05 s; sallitaan ajastimen epätarkkuus alaspäin.
        assert all(v >= 0.04 for v in valit), f"tahti ei pitänyt: {valit}"

    @pytest.mark.anyio
    async def test_rinnakkaisuudella_on_katto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Isäntiä voi olla tuhansia; yhtäaikaisia pyyntöjä ei saa olla.

        Ilman kattoa kattava ajo avaisi yhtä monta yhteyttä kuin on isäntiä,
        mikä kaataisi sekä paikallisen prosessin että kohteliaisuuden.
        """
        monkeypatch.setattr(probe_mod, "HOST_CONCURRENCY", 2)
        conn = self._conn_isannilla([f"h{i}.test" for i in range(6)])
        yhtaaikaa = 0
        huippu = 0

        async def prober(resource: dict[str, Any], client: Any) -> ProbeResult:
            nonlocal yhtaaikaa, huippu
            yhtaaikaa += 1
            huippu = max(huippu, yhtaaikaa)
            await asyncio.sleep(0.05)
            yhtaaikaa -= 1
            return ProbeResult(status=ProbeStatus.OK, http_status=200)

        yhteenveto = await run_probe(conn, now=NOW, limit=10, probers={"csv": prober})
        assert yhteenveto["ok"] == 6
        assert huippu <= 2, f"katto ei pitänyt, huippu {huippu}"

    @pytest.mark.anyio
    async def test_kaikki_tulokset_tallentuvat_rinnakkaisajossa(self) -> None:
        """Kirjoitukset menevät yhdestä paikasta, joten yhtään ei saa kadota.

        SQLite-yhteys ei kestä rinnakkaista kirjoitusta, joten proberit
        ajetaan rinnakkain mutta tulokset kirjataan sarjallisesti. Jos tämä
        menisi väärin, osa riveistä katoaisi hiljaa.
        """
        conn = self._conn_isannilla([f"h{i}.test" for i in range(12)])
        yhteenveto = await run_probe(
            conn, now=NOW, limit=50, probers={"csv": self._hidas_prober(0.01)}
        )
        assert yhteenveto["ok"] == 12
        rivit = conn.execute("SELECT COUNT(*) FROM probe_results").fetchone()[0]
        assert rivit == 12, f"kantaan päätyi {rivit}/12"
