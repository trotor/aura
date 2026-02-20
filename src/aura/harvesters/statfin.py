"""Harvester Tilastokeskuksen PxWeb API:lle."""

from __future__ import annotations

from aura.harvesters.pxweb import PxWebHarvester


class StatfinHarvester(PxWebHarvester):
    """Kerää tilastotaulut Tilastokeskuksen PxWeb API:sta.

    PxWeb-rajapinta on puumainen: juuritaso → aihealueet → alataso → taulut.
    Jokainen taulu on yksi datasetti.
    """

    name = "statfin"
    description = "Tilastokeskus (Statistics Finland) — PxWeb-tilastot"
    url = "https://stat.fi"
    pxweb_base_url = "https://statfin.stat.fi/PxWeb/api/v1"
    root_path = "StatFin"
    web_base_url = "https://statfin.stat.fi/PxWeb/pxweb/fi"
    org_id = "tilastokeskus"
    org_name = "tilastokeskus"
    org_title = "Tilastokeskus"
    dataset_id_prefix = "statfin"
    notes_template = "Tilastokeskuksen tilastotaulu"
