"""Testit server-instructionsin kahdelle variantille (#137).

Remote-moodissa palvelin ei saa luvata agentille pääsyä paikalliseen
tiedostojärjestelmään: kontissa ei ole ``data/boundaries/*.gpkg``-tiedostoja,
joten niihin viittaava ohje tuottaa väärää tietoa jokaiselle liittyvälle
asiakkaalle.
"""

from __future__ import annotations

from aura.server import WRITE_TOOL_NAMES, build_instructions

# Paikallisen moodin ohje nojaa näihin — remotessa yksikään ei saa esiintyä.
_LOCAL_FS_MARKERS = (
    "data/boundaries",
    ".gpkg",
    "karttalehtijako",
    "kuntajako_1000k",
    "kuntajako_10k",
)


def test_local_instructions_mainitsee_rajausaineistot() -> None:
    """Lokaali stdio-ohje säilyy ennallaan — GPKG:t ovat siellä oikeasti."""
    text = build_instructions(readonly=False)
    for marker in _LOCAL_FS_MARKERS:
        assert marker in text, f"lokaalista ohjeesta puuttuu {marker!r}"


def test_remote_instructions_ei_viittaa_tiedostojarjestelmaan() -> None:
    """Hyväksymiskriteeri: readonly-ohje ei viittaa tiedostojärjestelmään."""
    text = build_instructions(readonly=True)
    for marker in _LOCAL_FS_MARKERS:
        assert marker not in text, f"remote-ohje lupaa yhä {marker!r}"


def test_remote_instructions_ohjaa_paikkatietotyokaluihin() -> None:
    """Poistetun ohjeen tilalle on tultava toimiva korvaaja.

    Nämä työkalut lukevat kannasta (``ref_municipalities``, ``map_sheets``),
    eivät GPKG-tiedostoista, joten ne toimivat myös remotessa.
    """
    text = build_instructions(readonly=True)
    for tool in ("municipality_bbox", "find_map_sheets", "map_sheet"):
        assert tool in text, f"remote-ohje ei mainitse työkalua {tool!r}"


def test_remote_instructions_ei_lupaa_poistettuja_tyokaluja() -> None:
    """Ohje ei saa kehottaa kutsumaan työkalua jota ei ole rekisteröity.

    ``save_session_findings`` gataan pois read-only-moodissa
    (``WRITE_TOOL_NAMES``), joten sen mainitseminen olisi sama vika
    pienemmässä mittakaavassa kuin GPKG-lupaus.
    """
    text = build_instructions(readonly=True)
    for name in WRITE_TOOL_NAMES:
        assert name not in text, f"remote-ohje mainitsee gatatun työkalun {name!r}"


def test_molemmat_variantit_sailyttavat_rajapintaohjeen() -> None:
    """query_data toimii remotessa, joten ohje säilyy molemmissa."""
    for readonly in (False, True):
        text = build_instructions(readonly=readonly)
        assert "RAJAPINTOJEN SUORA KÄYTTÖ" in text
        assert "query_data()" in text


def test_variantit_eroavat_toisistaan() -> None:
    assert build_instructions(readonly=True) != build_instructions(readonly=False)
