"""Harvester Traficomin tilastotietokannan PxWeb-rajapinnalle.

Traficomilla on **kolme** erillistä avoimen datan rajapintaa, joista tämä on
kolmas:

1. ``opendata.traficom.fi`` — OData v12, rekisteridata (``traficom``-harvester)
2. avoindata.fi — CKAN-julkaisut (``avoindata.fi``-harvester)
3. ``trafi2.stat.fi`` — **tilastotietokanta**, tämä moduuli

Kolmas jäi pitkään huomaamatta, koska kaksi ensimmäistä kattavat Traficomin
nimen kaikissa katalogeissa: kysymykseen "onko meillä Traficomin data" sai
kahdesta lähteestä täyden vastauksen. Tilastotietokanta ei ole kummassakaan.

Sisältö on liikenteen viranomaistilastoa, jota ei ole StatFinissä: ajokortit,
ensirekisteröinnit, henkilöliikennetutkimus, ilmailulupakirjat, julkisen
liikenteen suoritetilasto, katsastuksen vikatilastot, kuljettajantutkinnot,
käytettynä maahantuodut ajoneuvot, liikennekäytössä olevat ajoneuvot,
taksiliikenteen kustannusindeksi sekä vesiliikenne ja sen onnettomuudet.
"""

from __future__ import annotations

from aura.harvesters.pxweb import PxWebHarvester


class TraficomTilastotHarvester(PxWebHarvester):
    """Kerää tilastotaulut Traficomin PxWeb-tilastotietokannasta.

    Sama PxWeb-rajapinta kuin Tilastokeskuksella ja Lukella, joten
    kantaluokka riittää sellaisenaan — vain osoitteet ja organisaatio
    vaihtuvat.
    """

    name = "traficom-tilastot"
    description = "Traficomin tilastotietokanta — liikenteen viranomaistilastot"
    url = "https://trafi2.stat.fi/PXWeb/pxweb/fi/TraFi/"
    pxweb_base_url = "https://trafi2.stat.fi/PXWeb/api/v1"
    root_path = "TraFi"
    web_base_url = "https://trafi2.stat.fi/PXWeb/pxweb/fi"
    org_id = "traficom"
    org_name = "traficom"
    org_title = "Liikenne- ja viestintävirasto Traficom"

    # Etuliite on ``trafi``, ei ``traficom``: OData-harvester käyttää jälkimmäistä
    # ja tunnisteet törmäisivät, jos entity setin nimi sattuisi olemaan sama kuin
    # taulukoodi. Erillinen etuliite pitää myös lähteet erotettavina haussa.
    dataset_id_prefix = "trafi"
    notes_template = "Traficomin tilastotaulu"
