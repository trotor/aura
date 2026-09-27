"""Laajennuspisteet aikomustason työkaluille.

Avoin Aura on metatietokatalogi. Laajennus (esim. Aura Pro) voi tuoda
työkaluvastauksiin sisältöä jota katalogissa ei ole — valmiita
tunnuslukuja, todennettuja kyselyreseptejä — ilman että avoimen auran
koodiin tarvitsee koskea tai sitä tarvitsee paikata ajossa.

Aiempi tapa oli vaihtaa moduulitason funktioviittaus (``search_datasets``)
jokaisessa työkalumoduulissa. Se toimii, mutta hajoaa hiljaa jos nimi
muuttuu. Nimetty koukku on sopimus: avoin aura lupaa kutsua sitä, ja
testit pitävät lupauksen.

Koukut:

``find_data.indicators(conn, query, region) -> list[dict]``
    Tunnusluvut jotka vastaavat hakua. Palautetaan ``find_data``-vastauksen
    ``indicators``-kentässä ennen aineistolistaa.

``inspect_dataset.recipe(conn, dataset) -> dict | None``
    Todennettu, parametrisoitu kyselypohja aineistolle.

``area_snapshot.key_figures(conn, area) -> list[dict]``
    Alueen tunnusluvut arvoineen ja lähteineen.

Koukun poikkeus kirjataan lokiin eikä kaada työkalua: laajennuksen vika ei
saa viedä katalogivastausta mukanaan.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

HOOKS = frozenset({"find_data.indicators", "inspect_dataset.recipe", "area_snapshot.key_figures"})

_registry: dict[str, list[Callable[..., Any]]] = {name: [] for name in HOOKS}


def register(hook: str, fn: Callable[..., Any]) -> None:
    """Rekisteröi koukku. Tuntematon nimi on virhe, ei hiljainen no-op."""
    if hook not in HOOKS:
        raise KeyError(f"Tuntematon koukku {hook!r}. Tunnetut: {sorted(HOOKS)}")
    if fn not in _registry[hook]:
        _registry[hook].append(fn)


def clear(hook: str | None = None) -> None:
    """Poista rekisteröinnit (testit)."""
    for name in [hook] if hook else list(HOOKS):
        _registry[name].clear()


def has(hook: str) -> bool:
    return bool(_registry.get(hook))


async def call_all(hook: str, **kwargs: Any) -> list[Any]:
    """Kutsu kaikki koukut. Palauttaa ei-tyhjät tulokset rekisteröintijärjestyksessä."""
    out: list[Any] = []
    for fn in _registry.get(hook, []):
        try:
            result = fn(**kwargs)
            if hasattr(result, "__await__"):
                result = await result
        except Exception:  # noqa: BLE001 — laajennus ei saa kaataa katalogia
            logger.warning("[extensions] Koukku %s epäonnistui", hook, exc_info=True)
            continue
        if result:
            out.append(result)
    return out
