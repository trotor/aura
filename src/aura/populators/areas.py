"""Aluetasojen ristiintaulukko ja kuntaliitoshistoria Tilastokeskuksen luokituspalvelusta.

Kaksi populaattoria, koska ne vastaavat eri kysymyksiin ja vanhenevat eri
tahtiin:

``areas``
    Mihin seutukuntaan, maakuntaan, hyvinvointialueeseen, suuralueeseen,
    elinvoimakeskukseen, kuntaryhmään ja NUTS-alueeseen kunta kuuluu.
    Vaihtuu vuoden vaihteessa luokitusversion mukana.

``municipality_changes``
    Mikä nykyinen kunta on lakkautetun kunnan seuraaja, ja minä vuonna
    liitos tuli voimaan. Historia ei muutu, mutta siihen lisätään rivi joka
    kerta kun kuntia yhdistyy.

Molemmat ovat transkriptiota — ne kopioivat mitä Tilastokeskus kertoo
luokituksistaan — ja kuuluvat siksi avoimeen Auraan.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from aura.populators.base import BasePopulator

logger = logging.getLogger(__name__)

API_BASE = "https://data.stat.fi/api/classifications/v2"

#: Taso → luokituksen tunnisteen alku. NUTS on versiossa 2, muut 1.
LEVEL_CLASSIFICATIONS: dict[str, str] = {
    "seutukunta": "seutukunta_1",
    "maakunta": "maakunta_1",
    "hyvinvointialue": "hyvinvointialue_1",
    "suuralue": "suuralue_1",
    "elinvoimakeskus": "evk_1",
    "kuntaryhmitys": "kuntaryhmitys_1",
    "vaalipiiri": "vaalipiiri_1",
    "nuts": "nuts_2",
}

#: NUTS-luokitus palauttaa jokaiselle kunnalle kolme riviä, yhden per taso.
NUTS_LEVELS = {1: "nuts1", 2: "nuts2", 3: "nuts3"}

#: Liitokset jotka ovat uudempia kuin luokituspalvelun viimeisin
#: "voimassaolevat ja lakkautetut kunnat" -avain. Palvelu julkaisee avaimen
#: harvemmin kuin kuntajako muuttuu, joten vuosiversioiden vertailu löytää
#: lakkautetun koodin mutta ei sen seuraajaa. Jokainen rivi on tarkistettava
#: julkaistusta päätöksestä; tuntematon lakkautus kirjataan lokiin varoituksena
#: eikä arvata.
KNOWN_SUCCESSORS: dict[str, tuple[str, int, str]] = {
    # Pertunmaa liitettiin Mäntyharjuun 1.1.2025 (valtioneuvoston päätös
    # 2023). Luokituspalvelun avain kunta_2_20240101 on liitosta vanhempi.
    "588": ("507", 2025, "valtioneuvoston päätös (Mäntyharju–Pertunmaa)"),
}

_VERSION = re.compile(r"/kunta_1_(\d{8})$")
_KEY_TABLE = re.compile(r"/(kunta_2_(\d{8})%23kunta_1_\2)$")


def _name(item: dict[str, Any]) -> str:
    names = item.get("classificationItemNames") or []
    return str(names[0]["name"]) if names else ""


class _ClassificationClient:
    """Luokituspalvelun kutsut, jaettu molemmille populaattoreille."""

    def __init__(self, populator: BasePopulator, client: httpx.AsyncClient) -> None:
        self.p = populator
        self.client = client

    async def get(self, path: str, **params: str) -> Any:
        resp = await self.p._fetch(
            self.client, f"{API_BASE}/{path}", params={"format": "json", **params}
        )
        return resp.json()

    async def kunta_versions(self) -> list[str]:
        """Kaikki kuntaluokituksen vuosiversiot vanhimmasta uusimpaan."""
        urls: list[str] = await self.get("classifications")
        return sorted(m.group(1) for u in urls if (m := _VERSION.search(u)))

    async def items(self, class_id: str, lang: str = "fi") -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = await self.get(
            f"classifications/{class_id}/classificationItems",
            content="data",
            meta="max",
            lang=lang,
        )
        return data

    async def names(self, class_id: str, lang: str) -> dict[str, str]:
        return {i["code"]: _name(i) for i in await self.items(class_id, lang)}

    async def maps(self, table_id: str) -> list[dict[str, Any]]:
        """Vastaavuustaulun rivit nimineen (``content=data``)."""
        data: list[dict[str, Any]] = await self.get(
            f"correspondenceTables/{table_id}/maps",
            content="data",
            meta="max",
            lang="fi",
        )
        return data


class AreaHierarchyPopulator(BasePopulator):
    """Kunnan jäsenyys kaikilla aluetasoilla + tasojen nimet."""

    name = "areas"
    description = (
        "Aluetasojen ristiintaulukko: kunta → seutukunta, maakunta, hyvinvointialue, "
        "suuralue, elinvoimakeskus, kuntaryhmä, vaalipiiri, NUTS 1–3"
    )
    source_url = f"{API_BASE}/"

    async def populate(self) -> int:
        async with self._make_client(timeout=60.0) as http:
            api = _ClassificationClient(self, http)
            version = (await api.kunta_versions())[-1]
            vintage = int(version[:4])

            kunta_id = f"kunta_1_{version}"
            kunnat_fi = await api.names(kunta_id, "fi")
            kunnat_sv = await api.names(kunta_id, "sv")

            areas: dict[tuple[str, str], tuple[str, str]] = {
                ("kunta", c): (n, kunnat_sv.get(c, n)) for c, n in kunnat_fi.items()
            }
            areas[("koko_maa", "SSS")] = ("Koko maa", "Hela landet")
            membership: list[tuple[str, str, str]] = [(c, "koko_maa", "SSS") for c in kunnat_fi]

            for level, prefix in LEVEL_CLASSIFICATIONS.items():
                target_id = f"{prefix}_{version}"
                try:
                    rows = await api.maps(f"{kunta_id}%23{target_id}")
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.warning("[%s] Ei vastaavuustaulua: %s", self.name, target_id)
                        continue
                    raise
                sv = await api.names(target_id, "sv")
                for row in rows:
                    muni = row["sourceItem"]["code"]
                    target = row["targetItem"]
                    tlevel = level
                    if level == "nuts":
                        tlevel = NUTS_LEVELS.get(int(target.get("level") or 0), "")
                        if not tlevel:
                            continue
                    name_fi = _name(target)
                    areas[(tlevel, target["code"])] = (name_fi, sv.get(target["code"], name_fi))
                    membership.append((muni, tlevel, target["code"]))

        with self.conn:
            self.conn.execute("DELETE FROM ref_areas")
            self.conn.execute("DELETE FROM ref_area_membership")
            self.conn.executemany(
                "INSERT INTO ref_areas (level, code, name_fi, name_sv, vintage)"
                " VALUES (?, ?, ?, ?, ?)",
                [(lvl, code, fi, sv, vintage) for (lvl, code), (fi, sv) in areas.items()],
            )
            self.conn.executemany(
                "INSERT OR REPLACE INTO ref_area_membership"
                " (municipality_code, level, area_code, vintage) VALUES (?, ?, ?, ?)",
                [(m, lvl, a, vintage) for m, lvl, a in membership],
            )
        self._update_metadata(len(areas), version=version)
        logger.info(
            "[%s] %d aluetta, %d jäsenyyttä (versio %s)",
            self.name,
            len(areas),
            len(membership),
            version,
        )
        return len(areas)


class MunicipalityChangesPopulator(BasePopulator):
    """Lakkautettujen kuntien seuraajat ja liitosvuodet."""

    name = "municipality_changes"
    description = "Kuntaliitoshistoria: lakkautetun kunnan koodi → nykyinen kunta"
    source_url = f"{API_BASE}/"

    async def populate(self) -> int:
        async with self._make_client(timeout=60.0) as http:
            api = _ClassificationClient(self, http)
            versions = await api.kunta_versions()

            # 1) Liitosvuodet: koodi joka puuttuu vuoden Y versiosta mutta oli
            #    vuoden Y-1 versiossa lakkautettiin 1.1.Y.
            per_version: dict[str, dict[str, str]] = {}
            for v in versions:
                per_version[v] = await api.names(f"kunta_1_{v}", "fi")
            effective: dict[str, int] = {}
            for prev, cur in zip(versions, versions[1:], strict=False):
                for code in per_version[prev].keys() - per_version[cur].keys():
                    effective[code] = int(cur[:4])

            # 2) Seuraajat: uusin "voimassaolevat ja lakkautetut kunnat" -avain.
            tables: list[str] = await api.get("correspondenceTables")
            keys = sorted((m.group(2), m.group(1)) for t in tables if (m := _KEY_TABLE.search(t)))
            if not keys:
                raise RuntimeError("Lakkautettujen kuntien luokitusavainta ei löytynyt")
            key_version, key_table = keys[-1]
            mapping: dict[str, tuple[str, str, str]] = {}
            names: dict[str, str] = {}
            for row in await api.maps(key_table):
                old, new = row["sourceItem"]["code"], row["targetItem"]["code"]
                names[old] = _name(row["sourceItem"])
                names[new] = _name(row["targetItem"])
                if old != new:
                    mapping[old] = (new, f"Tilastokeskus {key_table.replace('%23', '#')}", "")

        latest = per_version[versions[-1]]
        for v in versions:
            for code, name in per_version[v].items():
                names.setdefault(code, name)

        # 3) Avainta uudemmat lakkautukset.
        for code, year in effective.items():
            if code in mapping:
                continue
            if code in KNOWN_SUCCESSORS:
                new, _, source = KNOWN_SUCCESSORS[code]
                mapping[code] = (new, source, "")
            elif int(key_version[:4]) < year:
                logger.warning(
                    "[%s] Kunta %s (%s) lakkautettiin %d, mutta seuraajaa ei tiedetä."
                    " Lisää se KNOWN_SUCCESSORS-tauluun päätöksen perusteella.",
                    self.name,
                    code,
                    names.get(code, "?"),
                    year,
                )

        # 4) Ketjut nykyiseen kuntaan: vanha → 2024 → 2025.
        def resolve(code: str) -> str:
            seen = {code}
            while code not in latest and code in mapping:
                code = mapping[code][0]
                if code in seen:
                    break
                seen.add(code)
            return code

        rows = []
        for old, (_, source, _) in mapping.items():
            new = resolve(old)
            if new not in latest:
                logger.warning("[%s] %s → %s ei ole voimassa oleva kunta", self.name, old, new)
                continue
            rows.append((old, names.get(old, ""), new, latest[new], effective.get(old), source))

        with self.conn:
            self.conn.execute("DELETE FROM ref_municipality_changes")
            self.conn.executemany(
                "INSERT INTO ref_municipality_changes"
                " (old_code, old_name_fi, new_code, new_name_fi, effective_year, source)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        self._update_metadata(len(rows), version=versions[-1])
        logger.info("[%s] %d lakkautettua kuntaa", self.name, len(rows))
        return len(rows)
