"""Harvester Suomen metsäkeskuksen GeoServer-rajapinnalle."""

from __future__ import annotations

import logging
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

GEOSERVER_BASE = "https://avoin.metsakeskus.fi/rajapinnat/v1"
DOWNLOAD_BASE = "https://avoin.metsakeskus.fi/aineistot"
INFO_PAGE_URL = "https://avoin.metsakeskus.fi"

# Tunnetut palvelut ja niiden kuvaukset
SERVICES: list[dict[str, Any]] = [
    {
        "endpoint": "stand",
        "title": "Metsävarakuviot",
        "description": (
            "Kuviotason metsävaratiedot: puulaji, tilavuus, ikä,"
            " pituus, läpimitta, kasvupaikka"
        ),
        "keywords": ["metsä", "kuviotiedot", "puusto", "metsävarat"],
        "estimated_size_gb": 50,
        "download_dir": "Metsavarakuviot",
    },
    {
        "endpoint": "gridcell",
        "title": "Hilatiedot (16m ruutudata)",
        "description": (
            "Laserkeilauspohjaiset metsävaratiedot 16m ruuduissa:"
            " puulajikohtaiset tiedot"
        ),
        "keywords": ["metsä", "hila", "laserkeilaus", "LiDAR"],
        "estimated_size_gb": 200,
        "download_dir": "Hila",
    },
    {
        "endpoint": "habitat",
        "title": "Erityisen tärkeät elinympäristöt",
        "description": "Metsälain 10 §:n mukaiset erityisen tärkeät elinympäristöt",
        "keywords": ["metsä", "elinympäristö", "luonnonsuojelu", "metsälaki"],
        "estimated_size_gb": 5,
        "download_dir": "Erityisen_tarkeat_elinymparistokuviot",
    },
    {
        "endpoint": "forestusedeclaration",
        "title": "Metsänkäyttöilmoitukset",
        "description": "Hakkuu- ja muut metsänkäyttöilmoitukset",
        "keywords": ["metsä", "hakkuu", "metsänkäyttöilmoitus"],
        "estimated_size_gb": 10,
        "download_dir": "Metsankayttoilmoitukset",
    },
    {
        "endpoint": "forestmask",
        "title": "Metsämaski",
        "description": "Metsä/ei-metsä-luokitus",
        "keywords": ["metsä", "maankäyttö", "luokitus"],
        "estimated_size_gb": 5,
        "download_dir": "Metsamaski",
    },
    {
        "endpoint": "inventory_sampleplot",
        "title": "Inventointikoealat",
        "description": "Maastoinventoinnin koealat metsävarojen kalibrointiin",
        "keywords": ["metsä", "inventointi", "koeala"],
        "estimated_size_gb": 1,
        "download_dir": "Inventointikoealat",
    },
    {
        "endpoint": "sampleplot",
        "title": "Kaukokartoituskoealat",
        "description": "Kaukokartoituksen referenssikoealat",
        "keywords": ["metsä", "kaukokartoitus", "koeala"],
        "estimated_size_gb": 1,
        "download_dir": "Kaukokartoituskoealat",
    },
    {
        "endpoint": "CHM_newest",
        "title": "Latvusmalli (uusin)",
        "description": "Laserkeilauspohjainen latvuston korkeusmalli, uusin versio",
        "keywords": ["metsä", "latvusmalli", "CHM", "LiDAR"],
        "estimated_size_gb": 100,
        "format": "WCS",
    },
    {
        "endpoint": "Pintavesien_virtausmalli",
        "title": "Pintavesien virtausmalli",
        "description": "Hydrologinen pintavesien virtausmalli",
        "keywords": ["hydrologia", "vesistö", "virtaus"],
        "estimated_size_gb": 20,
        "format": "WCS",
    },
    {
        "endpoint": "D8_flow_direction",
        "title": "Virtaussuuntamalli (D8)",
        "description": "D8-algoritmin mukainen virtaussuuntamalli",
        "keywords": ["hydrologia", "virtaus", "D8"],
        "estimated_size_gb": 20,
        "format": "WCS",
    },
    {
        "endpoint": "FA_flow_accumulation",
        "title": "Valunta-aluemalli",
        "description": "Veden kertymämalli (flow accumulation)",
        "keywords": ["hydrologia", "valunta", "vesistö"],
        "estimated_size_gb": 20,
        "format": "WCS",
    },
]

# Latvusmallin vuosiversiot (2008–2022)
CHM_YEARS = list(range(2008, 2023))

