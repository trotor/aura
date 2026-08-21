"""Testit Traficomin tilastotietokannan harvesterille."""

import sqlite3

from aura.database import init_db
from aura.harvesters import HARVESTERS
from aura.harvesters.pxweb import PxWebHarvester
from aura.harvesters.traficom import TraficomHarvester
from aura.harvesters.traficom_tilastot import TraficomTilastotHarvester


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _harvester() -> TraficomTilastotHarvester:
    return TraficomTilastotHarvester(conn=_memory_db())


class TestConfig:
    def test_inherits_pxweb(self):
        assert issubclass(TraficomTilastotHarvester, PxWebHarvester)

    def test_registered(self):
        assert HARVESTERS["traficom-tilastot"] is TraficomTilastotHarvester

    def test_points_at_statistics_database(self):
        h = _harvester()
        assert h.pxweb_base_url == "https://trafi2.stat.fi/PXWeb/api/v1"
        assert h.root_path == "TraFi"

    def test_separate_source_from_odata_harvester(self):
        """Kaksi eri Traficom-rajapintaa, kaksi eri lähdettä.

        OData-harvester tuo rekisteridatan, tämä tilastot. Sama ``source``
        sulauttaisi ne yhdeksi eikä kumpaakaan voisi harvestoida erikseen.
        """
        assert TraficomTilastotHarvester.name != TraficomHarvester.name

    def test_id_prefix_does_not_collide_with_odata(self):
        """Tunnisteiden etuliitteet eivät saa mennä päällekkäin.

        OData-puolella id on ``traficom-<entity>``. Jos tämä käyttäisi samaa
        etuliitettä, samanniminen taulu ylikirjoittaisi rekisterin.
        """
        assert TraficomTilastotHarvester.dataset_id_prefix == "trafi"
        assert TraficomHarvester.name == "traficom"


class TestDatasets:
    def test_table_becomes_dataset(self):
        h = _harvester()
        item = {"id": "11j2.px", "text": "Uudet myönnetyt ilmailulupakirjat",
                "updated": "2026-06-08T16:03:43"}
        ds = h._table_to_dataset(item, "TraFi/Ilmailulupakirjat",
                                 "https://trafi2.stat.fi/PXWeb/api/v1/fi/"
                                 "TraFi/Ilmailulupakirjat/")
        assert ds.id == "trafi-11j2.px"
        assert ds.source == "traficom-tilastot"
        assert ds.organization_title == "Liikenne- ja viestintävirasto Traficom"

    def test_web_url_is_browsable(self):
        """Selainosoite kaksoisalaviivoilla — muuten 404."""
        h = _harvester()
        item = {"id": "11j2.px", "text": "Taulu", "updated": ""}
        ds = h._table_to_dataset(item, "TraFi/Ilmailulupakirjat",
                                 "https://example.com/api/")
        web = next(r.url for r in ds.resources if r.format == "HTML")
        assert web.endswith("/fi/TraFi/TraFi__Ilmailulupakirjat/11j2.px")

    def test_folder_becomes_keyword(self):
        h = _harvester()
        assert h._path_to_keywords("TraFi/Ilmailulupakirjat") == ["Ilmailulupakirjat"]
