"""Testit POHTIVA-harvesterille (puolueohjelmat)."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

from aura.database import init_db
from aura.harvesters.pohtiva import (
    PARTY_ALIASES,
    PohtivaHarvester,
    parse_party_codes,
    parse_programmes,
)


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


PARTY_LIST_HTML = """
<main>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/KOK">Kansallinen kokoomus</a>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR">Vihreä liitto</a>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/SDP">SDP</a>
  <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat">Takaisin</a>
</main>
"""

# Rakenne kopioitu oikealta VIHR-sivulta: <tr> jää sulkematta.
PROGRAMME_HTML = """
<tbody>
  <tr>
     <td>
        <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR/1563">
        Aluevaaliohjelma 2025 - Arki ratkaisee
        </a>
     </td>
     <td>Vihre&auml; liitto</td>
     <td>2025</td>
     <td>vaaliohjelma</td>
     <td>FI</td>
  <tr>
     <td>
        <a href="https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR/1526">
        Elinkeinopoliittinen ohjelma
        </a>
     </td>
     <td>Vihre&auml; liitto</td>
     <td>2023</td>
     <td>erityisohjelma</td>
     <td>FI</td>
</tbody>
"""


class TestParsePartyCodes:
    def test_finds_codes(self) -> None:
        assert parse_party_codes(PARTY_LIST_HTML) == ["KOK", "SDP", "VIHR"]

    def test_ignores_list_page_itself(self) -> None:
        """Takaisin-linkki osoittaa listasivulle — se ei ole puoluekoodi."""
        assert "ohjelmalistat" not in parse_party_codes(PARTY_LIST_HTML)

    def test_empty_html_yields_nothing(self) -> None:
        assert parse_party_codes("<html></html>") == []


class TestParseProgrammes:
    def test_finds_both_programmes(self) -> None:
        assert len(parse_programmes(PROGRAMME_HTML)) == 2

    def test_extracts_all_fields(self) -> None:
        first = parse_programmes(PROGRAMME_HTML)[0]
        assert first["party"] == "VIHR"
        assert first["pid"] == "1563"
        assert first["title"] == "Aluevaaliohjelma 2025 - Arki ratkaisee"
        assert first["party_name"] == "Vihreä liitto"
        assert first["year"] == "2025"
        assert first["ptype"] == "vaaliohjelma"

    def test_unescapes_html_entities(self) -> None:
        """&auml; pitää muuttua ä:ksi."""
        assert parse_programmes(PROGRAMME_HTML)[0]["party_name"] == "Vihreä liitto"

    def test_malformed_html_does_not_crash(self) -> None:
        assert parse_programmes("<tbody><tr><td>rikki") == []


def _mock_client() -> AsyncMock:
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.rstrip("/").endswith("ohjelmalistat"):
            resp.text = PARTY_LIST_HTML
        else:
            resp.text = PROGRAMME_HTML
        return resp

    client.get = AsyncMock(side_effect=mock_get)
    return client


def _harvester(conn: sqlite3.Connection) -> PohtivaHarvester:
    """Harvesteri ilman pyyntöviivettä — testit eivät mene verkkoon."""
    h = PohtivaHarvester(conn=conn)
    h.request_delay = 0.0
    return h


async def _run(h: PohtivaHarvester) -> int:
    with patch.object(h, "_make_client") as mock_make:
        mock_make.return_value.__aenter__ = AsyncMock(return_value=_mock_client())
        mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
        return await h.harvest()


class TestHarvest:
    async def test_creates_dataset_per_programme(self) -> None:
        """3 puoluetta × 2 ohjelmaa = 6 aineistoa."""
        h = _harvester(_memory_db())
        assert await _run(h) == 6

    async def test_dataset_id_format(self) -> None:
        conn = _memory_db()
        await _run(_harvester(conn))

        row = conn.execute(
            "SELECT title_fi FROM datasets WHERE id = 'pohtiva-vihr-1563'"
        ).fetchone()
        assert row is not None
        assert row["title_fi"] == "Aluevaaliohjelma 2025 - Arki ratkaisee"

    async def test_licence_is_left_empty(self) -> None:
        """POHTIVA ei ilmoita lisenssiä — sitä ei saa keksiä."""
        conn = _memory_db()
        await _run(_harvester(conn))

        row = conn.execute(
            "SELECT license_id, license_title FROM datasets "
            "WHERE id = 'pohtiva-vihr-1563'"
        ).fetchone()
        assert row["license_id"] == ""
        assert row["license_title"] == ""

    async def test_resource_links_to_programme_page(self) -> None:
        conn = _memory_db()
        await _run(_harvester(conn))

        row = conn.execute(
            "SELECT url, format FROM resources WHERE dataset_id = 'pohtiva-vihr-1563'"
        ).fetchone()
        assert row["url"] == "https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/VIHR/1563"
        assert row["format"] == "HTML"

    async def test_keywords_include_party_and_type(self) -> None:
        conn = _memory_db()
        await _run(_harvester(conn))

        row = conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'pohtiva-vihr-1563'"
        ).fetchone()
        kw = row["keywords_fi"]
        assert "puolueohjelma" in kw
        assert "vaaliohjelma" in kw
        assert "Vihreä liitto" in kw


class TestPuolueenLyhenteet:
    """Vakiintunut lyhenne, jota POHTIVAn oma koodi ei anna.

    Mitattu 15.8.2026: kysely ``RKP`` löysi 9 ohjelmaa 167:stä, koska
    avainsanoina olivat vain ``SFP`` ja "Ruotsalainen kansanpuolue".
    Yhdeksän osumaa tulivat otsikoista jotka sattuivat sisältämään "RKP:n".
    """

    def test_sfp_saa_rkp_lyhenteen(self) -> None:
        assert "RKP" in PARTY_ALIASES["SFP"]

    def test_alias_paatyy_avainsanoihin(self) -> None:
        harvester = _harvester(_memory_db())
        harvester._store({
            "party": "SFP", "pid": "1", "title": "Vaaliohjelma",
            "party_name": "Ruotsalainen kansanpuolue", "year": "2025",
            "ptype": "vaaliohjelma", "lang": "fi",
        })
        row = harvester.conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'pohtiva-sfp-1'"
        ).fetchone()
        assert "RKP" in row["keywords_fi"]

    def test_pienet_kirjaimet_koodissa_kelpaavat(self) -> None:
        """Koodi tulee sivulta kirjainkoossa jota ei voi olettaa."""
        harvester = _harvester(_memory_db())
        harvester._store({
            "party": "sfp", "pid": "2", "title": "Ohjelma",
            "party_name": "Ruotsalainen kansanpuolue", "year": "",
            "ptype": "", "lang": "fi",
        })
        row = harvester.conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'pohtiva-sfp-2'"
        ).fetchone()
        assert "RKP" in row["keywords_fi"]

    def test_muut_puolueet_eivat_saa_ylimaaraisia(self) -> None:
        harvester = _harvester(_memory_db())
        harvester._store({
            "party": "VIHR", "pid": "3", "title": "Ohjelma",
            "party_name": "Vihreä liitto", "year": "", "ptype": "", "lang": "fi",
        })
        row = harvester.conn.execute(
            "SELECT keywords_fi FROM datasets WHERE id = 'pohtiva-vihr-3'"
        ).fetchone()
        assert "RKP" not in row["keywords_fi"]
