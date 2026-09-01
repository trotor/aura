"""Vastauksen tosiasiat talteen samasta noudosta jonka probe jo tekee.

``resource_health`` kattoi 121 datasettiä 12 918:sta, koska sen täyttäminen
vaati oman kierroksensa (``aura.health``) joka hakee täsmälleen samat
osoitteet uudelleen. Probe noutaa jokaisen resurssin joka tapauksessa, joten
toinen nouto on pelkkää kuormaa — kannassa on 16 979 probattavaa resurssia
192 eri isännällä.

Testit ajetaan oikean ``httpx.AsyncClient``-olion läpi ``MockTransport``illa,
koska poiminta tapahtuu HTTP-kerroksen tapahtumakoukussa. Proberin
kutsuminen suoraan ei laukaisisi koukkua, jolloin testi menisi läpi
testaamatta juuri sitä mekanismia jonka varassa kaikki on.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import httpx
import pytest

from aura.database import init_db
from aura.probe import capture, run_probe

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
    """Oikea asiakas koukkuineen, mutta verkko korvattuna."""
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks=capture.event_hooks(),
        follow_redirects=True,
    )


async def _csv_prober(resource: dict[str, Any], client: httpx.AsyncClient) -> Any:
    """Minimaalinen proberi: hakee osoitteen ja palauttaa yhden kentän."""
    from aura.probe.types import ProbeResult, ProbeStatus

    await client.get(resource["url"])
    return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")])


class TestSaatavuusSamastaNoudosta:
    @pytest.mark.anyio
    async def test_terveysrivi_kirjautuu_ilman_omaa_kierrosta(self) -> None:
        conn = _kanta(["https://a.test/data.csv"])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/csv", "content-length": "4242"},
                text="a\n1\n",
            )

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": _csv_prober}
            )

        rivi = conn.execute("SELECT * FROM resource_health").fetchone()
        assert rivi is not None, "terveysriviä ei kirjattu"
        assert rivi["status_code"] == 200
        assert rivi["is_available"] == 1
        assert rivi["content_type"] == "text/csv"
        assert rivi["content_length"] == 4242
        assert rivi["response_time_ms"] is not None

    @pytest.mark.anyio
    async def test_uudelleenohjausta_ei_kirjata_vastaukseksi(self) -> None:
        """302 kertoo osoitteen, ei sitä onko data saatavilla.

        Tämä on avoindata.suomi.fi:n tapaus: se vastaa 302:lla ja varsinainen
        sisältö tulee S3:sta. Ilman ohitusta jokaisen resurssin terveydeksi
        kirjautuisi 302 ja ``content_type`` jäisi tyhjäksi.
        """
        conn = _kanta(["https://a.test/redirect"])

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/redirect":
                return httpx.Response(302, headers={"location": "https://b.test/real"})
            return httpx.Response(
                200, headers={"content-type": "text/csv"}, text="a\n1\n"
            )

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": _csv_prober}
            )

        rivi = conn.execute("SELECT * FROM resource_health").fetchone()
        assert rivi["status_code"] == 200, "302 kirjautui vastaukseksi"
        assert rivi["content_type"] == "text/csv"
        assert rivi["url"] == "https://b.test/real"

    @pytest.mark.anyio
    async def test_vastaamaton_kohde_kirjataan_saavuttamattomaksi(self) -> None:
        """Rivi kirjataan silti: "ei vastannut" on saatavuustieto sekin."""
        conn = _kanta(["https://a.test/kuollut.csv"])

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("ei yhteyttä")

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": _csv_prober}
            )

        rivi = conn.execute("SELECT * FROM resource_health").fetchone()
        assert rivi is not None, "vastaamattomasta ei kirjattu riviä"
        assert rivi["is_available"] == 0
        assert rivi["status_code"] is None

    @pytest.mark.anyio
    async def test_ensimmainen_pyynto_ratkaisee(self) -> None:
        """Moni proberi tekee kaksi pyyntöä; resurssin terveys on ensimmäinen.

        WFS hakee ensin GetCapabilitiesin ja sitten DescribeFeatureTypen.
        Jos jälkimmäinen ylikirjoittaisi tuloksen, terveystieto kertoisi
        skeemapyynnöstä eikä resurssista.
        """
        conn = _kanta(["https://a.test/palvelu"])

        def handler(request: httpx.Request) -> httpx.Response:
            if "toinen" in str(request.url):
                return httpx.Response(500, text="rikki")
            return httpx.Response(
                200, headers={"content-type": "application/xml"}, text="ok"
            )

        async def kaksi_pyyntoa(
            resource: dict[str, Any], client: httpx.AsyncClient
        ) -> Any:
            from aura.probe.types import ProbeResult, ProbeStatus

            await client.get(resource["url"])
            await client.get(resource["url"] + "?toinen=1")
            return ProbeResult(status=ProbeStatus.OK, fields=[("a", "string")])

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": kaksi_pyyntoa}
            )

        rivi = conn.execute("SELECT * FROM resource_health").fetchone()
        assert rivi["status_code"] == 200, "toinen pyyntö ylikirjoitti ensimmäisen"


class TestOikeaProberiKayttaaAnnettuaAsiakasta:
    """Poiminta on kiinni asiakkaassa, joten proberin on käytettävä sitä.

    Tämän puuttuminen maksoi oikean ajon: valeproberilla kirjoitetut testit
    menivät läpi, koska ne kutsuivat ``client.get``:iä suoraan. Oikea
    ``tabular``-proberi delegoi esikatselufunktioille, jotka avasivat **oman**
    yhteytensä — jolloin tapahtumakoukut eivät nähneet mitään. Mitattuna
    60 kohteen ajossa 55 kirjautui "ei vastausta" ja vain viisi
    XML-pohjaista (WFS/WMS) onnistui.

    CSV ja JSON ovat kohteista suurin osa, joten vika osui juuri sinne missä
    tieto oli arvokkainta.
    """

    @pytest.mark.anyio
    async def test_tabular_proberi_tuottaa_terveystiedon(self) -> None:
        from aura.probe import tabular

        conn = _kanta(["https://a.test/data.csv"])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/csv", "content-length": "99"},
                text="nimi,arvo\na,1\n",
            )

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": tabular.probe}
            )

        rivi = conn.execute("SELECT * FROM resource_health").fetchone()
        assert rivi is not None, "oikea proberi ei tuottanut terveystietoa"
        assert rivi["status_code"] == 200
        assert rivi["is_available"] == 1
        assert rivi["content_type"] == "text/csv"


class TestDatanMuutosaika:
    @pytest.mark.anyio
    async def test_last_modified_tallentuu_rikastuksena(self) -> None:
        """``Last-Modified`` kertoo milloin data muuttui.

        Katalogin ``metadata_modified`` kertoo milloin *metatietue* muuttui,
        ja laatupisteiden ``timeliness`` lasketaan siitä. Nämä ovat eri
        asioita, joten arvo tallennetaan omaan kenttäänsä.
        """
        conn = _kanta(["https://a.test/data.csv"])
        pvm = "Wed, 20 Aug 2026 10:00:00 GMT"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"last-modified": pvm}, text="a\n1\n")

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": _csv_prober}
            )

        arvo = conn.execute(
            "SELECT value FROM enrichments WHERE field = 'data_modified'"
        ).fetchone()
        assert arvo is not None, "data_modified puuttuu"
        assert arvo["value"] == pvm

    @pytest.mark.anyio
    async def test_ilman_otsaketta_ei_keksita_arvoa(self) -> None:
        conn = _kanta(["https://a.test/data.csv"])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="a\n1\n")

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=5, client=client, probers={"csv": _csv_prober}
            )

        rivit = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE field = 'data_modified'"
        ).fetchone()[0]
        assert rivit == 0


class TestRinnakkaisuusEiSekoitaHavaintoja:
    @pytest.mark.anyio
    async def test_jokainen_kohde_saa_omat_tietonsa(self) -> None:
        """Poiminta on taskikohtainen, ei jaettu.

        Työntekijät ajavat rinnakkain saman ``AsyncClient``-olion läpi. Jos
        poiminta olisi moduulitason muuttuja, nopeamman isännän vastaus
        kirjautuisi hitaamman kohteen terveydeksi — vika joka näkyisi vain
        rinnakkaisessa ajossa ja olisi käytännössä mahdoton jäljittää.
        """
        conn = _kanta([f"https://h{i}.test/data.csv" for i in range(6)])

        def handler(request: httpx.Request) -> httpx.Response:
            # Isäntä hN vastaa statuskoodilla 200 ja pituudella N*100.
            n = int(str(request.url.host)[1])
            return httpx.Response(
                200,
                headers={"content-length": str(n * 100), "content-type": f"t/{n}"},
                text="a\n1\n",
            )

        async with _asiakas(handler) as client:
            await run_probe(
                conn, now=NOW, limit=10, client=client, probers={"csv": _csv_prober}
            )

        rivit = conn.execute(
            "SELECT url, content_type, content_length FROM resource_health"
        ).fetchall()
        assert len(rivit) == 6
        for rivi in rivit:
            n = int(str(httpx.URL(rivi["url"]).host)[1])
            assert rivi["content_type"] == f"t/{n}", f"havainnot menivät ristiin: {rivi}"
            assert rivi["content_length"] == n * 100
