"""Vastauskoodista johdetut kentät.

auth_method ei ansaitse omaa kutsuaan: muut proberit tekevät saman pyynnön
joka tapauksessa, ja erillinen HEAD jokaiselle resurssille
kaksinkertaistaisi liikenteen kertomatta mitään uutta.
"""

from __future__ import annotations

#: Osoitteen osat jotka kertovat rekisteröintisivusta.
_REGISTRATION_HINTS = ("register", "signup", "rekister", "tunnus", "login")

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

    if final_url and any(h in final_url.lower() for h in _REGISTRATION_HINTS):
        return [
            ("auth_method", "registration"),
            ("auth_registration_url", final_url),
        ]

    method = _BY_STATUS.get(http_status)
    if method is None:
        return []
    return [("auth_method", method)]
