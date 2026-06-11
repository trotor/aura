"""Viiteaineistojen populaattorit."""

from __future__ import annotations

from aura.populators.base import BasePopulator
from aura.populators.boundaries import BoundaryPopulator
from aura.populators.map_sheets import MapSheetPopulator
from aura.populators.municipalities import MunicipalityPopulator
from aura.populators.municipality_bbox import MunicipalityBboxPopulator
from aura.populators.postal_codes import PostalCodePopulator

# Rekisteri kaikista populaattoreista
POPULATORS: dict[str, type[BasePopulator]] = {
    "municipalities": MunicipalityPopulator,
    "postal_codes": PostalCodePopulator,
    "boundaries": BoundaryPopulator,
    "map_sheets": MapSheetPopulator,
    "municipality_bbox": MunicipalityBboxPopulator,
}


def get_populator(name: str) -> type[BasePopulator]:
    """Hae populaattori nimellä."""
    if name not in POPULATORS:
        available = ", ".join(POPULATORS.keys())
        raise ValueError(f"Tuntematon populaattori: {name}. Saatavilla: {available}")
    return POPULATORS[name]


def get_all_populators() -> dict[str, type[BasePopulator]]:
    """Palauta kaikki rekisteröidyt populaattorit."""
    return POPULATORS.copy()
