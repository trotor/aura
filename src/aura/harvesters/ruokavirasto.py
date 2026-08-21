"""Harvester Ruokaviraston (Finnish Food Authority) aineistoille."""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

#: Ruokaviraston INSPIRE-GeoServer. Palvelu oli aiemmin jaettu
#: vuosikohtaisiin työtiloihin (``/geoserver/inspire_plohko_2024/wfs``);
#: ne vastaavat nykyään HTTP 404:llä. Aineistot ovat yhdessä
#: ``inspire``-työtilassa ja vuosi on osa tasonimeä. (16.8.2026)
#:
#: Vuoden 2020 tasot on julkaistu GetCapabilitiesissa mutta GetFeature
#: vastaa niihin HTTP 500:lla (``Error occurred getting features``)
#: kaikilla neljällä teemalla. Osoitteet on silti pidetty: ne vastaavat
#: julkaistua palvelukuvausta, ja vika on lähteen päässä. Saatavuus
#: näkyy ``health``-ajossa.
GEOSERVER_BASE = "https://inspire.ruokavirasto-awsa.com/geoserver"
WORKSPACE = "inspire"

#: Avoin tieto -sivusto on Angular-sovellus jonka osiot ovat
#: hash-reitityksen takana (``/#/osio``). Palvelin vastaa mihin tahansa
#: hash-osoitteeseen samalla sivulla, joten yksittäistä osiota ei voi
#: todentaa HTTP:llä — eikä keksiä. Aiemmat polkumuotoiset osoitteet
#: (``/elintarvikevalvonta``) vastaavat 404:llä. (16.8.2026)
AVOINTIETO_BASE = "https://avointieto.ruokavirasto.fi"


# --- Apufunktiot konfiguraation generointiin ---


def _inspire(
    type_id: str,
    title: str,
    description: str,
    keywords: list[str],
    layer: str,
) -> dict[str, Any]:
    """Luo INSPIRE-paikkatietoaineiston konfiguraatio (vuosiekspansiolla).

    ``layer`` on INSPIRE-tyyppinimi ilman vuotta, esimerkiksi
    ``LC.LandCoverSurfaces.LPIS``. Vuosi liitetään perään.
    """
    # Kaksoisaaltosulkeet {{year}} tuottavat {year}-paikkamerkin f-stringissä,
    # jonka StaticHarvester korvaa vuosinumerolla.
    tn = f"{WORKSPACE}:{layer}.{{year}}"
    return {
        "id": f"ruokavirasto-{type_id}-{{year}}",
        "title": f"{title} {{year}}",
        "notes_fi": (
            f"{description} Vuoden {{year}} aineisto."
            f" Rajapinnan tasonimi on {WORKSPACE}:{layer}.{{year}}."
        ),
        "keywords_fi": keywords,
        "years": range(2020, 2026),
        "access_level": "open",
        "resources": [
            # GetMap ilman bbox/width/height palauttaa palveluvirheen, joten
            # WMS-resurssi on GetCapabilities ja taso kerrotaan kuvauksessa.
            {
                "format": "WMS",
                "url": f"{GEOSERVER_BASE}/wms?service=WMS&version=1.3.0&request=GetCapabilities",
                "name_fi": f"{title} {{year}} — WMS",
                "description": f"Karttataso {tn}.",
            },
            {
                "format": "WFS",
                "url": (
                    f"{GEOSERVER_BASE}/wfs?service=WFS&version=2.0.0"
                    f"&request=GetFeature&typeNames={tn}"
                ),
                "name_fi": f"{title} {{year}} — WFS",
            },
            # GeoPackagea ei ole tuetuissa ulostulomuodoissa (SHAPE-ZIP,
            # json, csv), ja outputFormat=geopackage vastaa HTTP 400:lla.
            {
                "format": "GeoJSON",
                "url": (
                    f"{GEOSERVER_BASE}/wfs?service=WFS&version=2.0.0&request=GetFeature"
                    f"&typeNames={tn}&outputFormat=application/json"
                ),
                "name_fi": f"{title} {{year}} — GeoJSON",
            },
        ],
    }


