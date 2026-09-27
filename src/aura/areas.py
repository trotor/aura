"""Aluetunnisteiden tulkinta: nimi, koodi tai postinumero → yksi alue.

Jokainen työkalu joka ottaa alueen parametrina tarvitsee saman päätöksen:
mitä käyttäjä tarkoittaa sanalla "Tampere", "837", "KU837", "Pirkanmaa",
"33100" tai "Nastola". Ennen tätä moduulia päätös tehtiin kolmessa paikassa
kolmella eri tavalla, eikä yksikään tiennyt kuntaliitoksista.

**Tulkintajärjestys** on tarkoituksella kiinteä ja dokumentoitu, koska sama
nimi on usein monella tasolla: "Tampere" on sekä kunta että seutukunta,
"Pirkanmaa" sekä maakunta että NUTS 3 -alue. Kunta voittaa aina, sitten
maakunta ja hyvinvointialue — tasot joilla kysymykset tavallisimmin
esitetään. Muun tason saa pyytämällä sen koodilla (``SK064``) tai
``levels``-parametrilla.

**Lakkautettu kunta** tulkitaan seuraajakseen ja muistiinpano kertoo sen.
"Nastola" palauttaa Lahden, ja kutsuja näkee miksi. Hiljainen tulkinta
olisi väärä: Nastolan vuoden 2014 väkiluku ei ole Lahden väkiluku.

Aineistot: ``ref_areas``, ``ref_area_membership`` ja
``ref_municipality_changes`` (populaattorit ``areas`` ja
``municipality_changes``). Jos niitä ei ole ladattu, kunnat, maakunnat ja
hyvinvointialueet tulkitaan ``ref_municipalities``-taulusta.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

#: Tasojen etusijajärjestys nimen ollessa monitulkintainen.
LEVEL_PRIORITY: tuple[str, ...] = (
    "koko_maa",
    "kunta",
    "maakunta",
    "hyvinvointialue",
    "seutukunta",
    "elinvoimakeskus",
    "suuralue",
    "vaalipiiri",
    "nuts3",
    "nuts2",
    "nuts1",
    "kuntaryhmitys",
)

#: Tilastokeskuksen PxWeb-tauluissa käytetyt etuliitteet (esim. 11ra:
#: ``KU837``, ``MK06``, ``SK064``, ``HVA08``, ``SA3``, ``SSS``).
STATFIN_PREFIX: dict[str, str] = {
    "kunta": "KU",
    "seutukunta": "SK",
    "maakunta": "MK",
    "hyvinvointialue": "HVA",
    "suuralue": "SA",
}
_PREFIX_TO_LEVEL = {v: k for k, v in STATFIN_PREFIX.items()}
_PREFIXED = re.compile(r"^(KU|SK|MK|HVA|SA)(\d{1,3})$", re.I)

_WHOLE_COUNTRY = frozenset(
    {"sss", "koko maa", "suomi", "koko suomi", "finland", "whole country", "hela landet"}
)

# Tasojen nimien päätteet jotka käyttäjä voi jättää pois tai lisätä:
# "Pirkanmaan maakunta" → "Pirkanmaa".
_LEVEL_SUFFIXES = (" maakunta", " kunta", " kaupunki", " seutukunta", " region")


@dataclass(frozen=True)
class Area:
    """Yksi alue: taso + koodi + nimet."""

    level: str
    code: str
    name_fi: str
    name_sv: str = ""

    @property
    def statfin_code(self) -> str | None:
        """Koodi Tilastokeskuksen PxWeb-taulujen aluedimensiossa, jos taso tunnetaan."""
        if self.level == "koko_maa":
            return "SSS"
        prefix = STATFIN_PREFIX.get(self.level)
        return f"{prefix}{self.code}" if prefix else None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["statfin_code"] = self.statfin_code
        return out


@dataclass
class AreaMatch:
    """Tulkinnan tulos. ``note`` kertoo jos tulkinta ei ollut suora."""

    area: Area
    query: str
    note: str = ""
    alternatives: list[Area] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"query": self.query, **self.area.to_dict()}
        if self.note:
            out["note"] = self.note
        if self.alternatives:
            out["alternatives"] = [a.to_dict() for a in self.alternatives]
        return out


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    if row is None:
        return False
    return bool(conn.execute(f"SELECT 1 FROM {name} LIMIT 1").fetchone())


def _row_area(row: sqlite3.Row | tuple[Any, ...]) -> Area:
    return Area(level=row[0], code=row[1], name_fi=row[2], name_sv=row[3] or "")


def _areas_by_name(conn: sqlite3.Connection, name: str) -> list[Area]:
    """Kaikki alueet joiden fi- tai sv-nimi on täsmälleen ``name`` (kirjainkoosta riippumatta)."""
    if _has_table(conn, "ref_areas"):
        rows = conn.execute(
            "SELECT level, code, name_fi, name_sv FROM ref_areas"
            " WHERE name_fi = ? COLLATE NOCASE OR name_sv = ? COLLATE NOCASE",
            (name, name),
        ).fetchall()
        found = [_row_area(r) for r in rows]
    else:
        found = _fallback_by_name(conn, name)
    order = {lvl: i for i, lvl in enumerate(LEVEL_PRIORITY)}
    return sorted(found, key=lambda a: order.get(a.level, len(order)))


def _fallback_by_name(conn: sqlite3.Connection, name: str) -> list[Area]:
    """Tulkinta pelkästä kuntataulusta, jos aluetasoja ei ole ladattu."""
    out: list[Area] = []
    for r in conn.execute(
        "SELECT code, name_fi, name_sv FROM ref_municipalities"
        " WHERE name_fi = ? COLLATE NOCASE OR name_sv = ? COLLATE NOCASE",
        (name, name),
    ):
        out.append(Area("kunta", r[0], r[1], r[2] or ""))
    for level, code_col, name_col in (
        ("maakunta", "region_code", "region_name_fi"),
        ("hyvinvointialue", "wellbeing_area_code", "wellbeing_area_name_fi"),
    ):
        r = conn.execute(
            f"SELECT DISTINCT {code_col}, {name_col} FROM ref_municipalities"
            f" WHERE {name_col} = ? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if r and r[0]:
            out.append(Area(level, r[0], r[1]))
    return out


def get_area(conn: sqlite3.Connection, level: str, code: str) -> Area | None:
    """Hae alue tasolla ja koodilla."""
    if level == "koko_maa":
        return Area("koko_maa", "SSS", "Koko maa", "Hela landet")
    if _has_table(conn, "ref_areas"):
        row = conn.execute(
            "SELECT level, code, name_fi, name_sv FROM ref_areas WHERE level=? AND code=?",
            (level, code),
        ).fetchone()
        return _row_area(row) if row else None
    if level == "kunta":
        row = conn.execute(
            "SELECT code, name_fi, name_sv FROM ref_municipalities WHERE code=?", (code,)
        ).fetchone()
        return Area("kunta", row[0], row[1], row[2] or "") if row else None
    return None


def successor(conn: sqlite3.Connection, old_code: str) -> dict[str, Any] | None:
    """Lakkautetun kunnan seuraaja, tai None jos koodi ei ole lakkautettu."""
    if not _has_table(conn, "ref_municipality_changes"):
        return None
    row = conn.execute(
        "SELECT old_code, old_name_fi, new_code, new_name_fi, effective_year, source"
        " FROM ref_municipality_changes WHERE old_code = ?",
        (old_code,),
    ).fetchone()
    if row is None:
        return None
    return {
        "old_code": row[0],
        "old_name": row[1],
        "new_code": row[2],
        "new_name": row[3],
        "effective_year": row[4],
        "source": row[5],
    }


def _merged_note(change: dict[str, Any]) -> str:
    year = change["effective_year"]
    when = f" vuonna {year}" if year else ""
    return (
        f"{change['old_name']} ({change['old_code']}) on lakkautettu kunta; se liitettiin"
        f"{when} kuntaan {change['new_name']} ({change['new_code']}). Luvut koskevat"
        " nykyistä kuntaa rajoineen, eivät lakkautettua kuntaa."
    )


def _by_old_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    if not _has_table(conn, "ref_municipality_changes"):
        return None
    row = conn.execute(
        "SELECT old_code FROM ref_municipality_changes WHERE old_name_fi = ? COLLATE NOCASE",
        (name,),
    ).fetchone()
    return successor(conn, row[0]) if row else None


def _postal(conn: sqlite3.Connection, code: str) -> AreaMatch | None:
    row = conn.execute(
        "SELECT p.code, p.name_fi, p.name_sv, p.municipality_code, m.name_fi"
        " FROM ref_postal_codes p LEFT JOIN ref_municipalities m"
        " ON m.code = p.municipality_code WHERE p.code = ?",
        (code,),
    ).fetchone()
    if row is None:
        return None
    area = Area("postinumero", row[0], row[1], row[2] or "")
    note = f"Postinumeroalue kunnassa {row[4]} ({row[3]})." if row[3] else ""
    return AreaMatch(area=area, query=code, note=note)


def resolve_area(
    conn: sqlite3.Connection, query: str, *, levels: tuple[str, ...] | None = None
) -> AreaMatch | None:
    """Tulkitse aluetunniste. Palauttaa None jos mikään taso ei tunnista sitä.

    Args:
        query: Nimi (fi/sv), kuntakoodi (``837``), etuliitteellinen koodi
            (``KU837``, ``MK06``, ``SK064``, ``HVA08``), postinumero
            (``33100``) tai lakkautetun kunnan nimi tai koodi.
        levels: Rajaa sallitut tasot. Oletus: kaikki.
    """
    raw = query.strip()
    if not raw:
        return None
    allowed = set(levels) if levels else None

    def ok(level: str) -> bool:
        return allowed is None or level in allowed

    if raw.lower() in _WHOLE_COUNTRY and ok("koko_maa"):
        return AreaMatch(Area("koko_maa", "SSS", "Koko maa", "Hela landet"), raw)

    m = _PREFIXED.match(raw)
    if m:
        level = _PREFIX_TO_LEVEL[m.group(1).upper()]
        width = 3 if level in ("kunta", "seutukunta") else 2 if level != "suuralue" else 1
        code = m.group(2).zfill(width)
        if ok(level):
            area = get_area(conn, level, code)
            if area:
                return AreaMatch(area, raw)
            if level == "kunta":
                return _code_match(conn, code, raw)
        return None

    if raw.isdigit():
        if len(raw) == 5 and ok("postinumero"):
            return _postal(conn, raw)
        if len(raw) <= 3 and ok("kunta"):
            return _code_match(conn, raw.zfill(3), raw)
        return None

    candidates = _name_candidates(raw)
    for name in candidates:
        found = [a for a in _areas_by_name(conn, name) if ok(a.level)]
        if found:
            first, rest = found[0], found[1:]
            note = ""
            # Kunta on odotettu tulkinta, ja lähes jokaisella keskuskaupungilla
            # on samanniminen seutukunta — huomautus olisi joka vastauksessa
            # kohinaa. Vaihtoehdot jäävät silti alternatives-kenttään.
            if rest and first.level != "kunta":
                others = ", ".join(f"{a.level} {a.code}" for a in rest)
                note = f"Nimi on myös: {others}. Valittiin {first.level}."
            return AreaMatch(first, raw, note=note, alternatives=rest)

    if ok("kunta"):
        for name in candidates:
            change = _by_old_name(conn, name)
            if change:
                area = get_area(conn, "kunta", change["new_code"])
                if area:
                    return AreaMatch(area, raw, note=_merged_note(change))
    return None


def _code_match(conn: sqlite3.Connection, code: str, raw: str) -> AreaMatch | None:
    area = get_area(conn, "kunta", code)
    if area:
        return AreaMatch(area, raw)
    change = successor(conn, code)
    if change:
        area = get_area(conn, "kunta", change["new_code"])
        if area:
            return AreaMatch(area, raw, note=_merged_note(change))
    return None


#: Sijapäätteet jotka riisutaan ennen lemmatisointia. Lemmatisoija osaa
#: astevaihtelun ("Helsingin" → helsinki) mutta erehtyy harvinaisissa
#: nimissä: "Vantaan" → "vannas". Pelkkä päätteen poisto osuu niihin oikein.
_CASE_SUFFIXES = ("lla", "llä", "ssa", "ssä", "sta", "stä", "lta", "ltä", "lle", "n")


def _name_candidates(raw: str) -> list[str]:
    """Nimi sellaisenaan, ilman tasopäätettä, ilman sijapäätettä ja perusmuodossa.

    "Pirkanmaan maakunta" → "Pirkanmaan", "Pirkanmaa". "Vantaalla" →
    "Vantaa". Taivutettu muoto ("Tampereella") palautetaan perusmuotoon
    lemmatisoijalla, jos se on asennettu.
    """
    out = [raw]
    low = raw.lower()
    for suffix in _LEVEL_SUFFIXES:
        if low.endswith(suffix):
            out.append(raw[: -len(suffix)].strip())
    for name in list(out):
        if " " in name:
            continue
        for suffix in _CASE_SUFFIXES:
            if name.lower().endswith(suffix) and len(name) - len(suffix) >= 3:
                out.append(name[: -len(suffix)])
                break
    try:
        from aura.lemmatize import lemma

        for name in list(out):
            if " " not in name:
                base = lemma(name.lower())
                if base and base != name.lower():
                    out.append(base)
    except Exception:  # noqa: BLE001 — lemmatisointi on vain apu
        pass
    seen: set[str] = set()
    unique: list[str] = []
    for n in out:
        if n.lower() not in seen:
            seen.add(n.lower())
            unique.append(n)
    return unique


def resolve_areas(
    conn: sqlite3.Connection, queries: list[str], **kwargs: Any
) -> tuple[list[AreaMatch], list[str]]:
    """Tulkitse monta aluetta. Palauttaa (tulkitut, tunnistamattomat)."""
    matched: list[AreaMatch] = []
    missing: list[str] = []
    for q in queries:
        m = resolve_area(conn, q, **kwargs)
        if m is None:
            missing.append(q)
        else:
            matched.append(m)
    return matched, missing


def parents(conn: sqlite3.Connection, municipality_code: str) -> dict[str, Area]:
    """Kunnan kaikki ylemmät tasot: ``{"maakunta": Area(...), ...}``."""
    out: dict[str, Area] = {}
    if _has_table(conn, "ref_area_membership"):
        rows = conn.execute(
            "SELECT a.level, a.code, a.name_fi, a.name_sv FROM ref_area_membership m"
            " JOIN ref_areas a ON a.level = m.level AND a.code = m.area_code"
            " WHERE m.municipality_code = ?",
            (municipality_code,),
        ).fetchall()
        for r in rows:
            out[r[0]] = _row_area(r)
        return out
    row = conn.execute(
        "SELECT region_code, region_name_fi, wellbeing_area_code, wellbeing_area_name_fi"
        " FROM ref_municipalities WHERE code = ?",
        (municipality_code,),
    ).fetchone()
    if row:
        if row[0]:
            out["maakunta"] = Area("maakunta", row[0], row[1] or "")
        if row[2]:
            out["hyvinvointialue"] = Area("hyvinvointialue", row[2], row[3] or "")
    return out


def members(conn: sqlite3.Connection, area: Area) -> list[Area]:
    """Alueeseen kuuluvat kunnat. Kunnalle itse palautetaan se itse."""
    if area.level == "kunta":
        return [area]
    if area.level == "postinumero":
        return []
    if _has_table(conn, "ref_area_membership"):
        rows = conn.execute(
            "SELECT a.level, a.code, a.name_fi, a.name_sv FROM ref_area_membership m"
            " JOIN ref_areas a ON a.level = 'kunta' AND a.code = m.municipality_code"
            " WHERE m.level = ? AND m.area_code = ? ORDER BY a.name_fi",
            (area.level, area.code),
        ).fetchall()
        return [_row_area(r) for r in rows]
    column = {"maakunta": "region_code", "hyvinvointialue": "wellbeing_area_code"}.get(area.level)
    params: tuple[str, ...]
    if area.level == "koko_maa":
        where, params = "1=1", ()
    elif column:
        where, params = f"{column} = ?", (area.code,)
    else:
        return []
    rows = conn.execute(
        f"SELECT code, name_fi, name_sv FROM ref_municipalities WHERE {where} ORDER BY name_fi",
        params,
    ).fetchall()
    return [Area("kunta", r[0], r[1], r[2] or "") for r in rows]