# Lataus-only datasetit (ei API-endpointia)
DOWNLOAD_ONLY_DATASETS: list[dict[str, Any]] = [
    {
        "id": "korjuukelpoisuus",
        "title": "Korjuukelpoisuus",
        "description": "Korjuukelpoisuuskartat maakunnittain (~130 ZIP-tiedostoa)",
        "keywords": ["metsä", "korjuukelpoisuus", "hakkuu"],
        "download_dir": "Korjuukelpoisuus",
        "estimated_size_gb": 10,
    },
]

# Kemera-tukitoimenpiteiden endpointit
KEMERA_ENDPOINTS = [
    ("application_stand_06_16", "Kemera: taimikon varhaishoito (hakemus)"),
    ("application_stand_10_10", "Kemera: nuoren metsän hoito (hakemus)"),
    ("application_stand_10_30", "Kemera: pienpuun keräys (hakemus)"),
    ("application_stand_10_91", "Kemera: juurikäävän torjunta (hakemus)"),
    ("application_stand_11_30", "Kemera: suometsän hoito (hakemus)"),
    ("application_stand_11_50", "Kemera: metsätien tekeminen (hakemus)"),
    ("application_stand_11_90", "Kemera: ympäristötuki (hakemus)"),
    ("application_stand_11_91", "Kemera: luonnonhoitohanke (hakemus)"),
    ("application_stand_12_17", "Kemera: terveyslannoitus (hakemus)"),
    ("application_stand_13_50", "Kemera: metsätien perusparannus (hakemus)"),
    ("completiondeclaration_stand_06_16", "Kemera: taimikon varhaishoito (toteutus)"),
    ("completiondeclaration_stand_10_10", "Kemera: nuoren metsän hoito (toteutus)"),
    ("completiondeclaration_stand_10_30", "Kemera: pienpuun keräys (toteutus)"),
    ("completiondeclaration_stand_11_30", "Kemera: suometsän hoito (toteutus)"),
    ("completiondeclaration_stand_11_50", "Kemera: metsätien tekeminen (toteutus)"),
    ("completiondeclaration_stand_11_90", "Kemera: ympäristötuki (toteutus)"),
]


