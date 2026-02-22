"""Harvester kuntien paikkatietopalveluille."""

from __future__ import annotations

from aura.harvesters.static import StaticHarvester


class KunnatHarvester(StaticHarvester):
    """Kerää kuntien WMS/WFS-paikkatietoaineistot.

    36 suomalaista kuntaa tarjoaa kartta- ja paikkatietoaineistoja
    omien rajapintojensa kautta (WMS/WFS/ArcGIS REST).
    """

    name = "kunnat"
    description = (
        "Kuntien paikkatiedot — Helsinki, Espoo, Vantaa, Tampere, Turku, Oulu, "
        "Kuopio, Jyväskylä, Lahti, Pori, Kouvola, Joensuu, Lappeenranta, "
        "Hämeenlinna, Seinäjoki, Rovaniemi, Mikkeli, Kotka, Salo, Kokkola, "
        "Hyvinkää, Rauma, Kajaani, Nurmijärvi, Kauniainen, Tuusula, Vihti, "
        "Naantali, Raisio, Kangasala, Nokia, Ylöjärvi, Lempäälä, Pirkkala, "
        "Hämeenkyrö, Orivesi"
    )
    url = "https://www.gispo.fi/blogi/avoimen-datan-wms-ja-wfs-karttapalveluita/"
    org_id = "kunnat"
    org_name = "kunnat"
    org_title = "Kuntien paikkatietopalvelut"
    default_update_frequency = "vuosittain"

    datasets_config = [
        # =====================================================================
        # Suuret kaupungit (GeoServer / TeklaOGCWeb)
        # =====================================================================
        # --- Helsinki ---
        {
            "id": "kunnat-helsinki-avoindata",
            "title": "Helsinki — avoimet paikkatiedot",
            "notes_fi": (
                "Helsingin kaupungin avoimet kartta-aineistot."
                " 461 WMS-tasoa: opaskartat, kantakartta, ortokuvat,"
                " meluselvitykset, luontotiedot, kaavahakemisto ja tilastot."
            ),
            "keywords_fi": [
                "Helsinki", "kaupunki", "kartta", "opaskartta",
                "kaava", "luonto", "meluselvitys",
            ],
            "organization_title": "Helsingin kaupunki",
            "geographical_coverage": ["Helsinki"],
            "estimated_size_bytes": 10 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartta.hel.fi/ws/geoserver/avoindata/wfs",
                },
                {
                    "format": "WMS",
                    "url": "https://kartta.hel.fi/ws/geoserver/avoindata/wms",
                },
            ],
        },
        # --- Espoo ---
        {
            "id": "kunnat-espoo-avoindata",
            "title": "Espoo — avoimet paikkatiedot",
            "notes_fi": (
                "Espoon kaupungin kartta-aineistot."
                " 130 WMS-tasoa: opaskartta, ortokuvat (1950–2024),"
                " kaavat, geologia, meluselvitykset ja ekologinen verkosto."
            ),
            "keywords_fi": [
                "Espoo", "kaupunki", "kartta", "kaava",
                "geologia", "ortokuva",
            ],
            "organization_title": "Espoon kaupunki",
            "geographical_coverage": ["Espoo"],
            "estimated_size_bytes": 5 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartat.espoo.fi/teklaogcweb/wfs.ashx",
                },
                {
                    "format": "WMS",
                    "url": "https://kartat.espoo.fi/teklaogcweb/wms.ashx",
                },
            ],
        },
        # --- Vantaa ---
        {
            "id": "kunnat-vantaa-avoindata",
            "title": "Vantaa — avoimet paikkatiedot",
            "notes_fi": (
                "Vantaan kaupungin kartta-aineistot."
                " 112 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat, kiinteistöt ja palvelupisteet."
            ),
            "keywords_fi": [
                "Vantaa", "kaupunki", "kartta",
                "kaava", "kiinteisto",
            ],
            "organization_title": "Vantaan kaupunki",
            "geographical_coverage": ["Vantaa"],
            "estimated_size_bytes": 3 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://gis.vantaa.fi/geoserver/wfs",
                },
                {
                    "format": "WMS",
                    "url": "https://gis.vantaa.fi/geoserver/wms",
                },
            ],
        },
        # --- Tampere ---
        {
            "id": "kunnat-tampere-avoindata",
            "title": "Tampere — avoimet paikkatiedot",
            "notes_fi": (
                "Tampereen kaupungin kartta-aineistot."
                " 173 WMS-tasoa: maanpeite, ilmanlaatu (NO2, PM10, PM2.5),"
                " melualueet, maankäyttö, joukkoliikenne ja luontotiedot."
            ),
            "keywords_fi": [
                "Tampere", "kaupunki", "kartta", "ilmanlaatu",
                "joukkoliikenne", "maankaytto",
            ],
            "organization_title": "Tampereen kaupunki",
            "geographical_coverage": ["Tampere"],
            "estimated_size_bytes": 5 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://geodata.tampere.fi/geoserver/ows?service=WFS",
                },
                {
                    "format": "WMS",
                    "url": "https://geodata.tampere.fi/geoserver/wms",
                },
            ],
        },
        # --- Turku ---
        {
            "id": "kunnat-turku-avoindata",
            "title": "Turku — avoimet paikkatiedot",
            "notes_fi": (
                "Turun kaupungin kartta-aineistot."
                " 68 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat ja pohjakartta."
            ),
            "keywords_fi": [
                "Turku", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Turun kaupunki",
            "geographical_coverage": ["Turku"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://opaskartta.turku.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Oulu ---
        {
            "id": "kunnat-oulu-avoindata",
            "title": "Oulu — avoimet paikkatiedot",
            "notes_fi": (
                "Oulun kaupungin kartta-aineistot."
                " 28 WMS-tasoa: opaskartta, kantakartta ja pohjakartta."
            ),
            "keywords_fi": [
                "Oulu", "kaupunki", "kartta",
            ],
            "organization_title": "Oulun kaupunki",
            "geographical_coverage": ["Oulu"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://e-kartta.ouka.fi/TeklaOgcWebOpen/WMS.ashx",
                },
            ],
        },
        # --- Kuopio ---
        {
            "id": "kunnat-kuopio-avoindata",
            "title": "Kuopio — avoimet paikkatiedot",
            "notes_fi": (
                "Kuopion kaupungin kartta-aineistot."
                " WMS- ja WFS-rajapinnat: opaskartta, kantakartta,"
                " kaavat, kiinteistöt ja maastomalli."
            ),
            "keywords_fi": [
                "Kuopio", "kaupunki", "kartta", "kaava",
                "opaskartta", "kiinteisto",
            ],
            "organization_title": "Kuopion kaupunki",
            "geographical_coverage": ["Kuopio"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://ws.kuopio.fi/wfs",
                },
                {
                    "format": "WMS",
                    "url": "https://ws.kuopio.fi/wms",
                },
            ],
        },
        # --- Jyväskylä ---
        {
            "id": "kunnat-jyvaskyla-avoindata",
            "title": "Jyväskylä — avoimet paikkatiedot",
            "notes_fi": (
                "Jyväskylän kaupungin kartta-aineistot."
                " 56 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat, ortokuvat ja pohjakartta."
            ),
            "keywords_fi": [
                "Jyväskylä", "kaupunki", "kartta", "kaava",
                "opaskartta",
            ],
            "organization_title": "Jyväskylän kaupunki",
            "geographical_coverage": ["Jyväskylä"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://jyvaskyla.asiointi.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Lahti ---
        {
            "id": "kunnat-lahti-avoindata",
            "title": "Lahti — avoimet paikkatiedot",
            "notes_fi": (
                "Lahden kaupungin kartta-aineistot."
                " 47 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat, ortokuvat ja pohjakartta."
            ),
            "keywords_fi": [
                "Lahti", "kaupunki", "kartta", "kaava",
                "opaskartta",
            ],
            "organization_title": "Lahden kaupunki",
            "geographical_coverage": ["Lahti"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://lahti.asiointi.fi/teklaogcweb/wms.ashx",
                },
            ],
        },
        # --- Pori ---
        {
            "id": "kunnat-pori-avoindata",
            "title": "Pori — avoimet paikkatiedot",
            "notes_fi": (
                "Porin kaupungin kartta-aineistot."
                " 6 WMS-tasoa: opaskartta ja pohjakartta."
            ),
            "keywords_fi": [
                "Pori", "kaupunki", "kartta", "opaskartta",
            ],
            "organization_title": "Porin kaupunki",
            "geographical_coverage": ["Pori"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kartta.pori.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Kouvola ---
        {
            "id": "kunnat-kouvola-avoindata",
            "title": "Kouvola — avoimet paikkatiedot",
            "notes_fi": (
                "Kouvolan kaupungin kartta-aineistot."
                " 12 WMS-tasoa: opaskartta, kantakartta ja kaavat."
            ),
            "keywords_fi": [
                "Kouvola", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Kouvolan kaupunki",
            "geographical_coverage": ["Kouvola"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kouvola.asiointi.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Joensuu ---
        {
            "id": "kunnat-joensuu-avoindata",
            "title": "Joensuu — avoimet paikkatiedot",
            "notes_fi": (
                "Joensuun kaupungin kartta-aineistot (GeoServer)."
                " 31 WMS-tasoa ja 23 WFS-featuretyyppiä:"
                " opaskartta, kaavat, kiinteistöt ja maankäyttö."
            ),
            "keywords_fi": [
                "Joensuu", "kaupunki", "kartta", "kaava",
                "kiinteisto", "maankaytto",
            ],
            "organization_title": "Joensuun kaupunki",
            "geographical_coverage": ["Joensuu"],
            "estimated_size_bytes": 2 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://geoserver.joensuu.fi/geoserver/ows",
                },
                {
                    "format": "WMS",
                    "url": "https://geoserver.joensuu.fi/geoserver/ows",
                },
            ],
        },
        # --- Lappeenranta ---
        {
            "id": "kunnat-lappeenranta-avoindata",
            "title": "Lappeenranta — avoimet paikkatiedot",
            "notes_fi": (
                "Lappeenrannan kaupungin kartta-aineistot."
                " 37 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat ja pohjakartta."
            ),
            "keywords_fi": [
                "Lappeenranta", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Lappeenrannan kaupunki",
            "geographical_coverage": ["Lappeenranta"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kartta.lappeenranta.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Hämeenlinna ---
        {
            "id": "kunnat-hameenlinna-avoindata",
            "title": "Hämeenlinna — avoimet paikkatiedot",
            "notes_fi": (
                "Hämeenlinnan kaupungin kartta-aineistot."
                " 18 WMS-tasoa: opaskartta, kantakartta ja kaavat."
            ),
            "keywords_fi": [
                "Hämeenlinna", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Hämeenlinnan kaupunki",
            "geographical_coverage": ["Hämeenlinna"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kartta.hameenlinna.fi/teklaogcweb/wms.ashx",
                },
            ],
        },
        # --- Seinäjoki ---
        {
            "id": "kunnat-seinajoki-avoindata",
            "title": "Seinäjoki — avoimet paikkatiedot",
            "notes_fi": (
                "Seinäjoen kaupungin kartta-aineistot."
                " 16 WMS-tasoa: opaskartta, kantakartta ja kaavat."
            ),
            "keywords_fi": [
                "Seinäjoki", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Seinäjoen kaupunki",
            "geographical_coverage": ["Seinäjoki"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kartat.seinajoki.fi/teklaogcweb/wms.ashx",
                },
            ],
        },
        # --- Rovaniemi ---
        {
            "id": "kunnat-rovaniemi-avoindata",
            "title": "Rovaniemi — avoimet paikkatiedot",
            "notes_fi": (
                "Rovaniemen kaupungin kartta-aineistot."
                " 22 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat ja pohjakartta."
            ),
            "keywords_fi": [
                "Rovaniemi", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Rovaniemen kaupunki",
            "geographical_coverage": ["Rovaniemi"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://rovaniemi.asiointi.fi/teklaogcweb/WMS.ashx",
                },
            ],
        },
        # --- Mikkeli ---
        {
            "id": "kunnat-mikkeli-avoindata",
            "title": "Mikkeli — avoimet paikkatiedot",
            "notes_fi": (
                "Mikkelin kaupungin kartta-aineistot."
                " 3 WMS-tasoa: opaskartta ja pohjakartta."
            ),
            "keywords_fi": [
                "Mikkeli", "kaupunki", "kartta",
            ],
            "organization_title": "Mikkelin kaupunki",
            "geographical_coverage": ["Mikkeli"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://mikkeli.asiointi.fi/teklaogcweb/wms.ashx",
                },
            ],
        },
        # --- Kotka ---
        {
            "id": "kunnat-kotka-avoindata",
            "title": "Kotka — avoimet paikkatiedot",
            "notes_fi": (
                "Kotkan kaupungin kartta-aineistot (GeoServer)."
                " 22 WMS-tasoa ja 21 WFS-featuretyyppiä:"
                " opaskartta, kaavat, kiinteistöt ja infrastruktuuri."
            ),
            "keywords_fi": [
                "Kotka", "kaupunki", "kartta", "kaava",
                "kiinteisto",
            ],
            "organization_title": "Kotkan kaupunki",
            "geographical_coverage": ["Kotka"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://avoindata.kotka.fi:8443/geoserver/KOTKA/wfs",
                },
                {
                    "format": "WMS",
                    "url": "https://avoindata.kotka.fi:8443/geoserver/KOTKA/wms",
                },
            ],
        },
        # --- Salo ---
        {
            "id": "kunnat-salo-avoindata",
            "title": "Salo — avoimet paikkatiedot",
            "notes_fi": (
                "Salon kaupungin kartta-aineistot."
                " 11 WMS-tasoa: opaskartta, kantakartta ja kaavat."
            ),
            "keywords_fi": [
                "Salo", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Salon kaupunki",
            "geographical_coverage": ["Salo"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartta.salo.fi/TeklaOGCWeb/wfs.ashx",
                },
                {
                    "format": "WMS",
                    "url": "https://kartta.salo.fi/TeklaOGCWeb/wms.ashx",
                },
            ],
        },
        # --- Kokkola ---
        {
            "id": "kunnat-kokkola-avoindata",
            "title": "Kokkola — avoimet paikkatiedot",
            "notes_fi": (
                "Kokkolan kaupungin kartta-aineistot."
                " 38 WMS-tasoa: opaskartta, kantakartta,"
                " kaavat ja ortokuvat."
            ),
            "keywords_fi": [
                "Kokkola", "kaupunki", "kartta", "kaava",
                "ortokuva",
            ],
            "organization_title": "Kokkolan kaupunki",
            "geographical_coverage": ["Kokkola"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kokkola.asiointi.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # --- Hyvinkää ---
        {
            "id": "kunnat-hyvinkaa-avoindata",
            "title": "Hyvinkää — avoimet paikkatiedot",
            "notes_fi": (
                "Hyvinkään kaupungin kartta-aineistot."
                " 262 WMS-tasoa: opaskartta, kantakartta, kaavat,"
                " ortokuvat, johtotiedot ja maastomalli."
            ),
            "keywords_fi": [
                "Hyvinkää", "kaupunki", "kartta", "kaava",
                "opaskartta", "ortokuva",
            ],
            "organization_title": "Hyvinkään kaupunki",
            "geographical_coverage": ["Hyvinkää"],
            "estimated_size_bytes": 3 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kartta.hyvinkaa.fi/ows/ows.ashx",
                },
            ],
        },
        # --- Rauma ---
        {
            "id": "kunnat-rauma-avoindata",
            "title": "Rauma — avoimet paikkatiedot",
            "notes_fi": (
                "Rauman kaupungin kartta-aineistot."
                " 23 WMS-tasoa: opaskartta, kantakartta ja kaavat."
            ),
            "keywords_fi": [
                "Rauma", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Rauman kaupunki",
            "geographical_coverage": ["Rauma"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://opaskartta.rauma.fi/TeklaOgcWeb/WMS.ashx",
                },
            ],
        },
        # --- Kajaani ---
        {
            "id": "kunnat-kajaani-avoindata",
            "title": "Kajaani — avoimet paikkatiedot",
            "notes_fi": (
                "Kajaanin kaupungin kartta-aineistot."
                " 25 WMS-tasoa: opaskartta, kantakartta ja kaavat."
            ),
            "keywords_fi": [
                "Kajaani", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Kajaanin kaupunki",
            "geographical_coverage": ["Kajaani"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kajaani.asiointi.fi/teklaogcweb/WMS.ashx",
                },
            ],
        },
        # =====================================================================
        # Uudet kunnat — Uusimaa / pääkaupunkiseutu
        # =====================================================================
        # --- Kauniainen ---
        {
            "id": "kunnat-kauniainen-avoindata",
            "title": "Kauniainen — avoimet paikkatiedot",
            "notes_fi": (
                "Kauniaisten kaupungin kartta-aineistot."
                " 5 WMS-tasoa: opaskartta, osoitekartta, ortokuva,"
                " ajantasa-asemakaava ja yksinkertaistettu pohjakartta."
            ),
            "keywords_fi": [
                "Kauniainen", "kaupunki", "kartta", "kaava",
                "opaskartta",
            ],
            "organization_title": "Kauniaisten kaupunki",
            "geographical_coverage": ["Kauniainen"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartat.kauniainen.fi/teklaOgcWeb/WFS.ashx",
                },
                {
                    "format": "WMS",
                    "url": "https://kartat.kauniainen.fi/teklaOgcWeb/WMS.ashx",
                },
            ],
        },
        # --- Nurmijärvi ---
        {
            "id": "kunnat-nurmijarvi-avoindata",
            "title": "Nurmijärvi — avoimet paikkatiedot",
            "notes_fi": (
                "Nurmijärven kunnan kartta-aineistot."
                " WMS-tasoja: opaskartta, ilmakuva, ajantasa-asemakaava,"
                " maastokartta ja rakennusrajoitukset."
            ),
            "keywords_fi": [
                "Nurmijärvi", "kunta", "kartta", "kaava",
                "opaskartta",
            ],
            "organization_title": "Nurmijärven kunta",
            "geographical_coverage": ["Nurmijärvi"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://kartta.nurmijarvi.fi/TeklaOGCWeb/wms.ashx",
                },
            ],
        },
        # --- Tuusula ---
        {
            "id": "kunnat-tuusula-avoindata",
            "title": "Tuusula — avoimet paikkatiedot",
            "notes_fi": (
                "Tuusulan kunnan kartta-aineistot."
                " WMS/WFS-rajapinta: kaava-alueet, kaavamääräykset,"
                " kaavarekisteri, ilmanlaatu ja opaskartta."
            ),
            "keywords_fi": [
                "Tuusula", "kunta", "kartta", "kaava",
                "ilmanlaatu",
            ],
            "organization_title": "Tuusulan kunta",
            "geographical_coverage": ["Tuusula"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartta.tuusula.fi/tuusula_rajapintapalvelu/ows.ashx",
                },
                {
                    "format": "WMS",
                    "url": "https://kartta.tuusula.fi/tuusula_rajapintapalvelu/ows.ashx",
                },
            ],
        },
        # --- Vihti ---
        {
            "id": "kunnat-vihti-avoindata",
            "title": "Vihti — avoimet paikkatiedot",
            "notes_fi": (
                "Vihdin kunnan kartta-aineistot."
                " 7 WMS-tasoa ja 67 WFS-featuretyyppiä: ortokuvat,"
                " kaavoituskartat, infrastruktuuri, rakennukset ja osoitteet."
            ),
            "keywords_fi": [
                "Vihti", "kunta", "kartta", "kaava",
                "ortokuva", "infrastruktuuri",
            ],
            "organization_title": "Vihdin kunta",
            "geographical_coverage": ["Vihti"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartta.vihti.fi/TeklaOgcWeb/WFS.ashx",
                },
                {
                    "format": "WMS",
                    "url": "https://kartta.vihti.fi/TeklaOGCWeb/WMS.ashx",
                },
            ],
        },
        # =====================================================================
        # Uudet kunnat — Varsinais-Suomi
        # =====================================================================
        # --- Naantali ---
        {
            "id": "kunnat-naantali-avoindata",
            "title": "Naantali — avoimet paikkatiedot",
            "notes_fi": (
                "Naantalin kaupungin kartta-aineistot."
                " 7 WMS-tasoa: asemakaavat ja muut kaavoitusaineistot."
            ),
            "keywords_fi": [
                "Naantali", "kaupunki", "kartta", "kaava",
            ],
            "organization_title": "Naantalin kaupunki",
            "geographical_coverage": ["Naantali"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WMS",
                    "url": "http://kartta.naantali.fi:8080/NaantaliWMS.mapdef",
                },
            ],
        },
        # --- Raisio ---
        {
            "id": "kunnat-raisio-avoindata",
            "title": "Raisio — avoimet paikkatiedot",
            "notes_fi": (
                "Raision kaupungin kartta-aineistot (ArcGIS)."
                " Ajantasa-asemakaavat, maanomistus, osoitteet,"
                " osoitekartat, pohjakartat, vesihuoltoalueet ja yleiskaavat."
            ),
            "keywords_fi": [
                "Raisio", "kaupunki", "kartta", "kaava",
                "yleiskaava",
            ],
            "organization_title": "Raision kaupunki",
            "geographical_coverage": ["Raisio"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": "https://kartta.raisio.fi/arcgis/services/inspire/Raision_WFS/MapServer/WFSServer",
                },
            ],
        },
        # =====================================================================
        # Uudet kunnat — Pirkanmaa (pirnet.fi ArcGIS -klusteri)
        # =====================================================================
        # --- Kangasala ---
        {
            "id": "kunnat-kangasala-avoindata",
            "title": "Kangasala — avoimet paikkatiedot",
            "notes_fi": (
                "Kangasalan kaupungin kartta-aineistot (ArcGIS REST)."
                " 18 palvelua: opaskartta, pohjakartta, asemakaavat,"
                " liikenneväylät, virkistysreitit, vieraslajit ja tontti-inventaario."
            ),
            "keywords_fi": [
                "Kangasala", "kaupunki", "kartta", "kaava",
                "opaskartta", "virkistysreitit",
            ],
            "organization_title": "Kangasalan kaupunki",
            "geographical_coverage": ["Kangasala"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/services/kangasala/opaskartta/MapServer/WmsServer",
                },
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/kangasala",
                    "name_fi": "Kangasala — ArcGIS REST -rajapinta",
                },
            ],
        },
        # --- Nokia ---
        {
            "id": "kunnat-nokia-avoindata",
            "title": "Nokia — avoimet paikkatiedot",
            "notes_fi": (
                "Nokian kaupungin kartta-aineistot (ArcGIS REST)."
                " Opaskartta ja aluejaot."
            ),
            "keywords_fi": [
                "Nokia", "kaupunki", "kartta", "opaskartta",
            ],
            "organization_title": "Nokian kaupunki",
            "geographical_coverage": ["Nokia"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/services/nokia/Opaskartta2021/MapServer/WmsServer",
                },
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/nokia",
                    "name_fi": "Nokia — ArcGIS REST -rajapinta",
                },
            ],
        },
        # --- Ylöjärvi ---
        {
            "id": "kunnat-ylojarvi-avoindata",
            "title": "Ylöjärvi — avoimet paikkatiedot",
            "notes_fi": (
                "Ylöjärven kaupungin kartta-aineistot (ArcGIS REST)."
                " 17 palvelua: pohjakartta, kaavaindeksi, ajantasa-asemakaava,"
                " kiinteistökartta, opaskartta, maanomistus, vesihuolto ja tonttivaranto."
            ),
            "keywords_fi": [
                "Ylöjärvi", "kaupunki", "kartta", "kaava",
                "kiinteisto", "vesihuolto",
            ],
            "organization_title": "Ylöjärven kaupunki",
            "geographical_coverage": ["Ylöjärvi"],
            "estimated_size_bytes": 1 * 1024**3,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/services/ylojarvi/ylojarvi_ajantasa_asemakaava/MapServer/WmsServer",
                },
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/ylojarvi",
                    "name_fi": "Ylöjärvi — ArcGIS REST -rajapinta",
                },
            ],
        },
        # --- Lempäälä ---
        {
            "id": "kunnat-lempaala-avoindata",
            "title": "Lempäälä — avoimet paikkatiedot",
            "notes_fi": (
                "Lempäälän kunnan kartta-aineistot (ArcGIS REST)."
                " 7 palvelua: kaavayhdistelmä, kaavarajat, kantakartta,"
                " kiintopisteet, maanomistus, tonttivaranto ja yleiskaavayhdistelmä."
            ),
            "keywords_fi": [
                "Lempäälä", "kunta", "kartta", "kaava",
                "kantakartta",
            ],
            "organization_title": "Lempäälän kunta",
            "geographical_coverage": ["Lempäälä"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/services/lempaala/lempaala_kantakartta/MapServer/WmsServer",
                },
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/lempaala",
                    "name_fi": "Lempäälä — ArcGIS REST -rajapinta",
                },
            ],
        },
        # --- Pirkkala ---
        {
            "id": "kunnat-pirkkala-avoindata",
            "title": "Pirkkala — avoimet paikkatiedot",
            "notes_fi": (
                "Pirkkalan kunnan kartta-aineistot (ArcGIS REST)."
                " 10 palvelua: asema- ja yleiskaavat, aurauskartta,"
                " meluselvitys, mikroliikkuminen, koulupiirit, palvelut,"
                " tilastoalueet, tonttivaranto ja uimarannat."
            ),
            "keywords_fi": [
                "Pirkkala", "kunta", "kartta", "kaava",
                "meluselvitys", "koulupiirit",
            ],
            "organization_title": "Pirkkalan kunta",
            "geographical_coverage": ["Pirkkala"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WMS",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/services/pirkkala/Asema_ja_yleiskaavat/MapServer/WmsServer",
                },
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/pirkkala",
                    "name_fi": "Pirkkala — ArcGIS REST -rajapinta",
                },
            ],
        },
        # --- Hämeenkyrö ---
        {
            "id": "kunnat-hameenkyro-avoindata",
            "title": "Hämeenkyrö — avoimet paikkatiedot",
            "notes_fi": (
                "Hämeenkyrön kunnan kartta-aineistot (ArcGIS REST)."
                " Paikkatietopalvelu Pirnet-klusterin kautta."
            ),
            "keywords_fi": [
                "Hämeenkyrö", "kunta", "kartta",
            ],
            "organization_title": "Hämeenkyrön kunta",
            "geographical_coverage": ["Hämeenkyrö"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/hameenkyro",
                    "name_fi": "Hämeenkyrö — ArcGIS REST -rajapinta",
                },
            ],
        },
        # --- Orivesi ---
        {
            "id": "kunnat-orivesi-avoindata",
            "title": "Orivesi — avoimet paikkatiedot",
            "notes_fi": (
                "Oriveden kaupungin kartta-aineistot (ArcGIS REST)."
                " Paikkatietopalvelu Pirnet-klusterin kautta."
            ),
            "keywords_fi": [
                "Orivesi", "kaupunki", "kartta",
            ],
            "organization_title": "Oriveden kaupunki",
            "geographical_coverage": ["Orivesi"],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "API",
                    "url": "https://paikkatietopalvelu.pirnet.fi/arcgis/rest/services/orivesi",
                    "name_fi": "Orivesi — ArcGIS REST -rajapinta",
                },
            ],
        },
    ]