def _dashboard(
    dash_id: str,
    title: str,
    description: str,
    keywords: list[str],
) -> dict[str, Any]:
    """Luo avoin tieto -dashboardin konfiguraatio."""
    return {
        "id": f"ruokavirasto-{dash_id}",
        "title": title,
        "notes_fi": description,
        "keywords_fi": keywords,
        "access_level": "open",
        "resources": [
            {
                "format": "HTML",
                "url": AVOINTIETO_BASE,
                "name_fi": f"{title} — Avoin tieto -sivusto",
                "description": (
                    "Sivusto on yksisivusovellus; aihe valitaan sivuston omasta valikosta."
                ),
            },
        ],
    }


def _restricted(
    svc_id: str,
    title: str,
    description: str,
    keywords: list[str],
) -> dict[str, Any]:
    """Luo rajoitetun rajapinnan konfiguraatio."""
    return {
        "id": f"ruokavirasto-{svc_id}",
        "title": title,
        "notes_fi": description,
        "keywords_fi": keywords,
        "license_id": "",
        "license_title": "Ei avointa lisenssiä",
        "collection_type": "Restricted Data",
        "access_level": "restricted",
        "resources": [
            {"format": "API", "url": "https://liityntakatalogi.suomi.fi"},
        ],
    }


# --- Konfiguraatiot ---

_INSPIRE_DATASETS = [
    _inspire(
        "peltolohkorekisteri",
        "Peltolohkorekisteri",
        "Maatalouden peltolohkojen rajat ja tunnistetiedot. INSPIRE-yhteensopiva aineisto.",
        ["peltolohko", "maatalous", "INSPIRE", "Ruokavirasto"],
        "LC.LandCoverSurfaces.LPIS",
    ),
    _inspire(
        "maatalousmaa",
        "Maatalousmaa",
        "Maatalouskäytössä oleva maa-ala. Sisältää viljelykasvitiedot ja tukikelpoisuuden.",
        ["maatalousmaa", "viljelykasvit", "INSPIRE", "Ruokavirasto"],
        "LandUse.ExistingLandUse.AgriculturalArea",
    ),
    _inspire(
        "kasvulohkot",
        "Kasvulohkot",
        "Maatalouden kasvulohkot viljelykasvitietoineen. Lohkokohtaiset kasvilajit ja pinta-alat.",
        ["kasvulohko", "viljely", "INSPIRE", "Ruokavirasto"],
        "LandUse.ExistingLandUse.GSAAAgriculturalParcel",
    ),
    _inspire(
        "maisemapiirteet",
        "Maisemapiirteet",
        "Maatalousympäristön maisemapiirteet: suojakaistat, pientareet"
        " ja luonnon monimuotoisuuskohteet.",
        ["maisemapiirre", "ympäristö", "INSPIRE", "Ruokavirasto"],
        "LC.LandCoverSurfaces.LPISLandscapeFeature",
    ),
]

_DASHBOARD_DATASETS = [
    _dashboard(
        "elintarvikevalvonta",
        "Elintarvikevalvonnan avoin tieto",
        "Ruokamyrkytysepidemiat, luomutoimijat ja elintarvikevalvonnan tulokset dashboardina.",
        ["elintarvikevalvonta", "ruokamyrkytys", "luomu", "Ruokavirasto"],
    ),
    _dashboard(
        "elainten-terveys",
        "Eläinten terveyden avoin tieto",
        "Mikrobilääkeresistenssi, eläintaudit ja eläinten hyvinvointitiedot.",
        ["eläinterveys", "mikrobilääkeresistenssi", "eläintauti", "Ruokavirasto"],
    ),
    _dashboard(
        "kasvinterveys",
        "Kasvinterveyden avoin tieto",
        "Tuholaisseuranta, siementen sertifiointi ja lannoitevalvonnan tulokset.",
        ["kasvinterveys", "tuholainen", "siemen", "lannoite", "Ruokavirasto"],
    ),
    _dashboard(
        "eu-tuet-varainhoitovuosi",
        "EU-tukimaksut (varainhoitovuosi)",
        "EAGF- ja EAFRD-tukimaksut varainhoitovuosittain. Tuensaajat ja maksetut tuet.",
        ["EU-tuki", "maataloustuki", "EAGF", "EAFRD", "Ruokavirasto"],
    ),
    _dashboard(
        "eu-tuet-kalenterivuosi",
        "EU-tukimaksut (kalenterivuosi)",
        "EAGF- ja EAFRD-tukimaksut kalenterivuosittain. Tuensaajat ja maksetut tuet.",
        ["EU-tuki", "maataloustuki", "EAGF", "EAFRD", "Ruokavirasto"],
    ),
]

