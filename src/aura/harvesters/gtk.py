"""Harvester Geologian tutkimuskeskuksen (GTK) paikkatietorajapinnoille.

**Miksi tämä on kuratoitu lista eikä hakemiston luettelointi.** GTK:n
ArcGIS-hakemisto on koneluettava ja siinä on 188 palvelua, joten
automaattinen luettelointi olisi ilmeinen ajatus. Mitattuna 16.8.2026 se
tekisi katalogista huonomman, ei paremman:

- *Palvelut eivät kanna otsikkoa eivätkä kuvausta.* ``mapName`` on "Layers"
  ja kuvauskenttä tyhjä, joten otsikoksi jäisi palvelun tekninen nimi:
  ``20210603Maapera``, ``20221018_Mines_deposits``.
- *Hakemisto luettelee palveluja joita ei ole.* ``Korkeusmalli2018`` ja
  ``Turvevarat/202311_suotyypit`` näkyvät luettelossa mutta vastaavat
  "Service not found".
- *Kuvattu aineisto on jo katalogissa toista kautta.* GTK:lta on 53
  datasettiä, joista 30 tulee avoindata.fi:n ja 18 Paikkatietoikkunan
  kautta oikeilla suomenkielisillä otsikoilla — Kallioperä neljässä
  mittakaavassa, Maaperä neljässä, koko aerogeofysiikan sarja. Luettelointi
  lisäisi näille koneluettavat kaksoiskappaleet.
- *Loput ovat versiokopioita, työkaluja tai ulkomaisia.* 188:sta 21 on
  GPServer/GeometryServer-työkaluja ja 30:ssä on päivämääräleima.

Lista kattaa siksi ne aihealueet joilla on **oma rajapintansa ja jotka
puuttuvat muista lähteistä**. Puuttuvat tarkistettiin hakemalla katalogista
GTK:n organisaationimellä.
"""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

ARCGIS_BASE = "https://gtkdata.gtk.fi/arcgis/services/Rajapinnat"

#: REST-palvelut hakemiston muista kansioista. Näillä ei ole WFS/WMS-paria
#: ``/Rajapinnat``-kansion tapaan, joten resurssi on ArcGIS REST -palvelu.
REST_BASE = "https://gtkdata.gtk.fi/arcgis/rest/services"


