"""Harvester Ruokaviraston (Finnish Food Authority) aineistoille."""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

GEOSERVER_BASE = "https://inspire.ruokavirasto-awsa.com/geoserver"
GPKG_BASE = "https://inspire.ruokavirasto-awsa.com/geoserver"
AVOINTIETO_BASE = "https://avointieto.ruokavirasto.fi"

# --- A. INSPIRE-paikkatiedot (avoimet) ---

INSPIRE_TYPES: list[dict[str, Any]] = [
    {
        "id": "peltolohkorekisteri",
        "title": "Peltolohkorekisteri",
        "description": (
            "Maatalouden peltolohkojen rajat ja tunnistetiedot."
            " INSPIRE-yhteensopiva aineisto."
        ),
        "keywords": ["peltolohko", "maatalous", "INSPIRE", "Ruokavirasto"],
        "workspace": "inspire_plohko",
    },
    {
        "id": "maatalousmaa",
        "title": "Maatalousmaa",
        "description": (
            "Maatalouskäytössä oleva maa-ala."
            " Sisältää viljelykasvitiedot ja tukikelpoisuuden."
        ),
        "keywords": ["maatalousmaa", "viljelykasvit", "INSPIRE", "Ruokavirasto"],
        "workspace": "inspire_maatalousmaa",
    },
    {
        "id": "kasvulohkot",
        "title": "Kasvulohkot",
        "description": (
            "Maatalouden kasvulohkot viljelykasvitietoineen."
            " Lohkokohtaiset kasvilajit ja pinta-alat."
        ),
        "keywords": ["kasvulohko", "viljely", "INSPIRE", "Ruokavirasto"],
        "workspace": "inspire_kasvulohko",
    },
    {
        "id": "maisemapiirteet",
        "title": "Maisemapiirteet",
        "description": (
            "Maatalousympäristön maisemapiirteet: suojakaistat,"
            " pientareet ja luonnon monimuotoisuuskohteet."
        ),
        "keywords": ["maisemapiirre", "ympäristö", "INSPIRE", "Ruokavirasto"],
        "workspace": "inspire_maisemapiirre",
    },
]

INSPIRE_YEARS = list(range(2020, 2025))  # 2020–2024

# --- B. Avoin tieto -dashboardit (avoimet) ---

DASHBOARDS: list[dict[str, Any]] = [
    {
        "id": "elintarvikevalvonta",
        "title": "Elintarvikevalvonnan avoin tieto",
        "description": (
            "Ruokamyrkytysepidemiat, luomutoimijat ja"
            " elintarvikevalvonnan tulokset dashboardina."
        ),
        "keywords": ["elintarvikevalvonta", "ruokamyrkytys", "luomu", "Ruokavirasto"],
        "url": f"{AVOINTIETO_BASE}/elintarvikevalvonta",
    },
    {
        "id": "elainten-terveys",
        "title": "Eläinten terveyden avoin tieto",
        "description": (
            "Mikrobilääkeresistenssi, eläintaudit ja"
            " eläinten hyvinvointitiedot."
        ),
        "keywords": ["eläinterveys", "mikrobilääkeresistenssi", "eläintauti", "Ruokavirasto"],
        "url": f"{AVOINTIETO_BASE}/elainten-terveys",
    },
    {
        "id": "kasvinterveys",
        "title": "Kasvinterveyden avoin tieto",
        "description": (
            "Tuholaisseuranta, siementen sertifiointi ja"
            " lannoitevalvonnan tulokset."
        ),
        "keywords": ["kasvinterveys", "tuholainen", "siemen", "lannoite", "Ruokavirasto"],
        "url": f"{AVOINTIETO_BASE}/kasvinterveys",
    },
    {
        "id": "eu-tuet-varainhoitovuosi",
        "title": "EU-tukimaksut (varainhoitovuosi)",
        "description": (
            "EAGF- ja EAFRD-tukimaksut varainhoitovuosittain."
            " Tuensaajat ja maksetut tuet."
        ),
        "keywords": ["EU-tuki", "maataloustuki", "EAGF", "EAFRD", "Ruokavirasto"],
        "url": f"{AVOINTIETO_BASE}/eu-tuet-varainhoitovuosi",
    },
    {
        "id": "eu-tuet-kalenterivuosi",
        "title": "EU-tukimaksut (kalenterivuosi)",
        "description": (
            "EAGF- ja EAFRD-tukimaksut kalenterivuosittain."
            " Tuensaajat ja maksetut tuet."
        ),
        "keywords": ["EU-tuki", "maataloustuki", "EAGF", "EAFRD", "Ruokavirasto"],
        "url": f"{AVOINTIETO_BASE}/eu-tuet-kalenterivuosi",
    },
]

