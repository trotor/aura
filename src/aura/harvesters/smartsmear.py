"""Harvester SmartSMEAR-mittausasemien avoimelle datalle."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester

SMEAR_API = "https://smear-backend.rahtiapp.fi/search/timeseries"
SMEAR_PORTAL = "https://smear.avaa.csc.fi/"


class SmartSmearHarvester(StaticHarvester):
    """Kerää SmartSMEAR-mittausasemien datasetit.

    SmartSMEAR (HY/INAR + CSC) tarjoaa jatkuvaa ilmakehä-, ekosysteemi-,
    maaperä- ja puustomittausdataa SMEAR-asemaverkostosta REST API:n kautta.
    Yksi datasetti per mittausasema parantaa alueellista löydettävyyttä.
    """

    name = "smartsmear"
    description = "SmartSMEAR — SMEAR-asemaverkoston mittausdata (HY/INAR + CSC)"
    url = SMEAR_PORTAL
    org_id = "hy-inar"
    org_name = "hy-inar"
    org_title = "Helsingin yliopisto / INAR"
    default_update_frequency = "reaaliaikainen"

    datasets_config = [
        {
            "id": "smartsmear-hyytiaelae",
            "title": "SMEAR II Hyytiälä — ilmakehä- ja ekosysteemimittaukset",
            "notes_fi": (
                "SMEAR II on Helsingin yliopiston lippulaiva-asema Hyytiälän"
                " metsäasemalla Juupajoella. Jatkuvia mittauksia vuodesta 1996:"
                " ilmakehän kaasu- ja aerosolipitoisuudet, eddy covariance"
                " -hiili- ja energiavuot, maaperän lämpötila ja kosteus,"
                " puufysiologia (ksyleemi- ja niläsädevirtaus), sekä"
                " meteorologiset perusmuuttujat."
            ),
            "keywords_fi": [
                "SMEAR", "ilmakehä", "aerosoli", "eddy covariance",
                "hiilidioksidi", "metsä", "ekosysteemi", "maaperä",
                "puufysiologia", "Hyytiälä",
            ],
            "geographical_coverage": ["Juupajoki", "Pirkanmaa"],
            "resources": [
                {
                    "id": "smartsmear-hyytiaelae-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — SMEAR II Hyytiälä",
                },
                {
                    "id": "smartsmear-hyytiaelae-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Hyytiälä",
                },
            ],
        },
        {
            "id": "smartsmear-vaerrioe",
            "title": "SMEAR I Värriö — arktisen ilmakehän mittaukset",
            "notes_fi": (
                "SMEAR I on Helsingin yliopiston arktinen tausta-asema"
                " Sallan Värriössä Itä-Lapissa. Mittauksia vuodesta 1992:"
                " ilmakehän kaasupitoisuudet (O₃, SO₂, NOₓ, CO₂),"
                " aerosolihiukkaspitoisuudet ja -kokojakaumat sekä"
                " meteorologiset perusmuuttujat."
            ),
            "keywords_fi": [
                "SMEAR", "ilmakehä", "aerosoli", "arktinen",
                "tausta-asema", "Värriö", "Lappi",
            ],
            "geographical_coverage": ["Salla", "Lappi"],
            "resources": [
                {
                    "id": "smartsmear-vaerrioe-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — SMEAR I Värriö",
                },
                {
                    "id": "smartsmear-vaerrioe-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Värriö",
                },
            ],
        },
        {
            "id": "smartsmear-kumpula",
            "title": "SMEAR III Kumpula — kaupunki-ilmakehän mittaukset",
            "notes_fi": (
                "SMEAR III sijaitsee Helsingin Kumpulassa Ilmatieteen"
                " laitoksen ja Helsingin yliopiston kampuksella."
                " Kaupunkiympäristön mittauksia: ilmakehän kaasu- ja"
                " aerosolipitoisuudet, hiukkaskokojakaumat,"
                " säteilymittaukset sekä meteorologia."
            ),
            "keywords_fi": [
                "SMEAR", "ilmakehä", "aerosoli", "kaupunki",
                "ilmanlaatu", "säteily", "Helsinki", "Kumpula",
            ],
            "geographical_coverage": ["Helsinki"],
            "resources": [
                {
                    "id": "smartsmear-kumpula-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — SMEAR III Kumpula",
                },
                {
                    "id": "smartsmear-kumpula-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Kumpula",
                },
            ],
        },
        {
            "id": "smartsmear-kuopio",
            "title": "SMEAR IV Kuopio — ilmakehä- ja metsämittaukset",
            "notes_fi": (
                "SMEAR IV sijaitsee Itä-Suomen yliopiston Kuopion"
                " kampuksella. Mittauksia: ilmakehän kaasu- ja"
                " aerosolipitoisuudet, hiukkaskokojakaumat sekä"
                " puustomittaukset."
            ),
            "keywords_fi": [
                "SMEAR", "ilmakehä", "aerosoli", "metsä",
                "puusto", "Kuopio",
            ],
            "geographical_coverage": ["Kuopio"],
            "resources": [
                {
                    "id": "smartsmear-kuopio-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — SMEAR IV Kuopio",
                },
                {
                    "id": "smartsmear-kuopio-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Kuopio",
                },
            ],
        },
        {
            "id": "smartsmear-siikaneva",
            "title": "Siikaneva — suoekosysteemin mittaukset",
            "notes_fi": (
                "Siikanevan suomittausasema sijaitsee Ruovedellä"
                " Pirkanmaalla. Mittauksia: suoekosysteemin CH₄- ja"
                " CO₂-vuot (eddy covariance ja kammiomittaukset),"
                " vedenpinnan taso, maaperän lämpötila ja kosteus."
            ),
            "keywords_fi": [
                "SMEAR", "suo", "metaani", "hiilidioksidi",
                "eddy covariance", "ekosysteemi", "turve", "Siikaneva",
            ],
            "geographical_coverage": ["Ruovesi", "Pirkanmaa"],
            "resources": [
                {
                    "id": "smartsmear-siikaneva-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — Siikaneva",
                },
                {
                    "id": "smartsmear-siikaneva-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Siikaneva",
                },
            ],
        },
        {
            "id": "smartsmear-kuivajaervi",
            "title": "Kuivajärvi — järviekosysteemin mittaukset",
            "notes_fi": (
                "Kuivajärven mittausasema sijaitsee Juupajoella"
                " Pirkanmaalla lähellä Hyytiälän metsäasemaa."
                " Mittauksia: järven CO₂- ja CH₄-vuot, veden"
                " lämpötilaprofiili, liuennut happi sekä"
                " meteorologiset muuttujat."
            ),
            "keywords_fi": [
                "SMEAR", "järvi", "hiilidioksidi", "metaani",
                "eddy covariance", "veden lämpötila", "Kuivajärvi",
            ],
            "geographical_coverage": ["Juupajoki", "Pirkanmaa"],
            "resources": [
                {
                    "id": "smartsmear-kuivajaervi-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — Kuivajärvi",
                },
                {
                    "id": "smartsmear-kuivajaervi-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Kuivajärvi",
                },
            ],
        },
        {
            "id": "smartsmear-qvidja",
            "title": "Qvidja — maatalousekosysteemin mittaukset",
            "notes_fi": (
                "Qvidjan mittausasema sijaitsee Paraisilla"
                " Varsinais-Suomessa. Maatalousekosysteemin"
                " mittauksia: CO₂- ja N₂O-vuot (eddy covariance),"
                " maaperän lämpötila ja kosteus sekä"
                " meteorologiset muuttujat."
            ),
            "keywords_fi": [
                "SMEAR", "maatalous", "hiilidioksidi",
                "dityppioksidi", "eddy covariance",
                "pelto", "Qvidja",
            ],
            "geographical_coverage": ["Parainen", "Varsinais-Suomi"],
            "resources": [
                {
                    "id": "smartsmear-qvidja-api",
                    "format": "API",
                    "url": SMEAR_API,
                    "name_fi": "SmartSMEAR API — Qvidja",
                },
                {
                    "id": "smartsmear-qvidja-html",
                    "format": "HTML",
                    "url": SMEAR_PORTAL,
                    "name_fi": "SmartSMEAR-portaali — Qvidja",
                },
            ],
        },
    ]
