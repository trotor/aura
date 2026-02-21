"""Harvester Ruokaviraston (Finnish Food Authority) aineistoille."""

from __future__ import annotations

from typing import Any

from aura.harvesters.static import StaticHarvester

GEOSERVER_BASE = "https://inspire.ruokavirasto-awsa.com/geoserver"
GPKG_BASE = "https://inspire.ruokavirasto-awsa.com/geoserver"
AVOINTIETO_BASE = "https://avointieto.ruokavirasto.fi"


# --- Apufunktiot konfiguraation generointiin ---


def _inspire(
    type_id: str,
    title: str,
    description: str,
    keywords: list[str],
    workspace: str,
) -> dict[str, Any]:
    """Luo INSPIRE-paikkatietoaineiston konfiguraatio (vuosiekspansiolla)."""
    # Kaksoisaaltosulkeet {{year}} tuottavat {year}-paikkamerkin f-stringissä,
    # jonka StaticHarvester korvaa vuosinumerolla.
    return {
        "id": f"ruokavirasto-{type_id}-{{year}}",
        "title": f"{title} {{year}}",
        "notes_fi": f"{description} Vuoden {{year}} aineisto.",
        "keywords_fi": keywords,
        "years": range(2020, 2025),
        "access_level": "open",
        "resources": [
            {
                "format": "WMS",
                "url": f"{GEOSERVER_BASE}/{workspace}_{{year}}/wms",
            },
            {
                "format": "WFS",
                "url": f"{GEOSERVER_BASE}/{workspace}_{{year}}/wfs",
            },
            {
                "format": "GPKG",
                "url": (
                    f"{GPKG_BASE}/{workspace}_{{year}}/ows"
                    "?service=WFS&request=GetFeature&outputFormat=geopackage"
                ),
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
            {"format": "HTML", "url": f"{AVOINTIETO_BASE}/{dash_id}"},
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
        "peltolohkorekisteri", "Peltolohkorekisteri",
        "Maatalouden peltolohkojen rajat ja tunnistetiedot. INSPIRE-yhteensopiva aineisto.",
        ["peltolohko", "maatalous", "INSPIRE", "Ruokavirasto"],
        "inspire_plohko",
    ),
    _inspire(
        "maatalousmaa", "Maatalousmaa",
        "Maatalouskäytössä oleva maa-ala. Sisältää viljelykasvitiedot ja tukikelpoisuuden.",
        ["maatalousmaa", "viljelykasvit", "INSPIRE", "Ruokavirasto"],
        "inspire_maatalousmaa",
    ),
    _inspire(
        "kasvulohkot", "Kasvulohkot",
        "Maatalouden kasvulohkot viljelykasvitietoineen. Lohkokohtaiset kasvilajit ja pinta-alat.",
        ["kasvulohko", "viljely", "INSPIRE", "Ruokavirasto"],
        "inspire_kasvulohko",
    ),
    _inspire(
        "maisemapiirteet", "Maisemapiirteet",
        "Maatalousympäristön maisemapiirteet: suojakaistat, pientareet"
        " ja luonnon monimuotoisuuskohteet.",
        ["maisemapiirre", "ympäristö", "INSPIRE", "Ruokavirasto"],
        "inspire_maisemapiirre",
    ),
]

_DASHBOARD_DATASETS = [
    _dashboard(
        "elintarvikevalvonta", "Elintarvikevalvonnan avoin tieto",
        "Ruokamyrkytysepidemiat, luomutoimijat ja elintarvikevalvonnan tulokset dashboardina.",
        ["elintarvikevalvonta", "ruokamyrkytys", "luomu", "Ruokavirasto"],
    ),
    _dashboard(
        "elainten-terveys", "Eläinten terveyden avoin tieto",
        "Mikrobilääkeresistenssi, eläintaudit ja eläinten hyvinvointitiedot.",
        ["eläinterveys", "mikrobilääkeresistenssi", "eläintauti", "Ruokavirasto"],
    ),
    _dashboard(
        "kasvinterveys", "Kasvinterveyden avoin tieto",
        "Tuholaisseuranta, siementen sertifiointi ja lannoitevalvonnan tulokset.",
        ["kasvinterveys", "tuholainen", "siemen", "lannoite", "Ruokavirasto"],
    ),
    _dashboard(
        "eu-tuet-varainhoitovuosi", "EU-tukimaksut (varainhoitovuosi)",
        "EAGF- ja EAFRD-tukimaksut varainhoitovuosittain. Tuensaajat ja maksetut tuet.",
        ["EU-tuki", "maataloustuki", "EAGF", "EAFRD", "Ruokavirasto"],
    ),
    _dashboard(
        "eu-tuet-kalenterivuosi", "EU-tukimaksut (kalenterivuosi)",
        "EAGF- ja EAFRD-tukimaksut kalenterivuosittain. Tuensaajat ja maksetut tuet.",
        ["EU-tuki", "maataloustuki", "EAGF", "EAFRD", "Ruokavirasto"],
    ),
]

_RESTRICTED_DATASETS = [
    _restricted(
        "elainrekisteri", "Eläinrekisteri",
        "Nautojen, sikojen ja lampaiden rekisteritiedot. Rajoitettu viranomaiskäyttöön.",
        ["eläinrekisteri", "nauta", "sika", "lammas", "Ruokavirasto"],
    ),
    _restricted(
        "teurastamotiedot", "Teurastamotiedot",
        "Teurastus- ja lihantarkastustiedot. Rajoitettu viranomaiskäyttöön.",
        ["teurastamo", "lihantarkastus", "Ruokavirasto"],
    ),
    _restricted(
        "luomutoimijarekisteri", "Luomutoimijarekisteri",
        "Luomutoimijoiden valvontatiedot. Rajoitettu viranomaiskäyttöön.",
        ["luomu", "luomutoimija", "valvonta", "Ruokavirasto"],
    ),
    _restricted(
        "kasvinsuojeluainerekisteri", "Kasvinsuojeluainerekisteri",
        "Hyväksytyt kasvinsuojeluaineet ja niiden käyttöehdot. Rajoitettu viranomaiskäyttöön.",
        ["kasvinsuojeluaine", "torjunta-aine", "Ruokavirasto"],
    ),
    _restricted(
        "rehurekisteri", "Rehurekisteri",
        "Rehutoimijat ja rehuvalvonnan tulokset. Rajoitettu viranomaiskäyttöön.",
        ["rehu", "rehutoimija", "valvonta", "Ruokavirasto"],
    ),
    _restricted(
        "lannoiterekisteri", "Lannoiterekisteri",
        "Lannoitetoimijat ja lannoitetuotteet. Rajoitettu viranomaiskäyttöön.",
        ["lannoite", "lannoitetoimija", "Ruokavirasto"],
    ),
    _restricted(
        "vierasainerekisteri", "Vierasainerekisteri",
        "Elintarvikkeiden vierasainevalvonnan tulokset. Rajoitettu viranomaiskäyttöön.",
        ["vierasaine", "elintarvike", "valvonta", "Ruokavirasto"],
    ),
    _restricted(
        "elintarvikehuoneistorekisteri", "Elintarvikehuoneistorekisteri",
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
    org_id = "ruokavirasto"
    org_name = "ruokavirasto"
    org_title = "Ruokavirasto"

    datasets_config = _INSPIRE_DATASETS + _DASHBOARD_DATASETS + _RESTRICTED_DATASETS
