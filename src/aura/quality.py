"""Datasettien automaattinen laatupisteytys.

**Kaksi lukua, jotka mittaavat eri asiaa.**

``overall`` on metatiedon laatu — kuinka hyvin aineisto on *kuvattu*. Se
lasketaan neljästä dimensiosta:

- completeness (25 %): metatiedon täydellisyys
- timeliness (30 %): aineiston tuoreus
- accessibility (25 %): saavutettavuus ja koneluettavuus
- documentation (20 %): dokumentointi ja rikastukset

``agent_readiness`` on eri kysymys: pääseekö agentti dataan käsiksi ilman
ihmistä. Se lasketaan probe-havainnoista eikä metatiedosta, ja sen tarve on
mitattu — 1.9.2026 kannassa oli 434 datasettiä joiden ``overall`` on ≥ 85 ja
joista 67:n skeemaa ei tunneta lainkaan. Hyvin kuvattu aineisto voi olla
saavuttamaton, ja hyvin saavutettava huonosti kuvattu.

Luvut pidetään erillään tarkoituksella. Agenttivalmius **ei ole osa
``overall``-lukua**: ``DIMENSION_WEIGHTS`` on ennallaan, joten vanha luku
tarkoittaa yhä samaa kuin ennen eikä yksikään aiempi arvo liiku.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aura.constants import MACHINE_READABLE_FORMATS, parse_json_list

logger = logging.getLogger(__name__)

DIMENSION_WEIGHTS = {
    "completeness": 0.25,
    "timeliness": 0.30,
    "accessibility": 0.25,
    "documentation": 0.20,
}


# --- Yksittäiset dimensiot ---


def calculate_completeness(dataset: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Metatiedon täydellisyys: kuinka moni kenttä on täytetty."""
    checks = {
        "title": bool(
            (dataset.get("title_fi") or "").strip()
            or (dataset.get("title") or "").strip()
        ),
        "description": len(
            (dataset.get("notes_fi") or dataset.get("notes") or "").strip()
        ) > 50,
        "keywords": _keyword_count(dataset) >= 3,
        "organization": bool(
            (dataset.get("organization_title") or "").strip()
        ),
        "license": bool((dataset.get("license_id") or "").strip()),
        "update_frequency": bool(
            (dataset.get("update_frequency") or "").strip()
        ),
    }
    passed = sum(checks.values())
    score = (passed / len(checks)) * 100
    return score, checks


