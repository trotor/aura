"""Testit probe-komennon pinnalle.

infer-schemas jää aliakseksi: vanha nimi ei saa kadota käsistä, mutta uusi
nimi kertoo mitä komento tekee. probe-sizes on eri komento (koon mittaus)
eikä siihen kosketa.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, patch

from aura.cli import build_parser
from aura.database import init_db
from aura.probe import format_probe_summary


def test_probe_komento_on_olemassa() -> None:
    parser = build_parser()
    args = parser.parse_args(["probe", "--limit", "5", "--format", "WFS"])
    assert args.command == "probe"
    assert args.limit == 5
    assert args.format == "WFS"

    assert args.max_age_days == 0


def test_max_age_days_parsittu() -> None:
    """--max-age-days on peritty briefistä lippu — sen on vastaanotettava arvo.

    Ilman tätä testiä lippu voisi jäädä "kuolleeksi": parseri hyväksyisi sen,
    mutta mikään ei koskaan lukisi arvoa.
    """
    parser = build_parser()
    args = parser.parse_args(["probe", "--max-age-days", "7"])
    assert args.max_age_days == 7


def test_infer_schemas_on_alias() -> None:
    parser = build_parser()
    args = parser.parse_args(["infer-schemas", "--limit", "5"])
    assert args.command == "infer-schemas"


def test_probe_sizes_sailyy_erillisena() -> None:
    parser = build_parser()
    args = parser.parse_args(["probe-sizes"])
    assert args.command == "probe-sizes"


def test_yhteenveto_kertoo_epaonnistumiset() -> None:
    teksti = format_probe_summary({"ok": 12, "http_error": 3, "timeout": 1})
    assert "12" in teksti and "3" in teksti
    assert "http_error" in teksti or "virhe" in teksti.lower()


def test_tyhja_ajo_sanotaan_aaneen() -> None:
    assert format_probe_summary({}).strip() != ""


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_probe_dry_run_valittaa_max_age_days_select_targets_lle() -> None:
    """--max-age-days on kuljettava argparsesta select_targets():iin asti.

    Ilman tätä testiä lippu näyttäisi toimivalta (parseri hyväksyy sen) muttei
    tekisi mitään — juuri se vikaluokka jonka takia tämä parametri lisättiin.
    """
    conn = _memory_db()

    with (
        patch("aura.database.get_connection", return_value=conn),
        patch("aura.probe.select_targets", return_value=[]) as mock_select,
    ):
        from aura.cli import main

        with patch("sys.argv", ["aura", "probe", "--dry-run", "--max-age-days", "7"]):
            main()

    assert mock_select.call_args.kwargs["max_age_days"] == 7


def test_probe_ajo_valittaa_max_age_days_run_probelle() -> None:
    """Sama vaatimus ei-dry-run-haaralle: run_probe():n on saatava max_age_days."""
    conn = _memory_db()

    with (
        patch("aura.database.get_connection", return_value=conn),
        patch("aura.probe.run_probe", AsyncMock(return_value={})) as mock_run,
    ):
        from aura.cli import main

        with patch("sys.argv", ["aura", "probe", "--max-age-days", "3"]):
            main()

    assert mock_run.call_args.kwargs["max_age_days"] == 3

