"""Harvester Helsinki Region Infoshare (HRI) CKAN API:lle."""

from __future__ import annotations

from aura.harvesters.ckan import CkanHarvester


class HriHarvester(CkanHarvester):
    """Kerää datasetit Helsinki Region Infoshare -portaalista.

    HRI on pääkaupunkiseudun avoimen datan portaali (Helsinki, Espoo, Vantaa, Kauniainen).
    Käyttää samaa CKAN-rajapintaa kuin avoindata.fi.
    """

    name = "hri.fi"
    description = "Helsinki Region Infoshare — pääkaupunkiseudun avoin data"
    url = "https://hri.fi"
    ckan_base_url = "https://hri.fi/data/api/3/action"
    ckan_source = "hri.fi"
