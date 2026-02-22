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


def _get_findings(ctx: Context | None) -> list[dict[str, str]]:
    """Hae session-tason findings-lista lifespan-kontekstista.

    MCP-kontekstilla palauttaa session oman listan.
    Ilman kontekstia palauttaa module-level fallbackin (testit).
    """
    if ctx is not None:
        try:
            findings: list[dict[str, str]] = ctx.lifespan_context["findings"]
            return findings
        except (AttributeError, KeyError):
            pass
    return _fallback_findings


def reset_findings() -> None:
    """Tyhjennä fallback-findings. Käytetään testeissä."""
    _fallback_findings.clear()


@mcp.tool()
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
    findings.append({
        "dataset_id": dataset_id,
        "finding": finding,
        "category": category,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })

    return (
        f"Löydös kirjattu ({len(findings)} session aikana). "
        f"Datasetti: {dataset_id}, kategoria: {category}."
    )


@mcp.tool()
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
