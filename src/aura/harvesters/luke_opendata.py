"""Harvester Luonnonvarakeskuksen (LUKE) avoimelle tutkimusdatalle.

LUKE:n erillinen CKAN-portaali opendata.luke.fi sisältää ~124 tutkimus-
ja paikkatietodatasettiä: metsävarat (MVMI), suurpetohavainnot, kala-
kantojen arvioinnit, biomassapotentiaalit, maaperän eroosioherkkyyskartrat ym.

Nämä ovat erillisiä PxWeb-tilastotauluista (statdb.luke.fi) jotka kerätään
LukeHarvester-luokalla.
"""

from __future__ import annotations

from aura.harvesters.ckan import CkanHarvester


class LukeOpendataHarvester(CkanHarvester):
    """Kerää datasetit LUKE:n avoin tutkimusdata -portaalista.

    Luonnonvarakeskus julkaisee tutkimusdataa, paikkatietoaineistoja
    ja ympäristöseurantatietoja opendata.luke.fi CKAN-portaalissa.
    Sisältää mm. metsävarakartat (MVMI), suurpetohavainnot, kalakantojen
    arvioinnit, biomassapotentiaalit ja maaperätiedot.
    """

    name = "luke-opendata"
    description = (
        "LUKE avoin tutkimusdata — metsävarat, riista, kalatalous, biomassa"
    )
    url = "https://opendata.luke.fi"
    ckan_base_url = "https://opendata.luke.fi/api/3/action"
    ckan_source = "luke-opendata"
