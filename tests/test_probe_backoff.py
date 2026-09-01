"""429 ei ole palvelun vika vaan meidän — eikä sitä saa kirjata vialta.

Ensimmäinen kattava probe-ajo (1.9.2026) teki ``statfin.stat.fi``:lle 1 534
pyyntöä, joista **1 494 hylättiin koodilla 429**. Tahdinsäätö toimi
mitattuna oikein — lokista laskettuna 1,99 pyyntöä sekunnissa tavoitteen
ollessa 2,0 — joten kyse ei ollut liian nopeasta tahdista vaan siitä, että
kyseisen palvelun raja on tiukempi kuin kaksi kutsua sekunnissa. Ensimmäiset
~40 pyyntöä menivät läpi ja loput 13 minuuttia hylättiin, mikä on
aikaikkunakohtaisen kiintiön käyttäytyminen eikä liukuvan sekuntirajan.

Kaksi vikaa seurasi, ja ne testataan tässä erikseen:

1. **Turha kuorma.** Teimme 1 494 pyyntöä jotka tiesimme jo sadan jälkeen
   epäonnistuvan.
2. **Väärä tila kirjanpidossa.** Ne kirjautuivat ``http_error``-tilaan,
   eli kirjanpito väittää palvelun olevan rikki vaikka vika on meissä.
   Tämä on niistä pahempi: puuttuvan tilan näkee, väärä tila valehtelee.
   Mittaamaton aineisto ja rikkinäinen aineisto ovat eri asioita, ja
   ``select_targets`` kohtelee niitä eri tavalla.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import httpx
import pytest

import aura.probe as probe_mod
from aura.database import init_db
from aura.probe import capture, run_probe
from aura.probe.types import ProbeResult, ProbeStatus

NOW = "2026-09-01T12:00:00"


def _kanta(urls: list[str]) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO datasets (id, name, title, source) VALUES ('d1','d1','D','testi')"
    )
    for i, url in enumerate(urls):
        c.execute(
            "INSERT INTO resources (id, dataset_id, name, format, url)"
            " VALUES (?, 'd1', ?, 'CSV', ?)",
            (f"r{i}", f"r{i}", url),
        )
    c.commit()
    return c


def _asiakas(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks=capture.event_hooks(),
        follow_redirects=True,
    )


async def _prober(resource: dict[str, Any], client: httpx.AsyncClient) -> ProbeResult:
    """Proberi joka nostaa statuskoodin esiin kuten oikeatkin tekevät."""
    resp = await client.get(resource["url"])
    if resp.status_code >= 400:
        return ProbeResult(
            status=ProbeStatus.HTTP_ERROR,
            detail=f"HTTP {resp.status_code}",
            http_status=resp.status_code,
        )
    return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")])


class TestRajoitustaEiKirjataViaksi:
    @pytest.mark.anyio
    async def test_429_ei_paady_probe_resultsiin(self) -> None:
        """Rajoitettu kohde on *mittaamaton*, ei rikkinäinen."""
        conn = _kanta([f"https://rajoittaa.test/{i}.csv" for i in range(5)])

        async with _asiakas(lambda r: httpx.Response(429)) as client:
            await run_probe(
                conn, now=NOW, limit=10, client=client, probers={"csv": _prober}
            )

        rivit = conn.execute("SELECT COUNT(*) FROM probe_results").fetchone()[0]
        assert rivit == 0, "429 kirjautui probe_resultsiin"

    @pytest.mark.anyio
    async def test_rajoitettu_kohde_valitaan_uudelleen(self) -> None:
        """Koska mitään ei kirjattu, kohde on yhä probaamaton.

        Tämä on koko kirjaamatta jättämisen tarkoitus: probaamattomat
        valitaan ensin, joten seuraava ajo yrittää näitä uudelleen.
        """
        conn = _kanta(["https://rajoittaa.test/a.csv"])

        async with _asiakas(lambda r: httpx.Response(429)) as client:
            await run_probe(
                conn, now=NOW, limit=10, client=client, probers={"csv": _prober}
            )

        jaljella = probe_mod.select_targets(conn, now=NOW, limit=10)
        assert [t["id"] for t in jaljella] == ["r0"]

    @pytest.mark.anyio
    async def test_muut_virheet_kirjataan_yha(self) -> None:
        """Vain 429 on poikkeus. 404 on aito löydös ja kuuluu kirjata."""
        conn = _kanta(["https://poissa.test/a.csv"])

        async with _asiakas(lambda r: httpx.Response(404)) as client:
            await run_probe(
                conn, now=NOW, limit=10, client=client, probers={"csv": _prober}
            )

        rivi = conn.execute("SELECT status, detail FROM probe_results").fetchone()
        assert rivi is not None and rivi["status"] == ProbeStatus.HTTP_ERROR


class TestIsannastaLuovutaan:
    @pytest.mark.anyio
    async def test_pyynnot_loppuvat_katon_jalkeen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sata kohdetta ei saa tuottaa sataa turhaa pyyntöä."""
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_GIVE_UP", 3)
        conn = _kanta([f"https://rajoittaa.test/{i}.csv" for i in range(50)])
        pyynnot = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pyynnot
            pyynnot += 1
            return httpx.Response(429)

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=60, client=client, probers={"csv": _prober}
            )

        assert pyynnot <= 3, f"isännästä ei luovuttu: {pyynnot} pyyntöä"

    @pytest.mark.anyio
    async def test_onnistuminen_nollaa_laskurin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Yksittäinen 429 ei saa keskeyttää muuten toimivaa isäntää."""
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_GIVE_UP", 3)
        conn = _kanta([f"https://vaihteleva.test/{i}.csv" for i in range(9)])
        laskuri = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal laskuri
            laskuri += 1
            # Joka kolmas hylätään: peräkkäisiä ei koskaan kerry kolmea.
            if laskuri % 3 == 0:
                return httpx.Response(429)
            return httpx.Response(200, text="a\n1\n")

        async with _asiakas(handler) as client:
            yhteenveto = await run_probe(
                conn, now=NOW, limit=20, client=client, probers={"csv": _prober}
            )

        assert yhteenveto["ok"] == 6, f"ajo katkesi kesken: {yhteenveto}"

    @pytest.mark.anyio
    async def test_muut_isannat_jatkavat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Yhden isännän kiintiö ei saa pysäyttää koko ajoa."""
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_GIVE_UP", 2)
        conn = _kanta(
            [f"https://rajoittaa.test/{i}.csv" for i in range(10)]
            + [f"https://toimii.test/{i}.csv" for i in range(4)]
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if "rajoittaa" in str(request.url):
                return httpx.Response(429)
            return httpx.Response(200, text="a\n1\n")

        async with _asiakas(handler) as client:
            yhteenveto = await run_probe(
                conn, now=NOW, limit=20, client=client, probers={"csv": _prober}
            )

        assert yhteenveto["ok"] == 4, f"toimiva isäntä jäi ajamatta: {yhteenveto}"


class TestRetryAfter:
    @pytest.mark.anyio
    async def test_lyhyt_retry_after_odotetaan_ja_yritetaan_uudelleen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Palvelun oma ohje on parempi kuin meidän arvauksemme."""
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_MAX_WAIT", 5.0)
        conn = _kanta(["https://ohjeistaa.test/a.csv"])
        kutsut = 0
        odotukset: list[float] = []

        async def fake_sleep(s: float) -> None:
            odotukset.append(s)

        monkeypatch.setattr(probe_mod.asyncio, "sleep", fake_sleep)

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal kutsut
            kutsut += 1
            if kutsut == 1:
                return httpx.Response(429, headers={"retry-after": "2"})
            return httpx.Response(200, text="a\n1\n")

        async with _asiakas(handler) as client:
            yhteenveto = await run_probe(
                conn, now=NOW, limit=10, client=client, probers={"csv": _prober}
            )

        assert 2.0 in odotukset, f"Retry-Afteria ei noudatettu: {odotukset}"
        assert yhteenveto["ok"] == 1, "uusintaa ei tehty"

    @pytest.mark.anyio
    async def test_pitka_retry_after_ei_jaa_odottamaan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Kymmenen minuutin odotus varaisi työntekijävuoron turhaan.

        Isäntiä on 174 ja yhtäaikaisia vuoroja kahdeksan, joten pitkä
        odotus maksaa muille isännille enemmän kuin voittaa tälle.
        """
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_MAX_WAIT", 5.0)
        monkeypatch.setattr(probe_mod, "RATE_LIMIT_GIVE_UP", 1)
        conn = _kanta(["https://hidas.test/a.csv", "https://hidas.test/b.csv"])
        pyynnot = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pyynnot
            pyynnot += 1
            return httpx.Response(429, headers={"retry-after": "600"})

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=10, client=client, probers={"csv": _prober}
            )

        assert pyynnot == 1, f"pitkää odotusta ei ohitettu: {pyynnot} pyyntöä"
