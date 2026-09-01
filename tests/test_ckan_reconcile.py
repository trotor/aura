"""CKAN: hakuindeksi ei tunne kaikkia paketteja, ``package_list`` tuntee.

Mitattuna 1.9.2026 avoindata.suomi.fi:stä puuttui katalogista **214
pakettia**, joista 74 oli ``apiset``-tyyppisiä WFS/WMS-palveluita — mukaan
lukien koko Ahvenanmaa, Luomuksen palvelut ja avoimuusrekisteri. Yksikään
ei löytynyt kannasta millään slugilla tai otsikolla.

**Syy ei ole suodatus vaan indeksointi.** Ensimmäinen arvaus oli että
``package_search`` rajaa tyyppiin ``dataset`` ja että ``fq``-parametri
avaisi loput. Kokeiltuna se ei toimi::

    fq=+type:dataset             → 2 561
    fq=+type:apiset              →     0
    fq=+type:(dataset OR apiset) → 2 561

Nollat kertovat ettei kohteita ole hakuindeksissä lainkaan, joten mikään
kyselyparametri ei tuo niitä esiin. ``package_list`` palauttaa ne silti
(2 740 nimeä) ja ``package_show`` toimii yksittäin.

Vertailu lähteen omaan luetteloon on siksi sekä **korjaus** että
**regressiotarkistus**: aukko oli näkymätön nimenomaan siksi ettei mikään
verrannut harvestoitua siihen mitä lähde sanoo itsellään olevan.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.harvesters.avoindata import AvoindataHarvester

HAETTU = {
    "id": "id-haettu",
    "name": "haettu",
    "title": "Hakuindeksistä löytyvä",
    "organization": {"id": "o", "name": "o", "title": "Org"},
    "num_resources": 1,
    "resources": [{"id": "r1", "name": "a.csv", "format": "CSV", "url": "https://x/a.csv"}],
}

APISET = {
    "id": "id-apiset",
    "name": "aland-natura-2000-wms",
    "title": "Åland - Natura 2000 WMS",
    "type": "apiset",
    "organization": {"id": "o", "name": "o", "title": "Org"},
    "num_resources": 1,
    "resources": [{"id": "r2", "name": "wms", "format": "WMS", "url": "https://x/wms"}],
}

SHOWCASE = {
    "id": "id-showcase",
    "name": "sovellus",
    "title": "Jokin sovellus",
    "type": "showcase",
    "num_resources": 0,
    "resources": [],
}


def _kanta() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _client(package_list: list[str], naytettavat: dict[str, dict[str, Any]]) -> Any:
    """Mock joka reitittää vastauksen kutsutun päätteen mukaan."""
    kutsut: list[str] = []

    async def get(url: str, **kwargs: Any) -> Any:
        kutsut.append(url)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "package_list" in url:
            resp.json.return_value = {"success": True, "result": package_list}
        elif "package_show" in url:
            nimi = kwargs.get("params", {}).get("id", "")
            paketti = naytettavat.get(nimi)
            resp.json.return_value = (
                {"success": True, "result": paketti}
                if paketti
                else {"success": False}
            )
        else:  # package_search
            resp.json.return_value = {
                "success": True,
                "result": {"count": 1, "results": [HAETTU]},
            }
        return resp

    client = AsyncMock()
    client.get = AsyncMock(side_effect=get)
    client.kutsut = kutsut
    return client


async def _aja(h: AvoindataHarvester, client: Any) -> int:
    with patch.object(h, "_make_client") as mock_make:
        mock_make.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
        return await h.harvest()


class TestIndeksinUlkopuolisetLoytyvat:
    @pytest.mark.asyncio
    async def test_apiset_paatyy_kantaan(self) -> None:
        """Tämä on itse vika: 74 palvelua puuttui kokonaan."""
        conn = _kanta()
        h = AvoindataHarvester(conn=conn)
        client = _client(
            ["haettu", "aland-natura-2000-wms"], {"aland-natura-2000-wms": APISET}
        )
        maara = await _aja(h, client)

        nimet = {r[0] for r in conn.execute("SELECT name FROM datasets")}
        assert "aland-natura-2000-wms" in nimet, f"apiset puuttuu: {nimet}"
        assert maara == 2
        conn.close()

    @pytest.mark.asyncio
    async def test_resurssiton_ohitetaan(self) -> None:
        """``showcase`` on sovellus eikä aineisto — 101 kpl, 0 resurssia."""
        conn = _kanta()
        h = AvoindataHarvester(conn=conn)
        client = _client(["haettu", "sovellus"], {"sovellus": SHOWCASE})
        await _aja(h, client)

        nimet = {r[0] for r in conn.execute("SELECT name FROM datasets")}
        assert "sovellus" not in nimet
        conn.close()

    @pytest.mark.asyncio
    async def test_ei_ylimaaraisia_kutsuja_kun_luettelot_tasmaavat(self) -> None:
        """Kustannus on verrannollinen aukkoon, ei katalogin kokoon.

        Jos hakuindeksi tuntee kaiken, vertailu maksaa yhden ``package_list``
        -kutsun eikä yhtään ``package_show``:ta.
        """
        conn = _kanta()
        h = AvoindataHarvester(conn=conn)
        client = _client(["haettu"], {})
        await _aja(h, client)

        naytot = [u for u in client.kutsut if "package_show" in u]
        assert naytot == [], f"turhia package_show-kutsuja: {len(naytot)}"
        conn.close()


class TestVertailuEiSaaKaataaHarvestointia:
    @pytest.mark.asyncio
    async def test_package_listin_virhe_ei_hukkaa_haettua(self) -> None:
        """Vertailu on lisä, ei edellytys.

        Jos ``package_list`` kaatuu, hakuindeksistä saadut datasetit on jo
        tallennettu eikä niitä saa menettää.
        """
        conn = _kanta()
        h = AvoindataHarvester(conn=conn)

        async def get(url: str, **kwargs: Any) -> Any:
            if "package_list" in url:
                raise TimeoutError("ei vastausta")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "success": True,
                "result": {"count": 1, "results": [HAETTU]},
            }
            return resp

        client = AsyncMock()
        client.get = AsyncMock(side_effect=get)
        maara = await _aja(h, client)

        assert maara == 1
        nimet = {r[0] for r in conn.execute("SELECT name FROM datasets")}
        assert "haettu" in nimet
        conn.close()

    @pytest.mark.asyncio
    async def test_yksittaisen_naytto_virhe_ei_pysayta_muita(self) -> None:
        conn = _kanta()
        h = AvoindataHarvester(conn=conn)
        client = _client(
            ["haettu", "rikki", "aland-natura-2000-wms"],
            {"aland-natura-2000-wms": APISET},  # "rikki" palauttaa success=False
        )
        await _aja(h, client)

        nimet = {r[0] for r in conn.execute("SELECT name FROM datasets")}
        assert "aland-natura-2000-wms" in nimet
        conn.close()
