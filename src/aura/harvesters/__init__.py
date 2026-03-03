"""Datalähteiden keräimet."""

from __future__ import annotations

from aura.harvesters.avoindata import AvoindataHarvester
from aura.harvesters.base import BaseHarvester
from aura.harvesters.digitraffic import DigitrafficHarvester
from aura.harvesters.fmi import FmiHarvester
from aura.harvesters.gtk import GtkHarvester
from aura.harvesters.hri import HriHarvester
from aura.harvesters.koodistot import KoodistotHarvester
from aura.harvesters.kunnat import KunnatHarvester
from aura.harvesters.lipas import LipasHarvester
from aura.harvesters.luke import LukeHarvester
from aura.harvesters.luke_kartta import LukeKarttaHarvester
from aura.harvesters.luke_opendata import LukeOpendataHarvester
from aura.harvesters.metsakeskus import MetsakeskusHarvester
from aura.harvesters.mml import MmlHarvester
from aura.harvesters.overture import OvertureHarvester
from aura.harvesters.paikkatietoikkuna import PaikkatietoikkunaHarvester
from aura.harvesters.paituli import PaituliHarvester
from aura.harvesters.ruokavirasto import RuokavirastoHarvester
from aura.harvesters.sanastot import SanastotHarvester
from aura.harvesters.smartsmear import SmartSmearHarvester
from aura.harvesters.sotkanet import SotkanetHarvester
from aura.harvesters.statfin import StatfinHarvester
from aura.harvesters.statfin_geo import StatfinGeoHarvester

# noqa: F401 — StaticHarvester ei käytetä suoraan, mutta viedään osaksi API:a
from aura.harvesters.static import StaticHarvester  # noqa: F401
from aura.harvesters.stuk import StukHarvester
from aura.harvesters.syke import SykeHarvester
from aura.harvesters.taustakartat import TaustakartatHarvester
from aura.harvesters.traficom import TraficomHarvester
from aura.harvesters.vaalirahoitus import VaalirahoitusHarvester
from aura.harvesters.valtiokonttori import ValtiokonttoriHarvester
from aura.harvesters.vayla import VaylaHarvester

# Rekisteri kaikista harvestereista
HARVESTERS: dict[str, type[BaseHarvester]] = {
    "avoindata.fi": AvoindataHarvester,
    "hri.fi": HriHarvester,
    "syke": SykeHarvester,
    "statfin": StatfinHarvester,
    "statfin-geo": StatfinGeoHarvester,
    "luke": LukeHarvester,
    "digitraffic": DigitrafficHarvester,
    "fmi": FmiHarvester,
    "gtk": GtkHarvester,
    "traficom": TraficomHarvester,
    "metsakeskus": MetsakeskusHarvester,
    "taustakartat": TaustakartatHarvester,
    "overture": OvertureHarvester,
    "ruokavirasto": RuokavirastoHarvester,
    "vaalirahoitus": VaalirahoitusHarvester,
    "valtiokonttori": ValtiokonttoriHarvester,
    "mml": MmlHarvester,
    "vayla": VaylaHarvester,
    "stuk": StukHarvester,
    "lipas": LipasHarvester,
    "paikkatietoikkuna": PaikkatietoikkunaHarvester,
    "paituli": PaituliHarvester,
    "kunnat": KunnatHarvester,
    "koodistot": KoodistotHarvester,
    "sanastot": SanastotHarvester,
    "luke-opendata": LukeOpendataHarvester,
    "luke-kartta": LukeKarttaHarvester,
    "smartsmear": SmartSmearHarvester,
    "sotkanet": SotkanetHarvester,
}


def get_harvester(name: str) -> type[BaseHarvester]:
    """Hae harvester nimellä."""
    if name not in HARVESTERS:
        available = ", ".join(HARVESTERS.keys())
        raise ValueError(f"Tuntematon harvester: {name}. Saatavilla: {available}")
    return HARVESTERS[name]


def get_all_harvesters() -> dict[str, type[BaseHarvester]]:
    """Palauta kaikki rekisteröidyt harvesterit."""
    return HARVESTERS.copy()
