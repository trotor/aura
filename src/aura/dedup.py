"""Hakutulosten deduplikointi.

Sama aineisto esiintyy korpuksessa usein monta kertaa:

- Tilastokeskus julkaisee saman taulun useassa tietokantapolussa, jolloin
  otsikot eroavat vain taulukoodilla: ``12at -- Väestönmuutokset ja väkiluku``
  ja ``11ad -- Väestönmuutokset ja väkiluku`` ovat sama taulu.
- Katalogit peilaavat toisiaan: sama aineisto tulee sekä alkuperäisestä
  lähteestä että avoindata.suomi.fi:n tai Paikkatietoikkunan kautta.

Mitattuna: 11 202 datasetistä **579** on duplikaatti, kun taulukoodiprefiksi
normalisoidaan pois. Vaikutus näkyy juuri yleisimmissä kyselyissä — haku
``väkiluku`` käytti kahdeksan tulosta kahdestatoista samaan tauluun.

Duplikaatteja ei piiloteta vaan niputetaan: edustaja säilyy ja muut kulkevat
mukana kentissä ``duplicate_count`` ja ``duplicate_ids``.
"""

from __future__ import annotations

import re
from typing import Any

# Tilastokeskuksen taulukoodiprefiksi: "12vm -- ", "138v -- ", "11m2 -- ".
# Vuosilukuja EI karsita: "Maatalousmaa 2023" ja "Maatalousmaa 2024" ovat eri
# aineistoja.
_CODE_PREFIX = re.compile(r"^[0-9a-zA-Z]{2,8}\s+--\s+")
_WHITESPACE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Normalisoi otsikko ryhmittelyavaimeksi."""
    if not title:
        return ""
    stripped = _CODE_PREFIX.sub("", title.strip())
    return _WHITESPACE.sub(" ", stripped).strip().lower()


def _title_of(row: dict[str, Any]) -> str:
    for field in ("title_fi", "title", "name"):
        value = row.get(field)
        if value:
            return str(value)
    return ""


def group_key(row: dict[str, Any]) -> str:
    """Ryhmittelyavain. Tyhjä otsikko saa oman avaimensa datasetin id:stä."""
    normalized = normalize_title(_title_of(row))
    return normalized or f"\x00{row.get('id', '')}"


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Niputa saman otsikon aineistot, järjestys säilyttäen.

    Ensimmäinen esiintymä on edustaja — koska tulokset ovat jo
    relevanssijärjestyksessä, se on ryhmän parhaiten sijoittunut.
    """
    representatives: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for row in rows:
        key = group_key(row)
        if key not in representatives:
            copy = dict(row)
            copy["duplicate_count"] = 0
            copy["duplicate_ids"] = []
            representatives[key] = copy
            order.append(key)
        else:
            representative = representatives[key]
            representative["duplicate_count"] += 1
            representative["duplicate_ids"].append(str(row.get("id", "")))

    return [representatives[key] for key in order]
