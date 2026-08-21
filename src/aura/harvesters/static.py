"""Konfiguraatiopohjainen harvester staattisille datalähteille."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterator
from typing import Any

from aura.database import upsert_dataset
from aura.harvesters.base import BaseHarvester
from aura.models import Dataset, Resource

logger = logging.getLogger(__name__)

# Formaattien suomenkieliset nimet resurssien automaattiseen nimeämiseen
FORMAT_LABELS_FI: dict[str, str] = {
    "WFS": "WFS-rajapinta",
    "WMS": "WMS-karttapalvelu",
    "WCS": "WCS-rajapinta",
    "TMS": "TMS-tiilipalvelu",
    "API": "rajapinta",
    "HTML": "lisätiedot",
    "ZIP": "tiedostolataus",
    "GPKG": "GeoPackage-lataus",
    "GeoParquet": "GeoParquet",
    "XLSX": "Excel-taulukko",
    "CSV": "CSV-tiedosto",
}


class StaticHarvester(BaseHarvester):
    """Konfiguraatiopohjainen harvester staattisille datalähteille.

    Aliluokka määrittelee ``datasets_config``-listan, jossa kukin alkio
    on dict joka kuvaa yhden datasetin.  Harvester luo Dataset-oliot
    konfiguraation perusteella ilman API-kutsuja.

    Tukee vuosiekspansiota: jos konfiguraatiossa on ``years``-kenttä,
    datasetti monistetaan jokaiselle vuodelle ja ``{year}``-paikkamerkit
    korvataan vuosinumerolla.

    Organisaatiotiedot voi asettaa luokkatasolla (``org_id``, ``org_name``,
    ``org_title``) tai yliajaa datasetti-kohtaisesti.
    """

    org_id: str = ""
    org_name: str = ""
    org_title: str = ""
    default_update_frequency: str = ""
    datasets_config: list[dict[str, Any]] = []

    @classmethod
    def source_config(cls) -> dict[str, Any]:
        config = super().source_config()
        config.update({
            "harvester_type": "static",
            "query_protocol": "static",
        })
        return config

    async def harvest(self) -> int:
        count = 0
        for cfg in self.datasets_config:
            for dataset in self._expand(cfg):
                upsert_dataset(self.conn, dataset)
                self._auto_enrich_crs(dataset)
                count += 1
        self.conn.commit()
        logger.info("[%s] Harvest valmis: %d datasettiä", self.name, count)
        return count

    def _expand(self, cfg: dict[str, Any]) -> Iterator[Dataset]:
        """Luo yksi tai useampi Dataset konfiguraatiosta.

        Jos konfiguraatiossa on ``years``, tuottaa datasetin per vuosi.
        """
        years = cfg.get("years")
        if years:
            for year in years:
                yield self._to_dataset(cfg, year=year)
        else:
            yield self._to_dataset(cfg)

    def _to_dataset(
        self, cfg: dict[str, Any], *, year: int | None = None
    ) -> Dataset:
        """Muunna konfiguraatio-dict Dataset-olioksi."""

        def fmt(s: str) -> str:
            """Korvaa {year}-paikkamerkki vuosinumerolla."""
            return s.format(year=year) if year is not None else s

        ds_id = fmt(cfg["id"])
        title = fmt(cfg.get("title", ""))

        resources = []
        # Formaattilaskuri: oletustunnus oli pelkkä {ds_id}-{formaatti},
        # joten datasetin kolme JSON-resurssia saivat saman tunnuksen ja
        # save_dataset()-upsert kirjoitti ne toistensa päälle — kaksi
        # kolmesta katosi hiljaa. Ensimmäinen kutakin formaattia pitää
        # entisen tunnuksensa, jottei koko katalogin tunnuksia vaihdeta;
        # seuraaville lisätään järjestysnumero.
        seen_formats: Counter[str] = Counter()
        for r in cfg.get("resources", []):
            r_fmt = r.get("format", "")
            label = FORMAT_LABELS_FI.get(r_fmt, r_fmt)
            seen_formats[r_fmt] += 1
            n = seen_formats[r_fmt]
            default_id = f"{ds_id}-{r_fmt.lower()}" + ("" if n == 1 else f"-{n}")
            resources.append(
                Resource(
                    id=fmt(r["id"]) if "id" in r else default_id,
                    name=fmt(r.get("name", f"{title} ({r_fmt})")),
                    name_fi=fmt(r.get("name_fi", f"{title} — {label}")),
                    format=r_fmt,
                    url=fmt(r.get("url", "")),
                )
            )

        kwargs: dict[str, Any] = {
            "id": ds_id,
            "name": fmt(cfg.get("name", cfg["id"])),
            "title": title,
            "title_fi": fmt(cfg.get("title_fi", title)),
            "notes_fi": fmt(cfg.get("notes_fi", "")),
            "organization_id": cfg.get("organization_id", self.org_id),
            "organization_name": cfg.get("organization_name", self.org_name),
            "organization_title": cfg.get("organization_title", self.org_title),
            "keywords_fi": cfg.get("keywords_fi", []),
            "num_resources": len(resources),
            "resources": resources,
            "estimated_size_bytes": cfg.get("estimated_size_bytes", 0),
        }

        # Salli oletusarvojen yliajo (lisenssi, access_level, taajuus jne.)
        for key in (
            "license_id", "license_title", "collection_type",
            "geographical_coverage", "access_level",
            "update_frequency", "metadata_modified",
        ):
            if key in cfg:
                kwargs[key] = cfg[key]

        # Luokkatason oletustaajuus jos ei konfiguraatiossa
        if "update_frequency" not in kwargs and self.default_update_frequency:
            kwargs["update_frequency"] = self.default_update_frequency

        return self._make_dataset(**kwargs)
