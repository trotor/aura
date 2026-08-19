"""Testit vastauskoodista johdetulle autentikointitiedolle.

auth_method ei ansaitse omaa kutsuaan: muut proberit tekevät saman pyynnön
joka tapauksessa, ja erillinen HEAD kaksinkertaistaisi liikenteen
kertomatta mitään uutta.
"""

from __future__ import annotations

import pytest

from aura.probe.derive import auth_from_status


@pytest.mark.parametrize(
    ("status", "odotus"),
    [(200, "none"), (401, "apikey"), (403, "restricted")],
)
def test_koodi_kertoo_menetelman(status: int, odotus: str) -> None:
    assert dict(auth_from_status(status))["auth_method"] == odotus


def test_tuntematon_koodi_ei_arvaa() -> None:
    """Väärä arvaus on pahempi kuin puuttuva tieto."""
    assert auth_from_status(500) == []
    assert auth_from_status(None) == []


@pytest.mark.parametrize(
    ("url", "odotus_metodi"),
    [
        ("https://example.test/register?next=/data", "registration"),
        ("https://example.fi/kayttajan-rekisterointi/", "registration"),
        ("https://example.fi/signup.html", "registration"),
        ("https://api.example.fi/data?key=login_token", None),
        ("https://example.fi/tunnus-id/123.csv", None),
        ("https://example.fi/wfs?typeName=rekisteri:kohteet", None),
    ],
)
def test_rekisterointisivun_tunnistus_tarkasti(
    url: str, odotus_metodi: str | None
) -> None:
    """Testaa rekisteröintisivun tunnistus kuudella tapauksella.

    Positiiviset:
    - /register polulla
    - /rekisterointi osana polkua
    - /signup osana tiedostonimeä

    Negatiiviset:
    - login query-parametrissa (polku ei sisällä vihjeitä)
    - tunnus-id: tunnus poistettu hinteistä ambiguiteetin vuoksi
    - rekisteri query-parametrissa (polku ei sisällä vihjeitä)
    """
    result = auth_from_status(200, url)
    if odotus_metodi is None:
        # Ei saisi tunnistaa rekisteröintisivuksi
        if result:
            result_dict = dict(result)
            assert result_dict.get("auth_method") != "registration", (
                f"URL '{url}' väärä positiivinen"
            )
    else:
        # Saisi tunnistaa rekisteröintisivuksi
        result_dict = dict(result)
        assert result_dict["auth_method"] == odotus_metodi, (
            f"URL '{url}' ei tunnistettu oikein"
        )
        assert "auth_registration_url" in result_dict