_RESTRICTED_DATASETS = [
    _restricted(
        "elainrekisteri",
        "Eläinrekisteri",
        "Nautojen, sikojen ja lampaiden rekisteritiedot. Rajoitettu viranomaiskäyttöön.",
        ["eläinrekisteri", "nauta", "sika", "lammas", "Ruokavirasto"],
    ),
    _restricted(
        "teurastamotiedot",
        "Teurastamotiedot",
        "Teurastus- ja lihantarkastustiedot. Rajoitettu viranomaiskäyttöön.",
        ["teurastamo", "lihantarkastus", "Ruokavirasto"],
    ),
    _restricted(
        "luomutoimijarekisteri",
        "Luomutoimijarekisteri",
        "Luomutoimijoiden valvontatiedot. Rajoitettu viranomaiskäyttöön.",
        ["luomu", "luomutoimija", "valvonta", "Ruokavirasto"],
    ),
    _restricted(
        "kasvinsuojeluainerekisteri",
        "Kasvinsuojeluainerekisteri",
        "Hyväksytyt kasvinsuojeluaineet ja niiden käyttöehdot. Rajoitettu viranomaiskäyttöön.",
        ["kasvinsuojeluaine", "torjunta-aine", "Ruokavirasto"],
    ),
    _restricted(
        "rehurekisteri",
        "Rehurekisteri",
        "Rehutoimijat ja rehuvalvonnan tulokset. Rajoitettu viranomaiskäyttöön.",
        ["rehu", "rehutoimija", "valvonta", "Ruokavirasto"],
    ),
    _restricted(
        "lannoiterekisteri",
        "Lannoiterekisteri",
        "Lannoitetoimijat ja lannoitetuotteet. Rajoitettu viranomaiskäyttöön.",
        ["lannoite", "lannoitetoimija", "Ruokavirasto"],
    ),
    _restricted(
        "vierasainerekisteri",
        "Vierasainerekisteri",
        "Elintarvikkeiden vierasainevalvonnan tulokset. Rajoitettu viranomaiskäyttöön.",
        ["vierasaine", "elintarvike", "valvonta", "Ruokavirasto"],
    ),
    _restricted(
        "elintarvikehuoneistorekisteri",
        "Elintarvikehuoneistorekisteri",
        "Hyväksytyt elintarvikehuoneistot. Rajoitettu viranomaiskäyttöön.",
        ["elintarvikehuoneisto", "hyväksyntä", "Ruokavirasto"],
    ),
]


class RuokavirastoHarvester(StaticHarvester):
    """Kerää Ruokaviraston avoimet ja rajoitetut aineistot.

    Ruokavirasto (Finnish Food Authority) tarjoaa maatalouden
    paikkatietoaineistoja (INSPIRE GeoServer), avoin tieto -dashboardeja
    ja rajoitettuja viranomaiskäytön rajapintoja.
    """

    name = "ruokavirasto"
    description = "Ruokavirasto — maatalous, elintarvike- ja eläinvalvonta"
    url = "https://www.ruokavirasto.fi"
    default_update_frequency = "vuosittain"
    org_id = "ruokavirasto"
    org_name = "ruokavirasto"
    org_title = "Ruokavirasto"

    datasets_config = _INSPIRE_DATASETS + _DASHBOARD_DATASETS + _RESTRICTED_DATASETS