class MetsakeskusHarvester(BaseHarvester):
    """Kerää Suomen metsäkeskuksen avoimet metsä- ja luontotiedot.

    Metsäkeskus ylläpitää Suomen kattavinta avointa metsävaratietokantaa.
    Data sisältää kuviotason metsävaratiedot, hiladatan, elinympäristöt,
    hakkuuilmoitukset, Kemera-tukitiedot ja latvusmallit.
    """

    name = "metsakeskus"
    description = "Suomen metsäkeskus — metsävara-, elinympäristö- ja hakkuutiedot"
    url = "https://avoin.metsakeskus.fi"

    async def harvest(self) -> int:
        count = 0

        # Pääpalvelut
        for svc in SERVICES:
            dataset = self._service_to_dataset(svc)
            upsert_dataset(self.conn, dataset)
            count += 1

        # Latvusmallin vuosiversiot
        for year in CHM_YEARS:
            dataset = self._chm_year_dataset(year)
            upsert_dataset(self.conn, dataset)
            count += 1

        # Kemera-endpointit
        for endpoint, title in KEMERA_ENDPOINTS:
            dataset = self._kemera_dataset(endpoint, title)
            upsert_dataset(self.conn, dataset)
            count += 1

        # Lataus-only datasetit
        for cfg in DOWNLOAD_ONLY_DATASETS:
            dataset = self._download_only_dataset(cfg)
            upsert_dataset(self.conn, dataset)
            count += 1

        self.conn.commit()
        logger.info("[metsakeskus] Harvest valmis: %d datasettiä", count)
        return count

    def _service_to_dataset(self, svc: dict[str, Any]) -> Dataset:
        endpoint = svc["endpoint"]
        fmt = svc.get("format", "WFS")
        url = f"{GEOSERVER_BASE}/{endpoint}/ows"
        size_bytes = svc.get("estimated_size_gb", 1) * 1024 * 1024 * 1024
        download_dir = svc.get("download_dir")

        resources = [
            Resource(
                id=f"metsakeskus-{endpoint.lower()}-{fmt.lower()}",
                name=f"{svc['title']} ({fmt})",
                name_fi=f"{svc['title']} — {fmt}-rajapinta",
                format=fmt,
                url=url,
            ),
        ]

        if download_dir:
            resources.append(
                Resource(
                    id=f"metsakeskus-{endpoint.lower()}-download",
                    name=f"{svc['title']} (lataus)",
                    name_fi=f"{svc['title']} — tiedostolataus",
                    format="ZIP",
                    url=f"{DOWNLOAD_BASE}/{download_dir}/",
                ),
            )
        else:
            resources.append(
                Resource(
                    id=f"metsakeskus-{endpoint.lower()}-info",
                    name=f"{svc['title']} (infosivu)",
                    name_fi=f"{svc['title']} — lisätiedot",
                    format="HTML",
                    url=INFO_PAGE_URL,
                ),
            )

        return self._make_dataset(
            id=f"metsakeskus-{endpoint.lower()}",
            name=f"metsakeskus-{endpoint.lower().replace('_', '-')}",
            title=svc["title"],
            title_fi=svc["title"],
            notes_fi=svc["description"],
            organization_id="metsakeskus",
            organization_name="metsakeskus",
            organization_title="Suomen metsäkeskus",
            keywords_fi=svc.get("keywords", ["metsä"]),
            num_resources=len(resources),
            resources=resources,
            estimated_size_bytes=int(size_bytes),
        )

    def _chm_year_dataset(self, year: int) -> Dataset:
        endpoint = f"CHM_{year}"
        return self._make_dataset(
            id=f"metsakeskus-chm-{year}",
            name=f"metsakeskus-chm-{year}",
            title=f"Latvusmalli {year}",
            title_fi=f"Latvusmalli {year}",
            notes_fi=f"Laserkeilauspohjainen latvuston korkeusmalli vuodelta {year}",
            organization_id="metsakeskus",
            organization_name="metsakeskus",
            organization_title="Suomen metsäkeskus",
            keywords_fi=["metsä", "latvusmalli", "CHM", "LiDAR", str(year)],
            num_resources=2,
            resources=[
                Resource(
                    id=f"metsakeskus-chm-{year}-wcs",
                    name=f"CHM {year} (WCS)",
                    name_fi=f"Latvusmalli {year} — WCS-rajapinta",
                    format="WCS",
                    url=f"{GEOSERVER_BASE}/{endpoint}/ows",
                ),
                Resource(
                    id=f"metsakeskus-chm-{year}-download",
                    name=f"Latvusmalli {year} (lataus)",
                    name_fi=f"Latvusmalli {year} — tiedostolataus",
                    format="ZIP",
                    url=f"{DOWNLOAD_BASE}/Latvusmalli/",
                ),
            ],
            estimated_size_bytes=50 * 1024 * 1024 * 1024,  # ~50 GB per vuosi
        )

    def _kemera_dataset(self, endpoint: str, title: str) -> Dataset:
        return self._make_dataset(
            id=f"metsakeskus-{endpoint.lower()}",
            name=f"metsakeskus-{endpoint.lower().replace('_', '-')}",
            title=title,
            title_fi=title,
            notes_fi=f"Kemera-rahoituslain mukainen tukitieto. Endpoint: {endpoint}",
            organization_id="metsakeskus",
            organization_name="metsakeskus",
            organization_title="Suomen metsäkeskus",
            keywords_fi=["metsä", "kemera", "tuki", "metsänhoito"],
            num_resources=2,
            resources=[
                Resource(
                    id=f"metsakeskus-{endpoint.lower()}-wfs",
                    name=f"{title} (WFS)",
                    name_fi=f"{title} — WFS-rajapinta",
                    format="WFS",
                    url=f"{GEOSERVER_BASE}/{endpoint}/ows",
                ),
                Resource(
                    id=f"metsakeskus-{endpoint.lower()}-download",
                    name=f"{title} (lataus)",
                    name_fi=f"{title} — tiedostolataus",
                    format="ZIP",
                    url=f"{DOWNLOAD_BASE}/Kemera/",
                ),
            ],
            estimated_size_bytes=500 * 1024 * 1024,  # ~500 MB per Kemera-setti
        )

    def _download_only_dataset(self, cfg: dict[str, Any]) -> Dataset:
        ds_id = cfg["id"]
        return self._make_dataset(
            id=f"metsakeskus-{ds_id}",
            name=f"metsakeskus-{ds_id}",
            title=cfg["title"],
            title_fi=cfg["title"],
            notes_fi=cfg["description"],
            organization_id="metsakeskus",
            organization_name="metsakeskus",
            organization_title="Suomen metsäkeskus",
            keywords_fi=cfg.get("keywords", ["metsä"]),
            num_resources=1,
            resources=[
                Resource(
                    id=f"metsakeskus-{ds_id}-download",
                    name=f"{cfg['title']} (lataus)",
                    name_fi=f"{cfg['title']} — tiedostolataus",
                    format="ZIP",
                    url=f"{DOWNLOAD_BASE}/{cfg['download_dir']}/",
                ),
            ],
            estimated_size_bytes=int(
                cfg.get("estimated_size_gb", 1) * 1024 * 1024 * 1024
            ),
        )
