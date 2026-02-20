"""Harvester Luonnonvarakeskuksen (LUKE) PxWeb API:lle."""

from __future__ import annotations

from aura.harvesters.pxweb import PxWebHarvester


class LukeHarvester(PxWebHarvester):
    """Kerää tilastotaulut Luonnonvarakeskuksen PxWeb API:sta.

    LUKE:n PxWeb sisältää maa-, metsä- ja kalatilastoja.
    Sama PxWeb-rajapinta kuin Tilastokeskuksella.
    """

    name = "luke"
    description = "Luonnonvarakeskus (LUKE) — maa-, metsä- ja kalatilastot"
    url = "https://statdb.luke.fi"
    pxweb_base_url = "https://statdb.luke.fi/PxWeb/api/v1"
    root_path = "LUKE"
    web_base_url = "https://statdb.luke.fi/PxWeb/pxweb/fi"
    org_id = "luke"
    org_name = "luke"
    org_title = "Luonnonvarakeskus (LUKE)"
    dataset_id_prefix = "luke"
    notes_template = "Luonnonvarakeskuksen tilastotaulu"
