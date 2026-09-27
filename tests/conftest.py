"""Yhteiset testikiinnitykset."""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _nollaa_tyokaluprofiili() -> Iterator[None]:
    """Palauta ``mcp``-singletonin työkaluprofiili jokaisen testin jälkeen.

    ``create_asgi_app`` ja ``serve`` ottavat julkisen profiilin käyttöön,
    ja se on näkyvyysmuunnos moduulitason palvelimessa. Ilman nollausta
    yksi ASGI-testi piilottaisi ylläpitotyökalut kaikilta sen jälkeen
    ajettavilta testeiltä.
    """
    yield
    from aura.server import mcp, reset_tool_profile

    reset_tool_profile(mcp)
