"""Harvester CSC:n PaItuli-paikkatietopalvelulle."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

PAITULI_BASE = "https://paituli.csc.fi/geoserver"


class PaituliHarvester(StaticHarvester):
    """Kerää CSC PaItuli-palvelun paikkatietoaineistot.

    PaItuli tarjoaa laajan valikoiman suomalaisia paikkatietoaineistoja
    tutkimus- ja opetuskäyttöön. 628 WMS-tasoa GeoServer-palvelusta.
    """

    name = "paituli"
    description = "CSC PaItuli — tutkimuksen paikkatietoaineistot"
    url = "https://paituli.csc.fi"
    org_id = "csc"
    org_name = "csc"
    org_title = "CSC — Tieteen tietotekniikan keskus"
    default_update_frequency = "vuosittain"

    datasets_config = [
        {
            "id": "paituli-luke-metsavarat",
            "title": "LUKE metsävaratiedot (PaItuli)",
            "notes_fi": (
                "Luonnonvarakeskuksen metsävaratiedot: puuston hiilivarasto,"
                " tilavuus, biomassa ja kasvu. DTW-kosteusindeksi."
                " 384 WMS-tasoa."
            ),
            "keywords_fi": [
                "metsä", "hiilivarasto", "biomassa", "puusto", "DTW",
            ],
            "estimated_size_bytes": 50 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{PAITULI_BASE}/wms"},
                {"format": "WFS", "url": f"{PAITULI_BASE}/wfs"},
            ],
        },
        {
            "id": "paituli-mml-kartat",
            "title": "MML historialliset karttasarjat (PaItuli)",
            "notes_fi": (
                "Maanmittauslaitoksen topografiset karttasarjat"
                " eri vuosilta ja mittakaavassa. 134 WMS-tasoa."
            ),
            "keywords_fi": [
                "topografinen kartta", "peruskartta",
                "historiallinen kartta", "MML",
            ],
            "estimated_size_bytes": 30 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{PAITULI_BASE}/wms"},
            ],
        },
        {
            "id": "paituli-tilastokeskus",
            "title": "Tilastokeskuksen ruutuaineistot (PaItuli)",
            "notes_fi": (
                "Tilastoruutuaineistot eri vuosilta: väestö,"
                " kunnalliset avainluvut, työpaikat. 73 WMS-tasoa."
            ),
            "keywords_fi": [
                "tilastoruutu", "väestö", "avainluvut", "ruutudata",
            ],
            "estimated_size_bytes": 5 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{PAITULI_BASE}/wms"},
                {"format": "WFS", "url": f"{PAITULI_BASE}/wfs"},
            ],
        },
        {
            "id": "paituli-corine",
            "title": "CORINE maanpeiteaineisto (PaItuli)",
            "notes_fi": (
                "Euroopan ympäristökeskuksen CORINE Land Cover"
                " -maanpeiteluokitus Suomessa."
            ),
            "keywords_fi": [
                "CORINE", "maanpeite", "maankaytto", "land cover",
            ],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{PAITULI_BASE}/wms"},
                {"format": "WFS", "url": f"{PAITULI_BASE}/wfs"},
            ],
        },
        {
            "id": "paituli-dvv-osoitteet",
            "title": "DVV osoitetiedot (PaItuli)",
            "notes_fi": (
                "Digi- ja väestötietoviraston osoiterekisterin"
                " paikkatietoaineisto eri vuosilta."
            ),
            "keywords_fi": ["osoite", "osoiterekisteri", "DVV"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{PAITULI_BASE}/wms"},
                {"format": "WFS", "url": f"{PAITULI_BASE}/wfs"},
            ],
        },
    ]
