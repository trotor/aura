"""Testit probe-komennon pinnalle.

infer-schemas jää aliakseksi: vanha nimi ei saa kadota käsistä, mutta uusi
nimi kertoo mitä komento tekee. probe-sizes on eri komento (koon mittaus)
eikä siihen kosketa.
"""

from __future__ import annotations

from aura.cli import build_parser
from aura.probe import format_probe_summary


def test_probe_komento_on_olemassa() -> None:
    parser = build_parser()
    args = parser.parse_args(["probe", "--limit", "5", "--format", "WFS"])
    assert args.command == "probe"
    assert args.limit == 5
    assert args.format == "WFS"


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
