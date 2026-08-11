"""Instanssin itsekuvaus julkisella sivulla.

Avoin aura voi ajaa laajennetun hakukerroksen alla — silloin julkinen
instanssi ei ole sama asia kuin se mitä repositoriosta saa. Ländärisivu
väitti aiemmin ehdoitta että "tämä sivu ja MCP-endpoint tulevat samasta
repositoriosta", ja se lakkaa olemasta totta heti kun palvelin ajaa jotain
muuta.

Tämä moduuli antaa ajavalle instanssille tavan kertoa mitä se on. Oletus on
että instanssi on täsmälleen tämä repositorio; muu on kerrottava
eksplisiittisesti ympäristömuuttujilla.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import NamedTuple

#: Instanssin nimi, esim. "Aura Pro". Tyhjä = pelkkä avoin aura.
INSTANCE_NAME_ENV = "AURA_INSTANCE_NAME"

#: Yhden kappaleen kuvaus siitä mitä tämä instanssi tarjoaa yli avoimen.
INSTANCE_NOTE_ENV = "AURA_INSTANCE_NOTE"


class Instance(NamedTuple):
    """Mitä tämä ajava instanssi on."""

    name: str
    note: str

    @property
    def is_extended(self) -> bool:
        """Onko tässä jotain muuta kuin avoin repositorio."""
        return bool(self.name or self.note)


def describe_instance(env: Mapping[str, str] | None = None) -> Instance:
    """Lue instanssin itsekuvaus ympäristöstä.

    Ilman muuttujia palautuu tyhjä kuvaus, jolloin sivu kertoo instanssin
    olevan sama kuin repositorio. Se on oikea oletus: kuka tahansa joka ajaa
    tätä koodia saa sen mitä koodissa lukee.
    """
    if env is None:
        env = os.environ
    return Instance(
        name=env.get(INSTANCE_NAME_ENV, "").strip(),
        note=env.get(INSTANCE_NOTE_ENV, "").strip(),
    )