def calculate_timeliness(dataset: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Aineiston tuoreus metadata_modified-kentän perusteella."""
    modified = (dataset.get("metadata_modified") or "").strip()
    if not modified:
        return 10.0, {"metadata_modified": None, "days_old": None}

    try:
        mod_dt = datetime.fromisoformat(modified).replace(tzinfo=UTC)
        days_old = (datetime.now(tz=UTC) - mod_dt).days
    except (ValueError, TypeError):
        logger.warning("[quality] Virheellinen metadata_modified: '%s'", modified)
        return 10.0, {"metadata_modified": modified, "parse_error": True}

    if days_old <= 30:
        score = 100.0
    elif days_old <= 90:
        score = 85.0
    elif days_old <= 365:
        score = 60.0
    elif days_old <= 730:
        score = 30.0
    else:
        score = 10.0

    return score, {"metadata_modified": modified, "days_old": days_old}


def calculate_accessibility(
    dataset: dict[str, Any],
    resources: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Saavutettavuus: access_level, resurssimäärä, formaatit."""
    details: dict[str, Any] = {}

    # Access level
    access = (dataset.get("access_level") or "open").lower()
    access_scores = {"open": 100, "registration": 50, "restricted": 20}
    access_score = access_scores.get(access, 30)
    details["access_level"] = access
    details["access_score"] = access_score

    # Resurssien lukumäärä
    num_res = len(resources) if resources else (dataset.get("num_resources") or 0)
    if num_res == 0:
        res_score = 0.0
    elif num_res == 1:
        res_score = 50.0
    elif num_res < 5:
        res_score = 80.0
    else:
        res_score = 100.0
    details["num_resources"] = num_res
    details["resource_score"] = res_score

    # Koneluettavuus
    formats = {(r.get("format") or "").upper() for r in resources}
    machine_readable = formats & {f.upper() for f in MACHINE_READABLE_FORMATS}
    if machine_readable:
        format_score = 100.0
    elif formats:
        format_score = 40.0
    else:
        format_score = 0.0
    details["formats"] = sorted(formats - {""})
    details["machine_readable"] = sorted(machine_readable)
    details["format_score"] = format_score

    # Painotettu keskiarvo
    score = access_score * 0.4 + res_score * 0.3 + format_score * 0.3
    return score, details


def calculate_documentation(
    dataset: dict[str, Any],
    enrichment_count: int,
) -> tuple[float, dict[str, Any]]:
    """Dokumentoinnin taso: monikielisyys ja rikastukset."""
    details: dict[str, Any] = {}

    # Monikielisyys
    langs = set()
    if (dataset.get("title_fi") or "").strip() or (dataset.get("notes_fi") or "").strip():
        langs.add("fi")
    if (dataset.get("title_en") or "").strip() or (dataset.get("notes_en") or "").strip():
        langs.add("en")
    if (dataset.get("title_sv") or "").strip() or (dataset.get("notes_sv") or "").strip():
        langs.add("sv")

    lang_scores = {3: 100, 2: 70, 1: 40, 0: 0}
    lang_score = lang_scores.get(len(langs), 0)
    details["languages"] = sorted(langs)
    details["language_score"] = lang_score

    # Enrichment-rikastukset
    if enrichment_count >= 5:
        enrich_score = 100.0
    elif enrichment_count >= 3:
        enrich_score = 70.0
    elif enrichment_count >= 1:
        enrich_score = 40.0
    else:
        enrich_score = 0.0
    details["enrichment_count"] = enrichment_count
    details["enrichment_score"] = enrich_score

    score = lang_score * 0.5 + enrich_score * 0.5
    return score, details


# --- Kokonaispisteytys ---


def calculate_quality(
    dataset: dict[str, Any],
    resources: list[dict[str, Any]],
    enrichment_count: int,
) -> dict[str, tuple[float, dict[str, Any]]]:
    """Laske kaikki laatudimensiot datasettille.

    Returns:
        Dict dimensio -> (pisteet, yksityiskohdat).
    """
    scores = {
        "completeness": calculate_completeness(dataset),
        "timeliness": calculate_timeliness(dataset),
        "accessibility": calculate_accessibility(dataset, resources),
        "documentation": calculate_documentation(dataset, enrichment_count),
    }

    # Kokonaispisteet
    overall = sum(
        scores[dim][0] * weight
        for dim, weight in DIMENSION_WEIGHTS.items()
    )
    overall_details = {
        dim: {"score": scores[dim][0], "weight": weight}
        for dim, weight in DIMENSION_WEIGHTS.items()
    }
    scores["overall"] = (overall, overall_details)

    return scores


# --- Agenttivalmius ---
#
# Nykyinen laatupiste mittaa **metatiedon täydellisyyttä**. Se on hyvä siinä
# mitä se mittaa, mutta se ei kerro pääseekö dataan käsiksi — ja agentille
# juuri jälkimmäinen ratkaisee. Mitattuna 1.9.2026: 434 datasettiä saa
# laatupisteet ≥ 85, ja niistä 67:n skeemaa ei tunneta lainkaan.
#
# Agenttivalmius on **rinnakkainen mittari, ei korjaus vanhaan**:
# ``DIMENSION_WEIGHTS`` pysyy ennallaan, joten ``overall`` tarkoittaa yhä
# samaa kuin ennen eikä yksikään olemassa oleva luku liiku.


@dataclass(frozen=True)
class AgentFacts:
    """Mitä probe on havainnut yhdestä datasetistä.

    ``probed`` on erillään muista tarkoituksella: probaamaton datasetti ei
    ole sama kuin probattu ja epäonnistunut. Ensimmäinen on meidän
    puutteemme, toinen palvelun.
    """

    probed: bool = False
    probe_ok: bool = False
    schema_known: bool = False
    available: bool | None = None
    auth_required: bool = False


#: Agenttivalmiuden osapisteet. Painot on valittu sen mukaan mikä *estää*
#: agentin, ei sen mukaan mikä on helppo mitata.
#:
#: Vastaamaton rajapinta ja tuntematon skeema ovat kumpikin täysiä esteitä:
#: ensimmäisestä ei saa dataa, jälkimmäisestä ei osaa muodostaa kyselyä.
#: Tunnistautuminen painaa vähemmän, koska ihminen voi hoitaa sen kerran —
#: kaatuvaa rajapintaa ei voi kiertää mitenkään.
_READINESS_WEIGHTS = {"endpoint_responds": 40.0, "schema_known": 40.0, "no_auth": 20.0}


def calculate_agent_readiness(
    facts: AgentFacts,
) -> tuple[float, dict[str, Any]] | None:
    """Pystyykö agentti hakemaan tästä dataa ilman ihmistä.

    Palauttaa ``None`` jos datasettiä ei ole probattu. Se ei ole nolla vaan
    **mittaamaton**, ja ero on olennainen: nolla väittäisi aineiston olevan
    käyttökelvoton, vaikka kyse on siitä ettemme ole katsoneet. Kutsuja
    jättää tällöin rivin kirjoittamatta — puuttuvan tilan näkee, keksityn
    ei. Sama periaate kuin 429:n kirjaamatta jättämisessä probessa.

    Returns:
        ``(pisteet, liput)`` tai ``None``. Liput kertovat *miksi* pisteet
        ovat mitä ovat: luku järjestää, liput selittävät.
    """
    if not facts.probed:
        return None

    liput = {
        "endpoint_responds": facts.probe_ok or facts.available is True,
        "schema_known": facts.schema_known,
        "no_auth": not facts.auth_required,
    }
    pisteet = sum(_READINESS_WEIGHTS[k] for k, ok in liput.items() if ok)
    return pisteet, {**liput, "auth_required": facts.auth_required}


def collect_agent_facts(conn: sqlite3.Connection) -> dict[str, AgentFacts]:
    """Kokoa probe-havainnot datasetiteittäin yhdellä kyselykierroksella.

    Vain probatut datasetit päätyvät tulokseen; muille ei ole mitään
    sanottavaa eikä niistä pidä keksiä mitään.
    """
    probattu: dict[str, bool] = {}
    for ds_id, status in conn.execute(
        "SELECT dataset_id, status FROM probe_results"
    ).fetchall():
        probattu[ds_id] = probattu.get(ds_id, False) or status == "ok"

    skeema = {
        r[0] for r in conn.execute("SELECT DISTINCT dataset_id FROM resource_schema")
    }
    # WMS-palvelulla ei ole sarakkeita mutta on layerit, ja PxWeb-taulun
    # muoto on dimensioissa. Kumpikin kelpaa "muoto tunnetaan" -tiedoksi.
    for kentta in ("service_layers", "data_fields"):
        skeema |= {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT dataset_id FROM enrichments WHERE field = ?",
                (kentta,),
            )
        }

    saatavilla: dict[str, bool] = {}
    for ds_id, avail in conn.execute(
        "SELECT dataset_id, MAX(is_available) FROM resource_health GROUP BY dataset_id"
    ).fetchall():
        saatavilla[ds_id] = bool(avail)

    auth = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT dataset_id FROM enrichments WHERE field = 'auth_method'"
            " AND value NOT IN ('none', 'avoin', '')"
        )
    }

    return {
        ds_id: AgentFacts(
            probed=True,
            probe_ok=ok,
            schema_known=ds_id in skeema,
            available=saatavilla.get(ds_id),
            auth_required=ds_id in auth,
        )
        for ds_id, ok in probattu.items()
    }


