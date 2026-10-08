"""Tutkimustyökalut: log_finding, list_findings, save_session_findings."""

from __future__ import annotations

from datetime import UTC, datetime

from fastmcp import Context

import aura.server as _server
from aura.database import add_enrichment, get_dataset, get_latest_enrichments
from aura.server import mcp

# Category-to-enrichment-field mapping for save_session_findings
_CATEGORY_FIELD_MAP: dict[str, str] = {
    "quality": "quality_notes",
    "access": "access_instructions",
    "content": "data_fields",
    "description": "description_extended",
    "use_case": "use_case",
    "temporal": "temporal_coverage",
    "api": "api_endpoint",
    "general": "description_extended",
}

VALID_FINDING_CATEGORIES = set(_CATEGORY_FIELD_MAP.keys())

_fallback_findings: list[dict[str, str]] = []

#: Enintään näin monen istunnon löydökset muistissa; vanhin poistuu ensin.
MAX_SESSIONS = 200
#: Enintään näin monta löydöstä istuntoa kohden.
MAX_FINDINGS = 100
#: Löydöksen enimmäispituus merkkeinä.
MAX_FINDING_LENGTH = 2000


def _get_findings(ctx: Context | None) -> list[dict[str, str]]:
    """Hae **tämän istunnon** löydöslista.

    Löydökset erotellaan istunnoittain. Aiemmin koko prosessilla oli yksi
    lista, jolloin julkisessa /mcp/laatu-profiilissa käyttäjä näki toisen
    kirjaamat tekstit ja lista kasvoi rajatta (8.10.2026). Tilattomassa
    HTTP:ssä istuntoa ei ole: silloin lista on kutsukohtainen eikä jaettu.
    Ilman kontekstia palautetaan moduulitason lista (testit).
    """
    if ctx is None:
        return _fallback_findings
    try:
        store = ctx.lifespan_context["findings"]
    except (AttributeError, KeyError):
        return _fallback_findings
    try:
        session = str(ctx.session_id)
    except Exception:  # noqa: BLE001 — tilaton HTTP: ei istuntoa
        return []
    if not isinstance(store, dict):
        return _fallback_findings
    if session not in store:
        while len(store) >= MAX_SESSIONS:
            store.pop(next(iter(store)))
        store[session] = []
    findings: list[dict[str, str]] = store[session]
    return findings


def reset_findings() -> None:
    """Tyhjennä fallback-findings. Käytetään testeissä."""
    _fallback_findings.clear()


@mcp.tool(tags={"quality"})
def log_finding(
    dataset_id: str,
    finding: str,
    category: str = "general",
    ctx: Context | None = None,
) -> str:
    """Kirjaa löydös tutkimuksen aikana. Tallentuu session lokiin.

    Kevyempi kuin enrich() — ei vaadi tarkkaa kenttä/arvo-mappingia.
    Session lopussa löydökset voi tallentaa enrichmenteiksi
    kutsumalla save_session_findings().

    Args:
        dataset_id: Datasetin ID tai nimi
        finding: Löydös vapaana tekstinä
        category: Kategoria: "quality", "access", "content", "description",
            "use_case", "temporal", "api", "general"
    """
    if category not in VALID_FINDING_CATEGORIES:
        return (
            f"Tuntematon kategoria '{category}'. "
            f"Valitse: {', '.join(sorted(VALID_FINDING_CATEGORIES))}"
        )

    findings = _get_findings(ctx)
    if len(findings) >= MAX_FINDINGS:
        return f"Istunnossa on jo {MAX_FINDINGS} löydöstä; tallenna tai aloita uusi istunto."
    findings.append({
        "dataset_id": dataset_id[:200],
        "finding": finding[:MAX_FINDING_LENGTH],
        "category": category,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })

    return (
        f"Löydös kirjattu ({len(findings)} session aikana). "
        f"Datasetti: {dataset_id}, kategoria: {category}."
    )


@mcp.tool(tags={"quality"})
def list_findings(ctx: Context | None = None) -> str:
    """Näytä session aikana kirjatut löydökset.

    Palauttaa kaikki log_finding()-kutsulla tallennetut löydökset.
    """
    findings = _get_findings(ctx)

    if not findings:
        return "Ei löydöksiä tässä sessiossa."

    # Ryhmittele datasetin mukaan
    by_dataset: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        by_dataset.setdefault(f["dataset_id"], []).append(f)

    parts = [f"# Session löydökset ({len(findings)} kpl)\n"]
    for ds_id, ds_findings in by_dataset.items():
        parts.append(f"## {ds_id}")
        for f in ds_findings:
            parts.append(f"- [{f['category']}] {f['finding']}")
        parts.append("")

    return "\n".join(parts)


@mcp.tool()
def save_session_findings(ctx: Context | None = None) -> str:
    """Tallenna session aikana kerätyt löydökset enrichmenteiksi.

    Analysoi log_finding()-kutsut, mappaa sopiviin enrichment-kenttiin,
    deduplikoi olemassaolevien kanssa ja tallentaa uudet.
    """
    conn = _server._get_conn(ctx)
    findings = _get_findings(ctx)

    if not findings:
        return "Ei löydöksiä tallennettavaksi."

    saved: list[str] = []
    skipped: list[str] = []

    # Ryhmittele datasetin ja kategorian mukaan
    grouped: dict[tuple[str, str], list[str]] = {}
    for f in findings:
        key = (f["dataset_id"], f["category"])
        grouped.setdefault(key, []).append(f["finding"])

    for (ds_id, category), finding_texts in grouped.items():
        field = _CATEGORY_FIELD_MAP.get(category, "description_extended")

        # Yhdistä saman kategorian löydökset
        combined = "; ".join(finding_texts) if len(finding_texts) > 1 else finding_texts[0]

        # Tarkista duplikaatit
        existing = get_latest_enrichments(conn, ds_id)
        already_exists = any(
            e.get("field") == field and e.get("value") == combined
            for e in existing
        )

        if already_exists:
            skipped.append(f"- {ds_id}/{field} (duplikaatti)")
            continue

        if not get_dataset(conn, ds_id):
            skipped.append(f"- {ds_id}/{field} (datasetti ei löydy)")
            continue

        add_enrichment(
            conn, ds_id, field, combined,
            confidence="medium",
            source_type="mcp_session",
            source_detail="research_log",
        )
        saved.append(f"- {ds_id}/{field}")

    # Tyhjennä löydökset
    findings.clear()

    parts: list[str] = []
    if saved:
        parts.append(f"Tallennettu {len(saved)} rikastusta:")
        parts.extend(saved)
    if skipped:
        parts.append(f"\nOhitettu {len(skipped)} (duplikaatit):")
        parts.extend(skipped)
    if not saved and not skipped:
        parts.append("Ei uusia rikastuksia tallennettavaksi.")

    return "\n".join(parts)