# --- C. Rajoitetut rajapinnat (liityntäkatalogi) ---

RESTRICTED_SERVICES: list[dict[str, Any]] = [
    {
        "id": "elainrekisteri",
        "title": "Eläinrekisteri",
        "description": (
            "Nautojen, sikojen ja lampaiden rekisteritiedot."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["eläinrekisteri", "nauta", "sika", "lammas", "Ruokavirasto"],
    },
    {
        "id": "teurastamotiedot",
        "title": "Teurastamotiedot",
        "description": (
            "Teurastus- ja lihantarkastustiedot."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["teurastamo", "lihantarkastus", "Ruokavirasto"],
    },
    {
        "id": "luomutoimijarekisteri",
        "title": "Luomutoimijarekisteri",
        "description": (
            "Luomutoimijoiden valvontatiedot."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["luomu", "luomutoimija", "valvonta", "Ruokavirasto"],
    },
    {
        "id": "kasvinsuojeluainerekisteri",
        "title": "Kasvinsuojeluainerekisteri",
        "description": (
            "Hyväksytyt kasvinsuojeluaineet ja niiden käyttöehdot."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["kasvinsuojeluaine", "torjunta-aine", "Ruokavirasto"],
    },
    {
        "id": "rehurekisteri",
        "title": "Rehurekisteri",
        "description": (
            "Rehutoimijat ja rehuvalvonnan tulokset."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["rehu", "rehutoimija", "valvonta", "Ruokavirasto"],
    },
    {
        "id": "lannoiterekisteri",
        "title": "Lannoiterekisteri",
        "description": (
            "Lannoitetoimijat ja lannoitetuotteet."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["lannoite", "lannoitetoimija", "Ruokavirasto"],
    },
    {
        "id": "vierasainerekisteri",
        "title": "Vierasainerekisteri",
        "description": (
            "Elintarvikkeiden vierasainevalvonnan tulokset."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["vierasaine", "elintarvike", "valvonta", "Ruokavirasto"],
    },
    {
        "id": "elintarvikehuoneistorekisteri",
        "title": "Elintarvikehuoneistorekisteri",
        "description": (
            "Hyväksytyt elintarvikehuoneistot."
            " Rajoitettu viranomaiskäyttöön."
        ),
        "keywords": ["elintarvikehuoneisto", "hyväksyntä", "Ruokavirasto"],
    },
]


class RuokavirastoHarvester(BaseHarvester):
    """Kerää Ruokaviraston avoimet ja rajoitetut aineistot.

    Ruokavirasto (Finnish Food Authority) tarjoaa maatalouden
    paikkatietoaineistoja (INSPIRE GeoServer), avoin tieto -dashboardeja
    ja rajoitettuja viranomaiskäytön rajapintoja.
    """

    name = "ruokavirasto"
    description = "Ruokavirasto — maatalous, elintarvike- ja eläinvalvonta"
    url = "https://www.ruokavirasto.fi"

    async def harvest(self) -> int:
        count = 0

        # A. INSPIRE-paikkatiedot
        for dtype in INSPIRE_TYPES:
            for year in INSPIRE_YEARS:
                dataset = self._inspire_to_dataset(dtype, year)
                upsert_dataset(self.conn, dataset)
                count += 1

        # B. Dashboardit
        for dash in DASHBOARDS:
            dataset = self._dashboard_to_dataset(dash)
            upsert_dataset(self.conn, dataset)
            count += 1

        # C. Rajoitetut rajapinnat
        for svc in RESTRICTED_SERVICES:
            dataset = self._restricted_to_dataset(svc)
            upsert_dataset(self.conn, dataset)
            count += 1

        self.conn.commit()
        logger.info("[ruokavirasto] Harvest valmis: %d datasettiä", count)
        return count

    def _inspire_to_dataset(self, dtype: dict[str, Any], year: int) -> Dataset:
        type_id = dtype["id"]
        workspace = dtype["workspace"]
        ds_id = f"ruokavirasto-{type_id}-{year}"
        wms_url = f"{GEOSERVER_BASE}/{workspace}_{year}/wms"
        wfs_url = f"{GEOSERVER_BASE}/{workspace}_{year}/wfs"
        gpkg_url = (
            f"{GPKG_BASE}/{workspace}_{year}/ows"
            "?service=WFS&request=GetFeature&outputFormat=geopackage"
        )

        return self._make_dataset(
            id=ds_id,
            name=ds_id,
            title=f"{dtype['title']} {year}",
            title_fi=f"{dtype['title']} {year}",
            notes_fi=f"{dtype['description']} Vuoden {year} aineisto.",
            organization_id="ruokavirasto",
            organization_name="ruokavirasto",
            organization_title="Ruokavirasto",
            keywords_fi=dtype.get("keywords", []),
            num_resources=3,
            resources=[
                Resource(
                    id=f"{ds_id}-wms",
                    name=f"{dtype['title']} {year} (WMS)",
                    name_fi=f"{dtype['title']} {year} — WMS-karttapalvelu",
                    format="WMS",
                    url=wms_url,
                ),
                Resource(
                    id=f"{ds_id}-wfs",
                    name=f"{dtype['title']} {year} (WFS)",
                    name_fi=f"{dtype['title']} {year} — WFS-rajapinta",
                    format="WFS",
                    url=wfs_url,
                ),
                Resource(
                    id=f"{ds_id}-gpkg",
                    name=f"{dtype['title']} {year} (GeoPackage)",
                    name_fi=f"{dtype['title']} {year} — GeoPackage-lataus",
                    format="GPKG",
                    url=gpkg_url,
                ),
            ],
            access_level="open",
        )

    def _dashboard_to_dataset(self, dash: dict[str, Any]) -> Dataset:
        ds_id = f"ruokavirasto-{dash['id']}"

        return self._make_dataset(
            id=ds_id,
            name=ds_id,
            title=dash["title"],
            title_fi=dash["title"],
            notes_fi=dash["description"],
            organization_id="ruokavirasto",
            organization_name="ruokavirasto",
            organization_title="Ruokavirasto",
            keywords_fi=dash.get("keywords", []),
            num_resources=1,
            resources=[
                Resource(
                    id=f"{ds_id}-html",
                    name=f"{dash['title']} (Dashboard)",
                    name_fi=f"{dash['title']} — Avoin tieto -dashboard",
                    format="HTML",
                    url=dash["url"],
                ),
            ],
            access_level="open",
        )

    def _restricted_to_dataset(self, svc: dict[str, Any]) -> Dataset:
        ds_id = f"ruokavirasto-{svc['id']}"

        return self._make_dataset(
            id=ds_id,
            name=ds_id,
            title=svc["title"],
            title_fi=svc["title"],
            notes_fi=svc["description"],
            organization_id="ruokavirasto",
            organization_name="ruokavirasto",
            organization_title="Ruokavirasto",
            keywords_fi=svc.get("keywords", []),
            license_id="",
            license_title="Ei avointa lisenssiä",
            collection_type="Restricted Data",
            num_resources=1,
            resources=[
                Resource(
                    id=f"{ds_id}-api",
                    name=f"{svc['title']} (API)",
                    name_fi=f"{svc['title']} — Liityntäkatalogi-rajapinta",
                    format="API",
                    url="https://liityntakatalogi.suomi.fi",
                ),
            ],
            access_level="restricted",
        )