# --- Tietokantaoperaatiot ---


def save_quality_scores(
    conn: sqlite3.Connection,
    dataset_id: str,
    # Mapping eikä dict: funktio vain lukee, ja dict on invariantti
    # arvotyypissään. Ilman tätä ``calculate_quality``:n paluuarvoa
    # (jossa ei ole None-vaihtoehtoa) ei voisi antaa suoraan.
    scores: Mapping[str, tuple[float, dict[str, Any]] | None],
) -> None:
    """Tallenna laatupisteet tietokantaan.

    ``None`` tarkoittaa **mittaamatonta** eikä nollaa, joten sille ei
    kirjoiteta riviä. ``quality_scores.score`` on NOT NULL, mikä on tässä
    hyvä: puuttuvaa lukua ei voi vahingossa lukea nollaksi.
    """
    now = datetime.now(tz=UTC).isoformat()
    for dimension, arvo in scores.items():
        if arvo is None:
            continue
        score, details = arvo
        conn.execute(
            """
            INSERT INTO quality_scores (dataset_id, dimension, score, details, calculated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id, dimension) DO UPDATE SET
                score=excluded.score,
                details=excluded.details,
                calculated_at=excluded.calculated_at
            """,
            (dataset_id, dimension, score, json.dumps(details, ensure_ascii=False), now),
        )


