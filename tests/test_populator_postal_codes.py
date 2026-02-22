"""Testit PostalCodePopulator-luokalle."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import run_migrations
from aura.populators.postal_codes import PostalCodePopulator, _titlecase


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


# Simuloitu PCF-data (latin-1, fixed-width, 220 merkkiä/rivi)
# Kentät: PONOT(5)+pvm(8)+koodi(5)+nimi_fi(30)+nimi_sv(30)+lyh_fi(12)+lyh_sv(12)
#         +voimassa(8)+tyyppi(1)+alue(5)+alue_fi(30)+alue_sv(30)+kunta(3)+kunta_fi(20)+kunta_sv(20)+kieli(1)
SAMPLE_PCF_LINES = (
    "PONOT2026022100100HELSINKI                      HELSINGFORS                   "
    "HKI         HFORS       198810011FI1B1Helsinki-Uusimaa              "
    "Helsingfors-Nyland            091Helsinki            Helsingfors         2\n"
    "PONOT2026022102760ESPOO                         ESBO                          "
    "                        199608291FI1B1Helsinki-Uusimaa              "
    "Helsingfors-Nyland            049Espoo               Esbo                2\n"
    "PONOT2026022133100TAMPERE                       TAMMERFORS                    "
    "TRE         TFORS       198601011FI1C2Pirkanmaa                     "
    "Birkaland                     837Tampere             Tammerfors          2\n"
)

SAMPLE_DIR_HTML = """
<html><body>
<a href="PCF_20260220.dat">PCF_20260220.dat</a>
<a href="PCF_20260221.dat">PCF_20260221.dat</a>
<a href="BAF_20260221.dat">BAF_20260221.dat</a>
</body></html>
"""


def _make_mock_response(
    content: str, *, is_binary: bool = False
) -> MagicMock:
    resp = MagicMock()
    resp.text = content
    resp.content = content.encode("latin-1") if is_binary else content.encode()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    return resp


def _setup_mock_client() -> AsyncMock:
    client = AsyncMock()

    async def mock_get(url: str, **kwargs: object) -> MagicMock:
        if "unzip/" in url and url.endswith(".dat"):
            return _make_mock_response(SAMPLE_PCF_LINES, is_binary=True)
        if "unzip" in url:
            return _make_mock_response(SAMPLE_DIR_HTML)
        return _make_mock_response("")

    client.get = mock_get
    return client


class TestPostalCodePopulatorConfig:
    def test_name(self) -> None:
        p = PostalCodePopulator(conn=_memory_db())
        assert p.name == "postal_codes"

    def test_description(self) -> None:
        p = PostalCodePopulator(conn=_memory_db())
        assert "postinumero" in p.description.lower()


class TestPostalCodePopulate:
    @pytest.mark.asyncio
    async def test_populate_returns_count(self) -> None:
        p = PostalCodePopulator(conn=_memory_db())
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await p.populate()

        assert count == 3

    @pytest.mark.asyncio
    async def test_populate_writes_to_db(self) -> None:
        conn = _memory_db()
        p = PostalCodePopulator(conn=conn)
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        rows = conn.execute(
            "SELECT * FROM ref_postal_codes ORDER BY code"
        ).fetchall()
        assert len(rows) == 3

        # Helsinki
        hki = conn.execute(
            "SELECT * FROM ref_postal_codes WHERE code = '00100'"
        ).fetchone()
        assert hki["name_fi"] == "Helsinki"
        assert hki["name_sv"] == "Helsingfors"
        assert hki["municipality_code"] == "091"

        # Espoo
        espoo = conn.execute(
            "SELECT * FROM ref_postal_codes WHERE code = '02760'"
        ).fetchone()
        assert espoo["name_fi"] == "Espoo"
        assert espoo["name_sv"] == "Esbo"
        assert espoo["municipality_code"] == "049"

    @pytest.mark.asyncio
    async def test_populate_updates_metadata(self) -> None:
        conn = _memory_db()
        p = PostalCodePopulator(conn=conn)
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()

        assert p.is_populated()
        row = conn.execute(
            "SELECT * FROM ref_metadata WHERE name = 'postal_codes'"
        ).fetchone()
        assert row["record_count"] == 3
        assert row["version"] == "20260221"

    @pytest.mark.asyncio
    async def test_populate_idempotent(self) -> None:
        conn = _memory_db()
        p = PostalCodePopulator(conn=conn)
        mock_client = _setup_mock_client()

        with patch.object(p, "_make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)
            await p.populate()
            await p.populate()

        count = conn.execute(
            "SELECT COUNT(*) FROM ref_postal_codes"
        ).fetchone()[0]
        assert count == 3


class TestFindLatestPcfUrl:
    @pytest.mark.asyncio
    async def test_finds_latest(self) -> None:
        p = PostalCodePopulator(conn=_memory_db())
        mock_client = _setup_mock_client()
        url = await p._find_latest_pcf_url(mock_client)
        assert url.endswith("PCF_20260221.dat")

    @pytest.mark.asyncio
    async def test_raises_on_empty(self) -> None:
        p = PostalCodePopulator(conn=_memory_db())
        client = AsyncMock()
        resp = _make_mock_response("<html>no files</html>")
        client.get = AsyncMock(return_value=resp)

        with pytest.raises(RuntimeError, match="ei löytynyt"):
            await p._find_latest_pcf_url(client)


class TestTitlecase:
    def test_simple(self) -> None:
        assert _titlecase("HELSINKI") == "Helsinki"

    def test_hyphenated(self) -> None:
        assert _titlecase("PEDERSÖRE") == "Pedersöre"

    def test_compound(self) -> None:
        assert _titlecase("MÄNTTÄ-VILPPULA") == "Mänttä-Vilppula"

    def test_empty(self) -> None:
        assert _titlecase("") == ""

    def test_already_titlecase(self) -> None:
        assert _titlecase("Helsinki") == "Helsinki"
