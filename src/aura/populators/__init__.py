"""Viiteaineistojen populaattorit."""

from __future__ import annotations

from aura.populators.base import BasePopulator
from aura.populators.municipalities import MunicipalityPopulator

# Rekisteri kaikista populaattoreista
POPULATORS: dict[str, type[BasePopulator]] = {
    "municipalities": MunicipalityPopulator,
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
