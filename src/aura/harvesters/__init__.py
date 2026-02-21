"""Datalähteiden keräimet."""

from __future__ import annotations

from aura.harvesters.avoindata import AvoindataHarvester
from aura.harvesters.base import BaseHarvester
from aura.harvesters.digitraffic import DigitrafficHarvester
# noqa: F401 — StaticHarvester ei käytetä suoraan, mutta viedään osaksi API:a
from aura.harvesters.static import StaticHarvester  # noqa: F401
from aura.harvesters.fmi import FmiHarvester
from aura.harvesters.gtk import GtkHarvester
from aura.harvesters.hri import HriHarvester
from aura.harvesters.luke import LukeHarvester
from aura.harvesters.metsakeskus import MetsakeskusHarvester
from aura.harvesters.overture import OvertureHarvester
from aura.harvesters.ruokavirasto import RuokavirastoHarvester
from aura.harvesters.statfin import StatfinHarvester
from aura.harvesters.syke import SykeHarvester
from aura.harvesters.taustakartat import TaustakartatHarvester
from aura.harvesters.traficom import TraficomHarvester

# Rekisteri kaikista harvestereista
HARVESTERS: dict[str, type[BaseHarvester]] = {
    "avoindata.fi": AvoindataHarvester,
    "hri.fi": HriHarvester,
    "syke": SykeHarvester,
    "statfin": StatfinHarvester,
    "luke": LukeHarvester,
    "digitraffic": DigitrafficHarvester,
    "fmi": FmiHarvester,
    "gtk": GtkHarvester,
    "traficom": TraficomHarvester,
    "metsakeskus": MetsakeskusHarvester,
    "taustakartat": TaustakartatHarvester,
    "overture": OvertureHarvester,
    "ruokavirasto": RuokavirastoHarvester,
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
