"""Harvester Suomen ympäristökeskuksen (SYKE) CKAN API:lle."""

from __future__ import annotations

from aura.harvesters.ckan import CkanHarvester


class SykeHarvester(CkanHarvester):
    """Kerää datasetit SYKE:n CKAN-portaalista.

    Suomen ympäristökeskus (SYKE) julkaisee ympäristö-, vesistö- ja
    paikkatietoja ckan.ymparisto.fi:ssä. Sisältää mm. pohjavesialueet,
    Natura 2000 -alueet, maankäyttö-, vedenlaatu- ja satelliittihavaintodataa.
    """

    name = "syke"
    description = "Suomen ympäristökeskus — ympäristö-, vesistö- ja paikkatiedot"
    url = "https://ckan.ymparisto.fi"
    ckan_base_url = "https://ckan.ymparisto.fi/api/3/action"
    ckan_source = "syke"
