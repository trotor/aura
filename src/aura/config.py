"""Ajonaikainen konfiguraatio (#135).

Yksi paikka moodilogiikalle (read-only remote vs. täysi lokaalikäyttö).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

_TRUTHY = {"1", "true", "yes", "on"}


def is_readonly(env: Mapping[str, str] | None = None) -> bool:
    """Onko server read-only-moodissa (remote)?

    Ohjataan ``AURA_READONLY``-ympäristömuuttujalla. Read-only-moodissa
    kirjoittavat toolit eivät rekisteröidy ja tietokanta avataan vain luettavaksi.
    """
    if env is None:
        env = os.environ
    return env.get("AURA_READONLY", "").strip().lower() in _TRUTHY


#: Työkaluprofiilit. ``public`` on aikomustason pinta (≤ 8 työkalua);
#: ``admin`` näyttää kaiken, myös ylläpidon ja vanhentuneet työkalut.
TOOL_PROFILES = ("public", "admin")


def tool_profile(env: Mapping[str, str] | None = None) -> str:
    """Valittu työkaluprofiili ``AURA_TOOL_PROFILE``-muuttujasta (oletus ``public``).

    Tuntematon arvo on virhe eikä hiljainen paluu oletukseen: väärin
    kirjoitettu ``admn`` antaisi muuten julkisen pinnan ja näyttäisi siltä
    kuin ylläpitotyökalut olisivat kadonneet.
    """
    if env is None:
        env = os.environ
    value = env.get("AURA_TOOL_PROFILE", "").strip().lower() or "public"
    if value not in TOOL_PROFILES:
        raise ValueError(
            f"Tuntematon AURA_TOOL_PROFILE={value!r}. Sallitut: {', '.join(TOOL_PROFILES)}"
        )
    return value