class GtkHarvester(StaticHarvester):
    """Kerää GTK:n avoimet geologiset paikkatietoaineistot.

    Geologian tutkimuskeskus (GTK) tarjoaa Suomen kallioperä-, maaperä-
    ja kiviainestietoja ArcGIS-rajapintojen kautta.
    """

    name = "gtk"
    description = "Geologian tutkimuskeskus — kallioperä-, maaperä- ja kiviainestiedot"
    url = "https://www.gtk.fi/palvelut/aineistot-ja-myynti/avoimet-aineistot/"
    org_id = "gtk"
    org_name = "gtk"
    org_title = "Geologian tutkimuskeskus"
    default_update_frequency = "tarvittaessa"

    datasets_config = [
        # --- WFS + WMS -palvelut ---
        {
            "id": "gtk-kalliopera",
            "title": "Kallioperäkartta",
            "notes_fi": (
                "Suomen kallioperän geologinen kartta-aineisto."
                " Kivilajitiedot, rakennegeologia ja malmihavainnot."
            ),
            "keywords_fi": ["geologia", "kallioperä", "kivilaji", "GTK"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{ARCGIS_BASE}/GTK_Kalliopera_WFS/MapServer/WFSServer"},
                {"format": "WMS", "url": f"{ARCGIS_BASE}/GTK_Kalliopera_WFS/MapServer/WMSServer"},
            ],
        },
        {
            "id": "gtk-maapera",
            "title": "Maaperäkartta",
            "notes_fi": (
                "Suomen maaperäkartta-aineisto."
                " Maalajitiedot, kerrostumien paksuus ja pohjavesialueet."
            ),
            "keywords_fi": ["geologia", "maaperä", "maalaji", "GTK"],
            "estimated_size_bytes": 3 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{ARCGIS_BASE}/GTK_Maapera_WFS/MapServer/WFSServer"},
                {"format": "WMS", "url": f"{ARCGIS_BASE}/GTK_Maapera_WFS/MapServer/WMSServer"},
            ],
        },
        {
            "id": "gtk-kiviainesvarannot",
            "title": "Kiviainesvarannot",
            "notes_fi": "Kiviainesten (sora, hiekka, kalliokiviaines) varannot ja ottopaikat.",
            "keywords_fi": ["geologia", "kiviaines", "sora", "hiekka", "GTK"],
            "estimated_size_bytes": int(0.5 * 1024**3),
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{ARCGIS_BASE}/GTK_Kiviainesvarannot_WFS/MapServer/WFSServer",
                },
                {
                    "format": "WMS",
                    "url": f"{ARCGIS_BASE}/GTK_Kiviainesvarannot_WFS/MapServer/WMSServer",
                },
            ],
        },
        # --- WMS-only -palvelut ---
        {
            "id": "gtk-geofysiikka",
            "title": "Geofysikaaliset kartat",
            "notes_fi": (
                "Geofysikaaliset mittausaineistot: magneettiset, gravimetriset ja sähköiset kartat."
            ),
            "keywords_fi": ["geofysiikka", "magneettikenttä", "gravimetria", "GTK"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {"format": "WMS", "url": f"{ARCGIS_BASE}/geofysiikka"},
            ],
        },
        {
            "id": "gtk-pohjatutkimukset",
            "title": "Pohjatutkimukset",
            "notes_fi": (
                "Pohjatutkimusaineistot: kairaukset, näytteenotot ja laboratoriotulokset."
            ),
            "keywords_fi": ["pohjatutkimus", "kairaus", "geotekniikka", "GTK"],
            "estimated_size_bytes": int(0.5 * 1024**3),
            "resources": [
                {"format": "WMS", "url": f"{ARCGIS_BASE}/pohjatutkimukset"},
            ],
        },
        # --- Aihealueet joita ei ole muissa lähteissä (tarkistettu 16.8.2026) ---
        {
            "id": "gtk-kaavoitus",
            "title": "Kaavoituksen geologiset lähtötiedot",
            "notes_fi": (
                "Maankäytön suunnittelua palvelevat geologiset aineistot:"
                " pohjatutkimustiedot, kallionpinnan painovoimatulkinta ja"
                " muut rakennettavuuteen vaikuttavat tulkinnat. WFS tarjoaa"
                " 58 kohdetyyppiä."
            ),
            "keywords_fi": ["kaavoitus", "maankäyttö", "rakennettavuus", "geologia", "GTK"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {"format": "WFS", "url": f"{ARCGIS_BASE}/GTK_Kaavoitus_WFS/MapServer/WFSServer"},
                {"format": "WMS", "url": f"{ARCGIS_BASE}/GTK_Kaavoitus_WMS/MapServer/WMSServer"},
            ],
        },
        {
            "id": "gtk-merenpohja",
            "title": "Merenpohjan geologia",
            "notes_fi": (
                "Merenpohjan maaperä- ja kallioperäaineistot Suomen"
                " merialueilta, 17 karttatasoa. ArcGIS REST -palvelu."
            ),
            "keywords_fi": ["merenpohja", "merigeologia", "Itämeri", "merialueet", "GTK"],
            "estimated_size_bytes": int(0.5 * 1024**3),
            "resources": [
                {
                    "format": "API",
                    "name_fi": "Merenpohjan geologia — ArcGIS REST",
                    "url": f"{REST_BASE}/Maankamara/2022_Merenpohja/MapServer",
                },
            ],
        },
        {
            "id": "gtk-kaivokset",
            "title": "Kaivokset ja mineraaliesiintymät",
            "notes_fi": (
                "Suomen kaivokset, malmiaiheet ja mineraaliesiintymät"
                " tutkimustietoineen, 207 karttatasoa. ArcGIS REST -palvelu."
            ),
            "keywords_fi": ["kaivokset", "malmit", "mineraaliesiintymät", "malminetsintä", "GTK"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "API",
                    "name_fi": "Kaivokset ja esiintymät — ArcGIS REST",
                    "url": f"{REST_BASE}/MDaE/20221018_Mines_deposits/MapServer",
                },
            ],
        },
    ]
