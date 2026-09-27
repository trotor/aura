"""Harvester Tilastokeskuksen paikkatietoaineistoille (GeoServer WMS/WFS)."""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from aura.harvesters.static import StaticHarvester
from aura.wfs import parse_capabilities

logger = logging.getLogger(__name__)

GEOSERVER_BASE = "https://geo.stat.fi/geoserver"

#: Paavon uusin tilastokerros ``postialue:pno_tilasto_<vuosi>``, jos
#: GetCapabilities ei vastaa keruun aikana (tarkistettu 27.9.2026: 2026).
PAAVO_FALLBACK_YEAR = 2026

_PAAVO_STATS_LAYER = re.compile(r"^postialue:pno_tilasto_(\d{4})$")


class StatfinGeoHarvester(StaticHarvester):
    """Kerää Tilastokeskuksen avoimet paikkatietoaineistot.

    Tilastokeskus tarjoaa väestö-, alue- ja tilastoruutuaineistoja
    GeoServer-rajapinnan (WFS/WMS) kautta osoitteessa geo.stat.fi.
    """

    name = "statfin-geo"
    description = "Tilastokeskus — paikkatietoaineistot (WMS/WFS)"
    url = "https://www.stat.fi/org/avoindata/paikkatietoaineistot.html"
    org_id = "tilastokeskus"
    org_name = "tilastokeskus"
    org_title = "Tilastokeskus"
    default_update_frequency = "vuosittain"

    async def harvest(self) -> int:
        """Kerää konfiguraatio; Paavoon lisätään uusimman vuoden tilastokerros.

        Ulkoinen arvio 27.9.2026: Paavon ainoa WFS-resurssi oli ilman
        kerrosta, joten kysely osui palvelun ensimmäiseen kerrokseen
        (``postialue:pno``, pelkät rajat) eikä tunnuslukuihin. Tunnusluvut
        ovat kerroksissa ``postialue:pno_tilasto_<vuosi>``; uusin vuosi
        luetaan kyvyistä, jotta resurssi ei vanhene vuoden vaihtuessa.
        """
        year = await self._latest_paavo_year()
        self.datasets_config = [
            self._paavo_config(cfg, year) if cfg["id"] == "statfin-geo-paavo" else cfg
            for cfg in type(self).datasets_config
        ]
        return await super().harvest()

    async def _latest_paavo_year(self) -> int:
        """Uusin ``pno_tilasto_<vuosi>``-kerros GetCapabilitiesista, tai varavuosi."""
        try:
            async with self._make_client(timeout=30.0) as client:
                resp = await self._fetch(
                    client,
                    f"{GEOSERVER_BASE}/postialue/wfs",
                    params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
                )
            years = [
                int(m.group(1))
                for name in parse_capabilities(resp.text).feature_types
                if (m := _PAAVO_STATS_LAYER.match(name))
            ]
        except Exception as exc:  # noqa: BLE001 — varavuosi riittää, keruu ei kaadu
            logger.warning(
                "[%s] Paavon kerroksia ei saatu (%s); vuosi %d", self.name, exc, PAAVO_FALLBACK_YEAR
            )
            return PAAVO_FALLBACK_YEAR
        if not years:
            logger.warning(
                "[%s] Paavon tilastokerroksia ei löytynyt; vuosi %d", self.name, PAAVO_FALLBACK_YEAR
            )
            return PAAVO_FALLBACK_YEAR
        return max(years)

    @staticmethod
    def _paavo_config(cfg: dict[str, Any], year: int) -> dict[str, Any]:
        """Paavon konfiguraatio tilastokerroksen resurssilla (ensimmäisenä).

        Tilastokerros on ensimmäinen, koska kyselyn oletusvalinta ottaa
        ensimmäisen kyseltävän resurssin — ja postinumerokysymys koskee
        lähes aina tunnuslukuja, ei rajoja.
        """
        out = copy.deepcopy(cfg)
        layer = f"postialue:pno_tilasto_{year}"
        stats = {
            "id": "statfin-geo-paavo-wfs-tilasto",
            "format": "WFS",
            "url": f"{GEOSERVER_BASE}/postialue/wfs?service=WFS&typeName={layer}",
            "name": f"Paavo-tunnusluvut {year} (WFS)",
            "name_fi": f"Paavo-tunnusluvut {year} (WFS)",
        }
        out["resources"] = [stats, *out["resources"]]
        out["notes_fi"] = (
            f"{cfg['notes_fi']} Tunnusluvut kerroksessa {layer} (postinumerokenttä"
            " postinumeroalue): he_vakiy väkiluku, he_kika keski-ikä, hr_mtu"
            " asukkaiden mediaanitulot, te_taly taloudet, ra_asunn asunnot,"
            " tp_tyopy työpaikat, pt_tyott työttömät. Kerros postialue:pno on"
            " pelkät rajat; aiemmat vuodet kerroksissa pno_tilasto_<vuosi>."
        )
        return out

    datasets_config = [
        {
            "id": "statfin-geo-tilastointialueet",
            "title": "Kuntapohjaiset tilastointialueet",
            "notes_fi": (
                "Suomen kuntapohjaiset tilastolliset aluejaot: seutukunnat,"
                " maakunnat, suuralue, ELY-keskukset ja AVI-alueet."
                " Aluejaot muuttuvat kuntaliitoksissa."
            ),
            "keywords_fi": [
                "tilastointialue",
                "aluejako",
                "seutukunta",
                "maakunta",
                "hallinnollinen raja",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-vaestoalue",
            "title": "Väestö tilastointialueittain",
            "notes_fi": (
                "Väestötiedot tilastollisilla aluejaotuksilla:"
                " ikärakenne, sukupuoli ja kieli alueittain."
            ),
            "keywords_fi": [
                "väestö",
                "tilastointialue",
                "ikärakenne",
                "sukupuolijakauma",
            ],
            "estimated_size_bytes": 100 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/vaestoalue/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/vaestoalue/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-paavo",
            "title": "Paavo — postinumeroalueittainen avoin tieto",
            "notes_fi": (
                "Paavo-aineisto sisältää postinumeroalueittain väestörakenteen,"
                " koulutusasteen, tulotason, asumisen ja työllisyyden tietoja."
            ),
            "keywords_fi": [
                "paavo",
                "postinumero",
                "postinumeroalue",
                "väestörakenne",
                "tulotaso",
            ],
            "estimated_size_bytes": 200 * 1024**2,
            # Tilastokerroksen resurssi lisätään keruussa (_paavo_config):
            # uusin vuosi luetaan palvelun kyvyistä.
            "resources": [
                {
                    "id": "statfin-geo-paavo-wfs",
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/postialue/wfs",
                    "name_fi": "Paavo — postinumeroalueiden rajat ja vuosikerrokset (WFS)",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/postialue/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-vaestoruutu-1km",
            "title": "Väestöruutuaineisto 1 km x 1 km",
            "notes_fi": (
                "Väestötiedot 1 km x 1 km tilastoruuduissa."
                " Asukasmäärä, ikärakenne ja asuntokunnat ruuduittain."
            ),
            "keywords_fi": [
                "väestöruutu",
                "ruutudata",
                "1km",
                "väestötiheys",
                "asuntokunnat",
            ],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-vaestoruutu-5km",
            "title": "Väestöruutuaineisto 5 km x 5 km",
            "notes_fi": (
                "Väestötiedot 5 km x 5 km tilastoruuduissa."
                " Karkea ruutukoko koko Suomen kattaviin analyyseihin."
            ),
            "keywords_fi": [
                "väestöruutu",
                "ruutudata",
                "5km",
                "väestötiheys",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/vaestoruutu/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-tilastoruudukko-1km",
            "title": "Tilastoruudukko 1 km x 1 km",
            "notes_fi": (
                "Tilastoruudukko 1 km x 1 km: työpaikat, rakennukset"
                " ja yritystoimipaikat ruuduittain."
            ),
            "keywords_fi": [
                "tilastoruudukko",
                "ruutudata",
                "1km",
                "työpaikat",
                "rakennukset",
            ],
            "estimated_size_bytes": 500 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-tilastoruudukko-5km",
            "title": "Tilastoruudukko 5 km x 5 km",
            "notes_fi": (
                "Tilastoruudukko 5 km x 5 km: työpaikat, rakennukset"
                " ja yritystoimipaikat karkeammalla ruutujaolla."
            ),
            "keywords_fi": [
                "tilastoruudukko",
                "ruutudata",
                "5km",
                "työpaikat",
                "rakennukset",
            ],
            "estimated_size_bytes": 50 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tilastointialueet/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-tieliikenne",
            "title": "Tieliikenneonnettomuudet",
            "notes_fi": (
                "Poliisin tietoon tulleet tieliikenneonnettomuudet"
                " sijaintitietoineen. Sisältää onnettomuustyypin,"
                " osalliset ja vakavuuden."
            ),
            "keywords_fi": [
                "tieliikenne",
                "onnettomuus",
                "liikenneonnettomuus",
                "liikenneturvallisuus",
            ],
            "estimated_size_bytes": 100 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/tieliikenne/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/tieliikenne/wms",
                },
            ],
        },
        {
            "id": "statfin-geo-oppilaitokset",
            "title": "Oppilaitokset",
            "notes_fi": (
                "Suomen oppilaitosten sijaintitiedot."
                " Kattaa peruskoulut, lukiot, ammatilliset oppilaitokset"
                " ja korkeakoulut."
            ),
            "keywords_fi": [
                "oppilaitokset",
                "koulut",
                "koulutus",
                "sijaintitieto",
            ],
            "estimated_size_bytes": 10 * 1024**2,
            "resources": [
                {
                    "format": "WFS",
                    "url": f"{GEOSERVER_BASE}/oppilaitokset/wfs",
                },
                {
                    "format": "WMS",
                    "url": f"{GEOSERVER_BASE}/oppilaitokset/wms",
                },
            ],
        },
    ]
