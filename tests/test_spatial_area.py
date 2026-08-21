"""Testit aluerajauksen ratkaisulle ja lehtihierarkialle (#146).

``_resolve_area`` on yksi kohta joka kääntää agentin antaman alueen
EPSG:3067-bbox:ksi: kunta, karttalehti tai raaka bbox. Tunnistus tehdään
kannasta hakemalla, ei merkkijonoa arvaamalla — kuntien ja lehtitunnusten
muodot menisivät ennemmin tai myöhemmin päällekkäin.

Virheiden on kerrottava syy. Hiljaa ohitettu aluerajaus näyttäisi
onnistuneelta kyselyltä väärältä alueelta, mikä on pahin mahdollinen
lopputulos: vastaus näyttää oikealta mutta koskee väärää paikkaa.
"""

from __future__ import annotations

import sqlite3

import pytest

import aura.server as _server
from aura.database import init_db
from aura.tools.spatial import CRS, _resolve_area, find_map_sheets, map_sheet


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
        "INSERT INTO ref_municipalities (code, name_fi, name_sv)"
        " VALUES ('992','Bbox-puuttuu','-')"
    )
    # Hierarkia on aukollinen: utm100 (K23) puuttuu kannasta kokonaan,
    # joten vanhempi on haettava pisimpänä olemassa olevana prefiksinä.
    for sheet in (
        ("K2", "utm200", 400000, 6900000, 592000, 6996000),
        ("K231", "utm50", 500000, 6930000, 548000, 6954000),
        ("K2311", "utm25", 500000, 6930000, 512000, 6936000),
        ("K2311A", "utm10", 500000, 6930000, 506000, 6933000),
        ("K2311B", "utm10", 506000, 6930000, 512000, 6933000),
        ("K232", "utm50", 548000, 6930000, 596000, 6954000),
    ):
        c.execute(
            "INSERT INTO ref_map_sheets"
            " (id, scale, min_x, min_y, max_x, max_y, centroid_x, centroid_y)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (*sheet, (sheet[2] + sheet[4]) / 2, (sheet[3] + sheet[5]) / 2),
        )
    c.commit()
    monkeypatch.setattr(_server, "_get_conn", lambda ctx=None: c)
    return c


class TestResolveAreaBbox:
    def test_raaka_bbox_kelpaa(self, conn: sqlite3.Connection) -> None:
        bbox, label = _resolve_area(conn, "500000,6930000,512000,6936000")
        assert bbox == (500000.0, 6930000.0, 512000.0, 6936000.0)
        assert "bbox" in label.lower()

    def test_crs_paate_hyvaksytaan(self, conn: sqlite3.Connection) -> None:
        """Muiden työkalujen tuloste kantaa koordinaatiston mukanaan."""
        bbox, _ = _resolve_area(conn, f"500000,6930000,512000,6936000,{CRS}")
        assert bbox == (500000.0, 6930000.0, 512000.0, 6936000.0)

    def test_vaara_koordinaatisto_hylataan(self, conn: sqlite3.Connection) -> None:
        bbox, msg = _resolve_area(conn, "24.9,60.1,25.1,60.3,EPSG:4326")
        assert bbox is None
        assert "EPSG:4326" in msg and "ei kelpaa" in msg

    def test_epakelpo_bbox_saa_bbox_virheen(self, conn: sqlite3.Connection) -> None:
        """Kolmiosainen luku on selvästi bbox-yritys, ei kunnan nimi."""
        bbox, msg = _resolve_area(conn, "500000,6930000,512000")
        assert bbox is None
        assert "bbox" in msg.lower()
        assert "kunta" not in msg.lower()


class TestResolveAreaKarttalehti:
    def test_lehtitunnus_ratkeaa(self, conn: sqlite3.Connection) -> None:
        bbox, label = _resolve_area(conn, "K2311")
        assert bbox == (500000.0, 6930000.0, 512000.0, 6936000.0)
        assert "K2311" in label

    def test_kirjainkoolla_ei_valia(self, conn: sqlite3.Connection) -> None:
        bbox, _ = _resolve_area(conn, "k2311a")
        assert bbox == (500000.0, 6930000.0, 506000.0, 6933000.0)


class TestResolveAreaKunta:
    def test_nimi_ratkeaa(self, conn: sqlite3.Connection) -> None:
        bbox, label = _resolve_area(conn, "Kuopio")
        assert bbox == (494427.8, 6940948.7, 588843.3, 7030987.9)
        assert "Kuopio" in label and "297" in label

    def test_kuntakoodi_ratkeaa(self, conn: sqlite3.Connection) -> None:
        bbox, label = _resolve_area(conn, "297")
        assert bbox is not None
        assert "Kuopio" in label

    def test_puuttuva_bbox_ohjaa_populaattoriin(self, conn: sqlite3.Connection) -> None:
        bbox, msg = _resolve_area(conn, "Bbox-puuttuu")
        assert bbox is None
        assert "populate_reference" in msg

    def test_tuntematon_kertoo_mita_yritettiin(self, conn: sqlite3.Connection) -> None:
        bbox, msg = _resolve_area(conn, "Atlantis")
        assert bbox is None
        assert "Atlantis" in msg
        assert "kunta" in msg.lower() and "karttaleh" in msg.lower()


class TestMapSheetHierarkia:
    def test_nayttaa_vanhemman_ja_lapset(self, conn: sqlite3.Connection) -> None:
        out = map_sheet("K2311")
        assert "K231" in out
        assert "K2311A" in out and "K2311B" in out

    def test_vanhempi_ohittaa_puuttuvan_tason(self, conn: sqlite3.Connection) -> None:
        """K231:n vanhempi on K2, koska utm100-taso (K23) puuttuu kannasta."""
        out = map_sheet("K231")
        rivi = next(r for r in out.splitlines() if "vanhempi" in r.lower())
        assert "K2" in rivi
        assert "K23 " not in rivi

    def test_lapsiksi_vain_seuraava_taso(self, conn: sqlite3.Connection) -> None:
        """K2:n lapsia ovat utm50-lehdet, eivät kaikki alemmat tasot."""
        out = map_sheet("K2")
        lapset = next(r for r in out.splitlines() if "lapset" in r.lower())
        assert "K231" in lapset and "K232" in lapset
        assert "K2311" not in lapset

    def test_alimmalla_tasolla_ei_lapsia(self, conn: sqlite3.Connection) -> None:
        out = map_sheet("K2311A")
        assert "lapset" not in out.lower()


class TestFindMapSheetsMunicipality:
    def test_kunnan_nimi_suoraan(self, conn: sqlite3.Connection) -> None:
        """Ilman tätä agentti tarvitsee välikutsun municipality_bbox:iin."""
        out = find_map_sheets("utm50", municipality="Kuopio")
        assert "K231" in out and "K232" in out

    def test_tuntematon_kunta_kertoo_syyn(self, conn: sqlite3.Connection) -> None:
        out = find_map_sheets("utm50", municipality="Atlantis")
        assert "Atlantis" in out
        assert "Ei karttalehtiä" not in out

    def test_kunta_kelpaa_ainoaksi_suodattimeksi(self, conn: sqlite3.Connection) -> None:
        out = find_map_sheets("utm50", municipality="Kuopio")
        assert "Anna vähintään yksi suodatin" not in out