def get_quality_scores(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> dict[str, Any] | None:
    """Hae datasetin laatupisteet."""
    rows = conn.execute(
        "SELECT dimension, score, details FROM quality_scores WHERE dataset_id = ?",
        (dataset_id,),
    ).fetchall()
    if not rows:
        return None
    result: dict[str, Any] = {}
    for row in rows:
        result[row["dimension"]] = {
            "score": row["score"],
            "details": json.loads(row["details"]) if row["details"] else {},
        }
    return result


def score_all_datasets(conn: sqlite3.Connection, source: str = "") -> int:
    """Laske laatupisteet kaikille dataseteille.

    Args:
        source: Rajaa lähteeseen (tyhjä = kaikki).

    Returns:
        Pisteytettyjen datasettien lukumäärä.
    """
    if source:
        rows = conn.execute(
            "SELECT * FROM datasets WHERE source = ?", (source,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM datasets").fetchall()

    # Hae kaikki resurssit ja enrichment-luvut kerralla (vältetään N+1)
    resources_by_ds: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in conn.execute("SELECT * FROM resources").fetchall():
        resources_by_ds[r["dataset_id"]].append(dict(r))

    enr_counts: dict[str, int] = dict(conn.execute(
        "SELECT dataset_id, COUNT(DISTINCT field) FROM enrichments GROUP BY dataset_id"
    ).fetchall())

    # Agenttivalmius lasketaan probe-havainnoista eikä metatiedosta, joten
    # se on oma kierroksensa. Probaamattomat puuttuvat sanakirjasta, ja
    # ``calculate_agent_readiness`` palauttaa niille None.
    agent_facts = collect_agent_facts(conn)

    count = 0
    for row in rows:
        dataset = dict(row)
        ds_id = dataset["id"]
        resources = resources_by_ds.get(ds_id, [])
        enrichment_count = enr_counts.get(ds_id, 0)

        scores: dict[str, tuple[float, dict[str, Any]] | None] = dict(
            calculate_quality(dataset, resources, enrichment_count)
        )
        scores["agent_readiness"] = calculate_agent_readiness(
            agent_facts.get(ds_id, AgentFacts())
        )
        save_quality_scores(conn, ds_id, scores)
        count += 1

    conn.commit()
    logger.info("Laatupisteet laskettu %d datasetille", count)
    return count


def analyze_metadata_gaps(
    conn: sqlite3.Connection,
    source: str = "",
) -> dict[str, Any]:
    """Analysoi metatiedon puutteet lähteittäin.

    Returns:
        Dict jossa lähdekohtaiset tilastot ja parannusehdotukset.
    """
    where = "WHERE d.source = ?" if source else ""
    params: list[str] = [source] if source else []

    # Perustilastot
    rows = conn.execute(
        f"""
        SELECT
            d.source,
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(d.notes_fi, '') = '' THEN 1 ELSE 0 END) as missing_desc,
            SUM(CASE WHEN COALESCE(d.keywords_fi, '[]') IN ('[]', '', '[""]')
                THEN 1 ELSE 0 END) as missing_keywords,
            SUM(CASE WHEN COALESCE(d.update_frequency, '') = '' THEN 1 ELSE 0 END)
                as missing_freq,
            SUM(CASE WHEN COALESCE(d.license_id, '') = '' THEN 1 ELSE 0 END)
                as missing_license,
            SUM(CASE WHEN COALESCE(d.title_en, '') = '' THEN 1 ELSE 0 END)
                as missing_title_en,
            SUM(CASE WHEN COALESCE(d.notes_en, '') = '' THEN 1 ELSE 0 END)
                as missing_notes_en
        FROM datasets d
        {where}
        GROUP BY d.source
        ORDER BY total DESC
        """,
        params,
    ).fetchall()

    sources: list[dict[str, Any]] = []
    # float eikä int: kentät ovat lukumääriä, mutta samaan dictiin kirjoitetaan
    # myös completeness_pct, joka on desimaaliluku. Lukumäärät pysyvät
    # ajonaikaisesti int-tyyppisinä.
    totals: dict[str, float] = {
        "total": 0,
        "missing_desc": 0,
        "missing_keywords": 0,
        "missing_freq": 0,
        "missing_license": 0,
        "missing_title_en": 0,
        "missing_notes_en": 0,
    }

    for row in rows:
        src: dict[str, Any] = dict(row)
        # Lasketaan täydellisyysprosentti
        total = src["total"]
        if total > 0:
            filled = sum(
                total - src.get(f, 0)
                for f in [
                    "missing_desc", "missing_keywords", "missing_freq",
                    "missing_license",
                ]
            )
            src["completeness_pct"] = round(100.0 * filled / (total * 4), 1)
        else:
            src["completeness_pct"] = 0.0

        sources.append(src)
        for key in totals:
            totals[key] += src.get(key, 0)

    total_all = totals["total"]
    if total_all > 0:
        filled_all = sum(
            total_all - totals[f]
            for f in [
                "missing_desc", "missing_keywords", "missing_freq",
                "missing_license",
            ]
        )
        totals["completeness_pct"] = round(
            100.0 * filled_all / (total_all * 4), 1,
        )
    else:
        totals["completeness_pct"] = 0.0

    return {
        "sources": sources,
        "totals": totals,
    }


def suggest_improvements(
    conn: sqlite3.Connection,
    source: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Ehdota helposti parannettavia datasettejä.

    Palauttaa datasetit joilla on eniten puutteita mutta jotka ovat
    helposti rikastettavissa.
    """
    where = "AND d.source = ?" if source else ""
    params: list[Any] = [source] if source else []

    rows = conn.execute(
        f"""
        SELECT * FROM (
            SELECT d.id, d.name,
                   COALESCE(d.title_fi, d.title) as title,
                   d.source,
                   d.organization_title as org,
                   (CASE WHEN COALESCE(d.notes_fi, '') = '' THEN 1 ELSE 0 END
                    + CASE WHEN COALESCE(d.keywords_fi, '[]') IN ('[]', '', '[""]')
                        THEN 1 ELSE 0 END
                    + CASE WHEN COALESCE(d.update_frequency, '') = '' THEN 1 ELSE 0 END
                    + CASE WHEN COALESCE(d.license_id, '') = '' THEN 1 ELSE 0 END
                   ) as gap_count,
                   CASE WHEN COALESCE(d.notes_fi, '') = ''
                       THEN 'kuvaus' ELSE '' END as m1,
                   CASE WHEN COALESCE(d.keywords_fi, '[]') IN ('[]', '', '[""]')
                       THEN 'avainsanat' ELSE '' END as m2,
                   CASE WHEN COALESCE(d.update_frequency, '') = ''
                       THEN 'päivitystiheys' ELSE '' END as m3,
                   CASE WHEN COALESCE(d.license_id, '') = ''
                       THEN 'lisenssi' ELSE '' END as m4
            FROM datasets d
            WHERE 1=1 {where}
        ) sub
        WHERE gap_count > 0
        ORDER BY gap_count DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        missing = [
            v for v in [row["m1"], row["m2"], row["m3"], row["m4"]] if v
        ]
        results.append({
            "id": row["id"],
            "name": row["name"],
            "title": row["title"],
            "source": row["source"],
            "org": row["org"],
            "gap_count": row["gap_count"],
            "missing_fields": missing,
        })

    return results


def _keyword_count(dataset: dict[str, Any]) -> int:
    """Palauta avainsanojen lukumäärä (JSON-string tai lista)."""
    return len(parse_json_list(dataset.get("keywords_fi", "[]")))
