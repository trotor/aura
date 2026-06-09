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
