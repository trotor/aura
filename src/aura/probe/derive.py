"""Vastauskoodista johdetut kentät.

auth_method ei ansaitse omaa kutsuaan: muut proberit tekevät saman pyynnön
joka tapauksessa, ja erillinen HEAD jokaiselle resurssille
kaksinkertaistaisi liikenteen kertomatta mitään uutta.
"""

from __future__ import annotations

from urllib.parse import urlparse

#: Osoitteen polkuosassa esiintyvät vihjeet rekisteröintisivusta.
#: Vertailu on kirjainkoosta riippumaton.
#: Huomaa: "tunnus" on poistettu, koska se esiintyy datassa usein
#: (kiinteistotunnus, y-tunnus, tunnus-id) eikä ole luotettava signaali.
_REGISTRATION_HINTS = ("register", "signup", "rekister", "login")

_BY_STATUS = {200: "none", 401: "apikey", 403: "restricted"}


def auth_from_status(
    http_status: int | None, final_url: str = ""
) -> list[tuple[str, str]]:
    """Päättele autentikointitapa statuskoodista ja päätyneestä osoitteesta.

    Tuntematon koodi ei tuota mitään: väärä arvaus katalogissa on pahempi
    kuin puuttuva tieto, koska lukija ei näe kumpi se on.
    """
    if http_status is None:
        return []

    if final_url and _is_registration_url(final_url):
        return [
            ("auth_method", "registration"),
            ("auth_registration_url", final_url),
        ]

    method = _BY_STATUS.get(http_status)
    if method is None:
        return []
    return [("auth_method", method)]


def _is_registration_url(url: str) -> bool:
    """Tarkista onko URL:ssa rekisteröintisivun vihjeitä polkuosassa.

    Query-parametrit jätetään huomioimatta: niiden nimissä ei ole
    merkitystä sivun luonteelle.
    """
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(hint in path for hint in _REGISTRATION_HINTS)
