"""Testit paikkatietotyökalujen ketjutettavuudelle.

``municipality_bbox`` päättää tulosteensa kehotukseen syöttää bbox-arvo
``find_map_sheets(bbox=...)``-kutsuun. Arvo on muotoa
``minx,miny,maxx,maxy,EPSG:3067``, mutta ``find_map_sheets`` vaati
neliosaisen arvon ja hylkäsi viisiosaisen. Ohje siis neuvoi kutsun joka
ei toiminut — ja agentille tuo kehotus on ainoa vihje siitä miten
työkalut liittyvät toisiinsa.

Testit kiinnittävät molemmat suunnat: tuloste kelpaa syötteeksi, ja
väärä koordinaatisto hylätään äänekkäästi eikä ohiteta hiljaa.
"""

import sqlite3

import pytest

import aura.server as _server
from aura.database import init_db
from aura.tools.spatial import CRS, _strip_crs, find_map_sheets, municipality_bbox


@pytest.fixture
def conn(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.execute(
        "INSERT INTO ref_municipalities"
        " (code, name_fi, name_sv, min_x, min_y, max_x, max_y)"
        " VALUES ('297','Kuopio','Kuopio', 494427.8, 6940948.7, 588843.3, 7030987.9)"
    )
    c.execute(
        "INSERT INTO ref_map_sheets"
        " (id, scale, min_x, min_y, max_x, max_y, centroid_x, centroid_y)"
        " VALUES ('N522','utm50', 500000, 6930000, 548000, 6954000, 524000, 6942000)"
    )
    c.commit()
    monkeypatch.setattr(_server, "_get_conn", lambda ctx=None: c)
    return c


class TestStripCrs:
    def test_irrottaa_paatteen(self) -> None:
        assert _strip_crs("1,2,3,4,EPSG:3067") == ("1,2,3,4", "EPSG:3067")

    def test_ilman_paatetta_sailyy(self) -> None:
        assert _strip_crs("1,2,3,4") == ("1,2,3,4", None)

    def test_pienet_kirjaimet_normalisoidaan(self) -> None:
        """Muuten oikea koordinaatisto hylättäisiin kirjainkoon takia."""
        assert _strip_crs("1,2,3,4,epsg:3067")[1] == "EPSG:3067"


class TestKetju:
    """Tuloste on kelvollinen syöte seuraavaan kutsuun."""

    def test_municipality_bbox_syotettavissa_find_map_sheetsiin(
        self, conn: sqlite3.Connection
    ) -> None:
        tuloste = municipality_bbox("Kuopio")
        bbox = tuloste.split("bbox (WFS/WCS): ")[1].split("\n")[0].strip()
        assert bbox.endswith(CRS), "tuloste ei enää kanna koordinaatistoa"

        tulos = find_map_sheets("utm50", bbox=bbox)
        assert "N522" in tulos, tulos

    def test_find_map_sheets_oma_tuloste_kelpaa_takaisin(self, conn: sqlite3.Connection) -> None:
        """Lehden bbox on tarkennettava seuraavalle mittakaavatasolle."""
        eka = find_map_sheets("utm50", bbox=f"400000,6900000,600000,7000000,{CRS}")
        bbox = eka.split("bbox ")[1].split("\n")[0].strip()
        assert "N522" in find_map_sheets("utm50", bbox=bbox)

    def test_nelioisainen_bbox_toimii_yha(self, conn: sqlite3.Connection) -> None:
        assert "N522" in find_map_sheets("utm50", bbox="500000,6930000,548000,6954000")


class TestVaaraKoordinaatisto:
    """Hiljainen ohitus olisi pahin: WGS84-luvut eivät osu Suomen ruudukkoon."""

    def test_bbox_vaarassa_crssassa_hylataan(self, conn: sqlite3.Connection) -> None:
        tulos = find_map_sheets("utm50", bbox="24.9,60.1,25.1,60.3,EPSG:4326")
        assert "EPSG:4326" in tulos
        assert "ei kelpaa" in tulos

    def test_point_vaarassa_crssassa_hylataan(self, conn: sqlite3.Connection) -> None:
        tulos = find_map_sheets("utm50", point="24.9,60.1,EPSG:4326")
        assert "ei kelpaa" in tulos

    def test_virheilmoitus_ei_vaita_tyhjaa_tulosta(self, conn: sqlite3.Connection) -> None:
        """Tyhjä tulos näyttäisi 'ei dataa' -vastaukselta, ei virheeltä."""
        tulos = find_map_sheets("utm50", bbox="24.9,60.1,25.1,60.3,EPSG:4326")
        assert "Ei karttalehtiä" not in tulos


class TestPointKetju:
    def test_point_hyvaksyy_crs_paatteen(self, conn: sqlite3.Connection) -> None:
        assert "N522" in find_map_sheets("utm50", point=f"524000,6942000,{CRS}")
