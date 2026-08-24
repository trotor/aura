"""Testit ilmiselvästi rikkinäisten resurssi-URL:ien normalisoinnille.

Aura tallentaa uskollisesti sen mitä ylävirran katalogi julkaisee. Useimmiten
se on oikein — mutta kahdessa mitatussa tapauksessa julkaistu URL ei toimi
lainkaan, ja aineisto näyttää katalogissa käyttökelpoiselta vaikka ei ole.

Probe-vaiheen ensimmäinen ajo paljasti molemmat: 151 resurssia 12 918:sta,
ja noin 26 epäonnistumista 65:stä johtui näistä eikä palvelun viasta.

Normalisointi on tarkoituksella kapea. Jokainen sääntö osuu tarkkaan
tunnettuun rikkinäiseen muotoon ja palauttaa muuten syötteen sellaisenaan:
arvaava normalisointi rikkoisi toimivia osoitteita, mikä on pahempi vika
kuin se jota se korjaa.
"""

from __future__ import annotations

import pytest

from aura.url_normalize import normalize_resource_url


class TestStatHelPxWeb:
    """Selaussivu ei ole rajapinta.

    ``https://stat.hel.fi/pxweb/fi/…`` on PxWebin selain-UI ja palauttaa
    HTML:ää. Sama taulu on saatavilla ``/api/v1/fi/…``-polusta JSONina.
    Muunnos on todennettu elävää palvelua vasten: selaussivu antaa 200 +
    text/html, muunnettu 200 + application/json ja taulun metatiedot.

    Yhdistetty segmentti purkautuu: ``Aluesarjat__rak__ratuo`` on API:ssa
    polku ``rak/ratuo``, koska tietokannan nimi on jo edellisenä segmenttinä.
    """

    def test_taulun_url_muuntuu_apiksi(self) -> None:
        annettu = (
            "https://stat.hel.fi/pxweb/fi/Aluesarjat/"
            "Aluesarjat__rak__ratuo/alu_ratuo_039n.px/"
        )
        odotus = (
            "https://stat.hel.fi/api/v1/fi/Aluesarjat/rak/ratuo/alu_ratuo_039n.px"
        )
        assert normalize_resource_url(annettu) == odotus

    def test_ilman_loppukauttaviivaa(self) -> None:
        annettu = (
            "https://stat.hel.fi/pxweb/fi/Aluesarjat/"
            "Aluesarjat__rak__astuo/alu_astuo_039f.px"
        )
        assert normalize_resource_url(annettu).endswith(
            "/api/v1/fi/Aluesarjat/rak/astuo/alu_astuo_039f.px"
        )

    def test_kaksitasoinen_yhdistelma(self) -> None:
        """Segmenttejä voi olla enemmän kuin kaksi."""
        annettu = (
            "https://stat.hel.fi/pxweb/fi/Hyvinvointitilastot/"
            "Hyvinvointitilastot__a__b__c/taulu.px/"
        )
        assert normalize_resource_url(annettu) == (
            "https://stat.hel.fi/api/v1/fi/Hyvinvointitilastot/a/b/c/taulu.px"
        )

    def test_selauspolku_ilman_taulua_sailyy(self) -> None:
        """Ilman .px-taulua ei ole mitään mihin osoittaa — ei arvata."""
        annettu = "https://stat.hel.fi/pxweb/fi/SDG/SDG__SDG/"
        assert normalize_resource_url(annettu) == annettu

    def test_jo_api_muodossa_sailyy(self) -> None:
        annettu = "https://stat.hel.fi/api/v1/fi/Aluesarjat/rak/ratuo/x.px"
        assert normalize_resource_url(annettu) == annettu

    def test_toinen_pxweb_palvelin_ei_muutu(self) -> None:
        """Sääntö on isäntäkohtainen: muiden PxWeb-asennusten polut eroavat."""
        annettu = "https://statfin.stat.fi/pxweb/fi/StatFin/StatFin__tyti/135y.px/"
        assert normalize_resource_url(annettu) == annettu


