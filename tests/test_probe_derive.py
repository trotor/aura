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


def test_rekisterointisivu_tunnistetaan() -> None:
    arvot = dict(auth_from_status(200, "https://example.test/register?next=/data"))
    assert arvot["auth_method"] == "registration"
    assert arvot["auth_registration_url"].endswith("/register?next=/data")


def test_tuntematon_koodi_ei_arvaa() -> None:
    """Väärä arvaus on pahempi kuin puuttuva tieto."""
    assert auth_from_status(500) == []
    assert auth_from_status(None) == []
