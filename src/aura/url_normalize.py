"""Ilmiselvästi rikkinäisten resurssi-URL:ien normalisointi.

Aura tallentaa uskollisesti sen mitä ylävirran katalogi julkaisee, ja se on
oikea oletus: katalogi tuntee aineistonsa. Kahdessa mitatussa tapauksessa
julkaistu osoite ei kuitenkaan toimi lainkaan, jolloin aineisto näyttää
katalogissa käyttökelpoiselta vaikka ei ole — ja vika näyttää palvelun
vialta vaikka on meidän.

Probe-vaiheen ensimmäinen ajo paljasti molemmat: 151 resurssia, ja noin 26
epäonnistumista 65:stä johtui näistä.

**Jokainen sääntö on kapea ja todennettu elävää palvelua vasten.** Sääntö
osuu tarkkaan tunnettuun rikkinäiseen muotoon ja palauttaa muuten syötteen
sellaisenaan. Arvaava normalisointi rikkoisi toimivia osoitteita, mikä on
pahempi vika kuin se jota se korjaa — eikä lukija näkisi kumpi on kyseessä.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

#: stat.hel.fi:n PxWeb-selain-UI. Polun muoto on
#: ``/pxweb/<kieli>/<db>/<db>__<taso>__<taso>/<taulu>.px``, ja sama taulu on
#: API:ssa polussa ``/api/v1/<kieli>/<db>/<taso>/<taso>/<taulu>.px``.
#: Yhdistetty segmentti purkautuu, koska tietokannan nimi on jo edellisenä.
_STAT_HEL_PXWEB = re.compile(
    r"^(?P<scheme>https?)://stat\.hel\.fi/pxweb/"
    r"(?P<lang>[a-z]{2})/"
    r"(?P<db>[^/]+)/"
    r"(?P<compound>[^/]+)/"
    r"(?P<table>[^/]+\.px)/?$"
)


def _stat_hel_api_url(url: str) -> str | None:
    """Muunna stat.hel.fi:n selaus-URL API-osoitteeksi, tai None jos ei osu."""
    m = _STAT_HEL_PXWEB.match(url)
    if m is None:
        return None
    osat = m.group("compound").split("__")
    # Ensimmäinen osa on tietokannan nimi, joka on jo omana segmenttinään.
    polku = "/".join(osat[1:]) if len(osat) > 1 else ""
    if not polku:
        return None
    return (
        f"{m.group('scheme')}://stat.hel.fi/api/v1/{m.group('lang')}/"
        f"{m.group('db')}/{polku}/{m.group('table')}"
    )


def _without_port_80_on_https(url: str) -> str | None:
    """Poista portti 80 https-osoitteesta, tai None jos ei osu.

    Portti 80 https-skeemalla on aina virhe: palvelin puhuu siinä portissa
    selväkielistä HTTP:tä, ja TLS-kättely kaatuu ``WRONG_VERSION_NUMBER``-
    virheeseen. http-skeemalla sama portti on turha muttei väärä.
    """
    osat = urlsplit(url)
    if osat.scheme != "https" or not osat.netloc.endswith(":80"):
        return None
    return urlunsplit(osat._replace(netloc=osat.netloc[: -len(":80")]))


#: Säännöt sovellusjärjestyksessä. Ensimmäinen osuma voittaa.
_RULES = (
    ("stat.hel.fi PxWeb -selaussivu", _stat_hel_api_url),
    ("portti 80 https-osoitteessa", _without_port_80_on_https),
)


def normalize_resource_url(url: str | None) -> str:
    """Korjaa tunnetusti rikkinäinen resurssi-URL, tai palauta se sellaisenaan.

    Args:
        url: Ylävirran katalogin julkaisema osoite.

    Returns:
        Normalisoitu osoite, tai syöte muuttumattomana jos yksikään sääntö ei
        tunnistanut sitä. ``None`` palautuu tyhjänä merkkijonona.
    """
    if not url:
        return ""
    for nimi, saanto in _RULES:
        korjattu = saanto(url)
        if korjattu is not None and korjattu != url:
            logger.debug("[url] %s: %s -> %s", nimi, url, korjattu)
            return korjattu
    return url
