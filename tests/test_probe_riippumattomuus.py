"""``aura.probe`` ei saa riippua MCP-palvelimesta.

Ennen tätä testiä ``src/aura/probe/tabular.py`` sisälsi rivin
``import aura.server  # noqa: F401 — resolve circular import before tools``,
ja se oli **kantava eikä kosmeettinen**: poistettuna ``import aura.probe``
kaatui virheeseen ``ImportError: cannot import name 'harvest' from partially
initialized module 'aura.tools.admin'``.

Solmu ei ollut siellä missä miltä näytti. ``aura/tools/preview.py`` ja
``aura/tools/schema.py`` eivät kumpikaan tuo ``aura.server``:iä — jälkimmäisen
docstring sanoo sen suoraan. Ne kuitenkin asuivat paketissa, jonka
``__init__.py`` tuo *kaikki* työkalumoduulit, ja niistä kymmenen tuo
``aura.server``:in. Alimoduulin tuonti ajaa aina paketin ``__init__``:n, joten
``from aura.tools.preview import …`` veti mukanaan koko palvelimen.

Seuraus oli mitattava: ``import aura.probe`` latasi 1 426 moduulia ja kesti
~0,46 s, vaikka probe ei käytä palvelimesta mitään.

Vika oli myös **järjestysherkkä**, mikä on pahin osa: ``pytest
tests/test_probe_cli.py`` yksinään kaatui, kun taas koko paketin ajo meni
läpi, koska aakkosjärjestyksessä aiemmat testit latasivat ``aura.server``:in
ensin ja piilottivat virheen.

Testi ajetaan **omassa prosessissa**, koska ``sys.modules`` on jaettu:
saman prosessin sisällä jokin toinen testi on jo voinut ladata palvelimen,
jolloin tarkistus menisi läpi väärästä syystä.
"""

from __future__ import annotations

import subprocess
import sys

#: Moduulit joiden ei kuulu latautua pelkästä probe-tuonnista.
KIELLETYT = ("aura.server", "fastmcp")


def _tuo_omassa_prosessissa(koodi: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", koodi], capture_output=True, text=True, timeout=120
    )


def test_probe_ei_lataa_mcp_palvelinta() -> None:
    """Ydinpaketti ei saa vetää mukanaan MCP-palvelinta."""
    tulos = _tuo_omassa_prosessissa(
        "import sys, aura.probe\n"
        f"vuodot = [m for m in {KIELLETYT!r} if m in sys.modules]\n"
        "print(','.join(vuodot))"
    )
    assert tulos.returncode == 0, tulos.stderr
    vuotaneet = tulos.stdout.strip()
    assert not vuotaneet, f"aura.probe latasi: {vuotaneet}"


def test_probe_tabular_toimii_yksinaan() -> None:
    """Juuri tämä tuonti kaatui ennen korjausta.

    ``aura.probe.tabular`` tuo esikatselu- ja skeema-apurit. Jos ne ovat
    paketissa joka rekisteröi MCP-työkaluja, tuonti kaatuu osittain
    alustettuun moduuliin.
    """
    tulos = _tuo_omassa_prosessissa(
        "from aura.probe.tabular import probe\nprint('ok')"
    )
    assert tulos.returncode == 0, tulos.stderr
    assert tulos.stdout.strip() == "ok"


def test_probe_apurit_eivat_riipu_tools_paketista() -> None:
    """Apurit ovat omissa moduuleissaan, eivät työkalupaketin sisällä.

    Sijainti on se mikä ratkaisee: paketin ``__init__`` ajetaan aina, joten
    palvelinvapaakin moduuli vetää palvelimen mukanaan jos se asuu väärässä
    paketissa. Tämä testi kiinnittää sijainnin, ei vain lopputulosta.
    """
    tulos = _tuo_omassa_prosessissa(
        "import sys\n"
        "import aura.preview, aura.schema_infer\n"
        "print('aura.tools' in sys.modules)"
    )
    assert tulos.returncode == 0, tulos.stderr
    assert tulos.stdout.strip() == "False", "apurit vetivät tools-paketin mukanaan"