class TestPorttiKahdeksankymmenta:
    """Portti 80 https-skeemalla on aina virhe.

    ``https://geoserver.lounaistieto.fi:80/…`` tuottaa
    ``SSL: WRONG_VERSION_NUMBER``, koska palvelin puhuu portissa 80
    selväkielistä HTTP:tä. Sama osoite ilman porttia vastaa 200.
    """

    def test_portti_poistuu_https_sta(self) -> None:
        annettu = "https://geoserver.lounaistieto.fi:80/geoserver/varely/ows?service=WMS"
        assert normalize_resource_url(annettu) == (
            "https://geoserver.lounaistieto.fi/geoserver/varely/ows?service=WMS"
        )

    def test_http_ja_portti_80_sailyy(self) -> None:
        """http://host:80 on turha muttei väärä — ei kosketa."""
        annettu = "http://www.paikkatietohakemisto.fi:80/geonetwork/srv/api/records/x"
        assert normalize_resource_url(annettu) == annettu

    def test_muu_portti_sailyy(self) -> None:
        """Vain 80 on ristiriidassa https:n kanssa."""
        annettu = "https://example.test:8443/wfs"
        assert normalize_resource_url(annettu) == annettu

    def test_portti_443_sailyy(self) -> None:
        annettu = "https://example.test:443/wfs"
        assert normalize_resource_url(annettu) == annettu


class TestEiArvaa:
    """Normalisoinnin on oltava huomaamaton silloin kun se ei tunnista mitään."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.test/data.csv",
            "http://example.test/wfs?service=WFS",
            "https://opendata.fmi.fi/wfs?request=GetCapabilities",
            "",
            "ei-url-lainkaan",
            "ftp://example.test/tiedosto.zip",
        ],
    )
    def test_tuntematon_palautuu_sellaisenaan(self, url: str) -> None:
        assert normalize_resource_url(url) == url

    def test_none_ei_kaada(self) -> None:
        assert normalize_resource_url(None) == ""


class TestKytkentaHarvestointiin:
    """Normalisointi tapahtuu siellä missä Dataset syntyy.

    Sovelluskohta on ``BaseHarvester._make_dataset``, jolloin sääntö kattaa
    kaikki harvesterit eikä vain niitä kahta joista ongelma löytyi.
    Ongelmaluokka — ylävirran katalogi julkaisee toimimattoman osoitteen —
    ei ole lähdekohtainen.
    """

    def test_make_dataset_normalisoi_resurssin(self) -> None:
        import aura.server  # noqa: F401 — rikkoo kiertoimportin oikeassa järjestyksessä
        from aura.harvesters.base import BaseHarvester
        from aura.models import Resource

        class Testiharvesteri(BaseHarvester):
            name = "testi"
            description = "testi"
            url = "https://example.test"

            async def harvest(self) -> int:
                return 0

        h = Testiharvesteri(conn=None)
        ds = h._make_dataset(
            id="d1",
            name="d1",
            title="Testi",
            resources=[
                Resource(
                    id="r1",
                    name="taulu",
                    format="PXWEB",
                    url=(
                        "https://stat.hel.fi/pxweb/fi/Aluesarjat/"
                        "Aluesarjat__rak__ratuo/alu_ratuo_039n.px/"
                    ),
                ),
                Resource(
                    id="r2",
                    name="wms",
                    format="WMS",
                    url="https://geoserver.lounaistieto.fi:80/geoserver/varely/ows",
                ),
                Resource(
                    id="r3",
                    name="koskematon",
                    format="CSV",
                    url="https://example.test/data.csv",
                ),
            ],
        )
        urlit = [r.url for r in ds.resources]
        assert urlit[0] == (
            "https://stat.hel.fi/api/v1/fi/Aluesarjat/rak/ratuo/alu_ratuo_039n.px"
        )
        assert urlit[1] == "https://geoserver.lounaistieto.fi/geoserver/varely/ows"
        assert urlit[2] == "https://example.test/data.csv", "toimivaa URL:ia ei saa muuttaa"

    def test_resurssiton_datasetti_ei_kaada(self) -> None:
        import aura.server  # noqa: F401
        from aura.harvesters.base import BaseHarvester

        class Testiharvesteri(BaseHarvester):
            name = "testi"
            description = "testi"
            url = "https://example.test"

            async def harvest(self) -> int:
                return 0

        ds = Testiharvesteri(conn=None)._make_dataset(id="d1", name="d1", title="T")
        assert ds.resources == []
