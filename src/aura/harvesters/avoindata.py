"""Harvester avoindata.fi:n CKAN API:lle."""

from __future__ import annotations

from aura.harvesters.ckan import CkanHarvester


class AvoindataHarvester(CkanHarvester):
    """Kerää datasetit avoindata.fi:n CKAN API:sta.

    avoindata.fi on Suomen kansallinen avoimen datan portaali.
    Sisältää sekä aineistopaketteja (tiedostoja) että rajapintoja (WFS, WMS, API).
    """

    name = "avoindata.fi"
    description = "Suomen kansallinen avoimen datan portaali"
    url = "https://avoindata.suomi.fi"
    ckan_base_url = "https://avoindata.suomi.fi/data/api/3/action"
    ckan_source = "avoindata.fi"
