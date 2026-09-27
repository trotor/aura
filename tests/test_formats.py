"""Formaatin päättely URL:sta ja sen käyttö CKAN-keruussa ja kyselyssä.

Ulkoinen arvio 27.9.2026: SYKE:n 511 resurssilla formaatti oli tyhjä, 75
niistä WFS-palveluita — ja kaikkien 644 aineiston ``title_fi`` oli tyhjä.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.database import init_db
from aura.formats import infer_format, resource_format
from aura.harvesters.avoindata import AvoindataHarvester
from aura.harvesters.syke import SykeHarvester
from aura.preview import _pick_resource
from aura.server import mcp  # noqa: F401 — tools-paketti tuodaan palvelimen kautta
from aura.tools.source import _protocol


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs", "WFS"),
        ("https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs/", "WFS"),
        ("https://paikkatiedot.ymparisto.fi/geoserver/syke_x/wms", "WMS"),
        ("https://x.fi/ows?SERVICE=WFS&request=GetCapabilities", "WFS"),
        ("https://x.fi/ows?service=wms", "WMS"),
        ("https://x.fi/lataus/aineisto.zip", "ZIP"),
        ("https://x.fi/data/tilasto.CSV", "CSV"),
        ("https://x.fi/api/data.json", "JSON"),
        ("https://x.fi/api/data.geojson", "GEOJSON"),
        ("https://x.fi/t/huhtikuu-2022-laaja.xlsx", "XLSX"),
        ("https://x.fi/t/tilastot2025.xls", "XLS"),
        # Ei arvata: sivu, katalogilinkki tai tuntematon pääte.
        ("https://www.syke.fi/avointieto", ""),
        ("https://paituli.csc.fi/download.html?data_id=luke_vmi", ""),
        ("https://x.fi/wfs-ohje.html", ""),
        ("", ""),
    ],
)
def test_infer_format(url: str, expected: str) -> None:
    assert infer_format(url) == expected


def test_katalogin_oma_formaatti_voittaa() -> None:
    assert resource_format({"format": "shp", "url": "https://x.fi/a/wfs"}) == "SHP"
    assert resource_format({"format": "", "url": "https://x.fi/a/wfs"}) == "WFS"
    assert resource_format({"format": None, "url": "https://x.fi/a.csv"}) == "CSV"


def test_protocol_ja_resurssivalinta_formaatittomalle_wfs_resurssille() -> None:
    resources = [
        {"format": "ZIP", "url": "https://x.fi/a.zip"},
        {"format": "WMS", "url": "https://x.fi/geoserver/ps/wms"},
        {"format": "", "url": "https://x.fi/geoserver/ps/wfs"},
    ]
    picked = _pick_resource(resources)
    assert picked is resources[2]
    assert _protocol(resource_format(picked), picked["url"], {}, "ckan") == "wfs"
    assert _pick_resource(resources, format_hint="WFS") is resources[2]


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


RAW = {
    "id": "{C8FC4A42-A2C3-40C4-92CD-2299C688514E}",
    "name": "luonnonsuojelu-ja-eramaa-alueet",
    "title": "Luonnonsuojelu- ja erämaa-alueet",
    "notes": "Valtion ja yksityisten maiden luonnonsuojelualueet sekä erämaa-alueet.",
    "organization": {"id": "syke", "name": "syke", "title": "SYKE"},
    "resources": [
        {"id": "r-zip", "name": "Lataus", "format": "ZIP", "url": "https://x.fi/a.zip"},
        {
            "id": "r-wfs",
            "name": "SuojellutAlueet WFS-latauspalvelu",
            "format": "",
            "url": "https://paikkatiedot.ymparisto.fi/geoserver/inspire_ps/wfs",
        },
    ],
}


def test_syke_titteli_ja_kuvaus_suomeksi_ja_formaatti_urlista() -> None:
    ds = SykeHarvester(conn=_memory_db())._to_dataset(RAW)
    assert ds.title_fi == "Luonnonsuojelu- ja erämaa-alueet"
    assert ds.notes_fi.startswith("Valtion ja yksityisten")
    assert [r.format for r in ds.resources] == ["ZIP", "WFS"]


def test_kaannos_voittaa_eika_kielta_oleteta_ilman_asetusta() -> None:
    raw = {**RAW, "title_translated": {"fi": "Suojelualueet", "en": "Protected areas"}}
    ds = SykeHarvester(conn=_memory_db())._to_dataset(raw)
    assert ds.title_fi == "Suojelualueet"
    # avoindata.fi:llä kieli ei ole tiedossa: otsikkoa ei kopioida.
    ds2 = AvoindataHarvester(conn=_memory_db())._to_dataset(RAW)
    assert ds2.title_fi == ""
    # Formaatti päätellään silti kaikille CKAN-lähteille.
    assert ds2.resources[1].format == "WFS"


@pytest.mark.asyncio
async def test_syke_harvest_tallentaa_taydennetyt_kentat() -> None:
    conn = _memory_db()
    h = SykeHarvester(conn=conn)
    resp = MagicMock()
    resp.json.return_value = {"result": {"count": 1, "results": [RAW]}}
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)
    with (
        patch.object(h, "_make_client") as make,
        patch.object(h, "_reconcile", AsyncMock(return_value=0)),
    ):
        make.return_value.__aenter__ = AsyncMock(return_value=client)
        make.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await h.harvest() >= 1
    row = conn.execute("SELECT title_fi FROM datasets WHERE id = ?", (RAW["id"],)).fetchone()
    assert row[0] == "Luonnonsuojelu- ja erämaa-alueet"
    fmts = {
        r[0]
        for r in conn.execute("SELECT format FROM resources WHERE dataset_id = ?", (RAW["id"],))
    }
    assert "WFS" in fmts
